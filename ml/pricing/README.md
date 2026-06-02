# Smart Pricing Advisor

Research-grade, production-ready pricing-optimisation module for BizVision AI.

> **Thesis chapter**: §5 — Smart Pricing Advisor
> **Research contribution**: RC-003 (Explainable RL pricing — post-hoc SHAP + Monte Carlo uncertainty)
> **Ablation study**: AS-002 (Constant · CompetitorMatch · Elasticity-optimal · LightGBM-grid · PPO-RL)
> **Architecture**: mirrors `ml/recruitment/` per **ADR-025** — same shape across modules

---

## Architecture

```
ml/pricing/
├── data/            Product / PriceObservation / MonteCarloConfig schemas + loader
├── features/        engineered tabular features for the LightGBM demand model
├── models/          DemandModel + PricingPolicy interfaces (ADR-022 here too)
│                      baselines · elasticity (closed-form) · LightGBM-grid · PPO RL agent
│                      MonteCarloSimulator (revenue + profit distribution)
├── evaluation/      pure-numpy metrics (revenue uplift / MAPE / Sharpe / VaR / win rate)
│                      + benchmark harness
├── explainability/  SHAP for LightGBM demand + deterministic narrative generator
├── reproducibility/ seed control + env capture (for MLflow tags)
├── registry/        MLflow Model Registry helpers (smart-pricing-policy)
├── copilot/         pricing advisory LLM layer (structured JSON I/O)
├── training/        full pipeline · AS-002 ablation runner · TrainingConfig
├── pipelines/       legacy CLI entry (thin shim → training.pipeline)
├── tests/           offline unit tests (pure-numpy metrics + MC + elasticity)
├── cli.py           `python -m ml.pricing.cli {train|ablate|benchmark}`
└── README.md        (this file)
```

Every pricing policy implements `models.base.PricingPolicy`; every
demand estimator implements `models.base.DemandModel`. The benchmark
harness + ablation runner + copilot are all generic over the
interfaces — adding a new policy is one file in `models/` and one line
in `training.pipeline`. ADR-022's uniform-interface principle applies
here just as in recruitment (ADR-025).

---

## Quickstart

Inside the `ml-dev` container (or any env with `ml/requirements.txt`):

```bash
# Run a single training pipeline (synthetic data, MLflow tracked).
python -m ml.pricing.cli train --seed 42 --n 3000

# The AS-002 ablation matrix (3 seeds × 2 dataset sizes).
python -m ml.pricing.cli ablate

# Dump the benchmark comparison table.
python -m ml.pricing.cli benchmark
```

A single `train` call:

  1. Loads the synthetic pricing dataset
     (`ml/data/synthetic/generators.py:generate_pricing`).
  2. Splits deterministically by `(product_id, price)` hash — adding new
     observations can't reshuffle prior runs.
  3. Fits all five policy arms (Constant, CompetitorMatch,
     Elasticity-optimal, LightGBM-grid, PPO-RL).
  4. Runs the benchmark on the held-out products; the *evaluation
     demand* is a fresh `ConstantElasticityEstimator` fit on the test
     pool (so the scoring model is independent of any policy choice).
  5. Logs every metric to MLflow under the `bizvision-pricing` experiment.

---

## Research methodology

### Models compared (AS-002)

| Arm | Source | Signal |
|---|---|---|
| `baseline-constant-price` | `models.baselines.ConstantPricePolicy` | status-quo floor |
| `baseline-competitor-match` | `models.baselines.CompetitorMatchPolicy` | reactive (no demand model) |
| `policy-elasticity-optimal` | `models.elasticity.ElasticityOptimalPolicy` | closed-form log-log + revenue argmax |
| `policy-lightgbm-grid` | `models.demand.LightGBMGridPolicy` | EXP-PRC-001 — non-linear features |
| `policy-ppo-rl` | `models.rl_agent.PPOPricingPolicy` | EXP-PRC-002 — RC-003 target |

### Evaluation metrics

Defined in `evaluation.metrics` (pure numpy, unit-tested):

- `mean_absolute_percentage_error`, `root_mean_squared_error` — demand-model accuracy
- `revenue_uplift` — fractional mean revenue improvement vs baseline
- `win_rate` — fraction of products where the model strictly beats baseline
- `sharpe_ratio` — risk-adjusted mean (per-query)
- `value_at_risk` — 5%-tail downside (RC-003 risk axis)

The benchmark frame reports `{revenue_uplift_pct, mean_revenue,
win_rate_vs_baseline, sharpe, var_5pct}` per policy + the
`__baseline_constant__` row.

### Monte Carlo uncertainty (RC-003)

`MonteCarloSimulator` runs N (default 10 000) demand draws under a
clipped Gaussian assumption, reports `{mean, P5, P50, P95, VaR(5%),
P(profit)}` and a coarse histogram. Every recommended price can be
followed by an MC simulation for the recruiter copilot's risk callout.

### Reproducibility

- Seed control through `reproducibility.set_global_seed`
  (numpy + Python + torch + cuDNN).
- Deterministic hash-based train/val/test splits keyed on
  `(product_id, price)` — adding rows can't reshuffle.
- Every MLflow run is tagged with `reproducibility.capture_environment()`
  — versions of numpy / pandas / lightgbm / torch / gymnasium /
  stable-baselines3 / shap / mlflow + CUDA + git SHA.
- `PricingTrainingConfig` is fully YAML-serialisable; reconstructed from
  MLflow params.

### Production path

- Backend pricing service calls `train_pipeline` or `register_run` to
  produce a `smart-pricing-policy` MLflow model version.
- Promotion gate (recommended): NDCG-style — mean uplift ≥ Production
  AND `var_5pct` ≤ Production.
- Online inference: future `PricingInferenceClient` (Session 10) mirrors
  ADR-024 — lazy import, in-process singleton, per-worker ranker.

---

## Architectural decisions

- **ADR-022** — uniform `PricingPolicy` / `DemandModel` interfaces.
- **ADR-025** — package layout mirrors `ml.recruitment` (same shape, lower cognitive cost when navigating).
- **ADR-026** — RL pricing agent design: PPO over a constant-elasticity Gymnasium env so the RL arm is *directly comparable* to the closed-form elasticity arm.

See `project-management/architecture-decisions.md`.

---

## Heavy dependencies (lazy-imported)

| Module | Heavy dep | When loaded |
|---|---|---|
| `models.demand.LightGBMDemandModel` | `lightgbm` | inside `fit` |
| `models.rl_agent.PPOPricingPolicy` | `gymnasium` + `stable_baselines3` | inside `fit` |
| `explainability.shap_adapter` | `shap` | inside `_build_explainer` |
| `registry.model_registry` | `mlflow` | inside each helper |

This is the same pattern as recruitment (ADR-024 in spirit) — the
backend image without the ML stack imports cleanly, and the production
path opts in by installing `ml/requirements.txt`.
