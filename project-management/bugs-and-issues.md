# BizVision AI — Bugs & Issues

> Track everything broken, slow, or wrong. Honest engineering.

---

## Issue Format

```
### BUG-XXX: Title
**Severity**: Critical | High | Medium | Low
**Status**: Open | In Progress | Resolved | Won't Fix
**Module**: Frontend | Backend | ML | Infrastructure | Cross-module
**Root Cause**: ...
**Attempted Fixes**: ...
**Solution**: ...
```

---

## Known Issues / Pre-emptive Risks

### RISK-001: Docker Volume Performance on Windows
**Severity**: High  
**Status**: Open (watch)  
**Module**: Infrastructure  
**Context**: Docker bind mounts on Windows (WSL2) have ~50% I/O performance penalty vs Linux  
**Mitigation**: Use named Docker volumes for database data, not bind mounts  
**Solution**: Configured in docker-compose.yml with named volumes for PostgreSQL, Redis, MinIO

---

### RISK-002: WebGL Context Loss on Low-End Hardware
**Severity**: Medium  
**Status**: Open (watch)  
**Module**: Frontend  
**Context**: Aggressive particle systems and shader effects may cause WebGL context loss on integrated GPUs  
**Mitigation**: Adaptive rendering tier system (ADR-010), graceful fallback to 2D  
**Solution**: Implement `webglcontextlost` event handler, quality detection on load

---

### RISK-003: ML Model Cold Start Latency
**Severity**: Medium  
**Status**: Open (watch)  
**Module**: ML / Backend  
**Context**: First inference request loads model from disk (~2-10s for large models)  
**Mitigation**: Model pre-warming on backend startup via Celery startup task  
**Solution**: Implement model registry with in-memory cache, warm all models on startup

---

### RISK-004: pgvector Index Performance at Scale
**Severity**: Low  
**Status**: Open (monitor)  
**Module**: Backend / Database  
**Context**: IVFFlat index requires `nlist` tuning for optimal performance  
**Mitigation**: Start with HNSW (better accuracy), tune `ef_construction` and `m` parameters  
**Threshold**: Re-evaluate if vector collection > 500K embeddings

---

### BUG-001: Backend Non-Bootable — Broken Import Graph
**Severity**: Critical
**Status**: Resolved (2026-05-28)
**Module**: Backend
**Root Cause**: `main.py`, `api/v1/router.py`, and all 6 module routers imported
~12 modules that were never created (`core.redis`, `core.logging`, `core.deps`,
`middleware.{request_id,timing,rate_limiter}`, `models.user`, `services.*`,
`services.shared_context.{context_bus,model_registry}`, routers `users/admin/
shared_context`, `workers.celery_app`). There were also no `__init__.py` files,
so `src` was not importable as a package.
**Detection**: Static read of the import statements vs. the file tree, then a real
import attempt.
**Solution**: Implemented all missing modules (see TASK-003), added `__init__.py`
across the tree, and unified on a single SQLAlchemy `Base` (ADR-012). Verified with
`compileall` + an isolated-venv import smoke test: app imports, 41 routes register,
zero warnings.

### RISK-005: Tracking Files Drifting From Code
**Severity**: Medium
**Status**: Open (process)
**Module**: Project management
**Context**: The status files claimed progress the code did not reflect, which could
have led to building on a false foundation.
**Mitigation**: Standing rule — at the start of every session, verify claims against
the actual file tree (and an import/boot check for the backend) before trusting the
tracking markdown.

### BUG-002: bcrypt 4.1.x Incompatible with passlib 1.7.4 (auth would break)
**Severity**: High
**Status**: Resolved (2026-05-28)
**Module**: Backend / Auth
**Root Cause**: `requirements.txt` pinned `bcrypt==4.1.3`, which removed
`bcrypt.__about__` and tightened the 72-byte handling that `passlib==1.7.4` relies
on. `hash_password()` raised `ValueError: password cannot be longer than 72 bytes`
during passlib's backend self-test — auth register/login would have failed at runtime.
**Detection**: Backend unit test `test_password_hash_roundtrip` failed on first run.
**Solution**: Pinned `bcrypt==4.0.1` (last version compatible with passlib 1.7.4).
Unit tests now pass (4/4). Long-term: migrate off passlib to the `bcrypt` API directly.

### BUG-003: Invalid `theatre` dependency blocked `npm install`
**Severity**: Medium
**Status**: Resolved (2026-05-28)
**Module**: Frontend
**Root Cause**: `frontend/package.json` listed `"theatre": "^0.7.1"` — no such version
of the bare `theatre` package exists (the real Theatre.js packages are `@theatre/core`
and `@theatre/studio`, both already listed). `npm install` aborted with ETARGET.
**Solution**: Removed the erroneous `theatre` entry. Also added `.npmrc`
(`legacy-peer-deps=true`) for the R3F/three.js peer-range conflicts, plus missing
devDeps (`@types/node`, `@testing-library/dom`, `@vitejs/plugin-react`). `npm install`
now succeeds (1097 packages); tsc + vitest + eslint all green.

