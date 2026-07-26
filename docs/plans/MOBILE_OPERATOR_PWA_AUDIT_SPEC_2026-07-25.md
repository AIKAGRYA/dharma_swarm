# Mobile Operator Companion — Frontend Audit & Phased PWA Renovation Spec

**Date:** 2026-07-25
**Role:** working_plan (subordinate to `docs/governance/CANONICAL_DOC_STACK.md`)
**Audited checkout:** `bb3eb9f4fb9f` (base `origin/main`, ahead 0 / behind 0)
**Stop condition:** This document only. No `dashboard/` or `api/` code is committed in this pass. A docs-only PR is not hot-path (`scripts/runtime/pr_merge_control.py:88-103` — no pattern prefixes `docs/plans/`); the first renovation commit under `dashboard/` or `api/` IS hot-path and requires `make agent-build-preflight PACKET=<path>` plus closeout (`CLAUDE.md` § Before Anything Else).

Every claim below carries a `file:line` citation (observed in this checkout) or a runnable command. Aggregate counts are reproducible via the commands in §9 — do not re-cite them from this doc after the tree moves.

---

## 0. Executive summary

The dashboard (`dashboard/`, Next.js 16.1.6 / React 19.2.3 / Tailwind 4 — `dashboard/package.json:29-30,48`) is a modern, desktop-only web operator surface. **Mobile/PWA readiness is 0%**: no viewport export (`dashboard/src/app/layout.tsx:36-39` exports `metadata` only), no manifest, no service worker, no icons (`dashboard/public/` contains only 5 Next scaffold SVGs), and a shell hard-wired to a fixed 260px sidebar (`dashboard/src/app/layout.tsx:64`; `dashboard/src/components/layout/Sidebar.tsx:86`). Phones get Next's default `width=device-width` viewport (App Router emits it when no export exists), but the fixed shell leaves ~130px of usable content width on a 390px screen.

The renovation is nonetheless tractable because the stack needs no migration, the nav is data-driven (`dashboard/src/lib/dashboardNav.ts:47-98`), and a minority of routes carry the operator value. The plan: a 6-phase renovation converting the existing dashboard into an installable, offline-tolerant, touch-first **operator companion** for the phone-first operator context recorded in `docs/governance/ACTIVE_TRACK.yaml:2023` ("operator walking Japan … ~15% interaction, phone-first").

Hard blockers found beyond CSS:

1. **Realtime is loopback-locked with no config escape.** The WS session minter rejects any non-localhost origin via a hardcoded set (`dashboard/src/lib/wsSession.ts:12`; `dashboard/src/app/dharma-internal/ws-auth/route.ts:13-23`). Every live feature is dead on LAN/tunnel until this is configurable.
2. **No configuration authenticates both transports from a browser.** With `DASHBOARD_API_KEY` set (the only safe off-loopback mode), WS works via cookie but the Next rewrite proxy injects no `Authorization` header (`dashboard/src/lib/dashboardProxy.ts:10-19`; zero `Authorization` hits in `dashboard/src`), so every REST call 401s (`api/main.py:484-486`).
3. **No mobile-network resilience.** WS reconnect gives up permanently after 10 attempts (`dashboard/src/lib/ws.ts:188-190`), no visibility/online handlers exist anywhere in `dashboard/src` (§9 cmd 6), and phone unlock refires every query mounted on the active route at once (`dashboard/src/app/providers.tsx:17-20`; the runtime surfaces alone mount a 6-request fan-out per tick and telemetry mounts 9 keys, §4.3).

Governance: the active portfolio is at its hard ceiling (`max_active: 10`, `docs/governance/ACTIVE_TRACK.yaml:80`; 10 tracks ACTIVE per the generated digest in `CLAUDE.md`), so the draft track in §8 is a **proposal**, not an admission — an 11th ACTIVE track is a CI ERROR (`scripts/governance/check_track_status.py:1651-1654`).

---

## 1. Decision frame

Operator-ratified in the session that produced this audit:

| Decision | Choice |
|---|---|
| Platform | **PWA renovation of the existing dashboard** — no native wrapper, no second app |
| Scope | **Operator companion first** — mobile-first excellence for the operator core; long tail responsive best-effort |
| Deliverable | This audit + phased spec + draft track proposal (docs-only) |
| Access | Undecided → recommendation in §6 |

Doctrine this plan binds itself to:

- "TUI is the primary operator cockpit." / "This dashboard is the web operator surface." (`dashboard/README.md:10-11`). The PWA is the web operator surface made carryable — not a competing cockpit.
- "Recovery and upgrades should be surgical. **Do not invent a third website.**" (`dashboard/README.md:15`). This plan renovates the existing Next app in place; it creates no new site, no new framework target.
- Cockpit is a read-only projection, "NOT an authority or a command surface" (`ACTIVE_SURFACE_MANIFEST.yaml:209-210`; `docs/ops/LIVE_OPS_COCKPIT.md`). Mobile cockpit views stay read-only; command actions live on the surfaces that already own them (chat, tasks, runtime interrupts).
- Dashboard work constraints from the prior SSOT plan: no new substrate, no 3D UI, wire existing API routers rather than adding endpoints (`docs/plans/2026-05-22-dashboard-ssot-architecture.md:17-19`).
- Any nav/route change must keep `ACTIVE_SURFACE_MANIFEST.yaml` in agreement with `dashboardNav.ts`, `controlPlaneRouteDeck.js`, and registered routers (`ACTIVE_SURFACE_MANIFEST.yaml:3-4`).

