from aws_cdk import Duration, aws_dynamodb, aws_lambda, aws_stepfunctions, aws_stepfunctions_tasks
from constructs import Construct

from infra.constructs.workflow_steps import cleanup_task, set_status


class DeleteVpcWorkflow(Construct):
    """Step Functions workflow that tears a VPC down, frees its name and marks it DELETED."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        table: aws_dynamodb.ITable,
        cleanup: aws_lambda.IFunction,
    ) -> None:
        super().__init__(scope, id)

        # lock first, then mark DELETED (kept until ttl). Status write fails: retry still works,
        # deleting a missing lock is a no-op.
        delete_lock = aws_stepfunctions_tasks.DynamoDeleteItem(
            self,
            "DeleteNameLock",
            table=table,
            key={
                "pk": aws_stepfunctions_tasks.DynamoAttributeValue.from_string(
                    aws_stepfunctions.JsonPath.string_at("$.name_lock")
                ),
                "sk": aws_stepfunctions_tasks.DynamoAttributeValue.from_string("LOCK"),
            },
            result_path=aws_stepfunctions.JsonPath.DISCARD,
        )
        delete_record = set_status(self, "SetDeleted", table, "DELETED", expire=True)
        cleanup_step = cleanup_task(self, cleanup)

        # any error: keep record, mark FAILED with reason, DELETE can be retried
        failed = set_status(self, "SetFailed", table, "FAILED", reason=True)
        failed.next(aws_stepfunctions.Fail(self, "Failed"))
        for step in (cleanup_step, delete_lock, delete_record):
            step.add_catch(failed, result_path="$.error")

        self.state_machine = aws_stepfunctions.StateMachine(
            self,
            "StateMachine",
            state_machine_name="vpc-provisioning-api-delete-vpc",
            definition_body=aws_stepfunctions.DefinitionBody.from_chainable(
                cleanup_step.next(delete_lock).next(delete_record)
            ),
            timeout=Duration.minutes(30),
        )
