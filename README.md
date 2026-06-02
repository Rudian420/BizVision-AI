# BizVision AI

> **Elite SME Decision Intelligence Platform** — Research-grade, thesis-worthy, startup-level AI ecosystem

---

## What is BizVision AI?

BizVision AI is an integrated, multi-module AI platform that gives Small & Medium Enterprises the same quality of decision intelligence as large enterprise companies. It's built as a research-grade system suitable for academic thesis, publication, and startup deployment.

The platform combines five interconnected AI intelligence modules through a **Shared Context Architecture** that allows cross-module reasoning — where pricing decisions inform forecasting, hiring signals affect cost projections, and ESG risks shape financial outlook.

---

## AI Modules

| Module | Capability | Core AI |
|--------|-----------|---------|
| **Recruitment Intelligence** | Semantic candidate ranking with fairness auditing | SBERT + XGBoost Ensemble + SHAP |
| **Smart Pricing Advisor** | Price optimization with elasticity simulation | LightGBM + RL (PPO) + Monte Carlo |
| **Profit Forecasting** | Multi-scenario financial forecasting | Prophet + LSTM + XGBoost Ensemble |
| **Financial Advisory AI** | Executive AI chatbot with RAG | LangGraph + pgvector + Claude/GPT-4 |
| **Green Business Scorer** | ESG sustainability analysis | Multi-label Classification + AIF360 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BizVision AI Platform                    │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Next.js 14 + React Three Fiber + GSAP)           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │3D Neural │ │Holographic│ │Temporal  │ │Living ESG│       │
│  │Galaxy    │ │Pricing   │ │Rivers    │ │Ecosystem │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Celery + Redis)                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Recruit.│ │Pricing │ │Forecast│ │Chatbot │ │  ESG   │   │
│  │Router  │ │Router  │ │Router  │ │Router  │ │Router  │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
│                    Shared Context Bus                        │
├─────────────────────────────────────────────────────────────┤
│  ML Layer                                                    │
│  SBERT │ XGBoost │ LightGBM │ Prophet │ LSTM │ LangGraph    │
│  SHAP  │ LIME    │ Fairlearn │ AIF360  │ MLflow              │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                              │
│  PostgreSQL+pgvector │ Redis │ MinIO │ MLflow │ Nginx        │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Docker Desktop + Docker Compose
- 8GB RAM minimum (16GB recommended for ML models)
- Python 3.11+ (for local development without Docker)
- Node.js 20+ (for frontend development)

### One-Command Setup

```bash
# Clone and setup
git clone https://github.com/your-org/bizvision-ai
cd bizvision-ai

# Run the bootstrap script
bash setup.sh
```

The setup script will:
1. Copy `.env.example` → `.env` and generate a secure JWT secret
2. Build all Docker images
3. Run database migrations
4. Seed development data
5. Start all 9 services
6. Validate health checks

**Access the platform at: http://localhost:3000**

### Manual Setup (for development)

```bash
# Copy environment config
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start infrastructure
make up

# Run migrations
make migrate

# Seed data
make seed

# Train ML models
make generate-data
make train-all
```

---

## Development Commands

```bash
make help           # Show all available commands

# Lifecycle
make up             # Start all services
make down           # Stop all services
make restart        # Restart all services
make logs           # Follow all logs
make status         # Service status
make health         # Health check all services

# Database
make migrate        # Run pending migrations
make migrate-create NAME="add_table"   # Create new migration
make seed           # Seed development data

# ML Operations
make generate-data  # Generate synthetic training data
make train-all      # Train all 5 ML modules
make mlflow-ui      # Open MLflow in browser

# Testing
make test           # Run all tests
make test-backend   # Backend tests only
make test-frontend  # Frontend tests only

# Code Quality
make lint           # Lint all code
make format         # Format all code
```

---

## Research Contributions

1. **Unified Multi-Module XAI Framework** — First integrated explainable AI system spanning HR, pricing, financial forecasting, and ESG domains
2. **Fairness-Aware Recruitment with SHAP Bias Attribution** — Novel decomposition identifying proxy features driving demographic unfairness
3. **Cross-Module Profit Forecasting** — Hybrid ensemble that integrates hiring, pricing, and ESG signals for richer financial projections
4. **Explainable RL Pricing** — Post-hoc SHAP explanations for reinforcement learning pricing policies

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 14, React Three Fiber, GSAP, Framer Motion, Three.js |
| **3D/Shaders** | WebGL, GLSL, Postprocessing, Theatre.js |
| **State** | Zustand, React Query, WebSocket |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery |
| **Database** | PostgreSQL + pgvector, Redis, MinIO |
| **ML Core** | PyTorch, HuggingFace, SBERT, XGBoost, LightGBM |
| **XAI** | SHAP, LIME, custom narrative engine |
| **Fairness** | Fairlearn, IBM AIF360 |
| **MLOps** | MLflow, DVC, Docker, GitHub Actions |
| **LLM/Agents** | LangGraph, LangChain, Claude API |

---

## Project Management

All project tracking is in `/project-management/`:
- `roadmap.md` — Full 6-phase development roadmap
- `current-status.md` — Current progress (always up to date)
- `architecture-decisions.md` — Engineering decision log (10 ADRs)
- `research-notes.md` — Thesis material and publication opportunities
- `ml-experiments.md` — ML experiment tracking

---

## License

MIT License — See LICENSE file

---

*Built with the combined intelligence of a top-tier AI lab, Silicon Valley startup CTO, award-winning creative studio, and world-class research department.*
