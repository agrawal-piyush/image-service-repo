"""Tests for the upload handler (API 1)."""
import json

from src.common import config
from src.common.aws_clients import get_s3_client, get_table
from src.handlers import upload
from tests.conftest import make_upload_event


def test_upload_success_stores_s3_and_dynamodb(aws, sample_image_b64):
    event = make_upload_event(sample_image_b64, user_id="piyush", tags=["pet", "cute"])

    resp = upload.handler(event)

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    image = body["image"]
    assert image["user_id"] == "piyush"
    assert image["tags"] == ["pet", "cute"]
    assert image["size_bytes"] > 0
    image_id = image["image_id"]

    # Metadata is in DynamoDB.
    item = get_table().get_item(Key={"image_id": image_id}).get("Item")
    assert item is not None
    assert item["filename"] == "pixel.png"

    # Object is in S3.
    obj = get_s3_client().get_object(Bucket=config.BUCKET_NAME, Key=item["s3_key"])
    assert obj["ContentLength"] > 0


def test_upload_missing_body(aws):
    resp = upload.handler({})
    assert resp["statusCode"] == 400
    assert "body" in json.loads(resp["body"])["message"].lower()


def test_upload_invalid_json_body(aws):
    resp = upload.handler({"body": "not-json{"})
    assert resp["statusCode"] == 400


def test_upload_missing_required_fields(aws, sample_image_b64):
    # Missing user_id and filename.
    event = {"body": json.dumps({"image_base64": sample_image_b64})}
    resp = upload.handler(event)
    assert resp["statusCode"] == 400
    details = json.loads(resp["body"])["details"]
    assert "user_id" in details
    assert "filename" in details


def test_upload_invalid_base64(aws):
    event = make_upload_event("@@@not-base64@@@")
    resp = upload.handler(event)
    assert resp["statusCode"] == 400
    assert "base64" in json.loads(resp["body"])["message"].lower()


def test_upload_tags_must_be_list(aws, sample_image_b64):
    event = make_upload_event(sample_image_b64)
    body = json.loads(event["body"])
    body["tags"] = "not-a-list"
    event["body"] = json.dumps(body)
    resp = upload.handler(event)
    assert resp["statusCode"] == 400


def test_upload_rejects_oversized_image(aws, sample_image_b64, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 1)  # 1 byte limit
    event = make_upload_event(sample_image_b64)
    resp = upload.handler(event)
    assert resp["statusCode"] == 400
    assert "max size" in json.loads(resp["body"])["message"].lower()


def test_upload_accepts_dict_body(aws, sample_image_b64):
    # API Gateway may pass an already-parsed dict in some setups.
    event = {"body": {
        "image_base64": sample_image_b64,
        "filename": "a.png",
        "user_id": "u1",
    }}
    resp = upload.handler(event)
    assert resp["statusCode"] == 201
