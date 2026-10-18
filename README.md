# Image Service (Serverless, Instagram-style)

A scalable image upload & storage service built on **API Gateway → Lambda → S3 + DynamoDB**,
runnable entirely on your machine with **LocalStack**. Images are stored in S3; their
metadata is stored in DynamoDB.

- **Language:** Python 3.7+
- **Stores:** S3 (image bytes) + DynamoDB (metadata)
- **Local cloud:** LocalStack (Docker)
- **Tests:** `pytest` + `moto` (run without Docker)

---

## 1. Architecture

```
                 ┌──────────────┐
   HTTP client → │ API Gateway  │
                 └──────┬───────┘
                        │ (Lambda proxy integration)
         ┌──────────────┼───────────────┬───────────────┐
         ▼              ▼                ▼               ▼
   image-upload    image-list       image-get      image-delete   (Lambda)
         │              │                │               │
         ├──────────────┴────────┬───────┴───────────────┤
         ▼                        ▼                       ▼
   ┌───────────┐            ┌───────────┐          (deletes from both)
   │    S3     │            │ DynamoDB  │
   │  images   │            │  metadata │
   └───────────┘            └───────────┘
```

**Why it scales:** Lambda scales horizontally per-request automatically; S3 and
DynamoDB (PAY_PER_REQUEST) are managed, auto-scaling stores. There are no servers
to manage and no shared mutable state in the handlers.

### DynamoDB table: `images`

| Attribute      | Type   | Notes                                  |
|----------------|--------|----------------------------------------|
| `image_id` (PK)| String | UUID, partition key                    |
| `user_id`      | String | uploader — **filterable**              |
| `filename`     | String | original file name                     |
| `content_type` | String | e.g. `image/png` — **filterable**      |
| `tags`         | List   | e.g. `["pet","cute"]` — **filterable** |
| `s3_key`       | String | pointer to the object in S3            |
| `size_bytes`   | Number | decoded image size                     |
| `uploaded_at`  | String | ISO-8601 timestamp — **filterable**    |

---

## 2. Project layout

```
image-service/
├── docker-compose.yml        # LocalStack
├── Makefile                  # convenience targets
├── requirements.txt
├── pytest.ini
├── scripts/
│   └── bootstrap.sh          # provisions S3/DynamoDB/Lambda/API Gateway
├── src/
│   ├── common/               # config, boto3 clients, responses, repository
│   └── handlers/             # upload / list_images / get_image / delete_image
└── tests/                    # unit tests (moto)
```

---

## 3. Prerequisites & Setup

What you need depends on **what you want to run**:

| Goal | Requirements |
|------|--------------|
| Run the **unit tests** (24 tests) | Just **Python 3.7+**. **No Docker needed** — tests mock AWS in-memory with `moto`. |
| Run the **LocalStack end-to-end demo** (real HTTP upload/list/get/delete) | **Docker** + a bash shell (Linux/macOS/WSL). |

> **Key point:** Docker is **only** for the LocalStack demo. If you just want the
> tests to pass, skip straight to section 4a.

### 3.1 Install Python
- **Linux / WSL (Ubuntu):**
  ```bash
  sudo apt update && sudo apt install -y python3 python3-venv python3-pip
  ```
  `python3-venv` is required — without it `python3 -m venv .venv` fails with
  *"The virtual environment was not created successfully"*.
- **macOS:** `brew install python` (or use the system Python 3).
- **Windows (native):** install from https://www.python.org/downloads/ and tick
  **"Add Python to PATH"**.

### 3.2 Install Docker (only for the LocalStack demo)

**Windows — recommended path is WSL2 + Docker Desktop:**
1. In an **admin PowerShell**, install WSL and an Ubuntu distro, then reboot:
   ```powershell
   wsl --install -d Ubuntu
   ```
   Finish the Ubuntu first-run setup (create a username + password).
2. Install **Docker Desktop for Windows** and start it. Wait until the bottom-left
   status shows **"Engine running"** (green).
3. Enable Docker inside Ubuntu:
   **Docker Desktop → Settings → Resources → WSL Integration →** turn on your
   **Ubuntu** distro **→ Apply & Restart**.
   (If Ubuntu doesn't appear in that list, open the Ubuntu terminal once so it is
   `Running`, then re-check — see Troubleshooting.)
4. From now on, run all project commands **inside the Ubuntu (WSL) terminal**, not
   PowerShell — the `scripts/bootstrap.sh` script is bash.

