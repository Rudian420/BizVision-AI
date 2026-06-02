# BizVision AI — Master Roadmap

> **Mission**: Build an elite-level, research-grade, startup-quality AI-powered SME Decision Intelligence Platform — architecturally sophisticated, visually unforgettable, explainable, ethical, and thesis-worthy.

---

## Platform Overview

**BizVision AI** is a unified, multi-agent AI ecosystem for Small & Medium Enterprises comprising five interconnected intelligence modules:

| Module | Domain | Core AI Techniques |
|--------|--------|--------------------|
| Recruitment Intelligence | HR/Hiring | SBERT, XGBoost, SHAP, Fairlearn |
| Smart Pricing Advisor | Pricing Strategy | RL, Monte Carlo, LightGBM |
| Profit Forecasting | Financial Planning | Time Series, LSTM, Prophet |
| Financial Advisory Chatbot | Executive Intelligence | RAG, LangGraph, Multi-Agent |
| Green Business Sustainability Scorer | ESG/Sustainability | Multi-label Classification, AIF360 |

---

## Phase Architecture

```
Phase 0  →  Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6
 Setup      Backend     Frontend    ML Core    XAI+Fair    Advanced    Research+
 & Infra    Core        3D/Cinema   Pipelines  ness        Agents      Thesis
```

---

## PHASE 0 — Foundation & Infrastructure
**Goal**: Establish the engineering foundation — all scaffolding, DevOps, databases, and tooling.

### Milestones
- [x] `PM-001` Project management system created
- [x] `PM-002` Monorepo folder structure scaffolded
- [ ] `PM-003` Docker Compose full stack running _(compose file written; not yet run live)_
- [ ] `PM-004` PostgreSQL + pgvector + Redis + MinIO running
- [x] `PM-005` GitHub Actions CI/CD pipeline configured _(backend + frontend + docker-build + dependabot)_
- [x] `PM-006` Environment configuration system (`.env`, secrets management) _(.env.example + Pydantic settings)_
- [x] `PM-007` Makefile with all developer shortcuts _(targets now backed by real code: seed, alembic, ml pipelines)_
- [ ] `PM-008` MLflow tracking server deployed locally _(compose service defined; not yet run)_

### Deliverables
- `docker-compose.yml` (all services)
- `Makefile` (full developer ergonomics)
- `.env.example` with all required variables
- `setup.sh` / `setup.bat` one-command bootstrap
- `infrastructure/` — nginx, postgres init, redis config

### Risk
- Docker networking complexity with 10+ services → mitigate with named networks

---

## PHASE 1 — Backend Core (FastAPI)
**Goal**: Production-grade async Python API with all module routers, auth, and data models.

