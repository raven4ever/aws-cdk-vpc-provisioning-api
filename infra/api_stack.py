from aws_cdk import Stack, aws_apigateway, aws_cognito
from constructs import Construct

from infra.constructs.create_vpc_workflow import CreateWorkflow
from infra.constructs.function_factory import ManagedFunction

FUNCTIONS = {
    "health": {
        "handler": "main.lambda_handler",
        "path": "lambda/health",
        "http_method": "GET",
        "http_path": "health",
    },
    "create_vpc": {
        "handler": "main.lambda_handler",
        "path": "lambda/create_vpc",
        "http_method": "POST",
        "http_path": "vpc",
    },
    "get_vpc": {
        "handler": "main.lambda_handler",
        "path": "lambda/get_vpc",
        "http_method": "GET",
        "http_path": "vpc",
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

        for func_key, cfg in FUNCTIONS.items():
            print(f"triggering {func_key}")
            # create the function
            function = ManagedFunction(
                self,
                f"vpc-provisioning-api-${func_key}-function",
                handler=cfg["handler"],
                code_path=cfg["path"],
            )

            # attach Lambda integration
            path = cfg["http_path"].strip("/")

            if not path:
                target_resource = api.root
            elif path in resources:
                target_resource = resources[path]
            else:
                target_resource = api.root.add_resource(path)
                resources[path] = target_resource

            target_resource.add_method(
                cfg["http_method"],
                aws_apigateway.LambdaIntegration(function.function),
                authorizer=authorizer,
                authorization_type=aws_apigateway.AuthorizationType.COGNITO,
            )

        # create the create step function
        CreateWorkflow(self)
