# main.py
# FastAPI app with Swagger for uploading a weekly menu image
# and returning per-day / per-meal steps.
from dotenv import load_dotenv
load_dotenv()
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rag_llm import generate_plan_with_rag
from db import plans, tasks, reminders
import uuid
import datetime
from nlp_parser import parse_menu_image, parse_text_to_tasks, build_plan_from_menu, build_plan
from kafka_producer import publish_plan_event
from recipe_service import generate_recipes
from kafka_consumer import start_consumer, create_reminder_from_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Kafka consumer in a daemon thread at startup.
    # Fails gracefully if broker is unavailable.
    loop = asyncio.get_event_loop()
    start_consumer(loop)
    yield


app = FastAPI(
    title="SmartParent Planner",
    description="Upload a school menu image (weekly grid) and get day/meal plan.",
    version="1.1.0",
    lifespan=lifespan,
)

# Optional CORS (enable if you call from web apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextIn(BaseModel):
    text: str


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

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/plan-to-upload")
async def plan_to_upload(file: UploadFile = File(...)):
    """
    Upload a weekly menu IMAGE (e.g., JPEG/PNG).
    Returns per-day steps, a deduplicated shopping list, and short recipes for each food.
    """
    content = await file.read()
    menu = parse_menu_image(content)
    plan = build_plan_from_menu(menu)

    shopping_list = _build_shopping_list(plan["steps"])
    recipes = generate_recipes(shopping_list)

    plan["shopping_list"] = shopping_list
    plan["recipes"] = recipes
    return JSONResponse(plan)

@app.post("/plan-from-text")
async def plan_from_text(text: str = Form(...)):
    """
    Post raw OCR text or a circular note.
    Returns steps, a deduplicated shopping list, and short recipes for each food.
    Saves plan to MongoDB and publishes a Kafka event.
    """
    parsed = parse_text_to_tasks(text)
    plan = build_plan(parsed)

    shopping_list = _build_shopping_list(plan["steps"])
    recipes = generate_recipes(shopping_list)

    plan["shopping_list"] = shopping_list
    plan["recipes"] = recipes

    await plans.insert_one(plan.copy())
    publish_plan_event(plan)

    return JSONResponse(plan)

@app.post("/llm-plan")
async def llm_plan(note: str = Body(..., embed=True)):
    plan = generate_plan_with_rag(note)

    job_id = str(uuid.uuid4())

    # save to MongoDB
    await plans.insert_one({
        "job_id": job_id,
        "note": note,
        "plan": plan,
        "created_at": datetime.datetime.utcnow()
    })

    return {"job_id": job_id, "plan": plan}

AI_TRIGGERS = ["make", "prepare", "build", "do", "experiment", "project", "science", "cook"]

@app.post("/plan-auto")
async def plan_auto(note: str = Body(..., embed=True)):
    text = note.lower()

    # If text contains AI trigger keywords → use LLM
    if any(word in text for word in AI_TRIGGERS):
        plan = generate_plan_with_rag(note)
        return {"mode": "llm", "plan": plan}

    # Otherwise → use NLP parser
    parsed = parse_text_to_tasks(note)
    plan = build_plan(parsed)
    return {"mode": "parser", "plan": plan}


# ---------------------------------------------------------------------------
# Feature 2 — Homework & Project Tracking
# ---------------------------------------------------------------------------

class TaskOut(BaseModel):
    task_id: str
    title: str
    project_name: Optional[str]
    type: str                        # "homework" | "project" | "event" | "supply"
    deadline_date: Optional[str]
    deadline_time: Optional[str]
    supplies: List[str]
    done: bool
    created_at: str                  # ISO string for JSON serialisation

    class Config:
        # Allows constructing from a plain dict (e.g. MongoDB doc)
        populate_by_name = True

    @classmethod
    def from_doc(cls, doc: dict) -> "TaskOut":
        return cls(
            task_id=doc["task_id"],
            title=doc["title"],
            project_name=doc.get("project_name"),
            type=doc.get("type", "homework"),
            deadline_date=doc.get("deadline_date"),
            deadline_time=doc.get("deadline_time"),
            supplies=doc.get("supplies", []),
            done=doc.get("done", False),
            created_at=doc["created_at"].isoformat() if hasattr(doc.get("created_at"), "isoformat") else str(doc.get("created_at", "")),
        )


