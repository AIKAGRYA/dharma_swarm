# SWARM HOT ITEMS

One obvious, rewriteable live map for the current DHARMA SWARM architecture, drift, risks, and cleanup order.

If another doc disagrees with this file, verify against code, GitNexus, ContextPlus, and tests, then rewrite this file instead of creating another competing "source of truth" doc.

## How To Use This File

- Treat this as the current hot-items ledger and live architecture map.
- Keep sections nested and addressable by heading.
- Rewrite stale sections in place.
- Keep claims evidence-backed with file paths, symbols, routes, or process names.
- Do not turn this into a prose archive. Keep it compact, structured, and current.

## Current Verdict

- 2026-05-04 control-plane addendum: `chore/phase2-governance-rollup` is locally brake-green at `3e5b8d9`, but it is not promotion-ready without reconciliation. It is `89` commits ahead and `71` commits behind `origin/main`, and `origin/main` now carries a separate `dharma_swarm/operator_brief/` seam while rollup carries top-level Daily Insight/Telic seam work.
- Governance scanner addendum: assurance provider-contract noise has been reduced to zero in `chore/governance-truth-repairs`; remaining high assurance findings are concentrated in real dashboard/API route-contract drift. Do not treat this as permission to add new API/product surface.
- Clean enough to trust: desktop-shell boot path, 4-route dashboard control-plane deck, API lifespan/auth boundary, runtime fetch contract.
- Runtime authority membrane now exists: `ACTIVE_SURFACE_MANIFEST.yaml` classifies API routers, dashboard pages, cron jobs, state writers, and overlap families without deleting research artifacts.
- Noisy: API/router sprawl, dashboard surface count, `~/.dharma` state spread, many overlapping docs claiming canonical truth.
- Fake-stable: duplicate terminal shells, transitional TUI fallback chain, dual organism APIs, fleet "canonical" wording, placeholder dashboard pages.
- Must fix before review: terminal duplication, `SwarmManager` optional-subsystem accretion, state-store sprawl.
- Recently cleared: `ThinkodynamicDirector.execute_pending_tasks()` now fail-closes dependent workflow steps after blocked/failed parent tasks while preserving successful drain and dynamic fanout.

## Hot Items

- [ ] Reconcile `chore/phase2-governance-rollup` with `origin/main` before new feature work.
- [ ] Choose one canonical Operator Brief / Daily Insight Brief entrypoint; do not let `dharma_swarm/operator_brief/` and top-level `dharma_swarm/insight_brief.py` harden as parallel systems.
- [ ] Classify unsupported dashboard/API projections as inactive or fail-closed; do not add backend endpoints only to satisfy stale helpers.
- [ ] Collapse `terminal-v2/` into reference-only status and stop shell-core duplication.
- [ ] Replace implicit TUI fallback behavior with one explicit shell policy.
- [ ] Split `dharma_swarm/terminal_bridge.py` into transport, session, snapshot, and command slices.
- [x] Fix `ThinkodynamicDirector.execute_pending_tasks()` dependency contract and repair failing tests.
- [x] Install `ACTIVE_SURFACE_MANIFEST.yaml` plus assurance scanner for non-destructive runtime authority checks.
- [ ] Extract `SwarmManager._init_optional_subsystems()` into bounded boot modules.
- [ ] Consolidate `~/.dharma` state contracts and reduce ad hoc JSONL stores.
- [ ] Remove or demote placeholder and dead surfaces from dashboard/API/nav.
- [ ] Collapse `dharma_swarm/organism.py` to one runtime contract.
- [ ] Mark fleet surfaces as projections until backed by a stronger authority layer.
- [ ] Re-run focused verification after each cleanup wave.

## Canonical Live Map

### 1. Operator Surface

- Desktop shell is the clearest current boot surface: `desktop-shell/src-tauri/src/main.rs`
  - boots `scripts/dashboard_ctl.sh start`
  - defaults to `http://127.0.0.1:3420/dashboard/command-post`
- Dashboard control-plane deck is the canonical operator route set: `dashboard/src/lib/controlPlaneRouteDeck.js`
  - `/dashboard/command-post`
  - `/dashboard/qwen35`
  - `/dashboard/observatory`
  - `/dashboard/runtime`
- Dashboard nav exposes many more routes than the deck: `dashboard/src/lib/dashboardNav.ts`

### 2. Runtime / Control Plane

- API lifecycle and router registration live in `api/main.py`
- `get_swarm()` in `api/main.py` is the runtime singleton boundary into `dharma_swarm/swarm.py:SwarmManager`
- Runtime dashboard truth is fetched by `dashboard/src/hooks/useRuntimeControlPlane.ts`
  - `fetchChatStatus()`
  - `fetchHealth()`
- `RuntimePage` and the other deck pages cluster around the same small control-plane process family in GitNexus

### 3. Chat / Session Contract

- Chat contract source is `api/routers/chat.py`
  - `CHAT_CONTRACT_VERSION = "2026-03-19.chat.v1"`
  - chat conversations live under `~/.dharma/conversations`
