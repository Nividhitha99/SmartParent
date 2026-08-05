# kafka_producer.py
# Publishes plan-created events to Kafka for the consumer (kafka_consumer.py) to
# turn into reminders. Best-effort: never blocks the request or raises if the
# broker is unreachable — mirrors the graceful-failure design of the consumer.
import json
import logging
import os

logger = logging.getLogger(__name__)

KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"

producer = None
if KAFKA_ENABLED:
    try:
        from confluent_kafka import Producer
        producer_conf = {
            "bootstrap.servers": "localhost:9092",
            # Fail fast instead of retrying indefinitely against an unreachable broker.
            "socket.timeout.ms": 3000,
            "message.timeout.ms": 5000,
        }
        producer = Producer(producer_conf)
    except Exception as e:
        logger.warning(f"[kafka_producer] Could not initialize producer: {e} — plan events disabled")
        producer = None


def publish_plan_event(plan: dict):
    if producer is None:
        return
    try:
        producer.produce("plans-topic", json.dumps(plan).encode("utf-8"))
        producer.flush(timeout=5)
    except Exception as e:
        logger.warning(f"[kafka_producer] Failed to publish plan event: {e}")
