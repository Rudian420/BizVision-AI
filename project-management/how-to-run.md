# How to Run BizVision AI Locally (Windows + Docker)

> **Audience**: someone with a fresh clone of this repo on a Windows
> machine, who has never run it before.
>
> **Result**: all 9 services running in Docker, the platform
> accessible at http://localhost:3000.
>
> **Time**: 15–30 minutes on the first run (most of it is Docker
> pulling base images and building two project images). 30 seconds
> per subsequent start.

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [The happy path (5 commands)](#the-happy-path-5-commands)
3. [What each step does](#what-each-step-does)
4. [Service map](#service-map)
5. [Day-to-day lifecycle](#day-to-day-lifecycle)
6. [Troubleshooting — every error we hit, and the fix](#troubleshooting--every-error-we-hit-and-the-fix)
7. [The 3 patches the project needed for Docker to build](#the-3-patches-the-project-needed-for-docker-to-build)
8. [Hard reset](#hard-reset)
9. [FAQ](#faq)

---

## Prerequisites

Install these once.

### 1. Docker Desktop for Windows

- Download: https://www.docker.com/products/docker-desktop/
- Install → reboot when prompted.
- Launch Docker Desktop from the Start menu. **Wait until the
  bottom-left status bar says "Engine running"** (the whale icon
  in the system tray stops animating). First launch takes 30–90 s.
- Settings → Resources → give it **at least 8 GB RAM** (16 GB
  recommended for ML).
- If Docker asks about WSL 2 features during install, say yes.

### 2. (Optional) Python 3.11+

Only needed by `setup.ps1` to generate a strong JWT secret. Without
Python the script still works but uses a placeholder secret.

Verify: `python --version`

### 3. Sanity check Docker is alive

Open a **fresh** PowerShell:

```powershell
docker --version          # must print "Docker version 27.x"
docker compose version    # must print "Docker Compose version v2.x"
docker run --rm hello-world
```

The third command should print "Hello from Docker!". If it doesn't,
fix Docker first — nothing else in this guide will work.

> **If `docker` is "not recognized"** even after Docker Desktop is
> running: it installed but didn't put itself on PATH. See
> [Issue 2 in Troubleshooting](#issue-2--docker-is-not-recognized).

---

## The happy path (5 commands)

In a fresh PowerShell window:

```powershell
# 1. Navigate to the project root
cd "E:\CSE400 (Project)\bizvision-master skill"

# 2. (only if not already on PATH) make docker visible to this session
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"

# 3. Run the bootstrap (handles .env creation, JWT secret, infra start, migrations)
.\setup.ps1

# 4. Verify all 9 services are up
docker compose ps

# 5. Open the platform
start http://localhost:3000
```

If step 3 dies partway through, jump to
[Troubleshooting](#troubleshooting--every-error-we-hit-and-the-fix).

---

## What each step does

### `setup.ps1`

1. Copies `.env.example` → `.env` (skipped if `.env` already exists).
2. Generates a strong `JWT_SECRET_KEY` and writes it into `.env`.
3. Runs `docker compose build` for all services.
4. Starts `postgres` + `redis` first and waits 6 seconds for them
   to be healthy.
5. Runs `alembic upgrade head` (applies migrations `0001` → `0006`).
6. Seeds development data (`python -m src.utils.seed`).
7. Starts the remaining services with `docker compose up -d`.

When it finishes, you see:

```
[OK] Setup complete!
  Frontend:  http://localhost:3000
  Backend:   http://localhost:8000/api/v1/docs
  MLflow:    http://localhost:5000
  MinIO:     http://localhost:9001
  Flower:    http://localhost:5555
```

### "INITIALISING NEURAL CORE…" loader on first page load

**This is normal — wait 30–90 seconds.** Two things happen
together:

- **Next.js dev server compiles the route on first hit.** Inside the
  container, Next compiles every page on-demand. The landing page
  imports React Three Fiber + Three.js + GSAP, so its first compile
  is 20–40 s.
- **Browser initialises the WebGL scene.** Shader compilation +
  texture load. Another 10–30 s the first time.

Both are one-time. Subsequent page loads are sub-second.

You can watch the compile in real time:

```powershell
docker compose logs -f frontend
```

When you see `✓ Compiled / in X.Xs`, the page is ready. `Ctrl+C` to
stop tailing (the container keeps running).

If you don't want to wait for the 3D landing, go straight to
`http://localhost:3000/login` — no 3D scene there.

---

## Service map

| Service | Port | URL | Default credentials | Purpose |
|---|---|---|---|---|
| **Frontend** | 3000 | http://localhost:3000 | — | Next.js 14 UI |
| **Backend API** | 8000 | http://localhost:8000/api/v1/docs | — | FastAPI + auto-generated OpenAPI |
| **PostgreSQL** | 5432 | (internal) | `bizvision` / `bizvision123` | pgvector-enabled DB |
| **Redis** | 6379 | (internal) | — | Cache + Celery broker |
| **MLflow** | 5000 | http://localhost:5000 | — | Experiment tracking |
| **MinIO** | 9000 / 9001 | http://localhost:9001 | `minioadmin` / `minioadmin123` | S3-compatible storage |
| **Flower** | 5555 | http://localhost:5555 | `admin` / `admin123` | Celery monitor |
| **Nginx** | 80 / 443 | http://localhost | — | Reverse proxy (optional) |

Profile-gated services (off by default):

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

## Day-to-day lifecycle

After the first successful bootstrap, you don't need `setup.ps1`
again. Use `docker compose` directly:

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"

# Start everything (uses existing built images + volumes)
docker compose up -d

# Stop everything (keeps data)
docker compose down

# Restart a single service after a code change
docker compose restart backend
docker compose restart frontend

# Tail logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery-worker

# Status of every service
docker compose ps

# Rebuild a single service after Dockerfile changes
docker compose build backend
docker compose up -d backend
```

---

## Troubleshooting — every error we hit, and the fix

These are the **actual errors** we encountered during a real Windows
setup. They're listed in the order you're likely to hit them.

### Issue 1 — `./setup.ps1 : The term './setup.ps1' is not recognized`

**Why**: You're not in the project directory. The prompt shows
`PS E:\CSE400 (Project)>` — but the project lives in the
`bizvision-master skill` subfolder.

**Fix**:

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"
dir setup.ps1      # should now find the file
.\setup.ps1        # use .\ (back-slash) — PowerShell native form
```

### Issue 2 — "docker is not recognized"

**Why**: Docker Desktop is installed but not on PowerShell's PATH.
Confirmed by:

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' |
  Where-Object { $_.DisplayName -like '*Docker*' } |
  Select-Object DisplayName, DisplayVersion, InstallLocation
```

If that prints `Docker Desktop`, it's installed but PATH is stale.

**Fix — for the current PowerShell session (instant)**:

```powershell
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"
docker --version
```

**Fix — permanent (one-time)**:

```powershell
[Environment]::SetEnvironmentVariable(
  'Path',
  ([Environment]::GetEnvironmentVariable('Path','User') + ';C:\Program Files\Docker\Docker\resources\bin'),
  'User'
)
```

New PowerShell windows will see Docker automatically. (The current
window won't show the change — already fixed via the first command.)

Also make sure Docker Desktop is actually launched and the bottom-
left says **"Engine running"** before you proceed.

### Issue 3 — `failed to compute cache key: "/pyproject.toml": not found`

**Full error**:

```
[backend base 5/6] COPY pyproject.toml ./
ERROR: failed to calculate checksum of ref ...: "/pyproject.toml": not found
target celery-worker: failed to solve: failed to compute cache key
```

**Why**: The backend `Dockerfile` had `COPY pyproject.toml ./`, but
`pyproject.toml` lives at the **monorepo root** (not in `backend/`),
and the docker-compose build context for backend is `./backend`. The
file isn't visible inside the build.

**Fix** — already applied in this repo. If it ever comes back:

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"
(Get-Content backend\Dockerfile) | Where-Object { $_ -notmatch 'COPY pyproject\.toml' } | Set-Content backend\Dockerfile -Encoding utf8

# Verify (should print nothing now)
Select-String -Path backend\Dockerfile -Pattern 'pyproject'
```

The backend doesn't actually need the root `pyproject.toml` to build
— it installs from `requirements.txt` (which IS in `backend/`).

### Issue 4 — `npm error EUSAGE: npm ci requires package-lock.json`

**Full error**:

```
[frontend deps 1/1] RUN npm ci
npm error code EUSAGE
npm error The `npm ci` command can only install with an existing
npm error package-lock.json or npm-shrinkwrap.json with lockfileVersion >= 1
target frontend: failed to solve: process "/bin/sh -c npm ci" did not complete successfully
```

**Why**: This is an **npm workspaces monorepo**. The `package-lock.json`
lives at the monorepo root, not in `frontend/`. The frontend
Dockerfile only had access to `frontend/` (via the old build
context), so it couldn't see the lock file.

**Initial fix** — changed `npm ci` to `npm install`:

```powershell
(Get-Content frontend\Dockerfile) -replace 'RUN npm ci', 'RUN npm install --no-audit --no-fund' | Set-Content frontend\Dockerfile -Encoding utf8
```

…which led directly to:

### Issue 5 — `ERESOLVE: peer dep three@">= 0.168.0" conflicts with three@0.165.0`

**Full error**:

```
npm error code ERESOLVE
npm error ERESOLVE unable to resolve dependency tree
npm error Found: three@0.165.0
npm error Could not resolve dependency:
npm error peer three@">= 0.168.0 < 0.185.0" from postprocessing@6.39.1
```

**Why**: npm 7+ enforces peer-dep ranges by default. `postprocessing`
wants `three >= 0.168` but `package.json` pins `three@^0.165.0`.

**Fix** — add `--legacy-peer-deps` to `npm install`:

```powershell
(Get-Content frontend\Dockerfile) -replace 'RUN npm install --no-audit --no-fund', 'RUN npm install --no-audit --no-fund --legacy-peer-deps' | Set-Content frontend\Dockerfile -Encoding utf8
```

…which led directly to:

### Issue 6 — Workspace dep `@bizvision/contracts` not resolvable

**Symptom**: `npm install --legacy-peer-deps` still failed because
`frontend/package.json` declares `"@bizvision/contracts": "*"` as a
dependency. That package is a **monorepo workspace** at
`packages/contracts/`, which is not visible inside a build context
scoped to `./frontend/`.

**Fix — the real one** (Option A in the chat transcript):

1. **Change the build context to the monorepo root.** Edit
   `docker-compose.yml`'s `frontend:` block:

   ```yaml
   frontend:
     build:
       context: .                       # was: ./frontend
       dockerfile: frontend/Dockerfile  # was: Dockerfile
       target: ${NODE_ENV:-development}
     ...
     working_dir: /app/frontend         # NEW
     volumes:
       - .:/app                         # was: ./frontend:/app
       - /app/node_modules
       - /app/frontend/.next            # was: /app/.next
   ```

2. **Rewrite `frontend/Dockerfile`** to copy workspace manifests
   first so `npm install` can plan the tree:

   ```dockerfile
   FROM node:20-alpine AS base
   RUN apk add --no-cache libc6-compat curl
   WORKDIR /app

   # Workspace manifests
   COPY package.json package-lock.json* ./
   COPY frontend/package.json ./frontend/
   COPY packages/ ./packages/

   FROM base AS deps
   RUN npm install --no-audit --no-fund --legacy-peer-deps

   FROM base AS development
   COPY --from=deps /app/node_modules ./node_modules
   COPY . .
   ENV NODE_ENV=development
   WORKDIR /app/frontend
   CMD ["npm", "run", "dev"]
   # (builder + production stages similar — see frontend/Dockerfile)
   ```

3. Clean rebuild:

   ```powershell
   docker compose build --no-cache frontend
   docker compose up -d
   ```

**Both of these are already applied in this repo.** If you ever need
to redo them, see [the 3 patches section](#the-3-patches-the-project-needed-for-docker-to-build).

### Issue 7 — Frontend container is up but `localhost:3000` shows "INITIALISING NEURAL CORE…" forever

This is **not an error** if you've waited less than ~90 seconds.
See [What each step does → the loader explanation](#initialising-neural-core-loader-on-first-page-load).

If it's stuck for **more than 3 minutes**:

```powershell
docker compose logs frontend --tail=30
```

Look for:
- `✓ Compiled /` → page is actually ready, the browser is stuck.
  Hard-refresh (Ctrl + Shift + R) or open DevTools (F12) → Network
  tab → "Disable cache".
- An actual Next.js error trace → paste it for a fix.

Workaround: `http://localhost:3000/login` skips the 3D scene
entirely.

### Issue 8 — `port is already allocated`

Another process holds one of the ports the stack needs.

```powershell
# Replace 3000 with whichever port the error mentioned
netstat -ano | findstr :3000
```

The last column is the PID. Kill it (or stop the conflicting app):

```powershell
Stop-Process -Id <PID> -Force
```

Common culprits on Windows:
- Port 5432: a locally-installed PostgreSQL service.
- Port 6379: a local Redis service.
- Port 3000: another Node app already running.

### Issue 9 — JWT secret is the placeholder

```powershell
Get-Content .env | Select-String JWT_SECRET_KEY
```

If it prints `JWT_SECRET_KEY=change-this-in-production-32-chars`,
generate a real one:

```powershell
$secret = python -c "import secrets; print(secrets.token_hex(32))"
(Get-Content .env) -replace 'JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$secret" | Set-Content .env -Encoding utf8
docker compose restart backend celery-worker
```

(Non-blocking in dev — the platform runs with the placeholder; just
don't ship to production with it.)

### Issue 10 — `error during connect: ... The system cannot find the file specified`

Docker Desktop quit (or never started). Restart it from the system
tray (or `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`)
and wait for the bottom-left status to say **"Engine running"**.

---

## The 3 patches the project needed for Docker to build

This section documents what was changed in this repo to make the
Docker build work on Windows. **They are already applied.** If you
ever lose them (rebase, fresh clone of an older revision, etc.),
this is how to re-apply them.

### Patch 1 — `backend/Dockerfile`: drop the `COPY pyproject.toml` line

```diff
- COPY pyproject.toml ./
  COPY requirements.txt ./
```

The root `pyproject.toml` is not in the backend build context. The
backend installs from `requirements.txt` anyway.

### Patch 2 — `frontend/Dockerfile`: rewrite for monorepo context

The new version:

```dockerfile
FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat curl
WORKDIR /app

COPY package.json package-lock.json* ./
COPY frontend/package.json ./frontend/
COPY packages/ ./packages/

FROM base AS deps
RUN npm install --no-audit --no-fund --legacy-peer-deps

FROM base AS development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=development
WORKDIR /app/frontend
CMD ["npm", "run", "dev"]

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NODE_ENV=production
WORKDIR /app/frontend
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --gid 1001 --system nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
```

Three things matter:
- `COPY package.json package-lock.json* ./` — root manifests.
- `COPY frontend/package.json ./frontend/` — workspace manifest.
- `COPY packages/ ./packages/` — workspace packages
  (`@bizvision/contracts`).
- `--legacy-peer-deps` — bypasses `three` vs `postprocessing` peer
  conflict.

### Patch 3 — `docker-compose.yml`: change the frontend's build context + volumes

```yaml
frontend:
  build:
    context: .                             # was: ./frontend
    dockerfile: frontend/Dockerfile        # was: Dockerfile
    target: ${NODE_ENV:-development}
  ...
  working_dir: /app/frontend               # NEW
  volumes:
    - .:/app                               # was: ./frontend:/app
    - /app/node_modules
    - /app/frontend/.next                  # was: /app/.next
```

The build context must be the monorepo root so npm can see workspace
packages. The bind mount points the same root at `/app` for hot
reload. The anonymous volumes on `/app/node_modules` and
`/app/frontend/.next` shield those folders from being clobbered
by the bind mount.

---

## Hard reset

If something has gone irrecoverably wrong and you want to start
over:

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"

# Stop everything AND delete all volumes (postgres data, redis,
# minio, mlflow, grafana)
docker compose down -v --remove-orphans

# (Optional) delete .env so setup.ps1 regenerates it
Remove-Item .env -ErrorAction SilentlyContinue

# (Optional) remove the build cache (rare — only if Dockerfile
# layers are corrupted)
docker builder prune -a -f

# Re-bootstrap from scratch
.\setup.ps1
```

This wipes all data and re-runs the entire bootstrap.

---

## FAQ

### Q. Do I have to use `setup.ps1`? Can I run `docker compose` directly?

Yes. `setup.ps1` is a one-shot bootstrap. After the first successful
run you can do everything with raw `docker compose`:

```powershell
docker compose up -d         # start
docker compose ps            # status
docker compose down          # stop
```

### Q. The `version: '3.9'` warning at the top of every compose command

```
the attribute `version` is obsolete, it will be ignored, please remove it
```

Harmless. Modern Docker Compose v2 ignores the field. Cosmetic only.
You can delete the first two lines of `docker-compose.yml` if it
bothers you (`version: '3.9'` + the comment above it).

### Q. Do I need `make` to work on Windows?

No. The `Makefile` is just a wrapper around `docker compose`
commands. Everything in the Makefile has a direct
`docker compose ...` equivalent shown in this guide. If you want
`make` for convenience:

```powershell
choco install make    # or: scoop install make
```

### Q. The chatbot — do I need an Anthropic / OpenAI API key?

No, not in development. The chatbot ships with a synthetic
100-document RAG corpus and a mock responder. It returns canned
answers but the persistence layer + WS streaming + UI all work
end-to-end.

For a real Claude or OpenAI integration:

```powershell
notepad .env
# Add or replace:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
docker compose restart backend celery-worker
```

The `CHATBOT_USE_REAL_ML` flag in the backend gates whether real ML
is invoked. Default = mock.

### Q. How long should the first run take?

| Phase | Time | What's happening |
|---|---|---|
| Pull base images | 2–5 min | postgres+pgvector, redis, node:20-alpine, python:3.11-slim, mlflow, minio |
| Build backend / celery / frontend images | 5–10 min | apt-get + pip install + npm install (~1000 packages) |
| Start services | 30–60 s | Container init, healthchecks |
| First page load | 30–90 s | Next.js compiles routes on demand + WebGL scene init |
| **Total** | **8–17 min** | First run only |

Subsequent `docker compose up -d` = **15–30 seconds**.

### Q. How do I make a fresh user / test the platform?

1. Open http://localhost:3000.
2. Wait for the "INITIALISING NEURAL CORE…" loader to finish
   (30–90 s on first load).
3. Click **Register** → enter any email + a ≥12-char password.
4. You land on the dashboard with the 5 module tiles.
5. Click **Recruitment Intelligence** → fill the analyze form with
   any job description + 2-3 candidates → submit. You'll see a
   ranked list + SHAP attributions + fairness audit.
6. Open the sidebar's **ML Decision Feed** → you should see the
   audit row you just produced, with a clickable
   `recruitment_session` deep-link in the footer.

If all of that works, the stack is fully operational.

### Q. What's the difference between `.env` and `.env.example`?

| File | What it is | Edit it? |
|---|---|---|
| `.env` | Your real, local config. Docker Compose reads it. | Yes |
| `.env.example` | Template + docs for humans. Committed to git. | No |

`setup.ps1` copies `.env.example` → `.env` on first run.

### Q. Where do I look in the running stack?

| Symptom | Where |
|---|---|
| Frontend won't load | `docker compose logs frontend --tail=50` |
| API errors | `docker compose logs backend --tail=50` + http://localhost:8000/api/v1/docs |
| ML / Celery slow | http://localhost:5555 (Flower) |
| DB inspection | `docker compose exec postgres psql -U bizvision -d bizvision` |
| Object storage | http://localhost:9001 (MinIO console) |
| Experiment tracking | http://localhost:5000 (MLflow) |
| Anything misbehaving | Docker Desktop's Logs view (whale icon → Logs) |

---

## Cheat sheet (printable)

```powershell
# First-time
cd "E:\CSE400 (Project)\bizvision-master skill"
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"  # if docker not on PATH
.\setup.ps1
start http://localhost:3000

# Every day after
docker compose up -d
docker compose ps
docker compose logs -f backend
docker compose down

# Reset
docker compose down -v
.\setup.ps1
```

That's it. If something not covered here breaks, capture
`docker compose ps` + `docker compose logs <service> --tail=50`
and the error is almost always in those two outputs.

---

## TASK-041 verification (Recruitment SBERT pre-warm)

Code for TASK-041 (HF cache volume + lifespan pre-warm hook +
`RECRUITMENT_USE_REAL_ML=true`) was landed without Docker running,
so the first time you bring the stack up after this change, follow
these steps to confirm everything works.

### 1. Bring up a clean backend

```powershell
cd "E:\CSE400 (Project)\bizvision-master skill"
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"

docker compose up -d --force-recreate backend
```

### 2. Watch the lifespan pre-warm fire

```powershell
docker compose logs -f backend
```

You should see, immediately after `Application startup complete`:

```text
Scheduled 4 ML pre-warm task(s) in background
```

Then, over the next ~10 minutes (most of it is the one-time MPNet
download), each module's warmup will log its result:

```text
Pre-warm OK: pricing ready in 178.2s
Pre-warm OK: forecasting ready in 88.7s
Pre-warm OK: sustainability ready in 81.3s
Pre-warm OK: recruitment-sbert ready in 296.4s     ← first ever; subsequent restarts ~60s
```

If a warmup *fails*, the lifespan still completes (errors are
caught + logged), so the server stays healthy — only that one
module's first real request will pay the cold-train cost.

### 3. Confirm the HuggingFace cache is persisted

```powershell
docker compose exec backend ls -lh /root/.cache/huggingface/hub
```

You should see `models--sentence-transformers--all-mpnet-base-v2`
weighing in around 420 MB. From now on, every container recreate
will reuse this — the recruitment warmup will drop from ~5 min to
~1 min.

### 4. Fire a real recruitment ranking

```powershell
# Grab a token (replace email/password with your real account or
# the bench user created in TASK-040)
$body = @{ username = 'mlbench@bizvision.example.com'; password = 'BenchPass2026!' }
$resp = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login `
  -Method POST -Body $body -ContentType 'application/x-www-form-urlencoded'
$token = $resp.tokens.access_token

# Fire a 5-candidate analysis. With the pre-warm done, this should
# return in well under 1 second.
$payload = @'
{
  "job_description": {
    "title": "Senior Python Backend Engineer",
    "description": "FastAPI, async I/O, PostgreSQL, Redis, Docker. ML pipelines a plus.",
    "required_skills": ["python","fastapi","postgresql","async","docker"],
    "experience_level": "senior",
    "min_years_experience": 5
  },
  "candidates": [
    {"candidate_id":"C-001","cv_text":"Senior engineer, 8 yrs Python, 4 yrs FastAPI async, ML inference at scale on PostgreSQL+Redis, Docker, AWS."},
    {"candidate_id":"C-002","cv_text":"Frontend specialist, 6 yrs React/Next/Three.js, limited backend."},
    {"candidate_id":"C-003","cv_text":"Data engineer, 7 yrs Python/Airflow/dbt, some FastAPI, strong SQL."},
    {"candidate_id":"C-004","cv_text":"Junior dev, 2 yrs Django+SQL, FastAPI bootcamp recent, no production async yet."},
    {"candidate_id":"C-005","cv_text":"Staff engineer, 12 yrs Python+Go, led FastAPI microservices migration, PostgreSQL replication architect."}
  ],
  "anonymize_names": true,
  "top_k": 5
}
'@
Invoke-RestMethod -Uri http://localhost:8000/api/v1/recruitment/analyze `
  -Method POST -Body $payload -ContentType 'application/json' `
  -Headers @{ Authorization = "Bearer $token" } | ConvertTo-Json -Depth 6
```

Expected behaviour (real SBERT path):

- The top-ranked candidate is `C-005` (staff engineer) or `C-001` (senior FastAPI engineer), NOT a keyword-match fluke.
- `composite_score` values are continuous floats (e.g. `0.7421`) reflecting cosine similarity between the JD embedding and each CV embedding — not the 6 discrete bins the mock returned.
- `model_version` will identify the ensemble (e.g. `recruitment-sbert-ensemble-bootstrap`).

### 5. If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `Pre-warm FAILED for recruitment-sbert` with `ConnectionError` / `OSError` to huggingface.co | No internet, or HF rate-limiting | Wait, or fall back: edit `docker-compose.yml` → `RECRUITMENT_USE_REAL_ML=false`, restart. |
| Pre-warm log never appears at all | Lifespan failed earlier | `docker compose logs backend --tail 200`; look for stack traces above the `Application startup` line. |
| `/recruitment/analyze` returns 500 after pre-warm logged OK | Inference-time issue (translator, schema) | `docker compose logs backend --tail 100` immediately after the failing request; the traceback names the field. |
| Recruitment warmup is fast but ranking quality is poor | MPNet didn't actually load — XGBoost-only fallback | `docker compose exec backend ls /root/.cache/huggingface/hub` — directory should be non-empty. |
