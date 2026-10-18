"""Helpers to build API Gateway (Lambda proxy integration) responses.

Every handler returns a dict shaped like:
    {"statusCode": int, "headers": {...}, "body": "<json string>"}
"""
import json

_DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}


def _response(status_code, body, extra_headers=None):
    headers = dict(_DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body),
    }


def ok(body, status_code=200):
    """2xx success response."""
    return _response(status_code, body)


def created(body):
    """201 Created."""
    return _response(201, body)


def bad_request(message, details=None):
    """400 - client sent invalid input."""
    return _response(400, {"error": "BadRequest", "message": message, "details": details})


def not_found(message):
    """404 - resource does not exist."""
    return _response(404, {"error": "NotFound", "message": message})


def server_error(message):
    """500 - unexpected failure."""
    return _response(500, {"error": "InternalServerError", "message": message})