- Canonical session persistence is `dharma_swarm/operator_core/session_store.py`
  - session root: `~/.dharma/sessions`
  - writes `transcript.jsonl`, `audit.jsonl`, `runtime.jsonl`, `snapshots.jsonl`

### 4. Terminal Surfaces

- `terminal/` is the active Bun shell seam, but not yet a full replacement: `terminal/README.md`
- `terminal-v2/` is explicitly non-canonical and frozen: `terminal-v2/README.md`
- `dharma_swarm/tui_launcher.py` still keeps a multi-stage fallback chain into legacy Textual surfaces
- `dharma_swarm/terminal_bridge.py` is the shared Python seam between runtime and terminal UIs

### 5. Fleet / Worker Projection

- `api/routers/fleet.py` is a thin API surface over `dharma_swarm/fleet_control.py`
- `dharma_swarm/fleet_control.py` explicitly says it projects existing runtime state instead of being a new control plane

### 6. Organism / Evolution / Self-Modification

- `dharma_swarm/organism.py` intentionally exports both legacy and newer organism APIs
- `dharma_swarm/swarm.py` wires optional evolution, monitoring, director, gateway, and bridge subsystems into one boot path
- `dharma_swarm/thinkodynamic_director.py` is a very large hot path and remains operationally brittle

## Legacy / Duplicate Surface Map

### Shell Duplication

- `terminal/src/persistence.ts` and `terminal-v2/src/core/persistence.ts` are near-parallel files
  - line counts: `2139` vs `2222`
  - diff summary: `85 insertions`, `2 deletions`
- `terminal/src/state.ts` and `terminal-v2/src/core/state.ts` are effectively mirrored
  - line counts: `658` vs `658`
  - diff summary: `1 insertion`, `1 deletion`
- `terminal/tests/persistence.test.ts` and `terminal-v2/tests/core/persistence.test.ts` are also near-parallel

### Transitional Fallbacks

- `dharma_swarm/tui_launcher.py` still falls back from new TUI to `tui_legacy` and then older import paths
- `dharma_swarm/terminal_bridge.py` describes itself as the bridge for a future Bun/Ink frontend
- `dharma_swarm/organism.py` keeps both legacy and newer organism layers alive

### Dead Or Suspect Paths

- `dashboard/src/app/dashboard/blocks/page.tsx` remains on disk as a placeholder page and is no longer advertised in the sidebar
- `dashboard/src/app/dashboard/workflows/page.tsx` remains on disk as a placeholder page and is no longer advertised in the sidebar

## Hot-Path Risk Table

| Surface | Risk | Why |
| --- | --- | --- |
| `dharma_swarm/swarm.py:SwarmManager` | CRITICAL | GitNexus upstream impact is large and spans API, CLI, scripts, tests, and runtime surfaces |
| `api/main.py:get_swarm` | CRITICAL | Shared singleton boundary for health, agents, commands, routing, fleet, chat |
| `dharma_swarm/terminal_bridge.py:TerminalBridge` | CRITICAL | Shared seam across shells, sessions, snapshots, commands, and tests |
| `dharma_swarm/operator_core/session_store.py:SessionStore` | CRITICAL | Shared persistence contract for bridge and Textual/TUI flows |
| `dharma_swarm/thinkodynamic_director.py:ThinkodynamicDirector` | HIGH | Large file and broad blast radius, but worker-loop dependency regression is covered by passing focused tests |

## Source-Of-Truth Contract Table

| Topic | Current contract |
| --- | --- |
| Desktop boot route | `desktop-shell/src-tauri/src/main.rs` |
| Dashboard control-plane deck | `dashboard/src/lib/controlPlaneRouteDeck.js` |
| Dashboard runtime fetch truth | `dashboard/src/hooks/useRuntimeControlPlane.ts` |
| API lifecycle and router registration | `api/main.py` |
| Swarm singleton boundary | `api/main.py:get_swarm` |
| Swarm runtime core | `dharma_swarm/swarm.py:SwarmManager` |
| Runtime authority membrane | `ACTIVE_SURFACE_MANIFEST.yaml` |
| Chat API contract | `api/routers/chat.py` |
| Canonical session persistence | `dharma_swarm/operator_core/session_store.py` |
| Fleet read model | `dharma_swarm/fleet_control.py` |

## Current Measured Signals

- Dashboard pages on disk under `dashboard/src/app/dashboard`: `41`
- Canonical dashboard deck routes: `4`
- Registered router inclusions in `api/main.py`: `21` plus chat websocket
- Python files directly referencing `Path.home()` and `.dharma`: `231`
- Drift marker counts from `rg -i --count-matches <term> .` on 2026-05-02:
  - `TODO`: `441`
  - `FIXME`: `23`
  - `HACK`: `35`
  - `fallback`: `1657`
  - `legacy`: `1093`
  - `deprecated`: `209`
  - `placeholder`: `405`
- Actual open comment markers in active source/test/UI dirs:
  - `TODO`: `10`
  - `FIXME`: `0`
  - `HACK`: `0`
