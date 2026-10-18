# Windows Setup Guide

This project was developed on macOS but runs on Windows too (Python is
cross-platform). This file lists the Windows-specific commands so you can run
everything on your personal Windows laptop without converting anything.

There are two ways to run it on Windows:

- **Option A — Native Windows** (PowerShell / CMD): easiest for the unit tests.
- **Option B — WSL2** (Ubuntu inside Windows): behaves exactly like macOS/Linux,
  best if you also want the LocalStack end-to-end demo.

---

## Option A — Native Windows (PowerShell)

### A1. Prerequisites
- **Python 3.7+** — install from https://www.python.org/downloads/ and tick
  "Add Python to PATH" during install.
- (Only for LocalStack demo) **Docker Desktop for Windows** with the WSL2 backend.
- (Only for the bootstrap script) **Git for Windows** — it ships with "Git Bash",
  which can run the `.sh` script.

### A2. Run the unit tests (no Docker needed)

Open **PowerShell** in the project folder:

```powershell
cd image-service

# create virtual environment
python -m venv .venv

# activate it (PowerShell)
.venv\Scripts\Activate.ps1
#   If PowerShell blocks the script with an execution-policy error, run:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   then re-run the activate line above.
#
#   Using CMD instead of PowerShell? Activate with:
#   .venv\Scripts\activate.bat

# install dependencies
pip install -r requirements.txt

# run the tests
pytest
```

You should see **24 passed**.

Shortcut: just double-click / run **`run_tests.bat`** (included in this project) —
it does all of the above for you.

### A3. LocalStack end-to-end on native Windows

1. Start **Docker Desktop** (make sure it says "Engine running").
2. In PowerShell:
   ```powershell
   docker compose up -d
   ```
3. The provisioning script `scripts/bootstrap.sh` is a **bash** script. Run it with
   **Git Bash** (right-click in the folder → "Git Bash Here"), then:
   ```bash
   bash scripts/bootstrap.sh
   ```
   It will print the API **Base URL** and also write it to `.api_base_url`.
4. Stop LocalStack when done:
   ```powershell
   docker compose down
   ```

### A4. Base64-encode an image on Windows (for upload curl)

macOS uses `base64 -i cat.jpg`. On Windows PowerShell use:

```powershell
# encode a file to base64 and store it in a variable
$IMG_B64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("cat.jpg"))

# upload (curl.exe ships with Windows 10/11)
$body = @{
  image_base64 = $IMG_B64
  filename     = "cat.jpg"
  user_id      = "piyush"
  content_type = "image/jpeg"
  tags         = @("pet","cute")
} | ConvertTo-Json

curl.exe -s -X POST "$($env:BASE_URL)/images" -H "Content-Type: application/json" -d $body
```

List / get / delete with `curl.exe`:

```powershell
curl.exe -s "$($env:BASE_URL)/images"
curl.exe -s "$($env:BASE_URL)/images?user_id=piyush&tag=pet"
curl.exe -s "$($env:BASE_URL)/images/<image_id>"
curl.exe -s -X DELETE "$($env:BASE_URL)/images/<image_id>"
```

Set `BASE_URL` first (copy it from the bootstrap output):

```powershell
$env:BASE_URL = Get-Content .api_base_url
```

---

## Option B — WSL2 (recommended for the full demo)

WSL2 gives you a real Ubuntu environment inside Windows, so every macOS/Linux
command in the main README works unchanged (`make`, `bash`, etc.).

### B1. Install WSL2 (one time)
In an **admin** PowerShell:
```powershell
wsl --install
```
Reboot, let Ubuntu finish setup, then open the **Ubuntu** app.

### B2. Inside Ubuntu (WSL)
```bash
# python + tooling
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

cd image-service          # your files are reachable here
make setup
make test                 # 24 passing tests
```

### B3. LocalStack via WSL2
- Install **Docker Desktop for Windows** and enable **WSL integration** for your
  Ubuntu distro (Docker Desktop → Settings → Resources → WSL Integration).
- Then inside Ubuntu:
  ```bash
  make deploy               # docker compose up + bootstrap
  export BASE_URL=$(cat .api_base_url)
  curl -s "$BASE_URL/images"
  ```

Everything else matches the main `README.md`.

---

## Quick decision

- **Just need the tests to pass for submission?** → Option A, run `run_tests.bat`. Done.
- **Want to demo real upload/list/get/delete over HTTP?** → Option B (WSL2) is the
  smoothest; Option A + Git Bash + Docker Desktop also works.

---

## Common Windows gotchas

| Symptom | Fix |
|---------|-----|
| `Activate.ps1 cannot be loaded ... execution policy` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then activate again |
| `python` not found | Reinstall Python with "Add to PATH" checked, or use `py -3` instead of `python` |
| `bash: scripts/bootstrap.sh` not found on CMD | Use **Git Bash** or **WSL**, not CMD/PowerShell, to run `.sh` files |
| `docker` not recognized | Start Docker Desktop; ensure WSL2 backend is enabled |
| `make: command not found` | `make` isn't native on Windows — run the raw commands (see A2) or use WSL |
| line-ending issues in `.sh` | run `git config --global core.autocrlf input` before cloning, or `dos2unix scripts/bootstrap.sh` |
