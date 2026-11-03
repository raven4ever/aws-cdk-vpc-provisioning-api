import aws_cdk as cdk

from infra.aws_cdk_vpc_provisioning_api_stack import AwsCdkVpcProvisioningApiStack


app = cdk.App()
AwsCdkVpcProvisioningApiStack(
    app,
    "AwsCdkVpcProvisioningApiStack",
)

app.synth()
