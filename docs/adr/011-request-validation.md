# ADR-011 Request validation

## Problem Statement

`POST /vpc` has to reject bad requests before it starts a workflow that costs money. Two kinds of checks are needed: the shape of the body, and the limits of the AWS account in the Region.

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
- `private_egress` is only allowed together with `public`, because the NAT gateway lives in a public subnet.

Account limits come from the Service Quotas API instead of constants: subnets per VPC and VPCs per Region, using the applied value and falling back to the AWS default. The current number of VPCs comes from `DescribeVpcs` and includes VPCs the API did not create.

Known gaps: VPCs still being built are not counted yet, and the Elastic IP and NAT gateway quotas are not checked, so those failures show up later as a `FAILED` run. Pydantic is worth revisiting if the request schema grows.
