# ADR-003 VPC creation flow

## Problem Statement

Creating a VPC is many calls: the VPC itself, subnets, route tables, gateways and so on. Some resources, NAT gateways especially, take minutes to become available, and later steps depend on them. We need to decide how to orchestrate this, given that creation is asynchronous and its status is tracked.

## Choices

**Single Lambda**

- Pro: simplest to build and deploy, one function.
- Con: it has to block while waiting on slow resources, and it is bound by the 15 minute Lambda timeout.
- Con: a failure halfway leaves no clear record of which step it reached.

**Multiple Lambdas linked via SQS**

- Pro: no single long-running function, each step is small.
- Con: the waiting and polling for slow resources has to be written by hand.
- Con: the flow is spread across queues and functions, so it is hard to follow and debug.

**Step Functions workflow**

- Pro: wait and retry are built in, so polling for a NAT gateway needs no custom code and costs no compute while waiting.
- Pro: each step is a small Lambda, and the execution history shows exactly where a run is or failed.
- Con: the flow lives in a state machine definition, which is one more thing to learn and keep readable.

## Outcome

Step Functions. Wait steps handle resources like NAT gateways that take a long time to provision, and the flow stays visible in one place.
