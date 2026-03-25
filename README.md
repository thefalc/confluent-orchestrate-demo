# Predictive Maintenance Demo: Confluent Cloud + watsonx Orchestrate

An end-to-end demo that streams IoT sensor data through Confluent Cloud, detects anomalies with Flink SQL's built-in ML, and triggers an AI agent in IBM watsonx Orchestrate to triage issues and create work orders.

## Architecture

```
Sensor Simulator ──► Kafka (sensor-readings) ──► Flink SQL (ML_DETECT_ANOMALIES)
                                                          │
                                                          ▼
Streamlit Dashboard ◄── Kafka (equipment-alerts) ──► Orchestrate Agent
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                   Check History    Check Parts     Create Linear
                                                                   Issue + Notify
```

**Data flow:**
1. **Simulator** generates synthetic sensor readings (vibration, temperature, pressure) for 4 industrial machines
2. **Confluent Cloud Kafka** ingests readings into the `sensor-readings` topic
3. **Flink SQL** runs ARIMA-based anomaly detection over 10-second tumbling windows
4. Detected anomalies are written to the `equipment-alerts` topic
5. Alerts route to the **watsonx Orchestrate agent**, which:
   - Looks up equipment maintenance history
   - Checks parts inventory and availability
   - Creates a Linear issue with appropriate priority
   - Notifies the assigned technician
6. **Streamlit dashboard** provides real-time visualization and anomaly injection controls

## Project Structure

```
├── simulator/                  # Sensor data generation
│   ├── config.py               # Kafka config, machine & sensor definitions
│   ├── sensor_producer.py      # Produces readings to Kafka (every 10s)
│   └── anomaly_injector.py     # CLI to inject controlled anomalies
├── flink/                      # Flink SQL jobs (run in Confluent Cloud)
│   ├── 01_sensor_table.sql     # Add event_time column & watermark
│   ├── 02_anomaly_detection.sql # ARIMA anomaly detection pipeline
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

- Python 3.8+
- Docker & Docker Compose
- [Confluent Cloud](https://confluent.cloud/) account with a Kafka cluster
- IBM watsonx Orchestrate instance (SaaS or local via Docker)
- [Linear](https://linear.app/) account with an API key
- [ngrok](https://ngrok.com/) (optional, for HTTP Sink Connector webhook)

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

For Orchestrate, configure **either** remote SaaS or local:

**Remote (SaaS):** `WXO_API_KEY`, `WXO_INSTANCE_URL`, `WXO_AGENT_ID`

**Local (Docker):** `ORCHESTRATE_LOCAL_URL`, `ORCHESTRATE_AGENT_ID`, `JWT_SECRET`, `DEFAULT_TENANT_ID` (plus `server.env` for the Docker services)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create Kafka Topics

```bash
./demo/setup_confluent.sh
```

Creates `sensor-readings` and `equipment-alerts` topics (4 partitions each).

### 4. Deploy Flink SQL Jobs

In the Confluent Cloud Flink SQL workspace, execute in order:

1. `flink/01_sensor_table.sql` -- adds computed columns to sensor-readings
2. `flink/03_alerts_table.sql` -- creates equipment-alerts sink table
3. `flink/02_anomaly_detection.sql` -- deploys the anomaly detection pipeline

### 5. Start Orchestrate

**Option A -- Local Docker:**

```bash
docker-compose up -d
# Wait for all services to become healthy
# Access the chat UI at http://localhost:3000/chat-lite
```

Then import the agent and tools:

```bash
./orchestrate/import.sh
./scripts/patch_containers.sh   # Injects LINEAR_API_KEY into containers
```

**Option B -- Remote SaaS:**

Import via the watsonx Orchestrate UI or API using the specs in `orchestrate/`.

### 6. Set Up Alert Routing

**Option A -- HTTP Sink Connector (recommended for demos):**

1. Start ngrok: `ngrok http 8090`
2. Set `NGROK_URL` in `.env`
3. Deploy the connector using `connector/http_sink_config.json`
4. Start the webhook proxy: `python connector/webhook_proxy.py`

**Option B -- Kafka Consumer:**

```bash
python connector/alert_consumer.py
```

Subscribes to `equipment-alerts` and invokes the agent via the `orchestrate` CLI.

## Running the Demo

```bash
./demo/run_demo.sh
```

This starts the sensor producer and opens the Streamlit dashboard at **http://localhost:8501**.

### Injecting Anomalies

**Via the dashboard:** Use the sidebar controls to select a machine, sensor, and intensity, then click "Inject."

**Via CLI:**

```bash
python -m simulator.anomaly_injector compressor-01 vibration --intensity 5.0
```

The anomaly ramps up over 60 seconds. Flink detects it and publishes an alert, which triggers the Orchestrate agent to triage and respond.

### Resetting

```bash
./demo/reset_demo.sh
```

Clears anomaly state and stops background processes.

## Machines & Sensors

| Machine | Sensors | Facility |
|---------|---------|----------|
| compressor-01 | vibration, temperature, pressure | Plant-A |
| compressor-02 | vibration, temperature, pressure | Plant-A |
| pump-03 | vibration, temperature, pressure | Plant-B |
| turbine-04 | vibration, temperature, pressure | Plant-B |

Normal ranges: temperature ~72C, vibration ~3.5 mm/s, pressure ~150 psi.

## License

Apache License 2.0 -- see [LICENSE](LICENSE) for details.
