from common.aws import client


def quota(service: str, code: str) -> int:
    """Applied Service Quotas value, falling back to the AWS default when none is applied."""
    sq = client("service-quotas")
    try:
        found = sq.get_service_quota(ServiceCode=service, QuotaCode=code)
    except sq.exceptions.NoSuchResourceException:
        found = sq.get_aws_default_service_quota(ServiceCode=service, QuotaCode=code)
    return int(found["Quota"]["Value"])
