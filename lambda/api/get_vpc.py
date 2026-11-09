import json
from typing import Any


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    sub = claims.get("sub", "Unknown")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "healthy", "message": f"Health check passed for user {sub}"}),
    }
