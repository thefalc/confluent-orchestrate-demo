"""Webhook proxy: receives raw alert JSON from the HTTP Sink Connector
and forwards it to the Orchestrate agent via the Runs API."""

import json
import os
import time

import jwt
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Orchestrate local server
ORCHESTRATE_URL = os.getenv("ORCHESTRATE_LOCAL_URL", "http://localhost:4321")
AGENT_ID = os.getenv("ORCHESTRATE_AGENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "")


def get_token():
    """Generate a JWT token for the local Orchestrate server."""
    payload = {
        "sub": "f242eadf-0dc9-4eae-b2d7-65b09b4b4b16",
        "tenant_id": TENANT_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


def invoke_agent(alert: dict) -> str:
    """Send alert to the agent via the Runs API and poll for completion."""
    base = f"{ORCHESTRATE_URL}/v1/orchestrate"

    # Step 1: Create a run
    run_payload = {
        "message": {
            "role": "user",
            "content": "New equipment anomaly alert detected. Process this alert now:\n\n" + json.dumps(alert),
        },
        "agent_id": AGENT_ID,
    }
    resp = requests.post(f"{base}/runs", headers=get_headers(), json=run_payload, timeout=30)
    resp.raise_for_status()
    run_data = resp.json()
    run_id = run_data["run_id"]
    thread_id = run_data["thread_id"]
    print(f"  Run created: {run_id}, thread: {thread_id}")

    # Step 2: Poll for completion
    for _ in range(60):
        time.sleep(2)
        status_resp = requests.get(f"{base}/runs/{run_id}", headers=get_headers(), timeout=10)
        status_resp.raise_for_status()
        status = status_resp.json()
        run_state = status.get("status", "").lower()
        if run_state in ("completed", "failed", "cancelled"):
            break
    else:
        return "ERROR: Agent run timed out after 120 seconds"

    if run_state == "failed":
        return f"ERROR: Agent run failed: {status.get('error', 'unknown')}"

    # Step 3: Get thread messages for the response
    msgs_resp = requests.get(f"{ORCHESTRATE_URL}/v1/threads/{thread_id}/messages", headers=get_headers(), timeout=10)
    msgs_resp.raise_for_status()
    messages = msgs_resp.json()
    if isinstance(messages, dict) and "data" in messages:
        messages = messages["data"]

    # Find last assistant message
    for msg in reversed(messages if isinstance(messages, list) else []):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and item.get("response_type") == "text"
                ]
                return "\n".join(text_parts) if text_parts else str(content)
            return str(content)

    return "No response from agent"


@app.route("/alert", methods=["POST"])
def handle_alert():
    raw_body = request.get_data(as_text=True)
    print(f"[{time.strftime('%H:%M:%S')}] Raw body: {raw_body[:500]}")

    try:
        body = request.get_json(force=True)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] JSON parse error: {e}")
        return jsonify({"error": str(e)}), 400

    # HTTP Sink Connector sends an array even with batch.max.size=1
    alerts = body if isinstance(body, list) else [body]

    last_response = ""
    for alert in alerts:
        print(f"[{time.strftime('%H:%M:%S')}] Alert received: "
              f"{alert.get('machine_id')} / {alert.get('sensor_type')}")

        try:
            last_response = invoke_agent(alert)
        except Exception as e:
            last_response = f"ERROR: {e}"
            print(f"[{time.strftime('%H:%M:%S')}] Agent error: {e}")

        print(f"[{time.strftime('%H:%M:%S')}] Agent response: {last_response[:200]}...")

    return jsonify({"status": "processed", "response": last_response}), 200


if __name__ == "__main__":
    if not AGENT_ID:
        print("ERROR: Set ORCHESTRATE_AGENT_ID in .env")
        exit(1)
    if not JWT_SECRET:
        print("ERROR: Set JWT_SECRET in .env")
        exit(1)

    print(f"Webhook proxy starting on port 8090")
    print(f"Orchestrate: {ORCHESTRATE_URL}")
    print(f"Agent ID: {AGENT_ID}")
    print(f"Tenant ID: {TENANT_ID}")
    print(f"POST alerts to: http://localhost:8090/alert")
    app.run(host="0.0.0.0", port=8090)
