# main.py
# FastAPI app with Swagger for uploading a weekly menu image
# and returning per-day / per-meal steps.
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi import Body
from rag_llm import generate_plan_with_rag
from db import plans
import uuid
import datetime
from nlp_parser import parse_text_to_tasks, build_plan
from kafka_producer import publish_plan_event



from nlp_parser import (
    parse_menu_image,
    parse_text_to_tasks,
    build_plan_from_menu,
    build_plan,
)

app = FastAPI(
    title="SmartParent Planner",
    description="Upload a school menu image (weekly grid) and get day/meal plan.",
    version="1.1.0",
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

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/plan-to-upload")
async def plan_to_upload(file: UploadFile = File(...)):
    """
    Upload a weekly menu IMAGE (e.g., JPEG/PNG).
    We parse the table grid per cell and return steps grouped per weekday & meal.
    If grid parsing finds nothing, we reconstruct per-day meals from OCR text.
    """
    content = await file.read()
    menu = parse_menu_image(content)     # structured per_day + all_foods + raw_text
    steps = build_plan_from_menu(menu)   # builds steps using per_day first (with fallback)
    return JSONResponse(steps)

@app.post("/plan-from-text")
async def plan_from_text(text: str = Form(...)):
    """
    If you already have OCR text or a normal circular note, post raw text here.
    This returns a plan using best-effort extraction (no per-day grid).
    """
    parsed = parse_text_to_tasks(text)
    return JSONResponse(build_plan(parsed))

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

@app.post("/plan-from-text")
async def plan_from_text(text: str = Form(...)):
    parsed = parse_text_to_tasks(text)
    plan = build_plan(parsed)

    # Save to MongoDB
    await plans_collection.insert_one(plan)

    # Send to Kafka
    publish_plan_event(plan)

    return JSONResponse(plan)
