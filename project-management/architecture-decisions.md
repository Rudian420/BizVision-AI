# BizVision AI — Architecture Decision Log

> Professional engineering architecture log documenting *why* choices were made, tradeoffs, and future extensibility.

---

## ADR-036: Inline `pip install` of MLflow's Postgres + S3 deps at container start, plus a `minio-init` bucket-bootstrap one-shot

**Date**: 2026-06-03
**Status**: Accepted
**Decision**: The `docker-compose.yml` MLflow service installs
`psycopg2-binary` + `boto3` at container start (`sh -c "pip install
... && mlflow server ..."`) rather than baking them into a custom
MLflow image. A new `minio-init` one-shot service creates the
`mlflow-artifacts` bucket idempotently via `mc mb --ignore-existing`,
and MLflow's `depends_on` chain waits on
`minio-init: service_completed_successfully`.

**Context**: The official `ghcr.io/mlflow/mlflow:v2.13.0` image
ships *minimal* — the `mlflow` CLI but no Postgres driver and no S3
client. With `--backend-store-uri postgresql://...` and
`--default-artifact-root s3://mlflow-artifacts`, the server crashed
on every start with `ModuleNotFoundError`, then was hot-restarted by
`restart: unless-stopped` (see [[task-051]] for the full diagnosis).
Even after the deps issue, the `mlflow-artifacts` MinIO bucket
didn't exist and would have crashed the server on the first artifact
write.

**Options considered**:

| Option | Pros | Cons |
|---|---|---|
| **A. Custom MLflow Dockerfile** | Self-contained image; faster start (deps pre-cached); standard production posture | Adds a project-specific image to the build matrix; image rebuilds on every dep bump; bigger CI cost |
| **B. Inline `pip install` at container start** (this ADR) | No new Dockerfile; deps cache into the writable layer so subsequent restarts skip the network hop; single-file change | Slightly slower first start (~10 s on a warm pip cache); reaches network at start which can fail in air-gapped envs |
| **C. MLflow's own `--default-artifact-root file://...` path** | No S3 / MinIO dependency at all | Loses the S3 artifact semantics that the rest of the project assumes; would force a path-rewrite if the team ever moves to a real S3 |

