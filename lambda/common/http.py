import json
from decimal import Decimal
from typing import Any


def _default(value: Any) -> Any:
    # DynamoDB returns numbers as Decimal
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def response(status: int, body: Any = None, headers: dict[str, str] | None = None) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **(headers or {})},
        "body": json.dumps(body, default=_default),
    }


def error(status: int, message: str) -> dict:
    return response(status, {"message": message})
