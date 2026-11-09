from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    Stack,
    aws_apigateway,
    aws_cognito,
    aws_dynamodb,
    aws_iam,
    aws_lambda,
    aws_stepfunctions,
    custom_resources,
)
from constructs import Construct

from infra.constructs.cleanup_function import CleanupFunction
from infra.constructs.create_vpc_workflow import CreateVpcWorkflow
from infra.constructs.delete_vpc_workflow import DeleteVpcWorkflow
from infra.constructs.managed_function import ManagedFunction


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool: aws_cognito.IUserPool,
        table: aws_dynamodb.ITable,
        ipam_pool_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api = aws_apigateway.RestApi(
            self,
            "vpc-provisioning-api",
            rest_api_name="vpc-provisioning-api",
            deploy_options=aws_apigateway.StageOptions(stage_name="v1"),
        )

        # api.url ends with "/", the base URL does not: clients append "/vpc" etc.
        CfnOutput(
            self,
            "ApiBaseUrl",
            value=f"https://{api.rest_api_id}.execute-api.{self.region}.{self.url_suffix}"
            f"/{api.deployment_stage.stage_name}",
        )

        authorizer = aws_apigateway.CognitoUserPoolsAuthorizer(
            self,
            "vpc-provisioning-api-authorizer",
            authorizer_name="vpc-provisioning-api-authorizer",
            cognito_user_pools=[user_pool],
        )

        cleanup = CleanupFunction(self, "cleanup").function
        create_workflow = CreateVpcWorkflow(
            self,
            "create-vpc-workflow",
            table=table,
            ipam_pool_id=ipam_pool_id,
            cleanup_function=cleanup,
        )
        delete_workflow = DeleteVpcWorkflow(
            self, "delete-vpc-workflow", table=table, cleanup=cleanup
        )

        # cdk destroy deletes this first. Cleanup removes all API-created VPCs, then waits for IPAM
        # to release their CIDRs. Else Foundation stack cannot delete the pool.
        ipam_released = ManagedFunction(
            self,
            "teardown-ipam-released",
            handler="workflow.cleanup.is_complete",
            environment={"IPAM_POOL_ID": ipam_pool_id},
        )
        ipam_released.role.add_to_policy(
            aws_iam.PolicyStatement(actions=["ec2:GetIpamPoolAllocations"], resources=["*"])
        )
        CustomResource(
            self,
            "teardown",
            service_token=custom_resources.Provider(
                self,
                "teardown-provider",
                on_event_handler=cleanup,
                is_complete_handler=ipam_released.function,
                query_interval=Duration.minutes(1),
                # custom resource gets 1 h max
                total_timeout=Duration.minutes(55),
            ).service_token,
        )

        def route(
            resource: aws_apigateway.IResource,
            method: str,
            name: str,
            *,
            table_actions: list[str] | None = None,
            starts: tuple[str, aws_stepfunctions.StateMachine] | None = None,
        ) -> aws_lambda.IFunction:
            """One Lambda per route, with only the permissions it needs."""
            fn = ManagedFunction(
                self, f"vpc-provisioning-api-{name}-function", handler=f"api.{name}.handler"
            )
            if table_actions:
                fn.function.add_environment("TABLE_NAME", table.table_name)
                table.grant(fn.function, *table_actions)
            if starts:
                env_name, state_machine = starts
                fn.function.add_environment(env_name, state_machine.state_machine_arn)
                state_machine.grant_start_execution(fn.function)
            resource.add_method(
                method,
                aws_apigateway.LambdaIntegration(fn.function),
                authorizer=authorizer,
                authorization_type=aws_apigateway.AuthorizationType.COGNITO,
            )
            return fn.function

        vpcs = api.root.add_resource("vpc")
        vpc = vpcs.add_resource("{id}")

        route(api.root.add_resource("health"), "GET", "health")
        route(
            vpcs,
            "POST",
            "create_vpc",
            table_actions=["dynamodb:PutItem"],
            starts=("CREATE_STATE_MACHINE_ARN", create_workflow.state_machine),
        )
        route(vpcs, "GET", "list_vpcs", table_actions=["dynamodb:Scan"])
        route(vpc, "GET", "get_vpc", table_actions=["dynamodb:GetItem"])
        route(
            vpc,
            "DELETE",
            "delete_vpc",
            table_actions=["dynamodb:UpdateItem", "dynamodb:GetItem"],
            starts=("DELETE_STATE_MACHINE_ARN", delete_workflow.state_machine),
        )
