# Cockpit V2 Grafana Board Mode — Execution Receipt

Status: initialized. Implementation and verification will append below.

## Source Grounding

- Long-running goal: `docs/design/COCKPIT_V2_GRAFANA_LONG_RUNNING_GOAL.md`
- Desktop source manifest: `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`
- Current cockpit truth receipt: `reports/governance/operator_coherence_cockpit.md`


## 2026-06-23 Fugu Recommendations Folded In

Read and folded these reconciliation artifacts:

- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md`
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/prod_readiness/PROD_READINESS_CONTINUATION_2026-06-23.md`
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/prod_readiness/RENDER_CHECK_DISCREPANCY_RESOLVED_2026-06-23.md`
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.md`
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_LANE_PACKET_2026-06-23.md`
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/lane_admission/NEXT_AGENT_GOAL_COCKPIT_ADMISSION_2026-06-23.md`

Wrote:

- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.md`
- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json`
- `docs/governance/schemas/agent_lane_admission_packet.schema.json`

Fold-in verdict:

- Cockpit remains `CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL`.
- Recommended extraction branch: `governance/operator-coherence-cockpit-20260623`.
- Recommended future track identity: `operator-coherence-control-tower-2026-06`.
- Do not raw-merge dirty checkout.
- Do not treat local 11/11 active-track projection as canonical 7/10 origin/main truth.
- No destructive commands or branch surgery were executed.

## UI Lane Slice — V2 Grafana Board Wired (2026-06-23)

Role correction: this lane owns the `/dashboard/cockpit` UI/dashboard experience. The companion Fugu lane owns backplane/admission/truth semantics.

### Implemented in this slice

- Wired `/dashboard/cockpit` through `OperatorCoherenceCockpit` to the new V2 board component.
- Added `dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts`:
  - human risk/kind labels;
  - mode/filter functions;
  - design-source references from Desktop canon/prototypes/inspiration;
  - panel data builders;
  - inspect/handoff model.
- Added `dashboard/src/components/operator-coherence/v2/CockpitV2Primitives.tsx`:
  - reusable stat panel;
  - card row;
  - mode/search filter bar;
  - section shell;
  - right-side inspect drawer with evidence, raw JSON, and copy-scoped-handoff.
- Added `dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx`:
  - Grafana-style top hero/header;
  - 6 compact top stat panels;
  - mode buttons: Overview, Triage, Git, Runtime, Tracks, Preservation, Evidence, Design Sources;
  - local search over normalized cockpit cards;
  - overview next-action queue;
  - source-control bar gauge panel;
  - live-ops bar gauge panel;
  - incident list;
  - Desktop design-source board;
  - Git/runtime/tracks/preservation/evidence modes.
- Extended `dashboard/src/lib/operatorCoherence.ts` typing for live-ops summary fields used by the board.

### Design grounding explicitly represented in UI

The V2 board exposes design sources for:

- `MANDALA_MISSION_CONTROL_CANON.md`
- `LIVING_ONTOLOGY_v1_DESIGN_2026-06-15.md`
- `ART_DIRECTION_v2_2026-06-15_RUG_TO_INSTRUMENT.md`
- `LIVE_OPS_COCKPIT_V2_GOAL_SPEC.md`
- `grafana new.jpeg`
- `proto_1_atlas_board.png`
- `proto_v2b_command_synthesis.png`
- `POSTMORTEM_proto_v14_waste.md`
- `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`

### Verification commands

Focused UI lint:

```bash
cd dashboard && npm run lint -- \
  src/app/dashboard/cockpit/page.tsx \
  src/components/operator-coherence/OperatorCoherenceCockpit.tsx \
  src/components/operator-coherence/v2/CockpitV2Board.tsx \
  src/components/operator-coherence/v2/CockpitV2Primitives.tsx \
  src/components/operator-coherence/v2/cockpitV2Model.ts \
  src/lib/operatorCoherence.ts
```

Result: PASS.

Dashboard production build:

```bash
cd dashboard && npm run build
```

Result: PASS. `/dashboard/cockpit` listed in generated routes.

API proxy smoke through fresh production server:

```bash
curl -sS -m 10 'http://127.0.0.1:3421/api/operator-coherence/report?live_probes=false'
```

Result summary: `ok 46.0 176 207`.

