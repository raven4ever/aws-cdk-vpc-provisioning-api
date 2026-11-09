# ADR-005 Lambda code layout

## Problem Statement

Each API operation maps to its own Lambda function, and the creation workflow will add more functions for its steps. We need to decide how the Python source is laid out and packaged, especially where code shared between functions lives.

## Choices

**One folder per function**

- Pro: each function gets its own small bundle, and could have its own dependencies.
- Con: shared code (DynamoDB access, response helpers, the VPC record shape) has no natural home. It gets duplicated, or we add a Lambda layer.
- Con: every entry point is called `main.py`, which makes navigation and stack traces harder to read.

**One source tree, one module per function**

- Pro: shared code sits next to the handlers and is imported normally.
- Pro: modules have distinct names (`create_vpc.py`, `get_vpc.py`), and the handler is just a dotted path such as `api.create_vpc.handler`.
- Con: every function ships the whole tree. At this size that is a few KB, and only the imported modules are loaded, so cold starts are unaffected.
- Con: no per-function dependencies. We don't need any.

## Outcome

One source tree under `lambda/`, deployed as a single asset, with one module per function:

- `lambda/api/` holds the API handlers.
- `lambda/workflow/` will hold the Step Functions steps.
- `lambda/common/` will hold shared code.

The last two are created when there is code to put in them. Least privilege is unchanged, since each function still gets its own IAM role.