Vision hook (why this serves declared intent, not invented scope): the standing operator context is phone-first at ~15% interaction (`docs/governance/ACTIVE_TRACK.yaml:2023`); phone-gated decisions already exist as blocking next-items (`ACTIVE_TRACK.yaml:2003,2007,2015`); remote-ops prior art assumes "phone-only" operation (`docs/plans/handoffs/REMOTE_OPS_HANDOFF_DEVIN_2026-07-07.md:10,14,107`). The NORTH_STAR trust gate ("when I trust it we can go balls to the wall", `docs/vision_maps/NORTH_STAR.md:145-147`) is exactly what a glanceable, truthful phone surface serves.

---

## 2. Shell & design-system findings

### 2.1 The three unconditional constants that gate everything

1. `<main className="ml-[260px] flex-1">` — no breakpoint (`dashboard/src/app/layout.tsx:64`). At 390px, 130px of content remains.
2. Sidebar `fixed left-0 top-0 z-40 flex h-screen w-[260px]` — no drawer, no collapse, no toggle (`dashboard/src/components/layout/Sidebar.tsx:86`).
3. ChatOverlay `SIDEBAR_OFFSET = 280` / `MIN_WIDTH = 380` (`dashboard/src/components/chat/ChatOverlay.tsx:21,24`) — a *divergent duplicate* of the sidebar width; `clampRect` pins the window's `minX` to 280 (`ChatOverlay.tsx:44`), so the chat window is mathematically unreachable on any phone viewport. Default rect `x: 920` (`dashboard/src/hooks/useChatWorkspace.ts:16`).

No `export const viewport` exists (`dashboard/src/app/layout.tsx:36-39` is metadata-only). App Router emits the default `width=device-width, initial-scale=1` meta on its own, so the page is *not* rendered at a desktop-fallback width — an explicit export matters for `themeColor` and `viewportFit: "cover"` (safe-area insets), not for device-width. `overflow-x: hidden` on body masks the horizontal overflow the fixed shell creates (`dashboard/src/app/globals.css:55`).

### 2.2 Design system

- Tailwind 4 CSS-first theme (`dashboard/src/app/globals.css:8-39`): color + font tokens only. **No spacing, radius, breakpoint, or z-index tokens**; z-values are ad hoc up to `z-9999` (`globals.css:90,102`).
- **Zero `@media` queries in 409 lines** of `globals.css` (§9 cmd 1). No `prefers-reduced-motion` gate on seven `infinite` animation utilities (`globals.css:204-224,399-407`).
- **No UI primitive layer.** `dashboard/src/components/ui/` holds exactly two files (`ErrorBanner.tsx`, `KeyboardNav.tsx`) — no Button/Card/Dialog/Sheet/Table. Every control is a bespoke `<button>`; the only shared helper is `cn()` (`dashboard/src/lib/utils.ts:4-6`). Touch-target remediation without a primitive layer is ~200 individual edits.
- The default card surface is `backdrop-filter: blur(12px)` (`globals.css:298`) — the most expensive mobile GPU primitive here — plus three stacked full-viewport overlays (noise `globals.css:86-95`, scanlines `globals.css:101-115`, and a duplicate `ScanLines` component painting the identical gradient, `dashboard/src/components/layout/ScanLines.tsx:11-21`) and 20 permanently-animating fixed particles (`dashboard/src/components/layout/AmbientParticles.tsx:10`).
- Dominant type size is 10px: `text-[10px]` ×399, `text-[9px]` ×61 (§9 cmd 2). Inputs under 16px trigger iOS auto-zoom; the chat composer is 14px (`dashboard/src/components/chat/ChatInterface.tsx:264`). Zero uses of `inputMode`/`enterKeyHint`/`safe-area-inset`/`touch-action`/`dvh` repo-wide (§9 cmd 3).
- `OperatorMicrographics` (443 lines, purely synthetic `Math.sin` data, mouse-only interaction — `onMouseMove` at `:204,341`, 48 `onMouseEnter` cells at `:298-299`, self-tick every 1.4s at `:74-77`) is force-mounted on **every** dashboard route (`dashboard/src/app/dashboard/layout.tsx:30`). On touch it is dead weight and dead interaction.
- 96% client-rendered: 80/83 `.tsx` files carry `"use client"`, 32/34 pages; **zero** dynamic imports (`next/dynamic`/`React.lazy` grep = 0, §9 cmd 4). Largest client pages: `qwen35/page.tsx` 2394 lines, `glm5/page.tsx` 1956 lines.

### 2.3 No safety net

`dashboard/playwright.config.ts:6` points `testDir` at `./playwright`, **which does not exist** — the three `test:visual*` scripts (`dashboard/package.json:11-13`) execute zero specs. The config declares a single 1680×1050 desktop viewport (`playwright.config.ts:12`), no device projects. There is no visual baseline of any kind to protect a renovation.

### 2.4 Integrity defects to fix in passing (cheap, otherwise carried into the new shell)

- `/dashboard/opportunities` appears **twice** in nav (`dashboard/src/lib/controlPlaneRouteDeck.js:35-41` and `dashboard/src/lib/dashboardNav.ts:67`) and has **no page on disk** (34 `page.tsx` routes exist; `opportunities` is not among them). `/dashboard/timeline` exists but is in no nav section.
- Dead dependencies, imported nowhere in `src/`: `cmdk`, `elkjs`, `react-resizable-panels` (`dashboard/package.json:24,26,32`; §9 cmd 5).
- The global Cmd+K handler dispatches `"dharma:cmd-k"` to zero listeners (`dashboard/src/components/layout/Header.tsx:29-44`) — a dead affordance occupying header space.
- Five operator-coherence components have no importer (`CoherenceKanban`, `CoherenceSections`, `ExecutiveBoard`, `ReadinessScorePanel`, `CoherenceCardView` — grep each across `src/`, only self-definition).
- `zod` is declared (`dashboard/package.json:35`) and imported zero times; `api-generated.ts` is an intentionally-empty codegen stub (`dashboard/src/lib/api-generated.ts:41-45`).

