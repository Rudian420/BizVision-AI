# BizVision AI — ML Experiments Log

> Research reproducibility log. All experiments tracked here for thesis reference.

---

## Experiment Tracking System

- **Platform**: MLflow (self-hosted, Docker)
- **Backend**: PostgreSQL artifact store
- **Storage**: MinIO (S3-compatible) for model artifacts
- **Naming**: `{module}-{experiment}-{date}-{run_id}`

---

## Recruitment Intelligence Experiments

> **Status (2026-05-28)**: code path complete — `python -m ml.recruitment.cli train`
> runs the full pipeline. All metric implementations unit-tested (18/18 pass).
> Numerical results filled in once the pipeline runs in the `ml-dev` container.

### Experimental Protocol

For every recruitment experiment we follow the same protocol — encoded as
the `train_pipeline` orchestrator in `ml/recruitment/training/pipeline.py`:

1. **Seed** every PRNG via `reproducibility.set_global_seed(seed)`.
2. **Load** the synthetic dataset (`data.RecruitmentDataLoader.load_synthetic`)
   or a JSONL of real data once available.
3. **Split** deterministically by `sha256(seed:candidate_id) mod 1`
   into 70 / 15 / 15 (train / val / test). Hash-based splits guarantee no
   candidate crosses partitions when the dataset grows.
4. **Fit** each ranking model on train.
5. **Score** every model on test, group results by query, compute the
   metric grid: `{ndcg, precision, recall, map}@{1, 3, 5, 10}` + AUC + MRR.
6. **Audit** fairness across protected attributes (intersectional if ≥ 2).
7. **Log** every parameter, metric, and `capture_environment()` tag to
   MLflow under experiment `bizvision-recruitment`.

### EXP-REC-001: TF-IDF Baseline
**Date**: 2026-05-28 (code complete)
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.recruitment.models.baselines.TFIDFRanker`
**Implementation**: `TfidfVectorizer(max_features=10_000, ngram_range=(1,2),
min_df=2, sublinear_tf=True, strip_accents="unicode")` + cosine similarity
between JD and CV vectors.
**Expected**: AUC ≈ 0.72, NDCG@5 ≈ 0.68 (literature: classical retrieval
on technical resumes).

### EXP-REC-001b: BM25 Baseline (additional)
**Date**: 2026-05-28
**Status**: 🟢 Implemented
**Model**: `ml.recruitment.models.baselines.BM25Ranker` — Okapi BM25
(`k1=1.5, b=0.75`), gold-standard lexical retrieval baseline.
**Rationale**: TF-IDF and BM25 disagree on rare-term weighting; reporting
both pins down whether ensemble gains come from semantics or just from
better lexical scoring.

### EXP-REC-002: SBERT Semantic Similarity
**Date**: 2026-05-28
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.recruitment.models.semantic.SBERTRanker` with
`sentence-transformers/all-mpnet-base-v2` (768-dim) and L2-normalised
embeddings. Cosine = dot-product after normalisation.
**Cache**: content-hash keyed LRU + optional on-disk shard
(`~/.cache/bizvision/embeddings/`). Critical for AS-001 — the same CV
text is encoded once across all (model × seed × n) combinations.

### EXP-REC-003: XGBoost on Structured Features
**Date**: 2026-05-28
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.recruitment.models.structured.XGBoostRanker`
**Features** (canonical order — pass to SHAP for matching attribution):
   1. `years_experience` (numeric, missing → -1)
   2. `education_rank` (ordinal: HS=0, Bachelor=1, Master=2, PhD=3, unknown=-1)
   3. `required_skill_overlap` = |req ∩ cand_skills| / |req|
   4. `preferred_skill_overlap`
   5. `total_skill_count`
   6. `min_years_met` (binary)
   7. `location_match` (binary)
   8. `has_education` (binary)
**Hyperparameters**: see `XGBoostRanker.DEFAULT_PARAMS`
(`n_estimators=400, max_depth=6, lr=0.05, subsample=0.85, colsample=0.85`).

### EXP-REC-004: SBERT + XGBoost Weighted Ensemble (Target System)
**Date**: 2026-05-28
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.recruitment.models.ensemble.EnsembleRanker(SBERTRanker, XGBoostRanker, w)`
**Composition**: `score = w · normalise(SBERT_cos) + (1-w) · normalise(XGB_proba)`
where `normalise` is per-batch min-max into [0,1] (avoids re-fitting
calibration on each query).
**Weight selection**: `find_optimal_weight(grid=(0.3, 0.4, 0.5, 0.6, 0.7), k=5)`
maximises NDCG@5 on the validation split. The chosen weight is logged
to MLflow as `best_ensemble_weight`.
**Why a linear blend rather than a meta-learner**: see ADR-023 —
interpretability (SHAP attributions compose linearly), calibration, and
cold-start data efficiency.

---

## AS-001: Recruitment Ablation Matrix (Methodology)

Implemented in `ml.recruitment.training.ablation.run_ablation`.

