from aws_cdk import (
    aws_dynamodb,
    aws_lambda,
    aws_stepfunctions,
    aws_stepfunctions_tasks,
)
from constructs import Construct

# state helpers shared by the create and delete workflows


def cleanup_task(
    scope: Construct, function: aws_lambda.IFunction
) -> aws_stepfunctions_tasks.LambdaInvoke:
    return aws_stepfunctions_tasks.LambdaInvoke(
        scope,
        "cleanup-task",
        lambda_function=function,
        payload_response_only=True,
        result_path=aws_stepfunctions.JsonPath.DISCARD,
        state_name="cleanup",
    )


def set_status(
    scope: Construct,
    name: str,
    table: aws_dynamodb.ITable,
    status: str,
    reason: bool = False,
    expire: bool = False,
) -> aws_stepfunctions_tasks.DynamoUpdateItem:
    """Set the record status. With reason, the error name from $.error is stored too.
    With expire, $.ttl (epoch seconds, as a string) is stored so DynamoDB removes the record."""
    values = {
        ":s": aws_stepfunctions_tasks.DynamoAttributeValue.from_string(status),
        ":t": aws_stepfunctions_tasks.DynamoAttributeValue.from_string(
            aws_stepfunctions.JsonPath.string_at("$$.State.EnteredTime")
        ),
    }
    expression = "SET #s = :s, updated_at = :t"
    if reason:
        # error name only: full cause can hold stack traces, ARNs, account id.
        # Full cause stays in execution history.
        expression += ", status_reason = :r"
        values[":r"] = aws_stepfunctions_tasks.DynamoAttributeValue.from_string(
            aws_stepfunctions.JsonPath.string_at("$.error.Error")
        )
    names = {"#s": "status"}
    if expire:
        expression += ", #ttl = :ttl"
        names["#ttl"] = "ttl"  # ttl is a DynamoDB reserved word
        values[":ttl"] = aws_stepfunctions_tasks.DynamoAttributeValue.number_from_string(
            aws_stepfunctions.JsonPath.string_at("$.ttl")
        )
    task = aws_stepfunctions_tasks.DynamoUpdateItem(
        scope,
        name,
        table=table,
        key={
            "pk": aws_stepfunctions_tasks.DynamoAttributeValue.from_string(
                aws_stepfunctions.JsonPath.format(
                    "VPC#{}", aws_stepfunctions.JsonPath.string_at("$.id")
                )
            ),
            "sk": aws_stepfunctions_tasks.DynamoAttributeValue.from_string("META"),
        },
        update_expression=expression,
        expression_attribute_names=names,
        expression_attribute_values=values,
        result_path=aws_stepfunctions.JsonPath.DISCARD,  # keep state, drop DynamoDB response
    )
    # lost status write strands record (e.g. CREATING forever). Plain SET, retry is safe.
    task.add_retry(errors=["States.ALL"], max_attempts=4, backoff_rate=2)
    return task
