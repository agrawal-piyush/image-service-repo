"""API 2: List all images, with filters.

GET /images
Query string parameters (all optional, combined with AND):
  - user_id         exact match on uploader
  - tag             images whose tag list contains this value
  - content_type    exact match, e.g. image/png
  - uploaded_after  ISO timestamp lower bound (inclusive)
  - uploaded_before ISO timestamp upper bound (inclusive)

At least two filters (user_id and tag) are supported as required.
Returns 200 with {"count": N, "images": [...]}.
"""
from src.common import responses
from src.common import repository


def handler(event, context=None):
    params = event.get("queryStringParameters") or {}

    user_id = params.get("user_id")
    tag = params.get("tag")
    content_type = params.get("content_type")
    uploaded_after = params.get("uploaded_after")
    uploaded_before = params.get("uploaded_before")

    try:
        items = repository.list_metadata(
            user_id=user_id,
            tag=tag,
            content_type=content_type,
            uploaded_after=uploaded_after,
            uploaded_before=uploaded_before,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return responses.server_error(f"Failed to list images: {exc}")

    images = [_serialize(i) for i in items]
    # Stable, newest-first ordering for predictable output.
    images.sort(key=lambda i: i.get("uploaded_at", ""), reverse=True)

    return responses.ok({"count": len(images), "images": images})


def _serialize(item):
    out = dict(item)
    if "size_bytes" in out:
        out["size_bytes"] = int(out["size_bytes"])
    return out
