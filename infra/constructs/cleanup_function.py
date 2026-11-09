from aws_cdk import Duration, aws_iam
from constructs import Construct

from infra.constructs.managed_function import ManagedFunction

# shortcut: resources "*", tighten with aws:ResourceTag/vpc-provisioning-api:id conditions
CLEANUP_ACTIONS = [
    "ec2:DescribeNatGateways",
    "ec2:DeleteNatGateway",
    "ec2:DescribeAddresses",
    "ec2:ReleaseAddress",
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DeleteSubnet",
    "ec2:DescribeRouteTables",
    "ec2:DeleteRouteTable",
    "ec2:DescribeInternetGateways",
    "ec2:DetachInternetGateway",
    "ec2:DeleteInternetGateway",
    "ec2:DeleteVpc",
]


class CleanupFunction(Construct):
    """The teardown Lambda, shared by the create workflow (on failure) and the delete workflow."""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)
        fn = ManagedFunction(
            self,
            "Function",
            handler="workflow.cleanup.handler",
            timeout=Duration.minutes(10),
        )
        fn.role.add_to_policy(aws_iam.PolicyStatement(actions=CLEANUP_ACTIONS, resources=["*"]))
        self.function = fn.function
