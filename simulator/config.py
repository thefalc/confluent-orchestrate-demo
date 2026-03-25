import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_CONFIG = {
    "bootstrap.servers": os.getenv("CONFLUENT_BOOTSTRAP_SERVERS"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("CONFLUENT_API_KEY"),
    "sasl.password": os.getenv("CONFLUENT_API_SECRET"),
}

SCHEMA_REGISTRY_CONFIG = {
    "url": os.getenv("CONFLUENT_SCHEMA_REGISTRY_URL"),
    "basic.auth.user.info": f"{os.getenv('CONFLUENT_SR_API_KEY')}:{os.getenv('CONFLUENT_SR_API_SECRET')}",
}

SENSOR_TOPIC = "sensor-readings"
ALERTS_TOPIC = "equipment-alerts"

# Machine definitions
MACHINES = {
    "compressor-01": {"facility": "plant-north", "criticality": "high"},
    "compressor-02": {"facility": "plant-north", "criticality": "medium"},
    "pump-03": {"facility": "plant-south", "criticality": "high"},
    "turbine-04": {"facility": "plant-south", "criticality": "critical"},
}

# Normal operating ranges per sensor type
SENSOR_PROFILES = {
    "temperature": {"mean": 72.0, "std": 2.0, "unit": "celsius"},
    "vibration": {"mean": 3.5, "std": 0.5, "unit": "mm/s"},
    "pressure": {"mean": 150.0, "std": 5.0, "unit": "psi"},
}
