import os

import aws_cdk as cdk

from infra.api_stack import ApiStack
from infra.foundation_stack import FoundationStack

# create CDK application
app = cdk.App()

# create the Foundation stack
foundation_stack = FoundationStack(
    app,
    "FoundationStack",
    ipam_cidr=os.environ.get("IPAM_ROOT_CIDR", "10.0.0.0/8"),
)

# create the API stack
ApiStack(
    app,
    "ApiStack",
    user_pool=foundation_stack.user_pool,
    table=foundation_stack.table,
)


app.synth()
