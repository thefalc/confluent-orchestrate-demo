"""Tool that checks parts inventory for a given machine and optional part type."""

from ibm_watsonx_orchestrate.agent_builder.tools import tool

PARTS_CATALOG = {
    "compressor": [
        {
            "part_number": "BK-4420",
            "description": "Bearing kit",
            "quantity": 3,
            "status": "in_stock",
            "lead_time_days": 0,
        },
        {
            "part_number": "MA-7100",
            "description": "Motor assembly",
            "quantity": 1,
            "status": "in_stock",
            "lead_time_days": 0,
        },
        {
            "part_number": "FS-2200",
            "description": "Filter set",
            "quantity": 12,
            "status": "in_stock",
            "lead_time_days": 0,
        },
    ],
    "pump": [
        {
            "part_number": "SK-3300",
            "description": "Seal kit",
            "quantity": 5,
            "status": "in_stock",
            "lead_time_days": 0,
        },
        {
            "part_number": "IMP-5500",
            "description": "Impeller",
            "quantity": 0,
            "status": "backordered",
            "lead_time_days": 14,
        },
        {
            "part_number": "GS-1100",
            "description": "Gasket set",
            "quantity": 8,
            "status": "in_stock",
            "lead_time_days": 0,
        },
    ],
    "turbine": [
        {
            "part_number": "BS-9900",
            "description": "Blade set",
            "quantity": 1,
            "status": "in_stock",
            "lead_time_days": 0,
        },
        {
            "part_number": "BK-4420",
            "description": "Bearing kit",
            "quantity": 3,
            "status": "in_stock",
            "lead_time_days": 0,
        },
        {
            "part_number": "CL-6600",
            "description": "Coupling",
            "quantity": 2,
            "status": "in_stock",
            "lead_time_days": 0,
        },
    ],
}


def _extract_machine_type(machine_id: str) -> str:
    """Derive the machine type from the machine_id (e.g. 'compressor-01' -> 'compressor')."""
    parts = machine_id.rsplit("-", 1)
    return parts[0] if len(parts) > 1 else machine_id


@tool(name="parts_inventory", description="Checks parts inventory for a given machine. Returns available parts, quantities, and flags any backordered items that may delay repair.")
def check_parts_inventory(machine_id: str, part_type: str | None = None) -> dict:
    """Check parts inventory for the given machine.

    Args:
        machine_id: Identifier of the machine (e.g. "compressor-01").
        part_type: Optional filter by part description keyword (e.g. "bearing").

    Returns:
        Dict with machine_id, machine_type, and a list of matching inventory items.
    """
    machine_type = _extract_machine_type(machine_id)
    items = PARTS_CATALOG.get(machine_type, [])

    if part_type:
        keyword = part_type.lower()
        items = [item for item in items if keyword in item["description"].lower()]

    backordered = [item for item in items if item["status"] == "backordered"]

    return {
        "machine_id": machine_id,
        "machine_type": machine_type,
        "items": items,
        "backordered_count": len(backordered),
        "warning": (
            f"{len(backordered)} part(s) backordered - may delay repair"
            if backordered
            else None
        ),
    }
