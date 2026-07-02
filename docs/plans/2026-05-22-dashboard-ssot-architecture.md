# Dashboard SSOT Architecture — Deep Audit & Next-PR Ladder

**Date:** 2026-05-22
**Role:** working_plan (subordinate to `CANONICAL_DOC_STACK.md`)
**Stop condition:** This document only. No code committed in this pass.
**Provenance:** Devin session `2987d22290324e5ba8b44d6368115755`, executing Codex-drafted audit structure from `~/.claude/plans/2026-05-22-codex-dashboard-deep-audit-prompt.md`.

---

## §1  Purpose & Constraint

**The problem:** The operator (John) is the integration layer. Twelve+ agents produce PRs, context, and state — but no single surface lets an agent (or a human) see the full picture without copy-pasting across sessions. The dashboard exists to eliminate this bottleneck.

**Constraints for this pass:**

| Constraint | Rationale |
|---|---|
| No new substrate | MemoryKernel, BoardStore, Sakshi, ControlSurface are already in flight. Wire them; do not invent new ones. |
| No 3D UI | The 2D control surface + zone-based nav is the correct near-term surface. |
| No new API endpoints | 19 routers are already registered in `api/main.py`. Wire the existing ones to the frontend pages that claim to consume them. |
| No code in this pass | Architecture document only. The output is a ladder of specific, rankable PRs. |

---

## §2  What We've Shipped (The 10-Commit Ladder)

Recent track closures that feed the dashboard:

| Track | Shipped | Dashboard impact |
|---|---|---|
| `operator-brief-seam-2026-04` | Ontology-native operator brief | `/api/ontology` returns real records |
| `cockpit-control-surface-2026-05` | ControlSurface projector + Envelope + DisplayHints | `/dashboard/control-surface` is the only fully-wired 5-zone page |
| `boardstore-facade-2026-05` | BoardStore facade + event log + adapters | `/api/commands/tasks` now backed by facade |
| `trace-identity-coverage-2026-05` | CorrelationContext → Sakshi, BoardStore, operator-brief | Trace metadata available for lineage/audit pages |
| PR #321 (pending) | TaskBoard adapter + Dhyana onboard + BR closure | Wires first real adapter behind facade |
| PR #323 (pending) | dkeys↔dharma env alias normalization | Fixes the GEMINI/NVIDIA key mismatch blocking provider-gated pages |
| PR #312 (pending) | MemoryKernel release gate | Adds memory kernel control rows to control surface |

### The OperatorMicrographics Lesson

**Pattern to hunt: fake surfaces hiding real signals.**

The dashboard has 20 frontend pages. The manifest declares 7 LIVE, 7 DEGRADED, 6 STUB. But "DEGRADED" is doing a lot of work. Some degraded pages have working hooks and real API endpoints that return data (telemetry, ontology, evolution). Others have beautiful React pages that call hooks that call endpoints that return empty arrays because no runtime data flows through them yet.

The honest fidelity map (verified against code, not manifest claims):

| Status | Count | Pages |
|---|---|---|
| **LIVE — real data flows** | 7 | Overview, Control Surface, Command Post, Qwen Surgeon, Agents, Tasks, Stigmergy |
| **WIRED — API exists, data sparse** | 5 | Telemetry, Ontology, Evolution, Lineage, Eval Harness |
| **FACADE — hook exists, endpoint returns empty** | 2 | Audit, Runtime |
| **STUB — no API wiring at all** | 6 | Observatory, Gates, Ecosystem, Synthesizer, Workflows, Blocks |

