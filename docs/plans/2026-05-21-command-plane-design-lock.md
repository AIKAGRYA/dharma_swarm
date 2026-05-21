# Command Plane Design — LOCK

**Date locked:** 2026-05-21
**Owner:** Dhyana
**Status:** LOCKED (palette + architecture + first ship); 0 open decisions
**Provenance:** 6-agent research team + 4-agent adversarial stress-test, grill-me interview, full dashboard inventory of 26 routes. Working brief at `~/.claude/projects/-Users-dhyana/` chat history 2026-05-21.

---

## TL;DR

A Nihonga-anchored, observatory-leaning operator cockpit. 7 verb-zones with shared grammar (NOT shared chrome). 2D canonical, 3D as garnish per zone gated on a 60fps benchmark. Numbers are the protagonist; UI chrome is stage-hand. Migration via feature-flag from existing `/dashboard/control-surface`. First ship: refine COCKPIT center zone with new tokens + grammar + optional 3D toggle.

---

## Identity

| Decision | Value |
|---|---|
| Species | Observatory + Cockpit (observatory-leaning) |
| Container | Web (Next.js) primary → Desktop (Tauri 2 shell) → Mobile later (React Native / Capacitor) |
| Theme | Adaptive (auto-follows OS) + manual moon/sun toggle override |
| Density | Variable: focused (50-60% data) / overview (~75% data); expand later |

## Rendering architecture

- **2D is canonical truth.** Every zone has a clean 2D rendering (`<ZoneSheet/>`).
- **3D is opt-in per zone.** A `<ZoneSpace/>` only ships when that zone proves a measurable operator gain.
- **`<View>` per zone is mandatory** if any 3D — one `<Canvas>`, N viewports, isolated scenes/cameras.
- **Tab key toggles 2D/3D per zone.** Independent of theme (light/dark). Orthogonal axes.
- **Auto-fallback to 2D** when WebGL/GPU/battery/screen-size or `prefers-reduced-motion` says so.
- **Renderer-agnostic data layer**: FastAPI → TanStack Query → typed row models → either renderer.

```
FastAPI ──→ TanStack Query ──→ typed row models (canonical truth)
                                       │
                              ┌────────┴────────┐
                              ▼                 ▼
                       <ZoneSheet rows />   <ZoneSpace rows />
                          (2D view)           (3D view)
```

## The 7 R3F architectural rules (3D layer contract)

1. React Three Fiber declarative JSX only. No raw Three.js scene graphs.
2. **drei** for primitives (cameras, lights, billboards). No custom math when drei has a primitive.
3. Declarative motion via **Motion 3D** or **react-spring-three**. No imperative `useFrame` state machines; refs + Zustand `getState()` reads.
4. **Typed props per zone**. Data layer separate from render layer.
5. **Storybook story for every 3D zone.** Future-model handoff depends on this.
6. **One ADR per visual decision.** Camera, depth, motion language.
7. **No custom shaders in v1.** drei materials + standard PBR only.

**Text legibility split (mandatory):**
- `drei.Text` for ≤50 in-scene labels per zone (SDF, GPU-accelerated)
- `drei.Billboard` + `drei.Text` for camera-facing labels
- `drei.Html` for tabular data rows (≤20 simultaneous; virtualize the rest)
- Mixing these wrong is the #1 legibility failure mode.

**Performance budget:** 60fps locked target, 30fps floor. <400 total draw calls across all 7 zones. ~50 per zone. Tested on M2 Air 8GB. M1 8GB auto-falls-back to 2D.

## Information architecture — 7 verb-zones

**Shared grammar, NOT shared chrome.** Each zone exposes `{verb, signal, cadence, children?}` but renders a verb-appropriate surface. Forcing identical chrome across heterogeneous verbs is the Procrustean failure mode (Microsoft Bob, BumpTop, Pad++).

