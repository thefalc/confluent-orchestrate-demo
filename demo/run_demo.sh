#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "  Predictive Maintenance Demo"
echo "  Confluent + watsonx Orchestrate"
echo "========================================="
echo ""

# Check .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in credentials."
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."
echo "  NOTE: Flink anomaly detection pipeline must be running in Confluent Cloud."
echo "        Run ./demo/setup_confluent.sh first if not already done."
echo ""

# Clear any previous anomaly state
rm -f /tmp/anomaly_target.json

# Start sensor producer in background
echo "[1/2] Starting sensor data simulator..."
cd "$PROJECT_DIR"
python -m simulator.sensor_producer &
PRODUCER_PID=$!
echo "      Sensor producer running (PID: $PRODUCER_PID)"

# Cleanup on exit
trap "kill $PRODUCER_PID 2>/dev/null; echo 'Demo stopped.'" EXIT

# Start dashboard
echo "[2/2] Starting demo dashboard..."
echo ""
echo "  Dashboard:      http://localhost:8501"
echo "  Orchestrate UI: http://localhost:3000/chat-lite"
echo ""
echo "  Demo flow:"
echo "    1. Show live sensor data streaming in"
echo "    2. Click 'Inject Anomaly' to trigger degradation"
echo "    3. Watch Flink detect the anomaly (~5 min warmup for ML model)"
echo "    4. Watch Orchestrate agent triage and respond"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

streamlit run dashboard/app.py --server.headless true