Rendered browser DOM evidence from `http://127.0.0.1:3421/dashboard/cockpit`:

```json
{
  "hasV2": true,
  "hasDesign": true,
  "excerpt_contains": [
    "MANDALA MISSION CONTROL · LINEAR BOARD MODE",
    "Cockpit V2",
    "Grafana-style operator instrument grounded in Desktop canon/prototypes/inspiration",
    "207 BRANCHES",
    "19 RECEIPTS",
    "Overview / Triage / Git / Runtime / Tracks / Preservation / Evidence / Design Sources",
    "Prod readiness 41.5%",
    "Source control 0%",
    "Runtime liveness 5%"
  ]
}
```

### Notes / uncertainties

- The existing dev server on port `3420` appeared to serve a stale pre-V2 cockpit chunk. I did not kill it. I started a fresh production server on port `3421` for verification.
- A broad `npx tsc --noEmit` still reports unrelated repo-wide/test type issues; the authoritative dashboard `npm run build` passed after the V2 type gaps were fixed.
- The V2 board is a meaningful UI slice, but the full long-running goal remains active: more polish, canonicality badges, production-readiness cards, lane packet rendering, browser screenshot artifacts, and extraction into a clean branch are still pending.

## UI Lane Audit — Requirement-by-Requirement Verification (2026-06-23, Agent 3 audit role)

Independent re-derivation of the objective's explicit requirements and verification each is handled by the current patch.

| # | Requirement (from objective) | Evidence | Status |
|---|---|---|---|
| 1 | Grafana-style board on `/dashboard/cockpit` | `page.tsx` → `OperatorCoherenceCockpit` → `CockpitV2Board`; build lists `/dashboard/cockpit`; DOM shows "MANDALA MISSION CONTROL · LINEAR BOARD MODE" + "Cockpit V2" | PASS |
| 2 | Reusable panels | `CockpitV2Primitives.tsx` (`V2Panel`, `V2CardRow`, `V2Section`, `V2FilterBar`, `V2Drawer`); `buildTopPanels` yields 6 panels (unit test) | PASS |
| 3 | Filters/search | `V2FilterBar` + `filterCards`; unit test proves mode scoping + free-text search; DOM has search input + 8 mode buttons | PASS |
| 4 | Drilldown | `onInspect` wired on panels/cards/actions/sources → `V2Drawer`; `cardToInspect`/`actionToInspect`/`sourceToInspect` unit-tested | PASS |
| 5 | Evidence links | Every inspect item carries `evidence[]`; unit test asserts readiness panel + card + source inspect retain evidence | PASS |
| 6 | Verification receipts | This file + `reports/governance/operator_coherence_cockpit.{json,md}` | PASS |
| 7 | Grounded in Desktop design packet/inspiration/canon | `DESIGN_SOURCES` references canon, grafana ref, atlas/command prototypes, postmortem, manifest; unit-tested | PASS |
| 8 | Uses current operator coherence cockpit data | Consumes `/api/operator-coherence/report` via `useOperatorCoherence`; API smoke `ok 46.0 176 207` | PASS |

### New durable evidence added this turn

- Added `dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts` (8 tests, node:test via bun).
  - Covers: 8 modes, design-source grounding, 6 evidence-backed panels, mode+search filtering, triage routing, drilldown inspect conversion, safe handoff prompt, human labels/tone.

### Verification commands run (Agent 3)

```bash
cd dashboard && npm run lint -- <v2 files + page + lib>          # PASS (0 problems)
cd dashboard && bun test src/components/operator-coherence/v2/cockpitV2Model.test.ts  # 8 pass / 0 fail
cd dashboard && npm run lint -- src/components/operator-coherence/v2/cockpitV2Model.test.ts  # PASS
cd dashboard && npm run build                                    # PASS, /dashboard/cockpit emitted
```

Live DOM (earlier, port 3421): `buttonCount=43`, `hasSearchInput=true`, all 8 modes present, readiness panel found + clickable.

### Edge cases checked

- `live_ops` summary optional fields (`human_authority_required`, `proof_gap_surfaces`, `vps_candidates`) typed in `operatorCoherence.ts` — no runtime crash when absent (defaults via `?? 0`).
- `pr_ci_triage.enabled=false` path renders "Unavailable" reason rather than crashing.
- Empty card lists render "No cards match this view" empty state (`CardTableMode`).
- Drawer is null-safe (`if (!item) return null`).