**Hexagonal 1+6 spatial layout** as positioning frame only — never render the hex outline. Center holds primacy (z≈+0.5); satellites orbit at z=0 plane equidistant.

**Asymmetric depth.** Default 2 levels; COCKPIT actuation = 1; MAP/REMEMBER go to 3 where the data wants it. Total endpoints ~80-120, not uniform 7³=343.

**Navigation primitive: focus + context (Furnas DOI).** One zone is focal; the other six render at reduced fidelity but stay visible. This is what trading desks and ICU centrals do; what kept Pad++'s descendants alive.

| # | Zone | Verb | Nihonga affinity | Routes that live here |
|---|---|---|---|---|
| 1 | **COCKPIT** (center) | operate | Gunjō 群青 | control-surface (canonical), agents, tasks. `synthesizer` folds in. |
| 2 | **TALK** | converse | Rokushō 緑青 | command-post, glm5, qwen35, claude, codex-composer, models |
| 3 | **WATCH** | observe | Gofun on Sumi (no accent — restraint) | observatory, runtime, telemetry |
| 4 | **JUDGE** | evaluate | Ōdo 黄土 | eval, audit, gates |
| 5 | **MAP** | relate | Murasaki 紫 | ontology, lineage, ecosystem, modules |
| 6 | **SENSE** | track trails | Bengara 弁柄 | stigmergy, heatmaps, hot paths, evolution |
| 7 | **REMEMBER** | recall | Sumi-on-Gofun + Bengara seal | log, timeline |

Reserved (hidden until real): **COMPOSER** (blocks, workflows) — possibly as overlay/modal verb, not 8th zone.

## Cadence (no metaphor)

Each zone refreshes at its own rate. Precedent: Bloomberg Launchpad heterogeneous-cadence components, ICU central monitors (ECG 250Hz, SpO₂ 1Hz, trend numerics every 10s), NORAD video walls. **Uniform frame, heterogeneous content cadence.** No "heartbeat / living system" metaphor language — call it `cadence` in code.

| Zone | Cadence |
|---|---|
| COCKPIT | realtime (tool calls/sec) |
| TALK | realtime (token stream) |
| WATCH | second (telemetry refresh) |
| JUDGE | day (score deltas) |
| MAP | minute (edge events) |
| SENSE | minute (mark events) |
| REMEMBER | hour (log entries) |

## Palette — Nihonga / iwa-enogu (岩絵具)

Mineral pigments from natural stones. 400+ years of provenance through Hokusai, Sesshū, Ogata Kōrin. Each color has semantic purpose and is used with discipline — like in actual Nihonga painting.

| Pigment | 日本語 | Hex | System role | Where it lives |
|---|---|---|---|---|
| Sumi | 墨 | `#0F0D0B → #1A1715` | Substrate (warm-ink graphite, not cool) | Everything beneath |
| Gofun | 胡粉 | `#F2EDE3` at 92% | Text base (oyster-shell white) | All prose, labels |
| Tetsu-iro | 鉄色 | `#2A2522` | Hairline borders (warm gray) | All in-plane dividers |
| **Gunjō** | 群青 | `#1F4F8C` | Identity / actuation (azurite) | Active surface, focus, primary action, COCKPIT |
| **Rokushō** | 緑青 | `#6C8E7A` | Pulse / fresh signal (malachite) | Live data, ambient dot on most-recent value, TALK |
| **Murasaki** | 紫 | `#5B3E72` | Recall / contemplation (gentian) | REMEMBER, MAP, deep history |
| **Ōdo** | 黄土 | `#A57A35` | STALE / aging | Degraded data, JUDGE |
| **Bengara** | 弁柄 | `#7A3E2A` | Earthen depth / weight (iron oxide) | Evidence chain, SENSE, permanent records |
| **Shu** | 朱 | `#9C2A1F` | FAIL / urgent (vermillion) | Failure, drift — used sparingly like shrine vermillion |

