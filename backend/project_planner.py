# project_planner.py
# Classifies a circular/note as food, project/activity, or other. For activities,
# generates a materials list (with purchase links) and a day-by-day task breakdown
# toward the deadline. For food notes, extracts per-day/per-meal food items from
# freeform text (more robust than a fixed keyword dictionary). All via Claude Haiku.

import base64
import json
import os
import re
import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _amazon_search_link(query: str) -> str:
    return f"https://www.amazon.com/s?k={quote_plus(query)}"


def _maps_search_link(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _image_block(image_bytes: bytes, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type or "image/jpeg",
            "data": base64.b64encode(image_bytes).decode("utf-8"),
        },
    }


def _next_school_day(today: datetime.date) -> datetime.date:
    """Tomorrow, skipping to Monday if tomorrow falls on a weekend."""
    d = today + datetime.timedelta(days=1)
    while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        d += datetime.timedelta(days=1)
    return d


_CLASSIFY_SYSTEM = (
    "Classify the following school circular/note into exactly one category:\n"
    '"food" — a food/lunch/snack menu for one or more days.\n'
    '"activity" — anything academic or school-related that the student needs to '
    "prepare for or work on: a project, homework, an assignment, exam/test prep, "
    "or getting ready for a competition, science fair, art/craft activity, or "
    "similar — i.e. it requires materials and/or a sequence of steps or study "
    "leading up to a date.\n"
    '"other" — anything else (routine events, dress code, supply lists, general '
    "reminders) with no clear food or academic-activity content.\n"
    "Respond with only the single lowercase word: food, activity, or other."
)


def classify_circular(text: str) -> str:
    """Return 'food', 'activity', or 'other'. Defaults to 'other' on any error."""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=_CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": text}],
            temperature=0,
        )
        raw = (resp.content[0].text or "").strip().lower()
        for kind in ("food", "activity", "other"):
            if kind in raw:
                return kind
    except Exception as e:
        print(f"[project_planner] classify error: {e}")
    return "other"


def classify_circular_image(image_bytes: bytes, media_type: str) -> str:
    """Same classification as classify_circular, but reads the image directly via
    vision instead of relying on OCR text — important for homework with math
    notation, diagrams, etc. that OCR mangles. Defaults to 'other' on any error."""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=_CLASSIFY_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    _image_block(image_bytes, media_type),
                    {"type": "text", "text": "Classify this image."},
                ],
            }],
            temperature=0,
        )
        raw = (resp.content[0].text or "").strip().lower()
        for kind in ("food", "activity", "other"):
            if kind in raw:
                return kind
    except Exception as e:
        print(f"[project_planner] image classify error: {e}")
    return "other"


def _activity_system(default_deadline: str) -> str:
    today = datetime.date.today().isoformat()
    return (
        "You are a helpful assistant helping a child complete or prepare for a "
        "school activity — this could be a homework assignment/worksheet, a "
        "project, exam/test prep, or getting ready for a competition. Today's "
        f"date is {today}. If the note does not mention a deadline/due date, use "
        f"{default_deadline} (the next school day) as the deadline. Given the "
        "circular/note/homework content, return ONLY valid JSON with exactly "
        "these keys:\n"
        '"activity_type" (one of "assignment", "project", or "prep" — '
        '"assignment" for homework/worksheets with concrete problems or '
        'questions to answer, "project" for something to build/create/research '
        'over multiple days, "prep" for studying/practicing for a test or '
        "competition with no single deliverable),\n"
        '"title" (short string naming the activity),\n'
        '"deadline_date" (string YYYY-MM-DD — the mentioned/inferred due date, '
        f'or {default_deadline} if none is given),\n'
        '"materials" (array of strings — materials or study resources needed; '
        "empty array if genuinely none needed),\n"
        '"daily_plan" (array of objects, each with "date" (YYYY-MM-DD), '
        '"day_label" (e.g. "Day 1" or a weekday name), and "tasks" (array of '
        "short strings) — break the work needed (building, writing, studying, "
        "practicing, gathering materials, solving problems, etc. as "
        "appropriate) into a sensible sequence spread across the days between "
        "today and the deadline),\n"
        '"solutions" (array of objects, each with "question" and "solution" — '
        "if the note contains specific problems or questions (e.g. math "
        "problems, worksheet questions), work through and answer EVERY one of "
        "them here with clear step-by-step reasoning; otherwise an empty "
        "array).\n"
        "Return ONLY the JSON object, no markdown, no extra text."
    )


