from datetime import UTC, datetime
from typing import Any

from common.aws import table

# API sets PENDING and DELETING (FAILED or old status when a workflow cannot start).
# Workflows set the rest.
PENDING = "PENDING"
ACTIVE = "ACTIVE"
FAILED = "FAILED"
DELETING = "DELETING"


def key(vpc_id: str) -> dict[str, str]:
    return {"pk": f"VPC#{vpc_id}", "sk": "META"}


def name_key(name: str) -> dict[str, str]:
    """Lock item that keeps VPC names unique, case-insensitively."""
    return {"pk": f"NAME#{name.lower()}", "sk": "LOCK"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def to_api(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k not in ("pk", "sk")}


def set_status(vpc_id: str, status: str, reason: str | None = None) -> None:
    expression = "SET #s = :s, updated_at = :t"
    values = {":s": status, ":t": now()}
    if reason:
        expression += ", status_reason = :r"
        values[":r"] = reason
    table().update_item(
        Key=key(vpc_id),
        UpdateExpression=expression,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=values,
    )
