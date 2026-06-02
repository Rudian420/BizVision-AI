# BizVision AI — UI/UX Direction & Visual System

> The artistic bible for BizVision AI. Every visual decision flows from this document.

---

## Core Visual Identity

### The Feeling
**"A living intelligence system that thinks alongside you."**

Users should feel they are inside an AI command center — not looking at a dashboard, but inhabiting an intelligent space that responds to their presence and intention.

### Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Spatial Intelligence** | 3D space as a metaphor for data relationships |
| **Living Data** | Everything breathes, pulses, reacts — no static elements |
| **Cognitive Clarity** | Complexity revealed progressively, never dumped |
| **Cinematic Narrative** | The interface tells a story as users navigate |
| **Emotional Resonance** | Color, motion, and sound design evoke trust and intelligence |

---

## Color System

### Primary Palette

```
--color-void:        #050A14   /* Deep space background */
--color-abyss:       #080F1E   /* Secondary backgrounds */
--color-surface:     #0D1929   /* Card surfaces */
--color-surface-2:   #112035   /* Elevated surfaces */
--color-border:      #1A2F4A   /* Subtle borders */

--color-cyan:        #00F5FF   /* Primary brand — electric intelligence */
--color-cyan-dim:    #00B8BF   /* Secondary cyan */
--color-cyan-glow:   rgba(0, 245, 255, 0.15) /* Ambient glow */

--color-gold:        #FFB800   /* Neural gold — insights, warnings */
--color-gold-dim:    #CC9200   /* Secondary gold */

--color-violet:      #7C3AED   /* Deep intelligence — AI reasoning */
--color-violet-dim:  #5B21B6   /* Secondary violet */

--color-success:     #10F07C   /* Positive metrics */
--color-danger:      #FF3B6B   /* Alerts, critical data */
--color-neutral:     #8AA0B8   /* Secondary text */

--color-text-primary:   #E8F4FF  /* Primary text */
--color-text-secondary: #8AA0B8  /* Secondary text */
--color-text-muted:     #4A6080  /* Muted/disabled */
```

### Module Accent Colors

| Module | Primary Accent | Secondary | Glow |
|--------|---------------|-----------|------|
| Recruitment | `#00F5FF` (Cyan) | `#00B8BF` | Cyan neural |
| Pricing | `#FFB800` (Gold) | `#FF8C00` | Gold pulse |
| Forecasting | `#7C3AED` (Violet) | `#A855F7` | Violet wave |
| Sustainability | `#10F07C` (Emerald) | `#059669` | Green breathe |
| Chatbot | `#FF3B6B` (Coral) | `#E11D48` | Coral orbit |

---

## Typography

### Font Stack

```css
--font-ui:      'Space Grotesk', 'DM Sans', system-ui, sans-serif;
--font-data:    'JetBrains Mono', 'Fira Code', monospace;
--font-display: 'Space Grotesk', sans-serif;
```

### Type Scale

```
--text-xs:   11px  / 1.4  (data labels, micro text)
--text-sm:   13px  / 1.5  (secondary content)
--text-base: 15px  / 1.6  (body text)
--text-lg:   18px  / 1.5  (lead text)
--text-xl:   22px  / 1.4  (headings)
--text-2xl:  28px  / 1.3  (module titles)
--text-3xl:  36px  / 1.2  (hero titles)
--text-4xl:  48px  / 1.1  (display)
--text-5xl:  64px  / 1.0  (cinematic)
--text-hero: 96px  / 0.95 (landing hero)
```

---

## 3D Visual Systems

### Landing Page — Neural Intelligence Hero

**Scene**: A vast neural network rendered as a galaxy of interconnected nodes floating in deep space. The 5 AI modules are represented as planetary systems, each with orbiting particles representing data.

**Implementation**:
```javascript
// GPU particle system — 100K particles
// GSAP scroll-driven: particles converge as user scrolls
// Shader: custom GLSL with SDF-based glow
// Post-processing: bloom, chromatic aberration, vignette
```

**Animation Sequence** (scroll-driven):
1. Camera starts: wide view of data galaxy
2. As user scrolls: zoom into neural network core
3. Particles self-organize into the BizVision logo
4. Module planets separate and pulse
5. Hero text emerges from particle dissolution

### Module 1 — Recruitment: Candidate Constellation

**Scene**: Candidates float as luminous orbs in 3D space. Distance from a central "ideal candidate" star represents semantic similarity. Lines connect similar candidates. Clicking an orb zooms into that candidate's SHAP explanation.

**Shader**: Custom vertex shader for orbital motion, fragment shader for holographic glow
**Interaction**: Mouse-hover → orbit highlight, click → SHAP detail panel rises from particle

### Module 2 — Pricing: Price Surface

**Scene**: A 3D price surface (demand × price → revenue) rendered as a rippling holographic mesh. The optimal price point is a glowing peak. Monte Carlo scenarios appear as transparent layers.

