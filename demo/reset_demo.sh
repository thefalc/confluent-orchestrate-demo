#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Resetting demo state..."

# Clear anomaly injection
rm -f /tmp/anomaly_target.json
echo "  Cleared anomaly injection state"

# Kill any running producers
pkill -f "sensor_producer" 2>/dev/null && echo "  Stopped sensor producer" || true

# Kill any running dashboards
pkill -f "streamlit run dashboard" 2>/dev/null && echo "  Stopped dashboard" || true

echo ""
echo "Optional: To also clear Kafka topics, run:"
echo "  confluent kafka topic delete sensor-readings --cluster \$CONFLUENT_CLUSTER_ID"
echo "  confluent kafka topic delete equipment-alerts --cluster \$CONFLUENT_CLUSTER_ID"
echo ""
echo "Reset complete."