**Discipline:** a Nihonga painting uses 3-5 mineral colors total, not 20. Same here. Adding a 10th color requires removing one. **Each color has provenance — no synthetic accents.**

**Killed forever:** cyan, phosphor green, purple-magenta gradients, AI-palette tells.

## Typography

| Layer | Value |
|---|---|
| Primary (mono) | **Commit Mono** (free, neutral, mechanical, not saturated) |
| Prose secondary | Söhne Mono / GT America Mono / Inter Display (NOT Geist — shadcn-saturated in 2026) |
| Upgrade path v2 | Berkeley Mono ($75) once design is proven |
| Numeric features | `font-feature-settings: 'tnum'` everywhere |
| Hierarchy | Numbers > body. Numbers are 1-2 sizes larger than surrounding prose. |

## Motion

Three vocabularies, named tokens in `motion.ts`:

| Token | Use | Curve |
|---|---|---|
| `motion.instant` | State transitions (badge change, row select) | 80-120ms `cubic-bezier(0.2, 0, 0, 1)` |
| `motion.navigate` | Route change, panel slide | 200-240ms `cubic-bezier(0.4, 0, 0.2, 1)` |
| `motion.ambient` | Data pulse, fresh-value dot | 800-1200ms linear/sine |

**No spring physics.** Motion is information, not decoration.

## Shadows & elevation

- **In-plane (rows, panels, cards in-flow):** no shadows. Hairlines only.
- **Floating UI (cmdk, modals, popovers, tooltips):** one elevation tier — `0 8px 24px rgba(0,0,0,0.4)`.
- Two tiers, not zero, not five.

## Signature visual move

**Numbers as brand.** Tabular monospace numerals are the protagonist on every screen — IDs, timestamps, agent counts, latencies, metrics. Set 1-2 sizes larger than surrounding prose, in Gunjō at full saturation when active, Gofun at 92% at rest, with a 1px Tetsu-iro baseline rule under each numeric cluster. Most-recent value gets the `motion.ambient` pulse on a single Rokushō dot (NOT the number flashing).

**This is the dashboard where the numbers are the brand.** Everything else is restraint.

## Stack

| Layer | Choice |
|---|---|
| Foundation | **Next.js 16 + React 19.2 + React Compiler 1.0** (bleeding edge; user accepted R2 risk) |
| Container | Tauri 2 (`dashboard/src-tauri/` already exists) |
| Styling | Tailwind v4 (CSS-first `@theme`, OKLCH) + Panda CSS for runtime tokens |
| Components | Radix Primitives raw + **custom shadcn registry** (hosted at `/r/`) |
| State | Zustand (module) + Jotai (atomic, RSC-safe) + TanStack Query v5 (server) |
| Tables | TanStack Table v8 + TanStack Virtual + Glide Data Grid (hot tables) |
| Charts | Apache ECharts + TradingView Lightweight Charts |
| 3D | React Three Fiber + drei + Motion 3D |
| Motion | Motion + GSAP (scroll-triggered only) |
| Command palette | cmdk |
| Panes | react-resizable-panels |
| Testing | Vitest Browser Mode + Storybook 9 + Argos visual regression |
| Tooling | Biome local + Oxlint CI + Bun install |
| Realtime | SSE for telemetry + RSC streaming for shell + WebSocket only for bidirectional command channel |

## MCPs to install

```bash
# Priority 5
claude mcp add shadcn -- npx -y shadcn@latest registry mcp
claude mcp add --transport http figma  https://mcp.figma.com/mcp
claude mcp add --transport http vercel https://mcp.vercel.com
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
claude mcp add --transport http linear https://mcp.linear.app/mcp

# When cockpit moves from "works" to "Palantir-grade"
claude mcp add --transport http builder https://mcp.builder.io/dsi
claude mcp add --transport http posthog https://mcp.posthog.com/sse
```

## Safety actions

