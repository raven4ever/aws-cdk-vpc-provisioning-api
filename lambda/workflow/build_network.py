import ipaddress
import os
from typing import Any

from common.aws import aws_error_names, client, table
from common.ec2 import tags
from common.vpc import key, now


@aws_error_names
def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Create the VPC from the IPAM pool, the internet gateway and the subnets."""
    ec2 = client("ec2")
    request_id, name, tiers = event["id"], event["vpc_name"], event["subnet_tiers"]

    # IPAM picks a free CIDR of this size
    vpc = ec2.create_vpc(
        Ipv4IpamPoolId=os.environ["IPAM_POOL_ID"],
        Ipv4NetmaskLength=event["vpc_prefix"],
        TagSpecifications=tags("vpc", request_id, name),
    )["Vpc"]
    vpc_id, cidr = vpc["VpcId"], vpc["CidrBlock"]
    ec2.get_waiter("vpc_available").wait(VpcIds=[vpc_id])

    # equal split: the smallest prefix whose network count covers every subnet
    prefix = event["vpc_prefix"] + (len(tiers) - 1).bit_length()
    networks = ipaddress.ip_network(cidr).subnets(new_prefix=prefix)
    zones = [
        z["ZoneName"]
        for z in ec2.describe_availability_zones(
            Filters=[{"Name": "zone-type", "Values": ["availability-zone"]}]
        )["AvailabilityZones"]
    ]

    subnets = []
    # strict=False: the equal split can produce more networks than subnets
    for i, (tier, network) in enumerate(zip(tiers, networks, strict=False)):
        zone = zones[i % len(zones)]
        subnet_id = ec2.create_subnet(
            VpcId=vpc_id,
            CidrBlock=str(network),
            AvailabilityZone=zone,
            TagSpecifications=tags("subnet", request_id, f"{name}-{tier}-{i}"),
        )["Subnet"]["SubnetId"]
        if tier == "public":
            ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": True})
        subnets.append({"id": subnet_id, "tier": tier, "cidr": str(network), "az": zone})

    igw_id = None
    if any(s["tier"] == "public" for s in subnets):
        igw_id = ec2.create_internet_gateway(
            TagSpecifications=tags("internet-gateway", request_id, name)
        )["InternetGateway"]["InternetGatewayId"]
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

    # save AWS ids now: GET shows them even if a later step fails
    table().update_item(
        Key=key(request_id),
        UpdateExpression="SET aws_vpc_id = :v, cidr = :c, subnets = :s, updated_at = :t",
        ExpressionAttributeValues={":v": vpc_id, ":c": cidr, ":s": subnets, ":t": now()},
    )
    return {
        "aws_vpc_id": vpc_id,
        "cidr": cidr,
        "igw_id": igw_id,
        "needs_nat": any(s["tier"] == "private_egress" for s in subnets),
        "subnets": subnets,
    }
