from typing import Any

from common.aws import client
from common.ec2 import by_request


def handler(event: dict[str, Any], context: object) -> None:
    """Delete everything tagged with the request id. Safe to run again on a partial or empty set."""
    ec2 = client("ec2")
    filters = by_request(event["id"])

    # the NAT gateway first: it holds an ENI in a subnet and an Elastic IP
    nats = [
        n["NatGatewayId"]
        for n in ec2.describe_nat_gateways(Filter=filters)["NatGateways"]
        if n["State"] != "deleted"
    ]
    for nat_id in nats:
        ec2.delete_nat_gateway(NatGatewayId=nat_id)
    if nats:
        ec2.get_waiter("nat_gateway_deleted").wait(NatGatewayIds=nats)

    for address in ec2.describe_addresses(Filters=filters)["Addresses"]:
        ec2.release_address(AllocationId=address["AllocationId"])

    for vpc in ec2.describe_vpcs(Filters=filters)["Vpcs"]:
        vpc_filter = [{"Name": "vpc-id", "Values": [vpc["VpcId"]]}]
        for subnet in ec2.describe_subnets(Filters=vpc_filter)["Subnets"]:
            ec2.delete_subnet(SubnetId=subnet["SubnetId"])
        for table in ec2.describe_route_tables(Filters=vpc_filter)["RouteTables"]:
            if not any(a["Main"] for a in table["Associations"]):
                ec2.delete_route_table(RouteTableId=table["RouteTableId"])
        attached = [{"Name": "attachment.vpc-id", "Values": [vpc["VpcId"]]}]
        for igw in ec2.describe_internet_gateways(Filters=attached)["InternetGateways"]:
            ec2.detach_internet_gateway(
                InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc["VpcId"]
            )
            ec2.delete_internet_gateway(InternetGatewayId=igw["InternetGatewayId"])
        ec2.delete_vpc(VpcId=vpc["VpcId"])
