#!/usr/bin/env bash
# ============================================================
# BizVision AI — One-Command Bootstrap Script
# Compatible with: Linux, macOS, WSL2
#
# Usage: bash setup.sh
# ============================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helpers ───────────────────────────────────────────────────
log()     { echo -e "${CYAN}[BizVision]${NC} $*"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $*${NC}"; }
error()   { echo -e "${RED}❌ $*${NC}"; exit 1; }

# ── Banner ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║          BizVision AI Platform           ║"
echo "  ║     Elite SME Decision Intelligence      ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ── Prerequisites Check ───────────────────────────────────────
log "Checking prerequisites..."

check_command() {
    if ! command -v "$1" &>/dev/null; then
        error "$1 is required but not installed. Please install it first."
    fi
    success "$1 found: $(command -v $1)"
}

check_command docker
check_command "docker compose" 2>/dev/null || check_command "docker-compose"
check_command git

# Docker daemon check
if ! docker info &>/dev/null; then
    error "Docker daemon is not running. Please start Docker Desktop."
fi

# ── Environment Setup ─────────────────────────────────────────
log "Setting up environment configuration..."

if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env file created from .env.example"
    warn "IMPORTANT: Edit .env and add your API keys before proceeding"
    echo ""
    echo "Required (at minimum one for chatbot):"
    echo "  - ANTHROPIC_API_KEY or OPENAI_API_KEY"
    echo ""
    read -p "Press ENTER to continue with defaults (chatbot will use local mode)..."
else
    success ".env file already exists"
fi

# Generate secure JWT secret if using default
if grep -q "change-this-in-production" .env; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || \
                 openssl rand -hex 32)
    sed -i "s/change-this-to-a-random-64-char-secret-in-production/$JWT_SECRET/" .env
    success "JWT secret generated and saved"
fi

# ── Docker Build ──────────────────────────────────────────────
log "Building Docker images (this may take 5-10 minutes on first run)..."
docker compose build

success "Docker images built"

# ── Start Core Services ───────────────────────────────────────
log "Starting core services (PostgreSQL, Redis, MinIO)..."
docker compose up -d postgres redis minio

log "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U bizvision -q 2>/dev/null; then
        success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        error "PostgreSQL failed to start after 30 attempts"
    fi
    echo -n "."
    sleep 2
done

# ── Database Migrations ───────────────────────────────────────
log "Running database migrations..."
docker compose run --rm backend alembic upgrade head
success "Migrations complete"

# ── Seed Data ─────────────────────────────────────────────────
log "Seeding development data..."
docker compose run --rm backend python -m src.utils.seed
success "Seed data loaded"

# ── MLflow Setup ──────────────────────────────────────────────
log "Starting MLflow tracking server..."
docker compose up -d mlflow
sleep 5

# Create MLflow experiments
log "Creating MLflow experiments..."
docker compose run --rm backend python -c "
from ml.shared.utils.mlflow_utils import get_or_create_experiment
experiments = [
    'recruitment-intelligence',
    'smart-pricing',
    'profit-forecasting',
    'esg-sustainability',
    'chatbot-rag',
]
for exp in experiments:
    get_or_create_experiment(exp)
    print(f'  Created: {exp}')
"
success "MLflow experiments created"

# ── Start All Services ────────────────────────────────────────
log "Starting all services..."
docker compose up -d

log "Waiting for all services to be healthy..."
sleep 10

# Health checks
check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" &>/dev/null; then
        success "$name: $url"
    else
        warn "$name: $url (may still be starting)"
    fi
}

check_service "Frontend"  "http://localhost:3000"
check_service "Backend"   "http://localhost:8000/health"
check_service "MLflow"    "http://localhost:5000/health"
check_service "MinIO"     "http://localhost:9001"
check_service "Flower"    "http://localhost:5555"

# ── Complete ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   BizVision AI is ready!  🚀           ║${NC}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Access Points:${NC}"
echo "  🌐 Frontend:    http://localhost:3000"
echo "  📡 API Docs:    http://localhost:8000/api/v1/docs"
echo "  🔬 MLflow:      http://localhost:5000"
echo "  💾 MinIO:       http://localhost:9001  (admin/minioadmin123)"
echo "  🌸 Flower:      http://localhost:5555  (admin/admin123)"
echo ""
echo -e "${CYAN}Quick Commands:${NC}"
echo "  make up            Start all services"
echo "  make down          Stop all services"
echo "  make logs          Follow all logs"
echo "  make train-all     Train all ML models"
echo "  make test          Run test suite"
echo "  make help          Show all commands"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Open http://localhost:3000 and create an account"
echo "  2. Run 'make generate-data' to create synthetic training data"
echo "  3. Run 'make train-all' to train all ML models"
echo "  4. Explore the AI modules!"
echo ""
