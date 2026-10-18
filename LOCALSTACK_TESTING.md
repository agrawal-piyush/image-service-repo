# Running & Testing on LocalStack (End-to-End)

This guide shows how to run the whole service on **LocalStack** and test the four
APIs over real HTTP with `curl`. LocalStack needs **Docker**, so you'll do this on
your machine with Docker available (e.g. your Windows laptop via WSL2, or any
Mac/Linux with Docker/Colima).

> Unit tests do **not** need Docker — for those just run `pytest` (see `README.md`).
> This file is specifically for the **LocalStack end-to-end** flow.

---

## Step 0 — One-time Docker setup

### Windows (recommended: WSL2)
1. In an **admin PowerShell**: `wsl --install`, then reboot.
2. Install **Docker Desktop for Windows**.
3. Docker Desktop → **Settings → Resources → WSL Integration** → enable your Ubuntu distro.
4. Open the **Ubuntu (WSL)** terminal and work from there (the `.sh` script runs natively).

### macOS
```bash
brew install colima docker docker-compose
colima start
```

### Linux
Install Docker Engine + the compose plugin from your distro.

---

## Step 1 — Prepare the project (inside WSL/Linux/mac shell)

```bash
cd image-service
# (Linux/WSL only, if Python tooling is missing)
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

---

## Step 2 — Start LocalStack

```bash
docker compose up -d
```

First run pulls the image (~500 MB), so give it a minute. Verify:

```bash
docker ps
# You should see a container named "image-service-localstack" that is Up/healthy.
```

---

## Step 3 — Provision all AWS resources

```bash
bash scripts/bootstrap.sh
```

This automatically creates:
- the **S3 bucket**
- the **DynamoDB table**
- the **4 Lambda functions** (upload / list / get / delete)
- the **API Gateway** REST API and wires all routes

At the end it prints the API **Base URL** and writes it to `.api_base_url`:

```
Base URL : http://localhost:4566/restapis/<api-id>/local/_user_request_
```

Capture it into a variable:

```bash
export BASE_URL=$(cat .api_base_url)
echo "$BASE_URL"
```

---

## Step 4 — Test the four APIs with curl

Assume you have an image file named `cat.jpg` in the current folder.

### 4a. Upload — `POST /images`
```bash
IMG_B64=$(base64 -w0 cat.jpg)       # Linux/WSL
# on macOS use:  IMG_B64=$(base64 -i cat.jpg)

curl -s -X POST "$BASE_URL/images" \
  -H "Content-Type: application/json" \
  -d "{\"image_base64\":\"$IMG_B64\",\"filename\":\"cat.jpg\",\"user_id\":\"piyush\",\"content_type\":\"image/jpeg\",\"tags\":[\"pet\",\"cute\"]}"
```
Copy the `image_id` from the response for the next steps.

### 4b. List all — `GET /images`
```bash
curl -s "$BASE_URL/images"
```

### 4c. List with filters (two filters — the required scenario)
```bash
curl -s "$BASE_URL/images?user_id=piyush"
curl -s "$BASE_URL/images?tag=pet"
curl -s "$BASE_URL/images?user_id=piyush&tag=pet"
curl -s "$BASE_URL/images?content_type=image/jpeg"
```

### 4d. View / download — `GET /images/{image_id}`
```bash
curl -s "$BASE_URL/images/<image_id>"                 # metadata + base64 bytes
curl -s "$BASE_URL/images/<image_id>?download=url"    # presigned S3 URL

# Save the returned base64 back to a file:
curl -s "$BASE_URL/images/<image_id>" | \
  python3 -c "import sys,json,base64;d=json.load(sys.stdin);open('out.jpg','wb').write(base64.b64decode(d['image_base64']))"
```

### 4e. Delete — `DELETE /images/{image_id}`
```bash
curl -s -X DELETE "$BASE_URL/images/<image_id>"
# Deleting again returns 404 (already gone).
```

---

## Step 5 — (Optional) Inspect the stores directly

Install `awslocal` to query S3 / DynamoDB in LocalStack directly — great for
proving the data really landed in both stores:

```bash
pip install awscli-local

# object stored in S3
awslocal s3 ls s3://images-bucket/images/

# metadata stored in DynamoDB
awslocal dynamodb scan --table-name images
```

(If you don't have `awslocal`, the same works with:
`aws --endpoint-url=http://localhost:4566 s3 ls s3://images-bucket/images/`)

---

## Step 6 — Shut down

```bash
docker compose down
```

To also wipe persisted LocalStack state, delete the `.localstack-data/` folder.

---

## TL;DR

```bash
docker compose up -d                     # 1. start LocalStack
bash scripts/bootstrap.sh                # 2. create bucket/table/lambdas/api
export BASE_URL=$(cat .api_base_url)     # 3. grab the base URL
# 4. test:
curl -s -X POST "$BASE_URL/images" -H "Content-Type: application/json" -d '{...}'
curl -s "$BASE_URL/images?user_id=piyush&tag=pet"
curl -s "$BASE_URL/images/<image_id>"
curl -s -X DELETE "$BASE_URL/images/<image_id>"
docker compose down                      # 5. stop
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `docker: command not found` | Install/start Docker (Docker Desktop on Windows, Colima on mac) |
| `bootstrap.sh: Permission denied` | `chmod +x scripts/bootstrap.sh` or run `bash scripts/bootstrap.sh` |
| `bash\r: bad interpreter` (Windows line endings) | `dos2unix scripts/bootstrap.sh` or clone with `git config --global core.autocrlf input` |
| Lambda create fails / times out | LocalStack Lambda uses Docker — ensure the Docker socket is mounted (it is in `docker-compose.yml`) and Docker has enough resources |
| `curl` returns empty / connection refused | Confirm `docker ps` shows LocalStack Up; re-check `BASE_URL` matches the printed one |
| Everything 404 after restart | LocalStack free tier doesn't persist API Gateway across restarts — re-run `bash scripts/bootstrap.sh` |
