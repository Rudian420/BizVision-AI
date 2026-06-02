# BizVision AI — Research Notes & Thesis Material

> Continuously evolving research log. Goal: publication-worthy contributions.

---

## Core Research Contributions

### RC-001: Unified Multi-Module XAI Framework for SME Decision Intelligence

**Claim**: Current AI business tools are siloed — no system provides cross-domain explainable intelligence (pricing → forecasting → recruitment → sustainability) with shared context.

**Contribution**: BizVision AI is the first integrated, explainable multi-module AI decision system for SMEs with:
- Shared context architecture propagating signals across modules
- Unified fairness auditing across heterogeneous ML models
- Narrative AI reasoning bridging ML outputs and human understanding

**Publication target**: *Expert Systems With Applications* / *Decision Support Systems*

---

### RC-002: Fairness-Aware Recruitment AI with Adversarial Debiasing

**Status (2026-05-28)**: 🟢 Implementation complete; ready for experimental campaign.

**Literature Gap**: Most recruitment AI fairness papers study single-attribute bias (gender OR race). None study intersectional fairness with SHAP-attributed bias visualisation.

**Contribution**: Intersectional fairness auditing using:
- IBM AIF360: reweighing + adversarial debiasing (planned for Phase 4)
- Fairlearn: demographic parity + equalized odds (live in `fairness.auditor`)
- **Novel: SHAP-attributed bias decomposition** — implemented in
  `ml.recruitment.explainability.shap_adapter.SHAPRecruitmentExplainer.bias_decomposition`.
  For each protected attribute we stratify the SHAP matrix by group and
  compute `gap[i] = mean_SHAP[favoured][i] − mean_SHAP[unfavoured][i]` per
  feature. This identifies *which model inputs drive demographic
  unfairness* — actionable signal that group-level DPD/EOD numbers cannot
  supply. The method generalises to any tree-based ranker.

**Mitigation** (live in `ml.recruitment.fairness.mitigation`):
- Reweighing (Kamiran & Calders, 2012) — pre-processing.
- Threshold optimisation for equal opportunity (Hardt et al., 2016) — post-processing.

**Intersectional auditing** — `fairness.auditor.intersectional_audit` runs
DPD/EOD/DI checks over the Cartesian product of any two protected
attributes (e.g. gender × age_group), capped at 16 groups to prevent
degenerate estimation.

**Metrics**: Demographic parity difference, equalized odds difference, disparate impact ratio, NDCG@k parity.

---

### RC-003: Reinforcement Learning Price Optimization with Explainable Policy

**Status (2026-05-29)**: 🟢 Implementation complete; ready for the
experimental campaign.

**Literature Gap**: RL pricing papers (PPO/SAC) don't explain WHY the
policy recommends a price.

**Contribution**: RL pricing agent with post-hoc SHAP explanation of
state features driving each pricing decision + Monte Carlo uncertainty
quantification.

**Implementation**:
- `ml.pricing.models.rl_agent.PPOPricingPolicy` — PPO from Stable-
  Baselines3 over a **custom `_ConstantElasticityEnv`**. Critically,
  the env uses the **same constant-elasticity dynamics** as the closed-
  form `ElasticityOptimalPolicy` (ADR-026), so uplift over closed-form
  is attributable to cross-feature interaction PPO discovers — not to
  a richer simulator.
- `ml.pricing.models.monte_carlo.MonteCarloSimulator` — clipped-Gaussian
  draws, reports mean / P5 / P50 / P95 / VaR(5%) / P(profit). Every
  recommended price can be wrapped in an MC distribution for the
  copilot's risk callout.
- `ml.pricing.explainability.shap_adapter.PricingSHAPExplainer` —
  TreeExplainer over the `LightGBMDemandModel`; produces per-feature
  attribution aligned to `features.structured.FEATURE_NAMES`. For the
  RL arm specifically, attribution is taken on the env's demand model
  (the constant-elasticity backbone) — same shape, simpler basis.

