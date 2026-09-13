"""Specialist planning tools reused by the LangGraph text workflow."""
from project_planner import generate_activity_plan, generate_food_items
from recipe_service import generate_recipes
from nlp_parser import (parse_text_to_tasks, build_plan, build_step,
    build_supply_dress_event_steps, _when_string)

def _build_shopping_list(steps: list) -> list[str]:
    """
    Collect all items from 'buy' steps across the plan and deduplicate them.
    'pack' steps carry the same items, so we skip them to avoid doubling up.
    """
    seen, shopping = set(), []
    for step in steps:
        if step.get("type") != "buy":
            continue
        for item in step.get("items", []):
            key = item.lower().strip()
            if key not in seen:
                seen.add(key)
                shopping.append(item)
    return shopping


def plan_activity(text: str) -> dict:
    activity = generate_activity_plan(text)
    plan = {
        "kind": "activity",
        "raw_text": text,
        "steps": [],
        "shopping_list": [],
        "recipes": [],
        "activity_type": activity["activity_type"],
        "title": activity["title"],
        "deadline_date": activity["deadline_date"],
        "materials": activity["materials"],
        "daily_plan": activity["daily_plan"],
        "solutions": activity["solutions"],
    }
    return plan


def plan_food(text: str) -> dict:
    # Non-food signals (supplies/dress code/events) still come from the
    # regex-based parser; food items come from the LLM, which handles
    # freeform phrasing (e.g. bare "pasta") that a fixed keyword list misses,
    # and can group items by day/meal when the note covers more than one day.
    parsed = parse_text_to_tasks(text)
    when = _when_string(parsed)
    food_items = generate_food_items(text)

    steps: list = []
    if food_items:
        for entry in food_items:
            day = entry.get("day")
            meal = entry.get("meal")
            items = entry["items"]
            label = " – ".join([b for b in [day, meal] if b]) or (when or "the day")
            step_when = day or when
            steps.append(build_step("buy", f"Buy items for {label}", items, step_when, "grocery store near me"))
            steps.append(build_step("pack", f"Prepare/pack for {label}", items, step_when, "grocery store near me"))
    elif parsed.foods:
        # Fallback if the LLM call errored out — keyword-based extraction.
        steps.append(build_step("buy", f"Buy items for {when or 'the day'} – Lunch/Snack", parsed.foods, when, "grocery store near me"))
        steps.append(build_step("pack", f"Prepare/pack for {when or 'the day'} – Lunch/Snack", parsed.foods, when, "grocery store near me"))

    steps.extend(build_supply_dress_event_steps(parsed, when))

    if not steps:
        steps.append(build_step("reminder", "Review the note and add tasks (no food/supplies detected)", [], when, None))

    steps.append(build_step("reminder", "Set pickup/drop plan (consider carpool; check daycare/after-school if needed)", [], when, "daycare near me"))

    shopping_list = _build_shopping_list(steps)
    recipes = generate_recipes(shopping_list) if shopping_list else []

    plan = {
        "kind": "food",
        "raw_text": text,
        "steps": steps,
        "shopping_list": shopping_list,
        "recipes": recipes,
        "activity_type": None,
        "title": None,
        "deadline_date": None,
        "materials": [],
        "daily_plan": [],
        "solutions": [],
    }
    return plan


def plan_other(text: str) -> dict:
    parsed = parse_text_to_tasks(text)
    plan = build_plan(parsed)

    plan["kind"] = "other"
    plan["shopping_list"] = []
    plan["recipes"] = []
    plan["activity_type"] = None
    plan["title"] = None
    plan["deadline_date"] = None
    plan["materials"] = []
    plan["daily_plan"] = []
    plan["solutions"] = []
    return plan


