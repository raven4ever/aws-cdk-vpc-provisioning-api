from aws_cdk import Duration, aws_dynamodb, aws_lambda
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.constructs.workflow_steps import cleanup_task, set_status


class DeleteWorkflow(Construct):
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

        # the lock goes first and the record is only marked DELETED, kept until its ttl expires.
        # If the status update fails the retry still works, deleting a missing lock is a no-op
        delete_lock = tasks.DynamoDeleteItem(
            self,
            "DeleteNameLock",
            table=table,
            key={
                "pk": tasks.DynamoAttributeValue.from_string(sfn.JsonPath.string_at("$.name_lock")),
                "sk": tasks.DynamoAttributeValue.from_string("LOCK"),
            },
            result_path=sfn.JsonPath.DISCARD,
        )
        delete_record = set_status(self, "SetDeleted", table, "DELETED", expire=True)
        cleanup_step = cleanup_task(self, cleanup)

        # any error keeps the record, marks it FAILED with the reason so DELETE can be retried
        failed = set_status(self, "SetFailed", table, "FAILED", reason=True)
        failed.next(sfn.Fail(self, "Failed"))
        for step in (cleanup_step, delete_lock, delete_record):
            step.add_catch(failed, result_path="$.error")

        self.state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            state_machine_name="vpc-provisioning-api-delete-vpc",
            definition_body=sfn.DefinitionBody.from_chainable(
                cleanup_step.next(delete_lock).next(delete_record)
            ),
            timeout=Duration.minutes(30),
        )