**Rationale**: Option B was chosen as the *lightest change that
unblocks the loop* without committing to a project-specific MLflow
image. The trade-off is conscious — Option A is the right long-term
answer once we ship a production deploy, and that migration is
trivial (move the `pip install` from the compose command into the
Dockerfile's `RUN`). Until then, B keeps the change additive and
reviewable in one diff.

The `minio-init` service follows the standard MinIO-with-buckets
pattern: official `mc` client, idempotent `mb`, exits cleanly via
`restart: "no"`. The 30-iteration `mc alias set` retry loop tolerates
MinIO's 1-2 second handshake delay without coupling to a slow
`condition: service_healthy` check.

**Linked**: [[adr-035]] (the env-flag skip this patch eventually
deprecates — the user keeps `BIZVISION_SKIP_MLFLOW=1` until they
verify the new container is healthy, then flips to `0`), [[task-051]]
(the diagnosis + this fix's session), [[task-042]] (the original
chronic-restart loop documentation that drove ADR-035).

---

## ADR-035: `BIZVISION_SKIP_MLFLOW=1` — env-flag fast-skip of MLflow registry + tracking calls when the server is unhealthy

**Date**: 2026-06-01
**Status**: Accepted
**Decision**: All 5 modules' `latest_production()` helpers and the
shared `start_run()` context manager check `BIZVISION_SKIP_MLFLOW` at
call time and short-circuit when set. `latest_production()` returns
`None` (callers' existing bootstrap-fallback path takes over);
`start_run()` monkey-patches the 11 most-used `mlflow.log_*` /
`set_tag` / artifact-log functions to no-ops within the context, then
restores them on exit. The default in `docker-compose.yml` is `1`
(skip) until the local MLflow container's chronic-restart issue is
fixed.

**Context**: The local docker-compose stack ships an MLflow
container that has been in a `Restarting (1)` loop since the start
of the project. The MLflow lookup `MlflowClient.get_latest_versions`
uses urllib3 with default retry policy (`total=4`, `connect=4`,
exponential backoff): every cold-start was paying ~30 s of retries
before falling through to the bootstrap branch. With 4 modules
warming concurrently at server boot (TASK-041) that was ~120 s of
serial retries on every container recreate. Worse, the training
pipelines inside `_load_*` *also* called `start_run()`, which
attempted to talk to MLflow, and even when redirected to a local
file-store URI, mlflow rejected synthetic metric names like
`weight_search.ndcg@5.w030` on `@` character validation.

**Options considered**:

| Option | Pros | Cons |
|---|---|---|
| **A. Fix the MLflow container** | Restores the intended workflow; tracking and registry work for real | Requires diagnosing why the volume isn't writable + bringing the container healthy; orthogonal to TASK-040..TASK-042's "make real ML run" theme; should happen as its own task |
| **B. Add per-call timeouts** (mlflow client `timeout=5s`) | Less invasive than skip | Still 5 s × N retries per cold-start; still hits the metric-name-validation crash |
| **C. Env-flag skip + monkey-patch no-ops** (this ADR) | Single env-var toggle; no code-path divergence between mock and real; zero cost when MLflow is healthy and `=0`; same code runs in CI without MLflow | Bootstrap training runs no longer log to a registry → no comparable cross-run metrics until MLflow is fixed (acceptable for now; the `synthetic-bootstrap` source is already understood to be ephemeral per ADR-024) |

**Rationale**: Option C is the smallest unblocking change with the
largest immediate effect (8× faster cold-starts in this session
alone — see [[session-41]] before/after table). Future work is to
fix MLflow itself (the right long-term answer); when that lands, set
`BIZVISION_SKIP_MLFLOW=0` and registry lookups + experiment tracking
turn back on with no code changes.

**Linked**: [[adr-024]] (lazy-singleton bootstrap path),
[[adr-005]] (MLflow experiment naming),
[[bug-040b]] (this ADR's mitigation made the recruitment pre-warm
fast enough to complete reliably).

---

## ADR-034: Bind-mount `ml/` into the backend container at runtime instead of baking it into the image

**Date**: 2026-06-01
**Status**: Accepted
**Decision**: The backend (and celery-worker) container's `docker-compose.yml`
gains a `./ml:/app/ml` bind mount, in addition to the existing
`./backend:/app` mount. The `ml/*` package is NOT copied into the backend
Docker image at build time.

**Context**: Promoting `*_USE_REAL_ML=True` (TASK-040) revealed that the
backend image had no `ml/*` package at all — flipping the flag raised an
`ImportError`. Two options were available to make the import succeed:

| Option | Pros | Cons |
|---|---|---|
| **A. Bake `ml/` into the image** (`COPY ../ml /app/ml` in `backend/Dockerfile`) | Self-contained image, no host dependency at runtime | Requires monorepo-root build context (was already adjusted for the frontend per TASK-build-ctx), every `ml/` edit triggers a backend rebuild — hostile to the in-session "edit + observe" workflow we use to develop ML. |
| **B. Bind-mount at runtime** (`./ml:/app/ml` in `docker-compose.yml`) | Edits to `ml/*` are picked up on uvicorn `--reload`, matching the existing posture for `backend/src` (which is already a bind mount). No image rebuild. | Image is not self-contained — `ml/` is only available when the compose stack starts it. Production deploys will need to vendor `ml/` into the image instead. |

**Rationale**: Option B matches the dev posture we already use for
`backend/src` (the `./backend:/app` mount), keeps the dev loop fast, and
the ML code lives in the same repo as the backend anyway so there's no
network or registry dependency. The future production image can copy
`ml/` in via a multi-stage build when we ship a hardened image —
documented as a follow-up in `pending-tasks.md`.

**Linked**: [[adr-024]] (Backend↔ML lazy singleton + MLflow registry pattern)

---

## ADR-001: Monorepo Architecture

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Single monorepo with `frontend/`, `backend/`, `ml/`, `infrastructure/` at root

**Context**: 5 interconnected AI modules that share types, context, and business logic need a coherent development experience.

**Rationale**:
- Shared TypeScript types between Next.js frontend and FastAPI backend (via OpenAPI codegen)
- Unified Docker Compose for local development
- Single GitHub Actions pipeline for full-stack CI
- Easier cross-module refactoring

**Tradeoffs**:
- Larger repository size (mitigated by sparse checkout)
- All-or-nothing CI runs (mitigated by path-based triggers)

**Future extensibility**: Can split into polyrepo if teams > 10 people using `git subtree`

---

## ADR-002: FastAPI over Django/Flask

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: FastAPI as the primary Python web framework

**Rationale**:
- **Native async support** — critical for ML inference (non-blocking I/O while models run)
- **Pydantic v2 integration** — typed request/response schemas = auto-generated OpenAPI spec
- **Performance** — comparable to Go/Node for I/O-bound workloads
- **Type safety** — Python type hints flow through to API documentation
- **Modern** — best practices align with research-grade production systems

**Tradeoffs**:
- Less "batteries included" than Django (no admin, no ORM by default)
- Mitigation: SQLAlchemy 2.0 (async) + Alembic for migrations

**Alternatives Rejected**:
- Django REST Framework: sync-first, heavier overhead
- Flask: no native async, limited typing, less production-grade

---

## ADR-003: PostgreSQL + pgvector over dedicated vector DB

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: PostgreSQL with pgvector extension for all data including vector embeddings

**Rationale**:
- **Unified storage** — relational data and vector embeddings in one place
- **ACID compliance** — critical for financial data (pricing, forecasting)
- **pgvector** — supports cosine similarity, L2 distance, IVFFlat + HNSW indexes
- **Operational simplicity** — one database to manage, backup, monitor
- **Research reproducibility** — easier to snapshot and restore experiment states

**Tradeoffs**:
- Less optimized than dedicated vector DBs (Pinecone, Weaviate) at extreme scale (>100M vectors)
- Mitigation: HNSW indexing + IVFFlat partitioning covers our SME scale comfortably

**When to reconsider**: If vector dataset > 10M rows or query latency > 50ms at scale

---

## ADR-004: React Three Fiber over pure Three.js or Babylon.js

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: React Three Fiber (R3F) + Drei as the 3D rendering framework

**Rationale**:
- **React integration** — native hooks, context, Suspense for declarative 3D
- **Drei** — 250+ production-ready Three.js abstractions
- **Postprocessing** — bloom, depth-of-field, chromatic aberration from `@react-three/postprocessing`
- **Theatre.js integration** — cinematic timeline control for immersive sequences
- **Component reusability** — shader materials, particle systems as reusable React components

**Tradeoffs**:
- Reconciler overhead vs raw Three.js (negligible at < 100K vertices)
- Less control over render loop (mitigated by `useFrame` + `invalidate`)

**Alternatives Rejected**:
- Pure Three.js: More boilerplate, harder to compose with React state
- Babylon.js: Less ecosystem, fewer creative developer resources
- PlayCanvas: Game-engine overhead, not research-friendly

---

## ADR-005: MLflow for experiment tracking over W&B / Neptune

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Self-hosted MLflow as the ML experiment tracking system

**Rationale**:
- **Open source** — no cost, no vendor lock-in, fully controllable
- **Self-hostable** — can run in Docker alongside other services
- **Research reproducibility** — artifact storage + experiment versioning
- **Model registry** — production model management (staging/production lifecycle)
- **DVC compatibility** — data versioning alongside experiment tracking

**Tradeoffs**:
- Less polished UI than W&B
- Manual infrastructure management
- Mitigation: Docker Compose deployment, PostgreSQL backend for persistence

**Alternatives Rejected**:
- Weights & Biases: Paid at scale, vendor dependency
- Neptune: Similar concerns
- CometML: Less community adoption

---

## ADR-006: LangGraph for Multi-Agent Orchestration

**Date**: 2026-05-27  
**Status**: Tentatively Accepted (review after Phase 3)  
**Decision**: LangGraph for the Financial Advisory chatbot's multi-agent system

**Rationale**:
- **Graph-based reasoning** — nodes and edges map naturally to agent reasoning steps
- **State management** — explicit state machine = debuggable, auditable AI
- **Tool use** — native integration with module API calls
- **Streaming** — real-time token streaming for cinematic chatbot UX
- **LangSmith integration** — observability for agent traces (thesis-friendly)

**Tradeoffs**:
- Steeper learning curve than simple chain
- Heavier dependency surface than raw API calls

**Alternative to evaluate**: CrewAI for the multi-agent layer above LangGraph

---

## ADR-007: Celery + Redis for Background Task Queue

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Celery with Redis broker for ML inference tasks and async jobs

**Rationale**:
- **ML inference** — model training/batch inference must be non-blocking
- **Result caching** — ML predictions cached in Redis (TTL-based invalidation)
- **Horizontal scaling** — Celery workers can scale independently
- **Monitoring** — Flower dashboard for real-time task inspection

**Tradeoffs**:
- Operational complexity of managing worker processes
- Mitigation: Docker Compose with health checks, auto-restart policies

---

## ADR-008: Zustand over Redux/Jotai for Frontend State

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Zustand as the primary client-side state management library

**Rationale**:
- **Minimal boilerplate** — no action creators, reducers, or providers required
- **Performance** — fine-grained subscriptions prevent unnecessary re-renders
- **3D integration** — Zustand stores accessible inside R3F components without React context
- **Middleware** — persist, devtools, immer middleware available

**Tradeoffs**:
- Less structured than Redux (intentional — Zustand's flexibility is a feature here)

**State Architecture**:
```
useAuthStore       — JWT tokens, user profile
useModuleStore     — active module, navigation state  
useAIContextStore  — cross-module AI signals (shared context bus)
use3DStore         — Three.js scene state, camera, quality level
useRealtimeStore   — WebSocket data streams
```

---

## ADR-009: SHAP + LIME Dual Explainability Strategy

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Use both SHAP and LIME rather than choosing one

**Rationale**:
- **SHAP** — globally consistent (TreeSHAP for gradient boosted models), additive
- **LIME** — model-agnostic local explanations, better for tabular + text
- **Research value** — comparing both yields a richer thesis contribution
- **User experience** — different explanation types for different user contexts (technical vs executive)

**Implementation**:
- SHAP: global feature importance + waterfall plots per prediction
- LIME: local explanation cards for individual decisions
- Narrative layer: LLM-generated plain-English summary of SHAP/LIME outputs

---

## ADR-010: Adaptive Rendering Quality System

**Date**: 2026-05-27  
**Status**: Accepted  
**Decision**: Implement a 3-tier adaptive GPU rendering pipeline

**Rationale**:
- The platform must run on a range of hardware (laptop GPU → dedicated GPU)
- WebGL performance varies drastically across devices
- Cinematic effects (bloom, particle systems) must degrade gracefully

**Tiers**:
| Tier | Target | Particles | Post-FX | Shadows |
|------|--------|-----------|---------|---------|
| LOW | Integrated GPU | 1K | Minimal | None |
| MED | Dedicated GPU | 10K | Bloom+DOF | Simple |
| HIGH | RTX/M-series | 100K | Full | Ray-marched |

**Detection**: GPU benchmark on load → assign tier → persist in localStorage

---

## ADR-011: Bootability-First with a Typed-Mock Service Layer

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Make the backend import and boot end-to-end **before** any real ML
exists, by giving every module a service class that returns deterministic,
schema-valid mock data behind the final interface.

**Context**: An audit found the backend was a non-bootable scaffold — routers
referenced services, schemas, models, and core modules that did not exist, so the
app could not import. Two paths forward: (a) build real ML first, or (b) make the
contract real and bootable first, then swap implementations.

**Rationale**:
- **Unblocks parallel work** — frontend can integrate against a live OpenAPI spec
  and real responses today; ML can be developed behind a stable interface.
- **De-risks integration early** — auth, middleware, routing, the context bus, and
  the model-registry lifecycle are all exercised now, not at the end.
- **Stable seams** — services expose the exact signatures the real ML must satisfy
  (`RecruitmentService.analyze`, `PricingService.optimize`, …), so Phase 3 is a
  drop-in replacement, not a rewrite.
- **Deterministic mocks** — hash-seeded scores make responses reproducible for
  frontend snapshot tests.

**Tradeoffs**:
- Risk of mock data being mistaken for real results → mitigated by `*-mock-*`
  `model_version` stamps and explicit "PHASE 1 SCAFFOLD" docstrings.
- Two implementations to maintain briefly → acceptable; mocks are deleted as each
  real model lands.

**What is real vs mock as of 2026-05-28**:
- **Real**: app factory, config, async DB engine, JWT auth (bcrypt + Redis refresh
  rotation), logging, request-id/timing/rate-limit middleware, the Shared Context
  Bus (Redis pub/sub), the model-registry lifecycle, WebSocket connection manager.
- **Mock**: all five module inference services and the chatbot's LangGraph/RAG.

**When to revisit**: each mock is removed the session its real model is integrated
(Phase 3 ML-004/005/006/008/009, ML-010/011).

---

## ADR-012: Single Declarative Base via `models/base.py` Re-export

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Define the SQLAlchemy `Base` once in `core/database.py` and
re-export it (plus `UUIDMixin`/`TimestampMixin`) from `models/base.py`, rather than
declaring a second base in the models package.

**Rationale**: `main.py` calls `Base.metadata.create_all` using the
`core.database.Base`. If models inherited from a different base, their tables would
live in a separate metadata registry and never be created (and Alembic autogenerate
would miss them). One base = one metadata = one source of truth for migrations.

---

## ADR-013: npm Workspaces + Turborepo for Monorepo Orchestration

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Manage the JS/TS side (frontend + shared packages) with **npm
workspaces** and **Turborepo**; keep Python (backend, ml) as sibling packages
configured via a single root `pyproject.toml`.

**Rationale**:
- npm workspaces keep tooling consistent with the existing `npm`-based frontend and
  the Makefile (no new package manager to learn).
- Turborepo adds task caching + graph-aware `build/lint/test` across packages.
- A single root `pyproject.toml` centralises ruff/mypy/pytest config for `backend`
  and `ml` without forcing them into the JS workspace graph.

**Tradeoffs**: npm workspace hoisting + the R3F/three.js ecosystem's strict peer
ranges require `legacy-peer-deps=true` (`.npmrc`) for deterministic installs.
**Revisit** once the 3D dependency matrix is consolidated (Phase 2).

---

## ADR-014: OpenAPI-First Shared Contracts (`@bizvision/contracts`)

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: The backend's Pydantic schemas are the single source of truth. The
frontend consumes generated types from `@bizvision/contracts`, produced by running
`openapi-typescript` against the live `/api/v1/openapi.json`. Cross-language enums
that must stay in lock-step are hand-mirrored in `enums.ts` (with a CI drift note).

**Rationale**: One contract, two languages — eliminates frontend/backend type drift.
Generated types are reproducible from a running server or a committed snapshot.

**Tradeoffs**: Requires a running backend (or snapshot) to regenerate; the committed
placeholder keeps type-checking green before first generation.

---

## ADR-015: Python Floor Lowered to 3.10

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Set the ruff/mypy target to **py310** (was py311) and avoid 3.11-only
APIs (e.g. `datetime.UTC` → `datetime.timezone.utc`).

**Rationale**: The development machine runs Python 3.10; 3.10-compatible code also
runs unchanged on the 3.11 Docker image, maximising compatibility with zero downside.
Ruff's pyupgrade had auto-rewritten code to 3.11-only `datetime.UTC`, which broke
local imports — lowering the floor prevents recurrence.

---

## ADR-016: 3-Tier Adaptive Renderer (LOW / MED / HIGH)

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Detect GPU tier once on mount and dispatch all expensive 3D
decisions through a single `TIER_PROFILES` table.

**Implementation**: `frontend/src/lib/render-tier.ts` parses
`WEBGL_debug_renderer_info → UNMASKED_RENDERER_WEBGL` against two regexes
(HIGH_GPU, LOW_GPU); the result is cached in `localStorage('bv:tier')`. The
profile drives:

| Knob | LOW | MED | HIGH |
|------|-----|-----|------|
| NeuralGalaxy particles | 20K | 50K | 100K |
| Starfield count | 800 | 2 000 | 4 000 |
| `dpr` (devicePixelRatio) | [1, 1.25] | [1, 1.5] | [1, 2] |
| Bloom | ✗ | ✓ | ✓ |
| Chromatic aberration | ✗ | ✗ | ✓ |
| Vignette | ✓ | ✓ | ✓ |
| Film grain | ✗ | ✗ | ✓ |
| Energy connections / planet | 0 | 32 | 64 |
| Camera damping | 0.20 | 0.15 | 0.12 |

**Why a table, not per-scene if-statements**: scenes stay declarative — they
read one number from the store and allocate that many particles. Changing the
LOW knob never requires touching scene code.

**Tradeoffs**: A user with a top-end GPU stuck on the LOW profile (because
`WEBGL_debug_renderer_info` was masked) sees a degraded experience. A future
"Quality" setting in the app will let them upgrade manually.

---

## ADR-017: Scroll-Segment Camera Choreography (no Theatre.js for Phase 2)

**Date**: 2026-05-28
**Status**: Accepted (Theatre.js deferred to Phase 5)
**Decision**: The landing camera path is a hand-written list of waypoints
`{ t, position, lookAt, roll }` in `CinematicCamera.tsx`. The currently-active
segment is found by binary scan; position + lookAt are smooth-stepped between
adjacent waypoints; the camera lerps toward the target each frame.

**Rationale**: For the landing's 5-section narrative, a 13-waypoint piece-wise
path is trivially readable and tweakable in code — Theatre.js's authoring UI
adds value only when the camera animation lives outside the developer's edit
loop (per-module experiences in Phase 5).

**Tradeoffs**: No external authoring tool means non-engineers can't iterate on
the camera. We accept this for the landing where the engineer-designer loop is
tight; Phase 5 will bring Theatre.js for the bespoke module experiences.

---

## ADR-018: Window Scroll as the Single Source of Truth (Lenis, no `ScrollControls`)

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Smooth the **window scroll** with Lenis, normalise it to 0..1 in
`useActiveModule`, and have R3F scenes read `useSceneStore.getState().scrollOffset`
inside `useFrame`. Drei's `<ScrollControls>` is **not used**.

**Context**: `<ScrollControls>` creates a second scrollable element inside the
Canvas, separate from `window.scrollY`. Combined with a tall outer page
(700vh) needed for HTML overlay sections, this creates two scroll positions
that drift under wheel-bursts and momentum scroll.

**Rationale**:
- One scroll position keeps the 3D camera, the HUD, framer-motion HTML
  reveals, the URL hash anchors, and Lenis itself in lock-step.
- Lenis is purpose-built for this (RAF-driven, easings, accessibility
  flags) and integrates with the browser's native `scrollY` so dev-tools,
  accessibility tooling, and deep-links all work.
- A Zustand store keeps the relay zero-cost — scenes call `getState()`
  inside `useFrame` (no React re-renders).

**Tradeoffs**: We lose `ScrollControls`'s `<Scroll html>` slot for inline 3D
overlays, but we don't need it; the landing's HTML lives outside the canvas.

---

## ADR-019: Shaders as TypeScript String Constants (Phase 2)

**Date**: 2026-05-28
**Status**: Accepted (revisit when total shader LOC > ~600)
**Decision**: GLSL programs live in `frontend/src/shaders/*.ts` as exported
template strings (`/* glsl */ \`…\``), composed via TS imports. Webpack's
`asset/source` loader for `.glsl` files is configured (`next.config.mjs`) but
unused in Phase 2.

**Rationale**:
- **One module graph** — shader includes (noise, SDF, palette helpers) are
  TS imports, not glob-resolved string concatenation; tree-shakeable.
- **One language to lint** — ruff/eslint cover the TS string; no separate
  glsl-lint pipeline.
- **One source map** — debugging shader errors maps back to one TS line.
- **VSCode hint** — the `/* glsl */` block comment triggers GLSL syntax
  highlighting in most extensions.

**Tradeoffs**: Editor-side GLSL diagnostics (lint, format) require an opt-in
extension that recognises the tagged-template idiom. The asset/source path
stays available for very large shaders where TS-string indentation becomes
unwieldy.

---

## ADR-020: ML Module Package Layout — One Package per AI Module

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Each AI module (`recruitment`, `pricing`, `forecasting`,
`sustainability`, `chatbot`) gets its own top-level package under `ml/`
with a fixed sub-package taxonomy:

```
ml/<module>/
    data/           schemas + loader
    parsers/        domain-specific input → schema (where applicable)
    features/       structured feature engineering
    embeddings/     text / sequence encoders + cache
    models/         baselines + advanced + ensemble (uniform interface)
    evaluation/     metrics + benchmark harness
    explainability/ SHAP / LIME adapters + narrative
    fairness/       audit + mitigation (where applicable)
    reproducibility/ seed + env capture
    registry/       MLflow registered-model helpers
    search/         vector index (where applicable)
    copilot/        LLM-driven structured advisory (where applicable)
    training/       pipeline + ablation + config
    pipelines/      legacy CLI entry (Makefile-stable)
    tests/          offline unit tests
    cli.py          argparse entry point
    README.md       module overview
```

**Rationale**:
- **Mirrors the backend services layer** (`backend/src/services/<module>/`)
  — anyone navigating the codebase finds the same shape on both sides.
- **Bounded blast radius** — a change in `recruitment.embeddings` cannot
  break a `pricing` import; cross-module helpers live in `ml/shared/`.
- **One uniform interface per layer** (`Encoder`, `RankingModel`, `Pipeline`)
  enables benchmark harnesses, ablation runners, and dashboards to be
  generic over modules.
- **CI matrix-friendly** — `pytest ml/recruitment/tests` can run per-module
  in parallel; nothing to refactor when a module's heavy deps grow.

**Tradeoffs**: more directories than strictly necessary for the
synthesis-only modules (e.g. early-stage `chatbot` doesn't yet need its
own `features/`); empty packages are accepted in exchange for shape consistency.

---

## ADR-021: Embedding Cache — Content-Hash Keyed, LRU + Optional Disk

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: All text encoders write through a single `EmbeddingCache`
class keyed on `(encoder_name, sha256(text))`. In-memory LRU is always on
(default 4 096 entries); disk persistence is opt-in
(`~/.cache/bizvision/embeddings/`, two-char shard directory).

**Context**: The AS-001 ablation re-embeds the same CV corpus across
6 model arms × 3 seeds × 2 dataset sizes = 36 fits. Without caching,
SBERT alone is ~80 % of total wall time and the disk thrash overflows
the model_cache mount on CI.

**Rationale**:
- **Correctness** — content hash means there is no key-collision class:
  if the text differs by one character the cache misses.
- **Cross-encoder safety** — the encoder name is part of the key, so a
  SBERT and a future OpenAI embedding never share buckets.
- **Two-letter shard** — keeps a 100 K-entry disk cache out of the
  ext4/NTFS large-directory pathology.
- **Opt-in disk** — unit tests stay hermetic; production opts in.

**Tradeoffs**: Disk cache is not multi-tenant safe across users; a future
S3-backed cache lives behind the same `EmbeddingCache` interface.

---

## ADR-022: Uniform `RankingModel` Interface Across All Rankers

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: Every recruitment ranker — Random, TF-IDF, BM25, SBERT,
XGBoost, Ensemble — implements the same minimal interface:

```python
class RankingModel(ABC):
    requires_training: bool
    name: str
    def fit(self, pairs: Sequence[Pair]) -> RankingModel: ...
    def score(self, jd: JobDescription, cands: Sequence[CandidateRecord]) -> ndarray: ...
    def score_with_detail(self, jd, cands) -> list[ScoreDetail]: ...
```

**Rationale**:
- The benchmark harness (`evaluation.benchmark.run_benchmark`), the
  ensemble combiner, and the recruiter copilot all consume *any*
  `RankingModel` without case analysis — adding a learning-to-rank
  LambdaMART arm is one file in `models/` + one line in `training.pipeline`.
- `score_with_detail` is the *optional* richer output (sub-scores +
  feature contributions) used by SHAP / LIME / the copilot. The default
  implementation derives it from `score`, so a new ranker need only
  override when it has more to say.
- The contract is explicit about scores being *uncalibrated*
  ("higher = more relevant; no probability assumed"). Calibration is the
  caller's responsibility — kept out of the ranker to enable model
  comparison without rewriting the score scale.

**Tradeoffs**: A few rankers (e.g. RandomRanker) pay for a trivial `fit`
no-op so the call site can be uniform. Acceptable cost.

---

## ADR-023: Linear-Blend Ensemble over a Meta-Learner

**Date**: 2026-05-28
**Status**: Accepted
**Decision**: The target Recruitment Intelligence system
(`EnsembleRanker`) blends SBERT cosine and XGBoost probability via a
weighted convex combination — **not** a learned meta-classifier stack.

```python
score = w · normalise(sbert)  +  (1 - w) · normalise(xgb)
```

`w` is chosen on the validation split by `find_optimal_weight(grid=(0.3, …, 0.7))`
maximising NDCG@5.

**Rationale**:
1. **Interpretability**. SHAP attributions on each leg combine *linearly*
   into a composite attribution: `att = w · att_sbert + (1-w) · att_xgb`.
   A meta-learner would itself need explaining — the leg-level attribution
   would become an internal feature with no recruiter-readable meaning.
2. **Calibration**. Each leg is pre-normalised per query to [0, 1] via
   min-max so `w` remains a true dial between "more semantic" and "more
   structured" rather than absorbing scale differences.
3. **Cold-start**. SMEs have ≤ 50 hires / year; a stacking meta-learner
   needs hundreds of supervised observations before it generalises.
   The blend works *unsupervised* at the default 0.6/0.4 split and is
   fine-tuned as labels arrive.
4. **Cross-module reuse**. Forecasting (RC-004) and Pricing
   (RC-003) plan the same composition pattern; standardising on linear
   blending makes their SHAP attributions decomposable in the executive
   chatbot's narrative layer.

**When to revisit**: when supervised data exceeds ~1 000 pairs per JD
*and* a held-out improvement of ≥ 2 NDCG@5 points is reliably observed
over the linear blend across 5 seeds.

---

## ADR-024: Backend ML Inference — Lazy-Imported In-Process Client

**Date**: 2026-05-28
**Status**: Accepted (revisit when SBERT inference latency on a real
workload pushes us past the 500 ms response budget)
**Decision**: The backend calls `ml.recruitment` **in-process** with a
**lazy heavy import**. A single `RecruitmentInferenceClient` per worker
holds the fitted ranker, lazy-loaded on first call (preferring an MLflow
Model Registry Production version; falling back to a synthetic-data
bootstrap so the path is exercised on a fresh deploy).

```
recruitment_service.analyze
    ↓ (when RECRUITMENT_USE_REAL_ML=true)
_real_score_candidates
    ↓
get_inference_client()       ← module-level singleton, thread-safe
    ↓
RecruitmentInferenceClient.score_candidates
    ↓
ml.recruitment (lazy import here — torch / xgboost / shap)
```

**Rationale**:
- **Mock path stays free of heavy imports** — the backend cold-start cost
  is unchanged for the default `RECRUITMENT_USE_REAL_ML=false` deployment.
- **Singleton cache** — first inference call eats the SBERT model load
  (~300 MB / a few seconds); subsequent calls are O(N_candidates) GPU /
  CPU work only.
- **Pure-Python translation layer** (`ml_translation.py`) is unit-testable
  in the backend's lean dev venv — no need to install the full ML chain
  to verify the API↔ML shape contract.
- **Synthetic bootstrap fallback** is loud (warning-logged), explicitly
  temporary, and only activates when MLflow has no Production model —
  the path stays exercisable on a clean checkout.
- **Per-process singleton** rather than a global cache means each FastAPI
  worker holds its own ranker — fine at SME concurrency (≤ 4 workers ×
  ~300 MB = ~1.2 GB RSS overhead). Replace with a shared
  `mlflow.pyfunc.load_model` over a model-server when workers > 8.

**Tradeoffs**:
- **Cold-start tax** on the first inference call (model load + optional
  synthetic bootstrap). The mock path is unaffected; production deploys
  with a registered Production model skip the bootstrap.
- **Backend image must ship `ml.recruitment`** (and its deps) when
  `RECRUITMENT_USE_REAL_ML=true`. Today the backend Dockerfile only copies
  `backend/`; switching to the real path requires copying `ml/` and
  installing `ml/requirements.txt`. Mock-mode deploys remain slim.
- **Synchronous inference blocks the request thread.** Acceptable for the
  SME use case (≤ 50 candidates per JD, ~100 ms semantic + ~20 ms
  structured). Past the 500 ms budget, hop to Celery — see below.

**Alternatives rejected (for now)**:
- **Celery offload to ml-dev worker**. Best architectural fit — the
  worker already exists, ADR-007 routes `src.workers.tasks.ml.*` to the
  ml queue, and the ml-dev container has the ML chain. We didn't take it
  here because:
  1. Sync `.apply_async().get(timeout=N)` reintroduces request-thread
     blocking *plus* serialisation cost — no latency win.
  2. Truly async (202 + polling) requires a job-status endpoint pair the
     frontend doesn't yet consume.
  Slated as the v2 once the front-end recruitment UI ships and we can
  measure SBERT latency under real workload.
- **Dedicated ml-inference microservice**. Right answer at scale, wrong
  shape for a single SME workload + thesis-deadline pressure. Deferred to
  Phase 6 (OPS-001).

**When to revisit**:
- p95 inference latency > 500 ms over 10 000 real requests, or
- worker RSS > 1.5 GB sustained, or
- second consumer (e.g. forecasting cross-module signal) needs the same
  ranker — at that point shared model serving becomes a clear win.

---

## ADR-025: `ml/pricing/` Mirrors `ml/recruitment/` Package Layout

**Date**: 2026-05-29
**Status**: Accepted
**Decision**: The `ml/pricing/` package adopts the **same sub-package
taxonomy** as `ml/recruitment/` (ADR-020):

```
data/  features/  models/  evaluation/  explainability/
reproducibility/  registry/  copilot/  training/  pipelines/  tests/  cli.py  README.md
```

Even where a sub-module is module-specific (no `parsers/` because pricing
has no resume equivalent; no `fairness/` because pricing decisions don't
carry the same intersectional risk as recruitment hiring — see the
pricing module docstring), the *names* and *contracts* of the present
sub-modules match.

**Rationale**:
- **Cognitive economy.** A developer arriving at `ml.pricing.training.pipeline`
  has built a mental model from `ml.recruitment.training.pipeline` —
  identical entry-point name, identical `TrainingConfig` shape, identical
  return type pattern (`*TrainingResult` with `benchmark` + `env`).
- **Cross-module tooling.** The ablation runners (`ml.{x}.training.ablation`)
  expose `AblationRunResult.mean_with_ci(metric_name)` — same call site,
  same column shape — so the thesis's per-module comparison tables can
  be built by one helper rather than four.
- **One uniform interface per layer**: `RankingModel` for recruitment,
  `PricingPolicy` (+ `DemandModel`) for pricing; the *file* in
  `models/base.py` carries the abstract class in both. Future arms slot
  in as one file.
- **CI matrix-friendly**: `pytest ml/pricing/tests` runs in parallel with
  `pytest ml/recruitment/tests`; both share the offline-pure-numpy
  metric pattern so neither blocks on heavy deps.

**Tradeoffs**:
- A few sub-packages are deliberately *absent* per module — `parsers`,
  `fairness`. The shape is "same skeleton, module-specific muscles", not
  "identical skeleton including unused bones".
- Module-specific shapes still leak: pricing has *two* interfaces
  (`DemandModel` and `PricingPolicy`) where recruitment has *one*
  (`RankingModel`) — pricing genuinely has two roles (predict demand vs
  recommend price) and forcing one would obscure the composition.
  Documented in `models/base.py`.

**When to revisit**: when a third ML module (Forecasting) lands and we
see what *doesn't* generalise.

---

## ADR-026: PPO RL Pricing Agent — Constant-Elasticity Environment

**Date**: 2026-05-29
**Status**: Accepted (RC-003 — Explainable RL Pricing)
**Decision**: The RL arm of AS-002 (`PPOPricingPolicy`) trains Stable-
Baselines3 PPO over a **custom Gymnasium environment whose dynamics are
the constant-elasticity demand curve fit on the training pool** — *not*
a richer demand simulator.

**Rationale**:
- **Isolates the RL contribution.** The same constant-elasticity model
  drives both `ElasticityOptimalPolicy` (closed-form revenue argmax) and
  the RL env. Any *uplift* the RL arm produces over the closed-form arm
  in AS-002 comes from cross-feature interaction (season × competitor ×
  promotion) that the closed-form ignores. If we used a richer simulator
  for the RL arm only, uplift could come from either RL itself or the
  simulator fidelity — and we couldn't tell which.
- **Reproducibility.** Constant-elasticity is two numbers (α, ε) and a
  closed-form `predict_demand`. No stochastic side-channels in the env;
  random seeds + the same training data → identical PPO updates.
- **Soft fallback when RL stack is absent.** When `gymnasium` or
  `stable_baselines3` isn't installed, `PPOPricingPolicy.fit` still
  succeeds — it falls back to the closed-form elasticity recommendation
  and the benchmark harness records the lower-diversity result. The
  policy is *never* broken by a missing dep, which keeps the AS-002
  matrix complete even on partial installs.
- **Action shape: continuous price multiplier in [0.6, 1.6]** so the
  policy explores within ±60% of the current price (the same bound
  `LightGBMGridPolicy` searches). Two arms search the same hypothesis
  space → comparison stays clean.
- **Reward: per-step revenue** (not profit) so the agent doesn't get
  trapped at high prices with near-zero demand. The benchmark harness
  reports VaR(5%) separately for the risk-adjusted view (RC-003).

**Tradeoffs**:
- The RL agent **cannot beat the closed-form arm on any product whose
  demand obeys constant elasticity exactly** — because both arms use the
  same model. This is fine: AS-002's hypothesis is that real demand
  *doesn't* obey constant elasticity, so the LightGBM arm wins on
  unseen products and the RL arm wins on those where exploration helps.
- PPO is slow (50 000 timesteps default, ~5 min on the synthetic
  dataset). The slow arm in the matrix.
- The custom env is *not* a Gym-registered env — it's instantiated
  inline inside `fit`. This keeps the dep optional but means the env
  doesn't show up in `gym.envs.registry`. Acceptable since the policy is
  the only consumer.

**When to revisit**: when a real customer demand model lands (real
panel-data fit, not synthetic) we'll likely swap the RL env's dynamics
to it — same `_ConstantElasticityEnv` shape, different
`predict_demand` implementation behind the same interface.

---

## ADR-027: Chatbot Persistence Uses the Rich Relational Pattern, not Polymorphic

**Status**: Accepted — 2026-05-29 (TASK-014)

**Context**: Sessions 8/11/12 landed three persistence-aware modules
(pricing, ESG, forecasting) on the same shape — *one polymorphic table
keyed by an `analysis_type` discriminator with JSONB request/response
payloads*. The chatbot was the last Phase-1 module without persistence,
and the obvious next step was *"do the same thing again."* We did not.

**Decision**: The chatbot uses the **rich relational pattern** —
parent `chatbot_conversations` + ordered `chatbot_messages` child rows
+ independent `chatbot_executive_reports` rows — matching the
recruitment-side shape (`RecruitmentSession` + `CandidateScore` +
`FairnessAuditRecord`), **not** the polymorphic discriminator shape
used by pricing / ESG / forecasting.

**Rationale**:

1. **Shape symmetry, not aesthetic uniformity.** The polymorphic
   pattern compresses *N thin self-contained analysis types* into one
   table. Pricing has four (`optimize` / `monte_carlo` / `elasticity` /
   `scenario_comparison`), each a single-shot call with a single-shot
   response. ESG and forecasting are the same. Chat is the opposite:
   *one* primary shape (multi-turn dialog) with *deep* child rows —
   each message carries its own role, position, reasoning trace, tool
   sources, and token count. Folding messages into a JSONB array on
   the conversation row would make the common query — *"give me turn
   N of conversation X"* — a JSON-path scan instead of an indexed PK
   lookup, and would defeat the unique constraint
   `(conversation_id, position)` we use to make turn ordering
   deterministic under racing WS writes.

2. **ADR-022's uniform-interface principle applies at the *schema*
   layer, not the *storage* layer.** This is the same reasoning that
   justified the pricing-vs-recruitment split in TASK-009 — match each
   module's shape, don't force every module through the same template.
   The fact that pricing/ESG/forecasting *happen* to share storage is
   incidental; chatbot doesn't, and shouldn't.

3. **WebSocket persistence requires a stable per-turn anchor.** The
   WS handler persists *both* the inbound user turn and the final
   assistant turn at `complete`-event time. A reconnecting client
   hydrates from `/chatbot/conversations/{id}` and must see the turns
   in deterministic order. The `(conversation_id, position)` unique
   constraint is the anchor — impossible to express as cleanly on a
   JSONB-blob table.

4. **Aggregate columns belong on the parent.** `message_count`,
   `total_tokens_used`, and `modules_in_scope` (the running union of
   per-message module scopes) are bumped on every persisted turn.
   Storing them on the conversation row makes the *"list my
   conversations, newest first, with token totals"* page a single
   indexed read; recomputing them from a JSONB array on every list
   would scale badly.

5. **Executive reports are independent of conversations.** A report
   is a self-contained snapshot of the modules-in-scope at a point in
   time — not a chat turn. Folding it into the conversation table
   behind another discriminator would conflate two materially
   different response shapes; a separate `chatbot_executive_reports`
   table keeps the *"give me the most recent quarterly executive
   report"* query a single indexed read.

**Consequences**:

- Migration `0005_chatbot_conversations` lands three new tables, not
  one. Total tables after this migration: **12** (was 9 after TASK-013).
- WS `ws_manager.connect` now returns `user_id: UUID | None` (was
  `bool`) so the route handler can scope persistence to that user
  without re-decoding the token.
- A fresh `AsyncSessionLocal()` session is opened per WS turn — the
  WS connection outlives any single request, so the request-scoped
  `get_db` dependency doesn't fit. The per-turn session is committed
  before the `complete` event is emitted so a reconnecting client
  immediately sees the new turns.
- Frontend chatbot UI (FE-015) can call `/conversations` / `{id}`
  against real persisted data. Streamed token chunks remain non-durable;
  only the final assistant `content` is the row of record.

**When to revisit**: if/when chat agents start spawning *internal*
multi-step plans (LangGraph branching agents) that we want to
materialise separately from the user-facing message stream, a
`chatbot_agent_steps` child table would be the natural extension —
again, the rich relational pattern stays the right shape.

---

## ADR-028: `ml/forecasting/` Mirrors `ml/pricing/` Package Layout

**Status**: Accepted — 2026-05-29 (TASK-015)

**Context**: Phase-1 backend persistence is complete; Phase-3 ML work
resumes with the forecasting package. ADR-025 already locked in
*"`ml/pricing/` mirrors `ml/recruitment/` layout"* — the same shape
question applies here for the third module ML package.

**Decision**: `ml/forecasting/` adopts the same sub-package layout as
`ml/pricing/` (and therefore `ml/recruitment/`):

```
ml/forecasting/
  data/             — frozen dataclasses + synthetic loader
  features/         — temporal feature builders (lag/rolling/calendar)
  models/           — uniform ForecastModel ABC + 4 arms
  evaluation/       — pure-numpy metrics + rolling-origin backtest
  explainability/   — deterministic narrative generator
  copilot/          — LLM-powered executive briefing (structured I/O)
  reproducibility/  — seed + env capture
  registry/         — MLflow Model Registry helpers
  training/         — config + single-arm pipeline + ablation runner
  pipelines/        — backward-compatible shim
  cli.py            — argparse entry points (train/ablate/benchmark)
  tests/            — pure-numpy + pytest, no statsmodels dependency
```

**Rationale**:

1. **Cross-module pattern recognition.** A new contributor reading
   `ml/recruitment/` then `ml/pricing/` learns *one* layout. Forecasting
   would be the third module to follow it — by then the convention is
   load-bearing, and a divergent layout would cost more than it gains.

2. **Uniform `ForecastModel` ABC, not the dual ABCs pricing uses.**
   Recruitment had one role (rank candidates) → one ABC
   (`RankingModel`). Pricing had two distinct roles (predict demand /
   recommend price) → two ABCs (`DemandModel` + `PricingPolicy`, see
   ADR-022 / ADR-025). Forecasting has *one* role — produce a horizon
   forecast with a prediction interval — so it uses one ABC, matching
   recruitment, not pricing. The cross-module pattern is "use as many
   ABCs as you have distinct roles," not "always copy pricing exactly."

3. **Pure-numpy + closed-form arms only in the first wave.** Theta
   (closed-form) + HoltWinters (numpy recursion) + two baselines beat
   their relevant naive comparators on the synthetic fixture without
   pulling in statsmodels or sktime, which keeps the package
   testable in the lean dev venv (same constraint that
   `ml/pricing/` satisfies — see ADR-025). Prophet / LSTM / XGBoost
   arms join later as separate optional-dep modules behind the same
   `ForecastModel` ABC; the ablation harness needs no changes.

4. **Rolling-origin backtest as the only evaluation entry-point.**
   Single-fold holdout is what the Phase-1 `pipelines/train.py` stub
   used; that's fine for a one-shot report but not for thesis-grade
   reporting. `evaluation/benchmark.py.rolling_origin_backtest` is
   what AS-003 will use — same posture as AS-002 (pricing) reusing the
   `evaluation/benchmark.py` from ML-PRC-006.

5. **Backward-compatible pipeline shim.** `pipelines/train.py` already
   exists from the Phase-1 scaffold (referenced by
   `infrastructure/Makefile`). Rather than break the legacy invocation,
   the shim now defers to the new `training.pipeline.train`. Zero
   migration cost for the runbook.

**Consequences**:

- Phase-3 ML completion ticks up by one module: forecasting now has the
  same package depth as recruitment and pricing. ML-FOR-001..006
  move from ⬜ to 🟢 in `roadmap.md`.
- Backend `ForecastingInferenceClient` is the next natural step (TASK-016,
  future) — mirror `PricingInferenceClient` / `RecruitmentInferenceClient`
  per ADR-024, gated by `FORECASTING_USE_REAL_ML`.
- AS-003 (forecasting ablation) campaign can fill EXP-FOR-001..003
  numerical results in `ml-experiments.md` once an ml-dev container
  is available.
- The `evaluation/benchmark.py` `rolling_origin_backtest` is the
  proper-scoring-rule reference (Winkler / coverage / MASE — Gneiting
  & Raftery 2007; Hyndman & Koehler 2006) — same thesis-grade posture
  as the recruitment / pricing metric tests.

**When to revisit**: when the LSTM / Prophet / XGBoost arms land
(ML-FOR-002 expansion), they fit behind the same `ForecastModel` ABC
with no harness changes. If a future arm needs a non-univariate input
(e.g. covariate-aware deep model), we'll either widen the ABC's `fit`
signature once or add a separate `ConditionalForecastModel` ABC —
matching pricing's two-ABC posture per ADR-025's same-question
precedent.

---

## ADR-029: `ml/sustainability/` Mirrors `ml/forecasting/` Package Layout

**Status**: Accepted — 2026-05-29 (TASK-017)

**Context**: ADR-025 locked in *"`ml/pricing/` mirrors `ml/recruitment/`
layout"* and ADR-028 extended it to *"`ml/forecasting/` mirrors
`ml/pricing/` layout"*. Sustainability is the fourth Phase-3 ML
package; the layout-reuse question is settled, but two genuine
sustainability-specific decisions (uniform vs split ABCs; presence of a
fairness sub-module) need explicit documentation.

**Decision**: `ml/sustainability/` adopts the same sub-package layout as
`ml/forecasting/`, with one addition (`fairness/`) and one
clarification (carbon estimation lives outside the uniform ABC):

```
ml/sustainability/
  data/             — frozen dataclasses + synthetic loader
  features/         — pillar feature extractor (12 dims, stable order)
  models/           — uniform ESGScorer ABC + 3 arms + CarbonEstimatorModel
  evaluation/       — pure-numpy metrics + 3-fold holdout harness
  explainability/   — linear-SHAP adapter + deterministic narrative
  fairness/         — industry disparate-impact audit (NEW)
  copilot/          — LLM-powered executive briefing (structured I/O)
  reproducibility/  — seed + env capture
  registry/         — MLflow `esg-multilabel-classifier` helpers
  training/         — config + single-arm pipeline + AS-004 ablation
  pipelines/        — backward-compatible shim
  cli.py            — argparse: train/ablate/benchmark/audit
  tests/            — pure-numpy + pytest, no sklearn dependency
```

**Rationale**:

1. **One ABC for scoring, one concrete class for carbon.** ESG scoring
   has one role (multi-label classification → `ESGScoreResult`); carbon
   estimation is a *regression* task with no labels, no fit, no
   probabilities. Folding it under `ESGScorer` would force every
   classifier arm to also produce Scope 1/2/3 estimates and vice
   versa — losing the uniform-interface guarantee in the harness.
   Same posture as pricing's `DemandModel` vs `PricingPolicy` split
   (ADR-025): one ABC per role, not one ABC per module.

2. **New `fairness/` sub-module — load-bearing for the thesis.** ESG
   benchmarking has an inherent fairness problem: industries differ in
   baseline ESG potential, so a cross-industry classifier will
   systematically under-score high-intensity industries. The package
   must *measure* this, not paper over it. `fairness/auditor.py`
   implements two AIF360-style metrics (Disparate Impact + Demographic
   Parity Difference) per pillar with the EEOC four-fifths rule
   threshold. The recruitment module has its own `fairness/auditor.py`
   (intersectional protected-attribute audit, ADR-022/RC-002); ESG's
   adds a parallel module with the industry as the protected attribute.
   Forecasting and pricing do not have a `fairness/` sub-module —
   neither has a protected-attribute axis that maps to a real
   ESG-style group disparity.

3. **Pure-numpy classical arms only in wave 1.** Three arms behind
   the uniform `ESGScorer` ABC: `MajorityLabel` (random floor),
   `IndustryBaseline` (per-industry mean label rate), and
   `LinearLogisticMultiLabel` (binary-relevance logistic regression
   with z-standardised features). Same constraint that `ml/pricing/`
   and `ml/forecasting/` satisfy — no sklearn dependency, package
   stays testable in the lean dev venv. Gradient-boosted multi-label
   and chain-classifier arms join in a later wave behind the same ABC.

4. **Standardisation lives *inside* the classifier, not in a separate
   transform step.** Wave-1 caught a real bug during smoke testing —
   `revenue_per_head` (std ~4e5) dominated the gradient and crushed
   every other coefficient, making the linear model tie the majority
   floor (macro-F1 0.22). Adding per-column z-standardisation captured
   at fit time and re-applied at score time fixed it (macro-F1 → 0.80,
   3-fold benchmark 0.79). The standardiser is bound to the model
   instance — there is no separate sklearn-style `Pipeline` — so
   `fit` and `score` always see consistent stats and the SHAP adapter
   operates in the same (standardised) feature space the weights live
   in.

5. **Single-arm pipeline + AS-004 ablation share the same metrics +
   harness.** Same posture as forecasting (AS-003) and pricing
   (AS-002). The `audit_industry_fairness` is part of every
   single-arm training run so the four-fifths rule status appears
   alongside macro-F1 in every MLflow run — the promotion gate in
   `registry/model_registry.py` can read both numbers.

**Consequences**:

- Phase-3 ML completion ticks up to 4/5 modules: sustainability now
  has the same package depth as recruitment, pricing, and forecasting.
  ML-009 (ML-ESG-001..006) moves from ⬜ to 🟢 in `roadmap.md`.
- Backend `SustainabilityInferenceClient` is the next natural step
  (TASK-018, future) — mirror `ForecastingInferenceClient` per ADR-024,
  gated by `SUSTAINABILITY_USE_REAL_ML`.
- AS-004 ablation campaign can fill EXP-ESG-001..003 numerical results
  in `ml-experiments.md` once an ml-dev container is available.
- `fairness/auditor.py` is the seam where AIF360-style mitigation
  (reweighing, post-hoc threshold optimisation) will plug in — same
  pattern as recruitment's `fairness/mitigation.py`. The first wave
  reports DI / DPD; mitigation arrives later.
- Initial AS-004-style smoke on the synthetic 400-company fixture
  shows **LinearLogistic macro-F1 ≈ 0.80** beating
  **IndustryBaseline ≈ 0.39** and **MajorityLabel ≈ 0.22**, but
  **all three pillars fail the four-fifths rule** under standard
  industry mix. The thesis chapter on fair ESG scoring writes itself
  from there.

**When to revisit**: when the gradient-boosted / chain-classifier
arms land (ML-ESG-002 expansion), they fit behind the same `ESGScorer`
ABC. If a future arm needs continuous E/S/G regression *targets*
(not labels), we'll add a separate `ESGRegressor` ABC — matching the
ESGScorer-vs-CarbonEstimatorModel split posture in this ADR.

---

## ADR-030: `ml/chatbot/` Mirrors `ml/sustainability/` Package Layout, Wave-1 Has No Heavy Deps

**Status**: Accepted — 2026-05-29 (TASK-019)

**Context**: Chatbot is the fifth and final Phase-3 ML package. The
layout-reuse question is settled by ADRs 025 / 028 / 029, but two
chatbot-specific decisions need explicit documentation:
(1) the wave-1 "no heavy dependencies" scope; (2) the new
`embeddings/` + `retrieval/` + `agents/` sub-modules with their own
ABCs.

**Decision**: `ml/chatbot/` adopts the same sub-package layout as
`ml/sustainability/` (per ADR-029), with three chatbot-specific
additions and one explicit constraint:

```
ml/chatbot/
  data/             — frozen dataclasses + synthetic 100-doc corpus
                      + 25-query golden set
  embeddings/       — EmbeddingClient ABC + HashEmbedder (NEW)
  retrieval/        — VectorStore ABC + NumpyVectorStore + RagRetriever (NEW)
  agents/           — BaseAgent ABC + KeywordRouter + RagResponder
                      + ToolRegistry + AgentExecutor (NEW)
  evaluation/       — pure-numpy IR metrics + AS-005 benchmark harness
  explainability/   — reasoning-trace + source-attribution helpers
  copilot/          — LLM-powered chat briefing (structured I/O)
  reproducibility/  — seed + env capture
  registry/         — MLflow `chatbot-agent-executor` helpers
  training/         — config + single-arm pipeline + AS-005 ablation
  cli.py            — argparse: train/ablate/benchmark/chat
  tests/            — pure-numpy + pytest, no torch/SBERT dependency
```

**Rationale**:

1. **Wave 1 has *zero* heavy dependencies.** No
   sentence-transformers, no torch, no LangGraph, no pgvector. The
   build constraint is identical to `ml/forecasting/` (no statsmodels)
   and `ml/sustainability/` (no sklearn) — package stays testable in
   the lean dev venv. Wave-2 SBERT swaps in behind the
   `EmbeddingClient` ABC; pgvector backend swaps in behind the
   `VectorStore` ABC; LangGraph multi-agent flows swap in behind the
   `BaseAgent` ABC. None of the harness, metrics, benchmark, or test
   code changes when those upgrades land.

2. **Hashing trick + linear-scan cosine is good enough for the
   100-doc fixture.** The feature-hashing embedder (Weinberger et al.
   2009) with the standard sign trick + L2 normalization is *known to
   recover useful similarity* on short documents without any learned
   parameters. The wave-1 smoke achieves **MRR=0.86 / recall@5=0.77
   / NDCG@5=0.75** on the 25-query golden set — comfortably above
   chance (~0.05 for 100 docs) and gives the AS-005 ablation a non-
   trivial baseline that SBERT must beat to justify its dependency
   weight. Linear-scan cosine on 100 docs is microseconds; the
   wave-2 pgvector backend earns its keep when the corpus gets to
   ≥10k docs.

3. **Three new ABCs because the chatbot has three distinct roles.**
   Recruitment has one (`RankingModel`); forecasting has one
   (`ForecastModel`); sustainability has two (`ESGScorer` +
   `CarbonEstimatorModel`); pricing has two (`DemandModel` +
   `PricingPolicy`). Chatbot has *three*: embedding text into vectors
   (`EmbeddingClient`), storing + searching vectors (`VectorStore`),
   responding to a query given retrieved context (`BaseAgent`). Each
   role is independently swappable in wave 2, so each gets its own
   ABC. This is the same uniform-interface argument from
   ADR-022 / ADR-025 applied at three layers.

4. **Module routing as a first-class agent, not a hidden classifier.**
   The `KeywordRouterAgent` is itself a `BaseAgent` so the AS-005
   harness can score it independently. This matters: the wave-1 smoke
   shows the keyword router hits **92% routing accuracy** (23/25),
   and the harness reveals that strict module filtering *trades MRR
   for precision* (Router+RAG: MRR=0.85 vs RagOnly: MRR=0.86; but
   recall@3=0.73 vs 0.71). That trade-off is reportable because the
   router is a benchmarkable component, not a hidden preprocessing
   step.

5. **Tool registry exists in wave 1 with stub handlers** so the
   wave-2 LangGraph swap-in needs only to mutate the registry, not
   touch the executor. Same posture as `ml.pricing`'s
   inference-client seam (ADR-024) — define the interface in wave 1
   even when the implementation is a stub, so wave-2 wiring is
   localised.

**Consequences**:

- Phase-3 ML completion ticks up to **5/5 modules** — the chatbot
  package now has the same depth as the other four. ML-010
  (RAG-pipeline) and ML-011 (LangGraph multi-agent) are partially
  closed: ML-010's RAG retriever and ML-011's agent-executor pattern
  both exist in wave 1; the SBERT + LangGraph upgrades remain as
  wave-2 work behind the same ABCs.
- Backend `ChatbotInferenceClient` is the next natural step
  (TASK-020, future) — mirror `SustainabilityInferenceClient` per
  ADR-024, gated by `CHATBOT_USE_REAL_ML`. The existing chatbot
  service's `stream_response` / `send_message` short-circuits through
  it when the flag is set.
- AS-005 ablation campaign can fill EXP-BOT-001..003 numerical
  results in `ml-experiments.md` once an ml-dev container is
  available. The wave-1 numbers (MRR=0.86, routing acc=0.92) are
  already a meaningful baseline.
- The "no heavy deps in wave 1" constraint means the wave-1 chatbot
  is **deterministic** — same query yields the same response across
  machines. This is load-bearing for thesis reproducibility and is
  the reason the wave-1 RAG responder is templated rather than LLM-
  generated. Wave 2's LLM-augmented copilot wraps the same retriever
  in a generative layer; the templated responder remains the
  fallback (same posture as every other module's copilot fallback).

**When to revisit**: when SBERT lands, the `HashEmbedder` becomes the
random-baseline arm in AS-005 (compared against `SBERTEmbedder`); the
harness doesn't change. When LangGraph lands, `AgentExecutor` becomes
the linear-graph baseline against multi-step `LangGraphExecutor`.
When pgvector lands, `NumpyVectorStore` stays as the test fixture
backend; `PgVectorStore` is the production-scale arm. None of these
upgrades require changing the public ABCs or the benchmark harness —
which is the whole point of writing them down in this ADR.

---

## ADR-031: Cross-Module Audit Log — Append-Only Index Sibling to the 5 Owning Tables

**Status**: Accepted
**Date**: 2026-05-30
**Context**: TASK-028 — needed a foundation for the Phase-4 fairness +
XAI dashboards. Each of the 5 module tables already stores its full
request/response payload, but they share *no* common shape: recruitment
is rich-relational with child tables, pricing/ESG/forecasting are
polymorphic discriminator tables, chatbot is rich-relational with a
unique-position ordering. A dashboard query like "show me my last 20
ML decisions across all 5 modules with their fairness + risk
attributions" would have to UNION ALL across five differently-shaped
schemas, which is both slow and brittle to schema evolution.

**Decision**: Introduce a single append-only `audit_logs` table that
captures *one row per ML decision* across all 5 modules. Each row
carries:

  • a `module` enum (the 5 names are architecturally fixed),
  • an `action` string (each module owns its taxonomy — 'analyze',
    'optimize', 'score', 'forecast', 'message', 'carbon_estimate', …),
  • a *soft* FK pair (`reference_id`, `reference_type`) pointing back
    into the owning module table — soft because the audit row must
    survive deletion of the owning record,
  • JSONB **slices** of the request, response, top-K SHAP attributions,
    and fairness pass/fail summary (NOT the full payload — the owning
    table has that),
  • `risk_tier` as a free-form string (not a Postgres enum, so each
    module's risk taxonomy can evolve without an `ALTER TYPE`
    round-trip),
  • `model_version`, `latency_ms`, `created_at`.

**Recording contract** — fire-and-forget. `AuditService.record(...)`
catches and logs every exception internally and returns `None` on
failure. A module decision must never roll back because the audit
write failed. Phase-4 will surface "missing audit row" as a banner;
correctness of the underlying decision is not coupled to telemetry.

**Module wiring** — each module's service calls `AuditService.record(...)`
once per decision, after its own `_persist_*` step has flushed and
assigned the owning row's id. Recruitment is wired first as the
proof-of-pattern (TASK-028 wires the `/recruitment/analyze`
end-of-pipeline call). The remaining 4 modules follow the same
pattern in subsequent tasks without coupling.

**API surface** — read-only:
  • `GET /api/v1/audits` — paged, filterable by `module` + `risk_tier`.
  • `GET /api/v1/audits/summary` — total decisions + per-module
    histogram + per-risk-tier histogram + `latest_decision_at`.
  • `GET /api/v1/audits/{id}` — one row, user-scoped 404.
There is NO `POST /audits` — writes happen exclusively from inside the
module services.

**Alternatives considered**:

  1. **Reuse the existing shared-context-bus event log.** Rejected —
     that bus is an in-process pub/sub for cross-module *signals*
     (forecasting reading recruitment's headcount delta, etc.); it
     doesn't persist beyond the publishing request's lifetime. Mixing
     telemetry persistence with cross-module signal flow would couple
     two unrelated concerns.

  2. **Five module-specific audit child tables (e.g. `recruitment_audit_log`).**
     Rejected — every dashboard query becomes a 5-way UNION ALL with
     no shared shape; risk-tier histograms become impossible without
     querying per-module. The whole point is cross-module aggregation.

  3. **Materialised view over the 5 owning tables.** Rejected — the
     owning tables don't agree on which columns are headline values
     (recruitment has `top_candidate_score`, pricing has
     `recommended_price`, ESG has `composite_score`); the view would
     need 5 disjoint column sets and become CASE-WHEN soup. Also,
     materialised views don't refresh inside the request that wrote
     the underlying row, so the audit would arrive seconds late.

  4. **Hard FK constraint on `reference_id`.** Rejected — the audit
     row must outlive the owning row. If a user deletes a recruitment
     session for privacy reasons, the *fact* that they ran an analysis
     should remain auditable; only the personally-identifiable payload
     should disappear. A hard FK with `ON DELETE CASCADE` defeats this;
     `ON DELETE SET NULL` would lose the trace; soft FK is the right
     posture.

**Consequences**:

  • One new table + one new Postgres enum (`audit_module`) — Phase 1
    schema count goes from 12 → 13.
  • Each module service gains one `AuditService(self.db).record(...)`
    call at the end of its primary decision path (5 lines per call
    site, fully self-contained). Recruitment wired in TASK-028;
    pricing / forecasting / sustainability / chatbot follow.
  • The Phase-4 dashboards (FE-016 LIME, FE-017 bias-heatmap,
    FAIR-003 fairness-dashboard backend) all read from this one table
    instead of five. The aggregation queries are cheap (one composite
    index per dashboard hot path).
  • Audit rows accumulate without TTL today. A future ADR can add a
    TTL or archive job once we see real-world volume — the
    append-only shape is friendly to both.

**When to revisit**: when the table grows past ~10M rows per user
cohort, or when regulatory requirements demand a tamper-evident chain
(content-addressed hashes per row); both are additive on top of the
current shape.

---

## ADR-032: Explicit Three.js Resource Disposal — `useEffect` Cleanup Per Scene Component

**Status**: Accepted
**Date**: 2026-05-31
**Context**: TASK-039 performance audit. The cinematic landing's
4 scene components (`NeuralGalaxy`, `AmbientStars`,
`EnergyConnections`, `ModulePlanet`) own GPU buffers + compiled
shader programs through `<bufferGeometry>` and `<shaderMaterial>`
JSX. React-three-fiber's reconciler does NOT automatically call
`.dispose()` on these objects when the component unmounts. Every
route change away from the landing page leaks: one 100K-particle
BufferGeometry (~5MB VRAM at this geometry's attribute count) +
one custom ShaderMaterial program; 5 holographic ShaderMaterial
programs (one per module planet); 5 line-strip ShaderMaterial
programs (energy connections); one ambient starfield PointsMaterial.

On long-lived browser tabs these leaks accumulate. On low-VRAM
mobile devices, 3 navigation round-trips can be enough to OOM
the WebGL context. Even on desktop discrete GPUs, the shader
program cache fills with orphaned programs that no driver state
machine cleans up.

**Decision**: Every R3F scene component that owns `<bufferGeometry>`,
`<*Material>`, or any disposable Three.js object MUST attach a
`useEffect` with an empty deps array whose cleanup function calls
`.dispose()` on the relevant resources. Pattern (canonical form):

```tsx
const groupRef = useRef<THREE.Group>(null);

useEffect(() => {
  const group = groupRef.current;
  return () => {
    if (!group) return;
    group.traverse((obj) => {
      const mesh = obj as THREE.Mesh; // or LineSegments, Points
      mesh.geometry?.dispose?.();
      const mat = mesh.material as THREE.Material | undefined;
      mat?.dispose?.();
    });
  };
}, []);
```

The `group.traverse` covers nested children without having to
enumerate them; the optional chaining handles components that
also own resources via Drei abstractions where the prop shape
may differ.

**Alternatives considered**:

1. **Patch react-three-fiber to auto-dispose on unmount.** Out
   of scope — modifying a third-party library is a maintenance
   tax we shouldn't take on for a fix that is 5 lines per
   component.

2. **Use `<dispose />` declaratively** (a `<primitive />`-style
   sentinel some R3F docs recommend). Doesn't cover the case
   where the geometry was constructed via JSX inside the mesh;
   the sentinel only works when you hold an explicit reference
   to the object.

3. **Move all geometry/material construction to module scope**
   and share singletons across mount/unmount cycles. Works for
   genuinely static resources (AmbientStars positions, for
   instance) but the 100K particle galaxy depends on the tier
   profile snapshot at first mount; sharing would require
   replanning the data flow. Mixed signal — adopt for AmbientStars
   in a follow-up only if it shows up as a real perf issue.

4. **`<TestRenderer>`-style automatic disposal helper hook**:
   `useDispose(meshRef)`. Considered but rejected as additional
   indirection for a one-liner. The pattern as written is its
   own documentation.

**Consequences**:

- Every new 3D scene component MUST follow this pattern.
  Reviewable in PR via grep `useEffect.*dispose` after the
  component name.
- Geometry/material disposal is one-way: after `.dispose()` the
  object cannot be re-used. Resources created inside `useMemo`
  are safe because React will re-execute the memo body on the
  next mount. Module-scope singletons would NOT be safe with
  this pattern — they'd self-destruct after the first unmount.
- The cost of disposal itself is a tiny synchronous GL call per
  resource. Negligible on the unmount path; trivial compared
  to the leak it prevents.

**When to revisit**: If a future scene component wraps a Drei
abstraction (`<Sky>`, `<Stars>`, `<Cloud>`, etc.) that internally
manages its own disposal, the manual cleanup will double-dispose
and may log warnings. Switch to the abstraction's own teardown
hook if so.

---

## ADR-033: Per-Component Re-Render Isolation for 1Hz / Streaming State

**Status**: Accepted
**Date**: 2026-05-31
**Context**: TASK-039 surfaced two cases where high-frequency
state changes were re-rendering whole subtrees that didn't
depend on the changed value:

1. **HUD clock** ticked every 1 second; `HudOverlay` owned the
   clock state. The 1Hz `setState` re-rendered the four corner
   brackets, the static label strip, the tier readout, AND the
   5-element module ticker — none of which depend on the clock.
2. **Chatbot message thread** during WS streaming. The
   `MessageThread`'s scroll effect depended on
   `streamingContent`; a 200-token response fired the effect
   200 times. More importantly, the parent re-render cascaded
   through every persisted `MessageBubble`, none of which
   change during streaming.

**Decision**: Two complementary patterns:

1. **Isolate high-frequency state into its own component.** Any
   state with > 1 Hz update frequency MUST live in the smallest
   possible component that consumes it. The clock readout is a
   single `<span>UTC HH:MM:SS</span>` component; the rest of the
   HUD is its sibling, not its child.

2. **`React.memo` hot list rows.** Components rendered in a
   list — `MessageBubble`, `CandidateRow`, audit timeline rows,
   history page rows — MUST be wrapped in `React.memo` when:
   - they receive props sourced from React Query's structurally-
     shared cache (so reference equality is meaningful), AND
   - their parent re-renders frequently for reasons unrelated
     to the row's own data (parent owns streaming state,
     filter state, etc.).

These two rules eliminate the two most common reason for "why
is this so slow" answers in React: state in the wrong place
and missing reference comparison.

**Alternatives considered**:

1. **Zustand selectors + `useShallow` everywhere.** Solves
   one direction (store → component) but not the other
   (parent → child). The two patterns above are orthogonal and
   composable.

2. **`useDeferredValue` / `startTransition` on streaming content.**
   Defers rendering of stale content rather than skipping it
   altogether. Useful for prioritisation but doesn't help the
   case where the persisted bubbles' content didn't change at
   all — `memo` is the precise fix.

3. **Virtualisation.** A future intervention if list lengths
   ever exceed page-size caps. Today the list pages cap at 20
   visible rows so the cost is bounded.

**Consequences**:

- New high-frequency UI elements (live progress bars,
  per-frame counters, etc.) MUST live in dedicated components.
- New list-row components MUST default to `React.memo`. Skipping
  it is a perf bug, not a stylistic choice.
- `React.memo` with the default comparator works as long as
  props are reference-stable from the parent. React Query's
  structural sharing covers most cases; for hand-rolled
  parents, prefer passing `id` + `useState(id)` over passing
  the whole row object.
- These rules apply ONLY to rows in lists or to high-frequency
  state. Memoising every component is a code-smell of its own
  ("memo everything makes nothing fast").

**When to revisit**: If React Compiler (RC at time of writing)
lands in a stable version that auto-memos function components,
rule 2 becomes redundant. Rule 1 stays — even auto-memo can't
fix state in the wrong place.

---

*Last updated: 2026-05-31*
