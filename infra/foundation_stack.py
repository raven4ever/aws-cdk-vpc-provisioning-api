from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_cognito,
    aws_dynamodb,
)
from aws_cdk import (
    custom_resources as cr,
)
from constructs import Construct


class FoundationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Table to store VPC requests data
        self.table = aws_dynamodb.Table(
            self,
            "vpc-provisioning-api-table",
            table_name="vpc-provisioning-api-table",
            partition_key=aws_dynamodb.Attribute(name="pk", type=aws_dynamodb.AttributeType.STRING),
            sort_key=aws_dynamodb.Attribute(name="sk", type=aws_dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # create Cognito Pool
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

        # add test user
        test_user = aws_cognito.CfnUserPoolUser(
            self,
            "TestUser",
            user_pool_id=self.user_pool.user_pool_id,
            username="testuser@example.com",
            user_attributes=[
                {"name": "email", "value": "testuser@example.com"},
                {"name": "email_verified", "value": "true"},
            ],
            # prevent sending email invitation to dummy test addresses
            message_action="SUPPRESS",
        )

        # set the user password
        cr.AwsCustomResource(
            self,
            "SetUserPassword",
            on_create=cr.AwsSdkCall(
                service="CognitoIdentityServiceProvider",
                action="adminSetUserPassword",
                parameters={
                    "UserPoolId": self.user_pool.user_pool_id,
                    "Username": test_user.username,
                    "Permanent": True,
                    # Set to True so the user doesn't need to change it on first login
                    "Password": "MySecurePassword123!",
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"{test_user.username}-password"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
        )

        self.client = self.user_pool.add_client(
            "AppClient",
            auth_flows=aws_cognito.AuthFlow(user_password=True),
            generate_secret=False,
        )
