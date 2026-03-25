"""Bridge consumer: reads equipment-alerts from Kafka and invokes the Orchestrate agent."""

import json
import os
import subprocess
import sys
import time

from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

load_dotenv()

KAFKA_CONFIG = {
    "bootstrap.servers": os.getenv("CONFLUENT_BOOTSTRAP_SERVERS", ""),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("CONFLUENT_API_KEY", ""),
    "sasl.password": os.getenv("CONFLUENT_API_SECRET", ""),
    "group.id": "orchestrate-bridge",
    "auto.offset.reset": "latest",
}

ALERTS_TOPIC = "equipment-alerts"
ORCHESTRATE_CLI = os.getenv(
    "ORCHESTRATE_CLI",
    os.path.expanduser("~/Dev/watsonx-orchestrate-adk/.venv/bin/orchestrate"),
)
AGENT_NAME = "maintenance_triage_agent"


def invoke_agent(alert: dict) -> str:
    """Call the Orchestrate agent directly via CLI, bypassing the router."""
    message = json.dumps(alert)
    try:
        result = subprocess.run(
            [ORCHESTRATE_CLI, "chat", "ask", "--agent-name", AGENT_NAME, message],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "ERROR: Agent invocation timed out"
    except Exception as e:
        return f"ERROR: {e}"


def run():
    consumer = Consumer(KAFKA_CONFIG)
    consumer.subscribe([ALERTS_TOPIC])

    print(f"Alert bridge consumer started. Listening on '{ALERTS_TOPIC}'...")
    print(f"Agent: {AGENT_NAME}")
    print()

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"Kafka error: {msg.error()}")
                continue

            try:
                # Skip schema registry magic bytes (first 5 bytes)
                raw = msg.value()
                if raw[:1] == b"\x00":
                    raw = raw[5:]
                alert = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Failed to parse alert: {e}")
                continue

            print(f"[{time.strftime('%H:%M:%S')}] Alert received: "
                  f"{alert.get('machine_id')} / {alert.get('sensor_type')} "
                  f"(anomaly_score: {alert.get('anomaly_score', '?')})")

            response = invoke_agent(alert)
            print(response)
            print("-" * 60)

    except KeyboardInterrupt:
        print("\nShutting down alert consumer...")
    finally:
        consumer.close()
        print("Consumer closed.")


if __name__ == "__main__":
    run()
