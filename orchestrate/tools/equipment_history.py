"""Tool that returns maintenance history for a given machine."""

from datetime import datetime, timedelta
from ibm_watsonx_orchestrate.agent_builder.tools import tool


MAINTENANCE_HISTORY = {
    "compressor-01": [
        {
            "days_ago": 180,
            "type": "corrective",
            "description": "Bearing replacement - excessive vibration detected",
            "technician": "M. Torres",
        },
        {
            "days_ago": 30,
            "type": "preventive",
            "description": "Routine inspection - all parameters within spec",
            "technician": "M. Torres",
        },
    ],
    "compressor-02": [
        {
            "days_ago": 90,
            "type": "corrective",
            "description": "Motor assembly replacement - overheating reported",
            "technician": "M. Torres",
        },
        {
            "days_ago": 15,
            "type": "preventive",
            "description": "Routine inspection - minor filter wear noted",
            "technician": "M. Torres",
        },
    ],
    "pump-03": [
        {
            "days_ago": 60,
            "type": "corrective",
            "description": "Seal replacement - pressure leak on discharge side",
            "technician": "J. Chen",
        },
        {
            "days_ago": 20,
            "type": "preventive",
            "description": "Impeller cleaning - buildup reducing flow rate",
            "technician": "J. Chen",
        },
    ],
    "turbine-04": [
        {
            "days_ago": 45,
            "type": "preventive",
            "description": "Blade inspection - minor erosion on leading edges",
            "technician": "R. Patel",
        },
        {
            "days_ago": 365,
            "type": "overhaul",
            "description": "Full overhaul - bearings, seals, and blades replaced",
            "technician": "R. Patel",
        },
    ],
}


@tool(name="equipment_history", description="Returns maintenance history records for a given machine including past repairs, inspections, and overhauls.")
def get_equipment_history(machine_id: str) -> dict:
    """Return maintenance history for the given machine_id.

    Args:
        machine_id: Identifier of the machine (e.g. "compressor-01").

    Returns:
        Dict with machine_id and a list of maintenance records, each containing
        date, type, description, and technician.
    """
    today = datetime.now()
    raw_records = MAINTENANCE_HISTORY.get(machine_id, [])

    records = []
    for entry in raw_records:
        record_date = today - timedelta(days=entry["days_ago"])
        records.append(
            {
                "date": record_date.strftime("%Y-%m-%d"),
                "type": entry["type"],
                "description": entry["description"],
                "technician": entry["technician"],
            }
        )

    return {
        "machine_id": machine_id,
        "record_count": len(records),
        "history": records,
    }