def _clean_activity_data(data: dict, default_deadline: str) -> Dict:
    materials: List[str] = [str(m) for m in data.get("materials", [])]

    daily_plan = []
    for d in data.get("daily_plan", []):
        if not isinstance(d, dict):
            continue
        daily_plan.append({
            "date": d.get("date"),
            "day_label": str(d.get("day_label", "")),
            "tasks": [str(t) for t in d.get("tasks", [])],
        })

    solutions = []
    for s in data.get("solutions", []):
        if not isinstance(s, dict):
            continue
        solutions.append({
            "question": str(s.get("question", "")),
            "solution": str(s.get("solution", "")),
        })

    activity_type = str(data.get("activity_type") or "project").lower()
    if activity_type not in ("assignment", "project", "prep"):
        activity_type = "project"

    return {
        "activity_type": activity_type,
        "title": str(data.get("title") or "School Activity"),
        "deadline_date": data.get("deadline_date") or default_deadline,
        "materials": [
            {
                "name": m,
                "amazon_url": _amazon_search_link(m),
                "maps_url": _maps_search_link(f"{m} store near me"),
            }
            for m in materials
        ],
        "daily_plan": daily_plan,
        "solutions": solutions,
    }


def _empty_activity(default_deadline: str) -> Dict:
    return {
        "activity_type": "project",
        "title": "School Activity",
        "deadline_date": default_deadline,
        "materials": [],
        "daily_plan": [],
        "solutions": [],
    }


def generate_activity_plan(text: str) -> Dict:
    """
    Generate an activity type, title, deadline (defaulting to the next school day
    if unmentioned), materials (with purchase links), a day-by-day task plan, and
    worked solutions for any concrete problems/questions in the note. Works for
    projects, homework, assignments, and competition prep alike. Returns an
    empty-shaped dict on any error — never raises.
    """
    default_deadline = _next_school_day(datetime.date.today()).isoformat()
    system = _activity_system(default_deadline)

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": text}],
            temperature=0.3,
        )
        raw = _strip_code_fences(resp.content[0].text or "")
        data = json.loads(raw)
        return _clean_activity_data(data, default_deadline)

    except Exception as e:
        print(f"[project_planner] generate error: {e}")
        return _empty_activity(default_deadline)


def generate_activity_plan_from_image(image_bytes: bytes, media_type: str) -> Dict:
    """
    Same as generate_activity_plan, but reads the homework/activity directly from
    the image via vision instead of OCR text — important for math notation,
    diagrams, and handwriting that OCR would otherwise mangle.
    """
    default_deadline = _next_school_day(datetime.date.today()).isoformat()
    system = _activity_system(default_deadline)

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    _image_block(image_bytes, media_type),
                    {
                        "type": "text",
                        "text": (
                            "Here is a photo of the homework/activity note. Read "
                            "it carefully, including any problems or questions "
                            "shown, and respond with the JSON described."
                        ),
                    },
                ],
            }],
            temperature=0.3,
        )
        raw = _strip_code_fences(resp.content[0].text or "")
        data = json.loads(raw)
        return _clean_activity_data(data, default_deadline)

    except Exception as e:
        print(f"[project_planner] image generate error: {e}")
        return _empty_activity(default_deadline)


_FOOD_SYSTEM = (
    "You are a helpful assistant extracting a food/lunch/snack menu from a parent's "
    "note or school circular. Identify every distinct food or drink item mentioned, "
    "however casually phrased (e.g. \"pasta\" is a food item). Group items by day and "
    "meal whenever the text specifies them. Return ONLY valid JSON: an array of "
    'objects, each with keys "day" (a weekday name if mentioned, else null), "meal" '
    '(e.g. "Lunch", "Breakfast", "Snack" if mentioned, else null), and "items" (array '
    'of short, normally-capitalized food/drink item names, e.g. "Pasta", "2% Milk"). '
    "If the note describes only one day/meal, return a single-element array. If no "
    "food or drink items are mentioned at all, return an empty array []. Return ONLY "
    "the JSON array, no markdown, no extra text."
)


def generate_food_items(text: str) -> List[Dict]:
    """
    Extract per-day/per-meal food items from freeform circular text using Claude.
    Returns [] if no food items are found or on any error — never raises.
    """
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_FOOD_SYSTEM,
            messages=[{"role": "user", "content": text}],
            temperature=0.2,
        )
        raw = _strip_code_fences(resp.content[0].text or "")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []

        cleaned = []
        for d in data:
            if not isinstance(d, dict):
                continue
            items = [str(i).strip() for i in d.get("items", []) if str(i).strip()]
            if not items:
                continue
            cleaned.append({
                "day": d.get("day"),
                "meal": d.get("meal"),
                "items": items,
            })
        return cleaned
    except Exception as e:
        print(f"[project_planner] food extraction error: {e}")
        return []