def _infer_task_type(parsed) -> str:
    """Infer whether this note describes a project, event, supply run, or homework."""
    if parsed.event in ("project", "science"):
        return "project"
    if parsed.event in ("competition", "field trip", "sports day", "assembly", "picnic",
                        "presentation", "rehearsal"):
        return "event"
    if parsed.supplies and not parsed.event:
        return "supply"
    return "homework"


@app.post("/tasks/from-note", response_model=TaskOut)
async def create_task_from_note(note: str = Body(..., embed=True)):
    """
    Parse free-form text (homework note, circular, reminder) into a structured
    task and persist it to MongoDB.
    """
    parsed = parse_text_to_tasks(note)
    task_type = _infer_task_type(parsed)

    # Use event name as title when available; fall back to first supply or raw text snippet
    if parsed.event:
        title = parsed.event.title()
    elif parsed.supplies:
        title = f"Get supplies: {', '.join(parsed.supplies[:3])}"
    else:
        title = (note[:60] + "…") if len(note) > 60 else note

    # project_name is the title when it is project-type
    project_name = title if task_type == "project" else None

    doc = {
        "task_id": str(uuid.uuid4()),
        "title": title,
        "project_name": project_name,
        "type": task_type,
        "deadline_date": parsed.date,
        "deadline_time": parsed.time,
        "supplies": parsed.supplies,
        "done": False,
        "created_at": datetime.datetime.utcnow(),
    }

    await tasks.insert_one(doc)

    # Dual-write: if this task has a deadline or is an event, also create a reminder
    # directly in MongoDB (works even when Kafka is down).
    if parsed.date or parsed.event:
        await create_reminder_from_task(
            event_name=title,
            date=parsed.date,
            time=parsed.time,
        )

    return TaskOut.from_doc(doc)


@app.get("/tasks", response_model=list[TaskOut])
async def list_tasks():
    """Return all tasks, newest first."""
    cursor = tasks.find({}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [TaskOut.from_doc(d) for d in docs]


@app.patch("/tasks/{task_id}/done", response_model=TaskOut)
async def toggle_task_done(task_id: str):
    """Flip the done flag on a task."""
    doc = await tasks.find_one({"task_id": task_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")

    new_done = not doc.get("done", False)
    await tasks.update_one({"task_id": task_id}, {"$set": {"done": new_done}})
    doc["done"] = new_done
    return TaskOut.from_doc(doc)


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Permanently delete a task."""
    result = await tasks.delete_one({"task_id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": task_id}


# ---------------------------------------------------------------------------
# Feature 3 — Smart Reminders
# ---------------------------------------------------------------------------

class ReminderOut(BaseModel):
    reminder_id: str
    event_name: str
    date: Optional[str]
    time: Optional[str]
    source: str          # "plan" | "task"
    dismissed: bool
    created_at: str      # ISO string

    @classmethod
    def from_doc(cls, doc: dict) -> "ReminderOut":
        return cls(
            reminder_id=doc["reminder_id"],
            event_name=doc["event_name"],
            date=doc.get("date"),
            time=doc.get("time"),
            source=doc.get("source", "task"),
            dismissed=doc.get("dismissed", False),
            created_at=(
                doc["created_at"].isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else str(doc.get("created_at", ""))
            ),
        )


@app.get("/reminders", response_model=list[ReminderOut])
async def list_reminders():
    """Return all non-dismissed reminders, newest first."""
    cursor = reminders.find({"dismissed": False}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    return [ReminderOut.from_doc(d) for d in docs]


@app.patch("/reminders/{reminder_id}/dismiss", response_model=ReminderOut)
async def dismiss_reminder(reminder_id: str):
    """Mark a reminder as dismissed."""
    doc = await reminders.find_one({"reminder_id": reminder_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await reminders.update_one(
        {"reminder_id": reminder_id}, {"$set": {"dismissed": True}}
    )
    doc["dismissed"] = True
    return ReminderOut.from_doc(doc)

