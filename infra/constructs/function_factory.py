from aws_cdk import (
    aws_iam,
    aws_lambda,
)
from constructs import Construct


class ManagedFunction(Construct):
    """A reusable CDK Construct that bundles a Lambda function with a dedicated IAM role."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        handler: str,
        code_path: str,
        runtime: aws_lambda.Runtime = aws_lambda.Runtime.PYTHON_3_14,
        environment: dict = None,
    ) -> None:
        super().__init__(scope, id)

        # function IAM role
        self.role = aws_iam.Role(
            self,
            "Role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Lambda function
        self.function = aws_lambda.Function(
            self,
            "Resource",
            runtime=runtime,
            handler=handler,
            code=aws_lambda.Code.from_asset(code_path),
            role=self.role,
            environment=environment or {},
        )