**Shader**: GLSL heightmap shader with animated waves, color-mapped by revenue
**Interaction**: Drag to rotate surface, hover shows price/demand/revenue tooltip

### Module 3 — Forecasting: Temporal Rivers

**Scene**: Time flows as rivers of light — base case, bull, bear scenarios as three streams of different brightness/color. Rivers branch at decision points. Executive AI insights emerge as floating cards.

**Shader**: Animated flow field shader (noise-based velocity)
**Interaction**: Scroll through time, click scenario branches

### Module 4 — Sustainability: Living ESG Ecosystem

**Scene**: A living city model that transforms based on ESG score — at low score it's grey and industrial, at high score it blooms with greenery and solar panels. Particles represent carbon molecules.

**Shader**: Procedural tree growth shader, atmosphere scattering
**Interaction**: Drag sustainability sliders, city transforms in real-time

### Module 5 — Chatbot: AI Avatar

**Scene**: A central pulsating orb (the Executive AI) with reasoning streams visualized as glowing neural paths. When the AI is thinking, particles flow toward the center. When outputting, they flow outward.

**Shader**: SDF metaball shader for the orb, particle flow lines
**Interaction**: Speaks directly to the AI, responses appear as spatial text

---

## Motion System

### Animation Principles

1. **Physics-first**: Spring physics for all UI animations (no ease functions)
2. **Anticipation**: UI elements slightly retreat before expanding
3. **Follow-through**: Elements overshoot and settle
4. **Secondary motion**: Background particles always react to primary actions
5. **Hierarchy**: Cinematic sequences > module transitions > micro-interactions

### Timing Scale

```
--duration-micro:    80ms   (button states)
--duration-fast:     200ms  (card reveals)
--duration-medium:   400ms  (panel transitions)
--duration-slow:     800ms  (module navigation)
--duration-cinematic: 2000ms (hero sequences)
```

### Spring Configuration (Framer Motion)

```javascript
const springs = {
  snappy:   { type: 'spring', stiffness: 400, damping: 30 },
  smooth:   { type: 'spring', stiffness: 200, damping: 25 },
  gentle:   { type: 'spring', stiffness: 100, damping: 20 },
  cinematic:{ type: 'spring', stiffness: 50,  damping: 15 }
}
```

---

## Shader Library Architecture

```
frontend/src/shaders/
├── particles/
│   ├── neural.vert.glsl        # Neural particle system
│   ├── neural.frag.glsl
│   ├── flow.vert.glsl          # Flow field particles
│   └── flow.frag.glsl
├── surfaces/
│   ├── holographic.frag.glsl   # Holographic scanline effect
│   ├── price-surface.vert.glsl # Animated 3D price mesh
│   └── planet.frag.glsl        # Module planet shaders
├── postfx/
│   ├── god-rays.frag.glsl      # Volumetric light
│   ├── chromatic.frag.glsl     # Chromatic aberration
│   └── scanline.frag.glsl      # CRT scanline overlay
└── utils/
    ├── noise.glsl               # Perlin/Simplex noise
    ├── sdf.glsl                 # SDF primitives
    └── math.glsl                # Math helpers
```

---

## Scroll Experience Architecture

### Scroll Scenes (GSAP ScrollTrigger)

```
[0%]    Landing Hero — Neural galaxy, BizVision logo emerges
[15%]   "What is BizVision AI?" — modules fly in from deep space
[30%]   Recruitment scene — candidate constellation assembles
[45%]   Pricing scene — price surface rises from ocean
[60%]   Forecasting — temporal rivers animate
[75%]   Sustainability — city ecosystem blooms
[90%]   Chatbot — AI avatar awakens
[100%]  CTA — "Enter the Intelligence System"
```

### Camera Choreography

Each scroll section has a defined camera path:
- Start position, end position, focal length, DOF parameters
- Theatre.js timeline controls the camera keyframes
- GSAP ScrollTrigger maps scroll progress to timeline progress

---

## UI Component Philosophy

### No Bootstrap, No Generic Templates

Every component is custom-engineered:
- **DataCard**: Glass morphism with animated border gradient
- **MetricDisplay**: Number animation with countup + color reaction
- **AIInsightBubble**: Appears with particle dissolution effect
- **ModuleNav**: 3D tilting icon system with depth parallax
- **ExplanationPanel**: SHAP bar chart with animated reveal
- **FairnessGauge**: Circular gauge with neural glow effect

### Glass Morphism System

```css
.glass {
  background: rgba(13, 25, 41, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(0, 245, 255, 0.1);
  box-shadow: 
    0 4px 32px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(0, 245, 255, 0.05);
}
```

---

## Accessibility Considerations

- All animations respect `prefers-reduced-motion`
- 3D scenes have 2D fallback modes
- Color contrast meets WCAG AA on all text
- Screen reader annotations on all interactive elements
- Keyboard navigation for all module features

---

*Last updated: 2026-05-27*
