from aws_cdk import Duration, aws_dynamodb, aws_iam, aws_lambda
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.constructs.function_factory import ManagedFunction
from infra.constructs.workflow_steps import cleanup_task, set_status

CODE_PATH = "lambda"

# the limit is the action list: create calls have no useful resource-level scoping
# shortcut: resources "*", tighten with aws:RequestTag/vpc-provisioning-api:id conditions if needed
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


class CreateWorkflow(Construct):
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
        ) -> tasks.LambdaInvoke:
            fn = ManagedFunction(
                self,
                name,
                handler=f"workflow.{name}.handler",
                code_path=CODE_PATH,
                environment=env,
                timeout=timeout,
            )
            fn.role.add_to_policy(
                aws_iam.PolicyStatement(actions=EC2_ACTIONS[name], resources=["*"])
            )
            if name == "build_network":
                table.grant(fn.function, "dynamodb:UpdateItem")
            # the whole state is the Lambda input, its return value lands at result_path
            return tasks.LambdaInvoke(
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
        create_routes = function("create_routes", Duration.seconds(60), sfn.JsonPath.DISCARD)
        cleanup = cleanup_task(self, cleanup_function)

        creating = set_status(self, "SetCreating", table, "CREATING")
        active = set_status(self, "SetActive", table, "ACTIVE")
        failed = set_status(self, "SetFailed", table, "FAILED", reason=True)

        # failure path: remove what was built, record the reason, end the execution as failed
        failed.next(sfn.Fail(self, "Failed"))
        cleanup.next(failed)
        cleanup.add_catch(failed, result_path="$.cleanup_error")

        # NAT gateways take a few minutes: poll until available
        wait = sfn.Wait(self, "WaitForNat", time=sfn.WaitTime.duration(Duration.seconds(30)))
        describe = tasks.CallAwsService(
            self,
            "DescribeNat",
            service="ec2",
            action="describeNatGateways",
            parameters={
                "NatGatewayIds": sfn.JsonPath.array(sfn.JsonPath.string_at("$.nat.nat_id"))
            },
            iam_resources=["*"],
            result_selector={"state": sfn.JsonPath.string_at("$.NatGateways[0].State")},
            result_path="$.nat_status",
        )
        nat_failed = sfn.Pass(
            self,
            "NatFailed",
            result=sfn.Result.from_object(
                {"Error": "NatFailed", "Cause": "the NAT gateway failed to become available"}
            ),
            result_path="$.error",
        )
        no_nat = sfn.Pass(
            self,
            "NoNat",
            result=sfn.Result.from_object({"nat_id": None}),
            result_path="$.nat",
        )

        nat_ready = (
            sfn.Choice(self, "NatReady")
            .when(sfn.Condition.string_equals("$.nat_status.state", "available"), create_routes)
            .when(sfn.Condition.string_equals("$.nat_status.state", "failed"), nat_failed)
            .otherwise(wait)
        )
        needs_nat = (
            sfn.Choice(self, "NeedsNat")
            .when(sfn.Condition.boolean_equals("$.network.needs_nat", True), create_nat)
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

        self.state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            state_machine_name="vpc-provisioning-api-create-vpc",
            definition_body=sfn.DefinitionBody.from_chainable(creating.next(build_network)),
            # shortcut: bounds a stuck NAT wait, but a timed-out run skips the cleanup
            timeout=Duration.minutes(30),
        )
