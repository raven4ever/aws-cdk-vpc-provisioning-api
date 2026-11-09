# every resource the workflow creates carries this tag, so retries and cleanup can find it
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