- `claude mcp remove puppeteer` — archived, open CVEs (SSRF, sandbox bypass)
- **Do NOT install** the Vercel Claude Code plugin (April 2026 disclosure: harvests prompts). Use HTTP MCP above instead.
- Remove archived `@modelcontextprotocol/server-puppeteer` from npm dependencies.

## Skills to invoke

- `/frontend-design` (plugin) — first move on any cockpit screen
- `/brainstorming` (superpowers) — before any creative work
- `/writing-plans` (superpowers) — tracer-bullet vertical slices
- `/claude-api:webapp-testing`
- `/everything-claude-code:nextjs-turbopack`
- `/everything-claude-code:design-system`
- `/verification-before-completion`
- `/superpowers:subagent-driven-development` — for parallel zone work

## First ship — COCKPIT center zone

Refine the existing `/dashboard/control-surface` (114 LOC, composing NeedsJohnQueue / SystemTruthMatrix / EvidenceDrawer / RuntimeRail).

**Branch:** `feat/cockpit-v2-nihonga`

**Scope:**
1. New token system in `dashboard/src/styles/tokens.css` — Nihonga palette + 3 motion vocabularies + shadow tier
2. Custom shadcn registry scaffolded at `dashboard/registry.json` + `dashboard/src/registry/r/*.json` with 6 primitives (Numeral, StatusBadge, EvidenceRow, ZoneFrame, Glyph, Pane)
3. Refactor existing 4 cockpit components to use new tokens + grammar
4. 2D variant: refined version of current control-surface page
5. 3D variant: instanced-mesh telemetry field ≤200 nodes; 1 drei.Text title; 1 drei.Html data panel pinned bottom-right of `<View>`
6. Tab key toggles 2D/3D
7. Feature-flag behind `?v=2` — existing page keeps working

**Acceptance criteria:**
1. 60fps locked at full data load on M2 Air 8GB (3D variant)
2. Tab→2D transition <100ms
3. All 7 R3F architectural rules satisfied
4. Storybook story for 3D variant
5. ADR-0004 documents camera placement decision

**If hits all 5:** greenlight zones 2-7 same rules.
**If misses any:** kill always-3D; ship 2D-only refinement; reserve 3D for MAP only (graph topology where it earns).

## Migration plan

1. PR 0 — repair `@tanstack/react-table` lockfile drift; repair `terminal_engine.events` missing import (mechanical bugs from the dashboard-build assessment).
2. PR 1 — `feat/cockpit-v2-nihonga` (this doc's first ship).
3. PR 2 — MAP zone in 3D (graph topology) IF PR 1 hits all 5 criteria.
4. PR 3+ — remaining zones one at a time; each gated by the same 5 acceptance criteria.

`/synthesizer` folds into COCKPIT (duplicate). `/opportunities` is broken-nav, separate cleanup. `/codex-composer` (untracked) stays deferred until a real PR exists.

## What this document is NOT

- Not an R_V framing. No R_V framing anywhere in design.
- Not a "4:30 AM ritual" framing. Design merits only.
- Not a metaphor-heavy "living system" framing. Cadence is the term in code; the metaphor is dead.

## Provenance

- 6 research scouts (claude-code, vercel-lovable, palantir-ui, mcp-ecosystem, frontier-stack)
- 4 adversarial stress-testers (r3f-craft-specialist, fractal-architect, red-team, craft-reviewer)
- Grill-me interview cycle establishing species, container, theme, density, 3D model, IA, palette
- Full inventory of 26 existing dashboard routes
- Cross-cutting convergence captured in the running synthesis

## Open follow-ups (deferred, not blocking)

- Final identity-accent name (Gunjō is the canonical choice but secondary nihonga colors per zone may need further palette tuning)
- Berkeley Mono purchase decision (currently $75 deferred until design proven with Commit Mono)
- Exact hexagonal camera default for 3D mode
- Per-zone Storybook seed components
