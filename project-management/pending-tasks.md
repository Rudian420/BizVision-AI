# BizVision AI — Pending Tasks

> Prioritized implementation queue. Updated every session.

---

## Priority Legend
- 🔴 **CRITICAL** — Blocks other tasks
- 🟠 **HIGH** — Core functionality
- 🟡 **MEDIUM** — Important but not blocking
- 🟢 **LOW** — Enhancement / stretch goal

---

## Phase 0 — Infrastructure ✅ COMPLETE (2026-05-28)

> All Phase-0 items done in TASK-004. Plus added beyond the original list:
> monorepo orchestration (npm workspaces + Turborepo), `@bizvision/contracts`,
> pyproject (ruff/mypy/pytest), pre-commit, Alembic, observability stack
> (Prometheus/Grafana), `.env`/`.npmrc`/`.editorconfig`, VS Code workspace.

| ID | Status | Task | Notes |
|----|--------|------|-------|
| `INF-001` | ✅ | Full monorepo folder structure | frontend/backend/ml/packages/infrastructure |
| `INF-002` | ✅ | `docker-compose.yml` (all services) | + `ml-dev` (profile ml) & monitoring profile |
| `INF-003` | ✅ | Backend `Dockerfile` (Python 3.11) | pre-existing |
| `INF-004` | ✅ | Frontend `Dockerfile` (Node 20) | pre-existing |
| `INF-005` | ✅ | ML `Dockerfile` | CPU base; swap to CUDA for GPU |
| `INF-006` | ✅ | PostgreSQL init + pgvector | `infrastructure/postgres/init.sql` |
| `INF-007` | ✅ | MLflow service | compose + `ml/shared/mlflow_utils.py` |
| `INF-008` | ✅ | MinIO S3 service | compose |
| `INF-009` | ✅ | Makefile | pre-existing; targets now backed by real code |
| `INF-010` | ✅ | setup bootstrap | `setup.sh` + new `setup.ps1`/`setup.bat` |
| `INF-011` | ✅ | GitHub Actions CI | backend + frontend + docker-build + dependabot |
| `INF-012` | ✅ | Nginx reverse proxy | `infrastructure/nginx/nginx.conf` |
| `INF-013` | ✅ | Alembic migration env (async) | `versions/` empty — first migration is Phase 1 |
| `INF-014` | ✅ | Observability (Prometheus `/metrics` + Grafana) | `core/observability.py` + monitoring profile |

---

## Phase 1 — Backend Core

> **Status key:** ✅ done · 🟡 partial (mock/needs real impl) · ⬜ not started

