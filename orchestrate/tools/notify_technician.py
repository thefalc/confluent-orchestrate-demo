"""Tool that sends a notification to the assigned technician for a machine."""

import json
import logging
import os
import urllib.request

from ibm_watsonx_orchestrate.agent_builder.tools import tool

logger = logging.getLogger(__name__)

TECHNICIAN_ASSIGNMENTS = {
    "compressor-01": "M. Torres",
    "compressor-02": "M. Torres",
    "pump-03": "J. Chen",
    "turbine-04": "R. Patel",
}


@tool(name="notify_technician", description="Sends a notification to the technician assigned to a machine with severity level and issue details.")
def notify_technician(machine_id: str, severity: str, message: str) -> dict:
    """Send a notification to the technician assigned to the given machine.

    If the SLACK_WEBHOOK_URL environment variable is set, posts the notification
    to Slack. Otherwise, logs the notification locally.

    Args:
        machine_id: Identifier of the machine (e.g. "compressor-01").
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW).
        message: Notification message body with issue details.

    Returns:
        Dict with notification status, technician name, and delivery method.
    """
    technician = TECHNICIAN_ASSIGNMENTS.get(machine_id, "Unassigned")
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")

    notification = {
        "technician": technician,
        "machine_id": machine_id,
        "severity": severity,
        "message": message,
    }

    if slack_webhook:
        slack_payload = {
            "text": (
                f":rotating_light: *{severity} Alert* - {machine_id}\n"
                f"*Assigned to:* {technician}\n"
                f"{message}"
            ),
        }
        try:
            req = urllib.request.Request(
                slack_webhook,
                data=json.dumps(slack_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            delivery_method = "slack"
        except Exception as exc:
            logger.error("Slack notification failed: %s", exc)
            delivery_method = "slack_failed"
            return {
                "status": "error",
                "technician": technician,
                "delivery_method": delivery_method,
                "error": str(exc),
            }
    else:
        logger.info(
            "Notification for %s [%s]: %s -> %s",
            machine_id,
            severity,
            technician,
            message,
        )
        delivery_method = "log"

    return {
        "status": "sent",
        "technician": technician,
        "delivery_method": delivery_method,
        "notification": notification,
    }