### Milestones
- [x] `BE-001` FastAPI app scaffolded with App Router architecture
- [x] `BE-002` JWT authentication system (register/login/refresh/revoke)
- [x] `BE-003` PostgreSQL async models via SQLAlchemy 2.0 _(all 5 modules persisted: User + RefreshToken + Recruitment{Session, CandidateScore, FairnessAuditRecord, CandidateVector} + PricingAnalysis + SustainabilityAssessment + ForecastAnalysis + ChatbotConversation + ChatbotMessage + ChatbotExecutiveReport)_
- [x] `BE-004` Alembic migration system _(`0001_initial_schema` + `0002_pricing_analysis` + `0003_sustainability_assessment` + `0004_forecast_analysis` + `0005_chatbot_conversations` + **`0006_audit_logs`** chained — pgvector ext + **13 tables** + HNSW cosine index + (conv,position) unique constraint + `audit_module` enum + 9 audit_logs indexes including composite (user_id, created_at DESC) + (user_id, module, created_at DESC) for Phase-4 dashboard hot paths)_
- [~] `BE-005` Redis cache layer + session management _(client done; cache decorators pending)_
- [~] `BE-006` Celery async task queue + Flower monitoring _(app + placeholder tasks; real tasks pending)_
- [x] `BE-007` Recruitment Intelligence API router _(persistence real + inference client wired — ADR-024; **audit log recording wired (TASK-028, ADR-031)** — every `/analyze` writes one cross-module audit row with risk_tier + top-K SHAP features + per-attribute fairness pass/fail; flip `RECRUITMENT_USE_REAL_ML` to exercise the real ensemble)_
- [x] `BE-008` Smart Pricing API router _(persistence real + inference client wired for all 4 endpoints — TASK-011, ADR-024 pattern; **audit log recording wired — TASK-029, ADR-031** — every persisted analysis row also writes one audit row from inside `_persist`; flip `PRICING_USE_REAL_ML` in ml-dev to exercise the real LightGBM-grid / PPO policy)_
- [x] `BE-009` Profit Forecasting API router _(persistence real + DB-backed explanation + paged `/history` — TASK-013; **inference client wired** for all 4 endpoints — TASK-016, ADR-024 pattern; **audit log recording wired — TASK-029, ADR-031**; flip `FORECASTING_USE_REAL_ML=true` in ml-dev to exercise real Theta/HoltWinters arms)_
- [x] `BE-010` Financial Chatbot API router (WebSocket + REST) _(persistence real — rich relational pattern per ADR-027 — TASK-014; **inference client wired** for REST `/message` + WS `stream_response` — TASK-020, ADR-024 pattern; **audit log recording wired — TASK-029, ADR-031** — REST `message` / WS `stream_message` / `executive_report` each record a distinct audit row; flip `CHATBOT_USE_REAL_ML=true` in ml-dev to exercise real HashEmbedder + KeywordRouter + RagResponder + AgentExecutor on the synthetic 100-doc corpus)_
- [x] `BE-011` ESG Sustainability Scorer API router _(persistence real + reads-from-DB explanation + per-user 404 — TASK-012; **inference client wired** for `/score` + `/carbon-estimate` — TASK-018, ADR-024 pattern; **audit log recording wired — TASK-029, ADR-031** — `/score` writes risk_tier from composite-score risk_level (LOW/MEDIUM/HIGH/CRITICAL); flip `SUSTAINABILITY_USE_REAL_ML=true` in ml-dev to exercise real `LinearLogisticMultiLabel` + `CarbonEstimatorModel`)_
- [~] `BE-012` Shared Context API (cross-module intelligence bus) _(bus + read API; consumers pending)_
- [x] `BE-013` Observability: structured logging, health endpoints
- [x] `BE-014` Rate limiting + API versioning (`/api/v1/`)
- [ ] `BE-015` pgvector extension for semantic search

### Tech Stack
- FastAPI (async), SQLAlchemy 2.0, Alembic, Pydantic v2, Redis, Celery, JWT (python-jose)

### Deliverables
- Fully documented OpenAPI spec at `/api/v1/docs`
- All 5 module routers with typed request/response schemas

---

## PHASE 2 — Frontend Foundation (Next.js + 3D/Cinematic)
**Goal**: Cinematic, immersive, AI-native frontend that feels like a living intelligence system.

