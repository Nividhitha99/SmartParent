# kafka_consumer.py
# Consumes plan events from Kafka and writes reminders to MongoDB.
# Runs in a daemon thread so it never blocks the FastAPI event loop.
# Fails gracefully — if the Kafka broker is unreachable the app continues
# without reminders-via-Kafka; the dual-write path in main.py still works.

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

_consumer_thread: threading.Thread | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_reminder_doc(event_name: str, date: str | None, time: str | None,
                         source: str) -> dict:
    return {
        "reminder_id": str(uuid.uuid4()),
        "event_name": event_name,
        "date": date,
        "time": time,
        "source": source,
        "dismissed": False,
        "created_at": datetime.utcnow(),
    }


def _process_plan(plan: dict, loop: asyncio.AbstractEventLoop) -> None:
    """
    Extract reminder-type steps from a consumed plan dict and persist them.
    Runs synchronously inside the consumer thread; uses run_coroutine_threadsafe
    to call the async Motor insert on the main event loop.
    """
    from db import reminders  # import here to avoid circular import at module load

    steps = plan.get("steps", [])
    for step in steps:
        if step.get("type") != "reminder":
            continue

        doc = _build_reminder_doc(
            event_name=step.get("title", "Reminder"),
            date=step.get("when"),
            time=None,          # plan steps carry day name in `when`, not a time
            source="plan",
        )

        try:
            future = asyncio.run_coroutine_threadsafe(
                reminders.insert_one(doc), loop
            )
            future.result(timeout=5)
        except Exception as e:
            logger.error(f"[kafka_consumer] Failed to write reminder to MongoDB: {e}")


def _run_consumer(loop: asyncio.AbstractEventLoop) -> None:
    """
    Blocking Kafka poll loop — intended to run in a daemon thread.
    Any exception during setup exits cleanly; the rest of the app is unaffected.
    """
    try:
        from confluent_kafka import Consumer, KafkaError, KafkaException
    except ImportError:
        logger.warning("[kafka_consumer] confluent_kafka not installed — Kafka reminders disabled")
        return

    conf = {
        "bootstrap.servers": "localhost:9092",
        "group.id": "smartparent-reminders",
        "auto.offset.reset": "earliest",
        # Short timeouts so startup failure is detected quickly
        "socket.timeout.ms": 3000,
        "session.timeout.ms": 6000,
    }

    try:
        consumer = Consumer(conf)
        consumer.subscribe(["plans-topic"])
        logger.info("[kafka_consumer] Connected — subscribed to plans-topic")
    except KafkaException as e:
        logger.warning(f"[kafka_consumer] Broker unreachable at startup: {e} — Kafka reminders disabled")
        return
    except Exception as e:
        logger.warning(f"[kafka_consumer] Unexpected error during setup: {e} — Kafka reminders disabled")
        return

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                code = msg.error().code()
                if code == KafkaError._PARTITION_EOF:
                    continue
                # Any real broker error — log and exit thread cleanly
                logger.error(f"[kafka_consumer] Kafka error: {msg.error()} — stopping consumer thread")
                break

            try:
                plan = json.loads(msg.value().decode("utf-8"))
                _process_plan(plan, loop)
            except json.JSONDecodeError as e:
                logger.error(f"[kafka_consumer] Bad JSON in message: {e}")
            except Exception as e:
                logger.error(f"[kafka_consumer] Error processing message: {e}")
    finally:
        try:
            consumer.close()
        except Exception:
            pass
        logger.info("[kafka_consumer] Consumer thread exited")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_consumer(loop: asyncio.AbstractEventLoop) -> None:
    """
    Spin up the Kafka consumer in a daemon thread.
    Safe to call at FastAPI startup — will not raise even if Kafka is down.
    """
    global _consumer_thread
    _consumer_thread = threading.Thread(
        target=_run_consumer,
        args=(loop,),
        daemon=True,
        name="kafka-consumer",
    )
    _consumer_thread.start()
    logger.info("[kafka_consumer] Consumer thread started")


# ---------------------------------------------------------------------------
# Exposed helper for direct (non-Kafka) reminder writes
# ---------------------------------------------------------------------------

async def create_reminder_from_task(
    event_name: str,
    date: str | None,
    time: str | None,
) -> dict:
    """
    Direct MongoDB write used by the dual-write path in main.py.
    Called from async context (FastAPI handler) — no thread magic needed.
    """
    from db import reminders
    doc = _build_reminder_doc(event_name=event_name, date=date, time=time, source="task")
    await reminders.insert_one(doc)
    return doc
