# ADR-008 VPC record lifecycle

## Problem Statement

Creating and deleting a VPC both run in the background and take minutes. Right after `POST /vpc` the client needs something to poll, but the AWS VPC id (`vpc-…`) only exists once the workflow has created the VPC. We need a handle that exists from the first response, a way to report progress and failure, rules for when a delete is allowed, and a decision on what stays in the table once a VPC is gone.

## Choices

**Handle: AWS VPC id as the key, with an `/execution` endpoint**

- Pro: the key is the real AWS identifier.
- Con: until the VPC exists, the client's only handle is the execution id, so the API needs a second endpoint and a second concept.
- Con: a run that fails before the VPC exists leaves no record, and `GET /vpc` cannot show builds that are still in progress.
- Con: the execution ARN leaks the account id, the Region and the state machine name, and reading executions needs `states:DescribeExecution`.

**Handle: an id created by the API**

- Pro: the id exists from the first response. The record is written as `PENDING` before the workflow starts, so every run is visible, including failed ones.
- Pro: one handle for everything. The execution is named after the id, and `GET /vpc/{id}` shows progress.
- Con: there are two identifiers, ours and the AWS one.

**After delete: remove the record**

- Pro: the table only holds live VPCs, and there is nothing to expire.
- Con: a client polling after `DELETE` can only see a 404, which also means "wrong id" or "never existed".
- Con: no trace of what was deleted and when.

**After delete: keep a `DELETED` record forever**

- Pro: a full history.
- Con: the table and the `GET /vpc` list only grow.

**After delete: keep a `DELETED` record with a TTL**

- Pro: the client sees `DELETING` and then `DELETED`, which separates a finished delete from a bad id and from a failed one.
- Pro: a short audit trail, and DynamoDB removes old records on its own.
- Con: deleted VPCs show up in `GET /vpc` until they expire. TTL deletion is lazy, so a record can outlive its timestamp by a day or two.

## Decision

An id created by the API, and a `DELETED` record that expires after 14 days.

- `POST /vpc` returns a UUID as `{"id": "<uuid>"}` with a 202. The AWS id is stored on the record later as `aws_vpc_id`, together with the CIDR and the subnets. There is no `/execution` endpoint, and the execution ARN is not returned.
- The status moves through `PENDING`, `CREATING` and `ACTIVE`, or ends in `FAILED`. A delete moves it to `DELETING` and then `DELETED`.
- On failure `status_reason` holds only the error name, such as `VpcLimitExceeded`. The full cause can contain stack traces, ARNs and the account id, so it stays in the Step Functions execution history.
- Clients poll `GET /vpc/{id}`, which returns the full record. `GET /vpc` returns only `id` and `status`, for every record including `DELETED` ones.
- `DELETE /vpc/{id}` is allowed only from `ACTIVE` or `FAILED`. One conditional write moves the record to `DELETING`, so two requests cannot start two workflows. Any other state gets a 409, and an unknown id gets a 404.
- The delete workflow tears the VPC down, deletes the name lock so the name can be reused at once, and marks the record `DELETED` with a `ttl` attribute set 14 days ahead. The old `aws_vpc_id`, CIDR and subnets stay on that record.
- If the delete workflow fails, the record goes to `FAILED` and `DELETE` can be sent again.
