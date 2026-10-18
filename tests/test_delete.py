"""Tests for the delete handler (API 4)."""
import json

import pytest
from botocore.exceptions import ClientError

from src.common import config
from src.common.aws_clients import get_s3_client, get_table
from src.handlers import upload, delete_image
from tests.conftest import make_upload_event


def _upload_one(sample_image_b64):
    resp = upload.handler(make_upload_event(sample_image_b64))
    return json.loads(resp["body"])["image"]


def test_delete_success_removes_both_stores(aws, sample_image_b64):
    image = _upload_one(sample_image_b64)
    image_id = image["image_id"]
    s3_key = image["s3_key"]

    event = {"pathParameters": {"image_id": image_id}}
    resp = delete_image.handler(event)

    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["image_id"] == image_id

    # DynamoDB item gone.
    assert get_table().get_item(Key={"image_id": image_id}).get("Item") is None

    # S3 object gone.
    with pytest.raises(ClientError):
        get_s3_client().get_object(Bucket=config.BUCKET_NAME, Key=s3_key)


def test_delete_not_found(aws):
    event = {"pathParameters": {"image_id": "missing"}}
    resp = delete_image.handler(event)
    assert resp["statusCode"] == 404


def test_delete_missing_path_param(aws):
    resp = delete_image.handler({})
    assert resp["statusCode"] == 400


def test_delete_twice_second_is_404(aws, sample_image_b64):
    image = _upload_one(sample_image_b64)
    event = {"pathParameters": {"image_id": image["image_id"]}}

    first = delete_image.handler(event)
    assert first["statusCode"] == 200

    second = delete_image.handler(event)
    assert second["statusCode"] == 404
