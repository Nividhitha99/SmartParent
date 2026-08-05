# SmartParent — Local Setup Guide

Everything runs locally. No Docker required.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| Tesseract OCR | 5.x | See install steps below |
| MongoDB | 7.x | Local install or MongoDB Atlas (free tier) |

---

## 1 — MongoDB

### Option A: Local install (recommended for dev)

Download and install from [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community).

Start the server:
```bash
# macOS / Linux
mongod --dbpath ~/data/db

# Windows (run as Administrator, or use the MongoDB service)
"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe" --dbpath C:\data\db
```

Connection string used by the app: `mongodb://localhost:27017`

### Option B: MongoDB Atlas (no local install)

1. Create a free cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Copy your connection string (e.g. `mongodb+srv://user:pass@cluster.mongodb.net`)
3. Set it in `backend/.env`:
   ```
   MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net
   ```

---

## 2 — Tesseract OCR

Required by the menu image parser.

### Windows
Download the installer from [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki) and install to the default path (`C:\Program Files\Tesseract-OCR`).

Add to PATH, or set the path explicitly at the top of `backend/nlp_parser.py`:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### macOS
```bash
brew install tesseract
```

### Linux (Debian/Ubuntu)
```bash
sudo apt install tesseract-ocr
```

---

## 3 — Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

### backend/.env

```
OPENAI_API_KEY=sk-...         # Required — get from platform.openai.com
MONGO_URI=mongodb://localhost:27017
MONGO_DB=smartparent
```

### ChromaDB

ChromaDB runs **in-process** via the Python package — no separate server or install needed. The vector database is stored locally in `backend/rag_db/`.

---

## 4 — Frontend

Open a second terminal:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

Frontend runs at: `http://localhost:3000`

### frontend/.env.local

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## 5 — Kafka (optional)

Kafka is used to stream plan-created events to the reminders pipeline (a plan's
`reminder`-type steps get turned into entries in the bell dropdown). It is
**fully optional** — the Tasks feature uses a dual-write strategy so those
reminders are written directly to MongoDB regardless. If Kafka is not running,
the consumer thread logs a warning and exits; everything else continues
normally. Set `KAFKA_ENABLED=false` in `backend/.env` to skip it entirely.

### Option A: Docker (recommended)

A single-node broker in KRaft mode (no separate ZooKeeper needed) is defined
in the repo's `docker-compose.yml`:

```bash
docker compose up -d
```

### Option B: Manual binary

```bash
# Download from https://kafka.apache.org/downloads (binary, latest stable)
# Extract and run:

# Start ZooKeeper
bin/zookeeper-server-start.sh config/zookeeper.properties

# Start Kafka broker (separate terminal)
bin/kafka-server-start.sh config/server.properties
```

Kafka broker address used by the app: `localhost:9092`. The `plans-topic` topic
is created automatically the first time a plan is published — no manual setup
needed.

---

## Running Order

Start services in this order:

```
1. mongod            (MongoDB)
2. uvicorn main:app  (FastAPI backend)   → http://localhost:8000
3. npm run dev       (Next.js frontend)  → http://localhost:3000
```

---

## Pages

| URL | Description |
|---|---|
| `http://localhost:3000` | Planner — upload menu image or paste text |
| `http://localhost:3000/tasks` | Homework & task board |
| `http://localhost:8000/docs` | FastAPI Swagger UI — test all API endpoints |
