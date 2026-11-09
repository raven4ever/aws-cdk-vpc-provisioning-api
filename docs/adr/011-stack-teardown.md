# ADR-011 Stack teardown

## Problem Statement

The scope promises a fully automated teardown, including every VPC the API created. `cdk destroy` only removes what CloudFormation created, and the VPCs built by the workflows are not CloudFormation resources. They would stay behind, with their NAT gateways and Elastic IPs still billing. The destroy would also fail on the IPAM pool, because a pool cannot be deleted while it still has allocations, and IPAM only releases a VPC's CIDR some time after the VPC is gone. In our account that took anything from a few minutes to about 45.

## Choices

**Delete every VPC through the API first, then destroy**

- Pro: no extra code.
- Con: easy to forget, and a forgotten VPC keeps billing with nothing left in the project to clean it up.
- Con: a destroy run too soon after the last delete still fails on the IPAM pool.

**Custom resource that deletes all VPCs on stack delete**

- Pro: one command removes the VPCs.
- Con: CloudFormation moves on right away, reaches the IPAM pool while the CIDRs are not released yet, and the Foundation stack ends in `DELETE_FAILED`.

**Custom resource that deletes all VPCs and waits for IPAM**

- Pro: one command takes everything down in the normal case.
- Con: CloudFormation gives a custom resource at most one hour, so the wait has to be capped.
- Con: CDK's provider framework adds three small Node.js Lambdas and a state machine, which go away with the stack.

## Decision

A custom resource that deletes all VPCs and waits for IPAM.

- The custom resource sits in `ApiStack` and depends on the shared cleanup Lambda, so CloudFormation deletes it first.
- On stack delete the cleanup Lambda removes everything carrying the tag key `vpc-provisioning-api:id`, whatever the value, using the same code as the workflows.
- A completion check then calls `ec2:GetIpamPoolAllocations` once a minute and lets the deletion go on only when the pool is empty. It gives up after 55 minutes, and `ApiStack` ends in `DELETE_FAILED`. Running `cdk destroy` again later finishes the job.
- On create and update the custom resource does nothing.

Known limits:

- The custom resource's construct path must stay the same. If it changes, CloudFormation replaces the resource, and deleting the old one removes every VPC the API created.
- A create workflow still running during the destroy can build resources after the cleanup has run.
