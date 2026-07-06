---
title: Holon Runtime Full Estate Map
path: docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md
doc_type: architecture
status: current
created: 2026-07-06
owner_surface: sovereign_holon_runtime
companion_doc: docs/architecture/AGENT_HOLON_CODE_MAP.md
summary: Full code-bearing-surface census of the agent/holon runtime across dharma_swarm (repo), ~/.dharma (runtime state), ~/.hermes (parallel third-party ecosystem), and ~55-60 worktrees/clones — extends AGENT_HOLON_CODE_MAP.md, which remains canonical for the sovereign-holon talk/run/health call chains.
verification: 12-zone parallel discovery + synthesis + 9-claim adversarial verification (6 confirmed, 3 refuted-and-corrected) via Workflow run wf_959eb1c7-33b, 2026-07-06. Every number below is post-correction.
---

# Agent/Holon Runtime — Full Estate Map

**Scope**: dharma_swarm (repo-owned), `~/.dharma` (mutable runtime state), `~/.hermes` (third-party + parallel self-mod ecosystem), and the dharma_swarm-family worktrees/clones (60 trees, live-counted). This is a **companion, not a replacement** for [`AGENT_HOLON_CODE_MAP.md`](AGENT_HOLON_CODE_MAP.md), which remains canonical ground truth for the sovereign-holon talk/run/health call chains (`holon_bridge.py`, `holon_runtime.py`, `holon_persistence.py`, `holon_health.py`, `holon_service_liveness.py`, `holon_canonical_state.py`, `holon_truth_projection.py`, `holon_killswitch.py`, `holon_budget_guard.py`, `holon_compass.py`; `scripts/holon_talk.py`, `scripts/holon_run.py`, `scripts/runtime/live_ops_census.py`, `api/routers/holon.py`). This map covers everything that one did not: model routing, A2A transport/spine, API/gateway routers, CLI/wrapper inventory, identity/state-home census, ungoverned scripts, receipts/observability, worktree drift, and the full `~/.hermes` ecosystem.

**Method**: 12 parallel discovery agents → 1 synthesis pass → 9 highest-stakes claims independently re-verified by adversarial checkers (6 CONFIRMED as stated, 3 REFUTED on specific numbers — corrected below, not just flagged). One discovery zone (`identity_state_census`) failed on an API overload during the run; it was redone directly afterward with live shell commands and is folded into §2.12 and §7 below.

---

## 1. Executive Summary

