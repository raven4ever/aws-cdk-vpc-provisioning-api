# every workflow resource carries this tag: retries and cleanup find it
TAG_KEY = "vpc-provisioning-api:id"


def tags(resource_type: str, request_id: str, name: str) -> list[dict]:
    return [
        {
            "ResourceType": resource_type,
            "Tags": [{"Key": TAG_KEY, "Value": request_id}, {"Key": "Name", "Value": name}],
        }
    ]


def by_request(request_id: str) -> list[dict]:
    return [{"Name": f"tag:{TAG_KEY}", "Values": [request_id]}]


# all resources of all API-created VPCs, any request id
ALL_REQUESTS = [{"Name": "tag-key", "Values": [TAG_KEY]}]