---

## TASK-039 — Performance Audit (2026-05-31)

Several bugs surfaced during the static performance audit. Listed
here in severity order; each links to its fix in TASK-039.

### BUG-039a — CRITICAL: Three.js GPU resources never disposed

**Reported by**: TASK-039 static audit
**Severity**: Critical (VRAM leak on every navigation)
**Status**: FIXED

**Symptom**: 4 cinematic-landing scene components
(`NeuralGalaxy`, `AmbientStars`, `EnergyConnections`,
`ModulePlanet`) declared geometries and shader materials via JSX
inside `<mesh>`/`<points>`/`<lineSegments>` children. R3F does
NOT auto-dispose these on unmount. Every route change away from
the landing leaks:
- 1 BufferGeometry with ~5 attribute buffers × particleCount
  floats (NeuralGalaxy — 100K particles on HIGH tier)
- 1 ShaderMaterial with compiled vertex+fragment program
  (NeuralGalaxy)
- 5 ShaderMaterials with compiled programs (5 module planets)
- 5 BufferGeometries + 5 ShaderMaterials (energy connections)
- 1 BufferGeometry + 1 PointsMaterial (ambient stars)

**Root cause**: React-three-fiber's reconciler tracks the React
tree, not the Three.js scene-graph resource lifecycle.
Disposable Three.js objects need explicit `.dispose()` calls.

**Impact**: On long-lived browser tabs the leaks accumulate.
On low-VRAM mobile devices a 3-navigation round-trip can OOM
the WebGL context. On desktop the shader program cache fills
with orphaned programs.

**Fix**: TASK-039. Added `useEffect` cleanup to each scene
component. ADR-032 documents the canonical pattern.

### BUG-039b — HIGH: HUD 1Hz clock re-rendered the entire overlay

**Reported by**: TASK-039 static audit
**Severity**: High (continuous idle main-thread work)
**Status**: FIXED

**Symptom**: `components/ui/HudOverlay.tsx` owned a `clock`
state updated by `setInterval(..., 1000)`. Every second the
whole `HudOverlay` re-rendered — including 4 corner brackets,
the static label spans, the tier readout, and the 5-element
module ticker. None of those depend on the clock value.

**Root cause**: State lived too high in the component tree.

**Impact**: One long-task per second from `HudOverlay` showing
up in DevTools Performance panel. Battery hit on mobile.

**Fix**: TASK-039. Lifted the clock into a `<ClockReadout>`
component. Wrapped `<Bracket>` and `<ModuleTicker>` in
`React.memo`. ADR-033 documents the pattern.

### BUG-039c — HIGH: MessageThread auto-scroll jitter during streaming

**Reported by**: TASK-039 static audit
**Severity**: High (visible jitter during chatbot streaming)
**Status**: FIXED

**Symptom**: `MessageThread`'s `useEffect` depended on
`streamingContent`. A 200-token WS response fires the effect
~200 times, each with `behavior: 'smooth'`. The smooth-scroll
animations overlap; the browser cancels them; the scroll
position jitters perceptibly at the bottom edge.

**Root cause**: Smooth scroll animation re-armed every token
tick.

**Impact**: User-visible jitter during the most user-facing
feature (cinematic chatbot streaming).

**Fix**: TASK-039. Branch `behavior` on `isStreaming`:
- Streaming → `'auto'` (instant snap; no overlapping animations)
- Non-streaming → `'smooth'` (animated; the standard cinematic
  feel)
Also wrapped the scrollIntoView in `requestAnimationFrame` so
multiple effect fires in the same frame produce one paint.

### BUG-039d — MEDIUM: Hot list rows not memoised → re-render cascade

**Reported by**: TASK-039 static audit
**Severity**: Medium (render cost grows with list length)
**Status**: FIXED (MessageBubble + CandidateRow)

**Symptom**: `MessageBubble` (chatbot persisted turns) and
`CandidateRow` (ranked recruitment candidates) re-rendered on
every parent state change. During WS streaming the message
thread re-rendered all persisted bubbles per token tick. For
each analyze, every CandidateRow re-rendered on every
expand-collapse of one of them.

**Root cause**: No `React.memo` wrapping. The default React
behaviour is to re-render children when the parent re-renders,
regardless of whether their props actually changed.

**Impact**: With N=20 persisted bubbles + 200 streaming tokens
= 4000 wasted reconciliations per chatbot reply.