**Metrics**: Revenue uplift vs baseline (mean across products),
`win_rate_vs_baseline`, Sharpe ratio, VaR(5%), explanation fidelity
score. All implemented in pure numpy and unit-tested (`ml/pricing/tests/
test_metrics.py` — 18/18 pass).

**Ablation**: AS-002 — 6 runs × 5 policy arms = 30 policy fits per
ablation. Default `(seeds 42-44) × (n_observations 1k/3k)` matrix in
`ml.pricing.training.ablation.run_ablation`.

---

### RC-004: Hybrid Forecasting with Cross-Module Signal Integration

**Literature Gap**: Profit forecasting models treat the business in isolation — no system integrates hiring signals (cost changes), pricing signals (revenue elasticity), and ESG signals (regulatory cost risk).

**Contribution**: Multi-source forecasting model that ingests:
- Pricing module output (price elasticity → revenue projection)
- Recruitment module output (hiring cost → operational cost projection)
- ESG module output (compliance risk → regulatory cost scenario)

**Metrics**: MAPE, Winkler score on prediction intervals, cross-module signal importance (SHAP)

---

## Literature Review Notes

### Explainable AI (XAI)

| Paper | Key Finding | Relevance |
|-------|-------------|-----------|
| Lundberg & Lee (2017) - SHAP | SHAP values unify feature attribution methods | Core XAI method |
| Ribeiro et al. (2016) - LIME | Local approximation for model-agnostic explanations | Secondary XAI |
| Rudin (2019) - "Stop explaining black box ML" | Inherently interpretable > post-hoc | Motivates dual approach |
| Arrieta et al. (2020) - XAI survey | Taxonomy of XAI methods | Literature framework |

### Fairness in ML

| Paper | Key Finding | Relevance |
|-------|-------------|-----------|
| Hardt et al. (2016) - Equalized Odds | Fairness through equalized false positive rates | Recruitment fairness metric |
| Dwork et al. (2012) - Fairness Through Awareness | Individual fairness via similarity metrics | Advanced fairness notion |
| Mehrabi et al. (2021) - Bias survey | Taxonomy of bias types | Literature grounding |
| Bellamy et al. (2019) - AIF360 | IBM's fairness toolkit | Core library |

### Time Series Forecasting

| Paper | Key Finding | Relevance |
|-------|-------------|-----------|
| Taylor & Letham (2018) - Prophet | Additive model with trend/seasonality | Ensemble component |
| Hochreiter & Schmidhuber (1997) - LSTM | Long-term dependency modeling | Deep learning component |
| Chen & Guestrin (2016) - XGBoost | Gradient boosting with regularization | Tree-based component |
| Makridakis et al. (2022) - M6 Competition | Ensemble forecasting beats individual | Validates ensemble approach |

---

## Ablation Study Plan

### AS-001: Recruitment Intelligence Ablation

**Status (2026-05-28)**: 🟢 Runner implemented in
`ml.recruitment.training.ablation.run_ablation`.

Expanded from the original 4-arm plan to **6 arms** (per ADR-022 and the
literature norm of reporting at least one lexical retrieval baseline
alongside TF-IDF):

1. **Random** — uniform noise; sanity floor.
2. **TF-IDF** — `TfidfVectorizer` + cosine.
3. **BM25** — Okapi BM25 (k1=1.5, b=0.75). Gold-standard lexical baseline.
4. **+SBERT** — `all-mpnet-base-v2` cosine.
5. **+XGBoost** — boosted trees on 8 structured features.
6. **Full Ensemble** — weighted SBERT ⊕ XGBoost (`EnsembleRanker`); weight
   chosen by `find_optimal_weight` grid search on the validation split.