**macOS:**
```bash
brew install colima docker docker-compose
colima start
```

**Linux:** install Docker Engine + the Compose plugin from your distro.

### 3.3 (Optional) `awslocal` CLI
The bootstrap script uses `awslocal` if present, otherwise it falls back to
`aws --endpoint-url=http://localhost:4566`. To get the nicer `awslocal` command:
```bash
pip install awscli-local
```

---

## 4. Quick start

### 4a. Run the unit tests (no Docker required)

```bash
make setup      # create .venv + install deps
make test       # run pytest  -> 24 passing tests
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

### 4b. Run end-to-end on LocalStack (Docker required)

```bash
make up          # start LocalStack (docker compose up -d)
make bootstrap   # create bucket, table, 4 Lambdas, API Gateway
# ... or do both at once:
make deploy
```

`bootstrap.sh` prints the **base URL**, e.g.:

```
Base URL : http://localhost:4566/restapis/<api-id>/local/_user_request_
```

It is also written to `.api_base_url`. Capture it:

```bash
export BASE_URL=$(cat .api_base_url)
```

> **Reaching the API — two URL formats.** LocalStack exposes the REST API in two ways:
>
> 1. **Path style** (what `BASE_URL` above uses):
>    `http://localhost:4566/restapis/<api-id>/local/_user_request_/images`
> 2. **Host style** (`execute-api` virtual host):
>    `http://localhost:4566/local/images` **with** header
>    `Host: <api-id>.execute-api.localhost.localstack.cloud`
>
> On most setups the path style (`$BASE_URL`) just works. On **Docker Desktop + WSL2**
> with LocalStack 3.x the path style can be flaky — it sometimes gets routed to S3 and
> returns `NoSuchBucket`. If that happens, use the **host style** instead:
>
> ```bash
> # derive the api-id from the saved base URL
> APIID=$(sed -E 's#.*/restapis/([^/]+)/.*#\1#' .api_base_url)
> HOSTH="Host: $APIID.execute-api.localhost.localstack.cloud"
>
> # example: list images
> curl -s -H "$HOSTH" "http://localhost:4566/local/images"
> ```
>
> Both formats hit the exact same API Gateway → Lambda → S3/DynamoDB stack.

Tear down with `make down`.

---

## 5. API Reference

Base path: `/images`

### 5.1 Upload an image — `POST /images`

Request body (JSON). The image is sent as **base64**.

| Field          | Required | Description                        |
|----------------|----------|------------------------------------|
| `image_base64` | yes      | base64-encoded image bytes         |
| `filename`     | yes      | original filename (`cat.jpg`)      |
| `user_id`      | yes      | uploader id                        |
| `content_type` | no       | default `image/jpeg`               |
| `tags`         | no       | list of strings                    |

**201 Created**
```json
{
  "message": "Image uploaded",
  "image": {
    "image_id": "2b1f...-uuid",
    "user_id": "piyush",
    "filename": "cat.jpg",
    "content_type": "image/jpeg",
    "tags": ["pet", "cute"],
    "s3_key": "images/2b1f...-uuid.jpg",
    "size_bytes": 20481,
    "uploaded_at": "2026-10-13T10:00:00+00:00"
  }
}
```

**Errors:** `400` missing/invalid field, bad base64, oversized image.

```bash
# Build a base64 image from a real file and upload it
IMG_B64=$(base64 -i cat.jpg)       # macOS; on Linux: base64 -w0 cat.jpg
curl -s -X POST "$BASE_URL/images" \
  -H "Content-Type: application/json" \
  -d "{\"image_base64\":\"$IMG_B64\",\"filename\":\"cat.jpg\",\"user_id\":\"piyush\",\"content_type\":\"image/jpeg\",\"tags\":[\"pet\",\"cute\"]}"
```

### 5.2 List images (with filters) — `GET /images`

Query parameters (all optional, combined with **AND**):

| Param             | Example                         | Meaning                         |
|-------------------|---------------------------------|---------------------------------|
| `user_id`         | `?user_id=piyush`               | exact uploader match            |
| `tag`             | `?tag=pet`                      | tag list contains value         |
| `content_type`    | `?content_type=image/png`       | exact match                     |
| `uploaded_after`  | `?uploaded_after=2026-01-01T00:00:00+00:00` | ISO lower bound     |
| `uploaded_before` | `?uploaded_before=2026-12-31T00:00:00+00:00`| ISO upper bound     |

