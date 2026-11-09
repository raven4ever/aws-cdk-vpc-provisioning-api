# ADR-008 VPC identity and status tracking

## Problem Statement

Creation is asynchronous, but the client needs something to poll right after `POST /vpc`. The AWS VPC id (`vpc-…`) only exists once the workflow has created the VPC, which can be minutes later. We need a handle that exists from the first response, and a way to report progress and failure.

## Choices

**AWS VPC id as the key, with an `/execution` endpoint**

- Pro: the key is the real AWS identifier.
- Con: until the VPC exists, the client's only handle is the execution id, so the API needs a second endpoint and a second concept.
- Con: a run that fails before the VPC exists leaves no record, and `GET /vpc` cannot show builds that are still in progress.
- Con: the execution ARN leaks the account id, the Region and the state machine name, and reading executions needs `states:DescribeExecution`.

**An id created by the API**

- Pro: the id exists from the first response. The record is written as `PENDING` before the workflow starts, so every run is visible, including failed ones.
- Pro: one handle for everything. The execution is named after the id, and `GET /vpc/{id}` shows progress.
- Con: there are two identifiers, ours and the AWS one.

## Decision

An id created by the API: a UUID that `POST /vpc` returns as `{"id": "<uuid>"}` with a 202. The AWS id is stored on the record later as `aws_vpc_id`, together with the CIDR and the subnets. The workflow updates `status` (`PENDING`, `CREATING`, `ACTIVE`, `FAILED`, `DELETING`, `DELETED`) and, on failure, `status_reason`. Clients poll `GET /vpc/{id}`, which returns the full record. `GET /vpc` returns only `id` and `status`. There is no `/execution` endpoint, and the execution ARN is not returned.
