"""API 1: Upload an image with metadata.

POST /images
Body (JSON):
{
  "image_base64": "<base64-encoded image bytes>",   # required
  "filename": "cat.jpg",                              # required
  "content_type": "image/jpeg",                       # optional, default image/jpeg
  "user_id": "piyush",                                # required
  "tags": ["pet", "cute"]                             # optional
}

Returns 201 with the created metadata (including generated image_id).
"""
import base64
import binascii
import json
import uuid

from src.common import config, responses
from src.common import repository


def handler(event, context=None):
    # --- parse body ---
    raw_body = event.get("body")
    if not raw_body:
        return responses.bad_request("Request body is required")
    try:
        body = raw_body if isinstance(raw_body, dict) else json.loads(raw_body)
    except (ValueError, TypeError):
        return responses.bad_request("Request body must be valid JSON")

    # --- validate required fields ---
    image_b64 = body.get("image_base64")
    filename = body.get("filename")
    user_id = body.get("user_id")

    missing = [
        name for name, value in
        (("image_base64", image_b64), ("filename", filename), ("user_id", user_id))
        if not value
    ]
    if missing:
        return responses.bad_request("Missing required field(s)", details=missing)

    content_type = body.get("content_type") or "image/jpeg"
    tags = body.get("tags") or []
    if not isinstance(tags, list):
        return responses.bad_request("`tags` must be a list of strings")

    # --- decode image ---
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError):
        return responses.bad_request("`image_base64` is not valid base64")

    if len(image_bytes) == 0:
        return responses.bad_request("Decoded image is empty")
    if len(image_bytes) > config.MAX_IMAGE_BYTES:
        return responses.bad_request(
            f"Image exceeds max size of {config.MAX_IMAGE_BYTES} bytes"
        )

    # --- persist ---
    image_id = str(uuid.uuid4())
    try:
        item = repository.save_image(
            image_id=image_id,
            filename=filename,
            content_type=content_type,
            image_bytes=image_bytes,
            user_id=user_id,
            tags=tags,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return responses.server_error(f"Failed to store image: {exc}")

    return responses.created({"message": "Image uploaded", "image": _serialize(item)})


def _serialize(item):
    """Convert DynamoDB item (may contain Decimal) to JSON-friendly dict."""
    out = dict(item)
    if "size_bytes" in out:
        out["size_bytes"] = int(out["size_bytes"])
    return out
