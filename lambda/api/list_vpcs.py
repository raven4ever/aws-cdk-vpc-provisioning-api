from typing import Any

from boto3.dynamodb.conditions import Attr
from common.aws import table
from common.http import response


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # shortcut: full scan, fine for small table. Grows: GSI on constant partition, API paging.
    # created_at read only to sort.
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