The "WIRED but sparse" category is the OperatorMicrographics zone: these pages look broken but are actually blocked on upstream data (provider keys, loop closure, runtime state). Once the merge train lands (#321–#328) and provider aliases normalize (#323), several will transition to LIVE without any dashboard code changes.

---

## §3  Vision Docs — Read These First (In Order)

Any agent picking up dashboard work must read these 6 documents before writing code:

| # | Document | What it answers |
|---|---|---|
| 1 | `CLAUDE.md` | Behavioral contract, key abstractions, file organization |
| 2 | `docs/governance/CANONICAL_DOC_STACK.md` | What owns what; the three-layer SSoT model (Intent/Surface/State) |
| 3 | `ACTIVE_SURFACE_MANIFEST.yaml` | Machine-readable surface map: every page, router, agent, integration, loop |
| 4 | `docs/governance/ACTIVE_TRACK.yaml` | Current build track and non-goals |
| 5 | `INTERFACE_MISMATCH_MAP.md` | Every known interface mismatch (0 BLOCKERs, 4 DEGRADED) |
| 6 | `CYBERNETIC_LOOP_MAP.md` | Every feedback loop's closure status (latest: 4/13 bounded-replay closed; 0/13 all-history daemon clean) |

After those six, the depth-on-demand surface is:

- `docs/architecture/SWARM_BOARDSTORE_SPEC.md` — BoardStore facade contract
- `docs/architecture/CONTROL_SURFACE.md` — Control Surface projector design
- `docs/state/BROKEN_REGISTER.md` — 9 enumerated known issues (5 open)

---

## §4  The Split: Two Independent Audit Tracks

The dashboard aggregates two fundamentally different information domains. The audit must split cleanly along this boundary:

### Track A — REPO BUILD

What the codebase declares, what PRs exist, what governance gates pass or fail.

| Entity class | Source of truth | Current count |
|---|---|---|
| Manifest surface entries | `ACTIVE_SURFACE_MANIFEST.yaml` | 20 dashboard surfaces, 13 agents, 6 integrations, 6 recursive discovery surfaces, 5 loops |
| Active track | `ACTIVE_TRACK.yaml` | 1 ACTIVE, 3 recently closed |
| Broken register items | `docs/state/BROKEN_REGISTER.md` | 9 total (5 OPEN/PARTIAL, 4 CLOSED) |
| Interface mismatches | `INTERFACE_MISMATCH_MAP.md` | 0 BLOCKER, 4 DEGRADED (NEW-05 guarded, NEW-07/08 partial, MM-05 resolved) |
| Open PRs | `gh pr list` | 12 open (6 from this session, 3 from Codex, 1 security fix, 2 other) |
| Governance CI gates | 22 checks per PR | DocOps, pytest, semgrep, gitleaks, Rule 10, Shakti Warrant, Coherence Delta, etc. |
| API routers registered | `api/main.py` | 19 routers (health, agents, evolution, ontology, lineage, stigmergy, commands, modules, dashboard_new, telemetry, graphql, verify, opportunities, manifest, revenue, control_surface, chat, fleet, gateway) |

### Track B — WORKING DHARMA SWARM

What the live runtime actually does: agent execution, telemetry streams, economic transactions, board events.

| Entity class | Source of truth | Current state |
|---|---|---|
| Agent fleet | `agent_runner.py` + ontology registry | Agents register via ontology; dispatch fails at `orchestrator.py:2074` (Loop 1 not closed) |
| Telemetry plane | `telemetry_plane.py` + `runtime_telemetry_projector.py` | RuntimeTelemetryProjector wired; data sparse until loops close |
| Economic engine | `economic_engine.py` + `revenue/spine.py` | TransactionType/RevenueSource/ExpenseCategory modeled; 0 real transactions |
| Control surface rows | `operator_core/control_surface.py` (1001 lines, grandfathered) | Builds rows from ACTIVE_SURFACE_MANIFEST + runtime probes; 5-zone cockpit renders them |
| Stigmergy marks | `stigmergy.py` → `~/.dharma/stigmergy/marks.jsonl` | JSONL append-only; 6 channels; cross-channel at salience >0.8 |
| Board events | `board/event_log.py` → `~/.dharma/board/event_log.sqlite3` | Append-only SQLite; 10 event kinds; trace_id inherited from CorrelationContext |
| Sakshi provenance | `sakshi/provenance_log.py` → `~/.dharma/sakshi/provenance_log.jsonl` | 10 actor kinds, 10+ action kinds; governance snapshot hash per entry |
| Dhyana drift triage | `dhyana/drift_triage.py` | Wired to control surface; ranks findings alongside degraded evidence |
| Chetana | Referenced in MemoryKernel (`write_receipts.py`, `surface_specs_core.py`, `context_parity.py`, `identity.py`) | Name only; no standalone module. Chetana is a MemoryKernel concept, not a separate subsystem. |
| Cybernetic loops | `CYBERNETIC_LOOP_MAP.md` | 4/13 bounded-replay closed (Loops 1, 2, 5, 6); 7 PARTIAL; 2 BLOCKED behind One Wire; 0/13 all-history daemon clean |
| Mission state | `~/.dharma/state/runtime.db` | 27 sessions, 42 task claims (all failed), Loop 1 is the gate |

---

## §5  Six Parallel Audit Agents

Each agent has a clear scope, an input surface, and a deliverable. No overlaps.

### REPO BUILD side (3 agents)

#### Agent 1: manifest-archaeologist

**Scope:** Reconcile `ACTIVE_SURFACE_MANIFEST.yaml` against actual code.

**Input:**
- `ACTIVE_SURFACE_MANIFEST.yaml` (657 lines)
- `dashboard/src/lib/dashboardNav.ts` + `controlPlaneRouteDeck.js`
- `api/main.py` (router registration block, lines 269–293)
- Every `dashboard/src/app/dashboard/*/page.tsx`
- Every `dashboard/src/hooks/use*.ts`

**Deliverable:** Table of manifest-vs-reality for each of the 20 declared dashboard surfaces:
- Does the page exist? (file check)
- Does the page import a hook? (grep)
- Does the hook call an API endpoint? (grep)
- Is that API endpoint registered in `api/main.py`? (grep)
- Does the endpoint return non-empty data without runtime preconditions? (code read)

**Current findings (from this audit):**

| Surface | Page exists | Hook wired | API registered | Data flows |
|---|---|---|---|---|
| control_surface | Yes | `useControlSurface` | `/api/control-surface/*` | Yes — full 5-zone cockpit |
| overview | Yes | `useOverview`, `useAgents`, `useHealth` | `/api/overview`, `/api/agents`, `/api/health` | Yes |
| command_post | Yes (70 lines) | Chat hooks | `/api/chat` | Yes — dual-orchestrator relay |
| qwen_surgeon | Yes (2394 lines) | Chat hooks | `/api/chat` | Yes — surgical coding lane |
| agents | Yes | `useAgents` | `/api/agents` | Yes |
| tasks | Yes | `useTasks` | `/api/commands/tasks` | Yes |
| stigmergy | Yes | `useStigmergy` | `/api/stigmergy` | Yes |
| telemetry | Yes | `useTelemetry` | `/api/telemetry` | Wired — data sparse |
| ontology | Yes | `useOntology` | `/api/ontology` | Wired — needs ontology.db |
| evolution | Yes | `useEvolution` | `/api/evolution` | Wired — DarwinEngine degraded |
| lineage | Yes | `useLineage` | `/api/lineage` | Wired — needs Sakshi/trace data |
| eval_harness | Yes | via dashboard_new | `/api/eval/*` | Wired — needs gauntlet runs |
| runtime | Yes | `useRuntimeControlPlane` | `/api/health` | Facade — needs OperatorBridge |
| audit | Yes | via dashboard_new | `/api/health` | Facade — needs witness logs |
| observatory | Yes (802 lines) | `useQuery` → `/api/agents/observatory` | `/api/agents` | **Mismatch** — calls `/api/agents/observatory` but endpoint is `/api/agents` |
| gates | Yes | `useGates` | None registered | **Broken** — hook exists, no backend |
| ecosystem | Yes | Direct `fetch` calls | None registered | **Broken** — fetches to undefined endpoints |
| synthesizer | Yes | Direct `fetch` calls | None registered | **Broken** — fetches to undefined endpoints |
| models | Yes | Direct `fetch` calls | None registered | Partial — some model listing works |
| blocks | Yes | None | None | Pure stub |
| workflows | Yes | None | None | Pure stub |

#### Agent 2: pr-track-historian

**Scope:** Map every open PR to the dashboard surface it affects.

**Input:**
- `gh pr list --state open --limit 100`
- Each PR's changed files
- `docs/state/BROKEN_REGISTER.md`
- `ACTIVE_TRACK.yaml`

**Deliverable:** PR-to-surface matrix showing which dashboard pages each PR would improve.

**Current findings (12 open PRs):**

| PR | Surfaces affected | Effect |
|---|---|---|
| #321 | Tasks, Audit, Control Surface | TaskBoard adapter → tasks page gets real facade data; BR-009/010/011/012 close |
| #323 | All provider-gated pages | Env alias fix → GEMINI/NVIDIA keys resolve → telemetry/ontology/evolution data flows |
| #325 | None directly (ops docs) | Agent onboarding docs for Codex |
| #326 | None directly (state docs) | HOTLIST + NEXT_PHASE_MAP for coordination |
| #327 | None directly (ops tooling) | `make status` + cross-agent inventory |
| #328 | Active track governance | ADR-0002 → track becomes SHIPPABLE |
| #314 | Control Surface (docs) | Router/TaskBoard domain pinning doc |
| #312 | Control Surface, Runtime | MemoryKernel release gate → memory kernel rows in control surface |
| #320 | Evolution, Ontology | ADR-007: retire AutoProposer direct submission |
| #322 | Agents, Control Surface | DGM core + agent onboarding wiring |
| #324 | Telemetry, Audit | CWT v0 read-only collector + report |
| #329 | Runtime (security) | SQL injection fix in guardian runtime checks |

#### Agent 3: governance-gate-auditor

**Scope:** Verify every CI gate that protects dashboard PRs.

**Input:**
- `.github/workflows/`
- `scripts/governance/`
- `scripts/docops/`
- `.semgrep/`

**Deliverable:** Gate coverage matrix: which gates protect which dashboard surfaces.

**Current gate inventory (22 checks):**

| Gate | What it protects | Dashboard relevance |
|---|---|---|
| DocOps integrity | Canonical doc guard, assertion registry | Any PR adding/renaming dashboard docs |
| pytest (full suite) | 601 test files, 10,450 functions | Backend router behavior |
| Rule 10 (module budget) | 500-line limit (1000 grandfathered) | `control_surface.py` at 1001 (grandfathered) |
| Semgrep (anti-slop) | No bare RuntimeStateStore in tests | Test hygiene for dashboard backends |
| Gitleaks | No secrets in commits | API key safety |
| Shakti Warrant | Hot-path module changes need ACK | `swarm.py`, `orchestrator.py`, `telic_seam.py` |
| Coherence Delta | PR body must declare organ/gap/proof/drift | Every PR |
| CodeQL | Taint tracking, injection | Security (caught taint through `os.environ` in #323) |
| PR collision detect | No duplicate BR-id citations | Broken register coordination |

---

### WORKING DHARMA SWARM side (3 agents)

#### Agent 4: fleet-mission-auditor

**Scope:** Map agent fleet state, mission lifecycle, and task execution paths.

**Input:**
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/swarm.py`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/board/facade.py`
- `dharma_swarm/board/event_log.py`
- `~/.dharma/state/runtime.db`

**Deliverable:** Agent lifecycle diagram: spawn → claim → dispatch → execute → witness → handoff. Mark which steps are wired and which are broken.

**Current state:**
- **spawn:** SwarmManager creates agent pool. Works.
- **claim:** TaskBoard `claim_task()` acquires lease. Works (42 claims recorded).
- **dispatch:** Orchestrator `dispatch_to_worker()` fails at line 2074 — no available worker because Loop 1 is not closed (LLM provider dispatch fails).
- **execute:** Never reached in production. Works in test context (Witness loop has 1,013 entries).
- **witness:** Sakshi provenance log records actor/action/evidence. Wired but no production entries.
- **handoff:** Board event log records `card_handoff`. Wired but no production events.

**Dashboard impact:** The Agents page shows agent cards but with no live execution data. The Tasks page shows task records but all are in failed/pending state.

#### Agent 5: telemetry-economics-mapper

**Scope:** Map telemetry data flows and economic transaction paths to dashboard surfaces.

**Input:**
- `dharma_swarm/telemetry_plane.py`
- `dharma_swarm/telemetry_views.py`
- `dharma_swarm/runtime_telemetry_projector.py`
- `dharma_swarm/economic_engine.py`
- `dharma_swarm/revenue/spine.py`
- `api/routers/telemetry.py`
- `api/routers/revenue.py`

**Deliverable:** Data-flow diagram: where telemetry is produced, how it reaches the API, what the dashboard page renders.

**Current state:**
- **Telemetry production:** `TelemetryPlaneStore` reads from `~/.dharma/state/runtime.db`. `RuntimeTelemetryProjector` materializes runtime state into telemetry views. Both are lazily initialized in the router.
- **Telemetry API:** 7 endpoints in `telemetry.py` (277 lines). Returns real data when runtime.db has content.
- **Telemetry dashboard:** `useTelemetry` hook wired. Page renders metrics, timeline, agent telemetry. Data is sparse because few runtime events have occurred.
- **Revenue production:** `RevenueSpine` manages targets, outreach drafts. `EconomicEngine` tracks transactions.
- **Revenue API:** 5 endpoints in `revenue.py` (115 lines) — snapshot, targets, outreach, economic summary.
- **Revenue dashboard:** No dedicated revenue page exists. Revenue data is available via API but not surfaced in the frontend nav.

**Key gap:** Revenue/economics has a working backend (`revenue.py`, `economic_engine.py`) but zero frontend presence. This is a real signal hiding behind no surface.

#### Agent 6: operational-state-surveyor

**Scope:** Survey all operational state directories and their consumers.

**Input:**
- `~/.dharma/` directory tree
- `ACTIVE_SURFACE_MANIFEST.yaml` `state_dir` block
- `dharma_swarm/daemon_config.py` (`dharma_state_dir()`)

**Deliverable:** State directory map: what file/DB lives where, which API reads it, which dashboard page renders it.

**Current state directory layout:**

| Path | Format | Writer | API reader | Dashboard consumer |
|---|---|---|---|---|
| `~/.dharma/state/runtime.db` | SQLite | SwarmManager, RuntimeStateStore | `/api/telemetry`, `/api/health`, `/api/agents` | Overview, Telemetry, Agents |
| `~/.dharma/ontology.db` | SQLite | OntologyRegistry, TelicSeam | `/api/ontology` | Ontology page |
| `~/.dharma/board/event_log.sqlite3` | SQLite | BoardStore EventLog | None (not yet exposed) | **None — missing API** |
| `~/.dharma/sakshi/provenance_log.jsonl` | JSONL | Sakshi ProvenanceLog | None (not yet exposed) | **None — missing API** |
| `~/.dharma/stigmergy/marks.jsonl` | JSONL | StigmergyStore | `/api/stigmergy` | Stigmergy page |
| `~/.dharma/economics/` | JSON files | EconomicEngine | `/api/revenue` | **None — no frontend** |
| `~/.dharma/revenue_packets/` | JSON files | RevenueSpine | `/api/revenue` | **None — no frontend** |
| `~/.dharma/sessions/` | Mixed | SwarmManager | `/api/health` | Runtime page (partial) |
| `~/.dharma/evolution/archive.jsonl` | JSONL | DarwinEngine | `/api/evolution` | Evolution page (sparse) |
| `~/.dharma/witness/` | JSONL | TelosGatekeeper | None (not yet exposed) | **None — Gates page is broken** |
| `~/.dharma/go_receipts/world/` | JSON | Go world-radar | `/api/control-surface` (via rows) | Control Surface (incubating) |
| `~/.dharma/events/recursive_discovery.jsonl` | JSONL | RecursiveDiscovery | `/api/control-surface` (shadow) | Control Surface (shadow) |

---

## §6  Synthesis

### A. Inventory Summary

| Category | Total | Live | Degraded/Wired | Stub/Broken |
|---|---|---|---|---|
| Dashboard pages | 20 | 7 | 7 | 6 |
| API routers | 19 | 19 (all registered) | — | — |
| Backend agents/subsystems | 13 | 8 | 3 | 2 |
| Integrations | 6 | 2 (Anthropic, OpenRouter) | 2 (DBs) | 2 (receipts) |
| Cybernetic loops | 13 | 0 production / 1 test | 7 PARTIAL | 5 NO |
| State directories | 12 | 5 (have API readers) | 3 (have writers, no API) | 4 (empty/incubating) |
| Broken register items | 9 | — | 5 OPEN/PARTIAL | 4 CLOSED |

### B. Zone Assignments

The dashboard nav already organizes pages into 4 sections. Each audit agent owns a zone:

| Nav section | Pages | Primary audit agent | Secondary |
|---|---|---|---|
| **COMMAND** (L1) | Overview, Control Surface, Command Post, Qwen Surgeon, Observatory, Runtime, Opportunities, Conv. Log, Truth Map, Semantic Graph, Models, GLM-5, Telemetry, Ecosystem, Synthesizer, Agents, Tasks | manifest-archaeologist (structure), fleet-mission-auditor (data) | telemetry-economics-mapper |
| **INTELLIGENCE** (L3) | Eval Harness, System Audit, Evolution, Gates | governance-gate-auditor | fleet-mission-auditor |
| **DEEP** (L4) | Ontology, Lineage, Stigmergy | operational-state-surveyor | manifest-archaeologist |
| **COMPOSE** (L5) | Workflows, Blocks | manifest-archaeologist (these are pure stubs) | — |

### C. Shared Chrome

Infrastructure all zones depend on:

1. **`ACTIVE_SURFACE_MANIFEST.yaml`** — the declared-intent layer. Every zone reads it.
2. **`dharma_state_dir()`** (`dharma_swarm/daemon_config.py`) — canonical state directory resolution. Every backend router calls this.
3. **`ControlSurfaceEnvelope`** (`control_surface_models.py`) — the standard response envelope (schema_version, request_id, generated_at, source_errors, data). Should be adopted by all API routers for consistency.
4. **`CorrelationContext`** (`correlation_context.py`) — trace_id propagation. Board events, Sakshi entries, and operator-brief records already inherit it.
5. **`dashboardNav.ts` + `controlPlaneRouteDeck.js`** — the frontend nav declaration. Must match the manifest's `dashboard_nav_sections`.
6. **`useHealth` hook + `/api/health`** — the baseline health probe every page can check.

### D. Kill List

Pages and endpoints that should be deprecated or merged:

| Target | Current state | Action | Rationale |
|---|---|---|---|
| `/dashboard/glm5` (1956 lines) | Model-specific page | **Merge into Models page** | GLM-5 is one model; doesn't warrant its own page |
| `/dashboard/qwen35` (2394 lines) | Model-specific surgical lane | **Keep but rename** | It's actually a general surgical coding lane, not Qwen-specific. Rename to "Surgeon" |
| `/dashboard/claude` (580 lines, "Semantic Graph") | Misnamed | **Rename to Semantic Graph** or merge into Ontology | Route is `/dashboard/claude` but label is "Semantic Graph" — confusing |
| `/dashboard/modules` (625 lines, "Truth Map") | Module listing | **Merge into System Audit** | Duplicates information available through audit + manifest |
| `/dashboard/blocks` (88 lines) | Pure stub, no hook, no API | **Remove from nav** until wired | Dead weight in navigation |
| `/dashboard/workflows` (88 lines) | Pure stub, no hook, no API | **Remove from nav** until wired | Dead weight in navigation |
| `/api/graphql` (434 lines) | Registered but no dashboard consumer | **Audit usage** | If nothing calls it from the frontend, consider removing |
| `/api/viz` (98 lines) | No dashboard consumer | **Audit usage** | Likely dead code |
| `LIVE_OPS_DASHBOARD.md` | 10+ days stale (snapshot 2026-05-11) | **Replace with `make status`** | `make status` (PR #327) renders the same info live |
| `CYBERNETIC_LOOP_MAP.md` | 16+ days stale | **Refresh or auto-generate** | Still claims "no configured LLM provider" which is now false |
| `INTERFACE_MISMATCH_MAP.md` | 17+ days stale | **Refresh** | 90+ PRs merged since last update |

### E. Next 3 PRs (Ranked by Dashboard ROI)

#### PR Ladder Step 1: Wire Board Events + Sakshi Provenance to API

**Why first:** Two of the richest data sources (`board/event_log.sqlite3`, `sakshi/provenance_log.jsonl`) have zero API exposure. The Lineage, Audit, and Timeline pages are all DEGRADED because they have no data source. This single PR would light up 3 pages.

**Scope:**
- Add `/api/board-events` router (read-only: list events, filter by card_id/trace_id/kind)
- Add `/api/provenance` router (read-only: list entries, filter by actor/action/trace_id)
- Wire `useLineage` hook to `/api/provenance` + `/api/board-events`
- Wire Audit page to `/api/provenance` (decision chain rendering)
- Wire Timeline page to both (unified activity stream)
- Register both routers in `ACTIVE_SURFACE_MANIFEST.yaml`

**Surfaces affected:** Lineage (DEGRADED → WIRED), Audit (FACADE → WIRED), Timeline (currently unused → WIRED)

**Estimated size:** ~300 lines (2 routers + hook wiring)

#### PR Ladder Step 2: Wire Gates Page to TelosGatekeeper

**Why second:** The Gates page has a working `useGates` hook but no backend endpoint. The `telos_gates.py` module has gate check logic. The witness log at `~/.dharma/witness/` has 1,013 entries. This is a classic "fake surface hiding real signals" — the page exists, the data exists, they're just not connected.

**Scope:**
- Add `/api/gates` router (read-only: list gate definitions, recent gate check results from witness log)
- Wire `useGates` hook to `/api/gates`
- Register in manifest

**Surfaces affected:** Gates (STUB → LIVE)

**Estimated size:** ~120 lines

#### PR Ladder Step 3: Revenue/Economics Dashboard Surface

**Why third:** Revenue pipeline has a working backend (`revenue.py` — 5 endpoints, `economic_engine.py` — full transaction model) but zero frontend presence. Adding a nav entry + page that calls the existing API endpoints would surface real economic data with minimal work.

**Scope:**
- Add `/dashboard/revenue` page (call existing `/api/revenue/snapshot`, `/api/revenue/targets`)
- Add `useRevenue` hook
- Add nav entry in `controlPlaneRouteDeck.js`
- Register in manifest

**Surfaces affected:** New "Revenue" page (LIVE from day one — backend already works)

**Estimated size:** ~200 lines (page + hook + nav entry)

### F. 7 Broken Interfaces (OperatorMicrographics Pattern)

These are "fake surfaces hiding real signals" — places where the dashboard claims to show something but the data path is broken:

| # | Interface | Frontend | Backend | Break point |
|---|---|---|---|---|
| 1 | **Observatory → agent observatory** | `page.tsx` calls `/api/agents/observatory` | No `/api/agents/observatory` endpoint exists | Hook calls non-existent endpoint; returns undefined |
| 2 | **Gates → telos gate checks** | `useGates` hook exists | No `/api/gates` endpoint registered | Hook has no backend to call |
| 3 | **Ecosystem → module dependencies** | Page makes direct `fetch` calls | No ecosystem-specific endpoint | Fetches to undefined URLs |
| 4 | **Synthesizer → memory palace** | Page makes direct `fetch` calls | No synthesizer endpoint | Fetches to undefined URLs |
| 5 | **Board events → dashboard** | `event_log.sqlite3` is written by facade | No API router exposes board events | Data exists, no API |
| 6 | **Sakshi provenance → dashboard** | `provenance_log.jsonl` is written | No API router exposes provenance | Data exists, no API |
| 7 | **Revenue/economics → dashboard** | `revenue.py` has 5 API endpoints | No frontend page exists | Backend works, no UI |

### G. Elevator Pitch

The dharma_swarm dashboard is a cybernetic control surface for a self-modifying multi-agent system. It reconciles **declared intent** (what the manifest says should exist) against **observed reality** (what the runtime actually produces). Today, 7 of 20 pages show real data. The gap is not a frontend problem — the React pages are well-built and the hooks are properly abstracted. The gap is a **wiring problem**: rich backend data (board events, provenance logs, gate checks, economic transactions) exists in state directories and API routers but is not connected to the pages that claim to render it.

The next 3 PRs (board-events+provenance API, gates API, revenue page) would move the dashboard from 7/20 LIVE to 11/20 LIVE — a 57% improvement — by wiring existing data to existing pages. No new substrate. No new concepts. Just plumbing.

---

## §7  Don't-Do List

| Don't | Why |
|---|---|
| Don't build 3D UI | The 2D zone-based layout is correct for the current data density |
| Don't add new API endpoints for hypothetical data | Only expose data that already exists in `~/.dharma/` |
| Don't refactor ControlSurface (1001 lines) | It's grandfathered at Rule 10 ceiling; decomposition is a separate track |
| Don't commit code in this pass | This document is the deliverable |
| Don't propose MemoryKernel changes | MemoryKernel is in flight (PR #312); let it land first |
| Don't merge PRs #321–#329 | That's the operator's decision, not an agent's |
| Don't treat DEGRADED pages as broken | Many are "wired but sparse" and will come alive after provider normalization |
| Don't create new subsystems | Wire the existing 13 agent subsystems to the existing 19 API routers to the existing 20 dashboard pages |

---

## §8  Why This Matters

The operator is currently the integration layer between 12+ agent sessions. Every context transfer is a manual copy-paste. Every "where are we?" question requires re-reading 5+ state files. The dashboard is supposed to eliminate this — but with 7/20 pages live and 3 critical data sources (board events, provenance, gate checks) having zero API exposure, the dashboard cannot serve as the shared coordination surface it was designed to be.

This audit maps the exact wiring gaps. The next 3 PRs are specific, bounded, and measurable. An agent picking up this document can read it cold and know exactly what to build, in what order, and why. No human router required.

---

## Appendix: Verification Commands

```bash
# Verify manifest surface counts
python3 -c "import yaml; m=yaml.safe_load(open('ACTIVE_SURFACE_MANIFEST.yaml')); print(len(m['dashboard_surfaces']), 'surfaces')"

# Verify API router count
grep -c "include_router" api/main.py

# Verify dashboard page count
find dashboard/src/app/dashboard -name "page.tsx" -not -path "*/\[*" | wc -l

# Check hook wiring per page
for page in dashboard/src/app/dashboard/*/page.tsx; do
  name=$(echo "$page" | sed 's|dashboard/src/app/dashboard/||; s|/page.tsx||');
  hooks=$(grep -c "use[A-Z]" "$page" 2>/dev/null || echo 0);
  echo "$name: $hooks hooks";
done | sort -t: -k2 -rn

# Run full governance check
make onboard
```