This is **not one clean body** — it is one *intended* canonical body (the Holon Runtime in `dharma_swarm/dharma_swarm/holon_*.py` + its A2A/spine/provider substrate) surrounded by a thick, largely-still-live halo of forks, shadow scaffolds, a second competing agent-lifecycle (the `dgc agent`/`agent_runner`/`swarm.py` path), five competing identity homes, and an entirely separate third-party product (`~/.hermes/hermes-agent`) bridged in over the filesystem. The **real mass** is concentrated in five places: `dharma_swarm/dharma_swarm/runtime_state.py` (4,300 lines, **55 real distinct production importers** — the true substrate under everything; a naive grep sweep counts 90+, but that double-counts a duplicate worktree checkout nested at `.claude/worktrees/langgraph-parity-verifier-20260701/`), `dharma_swarm/dharma_swarm/swarm.py`/`agent_runner.py`/`orchestrator.py` (the legacy-but-dominant execution core, 28/12 real importers respectively), the `spine/` + `a2a/` package (a real, actively-enforced runtime-truth transport and receipt discipline — the code default is opt-in, `DHARMA_SPINE_DISPATCH` is OFF unless explicitly set, **but the one actual persistent daemon on this Mac, `com.dharma.swarm` (PID confirmed live), has it set to `1` in its real running environment right now** — the governance report's "unblessed_spine_launch_spec" flag on that daemon is about launch-spec provenance/pinning, not about dispatch being disabled), `scripts/runtime/` (a directory that is functionally a second, ungoverned package — several files there have 5-9 real importers and should live inside `dharma_swarm/dharma_swarm/`, not `scripts/`), and `~/.hermes/hermes-agent` (a fully independent, currently-running upstream product, PID-confirmed live, that talks to dharma_swarm only through three small bridge scripts over a shared filesystem queue).

**Where the mess is**: (1) `holon/` — a second, actively-developed (commits as recent as Jul 2) fork package at repo root with its **own provider-resolution stack** that bypasses `runtime_provider.py`/`api_keys.py` entirely, reading raw `os.environ`; (2) `dharma_swarm/holon_system/` — previously believed dead, in fact has fresh commits *today* (Jul 6) and a passing test, so it's a live-but-unconsumed facade, not confirmed-dead; (3) a genuine three-way fork of `holon_bridge.py` itself across **60** worktrees (canonical/468L in the current checkout only, "main-ish"/204L in **49** worktrees, "mem-ish"/397L in **6 worktrees + 1 release snapshot = 7 total**, and **3 worktrees with no `holon_bridge.py` at all** — `dharma_helm_build`, `dharma_swarm_cashclaw`, `dharma_swarm_live`); (4) two entirely separate agent-lifecycle surfaces live side by side (`dgc agent talk/run/wake` → `agent_runner.py`/`persistent_agent.py`/`swarm.py`, vs. `scripts/holon_talk.py` → `holon_bridge.py`) with different persistence and no shared identity; (5) **five** competing identity homes (`~/.dharma/agents` 67 dirs/only 17 with `identity.json`, `~/.dharma/ginko/agents` 52, `~/.dharma/external_agents` 26, `~/.dharma/a2a/cards` 49 with 6 hyphen/underscore duplicate pairs, `~/.dharma/a2a_bus/state` 20) with Hermes spelled four different ways (`hermes`, `hermes-m5`, `hermes_m5`, `hermes_m5_bootstrap`) and a live model fork (`ginko/agents/jagat-kalyan` declares `meta-llama/llama-3.3-70b-instruct`, `ginko/agents/jagat_kalyan` declares `claude-code` — same name, different underlying agent); (6) on the `~/.hermes` side, a **live, unguarded, twice-scheduled self-modification loop** (`gepa_lite.py`) whose acceptance gate is confirmed mathematically near-always-accept and has already overwritten live `SKILL.md` files 112 times in production (98.2% accept rate on real mutations, verified against its own 2,345-entry archive), guarded only by a `.bak` copy — this is a materially worse safety posture than dharma_swarm's own (dry-run-gated, structurally never-fired) `self_improve.py`. A second Hermes-side bridge script (`dharma_bridge.py`) shells out arbitrary free-text prompts read from dharma_swarm's shared task queue once an hour (804 completed runs, currently dormant but structurally armed and unguarded — no allowlist, no execution-specific kill-switch, only a broadcast kill-switch exists).

The good news: the spine/A2A transport layer, the governance scripts (`agent_admission.py`, `name_drift_preflight.py`, the three NATS contract scripts), and the API/gateway routers are all genuinely built, tested, and actively enforced — several things worried might not exist yet are in fact mature and green. The bad news is concentrated exactly where safety matters most: two unbounded self-mod loops (one dharma-side, armed-but-inert; one Hermes-side, live-and-firing), a fork family of the single most identity-critical file (`holon_bridge.py`) that no worktree outside the current checkout has caught up with, and an identity layer fragmented five ways with two live naming forks inside it.

---

## 2. Zone Classification Table

### 2.1 Model Routing & Provider Keys

| Location | Tags | Verdict | Evidence | Notes |
|---|---|---|---|---|
| `dharma_swarm/dharma_swarm/runtime_provider.py` | routing, kernel, wrapper | **CANONICAL** | ~65 importers (widest fan-in of any provider file) | The real "ONE WAY" |
| `dharma_swarm/dharma_swarm/api_keys.py` | routing, kernel | **CANONICAL** | 34 importers; loads `~/.dharma/agent_keys.env` (hardcoded path) | Matches CLAUDE.md doctrine exactly |
| `dharma_swarm/dharma_swarm/model_hierarchy.py` | routing, kernel | **CANONICAL** | 43 importers | Defines most-powerful-first order |
| `dharma_swarm/dharma_swarm/providers.py` | routing, runtime | **CANONICAL** | 38 importers | |
| `dharma_swarm/dharma_swarm/provider_policy.py` | routing, runtime | **CANONICAL** | 20 importers | |
| `provider_matrix.py` / `provider_smoke.py` / `base_provider.py` / `providers_extended.py` / `provider_registry.py` | routing, runtime | **CANONICAL (thin)** | 5 / 4 / 3 / 2 / 2 importers | Real but thin, not dead |
| `dharma_swarm/holon_bridge.py::get_holon_provider` | routing, identity | **CANONICAL, correctly wired** | Calls `resolve_runtime_provider_config` → `create_runtime_provider` directly | Confirms doctrine is accurate here |
| `holon/providers.py` + `holon/holon_bridge.py::get_holon_provider` (the fork) | routing, legacy (competing-dev) | **STALE/quarantined, not dead** | Own `Provider`/`ProviderRouter`/`build_provider_router()`; reads raw `os.environ` at line 208 (confirmed exact line); zero references to `runtime_provider`/`api_keys`/`dharma_swarm` anywhere in the file; exactly 2 real external importers (`tests/test_holon_truth_projection.py`, `scripts/verify_holon_harness_prod.py`) | **Danger, adversarially confirmed**: second live provider-resolution stack with no guaranteed link to `agent_keys.env` |
| `~/.claude/skills/dkeys/SKILL.md` | doctrine | **DOES NOT EXIST** | Zero hits anywhere in `~/.claude/` | `dkeys` CLI/skill doctrine is aspirational; actual mechanism is `api_keys.py` + `runtime_provider.py` |
| `~/.dharma/agent_keys.env` | state_only | **LIVE_RUNTIME_STATE** | 7,048 bytes, mtime Jul 4 | Matches hardcoded load path |
| `~/.dharma/model_routing/` | state_only | **LIVE_RUNTIME_STATE (vestigial)** | 1 file only | Name implies more than it holds |
| `~/.dharma/models/` | state_only | **LIVE_RUNTIME_STATE (empty)** | 0 items | Dead-in-practice, harmless |

### 2.2 A2A Transport & Spine

| Location | Tags | Verdict | Evidence | Notes |
|---|---|---|---|---|
| `dharma_swarm/a2a/a2a_server.py` | kernel, transport | **CANONICAL** | Base class for everything; imported by 9+ modules incl. `api/main.py`, 12 test files | Single most load-bearing A2A file |
| `dharma_swarm/a2a/nats_transport.py` | transport, kernel | **CANONICAL** | Imported by 4 modules + 4 tests + 3 governance scripts; mtime Jul 2 | Also shadow-re-exported by dead `holon_system/transport/__init__.py` |
| `dharma_swarm/operator_core/nats_live_contact.py` | gateway, observability | **CANONICAL** | 3 importers + 2 tests, mtime Jul 2 | |
| `dharma_swarm/operator_core/nats_substrate_status.py` | gateway, observability | **CANONICAL but stale-ish** | 1 importer + 2 tests + 3 governance scripts; mtime 3wk behind sibling | Worth a correctness check |
| `scripts/runtime/a2a_send.py` | cli, transport | **CANONICAL** | 5+ real importers incl. `spine/warrant.py`; 8 test files | Strong "promote to package" candidate |
| `scripts/runtime/a2a_inbox_bridge.py` | gateway, semantic_responder, cli | **CANONICAL** | 9 importers incl. `holon_transport_liveness.py`, `holon_canonical_state.py`, `holon_l4_smoke.py` | Real cross-tie into canonical holon core |
| `scripts/runtime/a2a_domain_reply_worker.py` | gateway, semantic_responder, cli | **CANONICAL** | 7 importers + 3 tests | |
| `scripts/runtime/a2a_reply_capture.py` | observability, cli | **CANONICAL** | 3 importers + 4 tests | |
| `dharma_swarm/a2a/a2a_cloud_contact.py` | gateway, transport | **CANONICAL, thin/staler** | Only own test + 3 governance scripts; ~2.5wk stale | Confirm with operator if paused |
| `dharma_swarm/a2a/contact_registry.py` | identity, gateway | **CANONICAL, thin** | 3 importers + own test | Infra-in-place, narrow radius |
| `dharma_swarm/a2a/verifier.py` | observability | **CANONICAL, narrow, honest scope** | Only own test | Docstring explicitly disclaims liveness claims |
| `dharma_swarm/a2a/a2a_bridge.py` | transport, kernel | **CANONICAL, heavily wired** | Imported directly by `orchestrator.py` + 10 test files | The literal seam into the main orchestrator |
| `~/.dharma/a2a_bus/` | state_only | **LIVE_RUNTIME_STATE** | messages/ 4,963; inboxes/ 187; receipts/ 6-7 (thin); actively growing today | Receipt-to-message ratio (7:4,963) suggests most traffic goes unreceipted at this layer |
| `~/.dharma/a2a/` | state_only | **LIVE_RUNTIME_STATE** | cards/ 49, task_log.jsonl 13.6MB, mtime today | Separate dir from `a2a_bus/` with overlapping purpose — dedup question open |

### 2.3 Spine / Orchestrator / Admission

| Location | Tags | Verdict | Evidence | Notes |
|---|---|---|---|---|
| `dharma_swarm/spine/identity.py` | kernel, routing, identity | **CANONICAL** | 21 real importers | |
| `dharma_swarm/spine/invoke.py` | kernel, routing | **CANONICAL** | thinkodynamic_director, orchestrator.py, a2a_bridge | The one blessed dispatch path |
| `dharma_swarm/spine/{receipt,routing,warrant,tollbooth,persistence,adapters,manual_runner}.py` | kernel, routing, identity | **CANONICAL** | Each independently confirmed importers | `adapters.py` explicitly does NOT dispatch (compat only) |
| `dharma_swarm/orchestrator.py` | kernel, routing, wrapper | **CANONICAL, opt-in at code level, ON in the real running daemon** | `_run_task_via_spine` at line 2739/2562 is real; `os.environ.get("DHARMA_SPINE_DISPATCH")=="1"` gates it, unset → legacy path. **But** `com.dharma.swarm` (PID 52094, confirmed running via `launchctl print`) has `DHARMA_SPINE_DISPATCH=1` in its actual live environment right now | `spine_dispatch_mode_report.py`'s "unblessed_spine_launch_spec" flag is about the plist's `ProgramArguments` wrapper not being repo-pinned — a provenance/pinning hygiene flag, not "dispatch is off" |
| `dharma_swarm/agent_runner.py` | runtime, legacy, wrapper-target | **CANONICAL leaf** | Only `swarm.py` + self import | Not a spine caller itself, correctly so |
| `dharma_swarm/semantic_commons.py` | semantic_responder, routing | **CANONICAL** | 4 importers | |
| `dharma_swarm/engine/hybrid_retriever.py` | semantic_responder, kernel | **CANONICAL** | 8 importers | Confirms fusion already works |
| `dharma_swarm/context.py` | kernel, semantic_responder | **CANONICAL** | 13 importers | 5-layer context engine |
| `scripts/governance/agent_admission.py` + `agent_admission_projection.py` | cli, semantic_responder, observability | **CANONICAL, built & green** | Live run: 42 objects/268 aliases/10 active uids/0 errors | Contradicts "may not exist yet" premise in CLAUDE.md track prose |
| `scripts/governance/name_drift_preflight.py` | cli, observability | **CANONICAL, built & active** | Live run produced ~900 real findings | Also contradicts "may not exist yet" |
| `dharma_swarm/revenue/spine.py` | routing (unrelated) | **NAME COLLISION, not duplication** | Zero real coupling to `dharma_swarm/spine/` beyond the word "spine" | Landmine for future greps |

### 2.4 API / Gateway

| Location | Tags | Verdict | Evidence | Notes |
|---|---|---|---|---|
| `api/main.py` | gateway, routing | **CANONICAL** | Sole app entrypoint, registers 21 routers | Also boots `node_gateway.init_gateway()` inline in lifespan |
| `api/routers/holon.py` | identity, gateway, semantic_responder | **CANONICAL** | Loads agent's own model via `holon_bridge`; writes real receipts | True agent-model chat path |
| `api/routers/agents.py` (`/agents/{id}/chat`) | identity, gateway, wrapper | **CANONICAL but cosmetic** | Delegates to `chat.py::_agentic_stream` wearing agent's persona | Does NOT load the agent's actual model — dashboard UX only |
| `api/routers/chat.py` + `api/chat_tools.py` | semantic_responder, gateway, routing | **CANONICAL** | Routed through `runtime_provider` (ONE WAY); 5 test files | Operator's own tool-using chat engine |
| `api/ws.py` | transport | **CANONICAL, thin** | 2 importers | Shared WS primitive |
| `api/routers/{health,agent_cards,evolution,ontology,lineage,stigmergy,commands,modules,dashboard_new,telemetry,graphql_router,verify,opportunities,manifest,revenue,control_surface,operator_coherence,pool,viz,fleet}.py` | mixed | **CANONICAL**, all wired in `main.py` | | 4 separate `/health`-shaped endpoints, no single canonical aggregator |
| `dharma_swarm/a2a/node_gateway.py` | gateway, transport, routing | **CANONICAL** | Router + own `_verify_api_key` auth | The concrete "hermes-m5" A2A hub referenced in CLAUDE.md |
| `api/graphql/schema.py` | dead code | **DEAD** | Zero real importers; `graphql_router.py` doesn't use it | Abandoned real-GraphQL attempt beside the REST router that kept the name |

### 2.5 CLI & Wrapper Layer

| Location | Tags | Verdict | Evidence | Notes |
|---|---|---|---|---|
| `dharma_swarm/dgc_cli.py` | cli, wrapper | **CANONICAL** | Single entry point | `agent wake/talk/run/status/kill` routes to `agent_runner.py`/`persistent_agent.py`/`swarm.py`, **a separate lifecycle from canonical holon** |
| `dharma_swarm/terminal_commands/*.py` (19 files) | cli, wrapper | **CANONICAL** | Sole importer is `dgc_cli.py` | Intentional split, not duplication |
| `scripts/holon_talk.py`, `scripts/holon_run.py` | runtime, cli | **CANONICAL** (pre-existing ground truth) | | The true holon entry points |
| `scripts/holon_l4_*.py` cluster (5 files) | runtime, legacy | **STALE** | Zero external importers | Shelved "L4 escalation" experiment — ask operator if superseded |
| `scripts/{allout_autopilot,overnight_autopilot,composer_background_loop,strange_loop}.py` | runtime, kernel/semantic_responder | **CANONICAL but mis-homed** | Top-level scripts backing `dgc` CLI verbs | `strange_loop.py` (71.5KB, largest file in `scripts/`) should arguably live in the package |
| `scripts/verify_holon_harness_prod.py` | runtime, kernel, observability | **CANONICAL, heaviest holon-adjacent top-level script** | 68KB | Unverified whether it shadow-duplicates `holon_health.py` logic — flagged only |
| `scripts/runtime/live_ops_census.py` | observability, cli | **CANONICAL** | 5 external importers; 4,106 lines (largest in dir) | Strongest promotion candidate |
| `scripts/runtime/pr_merge_control.py` | runtime, kernel | **CANONICAL** | 9 importers (highest in dir), 2,323 lines | Drives Merge Master Mike governance |
| `scripts/runtime/codex_composer_wake_loop.py` | runtime, semantic_responder | **CANONICAL, standalone process** | 0 external importers but mtime today | Run via tmux wrapper, not imported |
| `scripts/runtime/autonomy_spine.py` | runtime, kernel | **CANONICAL, ARMED-BUT-INERT** | 0 importers, mtime Jul 6 | Dharma-side self-mod spine, never fired |
| `scripts/runtime/` Living Agent Kernel cluster (9 files: activation/promotion/provider_worker/recovery/service/status/supervisor/worker/worker_process) | runtime, identity | **STALE-leaning / possible undocumented dup** | 0 external importers each | Name strongly suggests overlap with `holon_runtime.py`'s job — flagged not confirmed |
| ~30 other `scripts/runtime/*.py` | mixed | **CANONICAL, script-shaped** | 0-1 importers | Genuinely script-shaped, not library candidates |

### 2.6 Legacy Substrate (refresh-verified)

| Location | Lines | Real importers | Verdict |
|---|---|---|---|
| `dharma_swarm/swarm.py` | 3,306 | **28** | Heaviest legacy importer count — clearly load-bearing |
| `dharma_swarm/agent_runner.py` | 3,553 | 12 | Canonical generic-task-execution leaf under the spine |
| `dharma_swarm/agent_registry.py` | 980 | 11 | Canonical for the ginko identity scheme; confirmed `agents_dir = GINKO_DIR / "agents"` → `~/.dharma/ginko/agents` |
| `dharma_swarm/autonomous_agent.py` | 1,465 | 5 | Legacy but real |
| `dharma_swarm/persistent_agent.py` | 633 | 2 | Thinnest of the five but still touched recently |

None of these five are dead. All were re-verified this pass with non-zero real importer counts.

### 2.7 Fork / Scaffold (refresh-verified)

| Location | Verdict | Evidence |
|---|---|---|
| `holon/` (repo-root fork package, 24 files/3,318 lines) | **STALE, active unmerged dev, NOT dead** | 2 real external importers (test + verify script); newest touch Jul 2; its `holon_runtime.py` (391 lines) is now LARGER than canonical (287 lines) |
| `dharma_swarm/dharma_swarm/holon_system/` (21 files, 345 lines) | **STALE test-only-facade, NOT dead — reclassified and independently CONFIRMED** | 2 commits both dated **today** (Jul 6: `05d246efe`, `42215a90f`); sole real importer `tests/test_holon_system_imports.py`, all 12 tests pass; self-declared pure re-export facade | Someone is actively building on this branch right now — flag to operator, don't assume inert |

### 2.8 Receipts / Observability

| Location | Verdict | Evidence |
|---|---|---|
| `dharma_swarm/holon_persistence.py` | CANONICAL | 10 importers |
| `dharma_swarm/holon_service_liveness.py` | CANONICAL | 8 importers |
| `dharma_swarm/holon_health.py` | CANONICAL, thin | 2 importers |
| `dharma_swarm/holon_canonical_state.py` | CANONICAL | central hub, 4+ importers |
| `dharma_swarm/holon_truth_projection.py` | CANONICAL, narrowly used | 0 external importers besides own test |
| `dharma_swarm/runtime_state.py` | CANONICAL, massively load-bearing | **55 real distinct production importers** (independently re-counted via grep + an AST-based parser to avoid false positives/negatives), 4,300 lines — true substrate. A naive sweep reaches 90+ only by also counting `dharma_swarm/.claude/worktrees/langgraph-parity-verifier-20260701/` — a full duplicate checkout with its own inodes — as if it were distinct production code; +51 more if test files are folded in |
| `scripts/runtime/live_ops_census.py` | CANONICAL | central rollup for runtime-truth governance |
| `~/.dharma/state/runtime.db` | LIVE_RUNTIME_STATE | **438 MB** as of 2026-07-06 21:14 (still growing: ~100.8k session_events, ~105.7k runtime_receipts, ~31.3k idempotency_records, ~9.9k execution_identities, ~18.7k external_outcomes across 44 tables) | No VACUUM anywhere in the repo; no cron/launchd pruning job found — growth-risk framing holds even though the exact byte count drifts day to day |
| `~/.dharma/witness/` | LIVE_RUNTIME_STATE, distinct older substrate | 319 items, dated 2024, pre-dates JSON receipt convention |
| `~/.dharma/ledgers/` | LIVE_RUNTIME_STATE | 3,162 items; burst-write pattern on 2026-03-31 worth a targeted look |
| `~/.dharma/agents/{sarathi,merge_master_mike,magpie,artha_cream}/` | LIVE_RUNTIME_STATE, identity | All have `talk_receipts.jsonl`; sarathi uniquely has `holon_events.jsonl`+`compass_signals.jsonl`+doctrine files — confirms sarathi = apex/most-doctrine-heavy instance |

### 2.9 Ungoverned Scripts (`~/.dharma`)

| Location | Verdict | Evidence |
|---|---|---|
| `~/.dharma/build_loop/` (14 items) | **STALE, absent from current active portfolio — NOT "fully unowned" and NOT dormant since April** (both corrected on adversarial re-check) | `agent_loop.py` mtime is **2026-06-08 22:19:58 UTC**, not April — lands inside a ~10-15min cluster of other `.dharma` writes that day incl. a `self_improve` cycle log (`.dharma` isn't a git repo, so it's unproven whether this was a real edit or an incidental touch/scan). Has a real governance trail: paired launcher `scripts/build_loop.sh` was added in commit `95210b135` (2026-03-29), was the subject of closed-not-merged PR #142 ("archive build_loop.sh — superseded"), is referenced in `docs/state/NEXT_PHASE_MAP.md`, and is in `guardian_runtime_checks.py`'s known-top-level-dirs allowlist. Zero cron/launchd reference, zero mention in the **current** `ACTIVE_TRACK.yaml` portfolio — genuinely absent from active governance, just not an orphan nobody ever looked at |
| `~/.dharma/autonomy_spine/` (40 items) | **CANONICAL, LIVE_RUNTIME_STATE** | Backs canonical `scripts/runtime/autonomy_spine.py`; documented in ACTIVE_TRACK.yaml |
| `~/.dharma/autonomous_cleanup/` (5 items) | **DEAD/orphaned** | Apr 2026 one-off, zero live code | Low-risk, compostable |
| `~/.dharma/evolution/` (17 items, 110MB) | **CANONICAL, LIVE_RUNTIME_STATE** | DarwinEngine state, actively written today | |
| `~/.dharma/self_improve/` (2,516 items) | **LIVE_RUNTIME_STATE, CANONICAL owner in-repo** | Pure data, 0 scripts inside; owner = `self_improve.py`; per prior memory has never applied a live diff | |

### 2.10 `~/.hermes` (Third-Party + Bridge)

| Location | Verdict | Evidence |
|---|---|---|
| `~/.hermes/hermes-agent/` | **THIRD_PARTY, live executable** | Own git remote (NousResearch/hermes-agent, MIT), v0.17.0; PID 69876 confirmed running `hermes_cli/main.py gateway run`, Slack+Telegram connected; zero code-level dharma cross-contamination either direction |
| `~/.hermes/bin/{tirith,uv,uvx}` | **THIRD_PARTY** | Vendored binaries, not source |
| `~/.hermes/scripts/dharma_bridge.py` | **CANONICAL for Hermes side, HIGH RISK — adversarially CONFIRMED** | Cron `7fab4e8f09df`, hourly, enabled, 804 completed runs; `execute_assigned_tasks()` → `subprocess.run(["hermes","-z",prompt])` for any queue row addressed to hermes/hermes-m5/hermes_m5 with **zero check on sender identity or allowlist**; only guard in the file (`HERMES_DISABLE_A2A_BROADCAST`) protects the post-hoc broadcast, not execution itself; currently dormant (0 pending rows in the live queue) but structurally armed |
| `~/.hermes/scripts/a2a_dispatch.py` | **CANONICAL, LOW RISK** | Read-only classifier, writes only its own plan.json |
| `~/.hermes/scripts/hermes_a2a_server.py` | **STALE / compat shim** | Docstring confirms superseded by `dharma_swarm/a2a/executors/hermes_executor.py` |
| `~/.hermes/scripts/gepa_lite.py` + `gepa_evolution/` | **CANONICAL, CRITICAL RISK, live unguarded self-mod — adversarially CONFIRMED** | Acceptance gate is a near-always-accept in every real invocation (verified via code read + the live 2,345-entry archive: 114 real mutations attempted, 112 accepted = 98.2%); two enabled cron jobs (`f6d4fc21227a` weekly, `d416be9c51e1` nightly) invoke it bare, no `--dry-run` anywhere in any wrapper/config; 112 `.bak` files prove repeated live overwrites of production `SKILL.md` files (Apr–Jul 2026); no revert/approval workflow |
| `~/.hermes/scripts/darwin_evolve.py` + `evolution/` | **CANONICAL, SAFE (candidate-only)** | Verified: only ever writes to `candidates/`, never touches live SKILL.md |
| `~/.hermes/cron/jobs.json` | **LIVE_RUNTIME_STATE** | 60 jobs; ground truth for what's actually scheduled |
| `~/.hermes/kanban.db` | **LIVE_RUNTIME_STATE, unexamined** | Flag for a future pass |

### 2.11 Worktree/Clone Drift (corrected counts)

Full **60**-tree scan (`git worktree list`, live-counted — not "~55"): canonical `holon_bridge.py` (468L) matches only the current checkout; **49** worktrees carry a "main-ish" 204-line pre-dialogue-layer version; **6 worktrees + 1 release snapshot (7 total)** carry a "mem-ish" 397-line partial-backport version; **3 worktrees have no `holon_bridge.py` at all** (`dharma_helm_build`, `dharma_swarm_cashclaw`, `dharma_swarm_live`). 1 + 49 + 7 + 3 = 60, fully accounted for. See §9 for the condensed table.

### 2.12 Identity/State-Home Census (redone directly after the workflow's `identity_state_census` zone failed on an API error)

| Home | Count | Notes |
|---|---|---|
| `~/.dharma/agents` | 67 dirs, **only 17 with `identity.json`** (73.7% identity-less) | Canonical holon identity home per `holon_bridge.py`; contains **all four** Hermes spellings side by side: `hermes`, `hermes-m5`, `hermes_m5`, `hermes_m5_bootstrap` |
| `~/.dharma/ginko/agents` | 52 dirs | Legacy `AgentRegistry` scheme; contains **both** `jagat-kalyan` and `jagat_kalyan`, confirmed via direct read of each `identity.json` to declare **different models**: `jagat-kalyan` → `meta-llama/llama-3.3-70b-instruct`, `jagat_kalyan` → `claude-code` — same name, live fork, different agent underneath |
| `~/.dharma/external_agents` | 26 dirs | Mixed shapes |
| `~/.dharma/a2a/cards` | 49 files | **6 hyphen/underscore duplicate pairs** confirmed: `artha_cream`/`artha-cream`, `merge-master-mike`/`merge_master_mike`, `palantir-pilot`/`palantir_pilot`, `livelihood-loom-ceo`/`livelihood_loom_ceo`, `opus-forge-architect`/`opus_forge_architect`, `cybernetics_codex`/`cybernetics-codex` |
| `~/.dharma/a2a_bus/state` | 20 files | |

**None of this is source code** — every row above is `state_only`/`LIVE_RUNTIME_STATE`. It is documented here because it is exactly the "identity-only artifacts that are not a real body" the operator asked to have separated out: a directory entry here proves a name was registered, not that a holon is alive or doing work (per `AGENT_HOLON_CODE_MAP.md`'s Authority Model).

---

## 3. If You Need To Change The Body — Start Here

**Dialogue / holon identity behavior**
- Edit: `dharma_swarm/dharma_swarm/holon_bridge.py` (frontier-model dialogue routing lives ONLY here). Do not edit `holon/holon_bridge.py` (fork) or expect any worktree except the current checkout to have this layer.
- Companion: `dharma_swarm/dharma_swarm/holon_runtime.py`, `holon_compass.py`.

**Wake cycles / governed dispatch**
- Edit: `dharma_swarm/dharma_swarm/spine/invoke.py` (the one blessed dispatch path), `orchestrator.py::_run_task_via_spine`. The code is done and is already ON in the one real persistent daemon (`com.dharma.swarm`) — the remaining work is fixing the launch-spec provenance flag so governance stops calling it "unblessed," not writing new dispatch code.
- Do NOT add a second dispatch path in `agent_runner.py` — it is deliberately the leaf that spine-wrapped callers invoke into.
- Cross-check before touching: `scripts/governance/spine_dispatch_mode_report.py`, `scripts/governance/spine_bypass_report.py` (both live, both green as of this audit).

**Health / observability**
- Edit: `holon_service_liveness.py`, `holon_health.py`, `holon_canonical_state.py` for holon-specific health; `scripts/runtime/live_ops_census.py` for fleet-wide rollup.
- `holon_truth_projection.py` is built but has zero external consumers today — wire new health consumers through it rather than re-deriving reconciliation logic.
- Four separate `/health`-shaped API endpoints exist (`/api/health`, `/api/manifest/health`, `/api/verify/health`, `/a2a/health`) — don't add a 5th without consolidating.

**Model routing**
- Edit: `runtime_provider.py` (resolution), `api_keys.py` (env-var registry / `~/.dharma/agent_keys.env` load), `model_hierarchy.py` (ordering). This is the real ONE WAY.
- Never edit `holon/providers.py` expecting it to affect the canonical holon runtime.

**A2A transport**
- Edit: `dharma_swarm/a2a/a2a_server.py` (base primitives), `nats_transport.py`, `a2a_bridge.py` (the seam into `orchestrator.py`).
- CLI/worker layer: `scripts/runtime/a2a_send.py`, `a2a_inbox_bridge.py`, `a2a_domain_reply_worker.py`, `a2a_reply_capture.py` — all have real multi-file library usage despite living in `scripts/`.
- Never edit `dharma_swarm/holon_system/transport/__init__.py` expecting it to be consumed — it's a shadow re-export inside the recently-touched-but-still-unconsumed facade.

**Semantic responders / wake loops**
- Edit: `scripts/runtime/codex_composer_wake_loop.py`, `codex_composer_semantic_responder.py`, `fugu_ultra_semantic_responder.py` for live semantic-response workers.
- `scripts/allout_autopilot.py`, `scripts/composer_background_loop.py`, `scripts/strange_loop.py` back the `dgc cascade`/`dgc loops`/`dgc forge` CLI verbs directly.

**Gateway / API**
- Edit: `api/main.py` (router registration + lifespan), `api/routers/holon.py` (true agent-model chat — NOT `api/routers/agents.py`, which is cosmetic persona-wrapping), `dharma_swarm/a2a/node_gateway.py` (the cross-ecosystem A2A hub).
- Two separate auth mechanisms co-exist (`BearerAuthMiddleware` on `/api/*` vs. `node_gateway._verify_api_key` on A2A routes) — changing one does not protect the other.

**Identity naming / de-dup**
- Any fix touching duplicate/spelling-forked identities belongs in the `agent-admission-semantic-commons-2026-06` track surfaces (`scripts/governance/agent_admission.py`, `name_drift_preflight.py`, `docs/ontology/`), which are real and already catch this class of problem (~900 findings on the last live run) — do not hand-roll a second dedup mechanism.

---

## 4. Runtime State To Inspect, Never Edit Directly

| Path | What it proves |
|---|---|
| `~/.dharma/agent_keys.env` | Live provider keys/base-URLs actually loaded by `api_keys.py::bootstrap_runtime_env()` |
| `~/.dharma/a2a_bus/` (messages 4,963, inboxes 187, receipts 6-7, state 21, tasks 14) | Live A2A message/receipt/task traffic; freshest mtimes confirm it's live right now |
| `~/.dharma/a2a/` (cards 49, nodes.json, task_log.jsonl 13.6MB) | A separate live A2A state surface — dedup question vs `a2a_bus/` unresolved |
| `~/.dharma/state/runtime.db` (438MB, growing) | Backing store for `RuntimeStateStore` — the true substrate; no pruning observed |
| `~/.dharma/evolution/` (110MB, actively growing today) | DarwinEngine live mutation-proposal/archive state |
| `~/.dharma/self_improve/` (2,516 cycle files) | Proof `self_improve.py` runs cycles but per prior memory has never applied a live diff (shadow/dry-run) |
| `~/.dharma/autonomy_spine/` (40 items incl. `.runtime/runtime.db` 1.1MB) | Live state for the ARMED-BUT-INERT `autonomy_spine.py` control-tick runner |
| `~/.dharma/witness/` (319 items, dated 2024) | Older, pre-JSON contemplative log substrate — distinct lineage from current receipts |
| `~/.dharma/ledgers/` (3,162 items) | Ledger-entry history; burst-write cluster on 2026-03-31 worth investigating |
| `~/.dharma/agents/{uid}/talk_receipts.jsonl` etc. | Per-holon receipt/identity state |
| `~/.dharma/agents`, `~/.dharma/ginko/agents`, `~/.dharma/external_agents`, `~/.dharma/a2a/cards`, `~/.dharma/a2a_bus/state` | The five competing identity homes — see §2.12. Inspect only; resolve naming through `agent_admission.py`/`name_drift_preflight.py`, never by hand |
| `~/.dharma/model_routing/`, `~/.dharma/models/` | Both effectively empty — do not assume routing config lives here despite the names |
| `~/.dharma/build_loop/` | Stale but not fully orphaned autonomous-build harness logs; has real (closed) PR history — inspect only, do not re-launch without re-admitting under a current track |

---

## 5. Third-Party / Parallel Hermes Ecosystem (`~/.hermes/`)

**What it is**: a full, live, currently-running upstream checkout of NousResearch's `hermes-agent` product (v0.17.0, own git remote, MIT license) — not a stub, not config-only. Confirmed live via PID 69876 (`hermes_cli/main.py gateway run --replace`), Slack+Telegram connected as of Jul 5. Zero code-level cross-contamination with dharma_swarm in either direction — the two systems are coupled **only through a shared filesystem path**, `~/.dharma/a2a_bus/`.

**The exact live cross-system bridge files** (all under `~/.hermes/scripts/`):
- `dharma_bridge.py` — reads/writes `~/.dharma/a2a_bus/tasks/queue.jsonl` + `inboxes/`; own local state `~/.hermes/dharma_bridge/state.json`. Wired to cron job `7fab4e8f09df`, hourly, `enabled:true`, 804 completed runs.
- `a2a_dispatch.py` — reads `~/.dharma/a2a_bus/inboxes/hermes-m5/`, writes `~/.hermes/a2a_dispatch/plan.json` only. Schema-compatible with `dharma_swarm/a2a/a2a_bridge.py`'s wrapped-delivery envelope.
- `hermes_a2a_server.py` — compat shim only; real implementation moved to `dharma_swarm/dharma_swarm/a2a/executors/hermes_executor.py`.

**Explicit safety note — unguarded live self-mod paths on the Hermes side (both independently adversarially confirmed, not just discovery-reported)**:

1. **`gepa_lite.py` / `gepa_evolution/` — CRITICAL.** Hermes's equivalent of dharma_swarm's `self_improve.py`, with none of the same discipline. The acceptance gate (`child_fitness > parent_fitness + 1e-6`) is a near-always-accept whenever a real mutation is attempted — confirmed both from the code logic and empirically from the live 2,345-entry `archive.jsonl`: of 114 entries where content actually changed, 112 were accepted (98.2%). Two enabled cron jobs (`f6d4fc21227a` weekly, `d416be9c51e1` nightly) drive it directly against production `~/.hermes/skills/*/SKILL.md` with no `--dry-run` anywhere, protected only by a copy-on-write `.bak` (112 backups exist as evidence it has fired repeatedly, Apr–Jul 2026). No revert/approval workflow exists.
2. **`dharma_bridge.py`'s `execute_assigned_tasks()` — HIGH.** Confirmed exact call: `subprocess.run(["hermes", "-z", prompt], ...)` for any `queue.jsonl` row addressed to hermes/hermes-m5/hermes_m5, with zero check on the row's sender/`from` field — any writer to the 11.8MB/7,960-row shared queue can trigger autonomous execution. The only guard in the file protects the post-hoc broadcast (`HERMES_DISABLE_A2A_BROADCAST`), not execution itself. Currently dormant (0 pending rows addressed to hermes at time of check) but structurally armed, unguarded, and live-scheduled.
3. `darwin_evolve.py` (Hermes-side skill-mutation proposer) is genuinely safe — verified to only ever write to `candidates/<slug>/<timestamp>/`, never touches live `SKILL.md`.

---

## 6. Legacy Code Still Load-Bearing

| File | Lines | Real importers | Verdict |
|---|---|---|---|
| `dharma_swarm/swarm.py` | 3,306 | **28** | Heaviest legacy importer count — clearly load-bearing, not a removal candidate |
| `dharma_swarm/agent_runner.py` | 3,553 | 12 | Canonical generic-task-execution leaf under the spine |
| `dharma_swarm/agent_registry.py` | 980 | 11 | Canonical for the ginko identity scheme despite a stale mtime |
| `dharma_swarm/autonomous_agent.py` | 1,465 | 5 | Legacy but real |
| `dharma_swarm/persistent_agent.py` | 633 | 2 | Thinnest of the five but still recently touched |

---

## 7. Dangerous To Treat As Canonical

- **`holon/` (repo-root fork package, 24 files/3,318 lines)** — actively developed (commits as recent as Jul 2), its `holon_runtime.py` (391 lines) is now *larger* than the canonical one (287 lines). Its provider stack reads raw `os.environ` and has its own aliasing table — **completely bypasses `runtime_provider.py`/`api_keys.py`.** Adversarially confirmed: exactly 2 real external importers, not dead, a live quietly-diverging competitor.
- **`dharma_swarm/dharma_swarm/holon_system/` (21 files/345 lines)** — reclassify from DEAD to **STALE-but-freshly-touched**. Committed *today*, one passing test-only importer, self-declared pure facade. Someone is actively building on this branch right now — flag to operator, don't assume inert.
- **Two entirely separate agent-lifecycle surfaces**: `dgc agent {wake,talk,run,status,kill}` (→ `agent_runner.py`/`persistent_agent.py`/`swarm.py`) vs. `scripts/holon_talk.py`/`scripts/holon_run.py` (→ `holon_bridge.py`). Same-shaped commands, different runtimes, different persistence, no shared identity.
- **`api/routers/agents.py`'s `/agents/{id}/chat`** — looks like it talks to the agent's own model; actually delegates to the operator's `_agentic_stream` wearing the agent's name as a persona. Easy trap for anyone extending the dashboard.
- **Name collision: `dharma_swarm/revenue/spine.py` vs `dharma_swarm/spine/`** — unrelated systems sharing the word "spine." No real coupling today but a landmine for future greps/refactors.
- **`api/graphql/schema.py`** — dead code (0 importers), sitting next to the actually-used but misleadingly-named `graphql_router.py` (REST-shaped, not real GraphQL).
- **Three-way fork of `holon_bridge.py` across 60 worktrees** (corrected counts) — canonical (468L, current checkout only), "main-ish" (204L, 49 worktrees), "mem-ish" (397L, 6 worktrees + 1 release snapshot), plus 3 worktrees with no `holon_bridge.py` at all. None of the three cleanly supersede one another; any merge needs real conflict resolution.
- **`scripts/runtime/` Living Agent Kernel cluster** (9 files) — zero external importers, name strongly suggests an undocumented parallel to `holon_runtime.py`'s job. Not confirmed active, not confirmed dead — needs an operator decision before more logic is built near it.
- **`~/.hermes/gepa_evolution/` self-mod loop** — see §5. Treat any claim that Hermes's self-improvement is "shadow-only" as false until the cron jobs are flipped to `--dry-run` or the fitness gate is fixed. This is adversarially confirmed, not a discovery-agent guess.
- **`~/.hermes/scripts/dharma_bridge.py`'s task-execution channel** — armed, unguarded, hourly; also adversarially confirmed.
- **Five competing identity homes with two live naming forks inside them** — `~/.dharma/agents` has all four Hermes spellings side by side; `~/.dharma/ginko/agents` has `jagat-kalyan` (llama-3.3-70b) and `jagat_kalyan` (claude-code) declaring genuinely different models under near-identical names. A caller that resolves identity by simple string match can silently talk to the wrong agent.
- **`~/.dharma/build_loop/`** — not fully unowned as first believed (real PR/commit trail exists), but absent from the *current* ACTIVE_TRACK.yaml portfolio and was touched as recently as June 8 — do not assume "safe to ignore, nothing since April." Re-admit under a track or formally close out PR #142's archival intent before any re-use.

---

## 8. Scattered Scripts Needing Repo Owners

| Path | Why it's unowned (or under-owned) | Recommended action |
|---|---|---|
| `~/.dharma/build_loop/` (`agent_loop.py`, plus repo-side `scripts/build_loop.sh`) | Has real git/PR history (commit `95210b135`, closed PR #142) but is absent from the **current** ACTIVE_TRACK.yaml portfolio; touched as recently as June 8, not truly dormant | Either formally re-admit under a named track, or finish PR #142's archival intent — don't leave it in this ambiguous half-owned state |
| `~/.dharma/autonomous_cleanup/` | Zero live code, one-off from Apr 2026 | Low-risk compost candidate |
| `scripts/holon_l4_*.py` cluster (5 files) | Zero importers, no track ownership found | Ask operator: superseded, or resume? |
| `scripts/runtime/` Living Agent Kernel cluster (9 files) | Zero external importers, unclear relationship to canonical `holon_runtime.py` | Needs an explicit operator decision on identity/scope before further work |
| `scripts/runtime/codex_composer_wake_loop.py`, `autonomy_spine.py`, `merge_master_mike_daemon.py`, `capability_profile_loop.py`, `palantir_pilot_a2a_worker.py` | 0 importers each but process-critical (some mtime today) — correctly script-shaped, but living inside a directory that is functionally a second package | Consider promotion of the *library-shaped* files (`live_ops_census.py`, `pr_merge_control.py`, `a2a_send.py`, `a2a_domain_reply_worker.py`) into `dharma_swarm/dharma_swarm/`; document ownership for the standalone-process ones explicitly |
| `api/graphql/schema.py` | Zero importers, abandoned parallel to `graphql_router.py` | Delete or formally mark dead |

---

## 9. Worktree / Branch / Clone Sprawl (condensed, corrected counts)

| Worktree | Branch | `holon_bridge.py`? | Hash family | Verdict |
|---|---|---|---|---|
| `dharma_swarm` (canonical) | agent/magpie-seed | yes | CANONICAL (468L) | Production-of-record for dev |
| `dharma_swarm_main` | detached (main-ish) | yes | main-ish (204L) | Bidirectionally diverged from `agent/magpie-seed`: **84 commits ahead-on-main-only**, **47 commits ahead-on-magpie-seed-only** (re-counted; earlier figure of 44 was already 3 commits stale by the time of re-check — this number moves daily) |
| `dharma_swarm_live` (production) | organ/03-seat | **absent (0 holon*.py files anywhere, content-grep-confirmed)** | n/a | Production is genuinely clean of the holon subsystem today |
| `dharma_swarm_cashclaw` | cashclaw/revenue-hydra-v1 | absent | n/a | Unrelated feature work |
| `dharma_helm_build` | helm/worldclass-20260612 | absent | n/a | Unrelated feature work |
| `dharma_releases/af0ebc55e…` | detached, release snapshot | yes, full checkout | mem-ish (397L) | Frozen at release time |
| `dw-worktrees/mem` | stream/substrate-off-magpie | yes | mem-ish (397L) | Active, narrow-lane memory-substrate work |
| `ds_live_safety_pin_20260706`, `ds_karpathy_wiki_enforcement_seed_20260705`, `ds_forge_nvidia_foundry_mvp_20260701`, `ds_runtime_truth_nats_clean_20260701`, `dharma_swarm_local_risk_fixes` | various | yes | mem-ish (397L) | Diverged-dev, same partial-backport family (5 more, totaling 6 + the release snapshot = 7) |
| **49** remaining `ds_*`/`dw-worktrees/*`/`worktrees/*` (corrected from "~46") | various | yes | main-ish (204L) | Mirror of an old main baseline never rebased past the dialogue-layer work |
| `.claude/worktrees/langgraph-parity-verifier-20260701` | worktree-langgraph-parity | yes | main-ish (204L) | Structurally unusual: a worktree nested inside the canonical checkout's own `.claude/` dir — also the source of the runtime_state.py importer-count double-count in §2.8 |

**Bottom line**: no worktree in the 60-tree scan matches canonical exactly except the checkout itself. The dialogue-provider/frontier-routing layer is unreplicated anywhere else — merging any feature branch as-is risks silently regressing it unless git three-way-merges correctly.

---

## 10. Minimal Decision Rules

- Want to change how a holon **thinks/talks**? Edit `holon_bridge.py` + `holon_runtime.py`. Never `holon/holon_bridge.py` (fork).
- Want to change **wake/dispatch behavior**? Edit `spine/invoke.py`. The code path is done and already live in the one real running daemon — don't add a second dispatch path, and don't assume "opt-in" means "unused in production."
- Seeing `dgc agent talk` behave differently from `scripts/holon_talk.py`? Expected — two different runtimes. Pick one, don't assume parity.
- Before editing any provider/key logic, confirm you're in `runtime_provider.py`/`api_keys.py`, not `holon/providers.py` — `grep os.environ` in the file you're about to touch as a tripwire.
- Before merging any worktree/branch that touches `holon_bridge.py`, diff against the **current checkout's** version first — assume every other worktree is stale or forked, never assume "main" is ahead.
- Before trusting a "dead scaffold" or "zero importers" label in any prior doc, re-check mtime and `git log` — `holon_system/` flipped from dead to actively-committed-today between audits, and `build_loop/` flipped from "dormant since April" to "touched in June with real PR history" on the very same adversarial pass that produced this document.
- Treat `~/.hermes/scripts/gepa_lite.py` and `~/.hermes/scripts/dharma_bridge.py` as live production risk, not doctrine — one has a near-always-accept gate, the other executes untrusted queued prompts hourly with no execution kill-switch.
- Never treat `~/.dharma/` or `~/.hermes/*state*` directories as editable — inspect only.
- If a script lives in `scripts/runtime/` and has 5+ real importers, treat it as de facto package code needing a promotion decision, not a one-off script.
- Before quoting any specific count from this document (worktree counts, importer counts, DB sizes) more than a few days out, re-run the underlying command — every corrected number here was already stale-by-a-few-percent within the same session it was first measured.
- `dharma_swarm_live` (production) is holon-code-free today — don't assume prod runs any of the holon-subsystem behavior described here until it's actually deployed there.
- Don't resolve identity naming collisions (Hermes spellings, jagat-kalyan/jagat_kalyan) by hand — route through `scripts/governance/agent_admission.py` / `name_drift_preflight.py`, which already exist and already catch this class of problem.

---

## Appendix: Verification Ledger

9 highest-stakes claims from the synthesis pass were independently adversarially re-checked (each verifier told to actively try to refute, not confirm):

| # | Claim (short) | Verdict | Correction applied |
|---|---|---|---|
| 1 | Hermes `gepa_lite.py` gate is a near-always-accept, live-fired by 2 enabled cron jobs | **CONFIRMED** | None — used as stated |
| 2 | Hermes `dharma_bridge.py` shells out unallowlisted queued prompts hourly, no execution kill-switch | **CONFIRMED** | None — used as stated |
| 3 | `orchestrator.py` spine dispatch is code-gated OFF by default, daemon plist flagged "unblessed" | **CONFIRMED, with an important nuance** | Added: the one real running daemon has the flag ON right now; "unblessed" is a provenance flag, not a disabled-dispatch flag |
| 4 | `holon_system/` reclassified from dead to freshly-committed-today, one test-only importer | **CONFIRMED** | None — used as stated |
| 5 | `dharma_swarm_live` (production) has zero holon files | **CONFIRMED** (went further: confirmed via full content-grep too, not just filename glob) | None — used as stated |
| 6 | `holon/` fork's provider stack reads raw `os.environ`, 2 real external importers | **CONFIRMED** | None — used as stated |
| 7 | Three-way `holon_bridge.py` fork across ~55 worktrees, 46 main-ish, 7+1 mem-ish, 44/84 commit divergence | **REFUTED on specific counts, qualitative shape held** | Corrected throughout this doc: 60 worktrees, 49 main-ish, 6+1=7 mem-ish, 3 worktrees with no file at all (previously unmentioned), 47 (not 44) magpie-seed-only divergence |
| 8 | `runtime_state.py` has 90+ importers, `runtime.db` is 418MB, no pruning | **REFUTED on the headline numbers, growth-risk framing held** | Corrected: 55 real distinct production importers (90+ only reached by double-counting a duplicate nested worktree checkout), DB is 438MB not 418MB (stale/growing) |
| 9 | `~/.dharma/build_loop/` is fully unowned and dormant since Apr 7-11 | **REFUTED on both "unowned" and "dormant"** | Corrected: touched June 8 (coincident with a `self_improve` cycle), has real commit/PR history (`95210b135`, PR #142) — absent from the *current* active portfolio but not an untouched orphan |

**Net**: 6/9 held exactly as claimed, 3/9 needed numeric correction (applied throughout this document, not just noted here) — none of the 9 flipped from "real risk" to "non-issue" or vice versa; the corrections sharpen precision, they don't change the qualitative picture in §1 and §7.
