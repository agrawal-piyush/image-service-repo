"""Shared pytest fixtures.

Uses `moto` to mock S3 + DynamoDB entirely in-memory, so the full test suite
runs without Docker or LocalStack. Each test gets a fresh bucket + table.
"""
import base64
import os

import boto3
import pytest
from moto import mock_aws

# Ensure config picks up test values BEFORE any src module imports boto3.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("BUCKET_NAME", "images-bucket")
os.environ.setdefault("TABLE_NAME", "images")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
# Make sure we do NOT point at LocalStack during unit tests.
os.environ.pop("AWS_ENDPOINT_URL", None)

from src.common import aws_clients, config  # noqa: E402


@pytest.fixture
def aws(monkeypatch):
    """Spin up mocked S3 + DynamoDB and yield helper handles."""
    with mock_aws():
        # Reset cached boto3 clients so they bind to the moto mock.
        aws_clients.reset_clients()

        s3 = boto3.client("s3", region_name=config.AWS_REGION)
        s3.create_bucket(Bucket=config.BUCKET_NAME)

        dynamodb = boto3.client("dynamodb", region_name=config.AWS_REGION)
        dynamodb.create_table(
            TableName=config.TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "image_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "image_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.get_waiter("table_exists").wait(TableName=config.TABLE_NAME)

        yield {"s3": s3, "dynamodb": dynamodb}

        aws_clients.reset_clients()


@pytest.fixture
def sample_image_b64():
    """A tiny valid PNG (1x1 transparent pixel) base64-encoded."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(png_bytes).decode("utf-8")


def make_upload_event(image_b64, filename="pixel.png", user_id="piyush",
                      tags=None, content_type="image/png", extra=None):
    """Build an API Gateway proxy event for the upload handler."""
    import json
    body = {
        "image_base64": image_b64,
        "filename": filename,
        "user_id": user_id,
        "content_type": content_type,
    }
    if tags is not None:
        body["tags"] = tags
    if extra:
        body.update(extra)
    return {"body": json.dumps(body)}
