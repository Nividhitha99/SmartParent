"""RAG helpers with lazy external-client initialization."""
import json
import os
from functools import lru_cache

import anthropic
import chromadb
from chromadb.utils import embedding_functions


@lru_cache(maxsize=1)
def _anthropic_client():
    """Create the provider client only when a RAG request needs it."""
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


@lru_cache(maxsize=1)
def _collection():
    """Open the persistent vector collection on first RAG use, not API startup."""
    chroma_client = chromadb.PersistentClient(
        path=os.getenv("CHROMA_PATH", "rag_db")
    )
    return chroma_client.get_or_create_collection(
        name="smartparent",
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
    )


def add_knowledge(docs: list[dict]):
    """Add {id, text} documents to the SmartParent knowledge base."""
    _collection().add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
    )


def query_knowledge(query: str, k: int = 3):
    """Retrieve up to k relevant documents from the vector knowledge base."""
    results = _collection().query(query_texts=[query], n_results=k)
    return results["documents"][0] if results and results["documents"] else []


def generate_plan_with_rag(user_prompt: str) -> dict:
    try:
        retrieved_docs = query_knowledge(user_prompt)
        system_msg = (
            "You are SmartParent Planner AI. "
            "Always return valid JSON with keys: title, category, ingredients (or items), steps."
        )
        response = _anthropic_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_msg,
            messages=[{
                "role": "user",
                "content": f"Task: {user_prompt}\\nRelevant docs:\\n{retrieved_docs}",
            }],
        )
        return json.loads(response.content[0].text)
    except Exception as exc:
        return {
            "title": user_prompt,
            "category": "general",
            "ingredients": [],
            "steps": [f"LLM error: {exc}"],
        }
