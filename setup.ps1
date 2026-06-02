<#
.SYNOPSIS
    BizVision AI — one-command bootstrap (Windows / PowerShell).
.DESCRIPTION
    Mirrors setup.sh for Windows. Copies .env, generates a JWT secret,
    builds Docker images, starts infra, runs migrations, and seeds data.
.EXAMPLE
    ./setup.ps1            # full Docker bootstrap
    ./setup.ps1 -NoDocker  # local dev setup only (venv + npm install)
#>
[CmdletBinding()]
param(
    [switch]$NoDocker
)

$ErrorActionPreference = "Stop"
function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }

Write-Host "BizVision AI - Bootstrap" -ForegroundColor Magenta

# ── 1. Environment file ─────────────────────────────────────
Write-Step "Configuring environment (.env)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    $secret = python -c "import secrets; print(secrets.token_hex(32))"
    (Get-Content ".env") -replace 'JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$secret" |
        Set-Content ".env" -Encoding utf8
    Write-Ok ".env created with a generated JWT secret"
} else {
    Write-Warn ".env already exists - leaving it untouched"
}

if ($NoDocker) {
    # ── Local backend venv ──────────────────────────────────
    Write-Step "Creating backend virtual environment"
    Push-Location backend
    if (-not (Test-Path ".venv")) { python -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    Write-Ok "Backend dev environment ready (.\backend\.venv)"
    Pop-Location

    # ── Frontend deps ───────────────────────────────────────
    Write-Step "Installing frontend dependencies"
    npm install
    Write-Ok "Frontend dependencies installed"

    Write-Host "`nLocal dev setup complete." -ForegroundColor Green
    Write-Host "  Backend:  cd backend; .\.venv\Scripts\activate; uvicorn src.main:app --reload"
    Write-Host "  Frontend: npm run dev --workspace frontend"
    exit 0
}

# ── Docker bootstrap ────────────────────────────────────────
Write-Step "Building Docker images"
docker compose build

Write-Step "Starting core infrastructure (postgres, redis)"
docker compose up -d postgres redis
Start-Sleep -Seconds 6

Write-Step "Running database migrations"
docker compose run --rm backend alembic upgrade head

Write-Step "Seeding development data"
docker compose run --rm backend python -m src.utils.seed

Write-Step "Starting all services"
docker compose up -d

Write-Ok "Setup complete!"
Write-Host @"

  Frontend:  http://localhost:3000
  Backend:   http://localhost:8000/api/v1/docs
  MLflow:    http://localhost:5000
  MinIO:     http://localhost:9001
  Flower:    http://localhost:5555

"@ -ForegroundColor Green