**200 OK**
```json
{ "count": 2, "images": [ { "image_id": "...", "...": "..." } ] }
```

```bash
curl -s "$BASE_URL/images"                              # all
curl -s "$BASE_URL/images?user_id=piyush"               # filter 1
curl -s "$BASE_URL/images?tag=pet"                      # filter 2
curl -s "$BASE_URL/images?user_id=piyush&tag=pet"       # combined
```

### 5.3 View / download an image — `GET /images/{image_id}`

Default: returns metadata + the image inline as base64.
Add `?download=url` to get a presigned S3 URL instead.

**200 OK (inline)**
```json
{
  "image": { "image_id": "...", "...": "..." },
  "content_type": "image/jpeg",
  "image_base64": "<base64 bytes>"
}
```

**200 OK (`?download=url`)**
```json
{ "image": { "...": "..." }, "download_url": "http://localhost:4566/..." }
```

**404** if the id does not exist.

```bash
curl -s "$BASE_URL/images/<image_id>"                       # inline bytes
curl -s "$BASE_URL/images/<image_id>?download=url"          # presigned URL

# Save the returned base64 back to a file:
curl -s "$BASE_URL/images/<image_id>" | \
  python3 -c "import sys,json,base64;d=json.load(sys.stdin);open('out.jpg','wb').write(base64.b64decode(d['image_base64']))"
```

### 5.4 Delete an image — `DELETE /images/{image_id}`

Removes the object from S3 **and** the metadata row from DynamoDB.

**200 OK**
```json
{ "message": "Image deleted", "image_id": "..." }
```

**404** if the id does not exist.

```bash
curl -s -X DELETE "$BASE_URL/images/<image_id>"
```

---

## 6. Testing

```bash
make test
# or
pytest -v
```

24 tests cover success and error paths for all four handlers:

- **upload:** success (S3+DynamoDB written), missing body, invalid JSON,
  missing required fields, invalid base64, non-list tags, oversized image, dict body
- **list:** no filter, by `user_id`, by `tag`, combined, by `content_type`,
  no-match, date range, empty table
- **get:** inline bytes, presigned URL, not found, missing path param
- **delete:** success (both stores cleared), not found, missing path param, double-delete → 404

Tests use `moto` to mock AWS in-memory, so **no Docker/LocalStack is required** to run them.

---

## 7. Configuration (environment variables)

| Variable                | Default          | Purpose                                   |
|-------------------------|------------------|-------------------------------------------|
| `AWS_REGION`            | `us-east-1`      | region for all clients                    |
| `BUCKET_NAME`           | `images-bucket`  | S3 bucket                                 |
| `TABLE_NAME`            | `images`         | DynamoDB table                            |
| `AWS_ENDPOINT_URL`      | *(unset)*        | set to LocalStack endpoint for local runs |
| `MAX_IMAGE_BYTES`       | `10485760` (10MB)| upload size cap                           |
| `S3_KEY_PREFIX`         | `images`         | object key prefix                         |
| `PRESIGN_EXPIRY_SECONDS`| `3600`           | presigned URL lifetime                    |

The same code runs against real AWS by deploying the handlers as Lambdas and
leaving `AWS_ENDPOINT_URL` unset.

---

## 8. Notes & trade-offs

- **Scan vs Query:** `list` uses a DynamoDB `Scan` + `FilterExpression` for flexible
  multi-field filtering. For production scale you'd add a GSI (e.g. on `user_id`) and
  `Query` the hot access patterns. Scan is appropriate for this exercise.
- **Image transport:** images are sent/received as base64 JSON so the API is
  self-contained and easy to test. For large files in production you'd instead issue
  a presigned **upload** URL and have the client PUT directly to S3.
- **Handlers are thin:** all storage logic lives in `src/common/repository.py`,
  which keeps handlers readable and the logic unit-testable.

---

## 9. Troubleshooting

Real issues you may hit during setup, and how to fix them.

### Setup / Python

| Symptom | Cause | Fix |
|---------|-------|-----|
| `The virtual environment was not created successfully` (on `make setup`) | `python3-venv` is not installed (common on fresh Ubuntu/WSL) | `sudo apt update && sudo apt install -y python3-venv python3-pip`, then `rm -rf .venv && make setup` |
| `python: command not found` (Windows) | Python not on PATH | Reinstall Python with **"Add to PATH"** checked, or use `py -3` instead of `python` |
| `make: command not found` (Windows native) | `make` is not native on Windows | Use **WSL/Ubuntu**, or run the raw commands from the `Makefile` manually |
| `Activate.ps1 cannot be loaded ... execution policy` (Windows PowerShell) | PowerShell blocks scripts by default | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again |

