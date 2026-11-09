from typing import Any

from common.http import response


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    sub = claims.get("sub", "Unknown")
    return response(200, {"status": "healthy", "message": f"Health check passed for user {sub}"})
