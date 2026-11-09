# ADR-006 Duplicate request handling

## Problem Statement

Every `POST /vpc` creates a new record and starts a new workflow. Sending the same request twice builds two VPCs, each with its own IPAM CIDR, and with `private_egress` subnets a second NAT gateway and Elastic IP as well. A client that retries after a timeout can do this by accident. The quota check doesn't catch it, because it only counts VPCs that already exist, not the ones still being built.

## Choices

**Do nothing**

- Pro: no extra code.
- Con: retries and double clicks cost real money and burn quota, and the extra runs fail late in the workflow.

**Idempotency key**

- Pro: the standard pattern for safe retries. A repeated key returns the original `id`.
- Con: needs a header, key storage and expiry, and the client has to generate and reuse keys correctly.

**Unique VPC name**

- Pro: one conditional write rejects a duplicate with 409, and the name is the identifier people already use.
- Pro: no new concepts for the client.
- Con: it blocks a deliberate second VPC with the same name, and a retry gets a 409 instead of the original `id`.
- Con: the name stays reserved until the VPC is deleted, so the delete workflow has to remove the lock.

## Decision

Unique VPC name. Names are compared case-insensitively. A `NAME#<name>` lock item is written with `attribute_not_exists` before the VPC record, and a second request with the same name gets a 409. Failed creations keep their name until they are deleted.
