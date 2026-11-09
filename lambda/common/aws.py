import os
from functools import cache

import boto3


# clients are created on first use so importing this module needs no region or credentials
@cache
def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


@cache
def sfn():
    return boto3.client("stepfunctions")


@cache
def client(service: str):
    return boto3.client(service)
