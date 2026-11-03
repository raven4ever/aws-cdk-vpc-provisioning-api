import aws_cdk as core
import aws_cdk.assertions as assertions

from aws_cdk_vpc_provisioning_api.aws_cdk_vpc_provisioning_api_stack import AwsCdkVpcProvisioningApiStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aws_cdk_vpc_provisioning_api/aws_cdk_vpc_provisioning_api_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AwsCdkVpcProvisioningApiStack(app, "aws-cdk-vpc-provisioning-api")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
