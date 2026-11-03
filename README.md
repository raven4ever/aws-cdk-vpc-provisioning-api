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

## Technology Stack
