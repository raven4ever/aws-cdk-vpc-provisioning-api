# ADR-007 Single Region

## Problem Statement

The original scope said one account and multiple Regions, with the Region chosen per request. IPAM pools have a locale, and a VPC can only draw a CIDR from a pool in its own Region. Supporting several Regions therefore means more than passing a Region name through the API.

## Choices

**Multiple Regions**

- Pro: a client can create VPCs anywhere from one API.
- Con: the IPAM needs every Region as an operating Region, plus a regional child pool per Region under a parent pool, each provisioned with its own slice of the root CIDR.
- Con: the workflows, quota checks and EC2 clients all need a Region parameter, and the create request has to be validated against the Regions that are enabled and have a pool.
- Con: the multi-Region features of IPAM need the advanced tier.

**Single Region**

- Pro: one IPAM pool covers everything, and the code has no Region plumbing.
- Pro: quotas and the VPC count are checked in the Region the function runs in.
- Con: a VPC in another Region needs another deployment of the stacks, which would be a separate IPAM with its own root CIDR.

## Decision

Single Region. VPCs are created in the Region the stacks are deployed to, and the request has no region field. The pool locale, the IPAM operating Region and the quota checks all use that Region. The scope in the README is updated to match. The IPAM stays on the advanced tier, since private IPv4 pools need it regardless of the number of Regions.
