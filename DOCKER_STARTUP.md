# BizVision AI — Docker Startup Guide (Windows)

> **You are here**: a step-by-step guide to bring the whole stack up
> on a fresh Windows machine with Docker Desktop, using PowerShell.
>
> The fastest path is **Step 0 + `./setup.ps1`**. The rest of this doc
> explains what that script does, how to recover from common
> problems, and how to operate the running stack day-to-day.

---

## Status of the existing setup machinery (verified)

| Asset | Present? | Purpose |
|---|---|---|
| `docker-compose.yml` | ✅ | 9-service stack: nginx, frontend, backend, celery-worker, celery-beat, flower, postgres+pgvector, redis, mlflow, minio (+ profile-gated ml-dev / prometheus / grafana) |
| `.env.example` | ✅ | Template — all required env vars documented |
| `setup.ps1` | ✅ | **Windows one-command bootstrap** (this is what you'll run) |
| `setup.sh` / `setup.bat` | ✅ | Bash / cmd equivalents |
| `Makefile` | ✅ | Lifecycle commands (works inside WSL or Git Bash — see Step 7) |
| `backend/Dockerfile` | ✅ | Multi-stage: development + production |
| `frontend/Dockerfile` | ✅ | Multi-stage: deps → development / builder → production |
| `infrastructure/postgres/init.sql` | ✅ | pgvector extension + `bizvision_mlflow` DB |
| `infrastructure/nginx/nginx.conf` | ✅ | Reverse proxy |
| `.env` (your actual config) | ❌ | **Created by Step 1 below** |

Everything you need is already on disk. You do NOT need to write any
new config files — just follow the steps.

---

## Step 0 — Prerequisites

Install these once. None of them are project-specific.

1. **Docker Desktop for Windows** — https://www.docker.com/products/docker-desktop/
   - Launch it after install and wait until the whale icon in the
     system tray says "Docker Desktop is running".
   - Settings → Resources: give it at least **8 GB RAM** (16 GB
     recommended for the ML models).
   - Settings → General: WSL 2 backend should be enabled (default on
     Windows 10/11).

2. **Python 3.11+** — required by `setup.ps1` only to generate a
   strong JWT secret. If you don't have Python, the script falls
   back to a placeholder (you'd need to regenerate the secret later).
   Verify: `python --version`

3. **(Optional) Git** — only if you cloned the repo. You already
   have the source on disk at `E:\CSE400 (Project)\bizvision-master skill`,
   so this is not strictly required.

Sanity check Docker:

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

The third command should print `Hello from Docker!`. If it fails,
fix Docker Desktop before continuing — nothing else in this guide
will work.

---

## Step 1 — Boot the whole stack (one command)

Open PowerShell, navigate to the project root, and run the bootstrap:

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"
./setup.ps1
```

This single command will:

1. Copy `.env.example` → `.env` (if no `.env` exists).
2. Generate a cryptographically strong `JWT_SECRET_KEY` and write it
   into `.env`.
3. Build all Docker images (`docker compose build`) — first build
   takes 5–15 minutes depending on your machine + connection.
4. Start `postgres` and `redis` first.
5. Wait 6 seconds for them to come up.
6. Run database migrations (`alembic upgrade head` — applies
   `0001_initial_schema` through `0006_audit_logs`).
7. Seed development data (`python -m src.utils.seed`).
8. Start the remaining services (`docker compose up -d`).

When it finishes you should see:

```
[OK] Setup complete!

  Frontend:  http://localhost:3000
  Backend:   http://localhost:8000/api/v1/docs
  MLflow:    http://localhost:5000
  MinIO:     http://localhost:9001
  Flower:    http://localhost:5555
```

**Open http://localhost:3000 in a browser. You should see the
BizVision login page.**

---

## Step 2 — Verify it actually works

```powershell
# All 9 containers should show "Up" or "(healthy)"
docker compose ps

# Backend health probe
curl http://localhost:8000/health

# Open the auto-generated API docs in the browser
start http://localhost:8000/api/v1/docs
```

Try the end-to-end flow in the UI:

1. http://localhost:3000 → click **Register**
2. Create an account with any email + a password ≥ 12 chars.
3. You should land on the dashboard with the 5 module tiles.
4. Open **Recruitment** → fill in a tiny analysis (1 job + 2
   candidates) → submit. You should see a ranked list with SHAP
   attributions + a fairness audit.
5. Open **ML Decision Feed** (sidebar) → you should see the audit
   row you just produced with a recruitment_session deep-link.

If all of that works, the stack is fully operational.

---

## Step 3 — Day-to-day lifecycle

After the first bootstrap, you don't need to run `setup.ps1` again.
Use Docker Compose directly (works without `make`):

```powershell
# Start everything (uses existing images + volumes)
docker compose up -d

# Stop everything (keeps data)
docker compose down

# Restart a single service after a code change
docker compose restart backend
docker compose restart frontend

# Tail logs for one service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery-worker

# Tail logs for everything
docker compose logs -f

# Check status of every service
docker compose ps

# Stop the stack AND delete all data (full reset)
# ⚠ This deletes postgres + redis + minio + mlflow + grafana volumes
docker compose down -v
```

---

## Step 4 — Service map

What's running on which port:

| Service | Port | URL | Purpose |
|---|---|---|---|
| **Frontend** | 3000 | http://localhost:3000 | Next.js 14 UI |
| **Backend API** | 8000 | http://localhost:8000/api/v1/docs | FastAPI + OpenAPI |
| **PostgreSQL** | 5432 | (internal) | pgvector-enabled DB |
| **Redis** | 6379 | (internal) | Cache + Celery broker |
| **MLflow** | 5000 | http://localhost:5000 | Experiment tracking |
| **MinIO** | 9000 / 9001 | http://localhost:9001 | S3-compatible storage (admin / `minioadmin` / `minioadmin123`) |
| **Flower** | 5555 | http://localhost:5555 | Celery monitor (admin / `admin` / `admin123`) |
| **Nginx** | 80 / 443 | http://localhost | Reverse proxy (optional) |

Profile-gated services (off by default — start with the profile flag):

```powershell
# Jupyter Lab for ML development
docker compose --profile ml up -d ml-dev
# → http://localhost:8888

# Prometheus + Grafana
docker compose --profile monitoring up -d prometheus grafana
# → Prometheus http://localhost:9090
# → Grafana    http://localhost:3001  (admin / admin123)
```

---

## Step 5 — Common operations

### Open a shell inside a container

```powershell
# Backend (FastAPI process)
docker compose exec backend bash

# Frontend (Next.js process)
docker compose exec frontend sh

# Postgres
docker compose exec postgres psql -U bizvision -d bizvision

# Redis
docker compose exec redis redis-cli
```

### Run tests

```powershell
# Backend tests inside the container
docker compose exec backend pytest tests/ -v

# Frontend tests inside the container
docker compose exec frontend npm test
```

### Re-run migrations / seed

```powershell
# Apply any new migrations
docker compose exec backend alembic upgrade head

# Re-seed (idempotent — safe to repeat)
docker compose exec backend python -m src.utils.seed
```

### Rebuild after a Dockerfile change

```powershell
# Rebuild a single service
docker compose build backend
docker compose up -d backend

# Rebuild everything from scratch (slow)
docker compose build --no-cache
docker compose up -d
```

---

## Step 6 — Troubleshooting

### "port is already allocated" / "address already in use"

Another process holds the port. Find it:

```powershell
# Replace 3000 with whichever port the error mentioned
netstat -ano | findstr :3000
```

The last column is the PID. Kill it (or stop the conflicting app):

```powershell
Stop-Process -Id <PID> -Force
```

Common culprits on Windows:
- Port 5432: a locally-installed Postgres service.
- Port 6379: a local Redis service.
- Port 3000: another Node app running.

### Docker Desktop crashes / WSL out of memory

Edit `%USERPROFILE%\.wslconfig` (create if missing):

```
[wsl2]
memory=12GB
processors=4
swap=4GB
```

Then restart Docker Desktop from the system tray.

### "no matching manifest" / image pull failures

You're probably on an air-gapped network or Docker Desktop lost
auth. Sign in to Docker Hub via Docker Desktop → Settings → and
retry.

### Frontend container restarts forever

Usually a `node_modules` mismatch between host + container. The
compose file mounts `./frontend:/app` but uses an anonymous volume
for `node_modules` to avoid host/container clashes. If something
weird happened:

```powershell
docker compose down
docker compose build frontend --no-cache
docker compose up -d frontend
```

### Backend container restarts: "alembic upgrade head" failed

Postgres wasn't ready when the migration ran. Re-run it manually:

```powershell
docker compose up -d postgres
Start-Sleep -Seconds 8
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

### "JWT_SECRET_KEY=change-this-in-production-32-chars" warning in logs

`setup.ps1` failed to write a real secret (Python not on PATH).
Generate one and edit `.env` manually:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and replace the JWT_SECRET_KEY line in .env
```

Then restart the backend:

```powershell
docker compose restart backend celery-worker
```

### Hard reset — start over

```powershell
docker compose down -v --remove-orphans
Remove-Item .env -ErrorAction SilentlyContinue
./setup.ps1
```

This wipes all data and re-runs the entire bootstrap.

---

## Step 7 — If you want `make` commands to work on Windows

The repo's `Makefile` has nice shortcuts (`make up`, `make logs`,
`make test`, etc.) but Windows doesn't ship with `make`. Two
options:

**Option A (recommended): use the `docker compose` commands
directly** as shown above. The Makefile is just a thin wrapper —
nothing in it is Windows-specific.

**Option B: install GNU Make for Windows** via Chocolatey or Scoop:

```powershell
# Chocolatey
choco install make

# Scoop
scoop install make
```

Then `make help` works as documented in the main README.

---

## Step 8 — Optional: AI API keys for the chatbot

The chatbot's `wave-1` mock works without any external API keys (it
returns a canned response from a small synthetic 100-doc corpus).

For a real Anthropic Claude or OpenAI integration, edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Then restart the backend:

```powershell
docker compose restart backend celery-worker
```

The `CHATBOT_USE_REAL_ML` feature flag in the backend
controls whether real ML inference is invoked; in default
development mode it uses the synthetic responder.

---

## Summary cheat-sheet

```powershell
# First-time
cd "E:\CSE400 (Project)\bizvision-master skill"
./setup.ps1
start http://localhost:3000

# Every day after
docker compose up -d
docker compose ps
docker compose logs -f backend
docker compose down

# Reset
docker compose down -v
./setup.ps1
```

That's it. The platform is designed so a fresh clone → working stack
is one command (`./setup.ps1`); everything else in this guide is
operational detail.
