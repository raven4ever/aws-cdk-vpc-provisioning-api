from typing import Any

from common.aws import client
from common.ec2 import tags


def handler(event: dict[str, Any], context: object) -> dict[str, str]:
    """Start a NAT gateway in the first public subnet. The workflow waits for it to be available."""
    ec2 = client("ec2")
    request_id, name = event["id"], event["vpc_name"]
    # the request validation guarantees a public subnet whenever there is a private_egress one
    public = next(s for s in event["network"]["subnets"] if s["tier"] == "public")

    allocation_id = ec2.allocate_address(
        Domain="vpc", TagSpecifications=tags("elastic-ip", request_id, name)
    )["AllocationId"]
    nat_id = ec2.create_nat_gateway(
        SubnetId=public["id"],
        AllocationId=allocation_id,
        ClientToken=request_id,
        TagSpecifications=tags("natgateway", request_id, name),
    )["NatGateway"]["NatGatewayId"]
    return {"nat_id": nat_id}