### Remaining (goal stays active — not yet world-class-complete)

- Backplane contract fields (canonicality badges, lane admission packets, production-readiness verdict cards) are documented in the companion lane's schema but not yet rendered as first-class UI badges.
- Browser screenshot artifact not captured this turn (puppeteer bridge intermittently unavailable); DOM evaluate + unit tests used instead.
- Clean-branch extraction (`governance/operator-coherence-cockpit-20260623`) pending operator approval.

## UI Lane Continuation — 2026-06-22T20:56:21Z

### Scope

Continued Cockpit V2 Grafana Board Mode as the UI lane only. Boundary remained `UI rendering` + small `UI state` affordance (`/` focuses search). No backplane authority edits, no branch extraction, no `ACTIVE_TRACK.yaml` mutation, no destructive cleanup.

### Implemented

- Added an explicit hero authority banner: **candidate / not canonical**.
  - Shows dirty local branch from `report.git.main.branch` when available.
  - Shows canonical baseline `origin/main` / `839fd25f43c7...` and canonical 7/10 vs local projection count.
  - Drawer links back to the admission review and local generated report evidence.
- Added first-class truth/canonicality badge model for cards.
  - Taxonomy includes `CANONICAL_ORIGIN_MAIN`, `DIRTY_LOCAL_CANDIDATE`, `LOCAL_ONLY_BRANCH`, `LIVE_RUNTIME_PROOF`, `STALE_RECEIPT`, `OFF_REPO_ARTIFACT`, `UNAVAILABLE_UNCERTAIN`, and `INFERRED`.
  - Card rows now visibly distinguish tracked/untracked, live/stale, preserved/not preserved, intentional/rogue, local-only/origin-backed, and operator-decision/engineering-task facets.
- Added production-readiness verdict cards.
  - Renders the five production-grade review verdicts as UI cards.
  - Explicitly prevents “checker SHIPPABLE” from being visually treated as production closure.
- Added Agent Lane Admission Packet UI contract card.
  - Renders required lane packet fields and inspect drawer evidence for `docs/governance/schemas/agent_lane_admission_packet.schema.json`.
  - This is a UI consumer/contract view only; live lane packet ingestion remains the backplane lane.
- Improved inspect drawer evidence UX.
  - Shows evidence path/status/detail more clearly.
  - Added `Copy evidence` and `Copy raw` buttons alongside existing scoped handoff copy.
- Added keyboard affordance: `/` focuses board search unless typing in an input/textarea/contenteditable.

### Files touched in this slice

- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts`
- `dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx`
- `dashboard/src/components/operator-coherence/v2/CockpitV2Primitives.tsx`
- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts`
- `reports/governance/cockpit_v2_grafana_execution_receipt.md`

### Verification

```bash
cd dashboard && bun test src/components/operator-coherence/v2/cockpitV2Model.test.ts
# PASS: 12 pass / 0 fail

cd dashboard && npm run lint -- \
  src/app/dashboard/cockpit/page.tsx \
  src/components/operator-coherence/OperatorCoherenceCockpit.tsx \
  src/components/operator-coherence/v2/CockpitV2Board.tsx \
  src/components/operator-coherence/v2/CockpitV2Primitives.tsx \
  src/components/operator-coherence/v2/cockpitV2Model.ts \
  src/components/operator-coherence/v2/cockpitV2Model.test.ts \
  src/lib/operatorCoherence.ts
# PASS

cd dashboard && npm run build
# PASS: /dashboard/cockpit emitted

curl -sS -m 10 'http://127.0.0.1:3422/api/operator-coherence/report?live_probes=false'
# PASS smoke: ok 46.0 readiness, 176 cards, 207 branches
```

### Browser note

Started a fresh production dashboard server on port `3422` after build because the older `3421` server was serving the pre-continuation bundle. Puppeteer navigation to `http://127.0.0.1:3422/dashboard/cockpit` succeeded. The screenshot tool returned an image payload but did not create a repo file at `reports/governance/ui_artifacts/cockpit_v2_board.png`; treat screenshot artifact capture as still pending unless a later lane writes the PNG explicitly.

### Remaining UI work

