import json
import os
import time
import uuid
from datetime import datetime
from collections import defaultdict

import pandas as pd
import streamlit as st
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
    "group.id": f"demo-dashboard-{uuid.uuid4().hex[:8]}",
    "auto.offset.reset": "earliest",
}

SENSOR_TOPIC = "sensor-readings"
ALERTS_TOPIC = "equipment-alerts"

MACHINES = ["compressor-01", "compressor-02", "pump-03", "turbine-04"]
SENSORS = ["temperature", "vibration", "pressure"]
SENSOR_UNITS = {"temperature": "°C", "vibration": "mm/s", "pressure": "psi"}
SENSOR_COLORS = {
    "compressor-01": "#FF6B6B",
    "compressor-02": "#4ECDC4",
    "pump-03": "#45B7D1",
    "turbine-04": "#FFA07A",
}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Compact metric values */
    [data-testid="stMetricValue"] { font-size: 1.1rem; }
    [data-testid="stMetricDelta"] { font-size: 0.75rem; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; }
    div[data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size: 1.4rem; }

    /* Machine status badges */
    .machine-status {
        display: inline-block;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 4px;
        margin: 0 4px 4px 0;
    }
    .status-ok { background-color: #1a3a2a; color: #4ade80; }
    .status-alert {
        background-color: #3a1a1a; color: #f87171;
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }

    /* Agent log */
    .log-entry { font-family: 'SF Mono','Fira Code',monospace; font-size: 0.75rem; line-height: 1.5; padding: 1px 0; }
    .log-alert { color: #fbbf24; }
    .log-action { color: #4ade80; }
    .log-detail { color: #94a3b8; padding-left: 16px; }
    .log-separator { border-top: 1px solid #333; margin: 6px 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
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

MAX_POINTS = 60

# ---------------------------------------------------------------------------
# Kafka consumer
# ---------------------------------------------------------------------------
@st.cache_resource
def get_consumer():
    consumer = Consumer(KAFKA_CONFIG)
    consumer.subscribe([SENSOR_TOPIC, ALERTS_TOPIC])
    return consumer


def poll_messages(max_messages=50):
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
            raw = msg.value()
            if raw[:1] == b'\x00':
                raw = raw[5:]
            value = json.loads(raw.decode("utf-8"))
            value["_topic"] = msg.topic()
            messages.append(value)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return messages


# ---------------------------------------------------------------------------
# Anomaly injection
# ---------------------------------------------------------------------------
def inject_anomaly(machine_id, sensor_type, intensity=3.0):
    target = {
        "machine_id": machine_id,
        "sensor_type": sensor_type,
        "start_time": time.time(),
        "intensity": intensity,
    }
    with open("/tmp/anomaly_target.json", "w") as f:
        json.dump(target, f)


def clear_anomaly():
    try:
        os.remove("/tmp/anomaly_target.json")
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Simulate agent activity
# ---------------------------------------------------------------------------
def simulate_agent_response(alert):
    machine = alert.get("machine_id", "unknown")
    sensor = alert.get("sensor_type", "unknown")
    value = alert.get("value", 0)
    score = alert.get("anomaly_score", 0.85)
    unit = SENSOR_UNITS.get(sensor, "")
    now = datetime.now().strftime("%H:%M:%S")

    severity = "CRITICAL" if score > 0.9 else "HIGH" if score > 0.7 else "MEDIUM"

    history_map = {
        "compressor-01": "Bearing replacement: 180 days ago",
        "compressor-02": "Motor replacement: 90 days ago",
        "pump-03": "Seal replacement: 60 days ago",
        "turbine-04": "Blade inspection: 45 days ago",
    }
    tech_map = {
        "compressor-01": "M. Torres",
        "compressor-02": "M. Torres",
        "pump-03": "J. Chen",
        "turbine-04": "R. Patel",
    }

    tech = tech_map.get(machine, "Unassigned")
    ticket_id = f"MNT-{2800 + st.session_state.anomaly_count}"

    return [
        {"type": "alert", "text": f"[{now}] ALERT: {machine} / {sensor} = {value:.1f} {unit} (score: {score:.2f})"},
        {"type": "action", "text": f"[{now}] Severity: {severity}"},
        {"type": "detail", "text": f"History: {history_map.get(machine, 'No history')}"},
        {"type": "action", "text": f"[{now}] Created {ticket_id} | Assigned: {tech}"},
        {"type": "action", "text": f"[{now}] Technician {tech} notified"},
        {"type": "separator", "text": ""},
    ]


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------
def build_sensor_chart_data(sensor_type):
    """Build a DataFrame with one column per machine for a given sensor type."""
    frames = {}
    for machine in MACHINES:
        readings = st.session_state.sensor_data.get(machine, {}).get(sensor_type, [])
        if readings:
            df = pd.DataFrame(readings[-MAX_POINTS:])
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
            frames[machine] = df["value"]

    if not frames:
        return None
    return pd.DataFrame(frames)


def render_sensor_charts():
    """Render one time-series chart per sensor type with all machines overlaid."""
    for sensor in SENSORS:
        chart_data = build_sensor_chart_data(sensor)
        if chart_data is None or chart_data.empty:
            continue

        unit = SENSOR_UNITS[sensor]
        st.markdown(f"**{sensor.capitalize()}** ({unit})")

        # Assign colors based on which machines have data
        colors = [SENSOR_COLORS[m] for m in chart_data.columns]
        st.line_chart(chart_data, color=colors, height=180)


def render_machine_status():
    """Render compact machine status badges with latest values."""
    html_parts = []
    for machine in MACHINES:
        machine_data = st.session_state.sensor_data.get(machine, {})
        has_anomaly = any(
            a.get("machine_id") == machine
            for a in st.session_state.alerts[-5:]
        )
        css_class = "status-alert" if has_anomaly else "status-ok"
        icon = "🔴" if has_anomaly else "🟢"

        # Build tooltip-style value string
        vals = []
        for sensor in SENSORS:
            readings = machine_data.get(sensor, [])
            if readings:
                v = readings[-1]["value"]
                u = SENSOR_UNITS[sensor]
                vals.append(f"{sensor[:4]}: {v:.1f}{u}")
        val_str = " · ".join(vals) if vals else "waiting..."

        html_parts.append(
            f'<span class="machine-status {css_class}">{icon} {machine}</span>'
            f'<span style="font-size:0.75rem; color:#888; margin-right:16px;">{val_str}</span>'
        )

    st.markdown(" ".join(html_parts), unsafe_allow_html=True)


def render_agent_log():
    entries = st.session_state.agent_log[-40:]
    if not entries:
        st.info("Waiting for anomaly alerts...")
        return

    html_lines = []
    for entry in entries:
        t = entry.get("type", "detail")
        text = entry.get("text", "")
        if t == "separator":
            html_lines.append('<div class="log-separator"></div>')
        elif t == "alert":
            html_lines.append(f'<div class="log-entry log-alert">{text}</div>')
        elif t == "action":
            html_lines.append(f'<div class="log-entry log-action">{text}</div>')
        else:
            html_lines.append(f'<div class="log-entry log-detail">{text}</div>')

    st.markdown("\n".join(html_lines), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.markdown("### Predictive Maintenance Demo")
st.caption("Confluent Cloud  ·  Flink SQL  ·  watsonx Orchestrate")

# Sidebar
with st.sidebar:
    st.header("Demo Controls")

    st.subheader("Inject Anomaly")
    target_machine = st.selectbox("Machine", MACHINES)
    target_sensor = st.selectbox("Sensor", SENSORS)
    intensity = st.slider("Intensity", 1.0, 20.0, 10.0, 1.0)

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
    st.metric("Readings processed", f"{st.session_state.readings_count:,}")
    st.metric("Anomalies detected", st.session_state.anomaly_count)
    anomaly_active = os.path.exists("/tmp/anomaly_target.json")
    if anomaly_active:
        st.warning("Anomaly injection ACTIVE")
    else:
        st.success("Normal operation")

# Machine status bar
status_placeholder = st.empty()

# Main layout
col_charts, col_agent = st.columns([3, 2])

with col_charts:
    st.markdown("##### Sensor Readings")
    charts_placeholder = st.empty()

with col_agent:
    st.markdown("##### Agent Activity")
    agent_log_placeholder = st.empty()


# ---------------------------------------------------------------------------
# Auto-refreshing fragment
# ---------------------------------------------------------------------------
@st.fragment(run_every=2)
def live_data():
    messages = poll_messages()

    for msg in messages:
        if msg["_topic"] == SENSOR_TOPIC:
            st.session_state.readings_count += 1
            machine = msg.get("machine_id", "unknown")
            sensor = msg.get("sensor_type", "unknown")
            data_list = st.session_state.sensor_data[machine][sensor]
            data_list.append({
                "time": msg.get("timestamp", datetime.now().isoformat()),
                "value": msg.get("value", 0),
            })
            if len(data_list) > MAX_POINTS:
                st.session_state.sensor_data[machine][sensor] = data_list[-MAX_POINTS:]

        elif msg["_topic"] == ALERTS_TOPIC:
            st.session_state.anomaly_count += 1
            st.session_state.alerts.append(msg)
            log_entries = simulate_agent_response(msg)
            st.session_state.agent_log.extend(log_entries)

    # Machine status badges
    with status_placeholder.container():
        render_machine_status()

    # Sensor time-series charts
    with charts_placeholder.container():
        render_sensor_charts()

    # Agent log
    with agent_log_placeholder.container():
        render_agent_log()


live_data()
