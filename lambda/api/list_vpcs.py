from typing import Any

from boto3.dynamodb.conditions import Attr
from common.aws import table
from common.http import response


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # shortcut: full table scan, fine for a small table. Add a GSI on a constant
    # partition and paginate the API when the VPC count grows.
    # created_at is read only to sort, the response carries just the id and the status
    scan = {
        "FilterExpression": Attr("sk").eq("META"),
        "ProjectionExpression": "id, #s, created_at",
        "ExpressionAttributeNames": {"#s": "status"},
    }
    items = []
    while True:
        page = table().scan(**scan)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        scan["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    items.sort(key=lambda i: i["created_at"], reverse=True)
    return response(200, {"vpcs": [{"id": i["id"], "status": i["status"]} for i in items]})
