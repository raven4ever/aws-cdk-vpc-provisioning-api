from aws_cdk import (
    Duration,
    aws_dynamodb,
    aws_iam,
    aws_lambda,
    aws_stepfunctions,
    aws_stepfunctions_tasks,
)
from constructs import Construct

from infra.constructs.managed_function import ManagedFunction
from infra.constructs.workflow_steps import cleanup_task, set_status

# create calls have no useful resource-level scoping: the action list is the limit.
# shortcut: resources "*". Tighten with aws:RequestTag/vpc-provisioning-api:id if needed.
EC2_ACTIONS = {
    "build_network": [
        "ec2:CreateVpc",
        "ec2:AllocateIpamPoolCidr",
        "ec2:DescribeVpcs",
        "ec2:CreateTags",
        "ec2:DescribeAvailabilityZones",
        "ec2:CreateSubnet",
        "ec2:ModifySubnetAttribute",
        "ec2:CreateInternetGateway",
        "ec2:AttachInternetGateway",
    ],
    "create_nat": ["ec2:AllocateAddress", "ec2:CreateNatGateway", "ec2:CreateTags"],
    "create_routes": [
        "ec2:CreateRouteTable",
        "ec2:CreateRoute",
        "ec2:AssociateRouteTable",
        "ec2:CreateTags",
    ],
}


class CreateVpcWorkflow(Construct):
    """Step Functions workflow that builds a VPC, its subnets, gateways and routes."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        table: aws_dynamodb.ITable,
        ipam_pool_id: str,
        cleanup_function: aws_lambda.IFunction,
    ) -> None:
        super().__init__(scope, id)

        def function(
            name: str, timeout: Duration, result_path: str, **env: str
        ) -> aws_stepfunctions_tasks.LambdaInvoke:
            fn = ManagedFunction(
                self,
                name,
                handler=f"workflow.{name}.handler",
                environment=env,
                timeout=timeout,
            )
            fn.role.add_to_policy(
                aws_iam.PolicyStatement(actions=EC2_ACTIONS[name], resources=["*"])
            )
            if name == "build_network":
                table.grant(fn.function, "dynamodb:UpdateItem")
            # whole state is Lambda input, return lands at result_path
            return aws_stepfunctions_tasks.LambdaInvoke(
                self,
                name + "-task",
                lambda_function=fn.function,
                payload_response_only=True,
                result_path=result_path,
                state_name=name,
            )

        build_network = function(
            "build_network",
            Duration.minutes(3),
            "$.network",
            IPAM_POOL_ID=ipam_pool_id,
            TABLE_NAME=table.table_name,
        )
        create_nat = function("create_nat", Duration.seconds(30), "$.nat")
        create_routes = function(
            "create_routes", Duration.seconds(60), aws_stepfunctions.JsonPath.DISCARD
        )
        cleanup = cleanup_task(self, cleanup_function)

        creating = set_status(self, "SetCreating", table, "CREATING")
        active = set_status(self, "SetActive", table, "ACTIVE")
        failed = set_status(self, "SetFailed", table, "FAILED", reason=True)

        # failure: clean up, record reason, end execution as failed
        failed.next(aws_stepfunctions.Fail(self, "Failed"))
        cleanup.next(failed)
        # own path: keeps the original $.error for status_reason
        cleanup.add_catch(failed, result_path="$.cleanup_error")

        # NAT takes minutes: poll until available
        wait = aws_stepfunctions.Wait(
            self, "WaitForNat", time=aws_stepfunctions.WaitTime.duration(Duration.seconds(30))
        )
        describe = aws_stepfunctions_tasks.CallAwsService(
            self,
            "DescribeNat",
            service="ec2",
            action="describeNatGateways",
            parameters={
                "NatGatewayIds": aws_stepfunctions.JsonPath.array(
                    aws_stepfunctions.JsonPath.string_at("$.nat.nat_id")
                )
            },
            iam_resources=["*"],
            result_selector={
                "state": aws_stepfunctions.JsonPath.string_at("$.NatGateways[0].State")
            },
            result_path="$.nat_status",
        )
        nat_failed = aws_stepfunctions.Pass(
            self,
            "NatFailed",
            result=aws_stepfunctions.Result.from_object(
                {"Error": "NatFailed", "Cause": "the NAT gateway failed to become available"}
            ),
            result_path="$.error",
        )
        # create_routes always reads $.nat
        no_nat = aws_stepfunctions.Pass(
            self,
            "NoNat",
            result=aws_stepfunctions.Result.from_object({"nat_id": None}),
            result_path="$.nat",
        )

        nat_ready = (
            aws_stepfunctions.Choice(self, "NatReady")
            .when(
                aws_stepfunctions.Condition.string_equals("$.nat_status.state", "available"),
                create_routes,
            )
            .when(
                aws_stepfunctions.Condition.string_equals("$.nat_status.state", "failed"),
                nat_failed,
            )
            .otherwise(wait)
        )
        needs_nat = (
            aws_stepfunctions.Choice(self, "NeedsNat")
            .when(
                aws_stepfunctions.Condition.boolean_equals("$.network.needs_nat", True), create_nat
            )
            .otherwise(no_nat)
        )

        build_network.add_catch(cleanup, result_path="$.error")
        create_nat.add_catch(cleanup, result_path="$.error")
        describe.add_catch(cleanup, result_path="$.error")
        create_routes.add_catch(cleanup, result_path="$.error")
        nat_failed.next(cleanup)

        build_network.next(needs_nat)
        create_nat.next(wait)
        wait.next(describe)
        describe.next(nat_ready)
        no_nat.next(create_routes)
        create_routes.next(active)

        self.state_machine = aws_stepfunctions.StateMachine(
            self,
            "StateMachine",
            state_machine_name="vpc-provisioning-api-create-vpc",
            definition_body=aws_stepfunctions.DefinitionBody.from_chainable(
                creating.next(build_network)
            ),
            # shortcut: bounds a stuck NAT wait, but a timed-out run skips the cleanup
            timeout=Duration.minutes(30),
        )
