# Payload examples for `POST /vpc`

Request bodies for the create VPC endpoint. Files starting with `valid-` pass request validation, files starting with `invalid-` are rejected with a 400.

Send one with curl (see the main README for how to get `$TOKEN` and `$API_URL`):

```bash
curl -s -X POST "${API_URL}vpc" \
  -H "Authorization: ${TOKEN}" -H "Content-Type: application/json" \
  -d @docs/payload_examples/valid-three-tiers.json
```

A valid request returns 202 with `{"id": "<uuid>"}`. Two things can still reject it after validation:

- The name is already used by another VPC: 409. Change `vpc_name` before sending a file twice.
- The account is out of quota in the Region (VPCs per Region, subnets per VPC): 400.

## Valid

| File                                   | What it covers                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------- |
| `valid-minimal-public.json`            | The smallest useful request: one public subnet. No NAT gateway is created.            |
| `valid-three-tiers.json`               | One subnet of each tier. Creates an IGW, a NAT gateway and three route tables.        |
| `valid-public-and-egress.json`         | Public plus `private_egress`: the NAT gateway sits in the public subnet.              |
| `valid-isolated-only.json`             | Only `private_isolated` subnets. No IGW, no NAT, a local-only route table.            |
| `valid-multi-az-spread.json`           | Six subnets, two per tier. They are spread round-robin across the Availability Zones. |
| `valid-large-vpc.json`                 | A `/16` VPC with eight subnets, each split to a `/19`.                                |
| `valid-smallest-vpc.json`              | A `/28` VPC, the smallest AWS allows, with its one `/28` subnet.                      |
| `valid-name-with-spaces-and-dots.json` | A name using the allowed characters: letters, digits, space, `_`, `.`, `-`.           |

## Invalid

| File                                 | Rejected because                                                           |
| ------------------------------------ | -------------------------------------------------------------------------- |
| `invalid-missing-name.json`          | `vpc_name` is required.                                                    |
| `invalid-name-characters.json`       | The name has characters outside the allowed set.                           |
| `invalid-prefix-too-small.json`      | `vpc_prefix` is 15, the minimum is 16.                                     |
| `invalid-prefix-too-large.json`      | `vpc_prefix` is 29, the maximum is 28.                                     |
| `invalid-prefix-as-string.json`      | `vpc_prefix` must be an integer, not `"24"`.                               |
| `invalid-empty-tiers.json`           | `subnet_tiers` must have at least one entry.                               |
| `invalid-unknown-tier.json`          | `dmz` is not a tier. Use `public`, `private_egress` or `private_isolated`. |
| `invalid-egress-without-public.json` | `private_egress` needs a `public` subnet to host the NAT gateway.          |
| `invalid-too-many-subnets.json`      | A `/28` VPC cannot hold two subnets.                                       |

## Subnet sizes

There is no per-subnet size in the request. The VPC CIDR is split equally, so the subnet prefix is the VPC prefix plus enough bits to cover the number of subnets. For example, six subnets in a `/20` VPC become six `/23` networks, with two left unused.
