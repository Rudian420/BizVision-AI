# BizVision AI — Performance Notes

> Performance is a feature. Track every bottleneck and optimization.

---

## Performance Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| API p50 response | < 100ms | 500ms |
| API p99 response | < 500ms | 2000ms |
| ML inference (sync) | < 2s | 10s |
| ML inference (async) | < 30s (Celery) | 120s |
| Frontend FCP | < 2s | 4s |
| Frontend TTI | < 3s | 6s |
| 3D FPS (HIGH tier) | 60fps | 30fps |
| 3D FPS (MED tier) | 60fps | 24fps |
| 3D FPS (LOW tier) | 30fps | 15fps |
| WebSocket latency | < 50ms | 200ms |

---

## Frontend Optimizations

### Bundle Strategy
- Code splitting per module route (`dynamic()` imports)
- Three.js tree-shaking (import only what's used)
- GSAP plugins lazy-loaded per scene
- Font subsetting for Space Grotesk + JetBrains Mono

### 3D Performance Strategy
- GPU instancing for particle systems (one draw call for 100K particles)
- LOD (Level of Detail) for complex 3D models
- Frustum culling — only render visible objects
- Off-screen canvas for background scenes
- `requestIdleCallback` for non-critical updates

### Shader Optimization
- Avoid dynamic branching in GLSL (branch divergence kills GPU performance)
- Use `mediump` precision where full precision not needed
- Pre-compute constants in vertex shader, not fragment
- Texture atlases to minimize texture switches

---

## Backend Optimizations

### Database
- Connection pooling: SQLAlchemy async pool (min=5, max=20)
- Query optimization: EXPLAIN ANALYZE all slow queries
- Indexes: pgvector HNSW index on all embedding columns
- Redis caching: ML predictions cached 5min TTL

### ML Inference
- Model quantization (INT8) for faster inference
- Batch processing for embedding generation
- Async inference via Celery (never block API thread)
- Model pooling: one model instance shared across requests

---

## TASK-039 — Performance Audit + Targeted Optimizations (2026-05-31)

Static-analysis audit across the cinematic landing + module
workspaces + Decision Feed + chatbot streaming. Implemented the
findings most likely to move FPS and main-thread time on real
hardware. This was a **code-only audit** — no actual GPU/Lighthouse
profiling — but every finding was a clearly-identifiable
anti-pattern or known cost.

### Audit scope

| Surface | Files inspected |
|---|---|
| 3D landing | `components/3d/scenes/*` (5 files), `components/3d/primitives/ModulePlanet.tsx`, `components/3d/postfx/PostProcessing.tsx`, `lib/render-tier.ts`, `lib/store/use-scene-store.ts` |
| Smooth scroll + HUD | `components/layout/SmoothScroll.tsx`, `components/ui/HudOverlay.tsx`, `components/ui/ScrollProgress.tsx` |
| Hooks | `hooks/use-mouse-parallax.ts`, `hooks/use-active-module.ts`, `hooks/use-render-tier.ts`, `hooks/use-reduced-motion.ts`, `hooks/use-chatbot-stream.ts` |
| Chatbot streaming | `components/chatbot/MessageThread.tsx`, `MessageBubble.tsx`, `StreamingAssistantBubble.tsx`, `ChatbotWorkspace.tsx`, `lib/chatbot/ws.ts` |
| List rendering | `components/recruitment/CandidateRow.tsx`, `components/audits/AuditTimeline.tsx`, `components/common/ModuleHistoryShell.tsx` |

### Findings + fixes

#### 1. CRITICAL: Three.js GPU resources never disposed

**Symptom**: BufferGeometry + ShaderMaterial across the 4 hero
scenes own GPU-side buffers + compiled shader programs.
React-three-fiber does NOT auto-dispose them on unmount. Every
route change away from the landing leaks 100K particles' worth of
VRAM (NeuralGalaxy) + 5 holographic shader programs (planets) + a
5-line shader program (energy connections) + the ambient starfield
points buffer.

**Impact**: VRAM leaks accumulate across session navigation. On
long-lived tabs the GC may never reclaim them. On low-VRAM mobile
GPUs this is the difference between "fast first run" and "browser
killed the tab on 3rd navigation back".

**Fix**: Added `useEffect` cleanup that walks the mounted group and
calls `.dispose()` on every geometry + material it finds. Applied
to:
- `components/3d/scenes/NeuralGalaxy.tsx`
- `components/3d/scenes/AmbientStars.tsx`
- `components/3d/scenes/EnergyConnections.tsx`
- `components/3d/primitives/ModulePlanet.tsx`

**Verification**: Code-only. Real verification would be in Chrome
DevTools → Memory → "Detached GPU memory" trending flat across
navigations.

#### 2. HIGH: HUD 1Hz clock re-renders entire overlay

**Symptom**: `HudOverlay` owned a `clock` state updated every
1000 ms via `setInterval`. Each tick re-rendered the whole
component — corner brackets, status strip, tier label, AND the
module ticker (with its 5-element map). Brackets + ticker have
nothing to do with the clock; they were reconciling for no
visible benefit.

**Impact**: Continuous low-grade main-thread work even when the
page is otherwise idle. Battery hit on mobile; jank risk if other
work happens to land in the same frame.

**Fix**: Lifted the clock into its own `<ClockReadout>` component
so its `setState` ripples to a single `<span>UTC HH:MM:SS</span>`.
Wrapped `<ModuleTicker>` and `<Bracket>` in `React.memo` so the
parent's other re-renders don't propagate either.

**File**: `components/ui/HudOverlay.tsx`

#### 3. HIGH: MessageThread auto-scroll runs per WS token

**Symptom**: `MessageThread`'s `scrollIntoView` effect listed
`streamingContent` + `toolCalls` in its dependency array.
Streaming a 200-token response fires the effect ~200 times —
each with `behavior: 'smooth'`. The smooth scrolls overlap, the
browser cancels them, the scroll position jitters.

**Impact**: Visible bottom-edge jitter during streaming.
Per-token main-thread cost from re-arming a smooth-scroll
animation.

**Fix**: Branch `behavior` on `isStreaming` — instant snap while
streaming (`'auto'`), smooth scroll for non-streaming events
(turn count change, REST completion). Wrap the call in
`requestAnimationFrame` so multiple state updates in the same
frame coalesce into one paint.

**File**: `components/chatbot/MessageThread.tsx`

#### 4. MEDIUM: Hot list rows not memoised

**Symptom**: `MessageBubble`, `CandidateRow`, audit-feed rows
all re-render on every parent state change. During WS streaming
the chatbot thread re-renders all persisted bubbles on every
token tick because their parent re-renders.

**Impact**: Quadratic-ish growth in render cost as
conversation/ranking length increases.

**Fix**: Wrapped `MessageBubble` and `CandidateRow` in
`React.memo`. The default `Object.is` comparison is safe
because:
- MessageBubble's props are primitives + arrays from React
  Query's structurally-shared data (identical responses produce
  identical references).
