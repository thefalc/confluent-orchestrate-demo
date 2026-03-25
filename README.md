# Predictive Maintenance Demo: Confluent Cloud + watsonx Orchestrate

An end-to-end demo that streams IoT sensor data through Confluent Cloud, detects anomalies with Flink SQL's built-in ML, and triggers an AI agent in IBM watsonx Orchestrate to triage issues and create work orders.

## Architecture

```
Sensor Simulator ──► Kafka (sensor-readings) ──► Flink SQL (ML_DETECT_ANOMALIES)
                              │                            │
                              │                            ▼
                              │                  Kafka (equipment-alerts)
                              │                     │              │
                              ├─────────────────────┘              │
                              ▼                                    ▼
                     Streamlit Dashboard                  HTTP Sink Connector
                                                                   │
                                                                   ▼
                                                             ngrok tunnel
                                                                   │
                                                                   ▼
                                                            Webhook Proxy
                                                                   │
                                                                   ▼
                                                           Orchestrate Agent
                                                                   │
                                                   ┌───────────────┼───────────────┐
                                                   ▼               ▼               ▼
                                            Check History    Check Parts     Create Linear
                                                                            Issue + Notify
```

**Data flow:**
1. **Simulator** generates synthetic sensor readings (vibration, temperature, pressure) for 4 industrial machines
2. **Confluent Cloud Kafka** ingests readings into the `sensor-readings` topic (JSON Schema Registry format)
3. **Flink SQL** runs `ML_DETECT_ANOMALIES` over 10-second tumbling windows using ARIMA modeling
4. Detected anomalies are written to the `equipment-alerts` topic
5. **HTTP Sink Connector** forwards alerts to a local webhook proxy via an ngrok tunnel
6. **Webhook proxy** invokes the Orchestrate agent via the Runs API
7. The **watsonx Orchestrate agent** triages the alert:
   - Looks up equipment maintenance history
   - Checks parts inventory and availability
   - Creates a Linear issue with structured description and priority
   - Notifies the assigned technician
8. **Streamlit dashboard** provides real-time visualization and anomaly injection controls

## Project Structure

```
├── simulator/                  # Sensor data generation
│   ├── config.py               # Kafka config, machine & sensor definitions
│   ├── sensor_producer.py      # Produces readings to Kafka (every 10s)
│   └── anomaly_injector.py     # CLI to inject controlled anomalies
├── flink/                      # Flink SQL jobs (run in Confluent Cloud)
│   ├── 01_sensor_table.sql     # Add event_time column & watermark
│   ├── 02_anomaly_detection.sql # ML-based anomaly detection pipeline
│   └── 03_alerts_table.sql     # equipment-alerts sink table
├── connector/                  # Alert routing to Orchestrate
│   ├── http_sink_config.json   # HTTP Sink Connector config
│   ├── webhook_proxy.py        # Flask server → Orchestrate Runs API
│   └── alert_consumer.py       # Alternative: Kafka consumer → CLI
├── orchestrate/                # watsonx Orchestrate agent & tools
│   ├── agent/
│   │   └── maintenance_agent.yaml  # Agent spec with triage instructions
│   ├── tools/
│   │   ├── equipment_history.py    # Maintenance history lookup
│   │   ├── parts_inventory.py      # Parts availability check
│   │   └── notify_technician.py    # Slack/log notification
│   ├── toolkits/
│   │   └── linear_mcp_config.json  # Linear MCP server config
│   └── import.sh               # Import agent & tools into Orchestrate
├── dashboard/
│   └── app.py                  # Streamlit real-time monitoring UI
├── demo/                       # Demo lifecycle scripts
│   ├── setup_confluent.sh      # Create Kafka topics
│   ├── run_demo.sh             # Start producer + dashboard
│   └── reset_demo.sh           # Clear state and stop services
├── scripts/
│   └── patch_containers.sh     # Inject LINEAR_API_KEY into containers
├── docker-compose.yml          # Local Orchestrate server deployment
└── server.env                  # Orchestrate server config
```

## Prerequisites

