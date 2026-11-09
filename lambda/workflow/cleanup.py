import os
from typing import Any

from common.aws import client
from common.ec2 import ALL_REQUESTS, by_request


def handler(event: dict[str, Any], context: object) -> dict:
    """Called by the workflows with a request id, and by CloudFormation on stack teardown."""
    if "RequestType" in event:
        # CloudFormation custom resource: only Delete does work
        if event["RequestType"] == "Delete":
            delete_tagged(ALL_REQUESTS)
        return {}
    delete_tagged(by_request(event["id"]))
    return {}


def delete_tagged(filters: list[dict]) -> None:
    """Delete everything matching the tag filters. Safe to run again on a partial or empty set."""
    ec2 = client("ec2")

    # NAT first: holds an ENI in a subnet and the Elastic IP
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
            # main table goes with the VPC
            if not any(a["Main"] for a in table["Associations"]):
                ec2.delete_route_table(RouteTableId=table["RouteTableId"])
        attached = [{"Name": "attachment.vpc-id", "Values": [vpc["VpcId"]]}]
        for igw in ec2.describe_internet_gateways(Filters=attached)["InternetGateways"]:
            ec2.detach_internet_gateway(
                InternetGatewayId=igw["InternetGatewayId"], VpcId=vpc["VpcId"]
            )
            ec2.delete_internet_gateway(InternetGatewayId=igw["InternetGatewayId"])
        ec2.delete_vpc(VpcId=vpc["VpcId"])


def is_complete(event: dict[str, Any], context: object) -> dict:
    """Custom resource completion check: on stack delete, wait until IPAM has released every
    VPC CIDR. IPAM does that some time after the VPC is gone, and until then the IPAM pool in
    the Foundation stack cannot be deleted."""
    if event["RequestType"] != "Delete":
        return {"IsComplete": True}
    pool = client("ec2").get_ipam_pool_allocations(IpamPoolId=os.environ["IPAM_POOL_ID"])
    return {"IsComplete": not pool["IpamPoolAllocations"]}