---

## 3. Route portfolio — mobile value × renovation cost

Scored across all 34 on-disk routes (+1 API route). Value = does a phone-first operator need it; cost = S/M/L/XL. Full blockers carry citations in the two route-audit lanes that produced this table; the highest-leverage citations are inlined.

### 3.1 P0 — the mobile operator core (mobile-first excellence)

| Route | Value | Cost | Main blocker |
|---|---|---|---|
| `/dashboard` (home) | HIGH | M | `ActivityTable` is a real 4-col table (`dashboard/src/components/dashboard/ActivityTable.tsx:63-64`); page grids already responsive (`dashboard/src/app/dashboard/page.tsx:73,144`) |
| `/dashboard/cockpit` | HIGH | M | 6 panels × 7 modes stack to one column below `xl` (`dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx:80`); NOTE: files owned by titanium track, coordinate (§8) |
| `/dashboard/command-post` | HIGH | L | Stacked mode interleaves a 260px relay rail between the two chat lanes (`dashboard/src/components/chat/CommandPostWorkspace.tsx:636`); iOS has no `requestFullscreen` (`:566`) |
| `/dashboard/agents` | HIGH | M | 6-col table (`dashboard/src/app/dashboard/agents/page.tsx:75-87`); `w-[420px]` drawer and `w-[400px]` dialog overflow 390px (`:195,309`) |
| `/dashboard/agents/[id]/chat` | HIGH | **S** | One hardcoded `calc(100vh - 380px)` (`dashboard/src/app/dashboard/agents/[id]/chat/page.tsx:53`). **Best value-per-effort fix in the app.** |
| `/dashboard/runtime` | HIGH | M | Approve/reject/resume interrupts are 32px icon-only, tooltip-labelled buttons (`dashboard/src/app/dashboard/runtime/page.tsx:643-656`), below 12 stacked MiniStats (`:496-516`) — the single most operator-critical mobile action in the app |
| `/dashboard/tasks` | HIGH | M | `w-[440px]` create dialog wider than the viewport (`dashboard/src/app/dashboard/tasks/page.tsx:206`); 5-col table (`:74-100`) |
| `/dashboard/gates` | HIGH | **S** | Only a non-wrapping badge row (`dashboard/src/app/dashboard/gates/page.tsx:102`); already card-based |
| Needs-John queue (extracted from `/dashboard/control-surface`) | HIGH | M | The queue itself is already a touch-friendly swipe strip (`dashboard/src/components/cockpit/NeedsJohnQueue.tsx:89,103`); extract it as the mobile alerts surface rather than porting the page around it |

### 3.2 P1 — responsive best-effort (cheap correctness passes)

`/dashboard/telemetry` (S — best-behaved route), `/dashboard/models` (S), `/dashboard/eval` (S — but `grid-cols-4` unbreakpointed at `dashboard/src/app/dashboard/eval/page.tsx:109` is the worst single grid in the audit), `/dashboard/audit` (S), `/dashboard/log` (M — `grid-cols-4` at `log/page.tsx:154`), `/dashboard/timeline` (M — sub-44px transport buttons, `dashboard/src/components/timeline/TimelineControls.tsx:74-97`), `/dashboard/observatory` (L — 7-col leaderboard + fixed-width timeline rows, but HIGH glance value), `/dashboard/modules` (M), agent subtabs `config`/`tasks`/`memory`/`connections` (all S), `/dashboard/glm5` + `/dashboard/qwen35` chat lanes (XL as monoliths — treat via the shared chat-shell fix in Phase 3, not full renovation; note `qwen35/page.tsx:840` hides operator QuickLinks below `lg`, exactly backwards for a phone).

### 3.3 Desktop-only (defer; do not port in v1)

Graph-canvas and dense-matrix routes where `@xyflow/react` pan/zoom fights touch scroll and layouts are hardcoded in pixels:

- `/dashboard/ecosystem` (nodes on a hardcoded 6×220px grid, `dashboard/src/app/dashboard/ecosystem/page.tsx:196-199`), `/dashboard/ontology` (`w-[400px]` drawer, `ontology/page.tsx:225`), `/dashboard/lineage` (5×200px layout, `lineage/page.tsx:84`), `/dashboard/claude` (620px canvas, `claude/page.tsx:271`), `/dashboard/synthesizer` (dead selection state, `synthesizer/page.tsx:131-133`), `/dashboard/stigmergy` (min-400px JS-computed SVG, `stigmergy/page.tsx:209-218`), `/dashboard/evolution` DAG panel.
- `/dashboard/control-surface` matrix: a viewport-height 5-zone shell (`control-surface/page.tsx:64,81-96`) around a 1180px-wide 10-column TanStack table (`dashboard/src/components/cockpit/SystemTruthMatrix.tsx:136-236`). Extract the queue (§3.1), leave the matrix desktop-only.

The prior SSOT fidelity map corroborates this cut: the LIVE-fidelity routes (`docs/plans/2026-05-22-dashboard-ssot-architecture.md:44-51`) and the P0 set above overlap almost exactly; the STUB routes (`workflows`, `blocks` — placeholder pages with zero data sources and infinite decorative animations, `workflows/page.tsx:25-37`, `blocks/page.tsx:23-40`) should be **hidden from mobile nav**, not renovated.

---

