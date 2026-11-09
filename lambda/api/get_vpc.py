from typing import Any

from common.aws import table
from common.http import error, response
from common.vpc import key, to_api


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    vpc_id = (event.get("pathParameters") or {}).get("id", "")
    item = table().get_item(Key=key(vpc_id)).get("Item")
    if not item:
        return error(404, "VPC not found")
    return response(200, to_api(item))
