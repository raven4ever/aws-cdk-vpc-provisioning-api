# ADR-010 Request validation

## Problem Statement

`POST /vpc` has to reject bad requests before it starts a workflow that costs money. Two kinds of checks are possible: the shape of the body, and the limits of the AWS account in the Region.

## Choices

**Pydantic**

- Pro: declarative models and good error messages, which scale well if the schema grows.
- Con: it is not in the Lambda Python runtime, which only ships the standard library and boto3.
- Con: `pydantic-core` is compiled, so the package has to be installed from Linux wheels at build time and bundled, or put in a layer. That adds a build step to a project that otherwise deploys with plain `cdk deploy`.
- Con: about 7.7 MB more in the shared Lambda asset, and extra import time on cold starts.

**Standard library**

- Pro: no dependency and no build step.
- Con: the standard library has no validation framework, so the checks are written by hand with `json`, `re` and plain comparisons.

## Decision

Standard library. `parse_request` in `lambda/api/create_vpc.py` checks the shape:

- `vpc_name` matches a name pattern.
- `vpc_prefix` is an integer from 16 to 28.
- `subnet_tiers` is a non-empty list of `public`, `private_egress` or `private_isolated`.
- The subnets fit into the VPC CIDR.
- There are at most 200 subnets, the AWS default subnets-per-VPC quota.
- `private_egress` is only allowed together with `public`, because the NAT gateway lives in a public subnet.

Account limits are not checked in the API. Reading them needs the Service Quotas API, and counting VPCs needs the EC2 client. Both add AWS calls before the response. The workflow hits the same limits anyway: `CreateVpc` fails with `VpcLimitExceeded`, cleanup runs, and since the workflow Lambdas report AWS error codes as their error name, the record ends `FAILED` with `status_reason` `VpcLimitExceeded`. The subnet cap is a constant instead of the applied quota. A quota can be raised but not lowered below the default, so the constant can only be too strict.

Known gaps: the VPC, Elastic IP and NAT gateway quotas are not checked up front, so those failures show up later as a `FAILED` run, and an account that raised its subnet quota above 200 has to change the constant to use it.