| ID | Status | Priority | Task | Notes |
|----|--------|----------|------|-------|
| `BE-001` | ✅ | 🔴 | FastAPI application factory pattern | `create_application()` in main.py |
| `BE-002` | ✅ | 🔴 | Pydantic settings (env-based config) | `core/config.py` |
| `BE-003` | ✅ | 🔴 | PostgreSQL async engine + session factory | `core/database.py` |
| `BE-004` | ✅ | 🔴 | SQLAlchemy models (all entities) | All 5 modules persisted: Recruitment{Session,CandidateScore,FairnessAuditRecord,CandidateVector} + PricingAnalysis + SustainabilityAssessment + ForecastAnalysis + ChatbotConversation + ChatbotMessage + ChatbotExecutiveReport |
| `BE-005` | ✅ | 🔴 | Alembic migration system | `0001_initial_schema` (pgvector ext + HNSW index) + `0002_pricing_analysis` + `0003_sustainability_assessment` + `0004_forecast_analysis` + `0005_chatbot_conversations` chained (12 tables total) |
| `BE-006` | ✅ | 🔴 | JWT auth system (register/login/refresh/logout) | `auth_service.py` — Redis-backed refresh rotation |
| `BE-007` | 🟡 | 🟠 | Redis connection + cache decorators | `core/redis.py` done; cache decorators pending |
| `BE-008` | 🟡 | 🟠 | Celery worker + task definitions | `celery_app.py` + placeholder `tasks/ml.py`; real tasks pending |
| `BE-009` | 🟢 | 🔴 | Recruitment Intelligence router | persistence real + inference client wired (ADR-024) + **audit log recording wired (TASK-028, ADR-031)** — every `/analyze` writes one cross-module audit row with risk_tier + top-K SHAP + fairness pass/fail; flip `RECRUITMENT_USE_REAL_ML=true` in ml-dev to exercise the real ensemble |
| `BE-010` | 🟢 | 🔴 | Smart Pricing router | persistence real + inference client wired (TASK-011, ADR-024 pattern, all 4 endpoints) **+ audit log recording wired (TASK-029, ADR-031)** — every persisted row also writes one audit row; flip `PRICING_USE_REAL_ML=true` in ml-dev to exercise the real LightGBM-grid / PPO policy |
| `BE-011` | 🟢 | 🔴 | Profit Forecasting router | persistence real + DB-backed explanation + paged `/history` (TASK-013) **+ inference client wired** for all 4 endpoints (TASK-016, ADR-024 pattern) **+ audit log recording wired (TASK-029, ADR-031)**; flip `FORECASTING_USE_REAL_ML=true` in ml-dev to exercise the real Theta / HoltWinters arms |
| `BE-012` | 🟢 | 🔴 | Financial Chatbot router (WebSocket) | persistence real (rich relational, ADR-027) + WS persists turns deterministically via `(conversation_id, position)` unique + user-scoped /conversations + executive-report persisted per call (TASK-014) **+ inference client wired** for REST `/message` + WS `stream_response` (TASK-020, ADR-024 pattern) **+ audit log recording wired (TASK-029, ADR-031)** — REST + WS + executive-report each record distinct audit rows (`message` / `stream_message` / `executive_report`); flip `CHATBOT_USE_REAL_ML=true` in ml-dev to exercise the real HashEmbedder + KeywordRouter + RagResponder + AgentExecutor on the synthetic 100-doc corpus |
| `BE-013` | 🟢 | 🔴 | ESG Sustainability router | persistence real + reads-from-DB explanation + per-user 404 (TASK-012) **+ inference client wired** for `/score` and `/carbon-estimate` (TASK-018, ADR-024 pattern) **+ audit log recording wired (TASK-029, ADR-031)** — `/score` records risk_tier from composite-score risk_level; flip `SUSTAINABILITY_USE_REAL_ML=true` in ml-dev to exercise real `LinearLogisticMultiLabel` + `CarbonEstimatorModel` |
| `BE-014` | 🟡 | 🟠 | Shared Context Bus (cross-module signals) | `SharedContextBus` pub/sub + recent-signals; consumers pending |
| `BE-015` | ✅ | 🟡 | Structured logging + observability | `core/logging.py` (Loguru) + request-id/timing middleware |
| `BE-016` | ✅ | 🟡 | Rate limiting middleware | `middleware/rate_limiter.py` (Redis + fallback) |
| `BE-017` | 🟡 | 🟡 | API documentation enhancement | OpenAPI auto-gen live; examples/tags polish pending |

---

## Phase 2 — Frontend