- Python 3.10+
- Docker & Docker Compose
- [Confluent Cloud](https://confluent.cloud/) account with a Kafka cluster
- [watsonx Orchestrate Developer Edition](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/current) (local Docker install via `orchestrate` CLI)
- [Linear](https://linear.app/) account with an API key
- [ngrok](https://ngrok.com/) for tunneling HTTP Sink Connector webhooks to localhost

## Setup

### 1. Configure Environment

```bash
cp .env.example .env
```

Fill in your credentials:

| Variable | Description |
|----------|-------------|
| `CONFLUENT_BOOTSTRAP_SERVERS` | Kafka cluster bootstrap endpoint |
| `CONFLUENT_API_KEY` / `CONFLUENT_API_SECRET` | Kafka API credentials |
| `CONFLUENT_SCHEMA_REGISTRY_URL` | Schema Registry endpoint |
| `CONFLUENT_SR_API_KEY` / `CONFLUENT_SR_API_SECRET` | Schema Registry credentials |
| `CONFLUENT_CLOUD_API_KEY` / `CONFLUENT_CLOUD_API_SECRET` | Cloud REST API credentials |
| `CONFLUENT_ENVIRONMENT_ID` | Environment ID (`env-xxxxx`) |
| `CONFLUENT_CLUSTER_ID` | Cluster ID (`lkc-xxxxx`) |
| `LINEAR_API_KEY` | Linear API key for work order creation |
| `SLACK_WEBHOOK_URL` | *(Optional)* Slack webhook for notifications |

For the local Orchestrate webhook proxy, also set:

| Variable | Description |
|----------|-------------|
| `ORCHESTRATE_LOCAL_URL` | Orchestrate server URL (default: `http://localhost:4321`) |
| `ORCHESTRATE_AGENT_ID` | Agent ID from `orchestrate agents list` |
| `JWT_SECRET` | JWT secret from `server.env` |
| `DEFAULT_TENANT_ID` | Tenant ID from Orchestrate server |

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

You will also need `flask`, `PyJWT`, and `attrs`:

```bash
pip install flask PyJWT attrs
```

### 3. Create Kafka Topics

```bash
./demo/setup_confluent.sh
```

Creates `sensor-readings` (4 partitions) and `equipment-alerts` (6 partitions) topics.

### 4. Deploy Flink SQL Jobs

In the Confluent Cloud Flink SQL workspace, execute in order:

1. `flink/01_sensor_table.sql` — adds `event_time` watermarked column to `sensor-readings`
2. `flink/03_alerts_table.sql` — creates `equipment-alerts` sink table with `json-registry` format
3. `flink/02_anomaly_detection.sql` — deploys the anomaly detection pipeline

> **Note:** The anomaly detection uses `minTrainingSize=30`, so Flink needs ~5 minutes of baseline sensor data before it can start detecting anomalies.

### 5. Start Orchestrate (Developer Edition)

```bash
orchestrate server start --env-file server.env
```

Wait for all containers to become healthy, then import the agent and tools:

```bash
./orchestrate/import.sh
```

After import, patch the Docker containers to inject `LINEAR_API_KEY` (the orchestrate CLI doesn't automatically map custom env vars into the `tools-runtime` container):

```bash
./scripts/patch_containers.sh
```

> **Important:** You must re-run `patch_containers.sh` each time you restart the Orchestrate server.

The agent ID will be printed during import. Update `ORCHESTRATE_AGENT_ID` in `.env` with this value.

### 6. Set Up Alert Routing

Start an ngrok tunnel to expose the local webhook proxy:

```bash
ngrok http 8090
```

Deploy the HTTP Sink Connector in Confluent Cloud using the config in `connector/http_sink_config.json`. Update the `http.api.url` to your ngrok URL:

```json
{
  "http.api.url": "https://your-ngrok-id.ngrok.app/alert",
  "topics": "equipment-alerts",
  "input.data.format": "JSON_SR",
  "request.body.format": "json",
  "batch.max.size": "1"
}
```

> **Note:** Use `input.data.format: JSON_SR` (not `JSON`) since the Flink job writes with `json-registry` format.

Start the webhook proxy:

```bash
python connector/webhook_proxy.py
```

The proxy listens on port 8090 and forwards alerts to the Orchestrate agent via the Runs API.

## Running the Demo

### Start the Sensor Producer

```bash
python -m simulator.sensor_producer
```

This produces readings for all 4 machines (12 readings per cycle, every 10 seconds).

### Start the Dashboard

```bash
streamlit run dashboard/app.py --server.port 8501 --browser.gatherUsageStats false
```

Open **http://localhost:8501** to view the real-time dashboard.

### Injecting Anomalies

**Via the dashboard:** Use the sidebar controls to select a machine, sensor, and intensity, then click "Inject."

**Via CLI:**

```bash
python -m simulator.anomaly_injector compressor-01 vibration --intensity 5.0
```

The anomaly ramps up over 60 seconds. Flink detects it and publishes an alert to `equipment-alerts`, which the HTTP Sink Connector forwards to the webhook proxy, triggering the Orchestrate agent to triage and respond.

**What the agent does for each alert:**
1. Assesses severity (CRITICAL / HIGH / MEDIUM / LOW)
2. Queries equipment maintenance history
3. Checks parts inventory and availability
4. Creates a structured Linear issue with anomaly details, history, parts status, and recommended action
5. Notifies the assigned technician

### Stopping

```bash
# Stop the sensor producer
pkill -f sensor_producer

# Clear any active anomaly
rm -f /tmp/anomaly_target.json

# Or use the reset script
./demo/reset_demo.sh
```

## Machines & Sensors

| Machine | Facility | Criticality |
|---------|----------|-------------|
| compressor-01 | plant-north | high |
| compressor-02 | plant-north | medium |
| pump-03 | plant-south | high |
| turbine-04 | plant-south | critical |

Normal operating ranges: temperature ~72°C, vibration ~3.5 mm/s, pressure ~150 psi.

## Troubleshooting

**Linear issue creation fails:** Run `./scripts/patch_containers.sh` to inject `LINEAR_API_KEY` into the Orchestrate Docker containers. This is needed after every server restart.

**Connector returns errors:** Verify the ngrok tunnel is running and the URL in the connector config matches. Also ensure `input.data.format` is set to `JSON_SR`.

**Dashboard shows UnicodeDecodeError:** The dashboard strips the 5-byte Schema Registry header from messages. If you see this error, ensure you're running the latest version of `dashboard/app.py`.

**Flink not detecting anomalies:** The ML model needs ~30 data points (~5 minutes at 10-second intervals) of baseline data before it can detect anomalies. Let the sensor producer run for a few minutes first.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