- Re-run rendered DOM/screenshot capture from fresh port and persist `reports/governance/ui_artifacts/cockpit_v2_board.png` with a file-backed tool.
- Replace hardcoded candidate/admission constants with live backplane packet ingestion once the backplane lane exposes them through the report/API.
- Add real lane packet list rendering once packets exist, not just the contract card.
- Add finer operator drill-in flows for track verdict cards and PR/CI triage when GitHub auth is available.

### Render verification addendum — 2026-06-22T21:02Z

The sandboxed Playwright launch initially failed with macOS Chromium Mach port permission errors, so render verification was rerun with scoped escalation for local headless browser access only.

```bash
cd dashboard && node <playwright local dashboard verification>
# PASS: {"hasCandidateBanner":true,"hasProdReadiness":true,"hasLaneAdmission":true,"hasTruthBadge":true,"hasFacetBadges":true}
```

Screenshot artifact captured:

- `reports/governance/ui_artifacts/cockpit_v2_board.png` — 1440×1200 PNG, fresh production server on port 3422.

Correction to prior note: screenshot capture is now file-backed and present in the repo worktree.

### Drawer interaction verification addendum — 2026-06-22T21:12Z

Added and verified cockpit click-in/out ergonomics:

- Inspect drawer now has `role="dialog"` and `aria-modal="true"`.
- `Escape` closes the drawer.
- Clicking the backdrop closes the drawer.
- Close button title now advertises `Close (Esc)`.

Verification used a fresh production server on port `3423` after rebuilding the dashboard:

```bash
cd dashboard && npm run build
cd dashboard && npm run start -- -p 3423
cd dashboard && node <playwright drawer interaction verification>
# PASS: {"hasCandidateBanner":true,"hasProdReadiness":true,"hasLaneAdmission":true,"dialogOpen":1,"afterEsc":0,"reopened":1,"afterBackdrop":0}
```

Screenshot artifact captured:

- `reports/governance/ui_artifacts/cockpit_v2_board_latest.png` — fresh post-drawer-verification screenshot.

## Observatory Slice — Topology + Recursive + Uncertainty + AnswerRibbon + EventTape (2026-06-23)

Role: UI lane. Implemented the master-spec "First Implementation Slice" (spec §28) that was missing from the prior Grafana-board pass, turning the board into a truthful operator **observatory** per `MANDALA_COCKPIT_MASTER_SPEC_PROMPT_2026-06-23.md`.

### What this slice added (gap vs. master spec)

The prior pass shipped a Grafana stat board but lacked the spec's signature observatory pieces. This slice adds them, all bound to `/api/operator-coherence/report` (no new truth file):

