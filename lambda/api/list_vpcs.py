from typing import Any

from boto3.dynamodb.conditions import Attr
from common.aws import table
from common.http import response
from common.vpc import to_api


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # shortcut: full table scan, fine for a small table. Add a GSI on a constant
    # partition and paginate the API when the VPC count grows.
    scan = {"FilterExpression": Attr("sk").eq("META")}
    items = []
    while True:
        page = table().scan(**scan)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        scan["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    items.sort(key=lambda i: i["created_at"], reverse=True)
    return response(200, {"vpcs": [to_api(i) for i in items]})
