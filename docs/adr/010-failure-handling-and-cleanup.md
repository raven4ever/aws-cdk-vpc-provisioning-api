# ADR-010 Failure handling and cleanup

## Problem Statement

The create workflow builds a VPC, subnets, an internet gateway, an Elastic IP, a NAT gateway and route tables. It can fail at any of those steps. A half-built VPC holds IPAM address space, and a leftover NAT gateway or Elastic IP keeps costing money. We need a defined behaviour for failures, and one way to tear things down that the delete workflow can share.

## Choices

**Leave the partial resources**

- Pro: they are there to inspect.
- Con: they bill and hold address space until someone removes them by hand.

**Mark the run failed and clean up by hand**

- Pro: no cleanup code.
- Con: same leak, plus a manual procedure per failure.

**Roll back automatically, finding resources by tag**

- Pro: nothing is left behind, and no list of created ids has to be passed along. Ids from steps that never returned are still found.
- Pro: the same teardown serves the delete workflow, and it is safe to run again.
- Con: the reason for a failure has to be kept on the record, since the resources are gone afterwards.

## Decision

Automatic rollback by tag. Every resource the workflow creates carries the tag `vpc-provisioning-api:id` with the request id. One cleanup Lambda deletes whatever has that tag, in dependency order: NAT gateway first, waiting for it to be gone, then the Elastic IP, the subnets, the route tables, the internet gateway and the VPC. It does nothing when nothing is left. The create workflow runs it from every failure path and then sets the record to `FAILED` with the cause in `status_reason`. The delete workflow uses the same function, and the function is created once and shared by both state machines.

Known limits:

- A run that hits the 30 minute execution timeout ends without cleanup.
- A VPC that someone added their own resources to, such as instances or network interfaces, cannot be deleted. The record goes to `FAILED` with that reason and nothing is force-deleted.
