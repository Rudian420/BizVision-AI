# BizVision AI — ML Workspace

Research-grade ML pipelines for the five intelligence modules. Each module owns a
`pipelines/train.py` entry point that logs runs to MLflow.

```
ml/
├── data/synthetic/      # synthetic dataset generators (no PII)
├── recruitment/         # SBERT + XGBoost ensemble + fairness
├── pricing/             # LightGBM demand + PPO pricing agent
├── forecasting/         # Prophet + LSTM + XGBoost stacking
├── sustainability/      # ESG multi-label classifier
├── chatbot/             # RAG + LangGraph (lives mostly in backend)
└── shared/              # explainability, fairness, mlflow utils
```

## Commands (from repo root)

```bash
make generate-data        # synthetic data for all modules
make train-all            # train every module
make train-recruitment    # single module
make ml-notebook          # Jupyter Lab in the ml-dev container
```

> **Status (2026-05-28):** pipeline + data-generator *scaffolds* are in place with
> MLflow wiring. Real model training lands in Phase 3 (see `project-management/roadmap.md`).
