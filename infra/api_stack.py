from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool: cognito.IUserPool,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create API Gateway
        api = apigw.RestApi(
            self,
            "Api",
            rest_api_name="vpc-provisioning-api",
            deploy_options=apigw.StageOptions(stage_name="v1"),
        )

        # set the authorizer to the created user pool
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "Authorizer", cognito_user_pools=[user_pool]
        )

        # test endpoint
        mock_integration = apigw.MockIntegration(
            integration_responses=[
                apigw.IntegrationResponse(
                    status_code="200",
                    response_templates={
                        "application/json": '{"message": "Authorized request successful!"}'
                    },
                )
            ],
            request_templates={"application/json": '{"statusCode": 200}'},
        )

        test_resource = api.root.add_resource("test")
        test_resource.add_method(
            "GET",
            mock_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            method_responses=[apigw.MethodResponse(status_code="200")],
        )
