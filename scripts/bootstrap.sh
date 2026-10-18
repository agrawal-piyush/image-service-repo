#!/usr/bin/env bash
#
# Provisions the full image service inside LocalStack:
#   - S3 bucket
#   - DynamoDB table
#   - 4 Lambda functions (upload, list, get, delete)
#   - API Gateway REST API wiring routes to the Lambdas
#
# Requires: LocalStack running (docker compose up -d) and either `awslocal`
# or the standard `aws` CLI. If `awslocal` is not installed we fall back to
# `aws --endpoint-url=http://localhost:4566`.
#
# Usage:  ./scripts/bootstrap.sh
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Config (override via env if desired)
# ---------------------------------------------------------------------------
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
BUCKET_NAME="${BUCKET_NAME:-images-bucket}"
TABLE_NAME="${TABLE_NAME:-images}"
API_NAME="${API_NAME:-image-service-api}"
LAMBDA_ROLE="arn:aws:iam::000000000000:role/lambda-role"
RUNTIME="python3.11"

# Resolve project root (this script lives in <root>/scripts).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"

# ---------------------------------------------------------------------------
# Pick CLI: awslocal if present, else aws --endpoint-url
# ---------------------------------------------------------------------------
if command -v awslocal >/dev/null 2>&1; then
  AWS="awslocal"
else
  AWS="aws --endpoint-url=$ENDPOINT"
fi
echo "Using AWS CLI command: $AWS"

# ---------------------------------------------------------------------------
# 1. S3 bucket
# ---------------------------------------------------------------------------
echo "==> Creating S3 bucket: $BUCKET_NAME"
$AWS s3 mb "s3://$BUCKET_NAME" 2>/dev/null || echo "    bucket already exists"

# ---------------------------------------------------------------------------
# 2. DynamoDB table
# ---------------------------------------------------------------------------
echo "==> Creating DynamoDB table: $TABLE_NAME"
if ! $AWS dynamodb describe-table --table-name "$TABLE_NAME" >/dev/null 2>&1; then
  $AWS dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=image_id,AttributeType=S \
    --key-schema AttributeName=image_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "    waiting for table to become ACTIVE..."
  $AWS dynamodb wait table-exists --table-name "$TABLE_NAME"
else
  echo "    table already exists"
fi

# ---------------------------------------------------------------------------
# 3. Package Lambda code
# ---------------------------------------------------------------------------
echo "==> Packaging Lambda deployment zip"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cp -r "$ROOT_DIR/src" "$BUILD_DIR/src"
( cd "$BUILD_DIR" && zip -qr function.zip src )
ZIP_PATH="$BUILD_DIR/function.zip"

# ---------------------------------------------------------------------------
# 4. Create the 4 Lambda functions
#    handler path = src.handlers.<module>.handler
# ---------------------------------------------------------------------------
create_lambda () {
  local fn_name="$1"
  local handler_path="$2"
  echo "==> Deploying Lambda: $fn_name ($handler_path)"
  $AWS lambda delete-function --function-name "$fn_name" >/dev/null 2>&1 || true
  $AWS lambda create-function \
    --function-name "$fn_name" \
    --runtime "$RUNTIME" \
    --handler "$handler_path" \
    --role "$LAMBDA_ROLE" \
    --timeout 60 \
    --environment "Variables={BUCKET_NAME=$BUCKET_NAME,TABLE_NAME=$TABLE_NAME,AWS_ENDPOINT_URL=http://localstack:4566,AWS_REGION=$AWS_REGION}" \
    --zip-file "fileb://$ZIP_PATH" >/dev/null
  $AWS lambda wait function-active-v2 --function-name "$fn_name" 2>/dev/null || true
}

create_lambda "image-upload"  "src.handlers.upload.handler"
create_lambda "image-list"    "src.handlers.list_images.handler"
create_lambda "image-get"     "src.handlers.get_image.handler"
create_lambda "image-delete"  "src.handlers.delete_image.handler"

# ---------------------------------------------------------------------------
# 5. API Gateway REST API
#    Routes:
#      POST   /images              -> image-upload
#      GET    /images              -> image-list
#      GET    /images/{image_id}   -> image-get
#      DELETE /images/{image_id}   -> image-delete
# ---------------------------------------------------------------------------
echo "==> Creating API Gateway REST API: $API_NAME"
API_ID=$($AWS apigateway create-rest-api --name "$API_NAME" \
  --query 'id' --output text)
echo "    API_ID=$API_ID"

ROOT_ID=$($AWS apigateway get-resources --rest-api-id "$API_ID" \
  --query 'items[?path==`/`].id' --output text)

# /images
IMAGES_ID=$($AWS apigateway create-resource --rest-api-id "$API_ID" \
  --parent-id "$ROOT_ID" --path-part "images" --query 'id' --output text)

# /images/{image_id}
IMAGE_ID_RES=$($AWS apigateway create-resource --rest-api-id "$API_ID" \
  --parent-id "$IMAGES_ID" --path-part "{image_id}" --query 'id' --output text)

ACCOUNT_ID="000000000000"

wire_method () {
  local resource_id="$1"
  local http_method="$2"
  local fn_name="$3"

  $AWS apigateway put-method \
    --rest-api-id "$API_ID" \
    --resource-id "$resource_id" \
    --http-method "$http_method" \
    --authorization-type "NONE" >/dev/null

  local lambda_arn="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${fn_name}"
  local uri="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${lambda_arn}/invocations"

  $AWS apigateway put-integration \
    --rest-api-id "$API_ID" \
    --resource-id "$resource_id" \
    --http-method "$http_method" \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "$uri" >/dev/null

  # Allow API Gateway to invoke the Lambda.
  $AWS lambda add-permission \
    --function-name "$fn_name" \
    --statement-id "apigw-${fn_name}-${http_method}" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com >/dev/null 2>&1 || true
}

echo "==> Wiring routes"
wire_method "$IMAGES_ID"     "POST"   "image-upload"
wire_method "$IMAGES_ID"     "GET"    "image-list"
wire_method "$IMAGE_ID_RES"  "GET"    "image-get"
wire_method "$IMAGE_ID_RES"  "DELETE" "image-delete"

# ---------------------------------------------------------------------------
# 6. Deploy to a stage
# ---------------------------------------------------------------------------
STAGE="local"
echo "==> Deploying API to stage: $STAGE"
$AWS apigateway create-deployment \
  --rest-api-id "$API_ID" \
  --stage-name "$STAGE" >/dev/null

BASE_URL="$ENDPOINT/restapis/$API_ID/$STAGE/_user_request_"
echo ""
echo "============================================================"
echo " Image service is ready on LocalStack!"
echo "   API_ID    : $API_ID"
echo "   Base URL  : $BASE_URL"
echo ""
echo " Try:"
echo "   curl -s \"$BASE_URL/images\""
echo "============================================================"

# Persist the base URL for convenience.
echo "$BASE_URL" > "$ROOT_DIR/.api_base_url"
