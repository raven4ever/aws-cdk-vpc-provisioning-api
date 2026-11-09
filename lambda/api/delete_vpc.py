import json
import os
import time
from typing import Any

from botocore.exceptions import ClientError
from common.aws import client, table
from common.http import error, response
from common.vpc import ACTIVE, DELETING, FAILED, key, name_key, now, set_status, to_api

# DELETED record stays readable this long, then TTL removes it
TOMBSTONE_SECONDS = 14 * 24 * 3600


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    vpc_id = (event.get("pathParameters") or {}).get("id", "")

    # one conditional write: only existing ACTIVE or FAILED moves to DELETING.
    # Two concurrent deletes cannot both start a workflow.
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
        # condition failed: tell missing (404) from wrong state (409)
        item = table().get_item(Key=key(vpc_id)).get("Item")
        if not item:
            return error(404, "VPC not found")
        return error(409, f"VPC is {item['status']}, only {ACTIVE} or {FAILED} can be deleted")

    # workflow also frees the name lock: pass its key
    try:
        client("stepfunctions").start_execution(
            stateMachineArn=os.environ["DELETE_STATE_MACHINE_ARN"],
            input=json.dumps(
                {
                    "id": vpc_id,
                    "name_lock": name_key(previous["vpc_name"])["pk"],
                    "ttl": str(int(time.time()) + TOMBSTONE_SECONDS),  # DynamoDB N is a string
                }
            ),
        )
    except ClientError:
        set_status(vpc_id, previous["status"])
        return error(500, "could not start VPC deletion")

    return response(202, {**to_api(previous), "status": DELETING})
