"""Sensor data simulator that produces readings to Confluent Kafka with JSON Schema Registry."""

import json
import os
import random
import time
from datetime import datetime, timezone

from confluent_kafka import Producer
from confluent_kafka.serialization import SerializationContext, MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer

from simulator.config import KAFKA_CONFIG, SCHEMA_REGISTRY_CONFIG, SENSOR_TOPIC, MACHINES, SENSOR_PROFILES


ANOMALY_FILE = "/tmp/anomaly_target.json"

SENSOR_SCHEMA_STR = json.dumps({
    "type": "object",
    "properties": {
        "machine_id": {"type": "string"},
        "sensor_type": {"type": "string"},
        "value": {"type": "number"},
        "unit": {"type": "string"},
        "timestamp": {"type": "string"},
        "facility": {"type": "string"},
    },
    "required": ["machine_id", "sensor_type", "value", "unit", "timestamp", "facility"],
})


def delivery_report(err, msg):
    """Callback for Kafka produce delivery results."""
    if err is not None:
        print(f"Delivery failed for {msg.key()}: {err}")


def load_anomaly_target():
    """Read the anomaly target file if it exists."""
    if os.path.exists(ANOMALY_FILE):
        try:
            with open(ANOMALY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def compute_anomaly_offset(anomaly, sensor_profile):
    """Compute a gradual degradation offset that ramps up over ~60 seconds."""
    elapsed = time.time() - anomaly["start_time"]
    ramp = min(elapsed / 60.0, 1.0)
    return ramp * anomaly["intensity"] * sensor_profile["std"]


def sensor_to_dict(sensor, ctx):
    return sensor


def run():
    """Main loop: produce one reading per machine per sensor every 2 seconds."""
    schema_registry_client = SchemaRegistryClient(SCHEMA_REGISTRY_CONFIG)
    json_serializer = JSONSerializer(
        SENSOR_SCHEMA_STR,
        schema_registry_client,
        to_dict=sensor_to_dict,
    )

    producer = Producer(KAFKA_CONFIG)

    # Small per-sensor drift state for realism
    drift = {
        (m, sensor_type): 0.0
        for m in MACHINES
        for sensor_type in SENSOR_PROFILES
    }

    print(f"Starting sensor producer — {len(MACHINES)} machines, "
          f"{len(SENSOR_PROFILES)} sensors each. Producing to '{SENSOR_TOPIC}'.")

    try:
        while True:
            anomaly = load_anomaly_target()

            for machine_id, machine_info in MACHINES.items():
                for sensor_type, profile in SENSOR_PROFILES.items():
                    key = (machine_id, sensor_type)

                    # Slight random walk drift
                    drift[key] += random.gauss(0, profile["std"] * 0.01)
                    drift[key] *= 0.99  # mean-revert slowly

                    # Normal reading
                    value = random.gauss(profile["mean"], profile["std"]) + drift[key]

                    # Apply anomaly if this machine/sensor is the target
                    if (anomaly
                            and anomaly.get("machine_id") == machine_id
                            and anomaly.get("sensor_type") == sensor_type):
                        value += compute_anomaly_offset(anomaly, profile)

                    message = {
                        "machine_id": machine_id,
                        "sensor_type": sensor_type,
                        "value": round(value, 4),
                        "unit": profile["unit"],
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "facility": machine_info["facility"],
                    }

                    producer.produce(
                        SENSOR_TOPIC,
                        key=machine_id,
                        value=json_serializer(
                            message,
                            SerializationContext(SENSOR_TOPIC, MessageField.VALUE),
                        ),
                        callback=delivery_report,
                    )

            producer.poll(0)
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down sensor producer...")
    finally:
        producer.flush()
        print("Producer flushed. Done.")


if __name__ == "__main__":
    run()
