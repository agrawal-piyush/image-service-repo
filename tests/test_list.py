"""Tests for the list handler (API 2), including the filter scenarios."""
import json

from src.handlers import upload, list_images
from tests.conftest import make_upload_event


def _seed(sample_image_b64):
    """Upload a few images with varied metadata for filtering tests."""
    uploads = [
        dict(user_id="piyush", tags=["pet", "cute"], content_type="image/png",
             filename="a.png"),
        dict(user_id="piyush", tags=["food"], content_type="image/jpeg",
             filename="b.jpg"),
        dict(user_id="alice", tags=["pet"], content_type="image/png",
             filename="c.png"),
    ]
    ids = {}
    for u in uploads:
        event = make_upload_event(
            sample_image_b64,
            filename=u["filename"],
            user_id=u["user_id"],
            tags=u["tags"],
            content_type=u["content_type"],
        )
        resp = upload.handler(event)
        assert resp["statusCode"] == 201
        ids[u["filename"]] = json.loads(resp["body"])["image"]["image_id"]
    return ids


def test_list_all_no_filter(aws, sample_image_b64):
    _seed(sample_image_b64)
    resp = list_images.handler({})
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["count"] == 3
    assert len(body["images"]) == 3


def test_list_filter_by_user_id(aws, sample_image_b64):
    _seed(sample_image_b64)
    event = {"queryStringParameters": {"user_id": "piyush"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert all(img["user_id"] == "piyush" for img in body["images"])


def test_list_filter_by_tag(aws, sample_image_b64):
    _seed(sample_image_b64)
    event = {"queryStringParameters": {"tag": "pet"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert all("pet" in img["tags"] for img in body["images"])


def test_list_filter_combined_user_and_tag(aws, sample_image_b64):
    _seed(sample_image_b64)
    event = {"queryStringParameters": {"user_id": "piyush", "tag": "pet"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 1
    assert body["images"][0]["filename"] == "a.png"


def test_list_filter_by_content_type(aws, sample_image_b64):
    _seed(sample_image_b64)
    event = {"queryStringParameters": {"content_type": "image/jpeg"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 1
    assert body["images"][0]["content_type"] == "image/jpeg"


def test_list_filter_no_match_returns_empty(aws, sample_image_b64):
    _seed(sample_image_b64)
    event = {"queryStringParameters": {"user_id": "nobody"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 0
    assert body["images"] == []


def test_list_date_range_filter(aws, sample_image_b64):
    _seed(sample_image_b64)
    # A wide-open upper bound in the far future should match everything.
    event = {"queryStringParameters": {"uploaded_before": "2999-01-01T00:00:00+00:00"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 3

    # A far-future lower bound should match nothing.
    event = {"queryStringParameters": {"uploaded_after": "2999-01-01T00:00:00+00:00"}}
    resp = list_images.handler(event)
    body = json.loads(resp["body"])
    assert body["count"] == 0


def test_list_empty_table(aws):
    resp = list_images.handler({})
    body = json.loads(resp["body"])
    assert body["count"] == 0
