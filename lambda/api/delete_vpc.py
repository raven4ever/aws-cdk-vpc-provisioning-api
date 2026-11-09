from typing import Any

from botocore.exceptions import ClientError
from common.aws import table
from common.http import error, response
from common.vpc import ACTIVE, DELETING, FAILED, key, now, to_api


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    vpc_id = (event.get("pathParameters") or {}).get("id", "")

    # one conditional write: only an existing ACTIVE or FAILED VPC moves to DELETING,
    # so two concurrent deletes cannot both start a workflow later
    try:
        previous = table().update_item(
            Key=key(vpc_id),
            UpdateExpression="SET #s = :deleting, updated_at = :t",
            ConditionExpression="attribute_exists(pk) AND #s IN (:active, :failed)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":deleting": DELETING,
                ":active": ACTIVE,
                ":failed": FAILED,
                ":t": now(),
            },
            ReturnValues="ALL_OLD",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        item = table().get_item(Key=key(vpc_id)).get("Item")
        if not item:
            return error(404, "VPC not found")
        return error(409, f"VPC is {item['status']}, only {ACTIVE} or {FAILED} can be deleted")

    # execution_id is a placeholder until the deletion workflow is started here (named after the id)
    return response(202, {**to_api(previous), "status": DELETING, "execution_id": 0})
