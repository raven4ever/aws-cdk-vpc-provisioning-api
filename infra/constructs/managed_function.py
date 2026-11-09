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
        environment: dict | None = None,
        timeout: Duration | None = None,
    ) -> None:
        super().__init__(scope, id)

        # no managed policy: only default permission is writing to own log group
        self.role = aws_iam.Role(
            self,
            "Role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # own log group: role scoped to it, removed on destroy
        log_group = aws_logs.LogGroup(self, "Logs", removal_policy=RemovalPolicy.DESTROY)
        log_group.grant_write(self.role)

        self.function = aws_lambda.Function(
            self,
            "Function",
            runtime=aws_lambda.Runtime.PYTHON_3_14,
            # pure Python, no native deps: Arm duration 20% cheaper than x86
            architecture=aws_lambda.Architecture.ARM_64,
            handler=handler,
            # one asset for every function (ADR-005)
            code=aws_lambda.Code.from_asset("lambda"),
            role=self.role,
            log_group=log_group,
            environment=environment or {},
            # default 3 s too short for the AWS calls some handlers make
            timeout=timeout or Duration.seconds(15),
        )