| ID | Priority | Task | Complexity | Dependencies |
|----|----------|------|------------|--------------|
| `FE-001` | 🔴 | Next.js 14 project init with TypeScript | Low | INF-001 |
| `FE-002` | 🔴 | TailwindCSS + design token system | Medium | FE-001 |
| `FE-003` | 🔴 | React Three Fiber + Drei setup | Medium | FE-001 |
| `FE-004` | 🔴 | GSAP + ScrollTrigger integration | Medium | FE-001 |
| `FE-005` | 🟠 | Framer Motion animation system | Medium | FE-001 |
| `FE-006` | 🟠 | Zustand store architecture | Medium | FE-001 |
| `FE-007` | 🟠 | React Query setup + API client | Medium | FE-001 |
| `FE-008` | 🔴 | Landing page 3D hero (neural galaxy) | Very High | FE-003, FE-004 |
| `FE-009` | ✅ | App shell layout (command center) | High | done in TASK-021 — `<AuthGuard>` + `<Sidebar>` + `<Topbar>` in `(app)/layout.tsx`; module-routing scaffold + dashboard landing |
| `FE-010` | ✅ | Auth pages (login/register) | Medium | done in TASK-021 — Zustand auth store + bridged api-client + (auth)/login + (auth)/register on the real `/auth/*` backend |
| `FE-011` | 🟢 | Recruitment module UI + 3D constellation | Very High | wave 1 done in TASK-022 — `RecruitmentWorkspace`: analyze form + ranked list + per-candidate SHAP panel + fairness summary on the real `/recruitment/analyze`; **wave 2 done in TASK-032** — `/modules/recruitment/sessions` history list + `/modules/recruitment/sessions/[id]` persisted detail (full ranked candidates + reconstructed fairness audit) + audit-feed deep-link wire; 3D constellation defers to wave 3 |
| `FE-012` | 🟢 | Pricing module UI + 3D price surface | Very High | wave 1 done in TASK-023 — `PricingWorkspace`: optimize form + recommendation card + SVG-based revenue-curve chart with per-objective y axis + curve marker table + shared SHAP panel; **wave 2 done in TASK-033** — `/modules/pricing/analyses/[id]` persisted detail page (polymorphic-table renderer via shared `PersistedAnalysisDetail`) + audit-feed deep-link via `auditReferenceLink('pricing_analysis', id)`; **wave 3 done in TASK-035** — `/modules/pricing/analyses` paged history list page via shared `ModuleHistoryShell`; 3D price-surface defers to wave 4 |
| `FE-013` | 🟢 | Forecasting module UI + temporal rivers | Very High | wave 1 done in TASK-024 — `ForecastingWorkspace`: forecast form + scenario cards (ordered base→bull→bear with fractional change vs base) + SVG ScenarioChart with PI bands + history baseline + forecast-boundary divider + primary drivers via shared SHAP panel; geometry helpers extracted to `lib/chart/geometry.ts` (shared with pricing); **wave 2 done in TASK-033** — `/modules/forecasting/forecasts/[id]` persisted detail page + audit-feed deep-link via `auditReferenceLink('forecast_analysis', id)`; **wave 3 done in TASK-035** — `/modules/forecasting/forecasts` paged history list page via shared `ModuleHistoryShell`; "temporal rivers" 3D defers to wave 4 |
| `FE-014` | 🟢 | Sustainability module UI + living city | Very High | wave 1 done in TASK-025 — `SustainabilityWorkspace`: score form (company + industry + revenue + headcount + 3 free-form `key: value` indicator textareas) + composite score card with `RiskBadge` + industry percentile + regulatory chip + per-pillar 0..100 bar gauges (E/S/G accents) + shared SHAP; risk module promoted to shared `lib/risk` + `components/common/RiskBadge`; **wave 2 done in TASK-033** — `/modules/sustainability/assessments/[id]` persisted detail page (with RiskBadge slot from `risk_level`) + audit-feed deep-link via `auditReferenceLink('sustainability_assessment', id)`; **wave 3 done in TASK-035** — new `GET /sustainability/assessments` paged list backend endpoint + `/modules/sustainability/assessments` history list page (with RiskBadge per row for `score` variant); "living city" 3D defers to wave 4 |
| `FE-015` | 🟢 | Chatbot module UI + AI avatar | Very High | wave 1 done in TASK-026 — `ChatbotWorkspace`: message thread (auto-scroll + typing indicator) + composer (Cmd/Ctrl-Enter send + 4-module context chips + 4000-char counter) + right-rail conversation history (title preview + module-chip dots + freshness pip) + inline SourcesList per assistant turn; REST `/message` + paged `/conversations` + `/conversations/{id}` via auth-bridged apiClient; **wave 2 streaming done in TASK-027** — `lib/chatbot/ws.ts` factory (URL builders http→ws / https→wss / trailing-slash trim + `openChatbotWs` event dispatch via constructor-injected `WsCtor`) + `useChatbotStream` hook (per-conversation lifecycle, token concatenation, monotonic tool-call seq, `lastComplete` mirror handoff) + `StreamingAssistantBubble` (caret + tool-call chip strip, layout-stable with persisted bubble) + workspace routes REST first-send / WS follow-ups; **wave 3 done in TASK-034** — `/modules/chatbot/messages/[id]` deep-link landing (resolves message → conversation_id, auto-redirects with manual fallback) + `/modules/chatbot/reports/[id]` executive-report detail (shared `<PersistedAnalysisDetail />`) + workspace reads `?conversation_id=` URL param + Suspense boundary at the page level; AI-avatar 3D defers to wave 4 |
| `FE-016` | 🟢 | SHAP/LIME visualization components | High | SHAP wave 1 done in TASK-022/023 — extracted to `components/shap/ShapPanel.tsx` + shared `lib/shap/types.ts` SHAPFeature; now reused by **all 5 modules** (recruitment + pricing + forecasting + sustainability + chatbot via SourcesList); **TASK-030 ML Decision Feed renders `explanation_summary` from `/audits` via `AuditDetailPanel`**; **TASK-044 LIME wave 1 — `PricingLIMEExplainer` + pricing top_lime_features + `<LimePanel>` (violet/gold) wired into `<PricingResults>`**; **TASK-047 LIME wave 2 — sustainability `LinearLogisticMultiLabel` `<LimePanel>` mounted in `<ESGResults>`**; **TASK-048 LIME wave 3 — recruitment `CandidateRankingResult.top_lime_features` + `_mock_lime_attrs()` helper emits 3 rule-style attributions; `<LimePanel>` mounted in `<CandidateRow>` drawer**. **Wave 3a closed in TASK-049** — `RecruitmentInferenceClient` now captures the XGBoost arm + training-feature matrix during synthetic-bootstrap, lazily builds `LIMERecruitmentExplainer`, computes per-candidate LIME features in `score_candidates`, and threads them through `ml_score_to_api_ranking(..., lime_by_candidate=...)`. Rule-style names from `LIMERule.condition` (e.g. `"years_experience > 5"`) round-trip verbatim. Per-candidate failures swallow to empty so a flaky explainer can't tank the batch. **MLflow registry path closed in TASK-052** — new `ml/recruitment/registry/lime_companions.py` defines a 2-file on-disk contract (`xgb_ranker.joblib` + `background.npy` under `lime_companions/`); `register_run` optionally logs them as side-artifacts; `_load_from_registry` returns a 4-tuple with the rehydrated companions; `_load_ranker` threads them in symmetrically with synthetic-bootstrap. 5 roundtrip unit tests cover the contract. **Micro-follow-up TASK-053** — the recruitment training CLI doesn't pass the kwargs through yet; one-line wire-up in the `register` step. Persisted-row reconstruction (history detail) — **closed in TASK-050**: alembic `0007_candidate_scores_lime` migration adds the symmetric `top_lime_features JSONB NOT NULL DEFAULT '[]'` column; `_persist_session` writes it next to SHAP; `get_session_detail` reconstructs it via `SHAPFeatureAttribution(**f)`; existing integration test extended in place with 3 LIME round-trip assertions (truthy, length-3 per candidate, rule-style names containing `>`). Forecasting Theta (no perturbation room — research question) and chatbot RAG (gated on LLM key + only meaningful with a real generator) remain explicit non-goals for FE-016. |
| `FE-017` | 🟢 | Fairness dashboard components | High | wave 1 done in TASK-022 → TASK-025 promoted `RiskBadge` + `lib/risk/{types,tones}` to shared location; `FairnessSummary` (per-attribute metrics table + pass/fail chips + recommendations) used by recruitment, RiskBadge now reused by sustainability + **TASK-030 ML Decision Feed + TASK-031 `FairnessByAttributeCard` (per-protected-attribute pass-rate bars with 4/5ths-rule tier colouring)**; **TASK-043 `IntersectionalFairnessGrid` — per-`(attribute × metric)` matrix with tone-coded pass-rate cells + avg-value / threshold context — mounted side-by-side with `FairnessByAttributeCard` in the Decision Feed**. Per-group cells (e.g. female / male / non-binary slices within each cell) still pending — requires write-side change in the recruitment fairness auditor to emit per-group metric values inside `fairness_summary.attributes[*].metrics[*].by_group[*]`. |
| `FE-023` | ✅ | ML Decision Feed dashboard | High | done in TASK-030 — `/decisions` route + `DecisionFeedWorkspace` (3-card summary band + 2 filter strips + paged timeline + in-row detail panel) + sidebar entry; pure consumer of `/api/v1/audits` + `/api/v1/audits/summary` |
| `FE-018` | 🟡 | Adaptive rendering pipeline | High | FE-003 |
| `FE-019` | 🟡 | Custom GLSL shader library | Very High | FE-003 |