**Fix**: TASK-039. Wrapped both components in `React.memo`.
The default `Object.is` comparator works because props come
from React Query's structurally-shared cache (identical responses
produce identical references). ADR-033 documents the rule.

### BUG-039e — MEDIUM: CinematicCamera segment search O(N) per frame

**Reported by**: TASK-039 static audit
**Severity**: Medium (small but in the hot path)
**Status**: FIXED

**Symptom**: 14-waypoint camera path scanned linearly from
index 0 every frame to find the segment bracketing the current
scroll `t`. At 60 fps × 14 comparisons = 840/s in the hot
path.

**Root cause**: No knowledge of the previous frame's result.

**Impact**: ~0.05–0.1 ms per frame in `useFrame` callback.

**Fix**: TASK-039. Cached the last segment index in a ref.
Each frame checks whether the cached index still brackets `t`
first → O(1) common case. Walks forward/backward only on
boundary crossings (which fire on the order of once per scroll
gesture, not per frame).

### Issues observed but NOT patched

These are intentionally left for runtime profiling to confirm
their cost before optimisation.

- **NeuralGalaxy uses Simplex noise per particle per frame**.
  At 100K particles × 60 fps = 6 M GPU snoise evaluations/s on
  HIGH tier. Acceptable on discrete GPUs (the GPU is parallel
  enough); mobile MED already caps at 50K. Mark for revisit
  if GPU profiler shows saturation on MED.
- **Bundle splitting between landing and module workspaces**.
  Workspaces are 2D-only today; if wave-3 3D ships per module,
  each will need its own `dynamic({ ssr: false })` import.
- **No list virtualisation**. Audit timeline + history pages
  cap at 20 rows per page. Acceptable for now; revisit if
  page_size needs to grow beyond ~100.

---

## TASK-040 — Real ML Promotion (2026-06-01)

### BUG-040a — LOW: SHAP feature list returns empty from pricing real-ML path

**Severity**: Low (the recommendation itself is correct; only the
explainability sidecar is empty)
**Status**: **Fixed in TASK-042** (verified live: 6 SHAP features
returned, top driver `competitor_price_gap` SHAP `+129.73`)
**Module**: Backend / ML

**Symptom**: `POST /api/v1/pricing/optimize` with
`PRICING_USE_REAL_ML=true` returns `top_shap_features: []`. The headline
recommendation, expected uplift, confidence interval, and revenue curve
are all real and well-formed, but the SHAP sidecar that drives the
"why this price" UI panel is empty.

**Root cause** (suspected): `ml.pricing.models.demand.LightGBMGridPolicy`
exposes a `.recommend_price()` that returns the recommendation in the
shape the translator expects, but does not currently route the SHAP
attribution through to the API response. The mock path hardcodes a
sensible `top_shap_features` list; the real path returns its own.

**Fix (deferred)**: Add SHAP TreeExplainer integration to the bootstrap
policy and surface the top-k features through
`ml_translation.ml_recommendation_to_api`.

**Workaround**: The UI gracefully handles an empty list (renders "No
attribution available for this recommendation").

### BUG-040b — MEDIUM: Recruitment SBERT first-call download exceeds request budget

**Severity**: Medium (was: blocks `RECRUITMENT_USE_REAL_ML=true`)
**Status**: **Fixed in TASK-041** (code landed; runtime verification pending Docker restart)
**Module**: Backend / ML / Infrastructure

**Symptom**: With `RECRUITMENT_USE_REAL_ML=true`, the first
`POST /api/v1/recruitment/analyze` triggers
`sentence-transformers.SentenceTransformer('all-mpnet-base-v2')`, which
attempts to download ~420 MB from HuggingFace + fit XGBoost on the
synthetic dataset. The request exceeds the proxy / middleware budget;
`BaseHTTPMiddleware` raises `RuntimeError: No response returned.` and
the request fails with 500 after ~5 minutes.

**Root cause**: Two issues compound. (1) The HuggingFace cache lives at
`/root/.cache/huggingface` inside the container, which is **not bind-
mounted**, so every container recreate re-downloads MPNet. (2) The
cold-start path runs synchronously inside the request, blocking the
handler well past the middleware timeout.

**Fix (planned, two-step)**:

1. *Infra* — add a named volume:
   ```yaml
   volumes:
     - huggingface-cache:/root/.cache/huggingface
   ```
   so the model survives a container recreate.
2. *Backend* — pre-warm on app startup:
   `src/main.py` already has a startup hook; add a fire-and-forget task
   that calls `RecruitmentInferenceClient()._get_ranker()` so the first
   request hits a warm singleton.

**Workaround today**: `RECRUITMENT_USE_REAL_ML=false`. The mock
deterministic-keyword path keeps the recruitment workspace functional.

---

*All bugs should be filed within the same session they're discovered.*
