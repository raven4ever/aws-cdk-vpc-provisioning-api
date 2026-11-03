import aws_cdk as cdk

from infra.api_stack import ApiStack
from infra.foundation_stack import FoundationStack

# create CDK application
app = cdk.App()

# create the Foundation stack
foundation_stack = FoundationStack(
    app,
    "FoundationStack",
)

# create the API stack
ApiStack(app, "ApiStack", user_pool=foundation_stack.user_pool)


app.synth()
