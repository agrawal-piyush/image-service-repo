"""Tests for the view/download handler (API 3)."""
import base64
import json

from src.handlers import upload, get_image
from tests.conftest import make_upload_event


def _upload_one(sample_image_b64):
    resp = upload.handler(make_upload_event(sample_image_b64))
    return json.loads(resp["body"])["image"]["image_id"]


def test_get_returns_metadata_and_bytes(aws, sample_image_b64):
    image_id = _upload_one(sample_image_b64)
    event = {"pathParameters": {"image_id": image_id}}

    resp = get_image.handler(event)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["image"]["image_id"] == image_id
    assert body["content_type"] == "image/png"
    # Returned bytes must decode and be non-empty.
    raw = base64.b64decode(body["image_base64"])
    assert len(raw) > 0


def test_get_presigned_url_mode(aws, sample_image_b64):
    image_id = _upload_one(sample_image_b64)
    event = {
        "pathParameters": {"image_id": image_id},
        "queryStringParameters": {"download": "url"},
    }
    resp = get_image.handler(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "download_url" in body
    assert body["download_url"].startswith("http")


def test_get_not_found(aws):
    event = {"pathParameters": {"image_id": "does-not-exist"}}
    resp = get_image.handler(event)
    assert resp["statusCode"] == 404


def test_get_missing_path_param(aws):
    resp = get_image.handler({})
    assert resp["statusCode"] == 400