### Docker / WSL

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker: command not found` | Docker not installed / not on this shell | Install & start Docker Desktop (Windows/mac) or Docker Engine (Linux) |
| `The command 'docker' could not be found ... please invoke the docker CLI from PowerShell` (inside WSL) | Docker Desktop **WSL integration** is not enabled for your Ubuntu distro | Docker Desktop → Settings → Resources → **WSL Integration** → enable **Ubuntu** → Apply & Restart |
| Ubuntu does **not** appear in the WSL Integration list | The Ubuntu distro isn't installed, or is stopped (only `docker-desktop` shows in `wsl -l -v`) | Install it: `wsl --install -d Ubuntu`. If already installed, open the Ubuntu terminal once (so its STATE is `Running`), then re-check the list |
| `permission denied while trying to connect to the Docker ... socket` (inside WSL) | Your Linux user isn't in the `docker` group | `sudo usermod -aG docker $USER`, then from PowerShell `wsl --shutdown`, reopen Ubuntu, and retry `docker ps`. Quick one-session fix: `newgrp docker` |
| WSL shows `VERSION 1` | Docker Desktop needs WSL 2 | `wsl --set-version Ubuntu 2` (use the exact distro name from `wsl -l -v`) |

### LocalStack / bootstrap

| Symptom | Cause | Fix |
|---------|-------|-----|
| `bootstrap.sh: Permission denied` | script not executable | `chmod +x scripts/bootstrap.sh`, or just run `bash scripts/bootstrap.sh` |
| `bash\r: bad interpreter` | Windows (CRLF) line endings in the `.sh` file | `dos2unix scripts/bootstrap.sh`, or clone with `git config --global core.autocrlf input` |
| First `docker compose up -d` is slow | LocalStack image (~500 MB) is being pulled | One-time download; wait a minute. Verify with `docker compose ps` (container `image-service-localstack` should be `running`/`healthy`) |
| `curl` returns empty / connection refused | LocalStack not up, or wrong `BASE_URL` | Confirm `docker compose ps` shows it Up; re-run `export BASE_URL=$(cat .api_base_url)` |
| Lambda invoke hangs, logs show `Connection to 172.x.x.x ... /invoke timed out` | LocalStack and the Lambda containers it spawns are on **different** Docker networks (common on Docker Desktop + WSL2) | Ensure `LAMBDA_DOCKER_NETWORK` matches the network LocalStack itself runs on. This repo's `docker-compose.yml` puts both on a shared `ls-net` network. After editing, fully recreate: `docker compose down && docker compose up -d --force-recreate && bash scripts/bootstrap.sh` |
| API call returns XML `<Error><Code>NoSuchBucket</Code> ... <BucketName>restapis</BucketName>` | The path-style URL (`/restapis/<id>/.../_user_request_`) got routed to S3 — a LocalStack 3.x + WSL quirk | Use the **host-style** URL instead (see the note in section 4b): `curl -H "Host: <api-id>.execute-api.localhost.localstack.cloud" http://localhost:4566/local/images` |
| On WSL, `localhost:4566` is slow but `127.0.0.1:4566` works for health yet breaks API Gateway (`NoSuchBucket`) | `localhost` vs `127.0.0.1` resolve differently for LocalStack's host-based routing | Use `localhost` (not `127.0.0.1`) for API Gateway / host-style calls; `127.0.0.1` is fine for the `/_localstack/health` check |
| Everything returns `404` after a Docker restart | LocalStack (free tier) doesn't persist API Gateway across restarts | Re-run `bash scripts/bootstrap.sh` to recreate the resources |
| `bootstrap.sh` hangs at "waiting for table to become ACTIVE" | LocalStack occasionally keeps a DynamoDB table in `CREATING` | The table is usable anyway. In another terminal: `awslocal dynamodb update-table --table-name images --billing-mode PAY_PER_REQUEST`, then re-run bootstrap (it skips the existing table) |

> For the full step-by-step LocalStack walkthrough (with `curl` examples for all four
> APIs and direct S3/DynamoDB inspection), see **[LOCALSTACK_TESTING.md](LOCALSTACK_TESTING.md)**.
> Windows-specific notes are in **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**.
