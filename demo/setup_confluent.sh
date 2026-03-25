#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "  Confluent Cloud Setup"
echo "  Predictive Maintenance Demo"
echo "========================================="
echo ""

# Check .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in credentials."
    exit 1
fi

source "$PROJECT_DIR/.env"

# Validate required env vars
for var in CONFLUENT_ENVIRONMENT_ID CONFLUENT_CLUSTER_ID; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set in .env"
        exit 1
    fi
done

echo "Using environment: $CONFLUENT_ENVIRONMENT_ID"
echo "Using cluster:     $CONFLUENT_CLUSTER_ID"
echo ""

# Set active environment and cluster
confluent environment use "$CONFLUENT_ENVIRONMENT_ID"
confluent kafka cluster use "$CONFLUENT_CLUSTER_ID"

# ---------------------------------------------------------------------------
# Create topics
# ---------------------------------------------------------------------------
echo "[1/2] Creating Kafka topics..."

for TOPIC in sensor-readings equipment-alerts; do
    if confluent kafka topic describe "$TOPIC" &>/dev/null; then
        echo "  Topic '$TOPIC' already exists — skipping"
    else
        confluent kafka topic create "$TOPIC" --partitions 4
        echo "  Created topic '$TOPIC'"
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "[2/2] Verifying setup..."
echo ""
echo "  Topics:"
confluent kafka topic list | grep -E "sensor-readings|equipment-alerts" | sed 's/^/    /'
echo ""
echo "Confluent Cloud setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the sensor producer to register the JSON schema and begin streaming:"
echo "       python -m simulator.sensor_producer"
echo ""
echo "  2. Set up Flink SQL (run these in the Confluent Cloud Flink workspace):"
echo "       a. The sensor-readings table is auto-created from the topic + schema."
echo "          Run the ALTER statements in flink/01_sensor_table.sql to add"
echo "          the computed event_time column and watermark."
echo "       b. Run flink/03_alerts_table.sql to create the equipment-alerts sink table."
echo "       c. Run flink/02_anomaly_detection.sql to deploy the anomaly detection pipeline."
echo ""
echo "  3. Run the demo: ./demo/run_demo.sh"
