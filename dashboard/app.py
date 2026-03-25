import json
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict

import streamlit as st
import requests
from confluent_kafka import Consumer, KafkaError

# Must be first Streamlit call
st.set_page_config(page_title="Predictive Maintenance Demo", layout="wide")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv()

KAFKA_CONFIG = {
    "bootstrap.servers": os.getenv("CONFLUENT_BOOTSTRAP_SERVERS", ""),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("CONFLUENT_API_KEY", ""),
    "sasl.password": os.getenv("CONFLUENT_API_SECRET", ""),
    "group.id": "demo-dashboard",
    "auto.offset.reset": "latest",
}

SENSOR_TOPIC = "sensor-readings"
ALERTS_TOPIC = "equipment-alerts"

MACHINES = ["compressor-01", "compressor-02", "pump-03", "turbine-04"]

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "sensor_data" not in st.session_state:
    st.session_state.sensor_data = defaultdict(lambda: defaultdict(list))
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []
if "readings_count" not in st.session_state:
    st.session_state.readings_count = 0
if "anomaly_count" not in st.session_state:
    st.session_state.anomaly_count = 0

MAX_POINTS = 100  # Max data points per chart

# ---------------------------------------------------------------------------
# Kafka consumer helpers
# ---------------------------------------------------------------------------
@st.cache_resource
def get_consumer():
    consumer = Consumer(KAFKA_CONFIG)
    consumer.subscribe([SENSOR_TOPIC, ALERTS_TOPIC])
    return consumer


def poll_messages(max_messages=50):
    """Poll Kafka for new messages. Non-blocking."""
    consumer = get_consumer()
    messages = []
    for _ in range(max_messages):
        msg = consumer.poll(timeout=0.1)
        if msg is None:
            break
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                st.error(f"Kafka error: {msg.error()}")
            continue
        try:
            value = json.loads(msg.value().decode("utf-8"))
            value["_topic"] = msg.topic()
            messages.append(value)
        except json.JSONDecodeError:
            continue
    return messages


# ---------------------------------------------------------------------------
# Anomaly injection
# ---------------------------------------------------------------------------
def inject_anomaly(machine_id, sensor_type, intensity=3.0):
    """Write anomaly target file for the sensor producer to pick up."""
    target = {
        "machine_id": machine_id,
        "sensor_type": sensor_type,
        "start_time": time.time(),
        "intensity": intensity,
    }
    with open("/tmp/anomaly_target.json", "w") as f:
        json.dump(target, f)


