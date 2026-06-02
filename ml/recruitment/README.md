# Recruitment Intelligence

Research-grade, production-ready candidate-ranking module for BizVision AI.

This package contains the **end-to-end Recruitment Intelligence system**:
resume parsing → embeddings → ranking → explainability → fairness audit →
recruiter copilot, plus a benchmark harness and a thesis-grade ablation
runner.

> **Thesis chapter**: §4 — Recruitment Intelligence
> **Research contribution**: RC-002 (intersectional fairness with
> SHAP-attributed bias decomposition)
> **Ablation study**: AS-001 (TF-IDF · SBERT · XGBoost · Ensemble)

---

## Architecture

```
ml/recruitment/
├── data/            schemas + reproducible JSONL / synthetic loader
├── parsers/         PDF / DOCX / TXT → CandidateRecord (lazy heavy imports)
├── features/        structured features for boosting rankers (with SHAP-friendly names)
├── embeddings/      SBERT (mpnet) · TF-IDF baseline · content-hash cache
├── models/          Random · TF-IDF · BM25 · SBERT · XGBoost · Ensemble
├── evaluation/      pure-numpy metrics · deterministic splits · benchmark harness
├── explainability/  SHAP (+ bias decomposition · RC-002) · LIME · narrative
├── fairness/        intersectional audit · post-hoc reweighing + threshold opt.
├── reproducibility/ seed control · environment capture (for MLflow tags)
├── registry/        MLflow Model Registry helpers (recruitment-ranker)
├── search/          pgvector candidate index (production semantic retrieval)
├── copilot/         recruiter conversational LLM layer (structured I/O)
├── training/        full pipeline · ablation runner · TrainingConfig
├── pipelines/       legacy CLI entry (thin shim → training.pipeline)
├── tests/           offline unit tests (pure-numpy metrics)
├── cli.py           `python -m ml.recruitment.cli {train|ablate|benchmark}`
└── README.md        (this file)
```

Every ranking model implements the same `RankingModel.score(jd, cands)`
interface; the benchmark, the ensemble, and the copilot are all generic
over the interface so a new ranker — say a learning-to-rank LambdaMART
arm — is one file in `models/` and one line in `training.pipeline`.

---

## Quickstart

Inside the `ml-dev` container (or any env with `ml/requirements.txt` installed):

```bash
# Run a full training pipeline (synthetic data, MLflow tracked).
python -m ml.recruitment.cli train --seed 42 --n 2000

# The AS-001 ablation matrix (3 seeds × 2 dataset sizes).
python -m ml.recruitment.cli ablate

# Dump the benchmark comparison table.
python -m ml.recruitment.cli benchmark
```

A single `train` call:

  1. Loads the synthetic recruitment dataset (`ml/data/synthetic`).
  2. Splits deterministically by candidate-id hash (no leakage across reruns).
  3. Fits the five ranker arms + the weighted ensemble.
  4. Grid-searches the ensemble weight on the validation split.
  5. Runs the benchmark on test and produces per-query metrics.
  6. Audits fairness across protected attributes (intersectional, if ≥2).
  7. Logs everything to MLflow under the `bizvision-recruitment` experiment.

---

## Research methodology

### Models compared (AS-001)

| Arm | Source | Signal |
|---|---|---|
| `baseline-random` | `models.baselines.RandomRanker` | uniform noise (floor) |
| `baseline-tfidf` | `models.baselines.TFIDFRanker` | term-frequency-IDF cosine (EXP-REC-001) |
| `baseline-bm25` | `models.baselines.BM25Ranker` | Okapi BM25 lexical retrieval |
| `semantic-sbert` | `models.semantic.SBERTRanker` | `all-mpnet-base-v2` cosine (EXP-REC-002) |
| `structured-xgboost` | `models.structured.XGBoostRanker` | boosted trees on tabular features (EXP-REC-003) |
| `ensemble(...)` | `models.ensemble.EnsembleRanker` | weighted SBERT + XGBoost (EXP-REC-004 — target) |

### Evaluation metrics

Defined in `evaluation.metrics` (pure numpy, unit-tested):

- `precision@k`, `recall@k`, `average_precision@k`
- `ndcg@k` — graded relevance with the `(2^rel − 1)` gain formulation
- `mean_reciprocal_rank` — rank of the first relevant hit
- `roc_auc` — Mann-Whitney U binary AUC with tied-rank handling
- `spearman_correlation`

The harness reports `{ndcg, precision, recall, map}@{1,3,5,10}` plus
overall MRR + AUC, averaged across queries.

### Fairness analysis (RC-002)

Three layers in `fairness/`:

1. **Group fairness** — Demographic Parity Difference (DPD), Equalized Odds
   Difference (EOD), Disparate Impact ratio (4/5-ths rule).
2. **Intersectional fairness** — same metrics over the Cartesian product
   of any two protected attributes (gender × age_group, etc.).
3. **SHAP-attributed bias decomposition** — *novel*. Stratifies SHAP
   matrices by group and reports the per-feature contribution to the
   parity gap. Implemented in `explainability.shap_adapter.bias_decomposition`.

### Reproducibility

- All randomness routed through `reproducibility.set_global_seed`
  (numpy + Python + torch + cuDNN).
- Deterministic hash-based train/val/test splits — adding rows can't
  reshuffle prior runs.
- Every MLflow run is tagged with `reproducibility.capture_environment()`
  — Python version, platform, library versions, CUDA version, git SHA.
- `TrainingConfig` is fully YAML-serialisable; serialised verbatim
  into the MLflow params so any run can be reconstructed from its config.

### Production path

- Backend recruitment service calls `train_pipeline` or `register_run`
  to produce a `recruitment-ranker` MLflow model version.
- Promotion is gated by NDCG@5 ≥ current Production AND DPD ≤ current
  Production (see `registry.promote_to_production`).
- Online inference: `search.CandidateVectorIndex` (pgvector HNSW) +
  `XGBoostRanker` structured pass + `EnsembleRanker` composition.

---

## Architectural decisions

- **ADR-020** — Module package layout (this directory).
- **ADR-021** — Embedding cache strategy (content-hash + LRU + optional disk).
- **ADR-022** — Uniform `RankingModel` interface enables ensemble +
  ablation + copilot without case analysis.
- **ADR-023** — Linear-blend ensemble over a meta-learner for
  interpretability, calibration, and cold-start data-efficiency.

See `project-management/architecture-decisions.md`.
