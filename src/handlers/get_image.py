"""API 3: View / download a single image.

GET /images/{image_id}
Optional query param:
  - download=url    -> return a presigned S3 URL instead of inline bytes

Default behaviour returns the metadata plus the image bytes base64-encoded,
so the response is self-contained and easy to test with curl + jq.
Returns 404 if the image_id does not exist.
"""
import base64

from src.common import responses
from src.common import repository


def handler(event, context=None):
    path_params = event.get("pathParameters") or {}
    image_id = path_params.get("image_id")
    if not image_id:
        return responses.bad_request("image_id path parameter is required")

    item = repository.get_metadata(image_id)
    if not item:
        return responses.not_found(f"Image '{image_id}' not found")

    params = event.get("queryStringParameters") or {}
    mode = params.get("download")

    try:
        if mode == "url":
            url = repository.generate_presigned_url(item["s3_key"])
            return responses.ok({"image": _serialize(item), "download_url": url})

        image_bytes, content_type = repository.get_image_bytes(item["s3_key"])
    except Exception as exc:  # pragma: no cover - defensive
        return responses.server_error(f"Failed to fetch image: {exc}")

    return responses.ok({
        "image": _serialize(item),
        "content_type": content_type,
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
    })


def _serialize(item):
    out = dict(item)
    if "size_bytes" in out:
        out["size_bytes"] = int(out["size_bytes"])
    return out
