from aws_cdk import Stack, aws_apigateway, aws_cognito
from constructs import Construct

from infra.constructs.function_factory import ManagedFunction

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
    },
    "list_vpcs": {
        "handler": "api.list_vpcs.handler",
        "http_method": "GET",
        "http_path": "vpc",
    },
    "get_vpc": {
        "handler": "api.get_vpc.handler",
        "http_method": "GET",
        "http_path": "vpc/{id}",
    },
    "delete_vpc": {
        "handler": "api.delete_vpc.handler",
        "http_method": "DELETE",
        "http_path": "vpc/{id}",
    },
}


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool: aws_cognito.IUserPool,
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

        # set the authorizer to the created user pool
        authorizer = aws_apigateway.CognitoUserPoolsAuthorizer(
            self,
            "vpc-provisioning-api-authorizer",
            authorizer_name="vpc-provisioning-api-authorizer",
            cognito_user_pools=[user_pool],
        )

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
            )

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

        # create the create step function
        # CreateWorkflow(self)
