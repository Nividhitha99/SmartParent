# kafka_producer.py
import json
from confluent_kafka import Producer

producer_conf = {"bootstrap.servers": "localhost:9092"}
producer = Producer(producer_conf)

def publish_plan_event(plan: dict):
    producer.produce("plans-topic", json.dumps(plan).encode("utf-8"))
    producer.flush()
