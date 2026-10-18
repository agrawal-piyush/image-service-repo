"""LocalStack-aware boto3 client factory.

Clients are created lazily and cached per-process. Lambda reuses the same
process across invocations (warm starts), so caching the client avoids
re-creating connections on every request.

If AWS_ENDPOINT_URL is set (LocalStack), all clients point at it. Otherwise
boto3 resolves real AWS endpoints normally.
"""
import boto3

from src.common import config

_s3_client = None
_dynamodb_resource = None


def get_s3_client():
    """Return a cached S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=config.AWS_REGION,
            endpoint_url=config.AWS_ENDPOINT_URL,
        )
    return _s3_client


def get_dynamodb_resource():
    """Return a cached DynamoDB resource."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource(
            "dynamodb",
            region_name=config.AWS_REGION,
            endpoint_url=config.AWS_ENDPOINT_URL,
        )
    return _dynamodb_resource


def get_table():
    """Return the DynamoDB Table resource for image metadata."""
    return get_dynamodb_resource().Table(config.TABLE_NAME)


def reset_clients():
    """Clear cached clients. Used by tests so each test gets fresh mocks."""
    global _s3_client, _dynamodb_resource
    _s3_client = None
    _dynamodb_resource = None