---

## Phase 3 — ML Pipelines

| ID | Priority | Task | Complexity | Dependencies |
|----|----------|------|------------|--------------|
| `ML-001` | 🟠 | MLflow tracking integration (all modules) | Medium | INF-007 — **chronic-restart loop patched in TASK-051** (added `minio-init` one-shot bucket bootstrap + inline `pip install psycopg2-binary + boto3` in MLflow `command` + healthcheck + `depends_on` chain; see [[adr-036]]). Patch is unverified at runtime (Docker daemon still degraded). Once user verifies `docker compose ps mlflow` shows `(healthy)`, flipping `BIZVISION_SKIP_MLFLOW=0` lights up: real experiment tracking for `ml.*.training.train_pipeline`, AS-001..005 ablation runs, and the recruitment LIME MLflow registry path (TASK-049 left empty by design). |
| `ML-002` | 🔴 | Synthetic data generators (all 5 modules) | High | None |
| `ML-003` | ✅ | Resume parser (PDF → JSON) | Closed in TASK-045 — `ResumeParser` (pypdf / python-docx / UTF-8 with `EntityExtractor` for skills/years/education) wired through `RecruitmentService.process_cv_uploads` behind a process-wide singleton; `/upload-cvs` now returns a typed `UploadCVsResponse` with parsed `cv_text` + `skills` + `years_experience` + `education_level` per file plus a per-file `error` so one bad upload doesn't tank the batch. 4 unit tests cover happy-path TXT, unsupported extension, empty upload, unique-`file_id`. **FE-022 closed in TASK-046** — `<CVUploadDropzone>` + `uploadCVs()` client + `mergeCandidates()` mounted in `<AnalyzeForm>` (20/20 Vitest cases pass); the user can now drag-drop CVs into the recruitment workspace and they flow end-to-end through the real ML pipeline. |
| `ML-004` | 🔴 | SBERT embedding pipeline | High | ML-001 |
| `ML-005` | 🔴 | Recruitment ensemble model | Very High | ML-003, ML-004 |
| `ML-006` | ✅ | Pricing LightGBM model | `ml.pricing.models.demand.LightGBMDemandModel` + `LightGBMGridPolicy` (EXP-PRC-001) |
| `ML-007` | ✅ | RL pricing agent (PPO) | `ml.pricing.models.rl_agent.PPOPricingPolicy` over constant-elasticity env (EXP-PRC-002 / RC-003, ADR-026) |
| `ML-008` | 🟢 | Forecasting hybrid ensemble | Very High | classical-arms slice shipped via `ml.forecasting` (NaiveLast / NaiveSeasonal / HoltWinters / Theta) — TASK-015, ADR-028. LSTM / Prophet / XGBoost arms join later behind the same `ForecastModel` ABC. |
| `ML-009` | 🟢 | ESG multi-label classifier | High | classical-arms slice shipped via `ml.sustainability` (LinearLogisticMultiLabel + Industry/Majority baselines + CarbonEstimatorModel + industry fairness audit) — TASK-017, ADR-029. GBT / chain-classifier arms join later behind the same `ESGScorer` ABC. |
| `ML-010` | 🟢 | RAG pipeline (embeddings + pgvector) | High | wave-1 RAG classical-arms slice shipped via `ml.chatbot` (HashEmbedder + NumpyVectorStore + RagRetriever) — TASK-019, ADR-030. SBERT + pgvector remain as wave-2 work behind the `EmbeddingClient` / `VectorStore` ABCs. |
| `ML-011` | 🟢 | LangGraph chatbot agent | Very High | wave-1 multi-agent classical-arms slice shipped via `ml.chatbot` (KeywordRouter + RagResponder + AgentExecutor + ToolRegistry) — TASK-019, ADR-030. LangGraph orchestration + LLM-generated responder remain as wave-2 work behind the `BaseAgent` ABC. |