### Milestones
- [x] `FE-001` Next.js 14 App Router project initialized with TypeScript
- [x] `FE-002` TailwindCSS + custom design token system
- [x] `FE-003` React Three Fiber + Drei + Postprocessing setup
- [x] `FE-004` Scroll-driven cinematic system _(Lenis + scene store + segment-keyframed camera, see ADR-018)_
- [x] `FE-005` Framer Motion animation system _(SectionReveal + hero/CTA mask reveals)_
- [ ] `FE-006` Theatre.js timeline orchestration _(deferred to Phase 5; ADR-017)_
- [x] `FE-007` Custom GLSL shader library _(noise, holographic, connection-line — ADR-019)_
- [x] `FE-008` Zustand global state architecture _(`useSceneStore`)_
- [~] `FE-009` React Query data fetching layer _(`makeQueryClient` + `Providers` wired; query hooks pending)_
- [x] `FE-010` Landing page — cinematic hero _(AAA pass: GPU galaxy, holographic planets, energy tendrils, HUD)_
- [x] `FE-014` Adaptive rendering pipeline _(ADR-016 — 3-tier policy table)_
- [x] `FE-011` Authentication pages (login/register) _(TASK-021 — Zustand auth store + persisted refresh tokens + bridged api-client + (auth)/login + (auth)/register on the real `/auth/*` backend; formatAuthError handles string detail / ValidationError[] / 401-409-network)_
- [x] `FE-012` App shell — command center layout _(TASK-021 — `(app)/layout.tsx` wraps `<AuthGuard>` + `<Sidebar>` (per-module accent palette) + `<Topbar>` (user chip + sign-out); `(app)/dashboard` lists modules)_
- [x] `FE-013` Module routing architecture _(TASK-021 — 5 module placeholder routes under `(app)/modules/{recruitment,pricing,forecasting,sustainability,chatbot}/page.tsx`; each pings `/health` and renders a live/down badge; full 3D module UIs land in a later wave behind the same routes)_
- [~] `FE-016` Recruitment module UI _(TASK-022 wave 1 — `RecruitmentWorkspace`: analyze form + ranked-list with collapsible per-row SHAP attribution panel + fairness summary table with risk badge + recommendations; React Query mutation against `/recruitment/analyze`; **TASK-032 wave 2 — `/modules/recruitment/sessions` history list page + `/modules/recruitment/sessions/[id]` persisted detail page (full ranked candidates + reconstructed fairness audit via `/recruitment/fairness/{id}` + audit-feed deep-link via `auditReferenceLink('recruitment_session', id)`)**; 3D constellation visualization defers to wave 3)_
- [~] `FE-017` SHAP/LIME visualization components _(TASK-022 wave 1 → TASK-023 extracted `components/shap/ShapPanel.tsx` + shared `lib/shap/types.ts` SHAPFeature; reused by recruitment + pricing + forecasting (TASK-024) + sustainability (TASK-025); chatbot inherits it; LIME panel pending)_
- [~] `FE-018` Fairness dashboard components _(TASK-022 wave 1 → TASK-025 promoted `RiskBadge` + `lib/risk/{types,tones}` to shared location; `FairnessSummary` per-attribute metrics table with pass/fail chips + interpretation strings + recommendations used by recruitment; RiskBadge now also used by sustainability; intersectional bias-heatmap pending)_
- [~] `FE-019` Pricing module UI _(TASK-023 wave 1 — `PricingWorkspace`: optimize form + recommendation card + SVG-based revenue-curve chart with per-objective y axis (`pickY` selects revenue/profit/volume) + current/recommended price markers + curve marker table + shared SHAP panel; React Query mutation against `/pricing/optimize`; **TASK-033 wave 2 — `/modules/pricing/analyses/[id]` persisted detail page via shared `PersistedAnalysisDetail` + audit-feed deep-link**; **TASK-035 wave 3 — `/modules/pricing/analyses` paged history list via shared `ModuleHistoryShell`**; 3D price-surface defers to wave 4)_
- [~] `FE-020` Forecasting module UI _(TASK-024 wave 1 — `ForecastingWorkspace`: forecast form + scenario cards (ordered base→bull→bear with fractional change vs base) + SVG `ScenarioChart` with PI bands + history baseline + forecast-boundary divider + shared SHAP panel; React Query mutation against `/forecasting/forecast`; geometry helpers (`projectPoint`, `scaleFor`, `polylinePath`, `bandPath`, `isoDateToDayNumber`) extracted to `lib/chart/geometry.ts` and shared with pricing; **TASK-033 wave 2 — `/modules/forecasting/forecasts/[id]` persisted detail page + audit-feed deep-link**; **TASK-035 wave 3 — `/modules/forecasting/forecasts` paged history list**; "temporal rivers" 3D defers to wave 4)_
- [~] `FE-021` Sustainability module UI _(TASK-025 wave 1 — `SustainabilityWorkspace`: score form (company + industry + revenue + headcount + 3 free-form `key: value` indicator textareas; `parseIndicators` tolerates `:` or `=` + whitespace + non-numeric skip) + `CompositeScoreCard` (composite + industry percentile + `RiskBadge` + regulatory chip) + per-pillar 0..100 bar gauges (E ◯ emerald / S ◇ cyan / G □ gold) + shared SHAP panel; risk module promoted to shared `lib/risk/{types,tones}` + `components/common/RiskBadge`; **TASK-033 wave 2 — `/modules/sustainability/assessments/[id]` persisted detail page with RiskBadge slot + audit-feed deep-link**; **TASK-035 wave 3 — new `GET /sustainability/assessments` backend endpoint + `/modules/sustainability/assessments` history list page (per-row RiskBadge for the `score` variant)**; "living city" 3D defers to wave 4)_
- [~] `FE-022` Chatbot module UI _(TASK-026 wave 1 — `ChatbotWorkspace`: two-column layout (active conversation + history rail), `MessageThread` (auto-scroll, typing indicator, latest-response mirror), `MessageBubble` (user-right-cyan / assistant-left-coral / system-centred-dim + collapsible reasoning trace + inline `SourcesList`), `ChatComposer` (4-module context chip multiselect + Cmd/Ctrl-Enter send + plain-Enter newline + 4000-char counter), `ConversationHistoryList` (title preview + module-chip dots + freshness pip + relative-time stamp + "+ new" reset); `useSendMessageMutation` + `useConversationsQuery` + `useConversationQuery` + `chatbotKeys` factory; REST `/message` + paged `/conversations` + `/conversations/{id}`; TASK-027 wave 2 — `lib/chatbot/ws.ts` factory (http→ws / https→wss URL builders + `openChatbotWs` event dispatch through a single `onEvent`, JSON-parse / missing-type errors surfaced through `onError`, constructor-injected `WsCtor` so jsdom tests inject a `MockWebSocket`) + `useChatbotStream` hook (per-conversation WS lifecycle, token concatenation, monotonic tool-call seq, `lastComplete` mirror handoff) + `StreamingAssistantBubble` (blinking caret + tool-call chip strip, layout-stable with persisted bubble at handoff) + workspace routes REST first-send / WS follow-ups (composer locked during either, REST + WS errors merged into one banner); **TASK-034 wave 3 — `/modules/chatbot/messages/[id]` resolves message → conversation_id + auto-redirects with manual fallback + `/modules/chatbot/reports/[id]` executive-report detail (shared `<PersistedAnalysisDetail />`) + workspace reads `?conversation_id=` URL param + page wrapped in `<Suspense>` for useSearchParams**; AI-avatar 3D defers to wave 4)_
- [ ] `FE-015` WebGL performance monitoring + adaptive degradation _(rt FPS feedback into tier downgrades)_

