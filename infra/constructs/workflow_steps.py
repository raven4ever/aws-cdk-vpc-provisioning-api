from aws_cdk import Duration, aws_dynamodb, aws_iam, aws_lambda
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.constructs.function_factory import ManagedFunction

# shortcut: resources "*", tighten with aws:ResourceTag/vpc-provisioning-api:id conditions
CLEANUP_ACTIONS = [
    "ec2:DescribeNatGateways",
    "ec2:DeleteNatGateway",
    "ec2:DescribeAddresses",
    "ec2:ReleaseAddress",
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DeleteSubnet",
    "ec2:DescribeRouteTables",
    "ec2:DeleteRouteTable",
    "ec2:DescribeInternetGateways",
    "ec2:DetachInternetGateway",
    "ec2:DeleteInternetGateway",
    "ec2:DeleteVpc",
]


class CleanupFunction(Construct):
    """The teardown Lambda, shared by the create workflow (on failure) and the delete workflow."""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)
        fn = ManagedFunction(
            self,
            "Function",
            handler="workflow.cleanup.handler",
            code_path="lambda",
            timeout=Duration.minutes(10),
        )
        fn.role.add_to_policy(aws_iam.PolicyStatement(actions=CLEANUP_ACTIONS, resources=["*"]))
        self.function = fn.function


def cleanup_task(scope: Construct, function: aws_lambda.IFunction) -> tasks.LambdaInvoke:
    return tasks.LambdaInvoke(
        scope,
        "cleanup-task",
        lambda_function=function,
        payload_response_only=True,
        result_path=sfn.JsonPath.DISCARD,
        state_name="cleanup",
    )


def set_status(
    scope: Construct,
    name: str,
    table: aws_dynamodb.ITable,
    status: str,
    reason: bool = False,
    expire: bool = False,
) -> tasks.DynamoUpdateItem:
    """Set the record status. With reason, the failure cause from $.error is stored too.
    With expire, $.ttl (epoch seconds, as a string) is stored so DynamoDB removes the record."""
    values = {
        ":s": tasks.DynamoAttributeValue.from_string(status),
        ":t": tasks.DynamoAttributeValue.from_string(
            sfn.JsonPath.string_at("$$.State.EnteredTime")
        ),
    }
    expression = "SET #s = :s, updated_at = :t"
    if reason:
        expression += ", status_reason = :r"
        values[":r"] = tasks.DynamoAttributeValue.from_string(
            sfn.JsonPath.string_at("$.error.Cause")
        )
    names = {"#s": "status"}
    if expire:
        expression += ", #ttl = :ttl"
        names["#ttl"] = "ttl"  # ttl is a DynamoDB reserved word
        values[":ttl"] = tasks.DynamoAttributeValue.number_from_string(
            sfn.JsonPath.string_at("$.ttl")
        )
    return tasks.DynamoUpdateItem(
        scope,
        name,
        table=table,
        key={
            "pk": tasks.DynamoAttributeValue.from_string(
                sfn.JsonPath.format("VPC#{}", sfn.JsonPath.string_at("$.id"))
            ),
            "sk": tasks.DynamoAttributeValue.from_string("META"),
        },
        update_expression=expression,
        expression_attribute_names=names,
        expression_attribute_values=values,
        result_path=sfn.JsonPath.DISCARD,  # keep the state, not the DynamoDB response
    )
