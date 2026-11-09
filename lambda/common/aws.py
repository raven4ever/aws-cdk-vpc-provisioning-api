import functools
import os
from functools import cache

import boto3
from botocore.exceptions import ClientError


# lazy + cached: import needs no region or creds, warm calls reuse client and connection
@cache
def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


@cache
def client(service: str):
    return boto3.client(service)


def aws_error_names(handler):
    """Re-raise a ClientError as an exception named after the AWS error code. Lambda reports the
    class name as the error, so the workflow stores e.g. VpcLimitExceeded, not ClientError."""

    @functools.wraps(handler)
    def wrapper(event, context):
        try:
            return handler(event, context)
        except ClientError as e:
            raise type(e.response["Error"]["Code"], (Exception,), {})(str(e)) from e

    return wrapper
