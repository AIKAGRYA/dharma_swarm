# Command Plane — Living Checklist

**Status:** Queued. Update each item as work lands.
**Spec:** `docs/plans/2026-05-21-command-plane-design-lock.md`
**Vision:** `docs/plans/COMMAND_PLANE_VISION.md`
**Multi-agent protocol:** `docs/plans/COMMAND_PLANE_MULTIAGENT_PROTOCOL.md`
**Track in ACTIVE_TRACK.yaml:** `command-plane-redesign-2026-05` (queued)

---

## How to update this file

- When you ship a checkbox item, mark `[x]` AND add a commit hash in the trailing parentheses: `[x] Foo done (a1b2c3d4)`.
- When you discover a missing item, add it under the most relevant section. Don't reorder existing items.
- When a section is fully shipped, leave it — history of what shipped matters.
- An agent or human picking this up cold should be able to skim this file and know exactly what's next.

---

## Phase 0 — Pre-flight (mechanical)

- [x] Carry-forward commit of in-flight command-plane work (`d7ccfe40`)
- [x] Remove AmbientParticles + ScanLines + body::after scan-lines + orphan CSS (`f1bba2a4`)
- [ ] Fix `dharma_swarm.terminal_engine.events` ModuleNotFoundError (still failing per `python -c "import dharma_swarm.terminal_bridge"`). Locate where `ToolCallComplete`, `PermissionDecisionEvent`, etc. actually live or restore from git history.
- [ ] Refresh GitNexus index: `npx gitnexus analyze` (currently stale at `74f9d79`)
- [ ] Lockfile health: confirm `npm --prefix dashboard run build` stays green between sessions
- [ ] Triage remaining untracked work threads (`api/routers/pool.py`, `dharma_swarm/provider_fallback.py`, `docs/agents/`, `docs/ontology/`, `docs/ops/*`) — owners + status

## Phase 1 — Tokens and palette (Nihonga revaluation)

Reference: spec §VII Aesthetic + the explicit `theme.ts` audit from the design grill.

- [ ] Run `gitnexus_impact({target: "colors", direction: "upstream"})` and report blast radius BEFORE editing `dashboard/src/lib/theme.ts`
- [ ] Audit every consumer of `colors.aozora`, `.botan`, `.kinpaku`, `.rokusho`, `.bengara`, `.fuji`, `.torinoko`, `.kitsurubami` (grep + GitNexus context)
- [ ] Decision per token: **rename** (e.g., `aozora` → `gunjō` if semantic) or **revalue in place** (keep name, change hex). Record decisions inline.
- [ ] Replace hex values to match locked mineral-pigment palette:
  - [ ] Sumi 墨 substrate: `#0F0D0B → #1A1715` (warm-ink, not cool)
  - [ ] Gofun 胡粉 text base: `#F2EDE3` at 92% opacity
  - [ ] Tetsu-iro 鉄色 hairlines: `#2A2522`
  - [ ] Gunjō 群青 identity/actuation: `#1F4F8C` (replaces cyan `aozora`)
  - [ ] Rokushō 緑青 pulse/fresh: `#6C8E7A`
  - [ ] Murasaki 紫 recall/contemplation: `#5B3E72`
  - [ ] Ōdo 黄土 stale/aging: `#A57A35`
  - [ ] Bengara 弁柄 earthen depth: `#7A3E2A`
  - [ ] Shu 朱 fail/urgent: `#9C2A1F`
- [ ] Kill `glowText()` neon helper from `dashboard/src/lib/theme.ts`
- [ ] Audit `globals.css` for any neon / glow / scan / particle / drift CSS — remove or replace
- [ ] Add motion vocabulary tokens in new `dashboard/src/lib/motion.ts`:
  - [ ] `motion.instant` — 80-120ms `cubic-bezier(0.2, 0, 0, 1)`
  - [ ] `motion.navigate` — 200-240ms `cubic-bezier(0.4, 0, 0.2, 1)`
  - [ ] `motion.ambient` — 800-1200ms linear/sine
- [ ] Update status mapping in `theme.ts`: replace `aozora` (cyan) with `gunjō` (azurite); replace `botan` (pink) with `murasaki`
- [ ] Visual regression baseline: snapshot every dashboard route in 2D mode (Argos or Playwright); commit baselines
- [ ] Build + tests green

## Phase 2 — Cockpit v2 (2D-first)

- [ ] Rename `metadata.description` in `app/layout.tsx` from "Neo-Tokyo swarm visualization dashboard" to something instrument-grade and dharma_swarm-honest
- [ ] Replace Inter / Space Grotesk / JetBrains Mono with **Commit Mono** (free) primary + Inter Display (or Söhne if accessible) prose
- [ ] Custom shadcn registry scaffold at `dashboard/registry.json` + `dashboard/src/registry/r/*.json` with 6 primitives:
  - [ ] `Numeral` (tabular-figure numeric display, the protagonist)
  - [ ] `StatusBadge` (ALLCAPS-mono 4-state: PASS/FAIL/STALE/DRIFT)
  - [ ] `EvidenceRow` (hairline border, no shadow)
  - [ ] `ZoneFrame` (hexagonal positioning frame — never renders the hex outline)
  - [ ] `Glyph` (monochrome status glyph: ✓ ✗ ◐ ⊘)
  - [ ] `Pane` (resizable pane primitive wrapping react-resizable-panels)
