from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_iam,
    aws_lambda,
    aws_logs,
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

        # function IAM role, with no managed policy: the only default permission is writing
        # to the function's own log group (granted below)
        self.role = aws_iam.Role(
            self,
            "Role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # own log group so the role can be limited to it, and it is removed on destroy
        log_group = aws_logs.LogGroup(self, "Logs", removal_policy=RemovalPolicy.DESTROY)
        log_group.grant_write(self.role)

        # Lambda function
        self.function = aws_lambda.Function(
            self,
            "Function",
            runtime=runtime,
            handler=handler,
            code=aws_lambda.Code.from_asset(code_path),
            role=self.role,
            log_group=log_group,
            environment=environment or {},
            # the default 3 seconds is too short for the API calls some handlers make
            timeout=Duration.seconds(15),
        )