## 4. Data / realtime / auth layer

### 4.1 What is right already

- Browser API calls default to **same-origin relative** (`dashboard/src/lib/api.ts:40-45`), proxied by exactly two rewrites (`dashboard/src/lib/dashboardProxy.ts:10-19`, pinned by `dashboardProxy.test.ts`) with a server-side-tunable target (`dashboard/next.config.ts:6-7`). This is the mobile-correct architecture.
- WS base URL is protocol-relative on the default path (`api.ts:410-413`) — no mixed-content bug.
- The backend ingress gate is genuinely fail-closed once `DASHBOARD_API_KEY` is set (`api/main.py:484-486`; WS at `api/ws.py:154-169`), with a solid test matrix (`tests/test_api_auth.py`).

### 4.2 Blockers (in dependency order)

1. **Loopback-locked WS session minting.** `LOOPBACK_HOSTNAMES = {"127.0.0.1","::1","localhost"}` is a hardcoded `const` (`dashboard/src/lib/wsSession.ts:12`) consumed by the 403 gate (`dashboard/src/app/dharma-internal/ws-auth/route.ts:13-23`). No env escape exists. Off loopback, `ws.ts` burns 10 retries and gives up silently (`dashboard/src/lib/ws.ts:137-142,188-190`).
2. **HTTP/WS auth contradiction.** The proxy attaches no bearer (no `middleware.ts`; zero `Authorization` hits in `dashboard/src`), so key-set mode = WS green, REST 401. Key-unset mode = everything 401 unless `DHARMA_API_ALLOW_LOCAL_NOAUTH=1` — an env var set by no launcher and documented nowhere (only `api/main.py:393,422` + tests). The documented dev flow (`run_operator.sh` + `scripts/run_dashboard_ui.sh`) therefore 401s all data; CI stays green via the in-process `"testclient"` sentinel (`api/main.py:419-420`) no real deployment presents.
3. **The offline banner cannot detect the real failure mode.** It polls `/api/verify/health` (`dashboard/src/components/ui/ErrorBanner.tsx:92-96`), which is public (`api/main.py:339`), so it reports healthy while every authenticated panel 401s empty.

### 4.3 Mobile-network behavior

- Global query defaults `staleTime: 10_000, refetchInterval: 30_000, retry: 2, refetchOnWindowFocus: true` (`dashboard/src/app/providers.tsx:17-20`). Focus refetch fires only the queries *mounted on the active route* — routes are mutually exclusive, so the burst size is per-route, not the repo-wide ~40-hook count. It is still material on the operator core: `useRuntimeControlPlane` fans out 6 requests per invocation (`dashboard/src/hooks/useRuntimeControlPlane.ts:20-42`) and is mounted by runtime/command-post/observatory/qwen35; `useTelemetry` mounts 9 keys (`dashboard/src/hooks/useTelemetry.ts:19-69`); the home route mounts five 5s pollers (`useOverview.ts:11`, `useHealth.ts:11`, `useAgents.ts:11`, `useTraces.ts:11`, plus `FitnessTrend`). `retry: 2` multiplies each failed burst on a flaky link. Phase 4 sizing should measure the mounted set per P0 route, not the global count.
- **No** `visibilitychange`, `online`/`offline`, `refetchOnReconnect`, or `networkMode` handling anywhere in `dashboard/src` (§9 cmd 6).
- No client heartbeat; the chat WS channel has no server keepalive either (`api/routers/chat.py:1381-1382` blocks on receive) — half-open sockets after cellular NAT timeout are detected only on failed send (`api/ws.py:228-235`).
- WS messages and API responses are unvalidated casts (`ws.ts:159-167`; `api.ts:91-114`); captive-portal HTML interception on mobile makes this a real crash source, and `zod` is already installed.
- Chat streams (SSE-over-POST, `dashboard/src/hooks/useChat.ts:303-308,398-420`) have no resume token. Partial streamed text *survives* a disconnect (`trimTrailingEmptyAssistant` removes a trailing assistant turn only when content AND tool events are both empty, `useChat.ts:69-78`) — what's lost is the remainder of the answer, silently: no interrupted marker, no retry affordance.

---

## 5. PWA gap inventory

All absent (verified by grep/find across `dashboard/`, §9 cmd 3):

| Requirement | Status |
|---|---|
| `app/manifest.ts` / `manifest.webmanifest` | absent |
| `export const viewport` (`width=device-width`) | absent |
| `themeColor`, `appleWebApp` metadata | absent |
| `apple-touch-icon`, `icon-192/512`, maskable icons | absent (`public/` = 5 scaffold SVGs) |
| Service worker / registration / offline route | absent (no PWA package in `package.json:17-50`) |
| Query persistence for offline last-known state | absent (in-memory QueryClient only, `providers.tsx:12-24`) |
| `touch-action` / `overscroll-behavior` / `env(safe-area-inset-*)` / `dvh` | absent |
| Mobile viewport in Playwright | absent (`playwright.config.ts:12`) |

---

## 6. Access architecture — recommendation

| | (a) Loopback/LAN only | (b) Private tailnet tunnel — **RECOMMENDED** | (c) Public deployment |
|---|---|---|---|
| Reaches the walking operator | No (LAN evaporates when you leave the house) | Yes | Yes |
| Code changes needed | Phase 1-4 only | Phase 1-5 (auth seam) | All of (b) + rate limiting, identity, revocation, webhook hardening — **out of scope** |
| Security posture | Safe by locality | Network-layer identity (tailnet ACL) + app-layer bearer | Unsafe as-is: no rate limiting anywhere in `api/` (§9 cmd 7), one shared bearer with no identity/revocation (`api/main.py:426-434`), empty-Origin WS bypass (`api/ws.py:89`), public `/docs`+`/openapi.json` in every mode (`api/main.py:340-342`), signature-optional webhook outside production (`api/main.py:343`; `tests/test_verify_api.py:268-292`) — guarding endpoints that spawn agents and execute tools |

