# ADR-007 Single Region

## Problem Statement

IPAM pools are bound to a single AWS region, and a VPC can only draw a CIDR from a pool in its own Region. Supporting several Regions therefore means more than passing a Region name through the API.

## Choices

**Multiple Regions**

- Pro: a client can create VPCs anywhere from one API.
- Con: the IPAM needs every Region as an operating Region, plus a regional child pool per Region under a parent pool, each provisioned with its own slice of the root CIDR.
- Con: the workflows and EC2 clients all need a Region parameter, and the create request has to be validated against the Regions that are enabled and have a pool.
- Con: the multi-Region features of IPAM need the advanced tier.

**Single Region**

- Pro: one IPAM pool covers everything, and the code has no Region plumbing.
- Con: a VPC in another Region needs another deployment of the stacks, which would be a separate IPAM with its own root CIDR.

## Decision

Single Region. VPCs are created in the Region the stacks are deployed to, and the request has no region field. The pool locale and the IPAM operating Region both use that Region. The IPAM stays on the advanced tier, since private IPv4 pools need it regardless of the number of Regions.
