# ADR-009 Delete semantics

## Problem Statement

Deleting a VPC takes minutes because of the NAT gateway, so it runs in its own workflow. We need to decide when a delete is allowed, and what is left in the table once the workflow has finished.

## Choices

**Remove the record**

- Pro: the table only holds live VPCs, and there is nothing to expire.
- Con: a client polling after `DELETE` can only see a 404, which also means "wrong id" or "never existed".
- Con: no trace of what was deleted and when.

**Keep a `DELETED` record forever**

- Pro: a full history.
- Con: the table and the `GET /vpc` list only grow.

**Keep a `DELETED` record with a TTL**

- Pro: the client sees `DELETING` and then `DELETED`, which separates a finished delete from a bad id and from a failed one.
- Pro: a short audit trail, and DynamoDB removes old records on its own.
- Con: deleted VPCs show up in `GET /vpc` until they expire. TTL deletion is lazy, so a record can outlive its timestamp by a day or two.

## Decision

A `DELETED` record with a 14 day TTL.

- `DELETE /vpc/{id}` is allowed only from `ACTIVE` or `FAILED`. One conditional write moves the record to `DELETING`, so two requests cannot start two workflows. Any other state gets a 409, and an unknown id gets a 404.
- The workflow tears the VPC down, deletes the name lock so the name can be reused at once, and then marks the record `DELETED` with a `ttl` attribute set 14 days ahead.
- `GET /vpc` lists every record, including `DELETED` ones. The old `aws_vpc_id`, CIDR and subnets stay on the tombstone.
- If the workflow fails, the record goes to `FAILED` with the reason, and `DELETE` can be retried.
- IPAM releases the VPC's CIDR some time after the VPC is gone, not at once. Until then the allocation stays in the pool, and the pool cannot be destroyed.
