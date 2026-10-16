from app.core.errors import require

REQUEST_TRANSITIONS = {
    "PROCESSING": {
        "NEEDS_REVIEW",
        "PROCESSING_FAILED",
        "WAITING_FOR_TENANT",
        "APPROVED",
        "REJECTED",
    },
    "NEEDS_REVIEW": {"PROCESSING", "WAITING_FOR_TENANT", "APPROVED", "REJECTED"},
    "WAITING_FOR_TENANT": {"PROCESSING", "NEEDS_REVIEW", "APPROVED", "REJECTED"},
    "PROCESSING_FAILED": {
        "PROCESSING",
        "NEEDS_REVIEW",
        "WAITING_FOR_TENANT",
        "APPROVED",
        "REJECTED",
    },
    "APPROVED": set(),
    "REJECTED": set(),
}
ORDER_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "CANCELED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELED"},
    "COMPLETED": set(),
    "CANCELED": set(),
}
TEAMS = {
    "PLUMBING": "Plumbing team",
    "ELECTRICAL": "Electrical team",
    "HVAC": "HVAC team",
    "APPLIANCE": "Appliance team",
    "OTHER": "General maintenance",
    "UNKNOWN": "General maintenance",
}


def transition(row, new_status, mapping=REQUEST_TRANSITIONS):
    require(
        new_status == row.status or new_status in mapping[row.status],
        "INVALID_TRANSITION",
        f"Cannot change {row.status} to {new_status}",
        409,
    )
    row.status = new_status


def completeness(values):
    missing = []
    if values.get("category") not in TEAMS or values.get("category") == "UNKNOWN":
        missing.append("category")
    if not (values.get("room_or_area") or "").strip():
        missing.append("room_or_area")
    if len((values.get("description") or "").strip()) < 10:
        missing.append("description")
    if values.get("priority") not in {"ROUTINE", "PRIORITY", "URGENT"}:
        missing.append("priority")
    if values.get("assigned_team") != TEAMS.get(values.get("category")):
        missing.append("assigned_team")
    return missing
