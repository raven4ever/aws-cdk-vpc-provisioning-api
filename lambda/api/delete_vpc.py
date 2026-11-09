import json
import os
import time
from typing import Any

from botocore.exceptions import ClientError
from common.aws import sfn, table
from common.http import error, response
from common.vpc import ACTIVE, DELETING, FAILED, key, name_key, now, set_status, to_api

# deleted VPCs stay readable for this long, then DynamoDB removes the record
TOMBSTONE_SECONDS = 14 * 24 * 3600


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    vpc_id = (event.get("pathParameters") or {}).get("id", "")

    # one conditional write: only an existing ACTIVE or FAILED VPC moves to DELETING,
    # so two concurrent deletes cannot both start a workflow
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

    # the workflow also removes the name lock, so it needs the lock key
    try:
        sfn().start_execution(
            stateMachineArn=os.environ["DELETE_STATE_MACHINE_ARN"],
            input=json.dumps(
                {
                    "id": vpc_id,
                    "name_lock": name_key(previous["vpc_name"])["pk"],
                    "ttl": str(int(time.time()) + TOMBSTONE_SECONDS),  # DynamoDB N value as string
                }
            ),
        )
    except ClientError:
        set_status(vpc_id, previous["status"])
        return error(500, "could not start VPC deletion")

    return response(202, {**to_api(previous), "status": DELETING})