- Interpretation: `fallback`, `legacy`, `deprecated`, and `placeholder` are vocabulary debt signals, not open TODO items. They include tests, docs, reports, duplicated terminal surfaces, and scanner baselines unless explicitly scoped.

## Recommended Patch Order

1. Reconcile rollup with `origin/main`; local green is not enough while the branch is `89` ahead and `71` behind.
2. Resolve the Operator Brief / Daily Insight seam fork and preserve TelicSeam proposal, gate, outcome, value-event, and citation linkage.
3. Classify unsupported dashboard/API projections as inactive or fail-closed instead of adding new product surface.
4. Collapse duplicate shell ownership around `terminal/`.
5. Make terminal fallback behavior explicit and non-default.
6. Split `TerminalBridge` by responsibility.
7. Keep `ThinkodynamicDirector.execute_pending_tasks()` in the focused smoke suite; worker-loop dependency gating is currently green.
8. Modularize `SwarmManager` optional boot wiring.
9. Introduce a single typed state-root contract for `~/.dharma`.
10. Remove dead/placeholder routes and nav entries.
11. Collapse `organism.py` to one runtime surface.
12. Re-label projections as projections, not authority.
13. Re-run verification and refresh this file.

## Verification Snapshot

- GitNexus index was rebuilt on 2026-05-02 09:56 WITA and is now current: indexed commit `cc28fe3`, `30672` symbols, `78911` edges, `1809` clusters, `300` flows, embeddings off.
- GitNexus CLI is usable when the repo is explicit because two repos are indexed: `gitnexus context --repo dharma_swarm <symbol>`.
- GitNexus MCP server itself works: `node scripts/probe_gitnexus_mcp.mjs` reports tools `list_repos`, `query`, `cypher`, `context`, `detect_changes`, `rename`, `impact`.
- Current Codex session still cannot query GitNexus through `list_mcp_resources(server="gitnexus")`; the session appears to retain stale MCP startup wiring. `~/.codex/config.toml` now points GitNexus MCP at the local executable instead of `npx -y gitnexus@latest`, so new Codex sessions should avoid that timeout path.
- Local millisecond index exists at `.dharma/global_vision.sqlite`: `2743` files, `2466` text files, `25732` symbols, `17020` imports, `3557` marker hits, built by `python3 scripts/global_vision.py index`.
- Repeatable repair command exists: `scripts/reindex_global_vision.sh`.
- `npm --prefix dashboard run build` passed
- `pytest -q tests/test_thinkodynamic_director.py` passed: `46 passed`, `1 warning`
- `pytest -q tests/test_task_board.py` passed: `20 passed`, `1 warning`
- The previously failing director tests now pass:
  - `tests/test_thinkodynamic_director.py::test_execute_pending_tasks_handles_blocked`
  - `tests/test_thinkodynamic_director.py::test_execute_pending_tasks_preserves_failure_output_on_task_record`

## Assurance Slop Classes

<!-- assurance-meta:start -->
- Last learned: 2026-05-01T15:01:33.341294+00:00
- Current assurance status: FAIL
- `python_block_line_budget_exceeded`: 13 finding(s), severity=high, scanner=complexity_budget, example=dharma_swarm/agent_runner.py
- `file_line_budget_exceeded`: 8 finding(s), severity=high, scanner=complexity_budget, example=dharma_swarm/agent_runner.py
- `raw_env_access`: 23 finding(s), severity=medium, scanner=config_state, example=dharma_swarm/agent_runner.py
- `inactive_dashboard_route_in_nav`: 19 finding(s), severity=medium, scanner=active_surface_manifest, example=dashboard/src/lib/dashboardNav.ts
- `raw_dharma_state_path`: 13 finding(s), severity=medium, scanner=config_state, example=dharma_swarm/agent_runner.py
- `placeholder_runtime`: 2 finding(s), severity=medium, scanner=placeholder_debt, example=dharma_swarm/ontology.py
- `missing_obvious_test_coverage`: 2 finding(s), severity=medium, scanner=test_gap, example=api/routers/cascade_router.py
- `unmanifested_state_writer`: 1 finding(s), severity=medium, scanner=active_surface_manifest, example=dharma_swarm/agent_runner.py
- `ontology_runtime_leak`: 1 finding(s), severity=medium, scanner=ownership_audit, example=dharma_swarm/ontology.py
- `duplicate_active_surface`: 1 finding(s), severity=medium, scanner=complexity_budget, example=terminal-v2/src
- `human_alias_in_source`: 4 finding(s), severity=low, scanner=concept_registry, example=dharma_swarm/dgc_cli.py
<!-- assurance-meta:end -->

## Rewrite Rules

- Rewrite this file when the control-plane truth changes.
- Prefer replacing stale bullets over appending more prose.
- Keep new claims tied to code symbols, routes, tests, or GitNexus impact/context results.
- If a cleanup item is completed, move it from `Hot Items` into the relevant subsystem section with the new contract.
