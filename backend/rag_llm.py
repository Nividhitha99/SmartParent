import os, json
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# OpenAI client for embeddings + chat
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- ChromaDB setup (persistent local vector DB) ---
chroma_client = chromadb.PersistentClient(path="rag_db")

collection = chroma_client.get_or_create_collection(
    name="smartparent",
    embedding_function=embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
)

def add_knowledge(docs: list[dict]):
    """
    Add docs to Chroma knowledge base.
    Example:
    docs = [
      {"id":"recipe1","text":"Chickpeas salad recipe: ingredients: chickpeas, cucumber... steps: ..."},
      {"id":"proj1","text":"Volcano project: materials: baking soda, vinegar... steps: ..."}
    ]
    """
    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs]
    )

def query_knowledge(query: str, k: int = 3):
    """Retrieve top-k relevant docs for a query"""
    results = collection.query(query_texts=[query], n_results=k)
    return results["documents"][0] if results and results["documents"] else []

def generate_plan_with_rag(user_prompt: str) -> dict:
    try:
        retrieved_docs = query_knowledge(user_prompt)

        system_msg = (
            "You are SmartParent Planner AI. "
            "Always return valid JSON with keys: title, category, ingredients (or items), steps."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Task: {user_prompt}\nRelevant docs:\n{retrieved_docs}"}
            ]
        )

        content = resp.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        print("🔥 ERROR in LLM:", e)
        return {
            "title": user_prompt,
            "category": "general",
            "ingredients": [],
            "steps": [f"LLM error: {str(e)}"]
        }
