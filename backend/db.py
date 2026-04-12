import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "smartparent")

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]

# collections we’ll use
jobs = db["jobs"]
plans = db["plans"]
tasks = db["tasks"]
reminders = db["reminders"]
