"""Central configuration for the image service.

All values are read from environment variables so the same code runs
unchanged against LocalStack (local dev) and real AWS (prod).
"""
import os

# AWS region used by all clients.
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# S3 bucket that stores the raw image bytes.
BUCKET_NAME = os.environ.get("BUCKET_NAME", "images-bucket")

# DynamoDB table that stores image metadata.
TABLE_NAME = os.environ.get("TABLE_NAME", "images")

# When running against LocalStack this points boto3 at the local endpoint
# (e.g. http://localhost:4566). When empty/unset, boto3 talks to real AWS.
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL") or None

# Max upload size we accept (10 MB). Protects Lambda memory / payload limits.
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))

# Prefix used for object keys inside the bucket.
S3_KEY_PREFIX = os.environ.get("S3_KEY_PREFIX", "images")

# Presigned download URL expiry (seconds).
PRESIGN_EXPIRY_SECONDS = int(os.environ.get("PRESIGN_EXPIRY_SECONDS", "3600"))
