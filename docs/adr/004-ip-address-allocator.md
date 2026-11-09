# ADR-004 IP address allocator

## Problem Statement

Every VPC the API creates needs its own CIDR, and none of them may overlap. We need something that hands out those ranges and keeps track of what is taken. The API also has to return the CIDRs when a VPC is retrieved.

## Choices

**DynamoDB only**

- Pro: one store for everything, no extra AWS service.
- Con: the creation flow has to read the free ranges, pick one, and write it back itself.
- Con: overlap checks are our own Python code, and concurrent creations need conditional writes to avoid handing out the same range twice.

**AWS IPAM only**

- Pro: allocation, overlap prevention and tracking are managed for us.
- Con: IPAM is not a good store for the API's own data. Serving VPC lookups from it means an IPAM call on every read, and it holds no status or subnet metadata.

**Hybrid: IPAM allocates, DynamoDB caches**

- Pro: IPAM does the hard part (non-overlapping allocation), so there is no custom CIDR logic.
- Pro: reads are served from DynamoDB alongside the rest of the VPC record.
- Con: the CIDR lives in two places, so the DynamoDB copy has to be written whenever an allocation is made.

## Outcome

Hybrid. IPAM generates the CIDR allocation, and the result is stored in DynamoDB as a cache, so VPC retrieval through the API doesn't need to go back to IPAM.
