from aws_cdk import Stack, aws_apigateway, aws_cognito
from constructs import Construct

from infra.constructs.function_factory import ManagedFunction


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

        # create the health function
        health_function = ManagedFunction(
            self,
            "vpc-provisioning-api-health-function",
            handler="main.lambda_handler",
            code_path="lambda/health",
        )

        # attach Lambda integration
        health_resource = api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            aws_apigateway.LambdaIntegration(health_function.function),
            authorizer=authorizer,
            authorization_type=aws_apigateway.AuthorizationType.COGNITO,
        )
