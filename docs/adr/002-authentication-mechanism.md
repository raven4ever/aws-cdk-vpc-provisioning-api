# ADR-002 Authentication mechanism

## Problem Statement

The API has to be authenticated. Any signed-in user can call every operation, so we only need to know who is calling, not what they are allowed to do. We need to decide where that check lives.

## Choices

**Amazon Cognito**

- Pro: fully managed. Sign-in, token issuing, expiry and refresh are all handled for us.
- Pro: API Gateway validates the tokens natively, so there is no custom auth code to write or maintain.
- Con: ties authentication to an AWS service.

**Lambda authorizer on API Gateway**

- Pro: easy to set up, and we control the validation logic.
- Con: we would have to build and operate token storage and expiry handling ourselves.
- Con: it is custom security code that has nothing to do with VPC provisioning.

## Decision

Amazon Cognito. It needs no custom logic, which keeps the project focused on the VPC creation API.