- CandidateRow gets one `CandidateRankingResult` reference per
  analyze.

**Files**:
- `components/chatbot/MessageBubble.tsx`
- `components/recruitment/CandidateRow.tsx`

`AuditTimeline` row already had stable structure but is internal
to its parent and rendered with explicit keys; deferring memo
unless profiling shows it matters.

#### 5. MEDIUM: CinematicCamera segment search is O(N) per frame

**Symptom**: The camera waypoint path has 14 entries. Each frame
the segment containing the current scroll `t` was found by a
linear scan from index 0. At 60 fps × 14 = 840 comparisons per
second.

**Impact**: Small but in the hot path. Scroll moves monotonically,
so the next frame's segment is almost always the same as the
last frame's.

**Fix**: Cache the last segment index in a ref. Each frame, check
whether the cached index still brackets `t`. If yes → O(1). If
the user has scrolled past a boundary → walk forward/backward
only as far as needed.

**File**: `components/3d/scenes/CinematicCamera.tsx`

### Issues observed but not patched in this pass

These are documented because they need design judgement or
runtime profiling before committing to a fix.

- **NeuralGalaxy shader uses Simplex noise per particle per
  frame**. At 100K particles on HIGH tier this is ~300K snoise
  evaluations per frame on the GPU. Acceptable on discrete
  GPUs; mobile MED tier already caps at 50K. If profiling shows
  GPU saturation on MED tier, consider reducing noise scale or
  evaluating only every Nth frame.
