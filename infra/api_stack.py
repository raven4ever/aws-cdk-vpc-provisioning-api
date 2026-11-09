from aws_cdk import CfnOutput, Stack, aws_apigateway, aws_cognito, aws_dynamodb, aws_iam
from constructs import Construct

from infra.constructs.create_vpc_workflow import CreateWorkflow
from infra.constructs.delete_vpc_workflow import DeleteWorkflow
from infra.constructs.function_factory import ManagedFunction
from infra.constructs.workflow_steps import CleanupFunction

CODE_PATH = "lambda"

FUNCTIONS = {
    "health": {
        "handler": "api.health.handler",
        "http_method": "GET",
        "http_path": "health",
    },
    "create_vpc": {
        "handler": "api.create_vpc.handler",
        "http_method": "POST",
        "http_path": "vpc",
        # shortcut: these read-only actions use "*". The quota ARNs may allow tighter scoping,
        # check that before restricting. ec2:DescribeVpcs has no resource-level permissions.
        "iam_actions": [
            "servicequotas:GetServiceQuota",
            "servicequotas:GetAWSDefaultServiceQuota",
            "ec2:DescribeVpcs",
        ],
        "table_actions": ["dynamodb:PutItem"],
    },
    "list_vpcs": {
        "handler": "api.list_vpcs.handler",
        "http_method": "GET",
        "http_path": "vpc",
        "table_actions": ["dynamodb:Scan"],
    },
    "get_vpc": {
        "handler": "api.get_vpc.handler",
        "http_method": "GET",
        "http_path": "vpc/{id}",
        "table_actions": ["dynamodb:GetItem"],
    },
    "delete_vpc": {
        "handler": "api.delete_vpc.handler",
        "http_method": "DELETE",
        "http_path": "vpc/{id}",
        "table_actions": ["dynamodb:UpdateItem", "dynamodb:GetItem"],
    },
}


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

        # create API Gateway
        api = aws_apigateway.RestApi(
            self,
            "vpc-provisioning-api",
            rest_api_name="vpc-provisioning-api",
            deploy_options=aws_apigateway.StageOptions(stage_name="v1"),
        )

        CfnOutput(self, "ApiUrl", value=api.url)

        # set the authorizer to the created user pool
        authorizer = aws_apigateway.CognitoUserPoolsAuthorizer(
            self,
            "vpc-provisioning-api-authorizer",
            authorizer_name="vpc-provisioning-api-authorizer",
            cognito_user_pools=[user_pool],
        )

        cleanup = CleanupFunction(self, "cleanup").function
        create_workflow = CreateWorkflow(
            self,
            "create-vpc-workflow",
            table=table,
            ipam_pool_id=ipam_pool_id,
            cleanup_function=cleanup,
        )
        delete_workflow = DeleteWorkflow(self, "delete-vpc-workflow", table=table, cleanup=cleanup)

        resources = {}

        # create the API Lambdas
        for func_key, cfg in FUNCTIONS.items():
            print(f"triggering {func_key}")

            # create the function
            function = ManagedFunction(
                self,
                f"vpc-provisioning-api-${func_key}-function",
                handler=cfg["handler"],
                code_path=CODE_PATH,
                environment={"TABLE_NAME": table.table_name} if "table_actions" in cfg else None,
            )
            if func_key == "create_vpc":
                function.function.add_environment(
                    "CREATE_STATE_MACHINE_ARN", create_workflow.state_machine.state_machine_arn
                )
                create_workflow.state_machine.grant_start_execution(function.function)
            if func_key == "delete_vpc":
                function.function.add_environment(
                    "DELETE_STATE_MACHINE_ARN", delete_workflow.state_machine.state_machine_arn
                )
                delete_workflow.state_machine.grant_start_execution(function.function)
            if "iam_actions" in cfg:
                function.role.add_to_policy(
                    aws_iam.PolicyStatement(actions=cfg["iam_actions"], resources=["*"])
                )
            if "table_actions" in cfg:
                table.grant(function.function, *cfg["table_actions"])

            # attach Lambda integration
            # walk the path segments, reusing resources already created (vpc, vpc/{id})
            target_resource = api.root
            walked = ""
            for segment in cfg["http_path"].strip("/").split("/"):
                walked += f"/{segment}"
                if walked not in resources:
                    resources[walked] = target_resource.add_resource(segment)
                target_resource = resources[walked]

            target_resource.add_method(
                cfg["http_method"],
                aws_apigateway.LambdaIntegration(function.function),
                authorizer=authorizer,
                authorization_type=aws_apigateway.AuthorizationType.COGNITO,
            )
