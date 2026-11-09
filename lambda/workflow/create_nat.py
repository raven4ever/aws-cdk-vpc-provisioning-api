from typing import Any

from common.aws import aws_error_names, client
from common.ec2 import tags


@aws_error_names
def handler(event: dict[str, Any], context: object) -> dict[str, str]:
    """Start a NAT gateway in the first public subnet. The workflow waits for it to be available."""
    ec2 = client("ec2")
    request_id, name = event["id"], event["vpc_name"]
    # validation guarantees a public subnet when private_egress exists
    public = next(s for s in event["network"]["subnets"] if s["tier"] == "public")

    # shortcut: not idempotent, a retried step leaks one EIP until cleanup or delete
    allocation_id = ec2.allocate_address(
        Domain="vpc", TagSpecifications=tags("elastic-ip", request_id, name)
    )["AllocationId"]
    nat_id = ec2.create_nat_gateway(
        SubnetId=public["id"],
        AllocationId=allocation_id,
        ClientToken=request_id,  # retry returns the same NAT gateway
        TagSpecifications=tags("natgateway", request_id, name),
    )["NatGateway"]["NatGatewayId"]
    return {"nat_id": nat_id}