- [ ] Deploy registry to a vercel preview subdomain so v0 / shadcn CLI can read it
- [ ] Refactor existing 4 cockpit components (`NeedsJohnQueue`, `SystemTruthMatrix`, `EvidenceDrawer`, `RuntimeRail`) to consume new tokens + primitives
- [ ] Add ambient pulse on most-recent value: single Rokushō dot, `motion.ambient`, NOT the number itself flashing
- [ ] Feature-flag the v2 cockpit behind `?v=2` query param in `/dashboard/control-surface/page.tsx`. Existing v1 keeps working at the same URL.
- [ ] Acceptance:
  - [ ] Linear-grade aesthetic per `palantir-ui-scout` + `craft-reviewer` reports (see multi-agent protocol)
  - [ ] All 4 components consume new tokens (no hex literals in component files)
  - [ ] Numbers are visually dominant on every screen
  - [ ] `npm --prefix dashboard run build` green
  - [ ] `make governance-all` green

## Phase 3 — Cockpit 3D (gated on benchmark)

Reference: spec §V 7 R3F architectural rules; `r3f-craft-specialist` report (Task #7).

- [ ] Add R3F + drei + Motion 3D dependencies (verify version compatibility with React 19.2 + Next 16)
- [ ] Storybook 9 with Vitest Browser Mode + the Storybook MCP enabled
- [ ] Implement `<View>`-per-zone primitive (one `<Canvas>`, N isolated viewports per drei's `<View>`)
- [ ] Center zone (COCKPIT) 3D variant: instanced-mesh telemetry field ≤200 nodes, 1 `drei.Text` title, 1 `drei.Html` data panel pinned bottom-right of `<View>`
- [ ] Tab key toggle 2D ⇄ 3D in `<ZoneSheet/>` ⇄ `<ZoneSpace/>` via Zustand mode store
- [ ] Auto-fallback to 2D when WebGL/GPU/battery/screen size or `prefers-reduced-motion` says so
- [ ] Storybook story for the 3D zone
- [ ] ADR-0004: camera placement decision for center zone (orbit defaults, focus+context navigation per Furnas DOI)
- [ ] **Benchmark gate** — proceed to zones 2-7 only if all pass:
  - [ ] 60fps locked on M2 Air 8GB with full data load
  - [ ] Tab→2D transition <100ms
  - [ ] All 7 R3F architectural rules satisfied (no raw Three.js, drei primitives only, declarative motion, typed props, no custom shaders)
  - [ ] Visual regression baseline locked
- [ ] If benchmark fails: kill always-3D for the cockpit. Reserve 3D only for MAP zone (graph topology where it earns).

## Phase 4 — Zones 2-7 (zone-per-PR)

Each zone gets its own PR. Pattern: copy the COCKPIT-v2 shape, swap the zone's data hook and verb-appropriate chrome.

- [ ] **TALK** (converse): unify `/glm5`, `/qwen35`, `/claude`, `/codex-composer`, `/command-post`, `/models` into `/dashboard/talk/[provider]` with shared transcript chrome
- [ ] **WATCH** (observe): consolidate `/observatory`, `/runtime`, `/telemetry` under `/dashboard/watch` with sub-tabs; cadence-aware refresh
- [ ] **JUDGE** (evaluate): consolidate `/eval`, `/audit`, `/gates` under `/dashboard/judge`; day-over-day cadence
- [ ] **MAP** (relate): consolidate `/ontology`, `/lineage`, `/ecosystem`, `/modules` under `/dashboard/map` as the natural 3D candidate (graph topology earns 3D)
- [ ] **SENSE** (track trails): consolidate `/stigmergy`, hot paths, `/evolution` under `/dashboard/sense`; minute-cadence
- [ ] **REMEMBER** (recall): consolidate `/log`, `/timeline` under `/dashboard/remember`; hour-cadence
- [ ] Fold `/synthesizer` into COCKPIT (duplicate, kill the parallel surface)

## Phase 5 — Migration cleanup

- [ ] Delete v1 routes that are now subsumed by zones
- [ ] Remove the feature flag once every consumer migrated
- [ ] Update `dashboard/src/lib/dashboardNav.ts` and `controlPlaneRouteDeck.js` to reflect zone-shaped IA
- [ ] ADR-0005: declare command-plane shape locked; future top-level routes require track + ADR
- [ ] Update CLAUDE.md (via track-closure render) to point at the new zone vocabulary
- [ ] `make onboard` should render the new IA cleanly

## Phase 6 — Multi-agent acceptance (lock the gate)

- [ ] Spawn a fresh `command-plane-stress-test` team and have it re-validate the shipped state against the locked spec (red-team, craft-reviewer, fractal-architect, r3f-craft-specialist verdicts)
- [ ] Address every adversarial finding or document why deferred
- [ ] Final aesthetic acceptance per Linear-grade scrutiny

---

## Cross-cutting open decisions (deferred, not blocking start)

These can be resolved during Phase 1 by the team handling tokens; record decisions in the spec lock doc.

- [ ] Per-token rename vs revalue: which existing names stay, which migrate? (e.g., `aozora` → `gunjō`?)
- [ ] Berkeley Mono purchase ($75) — when does it become worth it? Phase 2 or Phase 5?
- [ ] Exact orbit-camera defaults for 3D (Phase 3 ADR-0004)
- [ ] Whether to refactor `OperatorMicrographics` to the new token names or leave as-is until its consumers migrate

---

## Out of scope (do not pull in)

- R_V research (separate track)
- terminal_bridge.py refactor (over its ceiling; needs decomposition track of its own)
- Mobile design (Phase X, after web+desktop solid)
- The untracked codex-composer page (stays deferred until a real PR per spec lock doc)
- Manifest_health.py deprecation (separate refactor PR, not blocking)
- CONTROL_WATCH_TOWER removal (docs-only cleanup, separate)

---

## Last touched

When you ship a checkbox, also note here:
- 2026-05-21 — Initial checklist created. Phase 0 items 1 + 2 complete.
