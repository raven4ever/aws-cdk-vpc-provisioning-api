import json
import os
import re
import uuid
from typing import Any

from botocore.exceptions import ClientError
from common.aws import client, table
from common.http import error, response
from common.vpc import FAILED, PENDING, key, name_key, now, set_status

VPC_SUBNET_TIERS = {"public", "private_egress", "private_isolated"}
VPC_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}")
MIN_PREFIX, MAX_PREFIX = 16, 28  # AWS limits for VPC and subnet CIDRs
# AWS default subnets-per-VPC quota. A raised quota still caps here: change this to use more.
MAX_SUBNETS = 200


def parse_request(raw: str | None) -> dict[str, Any]:
    """Check the body shape, raise ValueError with a client-facing message."""
    try:
        data = json.loads(raw or "")
    except json.JSONDecodeError:
        raise ValueError("body must be valid JSON") from None
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")

    name = data.get("vpc_name")
    if not isinstance(name, str) or not VPC_NAME_RE.fullmatch(name):
        raise ValueError("vpc_name must be 1-63 characters: letters, digits, space, '_', '.', '-'")

    prefix = data.get("vpc_prefix")
    # bool is an int subclass, reject it explicitly
    if (
        isinstance(prefix, bool)
        or not isinstance(prefix, int)
        or not MIN_PREFIX <= prefix <= MAX_PREFIX
    ):
        raise ValueError(f"vpc_prefix must be an integer between {MIN_PREFIX} and {MAX_PREFIX}")

    tiers = data.get("subnet_tiers")
    if not isinstance(tiers, list) or not tiers or not set(tiers) <= VPC_SUBNET_TIERS:
        raise ValueError(f"subnet_tiers must be a non-empty list of {sorted(VPC_SUBNET_TIERS)}")
    if len(tiers) > MAX_SUBNETS:
        raise ValueError(f"subnet_tiers can have at most {MAX_SUBNETS} entries")
    # NAT gateway lives in a public subnet
    if "private_egress" in tiers and "public" not in tiers:
        raise ValueError("private_egress subnets need at least one public subnet")
    # smallest subnet is /MAX_PREFIX: bounds how many fit
    if len(tiers) > 2 ** (MAX_PREFIX - prefix):
        raise ValueError(f"a /{prefix} VPC cannot hold {len(tiers)} subnets")

    return {"vpc_name": name, "vpc_prefix": prefix, "subnet_tiers": tiers}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    # account limits (VPCs per Region, Elastic IPs, NAT gateways) are not checked here: the
    # workflow fails with the AWS error name, e.g. VpcLimitExceeded, and cleans up
    try:
        request = parse_request(event.get("body"))
    except ValueError as e:
        return error(400, str(e))

    # generate internal VPC ID
    vpc_id = str(uuid.uuid4())
    try:
        table().put_item(
            Item={**name_key(request["vpc_name"]), "id": vpc_id},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return error(409, f"a VPC named {request['vpc_name']} already exists")

    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    timestamp = now()
    table().put_item(
        Item={
            **key(vpc_id),
            "id": vpc_id,
            **request,
            "status": PENDING,
            "created_by": claims.get("sub", "unknown"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )

    # execution named after id: id is the only handle the client needs
    try:
        client("stepfunctions").start_execution(
            stateMachineArn=os.environ["CREATE_STATE_MACHINE_ARN"],
            name=vpc_id,
            input=json.dumps({"id": vpc_id, **request}),
        )
    except ClientError:
        set_status(vpc_id, FAILED, "could not start the creation workflow")
        return error(500, "could not start VPC creation")

    return response(202, {"id": vpc_id})
