"""Data-access layer: all S3 + DynamoDB operations live here.

Keeping storage logic in one place keeps the Lambda handlers thin and makes
the filtering logic independently testable.
"""
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Attr

from src.common import config
from src.common.aws_clients import get_s3_client, get_table


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_s3_key(image_id, filename):
    """Compose the S3 object key for an image."""
    # Keep the original extension if present for nicer downloads.
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()
    return f"{config.S3_KEY_PREFIX}/{image_id}{ext}"


def put_image_object(s3_key, image_bytes, content_type):
    """Store raw image bytes in S3."""
    get_s3_client().put_object(
        Bucket=config.BUCKET_NAME,
        Key=s3_key,
        Body=image_bytes,
        ContentType=content_type,
    )


def put_metadata(item):
    """Persist image metadata in DynamoDB."""
    get_table().put_item(Item=item)


def save_image(image_id, filename, content_type, image_bytes, user_id, tags):
    """Store image in S3 and its metadata in DynamoDB. Returns the metadata item."""
    s3_key = build_s3_key(image_id, filename)
    put_image_object(s3_key, image_bytes, content_type)

    item = {
        "image_id": image_id,
        "user_id": user_id,
        "filename": filename,
        "content_type": content_type,
        "tags": tags or [],
        "s3_key": s3_key,
        "size_bytes": len(image_bytes),
        "uploaded_at": _utc_now_iso(),
    }
    put_metadata(item)
    return item


def get_metadata(image_id):
    """Fetch a single metadata item, or None if it does not exist."""
    resp = get_table().get_item(Key={"image_id": image_id})
    return resp.get("Item")


def list_metadata(user_id=None, tag=None, content_type=None,
                  uploaded_after=None, uploaded_before=None):
    """Return metadata items matching the given filters.

    Supported filters (all optional, combined with AND):
      - user_id        : exact match
      - tag            : item whose `tags` list contains this value
      - content_type   : exact match (e.g. "image/png")
      - uploaded_after  / uploaded_before : ISO timestamp range on uploaded_at

    Uses a DynamoDB Scan with a FilterExpression. For a production system at
    scale you would add a GSI (e.g. on user_id) and Query instead of Scan;
    Scan is fine for this exercise and keeps the filter logic flexible.
    """
    filter_expr = None

    def _and(expr, condition):
        return condition if expr is None else expr & condition

    if user_id:
        filter_expr = _and(filter_expr, Attr("user_id").eq(user_id))
    if tag:
        filter_expr = _and(filter_expr, Attr("tags").contains(tag))
    if content_type:
        filter_expr = _and(filter_expr, Attr("content_type").eq(content_type))
    if uploaded_after:
        filter_expr = _and(filter_expr, Attr("uploaded_at").gte(uploaded_after))
    if uploaded_before:
        filter_expr = _and(filter_expr, Attr("uploaded_at").lte(uploaded_before))

    table = get_table()
    scan_kwargs = {}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    items = []
    # Handle pagination so results are complete even for large tables.
    while True:
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return items


def get_image_bytes(s3_key):
    """Return the raw bytes + content type of an object in S3."""
    resp = get_s3_client().get_object(Bucket=config.BUCKET_NAME, Key=s3_key)
    return resp["Body"].read(), resp.get("ContentType", "application/octet-stream")


def generate_presigned_url(s3_key):
    """Return a time-limited download URL for the object."""
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.BUCKET_NAME, "Key": s3_key},
        ExpiresIn=config.PRESIGN_EXPIRY_SECONDS,
    )


def delete_image(image_id, s3_key):
    """Delete both the S3 object and the DynamoDB metadata item."""
    get_s3_client().delete_object(Bucket=config.BUCKET_NAME, Key=s3_key)
    get_table().delete_item(Key={"image_id": image_id})
