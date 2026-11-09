import os

import aws_cdk

from infra.api_stack import ApiStack
from infra.foundation_stack import FoundationStack

app = aws_cdk.App()

foundation_stack = FoundationStack(
    app,
    "FoundationStack",
    ipam_cidr=os.environ.get("IPAM_ROOT_CIDR", "10.0.0.0/8"),
    # defaults are public in repo. Override for shared or long-lived deploy.
    test_user_name=os.environ.get("TEST_USER_NAME", "testuser"),
    test_user_email=os.environ.get("TEST_USER_EMAIL", "testuser@example.com"),
    test_user_password=os.environ.get("TEST_USER_PASSWORD", "MySecurePassword123!"),
)

ApiStack(
    app,
    "ApiStack",
    user_pool=foundation_stack.user_pool,
    table=foundation_stack.table,
    ipam_pool_id=foundation_stack.ipam_pool.attr_ipam_pool_id,
)


app.synth()
