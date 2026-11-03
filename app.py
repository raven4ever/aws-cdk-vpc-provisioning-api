import aws_cdk as cdk

from infra.foundation_stack import FoundationStack

app = cdk.App()
FoundationStack(
    app,
    "FoundationStack",
)

app.synth()
