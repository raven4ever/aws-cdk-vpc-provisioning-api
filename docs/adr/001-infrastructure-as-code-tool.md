# ADR-001 Infrastructure as code tool

## Problem Statement

The whole stack (API Gateway, Lambda, Step Functions, DynamoDB, Cognito, IPAM) has to be deployed and torn down automatically. We need to pick the tool that defines that infrastructure.

## Choices

**Terraform**

- Pro: widely known, big provider and module ecosystem.
- Con: needs a state backend (bucket and locking) that has to exist before the first deploy.
- Con: that backend has to live in the target account, and we don't know which account that will be.

**AWS CDK**

- Pro: infrastructure is modelled in a general-purpose language, so we can use Python for both the infra and the Lambdas.
- Pro: high-level constructs cut a lot of boilerplate.
- Pro: state is kept by CloudFormation, so there is no backend to set up.
- Con: AWS only, and the target account/Region needs a one-time `cdk bootstrap`.

## Outcome

AWS CDK. With no state backend to provision and the target account still unknown, it is the lower-friction option. The project is AWS-only anyway, so Terraform's multi-cloud reach doesn't buy us anything here.