def clear_anomaly():
    """Remove anomaly target file."""
    try:
        os.remove("/tmp/anomaly_target.json")
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Simulate agent activity (used when Orchestrate isn't connected)
# ---------------------------------------------------------------------------
def simulate_agent_response(alert):
    """Generate a realistic agent activity log for demo purposes."""
    machine = alert.get("machine_id", "unknown")
    sensor = alert.get("sensor_type", "unknown")
    score = alert.get("anomaly_score", 0.85)
    now = datetime.now().strftime("%H:%M:%S")

    severity = "CRITICAL" if score > 0.9 else "HIGH" if score > 0.7 else "MEDIUM"

    history_map = {
        "compressor-01": "Bearing replacement: 180 days ago | Last inspection: 30 days ago",
        "compressor-02": "Motor replacement: 90 days ago | Last inspection: 15 days ago",
        "pump-03": "Seal replacement: 60 days ago | Impeller cleaning: 20 days ago",
        "turbine-04": "Blade inspection: 45 days ago | Full overhaul: 365 days ago",
    }

    parts_map = {
        "compressor": "Bearing kit BK-4420: IN STOCK (3 units)",
        "pump": "Seal kit SK-3300: IN STOCK (5 units)",
        "turbine": "Blade set BS-9900: IN STOCK (1 unit)",
    }

    tech_map = {
        "compressor-01": "M. Torres",
        "compressor-02": "M. Torres",
        "pump-03": "J. Chen",
        "turbine-04": "R. Patel",
    }

    machine_type = machine.split("-")[0]
    tech = tech_map.get(machine, "Unassigned")
    ticket_id = f"MNT-{2800 + len(st.session_state.agent_log)}"

    return [
        f"[{now}] Alert received: {machine} {sensor} anomaly (score: {score:.2f})",
        f"[{now}] Severity assessed: {severity}",
        f"[{now}] Checking maintenance history...",
        f"[{now}]   {history_map.get(machine, 'No history found')}",
        f"[{now}] Checking parts inventory...",
        f"[{now}]   {parts_map.get(machine_type, 'No parts info')}",
        f"[{now}] Creating work order...",
        f"[{now}]   Linear: {ticket_id} created | Priority: {severity} | Assigned: {tech}",
        f"[{now}] Technician {tech} notified",
        "",
    ]


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.title("Predictive Maintenance Demo")
st.caption("Confluent + watsonx Orchestrate")

# Sidebar: anomaly injection controls
with st.sidebar:
    st.header("Demo Controls")
    st.subheader("Inject Anomaly")
    target_machine = st.selectbox("Machine", MACHINES)
    target_sensor = st.selectbox("Sensor", ["vibration", "temperature", "pressure"])
    intensity = st.slider("Intensity", 1.0, 5.0, 3.0, 0.5)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Inject", type="primary", use_container_width=True):
            inject_anomaly(target_machine, target_sensor, intensity)
            st.success(f"Injecting on {target_machine}")
    with col2:
        if st.button("Clear", use_container_width=True):
            clear_anomaly()
            st.info("Anomaly cleared")

    st.divider()
    st.subheader("Pipeline Status")
    st.metric("Readings processed", st.session_state.readings_count)
    st.metric("Anomalies detected", st.session_state.anomaly_count)

    # Check if anomaly is active
    anomaly_active = os.path.exists("/tmp/anomaly_target.json")
    if anomaly_active:
        st.warning("Anomaly injection ACTIVE")
    else:
        st.success("Normal operation")

# Main content: two columns
col_sensors, col_agent = st.columns([1, 1])

with col_sensors:
    st.subheader("Live Sensor Feed")
    chart_placeholder = st.empty()

with col_agent:
    st.subheader("Agent Activity Log")
    agent_log_placeholder = st.empty()

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
# Poll for messages and update state
messages = poll_messages()

for msg in messages:
    if msg["_topic"] == SENSOR_TOPIC:
        st.session_state.readings_count += 1
        machine = msg.get("machine_id", "unknown")
        sensor = msg.get("sensor_type", "unknown")
        key = f"{machine}/{sensor}"
        data_list = st.session_state.sensor_data[machine][sensor]
        data_list.append({
            "time": msg.get("timestamp", datetime.now().isoformat()),
            "value": msg.get("value", 0),
        })
        # Trim to max points
        if len(data_list) > MAX_POINTS:
            st.session_state.sensor_data[machine][sensor] = data_list[-MAX_POINTS:]

    elif msg["_topic"] == ALERTS_TOPIC:
        st.session_state.anomaly_count += 1
        st.session_state.alerts.append(msg)
        # Simulate agent processing
        log_entries = simulate_agent_response(msg)
        st.session_state.agent_log.extend(log_entries)

# Render sensor charts
with chart_placeholder.container():
    for machine in MACHINES:
        machine_data = st.session_state.sensor_data.get(machine, {})
        if not machine_data:
            continue

        has_anomaly = any(
            a.get("machine_id") == machine
            for a in st.session_state.alerts[-5:]
        )
        status = "!!!" if has_anomaly else "OK"
        st.markdown(f"**{machine}** {'⚠️' if has_anomaly else '✅'}")

        # Show latest values as small metrics
        cols = st.columns(3)
        for i, sensor in enumerate(["temperature", "vibration", "pressure"]):
            readings = machine_data.get(sensor, [])
            if readings:
                latest = readings[-1]["value"]
                unit = {"temperature": "C", "vibration": "mm/s", "pressure": "psi"}[sensor]
                cols[i].metric(sensor.capitalize(), f"{latest:.1f} {unit}")

# Render agent log
with agent_log_placeholder.container():
    if st.session_state.agent_log:
        log_text = "\n".join(st.session_state.agent_log[-30:])
        st.code(log_text, language=None)
    else:
        st.info("Waiting for anomaly alerts...")

# Auto-refresh
time.sleep(2)
st.rerun()
