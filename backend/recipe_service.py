# recipe_service.py
# Generates short recipes for a list of food items using Claude Haiku.
# All items are batched into a single API call to keep latency and token cost low.

import json
import os
import re
from typing import List
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_SYSTEM_PROMPT = (
    "You are a helpful meal-prep assistant for parents. "
    "Given a list of food items, return a JSON array where each element has exactly these keys: "
    '"food" (string, the item name), '
    '"ingredients" (array of strings, 3-6 items), '
    '"steps" (array of strings, 2-4 short steps), '
    '"prep_time_mins" (integer). '
    "Return ONLY the JSON array, no markdown, no extra text."
)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences Claude sometimes wraps around JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_recipes(food_items: List[str]) -> List[dict]:
    """
    Generate short recipes for each food item in one batched Claude Haiku call.
    Returns a list of recipe dicts. Returns [] on any error — never raises.
    """
    if not food_items:
        return []

    # Deduplicate while preserving order
    seen, unique = set(), []
    for item in food_items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    user_msg = "Food items: " + ", ".join(unique)

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
        )
        raw = resp.content[0].text or ""
        raw = _strip_code_fences(raw)
        recipes = json.loads(raw)

        # Validate it's a list; drop any malformed entries
        if not isinstance(recipes, list):
            return []

        cleaned = []
        for r in recipes:
            if not isinstance(r, dict):
                continue
            cleaned.append({
                "food": str(r.get("food", "")),
                "ingredients": [str(i) for i in r.get("ingredients", [])],
                "steps": [str(s) for s in r.get("steps", [])],
                "prep_time_mins": int(r.get("prep_time_mins", 0)),
            })
        return cleaned

    except Exception as e:
        print(f"[recipe_service] Error generating recipes: {e}")
        return []