**Matrix**: `seeds ∈ {42, 43, 44}` × `n_candidates ∈ {500, 2000}` = 6 runs,
36 model fits. 3 seeds gives 95 % CI via `mean ± 1.96·SEM` (large-n
normal approximation; bootstrap available via `pandas.DataFrame.sample`).

**Metrics**: NDCG@{1,3,5,10}, Precision@{…}, Recall@{…}, MAP@{…}, MRR, AUC
— all pure-numpy implementations in
`ml.recruitment.evaluation.metrics` (18 unit tests, ✅ all pass).

**Fairness as a third axis**: every model's predictions also feed
`intersectional_audit(gender, age_group)` so the ablation table reports
DPD, EOD, DI alongside accuracy — making the
*accuracy–fairness tradeoff* directly readable.

### AS-002: Smart Pricing Ablation

**Status (2026-05-29)**: 🟢 Runner implemented in
`ml.pricing.training.ablation.run_ablation`.

Five policy arms behind the uniform `PricingPolicy` interface
(ADR-022 / ADR-025):

1. **Constant** (`ConstantPricePolicy`) — status-quo floor.
2. **CompetitorMatch** (`CompetitorMatchPolicy`) — reactive (no
   demand model); lowest competitor price wins.
3. **Elasticity-optimal** (`ElasticityOptimalPolicy`) — closed-form
   log-log + revenue argmax. Interpretable arm.
4. **LightGBM-grid** (`LightGBMGridPolicy`) — LightGBM demand model
   + 25-point grid search in `(0.6·current, 1.6·current)`. Captures
   non-linear price/competitor/season interactions (EXP-PRC-001).
5. **PPO-RL** (`PPOPricingPolicy`) — Stable-Baselines3 PPO over the
   **constant-elasticity environment** (ADR-026 — direct comparability
   to the closed-form arm; uplift attributable to cross-feature
   interaction, not richer simulator). EXP-PRC-002 / RC-003 target.

**Matrix**: `(seeds 42-44) × (n_observations 1k, 3k)` = 6 runs ×
5 policies = 30 policy fits. PPO is the slow arm.

**Metrics** (all pure-numpy, `ml.pricing.evaluation.metrics`,
18/18 tests pass):
revenue_uplift, mean_revenue, win_rate_vs_baseline, sharpe_ratio,
value_at_risk(5%).

**Risk as a third axis**: the benchmark reports VaR(5%) alongside mean
revenue so AS-002 tables show the *revenue–risk tradeoff* directly —
the same shape AS-001 uses for accuracy–fairness.

### AS-003: Forecasting Ensemble Ablation
1. **Prophet only**
2. **LSTM only**
3. **XGBoost only**
4. **Prophet + LSTM**
5. **Full ensemble** (all three)

**Metric**: MAPE on 30/60/90-day horizons

### AS-004: XAI Method Comparison
1. No explanation (black box)
2. SHAP only
3. LIME only
4. SHAP + LIME + Narrative (our approach)

**Metric**: User comprehension study (explanation quality survey), fidelity score

---

## Evaluation Metrics Master List

### Recruitment Intelligence
- **AUC** (ranking quality)
- **NDCG@k** (normalized discounted cumulative gain at k candidates)
- **MRR** (mean reciprocal rank)
- **Demographic parity difference** (fairness)
- **Equalized odds difference** (fairness)
- **SHAP fidelity** (explainability quality)

### Smart Pricing
- **Revenue uplift** (% improvement over baseline price)
- **Demand MAPE** (demand forecasting accuracy)
- **Price Sharpe ratio** (risk-adjusted revenue)
- **Explanation fidelity** (SHAP vs ground truth)

### Profit Forecasting
- **MAPE** (mean absolute percentage error, 30/60/90 day)
- **RMSE** (point accuracy)
- **Winkler score** (prediction interval quality)
- **Cross-module signal importance** (novel contribution metric)

### ESG Scorer
- **Macro F1** (multi-label classification)
- **Spearman correlation** (vs ground-truth ESG ratings)
- **Recommendation acceptance rate** (user study)

