# SmartParent

An AI-powered parenting assistant that turns school circulars, menu images, and homework notes into actionable weekly plans — with shopping lists, recipes, task tracking, and smart reminders.

---

## What it does

### Lunchbox / Menu Planning
- Upload a weekly school menu image (JPEG/PNG) — OpenCV detects the grid, Tesseract OCR reads each cell, and the app builds a structured per-day/per-meal plan
- Paste circular text — the NLP parser extracts food items, events, and supplies automatically
- Generates a **deduplicated shopping list** across the whole week with checkboxes
- Generates **short recipes** (ingredients, steps, prep time) for every food item via Claude Haiku
- Google Maps and DoorDash search links generated per step

### Homework & Project Tracking
- Paste any school note to create a structured task: type (`homework`, `project`, `event`, `supply`), deadline, and supplies list — all extracted automatically and saved to MongoDB
- Task board at `/tasks` with Pending / Done sections, checkboxes, and delete

### Smart Reminders
- Bell icon in the navbar with a live badge count of pending reminders
- Reminders created automatically when a task has a deadline or event
- Click the bell to see a dropdown — dismiss individually with optimistic UI updates
- Kafka consumer pipeline writes reminders from plan events in the background (optional — app works without Kafka)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15.5 · React 19 · TypeScript · Tailwind CSS v4 |
| Backend | Python 3.12 · FastAPI · Uvicorn |
| AI | Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) |
| NLP / OCR | OpenCV · Tesseract · Regex |
| Vector DB | ChromaDB (in-process, local) |
| Database | MongoDB (Motor async driver) |
| Messaging | Apache Kafka (optional) |

---

## Project Structure

```
SmartParentApp/
├── backend/
│   ├── main.py            # FastAPI app — all endpoints
│   ├── db.py              # MongoDB collections
│   ├── nlp_parser.py      # OCR + NLP menu/note parser
│   ├── rag_llm.py         # Claude + ChromaDB RAG plan generator
│   ├── recipe_service.py  # Claude recipe generation
│   ├── kafka_producer.py  # Publishes plan events to Kafka
│   ├── kafka_consumer.py  # Consumes events, writes reminders
│   └── requirements.txt
└── frontend/
    ├── src/app/
    │   ├── page.tsx        # Planner page (menu upload + weekly view)
    │   └── tasks/page.tsx  # Task board
    ├── src/components/
    │   └── Navbar.tsx      # Nav + reminder bell
    ├── src/lib/
    │   ├── api.ts          # Planner API calls
    │   ├── tasksApi.ts     # Task API calls
    │   └── remindersApi.ts # Reminder API calls
    └── src/types/plan.ts   # Shared TypeScript types
```

---

## Running Locally

See [local-setup.md](../local-setup.md) for the full guide. Quick version:

### 1. MongoDB

Install [MongoDB Community](https://www.mongodb.com/try/download/community) and start it:

```bash
# macOS / Linux
mongod --dbpath ~/data/db

# Windows
"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe" --dbpath C:\data\db
```

Or use a free [MongoDB Atlas](https://cloud.mongodb.com) cluster and set `MONGO_URI` in `backend/.env`.

### 2. Tesseract OCR

- **Windows:** install from [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`

### 3. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS / Linux

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Set your keys in `backend/.env`:

```
ANTHROPIC_API_KEY=your-key-here
MONGO_URI=mongodb://localhost:27017
MONGO_DB=smartparent
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local` should contain:

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
```

### 5. Kafka (optional)

Not required. If unavailable, the consumer thread exits gracefully and reminders still work via the direct MongoDB write path.

---

## Pages

| URL | Description |
|---|---|
| `http://localhost:3000` | Planner — upload menu image or paste text |
| `http://localhost:3000/tasks` | Homework & task board |
| `http://localhost:8001/docs` | FastAPI Swagger UI |
