from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cognito,
    aws_dynamodb,
    aws_ec2,
    custom_resources,
)
from constructs import Construct


class FoundationStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        ipam_cidr: str,
        test_user_name: str,
        test_user_email: str,
        test_user_password: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = aws_dynamodb.Table(
            self,
            "vpc-provisioning-api-table",
            table_name="vpc-provisioning-api-table",
            partition_key=aws_dynamodb.Attribute(name="pk", type=aws_dynamodb.AttributeType.STRING),
            sort_key=aws_dynamodb.Attribute(name="sk", type=aws_dynamodb.AttributeType.STRING),
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
            # DELETED tombstones expire via this epoch-seconds attribute
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_pool = aws_cognito.UserPool(
            self,
            "vpc-provisioning-api-user-pool",
            user_pool_name="vpc-provisioning-api-user-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=aws_cognito.SignInAliases(username=True, email=True),
            password_policy=aws_cognito.PasswordPolicy(
                min_length=17,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(3),
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        test_user = aws_cognito.CfnUserPoolUser(
            self,
            "TestUser",
            user_pool_id=self.user_pool.user_pool_id,
            username=test_user_name,
            user_attributes=[
                {"name": "email", "value": test_user_email},
                {"name": "email_verified", "value": "true"},
            ],
            # no invite email to dummy address
            message_action="SUPPRESS",
        )

        # set password at deploy: login works with no extra command.
        # on_update also runs on create, and reapplies a changed password.
        custom_resources.AwsCustomResource(
            self,
            "SetUserPassword",
            on_update=custom_resources.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminSetUserPassword",
                parameters={
                    "UserPoolId": self.user_pool.user_pool_id,
                    "Username": test_user.username,
                    # no forced change on first login
                    "Permanent": True,
                    "Password": test_user_password,
                },
                physical_resource_id=custom_resources.PhysicalResourceId.of(
                    f"{test_user.username}-password"
                ),
            ),
            # this pool only, not every pool in account
            policy=custom_resources.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[self.user_pool.user_pool_arn]
            ),
        )

        self.client = self.user_pool.add_client(
            "AppClient",
            auth_flows=aws_cognito.AuthFlow(user_password=True),
            generate_secret=False,
        )

        CfnOutput(self, "UserPoolClientId", value=self.client.user_pool_client_id)

        # advanced tier: free tier has no private IPv4 pools
        ipam = aws_ec2.CfnIPAM(
            self,
            "vpc-provisioning-api-ipam",
            description="vpc-provisioning-api",
            tier="advanced",
            operating_regions=[
                aws_ec2.CfnIPAM.IpamOperatingRegionProperty(region_name=self.region)
            ],
        )

        # single Region (ADR-007): a VPC draws only from a pool in its own Region
        self.ipam_pool = aws_ec2.CfnIPAMPool(
            self,
            "vpc-provisioning-api-ipam-pool",
            description="vpc-provisioning-api",
            address_family="ipv4",
            ipam_scope_id=ipam.attr_private_default_scope_id,
            locale=self.region,
            provisioned_cidrs=[aws_ec2.CfnIPAMPool.ProvisionedCidrProperty(cidr=ipam_cidr)],
        )

        CfnOutput(self, "IpamPoolId", value=self.ipam_pool.attr_ipam_pool_id)
