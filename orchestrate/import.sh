#!/usr/bin/env bash
# ============================================================================
# import.sh - Import the Maintenance Triage Agent and tools into
#             watsonx Orchestrate.
#
# Prerequisites:
#   - orchestrate CLI installed and authenticated
#   - Active env set (local or remote)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ORCHESTRATE="$(which orchestrate 2>/dev/null || echo "/Users/seanfalconer/Dev/watsonx-orchestrate-adk/.venv/bin/orchestrate")"

echo "=== Importing tools into watsonx Orchestrate ==="

# Step 1: Import Python tools
echo "[1/4] Importing equipment_history tool..."
$ORCHESTRATE tools import --kind python --file "${SCRIPT_DIR}/tools/equipment_history.py"

echo "[2/4] Importing parts_inventory tool..."
$ORCHESTRATE tools import --kind python --file "${SCRIPT_DIR}/tools/parts_inventory.py"

echo "[3/4] Importing notify_technician tool..."
$ORCHESTRATE tools import --kind python --file "${SCRIPT_DIR}/tools/notify_technician.py"

# Step 2: Import agent
echo "[4/4] Importing maintenance-triage-agent..."
$ORCHESTRATE agents import --file "${SCRIPT_DIR}/agent/maintenance_agent.yaml"

echo ""
echo "=== Import complete ==="
echo ""
$ORCHESTRATE agents list
