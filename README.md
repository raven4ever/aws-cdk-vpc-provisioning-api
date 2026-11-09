# VPC Provisioning API

A serverless, authenticated REST API that creates Amazon VPCs with multiple subnets, stores the results and exposes them for retrieval.

Built in Python on AWS Lambda, API Gateway, Step Functions, DynamoDB, Cognito and VPC IP Address Manager (IPAM), and deployed end to end with the AWS CDK.

## Scope

In scope:

- Create a VPC with any number of subnets in one of three tiers: public, private with egress (NAT), private isolated.
- Non-overlapping address space across all API-created VPCs, managed by IPAM.
- One AWS account and one Region: VPCs are created in the Region the stack is deployed to.
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

## How to run

### Prerequisites

- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) (`npm install -g aws-cdk`, needs Node.js).
- [uv](https://docs.astral.sh/uv/) to manage Python and the dependencies.
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), used below to read the stack outputs.
- [jq](https://jqlang.org/) to pull the token out of the Cognito login response.
- An AWS account to deploy to, with credentials configured for the CLI (`aws configure` or SSO).

### Deploy

```bash
uv sync

# once per account (the app deploys to us-east-1)
cdk bootstrap

cdk deploy --all
```

The IPAM pool that hands out VPC CIDRs defaults to `10.0.0.0/8`. To use another range, set the `IPAM_ROOT_CIDR` environment variable on deploy: `IPAM_ROOT_CIDR=172.16.0.0/12 cdk deploy --all`. IPAM runs in the advanced tier, which is billed per active IP address.

The deploy prints two outputs that the next section needs: `ApiStack.ApiUrl` and `FoundationStack.UserPoolClientId`. To remove everything, run `cdk destroy --all`.

### Sign in and call the API

The Foundation stack creates a test user, `testuser@example.com` with password `MySecurePassword123!`. It is for testing only: remove it before using the stack for anything real.

Set the Region and read the stack outputs:

```bash
export AWS_REGION=us-east-1

CLIENT_ID=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name FoundationStack \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text)
API_URL=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name ApiStack \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
```

Log in against the Cognito API with curl. The API expects the ID token, which is valid for one hour:

```bash
COGNITO_USER='testuser@example.com'
COGNITO_PASSWORD='MySecurePassword123!'

TOKEN=$(jq -n --arg client "$CLIENT_ID" --arg user "$COGNITO_USER" --arg pass "$COGNITO_PASSWORD" \
  '{AuthFlow: "USER_PASSWORD_AUTH", ClientId: $client, AuthParameters: {USERNAME: $user, PASSWORD: $pass}}' \
  | curl -s -X POST "https://cognito-idp.${AWS_REGION}.amazonaws.com/" \
    -H "Content-Type: application/x-amz-json-1.1" \
    -H "X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth" \
    -d @- \
  | jq -r .AuthenticationResult.IdToken)
```

Send the token in the `Authorization` header. `API_URL` already ends with a slash.

```bash
# health check
curl -s "${API_URL}health" -H "Authorization: ${TOKEN}"

# create a VPC (validates the request against the AWS quotas of this Region)
curl -s -X POST "${API_URL}vpc" \
  -H "Authorization: ${TOKEN}" -H "Content-Type: application/json" \
  -d '{
    "vpc_name": "dev",
    "vpc_prefix": 20,
    "subnet_tiers": ["public", "private_egress", "private_isolated"]
  }'

# list all VPCs
curl -s "${API_URL}vpc" -H "Authorization: ${TOKEN}"

# get one VPC and its status (PENDING, CREATING, ACTIVE, FAILED, DELETING)
curl -s "${API_URL}vpc/<id>" -H "Authorization: ${TOKEN}"

# delete a VPC (only when ACTIVE or FAILED)
curl -s -X DELETE "${API_URL}vpc/<id>" -H "Authorization: ${TOKEN}"
```

`subnet_tiers` takes `public`, `private_egress` (NAT) or `private_isolated`, one entry per subnet. `vpc_prefix` goes from 16 to 28.