### UI/UX Direction
- Color palette: Deep space (#050A14), Electric cyan (#00F5FF), Neural gold (#FFB800)
- Typography: Space Grotesk (UI), JetBrains Mono (data/code)
- Feel: Cinematic AI OS, Holographic Command Center

### Deliverables
- Landing page with 3D hero
- Authenticated app shell
- Module navigation system

---

## PHASE 3 — ML Core Pipelines (All 5 Modules)
**Goal**: Research-grade ML implementations with full experiment tracking.

### Milestones

#### Recruitment Intelligence (`ml/recruitment/`) — ✅ implemented 2026-05-28
- [x] `ML-REC-001` Resume parser (PDF/DOCX/TXT → CandidateRecord) — `parsers/resume_parser.py`
- [x] `ML-REC-002` SBERT embedding pipeline (mpnet, with cache) — `embeddings/sbert.py`
- [x] `ML-REC-003` Candidate ranking ensemble (SBERT + XGBoost, ADR-023) — `models/ensemble.py`
- [~] `ML-REC-004` Confidence scoring _(per-leg sub_scores live; calibrated confidence pending)_
- [x] `ML-REC-005` MLflow tracking — `training/pipeline.py` + `reproducibility/env.py`
- [x] `ML-REC-006` Benchmark: AUC, NDCG@k, MRR (+ MAP@k, P@k, R@k, Spearman) — `evaluation/metrics.py` + 18 tests
- [x] `ML-REC-007` SHAP + LIME + narrative explainability (+ bias decomposition RC-002) — `explainability/`
- [x] `ML-REC-008` Intersectional fairness audit + mitigation — `fairness/{auditor,mitigation}.py`
- [x] `ML-REC-009` Recruiter copilot (LLM, structured I/O) — `copilot/recruiter_copilot.py`
- [x] `ML-REC-010` AS-001 ablation runner (6 arms × 3 seeds × 2 sizes) — `training/ablation.py`
- [ ] `ML-REC-011` Live runs in `ml-dev` to fill EXP-REC-001..004 numerical results
- [ ] `ML-REC-012` Alembic migration for `candidate_vector` table (pgvector) + backend persistence

#### Smart Pricing Advisor (`ml/pricing/`) — ✅ implemented 2026-05-29
- [x] `ML-PRC-001` Price elasticity estimation — `models/elasticity.py` (ConstantElasticityEstimator + ElasticityOptimalPolicy)
- [x] `ML-PRC-002` LightGBM demand forecasting model — `models/demand.py` (LightGBMDemandModel + LightGBMGridPolicy, EXP-PRC-001)
- [x] `ML-PRC-003` Monte Carlo price simulation engine — `models/monte_carlo.py` (MonteCarloSimulator)
- [x] `ML-PRC-004` Reinforcement Learning pricing agent (PPO) — `models/rl_agent.py` (PPOPricingPolicy over constant-elasticity env, ADR-026)
- [x] `ML-PRC-005` Scenario comparison engine — via `MonteCarloSimulator` + `LightGBMGridPolicy` revenue curve
- [x] `ML-PRC-006` Benchmark: Revenue uplift, MAPE, Sharpe ratio, VaR, win rate — `evaluation/{metrics,benchmark}.py` (+ 18 offline tests)
- [x] `ML-PRC-007` SHAP attribution for LightGBM demand — `explainability/shap_adapter.py`
- [x] `ML-PRC-008` Pricing copilot (LLM, structured I/O) — `copilot/pricing_copilot.py`
- [x] `ML-PRC-009` AS-002 ablation runner (5 arms × 3 seeds × 2 sizes) — `training/ablation.py`
- [ ] `ML-PRC-010` Live runs in `ml-dev` to fill EXP-PRC-001..003 numerical results
- [x] `ML-PRC-011` `PricingInferenceClient` mirroring ADR-024 — backend ↔ ml.pricing for all 4 endpoints (TASK-011)

#### Profit Forecasting (`ml/forecasting/`) — ✅ classical-arms wave implemented 2026-05-29
- [x] `ML-FOR-001` Time series feature engineering pipeline — `features/temporal.py` (lag/rolling/calendar, stable column order)
- [~] `ML-FOR-002` Ensemble: classical arms shipped (NaiveLast/NaiveSeasonal/HoltWinters/Theta) — `models/{baselines,exp_smoothing,theta}.py`; LSTM/Prophet/XGBoost arms join later behind same `ForecastModel` ABC
- [x] `ML-FOR-003` Multi-scenario simulation (base/bull/bear) — backend route already exposes scenarios; ensemble arms here power the underlying point forecast
- [~] `ML-FOR-004` Sensitivity analysis + tornado charts — backend `/sensitivity` is wired (mock); LightGBM SHAP attribution arrives with ML-FOR-002 expansion
- [ ] `ML-FOR-005` Cross-module data integration (pricing + recruitment signals)
- [x] `ML-FOR-006` Benchmark: MAPE, RMSE, MASE, Winkler score (PI), coverage — `evaluation/{metrics,benchmark}.py` + rolling-origin backtest (+ 29 offline tests)
- [x] `ML-FOR-007` AS-003 ablation runner — `training/ablation.py` (4 arms × N seeds × rolling-origin folds, MLflow logged)
- [x] `ML-FOR-008` Forecast copilot (LLM, structured I/O) — `copilot/forecast_copilot.py`
- [x] `ML-FOR-009` `ForecastingInferenceClient` mirroring ADR-024 — backend ↔ ml.forecasting for the 3 model-backed endpoints (TASK-016); `/sensitivity` stays closed-form

#### Green Business Scorer (`ml/sustainability/`) — ✅ classical-arms wave implemented 2026-05-29
- [x] `ML-ESG-001` ESG feature extraction pipeline — `features/structured.py` (12 dims, stable column order, pillar means + industry one-hot + scale features)
- [~] `ML-ESG-002` Multi-label sustainability classifier — classical arms shipped (`MajorityLabelScorer` / `IndustryBaselineScorer` / `LinearLogisticMultiLabel` with hand-implemented GD + z-standardisation); GBT / chain-classifier arms join later behind same `ESGScorer` ABC
- [x] `ML-ESG-003` Carbon footprint estimation model — `models/carbon.py` (Scope 1/2/3 decomposition, industry-intensity table + EIA/EPA emission factors, reduction-pathway ranking)
- [x] `ML-ESG-004` Industry benchmarking system — `evaluation/benchmark.py` + AS-004 ablation harness + industry-aware fixture loader
- [x] `ML-ESG-005` Sustainability improvement recommender — `copilot/esg_copilot.py` (LLM with structured I/O + deterministic fallback)
- [x] `ML-ESG-006` Benchmark: F1 macro, accuracy, Hamming loss, Brier score, ECE — `evaluation/{metrics,benchmark}.py` (+ 17 offline tests)
- [x] `ML-ESG-007` AS-004 ablation runner — `training/ablation.py` (3 arms × N seeds × 3-fold benchmark, MLflow logged)
- [x] `ML-ESG-008` Industry fairness audit (Disparate Impact + Demographic Parity Difference + EEOC four-fifths rule) — `fairness/auditor.py` (NEW sub-module; industry as protected attribute, parallel to recruitment's intersectional audit per ADR-022/RC-002)
- [x] `ML-ESG-009` Linear-SHAP adapter (closed-form in standardised feature space) — `explainability/shap_adapter.py`
- [x] `ML-ESG-010` `SustainabilityInferenceClient` mirroring ADR-024 — backend ↔ ml.sustainability for `/score` + `/carbon-estimate` (TASK-018); `/simulate`, `/recommendations`, `/benchmarks/{industry}` stay closed-form / reference-data

#### Financial Chatbot (`ml/chatbot/`) — ✅ wave-1 classical-arms implemented 2026-05-29
- [~] `ML-BOT-001` RAG pipeline (pgvector + HuggingFace embeddings) — wave-1 shipped: HashEmbedder + NumpyVectorStore + RagRetriever behind `EmbeddingClient` / `VectorStore` ABCs (`embeddings/`, `retrieval/`); SBERT + pgvector remain as wave-2 swap-ins
- [~] `ML-BOT-002` LangGraph multi-agent orchestration — wave-1 shipped: KeywordRouterAgent + RagResponderAgent + AgentExecutor behind `BaseAgent` ABC (`agents/`); LangGraph orchestration + LLM-generated responder remain as wave-2 swap-ins
- [x] `ML-BOT-003` Tool-use integration (call module APIs) — `ToolRegistry` + 5 default stub tools (one per BizVision module); wave-2 mutates the registry to register real backend-facing handlers
- [x] `ML-BOT-004` Conversational memory system — backend persistence (TASK-014, ADR-027) already provides rich relational thread history with deterministic `(conversation_id, position)` ordering; ML side reads via the API
- [x] `ML-BOT-005` Structured output generation (reports, charts) — `AgentResponse` + `explainability/trace.py` produce JSON-friendly source/tool-call payloads + one-line interpretation string; copilot's `ChatBriefing` adds headline / key_points / follow-ups
- [x] `ML-BOT-006` Benchmark: Recall@k, MRR, NDCG@k, routing accuracy — `evaluation/{metrics,benchmark.py}` (+ 17 offline tests)
- [x] `ML-BOT-007` AS-005 ablation runner — `training/ablation.py` (RagOnly vs RouterPlusRag × N seeds, MLflow logged)
- [x] `ML-BOT-008` Chat copilot (LLM, structured I/O) — `copilot/chat_copilot.py`
- [x] `ML-BOT-009` `ChatbotInferenceClient` mirroring ADR-024 — backend ↔ ml.chatbot for REST `/message` + WS `stream_response` (TASK-020); `/executive-report` stays closed-form / static-catalog

---

## PHASE 4 — Explainable AI + Fairness Auditing
**Goal**: Become a reference implementation of responsible, transparent AI.

### Milestones
- [ ] `XAI-001` SHAP dashboard — global feature importance + force plots
- [ ] `XAI-002` LIME local explanations for individual predictions
- [ ] `XAI-003` Narrative explanation generator (LLM-powered rationale)
- [ ] `XAI-004` Interactive causal graph visualization (D3.js)
- [ ] `XAI-005` Feature attribution heatmaps (3D visualization)
- [ ] `FAIR-001` Fairlearn integration — demographic parity, equalized odds
- [ ] `FAIR-002` IBM AIF360 bias detection and mitigation
- [~] `FAIR-003` Fairness dashboard with bias heatmaps _(wave 1 backend primitive `/api/v1/audits/summary` from TASK-028 exposes per-module + per-risk-tier histograms; **TASK-030 ML Decision Feed (`/decisions` route) renders them**; **TASK-031 adds `/api/v1/audits/fairness` + `FairnessByAttributeCard`** rendering per-protected-attribute pass rates with 4/5ths-rule tier colouring; intersectional cells (attribute × metric × group) still pending as a richer aggregation grain)_
- [x] `FAIR-004` Audit log system for all AI decisions _(TASK-028 + TASK-029, ADR-031 — append-only `audit_logs` table + `AuditService` (record/list/get/summary) + `/api/v1/audits` API surface (GET-only by design); **all 5 modules wired (5/5)** — recruitment / pricing / forecasting / sustainability each record through their `_persist` helper; chatbot records through 3 distinct paths (REST `message` / WS `stream_message` / `executive_report`); 122/122 unit tests pass + 5 new integration tests cover per-module wiring + cross-module summary aggregation)_
- [ ] `FAIR-005` Model cards + dataset cards (per module)
- [ ] `FAIR-006` Adversarial fairness testing suite

---

## PHASE 5 — Advanced Modules (3D Experiences + AI Agents)
**Goal**: Cinematic module UIs and multi-agent AI orchestration.

### Milestones

#### 3D Module Experiences
- [ ] `3D-001` Recruitment — 3D candidate constellation visualization
- [ ] `3D-002` Pricing — Holographic price surface + elasticity wave
- [ ] `3D-003` Forecasting — Animated financial timeline with scenario branches
- [ ] `3D-004` Sustainability — Living ESG ecosystem visualization
- [ ] `3D-005` Chatbot — Pulsating neural AI avatar with reasoning streams

#### Multi-Agent System
- [ ] `AGT-001` Recruitment AI Agent (autonomous resume analysis)
- [ ] `AGT-002` Pricing AI Agent (autonomous optimization)
- [ ] `AGT-003` Forecasting AI Agent (autonomous scenario generation)
- [ ] `AGT-004` Sustainability AI Agent (autonomous ESG recommendations)
- [ ] `AGT-005` Executive Intelligence Agent (cross-module synthesis)
- [ ] `AGT-006` Agent orchestration UI (CrewAI/LangGraph visualization)

---

## PHASE 6 — Research, MLOps & Thesis Preparation
**Goal**: Production-ready deployment, reproducible research, thesis documentation.

### Milestones
- [ ] `RES-001` Comprehensive ablation studies (all modules)
- [ ] `RES-002` Statistical validation (confidence intervals, significance tests)
- [ ] `RES-003` Benchmark against baselines (rule-based, single models)
- [ ] `RES-004` Error analysis + failure mode documentation
- [ ] `RES-005` MLflow full experiment archive
- [ ] `OPS-001` Kubernetes deployment manifests (production-grade)
- [ ] `OPS-002` Prometheus + Grafana monitoring dashboards
- [ ] `OPS-003` Render + Vercel production deployment
- [ ] `THESIS-001` Research methodology chapter (contribution framing)
- [ ] `THESIS-002` System architecture chapter
- [ ] `THESIS-003` Experimental evaluation chapter
- [ ] `THESIS-004` Ethical AI chapter

---

## Dependency Graph

```
Phase 0 (Infra)
    ├── Phase 1 (Backend)
    │       ├── Phase 3 (ML Pipelines)
    │       │       └── Phase 4 (XAI + Fairness)
    │       │               └── Phase 6 (Research)
    │       └── Phase 5 (Agents)
    └── Phase 2 (Frontend)
            └── Phase 5 (3D Experiences)
```

---

## Timeline Estimate

| Phase | Duration | Complexity |
|-------|----------|------------|
| Phase 0 | 2-3 days | High (infra) |
| Phase 1 | 1-2 weeks | Very High |
| Phase 2 | 2-3 weeks | Extreme (3D/WebGL) |
| Phase 3 | 2-4 weeks | Extreme (5 ML systems) |
| Phase 4 | 1-2 weeks | Very High (XAI) |
| Phase 5 | 2-3 weeks | Extreme (3D + Agents) |
| Phase 6 | 1-2 weeks | High (Research) |

**Total: ~3-4 months of focused engineering**

---

*Last updated: 2026-05-28 | Phase: 1 (Backend Core) | Status: Backend bootable — auth real, module services typed-mock; next is persistence + Alembic, then Phase 3 ML*

> Legend: `[x]` done · `[~]` partial · `[ ]` not started