**Recommendation: (b), single-operator, tailnet-only.** The backend is by design "a single-user loopback boundary, not remote user authentication" (`dashboard/README.md:63-67`), and that README explicitly forbids tunneling the Next server as an authenticated *multi-user* control plane. A single-operator tailnet deployment keeps that contract: transport identity = tailnet ACL (only the operator's devices), application auth = the existing `DASHBOARD_API_KEY` bearer presented end-to-end. Phase 5 specifies the minimal seam; it requires operator ratification because it amends the README's trust doctrine for the tailnet case. Public deployment is explicitly rejected until a real identity layer exists (not this track).

---

## 7. Phased renovation plan

Every phase below that touches `dashboard/` or `api/` is hot-path (`scripts/runtime/pr_merge_control.py:90-91`): packet preflight + closeout required, PR grades HIGH (`pr_merge_control.py:557-558`). Phases are sized to ship independently, each behind its own visual baseline.

### Phase 0 — Safety net + viewport truth (prerequisite for everything)

1. Create `dashboard/playwright/` with smoke + screenshot specs for the P0 routes; add device projects (390×844 mobile, 1680×1050 desktop) to `playwright.config.ts`; wire `test:visual` into CI so regressions are visible before renovation begins. **The suite must run against deterministic data**: the current `webServer` starts only Next (`dashboard/playwright.config.ts:16-20`) while rewrites target a separately-run FastAPI on 8420 — and the documented launcher 401s without the undocumented no-auth opt-in (§4.2) — so naive screenshots would baseline empty/401 states. Either start a fixture-seeded FastAPI (with `DASHBOARD_API_KEY` wired) as a second `webServer`, or serve recorded fixtures via Playwright route interception; pick one and pin it in the spec files themselves.
2. Add `export const viewport` to `dashboard/src/app/layout.tsx` for `themeColor` and `viewportFit: "cover"` (safe-area insets). Note: App Router already emits the default `width=device-width, initial-scale=1` meta, so this is PWA polish, not the defect-visibility gate — the 390px defects are visible today in any device emulator.
3. Integrity sweep: remove the duplicate + dead `/dashboard/opportunities` nav entries, add `/dashboard/timeline` to nav or record why not (manifest agreement rule, `ACTIVE_SURFACE_MANIFEST.yaml:3-4`); drop dead deps `elkjs`, `react-resizable-panels`; either wire `cmdk` to the dead `dharma:cmd-k` event or remove both; delete the 5 orphaned operator-coherence components; dedupe the `ScanLines` component vs `body::after`.

**Acceptance:** `npm --prefix dashboard run test:visual` executes >0 specs on both viewports; no nav entry without a page; `npm --prefix dashboard run lint` clean.

### Phase 1 — Responsive shell

1. Breakpoint-gate the shell: sidebar `hidden md:flex`, main `md:ml-[260px]`; below `md`, a bottom nav with ≤5 slots, plus a full-nav drawer using the one already-mobile-safe drawer pattern in the repo (`w-[480px] max-w-[calc(100vw-24px)]`, `dashboard/src/components/operator-coherence/v2/CockpitV2Primitives.tsx:231`). The five slots do NOT all exist as routes today — `dashboardNav.ts` has no Chat or Approvals entry — so extend it with a typed mobile-nav structure mixing route links (Cockpit `/dashboard/cockpit`, Agents `/dashboard/agents`, Approvals → `/dashboard/runtime` until the Phase 3 alerts surface lands, then retargeted) and action entries (Chat opens the chat sheet — it is an overlay, not an href). No invented routes, no duplicated nav state.
2. ChatOverlay mobile mode: below `md`, the FAB (already 64px, `ChatOverlay.tsx:281`) opens a full-screen sheet instead of a draggable window; derive the desktop offset from one shared sidebar-width constant, deleting the divergent `SIDEBAR_OFFSET = 280`.
3. Introduce the primitive layer in `dashboard/src/components/ui/`: `Button` (≥44px touch), `Sheet` (bottom sheet), `Card`, `ResponsiveTable` (table→card-list under `md`), `Input` (16px font floor, `enterKeyHint`). New primitives only where the P0 routes need them — no big-bang migration.
4. Performance gates: mount `AmbientParticles`/`ScanLines`/`OperatorMicrographics` only on `md+` **and** `prefers-reduced-motion: no-preference`; add a `@media (prefers-reduced-motion)` kill-switch for the seven infinite animations; replace `glass-panel` backdrop-blur with an opaque fallback below `md`.
5. Replace `h-screen`/`100vh` in shell components with `dvh`/flex; add `env(safe-area-inset-*)` padding to the bottom nav and chat composer.

**Acceptance:** zero horizontal scroll at 390px on shell + P0 routes (Playwright assertion); all shell tap targets ≥44px; bottom nav reachable on every route.

### Phase 2 — PWA layer

1. `app/manifest.ts` (name, `start_url: /dashboard`, `display: standalone`, icons 192/512 + maskable, dark `background_color`/`theme_color` matching `--color-sumi-950`), `apple-touch-icon`, `appleWebApp` metadata.
2. Service worker (Serwist or hand-rolled): precache the app shell, network-first for `/api/*`, an `/offline` fallback route.
3. TanStack Query persister (localStorage/IDB) so cockpit/overview render **last-known data explicitly labeled STALE with its timestamp** when offline — projection honesty per the claim-language rules (`docs/governance/SWARM_GENOME.md` § projection surfaces): never render cached data as live.
4. Fix the liveness banner: listen to real `online`/`offline` events AND distinguish "backend unreachable" from "backend 401" (an authenticated probe), replacing the public-endpoint-only poll (`ErrorBanner.tsx:92-96`).

**Acceptance:** concrete installability assertions (current Lighthouse has no PWA category, so "Lighthouse PWA pass" is not executable): Playwright asserts the manifest is served and parses with required fields + icons, a service worker is registered and controlling the page, `display: standalone` metadata is present, and offline navigation lands on the fallback route; airplane-mode shows last-known cockpit labeled stale, not a spinner or a lie.

### Phase 3 — Operator core routes, mobile-first

In value-per-effort order:

1. **Agent chat** (`agents/[id]/chat`): replace `calc(100vh - 380px)` with a `dvh` flex shell; add `enterKeyHint="send"`; keyboard-safe composer. (S)
2. **Gates**: wrap the header badge row. (S)
3. **Runtime**: promote the interrupt queue above the 12 MiniStats; approve/reject/resume become ≥44px labeled buttons; confirm-on-destructive. (M)
4. **Tasks**: `ResponsiveTable` + create dialog → bottom `Sheet`. (M)
5. **Agents list**: `ResponsiveTable` (reuse `AgentCard`); drawer/dialog → `Sheet` with `max-w` cap. (M)
6. **Home**: `ActivityTable` → card list; `FitnessTrend` compact sparkline mode. (M)
7. **Alerts surface**: extract `NeedsJohnQueue` (+ `EvidenceDrawer` as a bottom sheet) into the mobile approvals view; control-surface matrix stays desktop. (M)
8. **Cockpit**: mobile OverviewMode — readiness score, next-3 actions, incidents, spine pulse; **coordinate with `repository-titanium-hardening-2026-07`, which owns the four Cockpit V2 files** (`docs/governance/ACTIVE_TRACK.yaml:1811-1814`) — this item lands via that track's next-items or an acknowledged WARN overlap (`ACTIVE_TRACK.yaml:86`). (M)
9. **Command-post**: lane tabs (swipe between Claude lane / relay / Codex lane) replacing the stacked 260px relay sandwich; remove the iOS-unsupported fullscreen call. (L)
10. **Chat monoliths** (`glm5`, `qwen35`): apply the shared chat-shell + sidebar-as-sheet fix only; full decomposition is out of scope (also mind the 1000-line module budget for *new* files, `docs/governance/ANTI_SLOP_RULES.md` Rule 10).

**Acceptance:** per-route 390px visual baselines green; all action controls ≥44px; P1 routes get the cheap fixes (`eval` `grid-cols-4`, `log` `grid-cols-4`, timeline transport buttons) in the same pass.

### Phase 4 — Realtime + network resilience

1. `ws.ts`: `visibilitychange` + `online` listeners; reset retry budget and reconnect on resume; remove the permanent give-up (`ws.ts:188-190`) in favor of pause-while-hidden + resume-on-visible; expose connection state. Liveness detection must be channel-appropriate: browsers cannot send protocol-level ping frames, and both server receive loops discard inbound text without replying (`api/routers/agents.py:641-648`, `api/routers/chat.py:1381-1382`) — so a client-only "heartbeat + timeout" would flag healthy chat sockets dead. For `/ws/agents`, derive liveness from the existing 5s `agents_update` cadence; for the chat channel, add an application-level ping→pong echo server-side (an `api/` change: hot-path, packet-bound, coordinate ingress tests).
2. Query tuning — behavioral changes only, no restating v5 defaults (`refetchOnReconnect: true` and `networkMode: "online"` are already the defaults): tiered `staleTime` for focus-refetch damping, verify `refetchIntervalInBackground` stays off, and audit the 5s polls down to what the phone actually needs (WS `agents_update` already exists as a push channel, `api/routers/agents.py:614-630`). The acceptance test below proves the reconnect transition instead of trusting settings.
3. zod validation at every response boundary, not just two: `ws.ts` message parse, `api.ts` envelope unwrap, AND the direct stream parsers that bypass both (`useChat.ts`, `useAgentChat.ts`, and the glm5/qwen35 page-local `fetch(apiPath(...))` parsers) — either enumerate schemas at each parser or route them through one validated transport. The dependency is already declared.
4. Chat stream: partial text already survives disconnects (`trimTrailingEmptyAssistant` trims only fully-empty turns, `useChat.ts:69-78`); the missing behavior is marking the retained partial turn as interrupted and offering a visible "stream interrupted — retry" affordance.

**Acceptance:** scripted Playwright test — background the page, sever network, restore, foreground → socket reconnects and queries settle without a manual reload.

### Phase 5 — Remote access seam (requires operator ratification; touches `api/` + `dashboard/`)

1. Make WS-session trust configurable: `DASHBOARD_TRUSTED_ORIGINS` env consumed by `wsSession.ts` (default stays loopback-only — fail-closed, current behavior unchanged).
2. Same-origin bearer seam: a Next route-handler proxy (or middleware) attaches `Authorization: Bearer $DASHBOARD_API_KEY` server-side to proxied `/api/*` requests, so the key never reaches the phone and both transports authenticate. This amends `dashboard/README.md:63-67` doctrine for the single-operator tailnet case — README update ships in the same PR.
3. Deployment recipe (docs): `DASHBOARD_HOST`/`OPERATOR_HOST` binding, `DASHBOARD_WS_ORIGINS` (all-`http://`-loopback defaults today, `api/ws.py:27-34`), CORS defaults missing the actual dashboard port 3420 (`api/main.py:535` vs `scripts/run_dashboard_ui.sh:19`), cookie `Secure` under TLS-terminating proxies (`ws-auth/route.ts:30` reads `nextUrl.protocol`), and the documented-dev-flow 401 (`DHARMA_API_ALLOW_LOCAL_NOAUTH`, §4.2.2) fixed or documented.
4. Explicit non-goal: public deployment (§6 column c).

**Acceptance:** phone on the tailnet gets live cockpit + chat with `DASHBOARD_API_KEY` set; loopback behavior byte-identical when the new env vars are unset; `tests/test_api_auth.py` matrix extended, not weakened.

### Phase ordering rationale

0→1→2 are strictly sequential (can't see mobile defects without a viewport; can't baseline without specs; can't install without a shell worth installing). 3 and 4 can interleave per-route. 5 is independent of 2-4 and gated on operator ratification; until it lands, the PWA is fully exercisable on loopback (desktop browser mobile emulation + phone via `localhost` port-forward over `tailscale ssh`/`adb reverse`).

---

## 8. Governance — draft track proposal

The portfolio is at the hard ceiling: `max_active: 10` (`docs/governance/ACTIVE_TRACK.yaml:80`), 10 ACTIVE tracks (generated digest, `CLAUDE.md`), and an 11th is a CI ERROR (`scripts/governance/check_track_status.py:1651-1654`). Spine coverage is already complete, so admission rides the ROI tiebreaker (`docs/vision_maps/NORTH_STAR.md:84-87`). Doctrine-conformant paths, strongest precedent first:

1. **One-for-one admission** when a current track closes (precedent: TAM→Titanium 2026-07-17, `ACTIVE_TRACK.yaml:80-81,1828-1830`).
2. **Park in `docs/governance/proposed_tracks/`** as a draft (explicitly non-load-bearing, `docs/governance/proposed_tracks/README.md:19-22`; 30-day staleness rule applies).
3. **Fold Phase 0 only** into `repository-titanium-hardening-2026-07` (which already carries the dashboard toolchain lane as WP-0H, `ACTIVE_TRACK.yaml:1916-1919`) — a poor fit for Phases 1-5 given that track's non-goals.

Draft block (proposal-grade criterion kinds per `docs/governance/proposed_tracks/README.md:23-25`; deliberately excludes the four Titanium-owned Cockpit V2 files):

```yaml
  - id: mobile-operator-pwa-2026-07
    name: Mobile Operator Companion — PWA renovation of the web operator surface
    status: ACTIVE   # on admission only; see admission paths above
    opened_at: "TBD-on-admission"
    verified_at: "TBD-on-admission"
    ttl_days: 21
    owner: "@AmitabhainArunachala"
    serves: substrate-nativeness
    complements: [helm-worldclass-terminal-2026-06, repository-titanium-hardening-2026-07]
    owned_surfaces:
      # Full closure over what Phases 0-4 actually edit (review finding: the
      # first draft omitted surfaces its own phases touch).
      - dashboard/package.json
      - dashboard/next.config.ts
      - dashboard/src/app/layout.tsx
      - dashboard/src/app/providers.tsx
      - dashboard/src/app/manifest.ts
      - dashboard/src/app/globals.css
      - dashboard/src/app/dharma-internal/**
      - dashboard/src/app/dashboard/**        # Phase 3 route work; no overlap with titanium's four files (all under components/ and lib/)
      - dashboard/src/components/layout/**
      - dashboard/src/components/ui/**
      - dashboard/src/components/chat/**
      - dashboard/src/hooks/**
      - dashboard/src/lib/api.ts
      - dashboard/src/lib/ws.ts
      - dashboard/src/lib/wsSession.ts
      - dashboard/src/lib/dashboardNav.ts
      - dashboard/playwright.config.ts
      - dashboard/playwright/**
      - dashboard/public/**
      - .github/workflows/dashboard-visual.yml   # new Phase 0 CI lane
      - docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md
      # Phase-5-gated (operator ratification; claimed only when Phase 5 opens):
      - api/ws.py
      - tests/test_api_auth.py
      - dashboard/README.md
      # NOT claimed: api/main.py (titanium-owned — the CORS-default fix in
      # Phase 5 item 3 lands via that track's next-items per the WARN-overlap
      # coordination policy, ACTIVE_TRACK.yaml:86); the four titanium-owned
      # Cockpit V2 files (Phase 3 item 8 coordinates likewise).
    moves_vital_signs:
      - tool_coverage
      - security_guardrails
    target_closure_kind: CLOSED_NOT_PROD
    claim_boundary: >-
      Criteria prove a mobile-installable, offline-tolerant renovation of the
      existing dashboard verified by device-viewport visual baselines. They do
      NOT prove public-deployment safety, multi-user auth, or any authority
      over Cockpit V2 read-model files (titanium-owned) or terminal/** (helm).
    description: |
      Convert the existing Next.js web operator surface into a phone-first PWA
      operator companion (audit + spec: docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md).
      Serves the standing phone-first operator context (ACTIVE_TRACK.yaml:2023).
      Not a third website (dashboard/README.md:15): same app, same routes.
    prerequisites:
      # Existence-grade gates deliberately live HERE, not in completion_criteria —
      # file-existence is never closure (docs/governance/evidence_grades.yaml:8-10).
      - id: viewport_export_exists
        kind: file_contains
        file: dashboard/src/app/layout.tsx
        pattern: "export const viewport"
      - id: manifest_exists
        kind: file_exists
        file: dashboard/src/app/manifest.ts
    completion_criteria:
      # Outcome-bound, in live-track grammar (command_passes, as helm uses at
      # ACTIVE_TRACK.yaml:1332). If this block is parked as a formal file in
      # docs/governance/proposed_tracks/, its README (:23-25) requires downgrading
      # command_passes to file_exists/file_contains/pr_merged shapes until
      # admission — and any pr_merged criterion MUST carry a numeric pr: the
      # checker calls int(crit["pr"]) (scripts/governance/check_track_status.py:1087),
      # so a placeholder string crashes the track-status gate.
      # Oracle note: these suites are claimant-run; evidence_grades downgrades
      # oracle-dependent passes to S2 (evidence_grades.yaml:34-38) — same posture
      # as helm's bun-test gate.
      - id: mobile_shell_and_p0_baselines_green
        # Phases 0/1/3: shell + P0 routes render at 390px with no horizontal
        # scroll, >=44px action targets, visual baselines green on the mobile
        # Playwright project (spec sections 7.0, 7.1, 7.3 acceptance).
        kind: command_passes
        command: ["bash", "-c", "cd dashboard && npx playwright test --project=mobile --reporter=line"]
        timeout_s: 1200
      - id: pwa_install_offline_green
        # Phase 2: installability (manifest + SW + icons) and airplane-mode
        # last-known-state labeled STALE (spec section 7.2 acceptance).
        kind: command_passes
        command: ["bash", "-c", "cd dashboard && npx playwright test playwright/pwa-install.spec.ts --project=mobile --reporter=line"]
        timeout_s: 600
      - id: ws_resilience_green
        # Phase 4: background -> sever network -> restore -> foreground
        # reconnects without manual reload (spec section 7.4 acceptance).
        kind: command_passes
        command: ["bash", "-c", "cd dashboard && npx playwright test playwright/ws-resilience.spec.ts --project=mobile --reporter=line"]
        timeout_s: 600
      - id: phase5_ratified_or_descoped
        # Phase 5 is operator-gated: this file is written by the ratify-or-descope
        # decision itself (replaces a non-numeric pr_merged placeholder that would
        # have crashed the checker — see int() note above).
        kind: file_exists
        file: docs/plans/decisions/MOBILE_PWA_PHASE5_DECISION.md
    next_items:
      - { id: 1, what: "Phase 0: playwright device projects + viewport export + nav integrity sweep", kind: test, blocker: true }
      - { id: 2, what: "Phase 1: responsive shell (sidebar drawer + bottom nav + ui primitives + effect gating)", kind: code, blocker: true }
      - { id: 3, what: "Phase 2: manifest + service worker + offline last-known-state labeled STALE", kind: code, blocker: false }
      - { id: 4, what: "Phase 3: P0 routes mobile-first (chat dvh shell, runtime interrupt touch targets, tables to cards, Needs-John extraction)", kind: code, blocker: false }
      - { id: 5, what: "Phase 4: ws resilience (visibility/online handlers, no permanent give-up, zod boundaries)", kind: code, blocker: false }
      - { id: 6, what: "Phase 5: OPERATOR-GATED remote access seam (configurable ws-auth trust + server-side bearer proxy + README doctrine amendment)", kind: code, blocker: false }
    non_goals:
      - No third website, native wrapper, or second frontend app (dashboard/README.md:15).
      - No public deployment; remote access is single-operator tailnet only (spec section 6).
      - No edits to titanium-owned Cockpit V2 files except through that track's next-items.
      - No terminal/** work (helm-owned); TUI remains the primary operator cockpit.
      - No new API routers; auth seam reuses the existing bearer + env configuration.
      - Cockpit views remain read-only projections (ACTIVE_SURFACE_MANIFEST.yaml:209-210).
      - Graph-canvas routes (ecosystem/ontology/lineage/claude/synthesizer/stigmergy heatmap) are not ported to mobile in v1.
```

---

## 9. Verification commands (re-derive the aggregate claims)

```bash
# 1. zero @media queries in globals.css
grep -c "@media" dashboard/src/app/globals.css                      # expect 0

# 2. micro-type density
grep -rno "text-\[10px\]" dashboard/src --include=*.tsx | wc -l     # ~399 at audit time

# 3. PWA surface absent
find dashboard -name "manifest*" -o -name "sw.js" -o -name "apple-*" | grep -v node_modules
grep -rn "export const viewport\|serviceWorker\|safe-area\|touch-action\|dvh" dashboard/src

# 4. zero code splitting; use-client density
grep -rn "next/dynamic\|React.lazy" dashboard/src | wc -l           # expect 0
grep -rln '"use client"' dashboard/src --include=*.tsx | wc -l      # 80 of 83 at audit time

# 5. dead dependencies
grep -rn "cmdk\|elkjs\|react-resizable-panels" dashboard/src        # expect no hits

# 6. no visibility/online handling
grep -rn 'addEventListener("visibilitychange"\|addEventListener("online"' dashboard/src  # expect no hits

# 7. no rate limiting in api/
grep -rniE "ratelimit|rate_limit|slowapi|limiter|throttle" api/     # expect no hits

# 8. hot-path check for this doc's PR (docs-only => not hot)
python3 - <<'EOF'
from scripts.runtime.pr_merge_control import HOT_PATH_PATTERNS
p = "docs/plans/MOBILE_OPERATOR_PWA_AUDIT_SPEC_2026-07-25.md"
print(any(p == pat or p.startswith(pat) for pat in HOT_PATH_PATTERNS))
EOF

# 9. portfolio state
python3 scripts/governance/check_track_status.py
```
