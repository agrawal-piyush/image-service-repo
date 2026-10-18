"""API 4: Delete an image.

DELETE /images/{image_id}

Removes both the S3 object and the DynamoDB metadata record.
Returns 404 if the image_id does not exist, 200 on success.
"""
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

    try:
        repository.delete_image(image_id, item["s3_key"])
    except Exception as exc:  # pragma: no cover - defensive
        return responses.server_error(f"Failed to delete image: {exc}")

    return responses.ok({"message": "Image deleted", "image_id": image_id})