---

## Phase 4 — XAI + Fairness

| ID | Priority | Task | Complexity | Dependencies |
|----|----------|------|------------|--------------|
| `XAI-001` | 🟠 | SHAP integration (all ML models) | High | Phase 3 |
| `XAI-002` | 🟠 | LIME integration | High | Phase 3 |
| `XAI-003` | 🟡 | Narrative explanation generator | High | XAI-001 |
| `FAIR-001` | 🟠 | Fairlearn fairness metrics | High | Phase 3 |
| `FAIR-002` | 🟠 | AIF360 bias detection + mitigation | High | Phase 3 |
| `FAIR-003` | 🟢 | Fairness dashboard backend APIs | wave 1 done in TASK-031 — `/api/v1/audits/fairness` per-attribute pass-rate aggregation + `FairnessByAttributeCard` on the Decision Feed; recruitment audit slice now carries structured per-attribute rollup with each metric's value/threshold/passed; intersectional cells (per attribute × metric × group) still pending as a richer aggregation grain |
| `FAIR-004` | ✅ | Audit log system | Done in TASK-028 + TASK-029 (ADR-031) — append-only `audit_logs` table + `AuditService` + `/api/v1/audits` GET/list/summary/detail; **all 5 modules wired (5/5)** — recruitment/pricing/forecasting/sustainability/chatbot each record one audit row per persisted analysis row through their `_persist` helper; chatbot has 3 paths (REST `message` / WS `stream_message` / `executive_report`) |

