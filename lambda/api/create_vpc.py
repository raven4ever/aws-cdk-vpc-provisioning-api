import json
import re
import uuid
from typing import Any

from botocore.exceptions import ClientError
from common.aws import client, table
from common.http import error, response
from common.quotas import quota
from common.vpc import PENDING, key, now

VPC_SUBNET_TIERS = {"public", "private_egress", "private_isolated"}
VPC_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}")
MIN_PREFIX, MAX_PREFIX = 16, 28  # the CIDR sizes AWS allows for a VPC or subnet
SUBNETS_PER_VPC = "L-407747CB"  # Service Quotas codes of the vpc service
VPCS_PER_REGION = "L-F678F1CE"


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
    # the smallest subnet is MAX_PREFIX, so that bounds how many fit in the VPC
    if len(tiers) > 2 ** (MAX_PREFIX - prefix):
        raise ValueError(f"a /{prefix} VPC cannot hold {len(tiers)} subnets")

    return {"vpc_name": name, "vpc_prefix": prefix, "subnet_tiers": tiers}


def check_quotas(request: dict[str, Any]) -> None:
    """Reject requests that would exceed the account's limits in this Region."""
    tiers = request["subnet_tiers"]

    max_subnets = quota("vpc", SUBNETS_PER_VPC)
    if len(tiers) > max_subnets:
        raise ValueError(f"{len(tiers)} subnets requested, the quota is {max_subnets}")

    # counts every VPC in the Region, not only the ones created by this API
    pages = client("ec2").get_paginator("describe_vpcs").paginate()
    existing = sum(len(page["Vpcs"]) for page in pages)
    max_vpcs = quota("vpc", VPCS_PER_REGION)
    if existing >= max_vpcs:
        raise ValueError(f"this Region already has {existing} VPCs, the quota is {max_vpcs}")


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    try:
        request = parse_request(event.get("body"))
        check_quotas(request)
    except ValueError as e:
        return error(400, str(e))
    except ClientError:
        return error(502, "could not read the AWS quotas")

    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    vpc_id = str(uuid.uuid4())
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

    # execution_id is a placeholder until the creation workflow is started here, named after
    # the id. The workflow later stores the real AWS VPC id on the record as aws_vpc_id.
    return response(200, {"verification": "ok", "id": vpc_id, "execution_id": 0})
