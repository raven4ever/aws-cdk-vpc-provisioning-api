# VPC Provisioning API

A serverless, authenticated REST API that creates Amazon VPCs with multiple subnets, stores the results and exposes them for retrieval.

Built in Python on AWS Lambda, API Gateway, Step Functions, DynamoDB, Cognito and VPC IP Address Manager (IPAM), and deployed end to end with the AWS CDK.

## Scope

In scope:

- Create a VPC with any number of subnets in one of three tiers: public, private with egress (NAT), private isolated.
- Non-overlapping address space across all API-created VPCs, managed by IPAM.
- One AWS account, multiple Regions.
- Asynchronous creation with status tracking; retrieve one VPC or list all.
- Delete a VPC created by the API
- Authentication with Amazon Cognito; every authenticated user is authorized for every operation.
- Fully automated deploy and teardown, including removal of every VPC the API created.

Out of scope:

- Cross-account provisioning (no assumed roles).
- Modifying an existing VPC (resize, add subnets).
- IPv6, VPC peering, Transit Gateway, VPC endpoints, NACL or security group management.
- Fine-grained authorization (per-user or per-team permissions).

## Architecture

## Business Flow

## Architectural Decisions

| #   | Decision                    | Outcome                                                                | Details                                                |
| --- | --------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------ |
| 001 | Infrastructure as code tool | AWS CDK: no state backend to set up, target account unknown            | [ADR-001](docs/adr/001-infrastructure-as-code-tool.md) |
| 002 | Authentication mechanism    | Amazon Cognito: no custom auth logic, focus stays on the VPC API       | [ADR-002](docs/adr/002-authentication-mechanism.md)    |
| 003 | VPC creation flow           | Step Functions with wait steps for slow resources such as NAT gateways | [ADR-003](docs/adr/003-vpc-creation-flow.md)           |
| 004 | IP address allocator        | Hybrid: IPAM allocates the CIDR, DynamoDB caches it for retrieval      | [ADR-004](docs/adr/004-ip-address-allocator.md)        |
| 005 | Lambda code layout          | One source tree, one module per function, shared code alongside        | [ADR-005](docs/adr/005-lambda-code-layout.md)          |

## Technology Stack