**Matrix**: `{seeds} × {n_candidates}` — default
`(42, 43, 44) × (500, 2000)` = **6 runs**, each producing 6 model fits
(Random, TF-IDF, BM25, SBERT, XGBoost, Ensemble) = **36 model fits per ablation**.

**Aggregation**: `AblationRunResult.mean_with_ci("ndcg@5")` returns
mean NDCG@5 with 95 % CI (1.96 × SEM across seeds) per model — the
canonical thesis Table 4.X.

**Reporting target**:

| Model | NDCG@5 (mean ± 95 % CI) | AUC | MRR | DPD(gender) |
|-------|------------------------|-----|-----|-------------|
| Random | TBD | TBD | TBD | TBD |
| TF-IDF | TBD | TBD | TBD | TBD |
| BM25 | TBD | TBD | TBD | TBD |
| SBERT | TBD | TBD | TBD | TBD |
| XGBoost | TBD | TBD | TBD | TBD |
| **Ensemble (target)** | TBD | TBD | TBD | TBD |

---

## Smart Pricing Experiments

> **Status (2026-05-29)**: code path complete (TASK-010) —
> `python -m ml.pricing.cli train` runs the full pipeline against the
> synthetic generator. All metric implementations unit-tested
> (**18/18 pure-numpy tests pass**). Numerical results filled in once the
> pipeline runs in the `ml-dev` container.

### Experimental Protocol

`train_pipeline` in `ml/pricing/training/pipeline.py`:

1. **Seed** every PRNG via `reproducibility.set_global_seed(seed)`.
2. **Load** the synthetic dataset (`PricingDataLoader.load_synthetic`)
   or JSONL.
3. **Split** deterministically by `sha256(seed:product_id:price)` into
   70 / 15 / 15. Adding observations can't reshuffle prior splits.
4. **Fit** every policy on `train`.
5. **Score** each policy on `test_products` using an *independent*
   `ConstantElasticityEstimator` fit on the test pool (eliminates the
   "model evaluated by itself" anti-pattern).
6. **Log** every parameter, metric, and `capture_environment()` tag to
   MLflow under experiment `bizvision-pricing`.