- **Drei's `<ScrollControls>` is NOT used** — ADR-018 chose
  window scroll as single source of truth. No issue, just
  noting the architecture choice was already a perf-aware one.
- **Lenis runs an unconditional rAF** in `SmoothScroll`. This is
  the right pattern; the cost is bounded.
- **Postprocessing stack already tier-gated** in
  `PostProcessing.tsx` per ADR-016. Good.
- **`'use client'` is everywhere on the landing route**. With
  fully interactive 3D + Zustand store + Lenis there's no
  server-rendered content to send anyway, so the initial-paint
  cost is set by the bundle, not the SSR/CSR split. Splitting
  static text into a server component would only matter if
  search-engine SEO was a goal.
- **Bundle: the landing + ALL workspaces sit in the same Next
  route group**. SceneStage is already dynamic-imported
  (`{ ssr: false }`); the per-workspace heavy code (Three.js
  visualisations for pricing/forecasting/sustainability when
  they ship wave-3 3D) would benefit from the same pattern.
  Today the workspaces are 2D-only so the bundle is acceptable.
- **No virtualization on lists**. AuditTimeline + history
  pages cap at 20 rows per page so a fixed-window list is fine.
  If page_size goes above ~100, react-virtual would be the next
  intervention.

### How to confirm gains on real hardware

Numbers below should improve. They are NOT measured in this
audit (which was static).

1. **VRAM stability after route navigation** (fix #1):
   `chrome://gpu` → "GPU Memory" trend should be flat across
   landing → /dashboard → landing round-trips.
2. **Main thread idle time** (fix #2): Chrome DevTools
   Performance → record 10s on landing. Long tasks per second
   from `HudOverlay` should drop from ~1/s to ~0.05/s (one per
   minute, when the corner clock rolls).
3. **Streaming jitter** (fix #3): visual inspection. Send a
   long chatbot message and watch the thread bottom edge during
   streaming. Should stick instead of jitter.
4. **Scroll responsiveness** (fix #5): Chrome DevTools
   Performance flame chart during landing scroll. CinematicCamera
   `useFrame` should be ≤ 0.05ms; was likely ≤ 0.1ms before.
5. **Re-render counts** (fix #4): React DevTools profiler →
   trigger an analyze → expand/collapse a CandidateRow.
   Sibling rows should NOT re-render.

### Files touched

```
frontend/src/components/3d/scenes/NeuralGalaxy.tsx
frontend/src/components/3d/scenes/AmbientStars.tsx
frontend/src/components/3d/scenes/EnergyConnections.tsx
frontend/src/components/3d/scenes/CinematicCamera.tsx
frontend/src/components/3d/primitives/ModulePlanet.tsx
frontend/src/components/ui/HudOverlay.tsx
frontend/src/components/chatbot/MessageThread.tsx
frontend/src/components/chatbot/MessageBubble.tsx
frontend/src/components/recruitment/CandidateRow.tsx
```

### Verification

- Backend `pytest tests/unit/` excluding pre-existing forecasting
  drift → **125/125 PASS** in 3.15s. No regression (no backend
  changes in this task).
- Frontend `npm run type-check` → 0 errors.
- Frontend `npm test` → **283/283 vitest tests pass** across 25
  files in 26.42s. No regression.
- Frontend `npx eslint` on touched files → clean.

---

*Update this file whenever a significant optimization is made or bottleneck discovered.*
