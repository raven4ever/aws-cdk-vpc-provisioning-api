from typing import Any

from common.aws import client
from common.ec2 import tags


def handler(event: dict[str, Any], context: object) -> None:
    """One route table per tier: public to the IGW, private_egress to the NAT, isolated local."""
    ec2 = client("ec2")
    request_id, name = event["id"], event["vpc_name"]
    network, nat_id = event["network"], event["nat"]["nat_id"]
    routes = {
        "public": {"GatewayId": network["igw_id"]},
        "private_egress": {"NatGatewayId": nat_id},
        "private_isolated": None,
    }

    for tier, route in routes.items():
        subnets = [s for s in network["subnets"] if s["tier"] == tier]
        if not subnets:
            continue
        table_id = ec2.create_route_table(
            VpcId=network["aws_vpc_id"],
            TagSpecifications=tags("route-table", request_id, f"{name}-{tier}"),
        )["RouteTable"]["RouteTableId"]
        if route:
            ec2.create_route(RouteTableId=table_id, DestinationCidrBlock="0.0.0.0/0", **route)
        for subnet in subnets:
            ec2.associate_route_table(RouteTableId=table_id, SubnetId=subnet["id"])