---

## Stretch Goals / Advanced Features

| ID | Priority | Task | Complexity |
|----|----------|------|------------|
| `ADV-001` | 🟢 | WebGPU rendering pipeline | Extreme |
| `ADV-002` | 🟢 | Real-time collaborative sessions | Very High |
| `ADV-003` | 🟢 | Kafka event streaming | Very High |
| `ADV-004` | 🟢 | Kubernetes production deployment | Very High |
| `ADV-005` | 🟢 | Grafana + Prometheus monitoring | High |
| `ADV-006` | 🟢 | Mobile PWA version | High |
| `ADV-007` | 🟢 | Voice interface for chatbot | High |
| `ADV-008` | 🟢 | Digital twin business simulation | Extreme |

---

*Last updated: 2026-05-31 | Current focus: **Phase 1 persistence COMPLETE (5/5)** + **Phase 3 ML packages COMPLETE (5/5)** + **Backend↔ML inference COMPLETE (5/5)** + **Frontend module UIs COMPLETE (5/5)** + **Cross-module audit log fully wired (5/5 modules — TASK-028 + TASK-029, ADR-031)** + **ML Decision Feed dashboard live at `/decisions` (TASK-030 + TASK-038, FE-023)** + **Per-protected-attribute fairness aggregation (TASK-031, FAIR-003 wave 1)** + **Per-module deep-link 5/5 wired (TASK-032 + TASK-033 + TASK-034)** + **Per-module history list pages 4/4 wired (TASK-032 + TASK-035)** + **History UX polish (TASK-036) — workspace "Past X →" links + analysis_type chip filters** + **Date-range filter on all 4 list pages + Decision Feed (TASK-037 + TASK-038) — `since`/`until` end-to-end** + **Quick-range presets on `<DateRangeFilter />` — Last 7 / Last 30 / This month / Last month / This year (TASK-038)**. Next priorities: live `docker compose up` + AS-001..005 ablation runs in ml-dev, FE-016 LIME panel as a richer `explanation_summary` renderer, FE-017 intersectional bias-heatmap as a richer `fairness_summary` renderer (per attribute × metric × group cells), "compare two analyses" view (chip-filtered + date-windowed → 2-select → side-by-side via `<PersistedAnalysisDetail />`), saved-search persistence (queryKey already encodes the full filter shape), window-aware permalinks (serialise Decision Feed state into URL query params), conversation-thread "scroll to message" UX polish, 3D scene visualizations as wave 4.*