1. **AnswerRibbon** (spec 11.3 / REQ-013/014): 8 under-60-second answers (Safe, Dirty, Abandoned, Live, Blocked, Rogue, Next, Readiness) derived from `report.definition_answers`. Empty `what_is_live` renders as **uncertainty**, never blank success (anti-pattern #14).
2. **Impossible-to-miss UncertaintyStrip** (REQ-006, core goal target): full-width banner under the hero. `buildUncertainty()` surfaces raw `source_errors` plus gh/tmux/gcx unavailability explicitly. "ABSENCE IS NOT SUCCESS." Clean snapshots show an explicit all-clear, not a blank.
3. **Errors mode** (REQ-052/070/072, spec 11.10): dedicated lens for unavailable sources, PR/CI (gh auth) unavailable, and Grafana/gcx unconfigured — no fake telemetry.
4. **CockpitTopology** with `@xyflow/react` (spec 7.1/7.2/8.5/11.6, REQ-030/031/034/035): `buildTopology()` derives stable `CockpitNode`/`CockpitEdge` from readiness categories, tracks, live surfaces, action cards, and source errors. Node size = evidence+risk, opacity = freshness, dashed edges = uncertain, pulse only for **live+fresh** surfaces. MiniMap + Controls + deterministic cluster layout.
5. **RecursiveMandala** (spec 11.7, REQ-032): same node model in nested rings (readiness → tracks → live surfaces → cards/uncertainty). Faded = stale, dashed = uncertain.
6. **Cross-mode selection preservation** (REQ-032): `selectedId` is retained across Linear ↔ Topology ↔ Recursive.
7. **ReceiptEventTape** (spec 11.9 / REQ-060/062): snapshot tape of report event, recent receipts (freshness-aged), source errors, and PR/CI unavailable; honestly labeled "history not yet wired."
8. **Reduced-motion** (REQ-084) + state-encoded pulse CSS in `globals.css` (spec 8.4): pulse used only where state is live+fresh; `prefers-reduced-motion` disables all non-data motion and React Flow edge animation.
9. **Machine-readable status-token coverage** (spec §16 testing): `STATUS_TOKENS` + `statusTone()` guarantee every status maps to a visual tone; unit-tested.

### Files touched

- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts` — added freshness helpers, `buildAnswerRibbon`, `buildUncertainty`, `buildTopology` (CockpitNode/CockpitEdge), `buildEventTape`, `STATUS_TOKENS`/`statusTone`, new modes (topology/recursive/errors).
- `dashboard/src/components/operator-coherence/v2/CockpitV2Topology.tsx` — NEW: React Flow topology + SVG recursive mandala.
- `dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx` — wired UncertaintyStrip, AnswerRibbon, ErrorsMode, ReceiptEventTape, topology/recursive modes, cross-mode selection. Removed dead/broken `OperatingLoopsSection` (referenced non-existent `report.operating_loops` + undefined `uguisu` token; it broke the build).
- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts` — +7 tests (answer ribbon, uncertainty, topology stability/no-stale-pulse, event tape, freshness, token coverage).
- `dashboard/src/app/globals.css` — cockpit pulse keyframes + reduced-motion block.

### Verification

```bash
cd dashboard && bun test src/components/operator-coherence/v2/cockpitV2Model.test.ts   # 19 pass / 0 fail
cd dashboard && npm run lint -- src/components/operator-coherence/v2/ src/lib/operatorCoherence.ts  # 0 problems
cd dashboard && npm run build   # PASS, /dashboard/cockpit emitted
```

Live render (fresh prod server, Playwright local headless; API proxied to 127.0.0.1:8420):

```json
{"cockpitV2":true,"answerLiveUncertainty":true,"uncertaintyStrip":true,
 "modesTopology":true,"modesRecursive":true,"modesErrors":true,"eventTape":true,
 "topology":{"react-flow":true,"nodes":124,"edges":123},
 "recursive":{"svgCircles":148,"mandala":true},
 "errors":{"gcx":true,"prci":true},
 "answerRibbon":["Safe","Dirty","Abandoned","Live","Blocked","Rogue","Next","Readiness"] all present,
 "mobileNoHorizontalOverflow":true (scrollW==clientW==390),
 "consoleErrors":0}
```

Screenshot artifacts (repo-root):

- `reports/governance/ui_artifacts/cockpit_v2_observatory.png` (Errors mode, full)
- `reports/governance/ui_artifacts/cockpit_v2_overview.png`
- `reports/governance/ui_artifacts/cockpit_v2_topology.png`
- `reports/governance/ui_artifacts/cockpit_v2_recursive.png`
- `reports/governance/ui_artifacts/cockpit_v2_mobile.png`

### Acceptance criteria (spec §19) status

1 loads ✓ · 2 same API ✓ · 3 no new truth file ✓ · 4 top strip answers readiness/health/freshness/uncertainty ✓ · 5 top-3 actions without scrolling ✓ · 6 evidence inspector ✓ · 7 dirty/blocked/abandoned/live/rogue/stale/unknown visually distinct ✓ · 8 topology from real nodes/edges ✓ · 9 recursive uses same objects ✓ · 10 source errors visible ✓ · 11 gh/tmux/gcx unavailable visible ✓ · 12 no fake time-series (tape labeled "history not yet wired") ✓ · 13 mobile no overlap ✓ · 14 reduced motion respected ✓ · 15 instrument not landing page ✓.

### Remaining (goal stays active)

- Backplane: replace hardcoded candidate/admission/prod-readiness constants with live report fields once the backplane lane exposes them.
- Topology: optional elkjs layout if node density grows beyond the current deterministic cluster layout.
- gcx: render real Grafana sources once context is configured (currently truthful "unavailable").

## Independent Spec Audit Fixes — Source Truth, Resilience, Full Topology (2026-06-24)

Second-pass audit independently re-derived the first-slice requirements from the master spec and found gaps in the prior patch that were not acceptable for an 8.5+/10 truthful operator observatory:

- **REQ-004/005 gap:** loading was a one-line card and API failure lacked endpoint/retry detail.
- **REQ-006/010 gap:** top strip did not show a derived report source mode (`live/cached/partial/stale/unavailable`) from report status, age, and source errors.
- **Truth-rule gap:** hero/authority panels displayed hardcoded canonical/candidate commit and active-track claims. These were removed from visible UI/model tests; the cockpit now only reports authority/source state from `/api/operator-coherence/report` and labels missing canonical baseline proof as uncertainty.
- **Spec §7/REQ-030 gap:** topology derived only action cards + tracks + live surfaces + source errors. It now derives semantic nodes for **all cards**, branch/worktree/receipt/action/live-surface/source-error/readiness objects, and all edges carry evidence arrays.
- **Spec §7.3/REQ-025/026 gap:** action packets were not explicit. Added `ActionPacket` derivation with `allowedNow: false` and visible “proposal only · can act now: no”.
- **REQ-032/§11.6 gap:** topology/recursive modes did not consume the global filter. They now dim non-matching nodes/edges and preserve selected IDs from linear/card selections.
- **Data-contract gap:** frontend assumed complete report shape. `fetchOperatorCoherenceReport()` now normalizes wrapped and direct responses, defaults missing core arrays/objects, and checks `data.source_errors` correctly for wrapped responses.

### Additional files/areas changed in this pass

- `dashboard/src/lib/operatorCoherence.ts` — report normalization, optional `status`/`metadata`, wrapped/direct response resilience.
- `dashboard/src/components/operator-coherence/OperatorCoherenceCockpit.tsx` — designed layout skeleton; explicit source failure panel with retry and endpoint details.
- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts` — `ReportSourceSummary`, `ActionPacket`, full semantic topology nodes/edges, evidence arrays, node filter matching; removed visible dependency on hardcoded canonical/candidate claims.
- `dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx` — source-mode hero, report-source/read-only authority, proposal-only action queue, filter-aware topology/recursive calls.
- `dashboard/src/components/operator-coherence/v2/CockpitV2Topology.tsx` — filter dimming, action/receipt clusters, recursive filter display.
- `dashboard/src/components/operator-coherence/v2/CockpitV2Primitives.tsx` — snapshot time-window selector.
- `dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts` — 20 tests covering action packets, report source mode, full semantic topology, edge evidence arrays, filter matching, and removal of hardcoded canonical proof expectations.

### Final verification

```bash
cd dashboard && bun test src/components/operator-coherence/v2/cockpitV2Model.test.ts
# 20 pass / 0 fail

cd dashboard && npm run lint -- src/components/operator-coherence/OperatorCoherenceCockpit.tsx src/components/operator-coherence/v2/ src/lib/operatorCoherence.ts
# 0 problems

cd dashboard && npm run build
# PASS; /dashboard/cockpit emitted
```

Final fresh-build browser verification with local API (`.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8420`) and local Next server (`npm run start -- -p 3437`):

```json
{
  "overview": {
    "title": true,
    "reportSource": true,
    "sourceMode": true,
    "noHardcodedCanonical": true,
    "uncertainty": true,
    "answerRibbon": true,
    "proposalOnly": true,
    "eventTape": true,
    "overflow": false
  },
  "topology": { "rf": true, "nodes": 265, "edges": 264 },
  "recursive": { "mandala": true, "circles": 289 },
  "errorCount": 0
}
```

Also verified the source-failure state by loading the cockpit while `127.0.0.1:8420` was unavailable: the route showed the explicit `/api/operator-coherence/report` source failure panel with retry and did not present a blank/healthy dashboard.

New artifact:

- `reports/governance/ui_artifacts/cockpit_v2_final_overview.png`

### Current acceptance status

All first-slice acceptance criteria are now supported by current code and direct evidence: existing endpoint preserved, no new manual truth file, source errors/uncertainty impossible to miss, report source mode prominent, top-3 proposal-only actions visible, evidence drilldown, real report-derived topology/recursive views, gh/tmux/gcx unavailable states visible, history explicitly not wired, reduced motion CSS present, mobile/browser render checks pass, and no hardcoded canonical operational claims remain visible.