### Chatbot
- **Response relevance** (BERTScore vs reference answers)
- **Tool usage accuracy** (correct API calls)
- **Factual consistency** (hallucination rate)

---

## Thesis Chapter Outline

1. **Introduction** — SME AI gap, motivation, research questions
2. **Literature Review** — XAI, Fairness, Forecasting, NLP/RAG
3. **System Architecture** — Federated module design, shared context bus
4. **Recruitment Intelligence** — SBERT + ensemble + fairness
5. **Smart Pricing Advisor** — RL + Monte Carlo + SHAP
6. **Profit Forecasting** — Hybrid ensemble + cross-module integration
7. **Green Business Scorer** — Multi-label ESG + carbon estimation
8. **Financial Advisory Chatbot** — RAG + LangGraph multi-agent
9. **Explainable AI Framework** — SHAP + LIME + narrative layer
10. **Fairness Auditing System** — Comprehensive bias analysis
11. **Experimental Evaluation** — Ablation studies, benchmarks
12. **Conclusion** — Contributions, limitations, future work

---

## Publication Opportunities

| Venue | Type | Deadline | Target Chapter |
|-------|------|----------|----------------|
| Expert Systems With Applications | Journal | Rolling | Full system |
| IEEE Transactions on Neural Networks | Journal | Rolling | ML architecture |
| AAAI 2027 | Conference | Sept 2026 | Fairness contribution |
| ACM FAccT 2027 | Conference | Oct 2026 | Ethics/fairness |
| ECML-PKDD 2026 | Conference | Apr 2026 | Forecasting |

---

## Recruitment Module — Implementation Status (2026-05-28)

The Phase-3 recruitment module (`ml/recruitment/`) is now implemented end-to-end:

| Layer | Module | Status |
|-------|--------|--------|
| Data schema + reproducible loader | `data/{schema,loader}.py` | ✅ |
| Multi-format resume parsing | `parsers/{resume_parser,entity_extractor}.py` | ✅ |
| Structured features | `features/structured.py` (8 features, FEATURE_NAMES) | ✅ |
| Embeddings + cache | `embeddings/{sbert,tfidf,cache,base}.py` | ✅ |
| Ranking models | `models/{baselines,semantic,structured,ensemble,base}.py` | ✅ (6 arms) |
| Evaluation metrics | `evaluation/metrics.py` (pure numpy) | ✅ + 18/18 tests |
| Benchmark harness | `evaluation/benchmark.py` | ✅ |
| SHAP + LIME + narrative | `explainability/` (+ bias decomposition — RC-002) | ✅ |
| Fairness audit + mitigation | `fairness/{auditor,mitigation}.py` | ✅ |
| Reproducibility | `reproducibility/{seed,env}.py` | ✅ |
| MLflow registry | `registry/model_registry.py` | ✅ |
| pgvector index helper | `search/pgvector_index.py` | ✅ (Alembic migration pending) |
| Recruiter copilot (LLM) | `copilot/recruiter_copilot.py` | ✅ |
| Training pipeline + ablation | `training/{config,pipeline,ablation}.py` | ✅ |
| CLI | `cli.py` (`train` / `ablate` / `benchmark`) | ✅ |
| Module README | `ml/recruitment/README.md` | ✅ |

**Architecture decisions captured**: ADR-020 (package layout),
ADR-021 (embedding cache), ADR-022 (uniform `RankingModel` interface),
ADR-023 (linear-blend ensemble over a meta-learner).

**Pending**:
- Live runs in the `ml-dev` container to fill the numerical results in
  EXP-REC-001..004 + AS-001.
- Backend persistence (RecruitmentSession ORM model + Alembic migration)
  so production sessions are saved with their SHAP/fairness outputs.
- Phase-4 adversarial debiasing (AIF360 in-processing) per RC-002.

---

*Last updated: 2026-05-28*
