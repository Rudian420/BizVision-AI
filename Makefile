# ============================================================
# BizVision AI — Developer Makefile
# Run `make help` to see all available commands
# ============================================================

.PHONY: help setup up down restart logs clean \
        backend-dev frontend-dev ml-dev \
        migrate seed test lint format \
        build deploy status

# ─── Colors ────────────────────────────────────────────────
CYAN    := \033[0;36m
GREEN   := \033[0;32m
YELLOW  := \033[0;33m
RED     := \033[0;31m
RESET   := \033[0m
BOLD    := \033[1m

# ─── Configuration ─────────────────────────────────────────
COMPOSE := docker compose
BACKEND := $(COMPOSE) exec backend
FRONTEND:= $(COMPOSE) exec frontend
PYTHON  := $(BACKEND) python
ALEMBIC := $(BACKEND) alembic

# ────────────────────────────────────────────────────────────
# HELP
# ────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "$(BOLD)$(CYAN)🧠 BizVision AI — Developer Commands$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-25s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ────────────────────────────────────────────────────────────
# SETUP & LIFECYCLE
# ────────────────────────────────────────────────────────────
setup: ## First-time setup: copy .env, build images, run migrations
	@echo "$(CYAN)🚀 Setting up BizVision AI...$(RESET)"
	@[ -f .env ] || (cp .env.example .env && echo "$(YELLOW)⚠  .env created from .env.example — review and edit it$(RESET)")
	@$(COMPOSE) build
	@$(COMPOSE) up -d postgres redis
	@sleep 5
	@$(MAKE) migrate
	@$(MAKE) seed
	@echo "$(GREEN)✅ Setup complete! Run 'make up' to start all services.$(RESET)"

up: ## Start all services
	@echo "$(CYAN)⬆  Starting BizVision AI...$(RESET)"
	@$(COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)✅ All services running:$(RESET)"
	@echo "  Frontend:  http://localhost:3000"
	@echo "  Backend:   http://localhost:8000/api/v1/docs"
	@echo "  MLflow:    http://localhost:5000"
	@echo "  MinIO:     http://localhost:9001"
	@echo "  Flower:    http://localhost:5555"
	@echo ""

down: ## Stop all services
	@echo "$(RED)⬇  Stopping BizVision AI...$(RESET)"
	@$(COMPOSE) down

restart: down up ## Restart all services

restart-backend: ## Restart only the backend service
	@$(COMPOSE) restart backend celery-worker celery-beat

restart-frontend: ## Restart only the frontend service
	@$(COMPOSE) restart frontend

logs: ## Follow logs for all services
	@$(COMPOSE) logs -f

logs-backend: ## Follow backend logs
	@$(COMPOSE) logs -f backend

logs-frontend: ## Follow frontend logs
	@$(COMPOSE) logs -f frontend

logs-celery: ## Follow Celery worker logs
	@$(COMPOSE) logs -f celery-worker

status: ## Show service status
	@$(COMPOSE) ps

# ────────────────────────────────────────────────────────────
# DEVELOPMENT
# ────────────────────────────────────────────────────────────
backend-dev: ## Run backend in dev mode (outside Docker, with hot reload)
	@echo "$(CYAN)🔧 Starting backend in dev mode...$(RESET)"
	@cd backend && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev: ## Run frontend in dev mode (outside Docker)
	@echo "$(CYAN)🔧 Starting frontend in dev mode...$(RESET)"
	@cd frontend && npm run dev

ml-notebook: ## Launch Jupyter notebook server for ML development
	@echo "$(CYAN)📓 Starting Jupyter...$(RESET)"
	@$(COMPOSE) exec ml-dev jupyter lab --ip=0.0.0.0 --port=8888 --no-browser

shell-backend: ## Open shell in backend container
	@$(COMPOSE) exec backend bash

shell-frontend: ## Open shell in frontend container
	@$(COMPOSE) exec frontend sh

shell-db: ## Open psql session
	@$(COMPOSE) exec postgres psql -U bizvision -d bizvision

shell-redis: ## Open redis-cli session
	@$(COMPOSE) exec redis redis-cli

# ────────────────────────────────────────────────────────────
# DATABASE
# ────────────────────────────────────────────────────────────
migrate: ## Run all pending database migrations
	@echo "$(CYAN)🗄  Running migrations...$(RESET)"
	@$(ALEMBIC) upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create NAME="add user table")
	@$(ALEMBIC) revision --autogenerate -m "$(NAME)"

migrate-rollback: ## Rollback last migration
	@$(ALEMBIC) downgrade -1

migrate-history: ## Show migration history
	@$(ALEMBIC) history --verbose

seed: ## Seed database with development data
	@echo "$(CYAN)🌱 Seeding database...$(RESET)"
	@$(PYTHON) -m src.utils.seed

reset-db: ## ⚠ Destroy and recreate database (DESTRUCTIVE)
	@echo "$(RED)⚠  DESTRUCTIVE: This will delete all data!$(RESET)"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	@$(COMPOSE) exec postgres psql -U bizvision -c "DROP DATABASE IF EXISTS bizvision;"
	@$(COMPOSE) exec postgres psql -U bizvision -c "CREATE DATABASE bizvision;"
	@$(MAKE) migrate
	@$(MAKE) seed

# ────────────────────────────────────────────────────────────
# TESTING
# ────────────────────────────────────────────────────────────
test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	@echo "$(CYAN)🧪 Running backend tests...$(RESET)"
	@$(BACKEND) pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

test-frontend: ## Run frontend tests
	@echo "$(CYAN)🧪 Running frontend tests...$(RESET)"
	@$(FRONTEND) npm run test

test-ml: ## Run ML pipeline tests
	@echo "$(CYAN)🧪 Running ML tests...$(RESET)"
	@$(COMPOSE) exec ml-dev pytest ml/ -v --tb=short

test-e2e: ## Run end-to-end tests (Playwright)
	@echo "$(CYAN)🧪 Running E2E tests...$(RESET)"
	@$(FRONTEND) npm run test:e2e

test-watch: ## Run backend tests in watch mode
	@$(BACKEND) pytest tests/ -v --tb=short -f

# ────────────────────────────────────────────────────────────
# CODE QUALITY
# ────────────────────────────────────────────────────────────
lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint Python code (ruff + mypy)
	@echo "$(CYAN)🔍 Linting backend...$(RESET)"
	@$(BACKEND) ruff check src/ tests/
	@$(BACKEND) mypy src/ --ignore-missing-imports

lint-frontend: ## Lint TypeScript code (ESLint + tsc)
	@echo "$(CYAN)🔍 Linting frontend...$(RESET)"
	@$(FRONTEND) npm run lint
	@$(FRONTEND) npm run type-check

format: format-backend format-frontend ## Format all code

format-backend: ## Format Python code (ruff + black)
	@echo "$(CYAN)✨ Formatting backend...$(RESET)"
	@$(BACKEND) ruff format src/ tests/
	@$(BACKEND) ruff check --fix src/ tests/

format-frontend: ## Format TypeScript code (prettier)
	@echo "$(CYAN)✨ Formatting frontend...$(RESET)"
	@$(FRONTEND) npm run format

# ────────────────────────────────────────────────────────────
# ML OPERATIONS
# ────────────────────────────────────────────────────────────
train-recruitment: ## Train recruitment intelligence models
	@echo "$(CYAN)🤖 Training recruitment models...$(RESET)"
	@$(PYTHON) -m ml.recruitment.pipelines.train

train-pricing: ## Train smart pricing models
	@echo "$(CYAN)🤖 Training pricing models...$(RESET)"
	@$(PYTHON) -m ml.pricing.pipelines.train

train-forecasting: ## Train profit forecasting models
	@echo "$(CYAN)🤖 Training forecasting models...$(RESET)"
	@$(PYTHON) -m ml.forecasting.pipelines.train

train-sustainability: ## Train ESG scorer models
	@echo "$(CYAN)🤖 Training sustainability models...$(RESET)"
	@$(PYTHON) -m ml.sustainability.pipelines.train

train-all: ## Train all ML models
	@$(MAKE) train-recruitment train-pricing train-forecasting train-sustainability

generate-data: ## Generate synthetic training data for all modules
	@echo "$(CYAN)📊 Generating synthetic data...$(RESET)"
	@$(PYTHON) -m ml.data.synthetic.generate_all

mlflow-ui: ## Open MLflow UI in browser
	@open http://localhost:5000

# ────────────────────────────────────────────────────────────
# BUILD & DEPLOY
# ────────────────────────────────────────────────────────────
build: ## Build all Docker images for production
	@echo "$(CYAN)🏗  Building production images...$(RESET)"
	@$(COMPOSE) build --no-cache

build-frontend: ## Build frontend for production
	@$(FRONTEND) npm run build

deploy-staging: ## Deploy to staging (Render + Vercel)
	@echo "$(CYAN)🚀 Deploying to staging...$(RESET)"
	@./infrastructure/scripts/deploy-staging.sh

deploy-production: ## Deploy to production
	@echo "$(RED)⚠  Deploying to PRODUCTION$(RESET)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ]
	@./infrastructure/scripts/deploy-production.sh

# ────────────────────────────────────────────────────────────
# UTILITIES
# ────────────────────────────────────────────────────────────
clean: ## Remove all Docker volumes and rebuild from scratch
	@echo "$(RED)⚠  This will delete all local data!$(RESET)"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	@$(COMPOSE) down -v --remove-orphans
	@docker system prune -f

health: ## Check health of all services
	@echo "$(CYAN)🏥 Health check...$(RESET)"
	@curl -sf http://localhost:8000/health && echo " $(GREEN)✅ Backend$(RESET)" || echo " $(RED)❌ Backend$(RESET)"
	@curl -sf http://localhost:3000 && echo " $(GREEN)✅ Frontend$(RESET)" || echo " $(RED)❌ Frontend$(RESET)"
	@curl -sf http://localhost:5000/health && echo " $(GREEN)✅ MLflow$(RESET)" || echo " $(RED)❌ MLflow$(RESET)"
	@$(COMPOSE) exec redis redis-cli ping | grep -q PONG && echo " $(GREEN)✅ Redis$(RESET)" || echo " $(RED)❌ Redis$(RESET)"
	@$(COMPOSE) exec postgres pg_isready -U bizvision | grep -q "accepting" && echo " $(GREEN)✅ PostgreSQL$(RESET)" || echo " $(RED)❌ PostgreSQL$(RESET)"

install-hooks: ## Install git pre-commit hooks
	@echo "$(CYAN)🪝 Installing git hooks...$(RESET)"
	@pip install pre-commit
	@pre-commit install

docs: ## Generate API documentation
	@$(PYTHON) -m src.utils.generate_docs

version: ## Show versions of all key dependencies
	@$(BACKEND) python --version
	@$(BACKEND) pip show fastapi | grep Version
	@$(FRONTEND) node --version
	@$(FRONTEND) npm --version