### EXP-PRC-001: LightGBM Demand Forecasting Baseline
**Date**: 2026-05-29 (code complete)
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.pricing.models.demand.LightGBMDemandModel`
**Implementation**: `LGBMRegressor(n_estimators=400, num_leaves=31,
learning_rate=0.05, subsample=0.85, colsample_bytree=0.85, …)` on the 8
engineered features (`features.structured.FEATURE_NAMES`).
**Policy wrapper**: `LightGBMGridPolicy` — at recommendation time,
constructs a 25-point grid in `(0.6·current, 1.6·current)`, predicts
demand at each point, picks the revenue argmax.

### EXP-PRC-001b: Constant-Elasticity Closed-Form (additional)
**Date**: 2026-05-29
**Status**: 🟢 Implemented
**Model**: `ml.pricing.models.elasticity.ConstantElasticityEstimator` +
`ElasticityOptimalPolicy`. log-log linear regression recovers ε in
closed form; revenue argmax in a bounded grid (avoids the inelastic
edge case). Verified by unit test: recovers ε = -1.5 from synthetic
`demand = price^-1.5` within 1 %.

### EXP-PRC-002: RL Pricing Agent (PPO) — RC-003 target
**Date**: 2026-05-29
**Status**: 🟢 Implemented · awaits ml-dev run
**Model**: `ml.pricing.models.rl_agent.PPOPricingPolicy` (Stable-
Baselines3 PPO) over a **custom `_ConstantElasticityEnv`** —
see ADR-026 for why the env uses the same dynamics as the closed-form
arm.
**Action**: continuous price multiplier in `[0.6, 1.6]`.
**Reward**: per-step revenue (not profit) so the agent doesn't get
trapped at high prices with near-zero demand. VaR(5%) reported
separately for the risk-adjusted view.
**Soft fallback**: when `gymnasium` / `stable_baselines3` aren't
installed, the policy returns the closed-form elasticity
recommendation — keeps the AS-002 matrix complete on partial installs.

### EXP-PRC-003: Monte Carlo Revenue Simulator (RC-003)
**Date**: 2026-05-29
**Status**: 🟢 Implemented
**Model**: `ml.pricing.models.monte_carlo.MonteCarloSimulator`
**Implementation**: clipped-Gaussian demand draws (N=10 000 default),
reports `{mean, P5, P50, P95, VaR(5%), P(profit)}` plus a coarse
histogram. Deterministic given the same seed. Used both as the
`/pricing/simulate` API path and as the per-recommendation risk
overlay for the recruiter copilot.

---

## AS-002: Pricing Ablation Matrix (Methodology)

Implemented in `ml.pricing.training.ablation.run_ablation`.

**Matrix**: `{seeds} × {n_observations}` — default
`(42, 43, 44) × (1 000, 3 000)` = **6 runs**, each producing 5 policy
fits (Constant, CompetitorMatch, Elasticity-optimal, LightGBM-grid,
PPO-RL) = **30 policy fits per ablation**.

**Aggregation**: `AblationRunResult.mean_with_ci("revenue_uplift_pct")`
returns mean revenue uplift with 95 % CI (1.96 × SEM across seeds) per
policy — the canonical thesis Table 5.X.

**Reporting target**:

| Policy | Uplift (mean ± 95 % CI) | Mean Rev | Sharpe | VaR(5%) | Win-rate |
|---|---|---|---|---|---|
| Constant | TBD | TBD | TBD | TBD | TBD |
| CompetitorMatch | TBD | TBD | TBD | TBD | TBD |
| Elasticity-optimal | TBD | TBD | TBD | TBD | TBD |
| LightGBM-grid | TBD | TBD | TBD | TBD | TBD |
| **PPO-RL (target)** | TBD | TBD | TBD | TBD | TBD |

---

## Profit Forecasting Experiments

### EXP-FOR-001: Prophet Baseline
**Date**: TBD  
**Status**: Planned

### EXP-FOR-002: LSTM Sequence Model
**Date**: TBD  
**Status**: Planned  
**Architecture**: 2-layer LSTM (128 hidden, 64 hidden) + Dense

### EXP-FOR-003: XGBoost with Lag Features
**Date**: TBD  
**Status**: Planned

### EXP-FOR-004: Hybrid Ensemble (Target)
**Date**: TBD  
**Status**: Planned  
**Method**: Stacking ensemble (Prophet + LSTM + XGBoost → meta-learner)

---

## ESG Sustainability Experiments

### EXP-ESG-001: Multi-Label Classifier Baseline
**Date**: TBD  
**Status**: Planned  
**Model**: LightGBM multi-label classification  
**Labels**: carbon_score, waste_score, energy_score, social_score, governance_score

---

## Fairness Audit Log

> **Methodology (RC-002)**. Three layers:
>   1. **Group fairness** — Demographic Parity Difference (DPD), Equalized
>      Odds Difference (EOD), Disparate Impact (DI = min/max selection-rate
>      ratio; 4/5-ths rule passes when DI ≥ 0.8). Implemented in
>      `ml.recruitment.fairness.auditor.audit_ranking`.
>   2. **Intersectional fairness** — same metrics over the Cartesian
>      product of any two protected attributes (e.g. gender × age_group).
>      Implemented in `intersectional_audit`. Cardinality capped at 16 to
>      avoid degenerate groups.
>   3. **SHAP-attributed bias decomposition (novel)** — per-feature
>      contribution to the parity gap. Implemented in
>      `explainability.shap_adapter.SHAPRecruitmentExplainer.bias_decomposition`.
>      The gap is computed as
>      `(mean SHAP, favoured group) − (mean SHAP, unfavoured group)`
>      per feature, identifying *which model inputs drive demographic unfairness*.
> **Mitigation**: post-hoc reweighing (Kamiran & Calders, 2012) +
> threshold optimisation (Hardt et al., 2016) wired in `fairness.mitigation`.

| Experiment | Model | Protected Attr. | DPD | EOD | DI | Mitigation | Post-mit. DPD |
|------------|-------|-----------------|-----|-----|----|-----------|---------------|
| REC-004 | SBERT+XGBoost | gender | TBD | TBD | TBD | Reweighing | TBD |
| REC-004 | SBERT+XGBoost | age_group | TBD | TBD | TBD | Threshold opt | TBD |
| REC-004 | SBERT+XGBoost | gender × age_group | TBD | TBD | TBD | — | — |

*DPD = Demographic Parity Difference, EOD = Equalized Odds Difference, DI = Disparate Impact ratio*

---

## Results Summary Table (Fill as experiments complete)

| Experiment | AUC | NDCG@5 | MAPE | F1-macro | Notes |
|------------|-----|--------|------|----------|-------|
| REC-001 (TF-IDF) | — | — | — | — | Baseline |
| REC-002 (SBERT) | — | — | — | — | Semantic |
| REC-003 (XGBoost) | — | — | — | — | Structured |
| REC-004 (Ensemble) | — | — | — | — | **Target** |

---

## Reproducibility Contract

Every recruitment experiment ships with three artefacts written by
`train_pipeline`:

1. **`TrainingConfig` (YAML-serialisable)** — captured verbatim into
   MLflow `params` as `config=…`. Includes seed, dataset size,
   SBERT model name, XGBoost params, ensemble grid, fairness top-k,
   protected-attribute list.
2. **Environment snapshot** — `reproducibility.capture_environment()`
   logs Python version, platform, all tracked library versions
   (`numpy, pandas, sklearn, xgboost, lightgbm, torch,
   sentence-transformers, transformers, shap, lime, fairlearn, aif360,
   mlflow`), CUDA version, and the current git SHA.
3. **MLflow tags** — every metric / param prefixed with the model name
   (e.g. `ensemble(semantic-sbert::…@0.60+structured-xgboost).ndcg@5`).

To reproduce any historical run:
```bash
# Pull config + env from MLflow run, then:
python -m ml.recruitment.cli train --seed <seed> --n <n>
```
The hash-based split + global seed control guarantees bit-identical
results on the same toolchain.

---

*Last updated: 2026-05-28 | Recruitment module implemented; pending live ml-dev runs for numerical results*
