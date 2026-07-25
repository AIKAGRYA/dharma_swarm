# 000 Master Coherence Synthesis

> **Re-verification 2026-06-15 (perplexity-computer, Stage 1 EVIDENCE_ONLY):** This audit is 50 days old but remains the canonical source for the "~10–15% ontology-native" estimate, cited verbatim by `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/ops/AGENT_ONBOARDING.md`, and `docs/governance/ACTIVE_TRACK.yaml`. **Retained as canonical until superseded by a fresh end-to-end audit.** The runtime-truth-* tracks landed since this audit have moved the spine to 7/8 SHIPPABLE; numeric estimate likely conservative now. A new end-to-end pass is the right way to refresh — do not silently update the number here.

Date: 2026-04-26
Branch: `promote/lf5-runtime-spine`
Source reports: `10_RUNTIME_SPINE_MAP.md` through `100_DOCS_DRIFT_REGISTER.md`

## 1. Executive summary

The end-to-end audit converges on one central truth: the system already has the main canonical substrates it needs. The current failure mode is not absence of tables, routers, memories, or queues. It is incomplete wiring between existing substrates, plus stale docs that make agents rebuild things that already exist.

Slice 1 is settled in this promotion worktree. The task lifecycle now writes `session_events`, `task_claims`, and `delegation_runs` through `SessionLedger` and `RuntimeStateStore`, with temp DB tests proving row counts and idempotence.

The next promotion work should avoid broad restores and new organs. The immediate path is:

1. Wire remaining structured producers into existing `RuntimeStateStore` tables.
2. Add a `LEDGER_WATCHER` to Guardian so empty structured tables cannot silently recur.
3. Unify identity and routing through existing runtime contracts before touching dashboard or autonomous-agent surfaces.

## 2. Settled truths

1. `RuntimeStateStore` is the canonical structured runtime state store.
2. `SessionLedger` JSONL remains the canonical append-only session trace.
3. `RuntimeStateStore.session_events` is the searchable index of `SessionLedger`, not a replacement trace.
4. `TaskBoard` is the task queue and status FSM, not a duplicate runtime ledger.
5. Slice 1 producer wiring exists for `task_claims`, `delegation_runs`, and `session_events`.
6. `RuntimeStateStore.record_task_claim()` and `record_delegation_run()` already exist and should be reused.
7. `RuntimeStateStore` already has writer methods for artifacts, memory facts, context bundles, and operator actions.
8. `RuntimeTelemetryProjector` is the existing bridge from runtime rows into telemetry read models.
9. `AgentConfig` is the current runtime constructor identity model in code.
10. `AgentState` is runtime status, not canonical identity.
11. There are multiple identity-shaped classes today; the unification doc is aspirational, not implemented truth.
12. `model_hierarchy.py`, `runtime_provider.py`, and `providers.ModelRouter` are the existing routing hierarchy.
13. `RoutingMemoryStore` is the existing learned routing memory substrate.
14. Dashboard chat currently has a separate per-request provider path and does not share swarm routing memory.
15. `pending_proposals.py` is the existing Shakti-to-Darwin queue substrate.
16. Shakti escalation is partly implemented through `orchestrate_live._enqueue_shakti_escalations()`.
17. The main evolution loop appears to log loaded pending proposals without visibly merging them into `auto_evolve()`.
18. Guardian does not yet inspect structured runtime row counts.
19. Dashboard/API health can look green without directly exposing `task_claims` or `delegation_runs`.
20. Docs are advisory; current code plus tests are the runtime truth.

## 3. Top 20 unresolved coherence gaps

1. Completed tasks do not yet prove `artifact_records` are created from `_persist_result()`.
2. Completed tasks do not yet prove `memory_facts` are produced from execution outcomes.
3. No read-before-propose test requires agents to consult `session_events` or `memory_facts`.
4. Guardian has no `LEDGER_WATCHER` for `session_events > 100` with empty `task_claims`.
5. Guardian has no stronger blocker threshold for `session_events > 1000` with empty `task_claims`.
6. Dashboard/API tests do not prove claim/run rows from dispatch are visible to operators.
7. Telemetry projection is not tested immediately after a real orchestrator dispatch.
8. API task status and runtime claim/run status are not cross-checked for the same task.
9. Dashboard chat routing bypasses shared `ModelRouter` and `RoutingMemoryStore`.
10. `AutonomousAgent` still bypasses shared model routing and circuit breakers.
11. Conductors use fallback behavior but still hardcode model names and bypass the full hierarchy.
12. Identity has at least five identity-shaped surfaces with no duplicate-class guard test.
13. `AgentProfile` is not proven to be an alias or projection of the canonical runtime identity.
14. `agent_registry.AgentIdentity` and GraphQL/API identity DTOs remain separate from live swarm identity.
15. Shakti pending proposals are not proven to flow through `append_pending_proposals()` into `DarwinEngine.load_pending_proposals()` and `run_cycle()`.
16. Shakti escalations are not proven to become archived Darwin results.
17. `CYBERNETIC_LOOP_MAP.md` is stale for Slice 1 bootstrap runtime truth.
18. `MODEL_ROUTING_MAP.md` is partially stale for conductor fallback behavior.
19. `AGENT_IDENTITY_UNIFICATION.md` names a desired canonical `AgentIdentity`, while code names `AgentConfig` canonical.
20. Governance has no automated check that slice diffs exclude quarantined LF5-only modules.

## 4. Gaps grouped by slice

### Slice 2 structured producers

- Wire `Orchestrator._persist_result()` to existing `RuntimeStateStore.record_artifact()`.
- Add a bootstrap acceptance test asserting `artifact_records > 0` after a completed task.
- Decide the smallest memory producer: direct `memory_facts` from task outcome, or explicit context/read-before-propose guard first.
- Add a test proving a proposal path reads at least one `session_events` or `memory_facts` source before proposing.
- Keep `SessionLedger` behavior unchanged; do not add another event ledger.
- Optionally add a public `SessionLedger.runtime_state` accessor to remove private `_runtime_state` coupling.

### Slice 3 LEDGER_WATCHER

- Add `run_ledger_watcher(state_dir)` to Guardian.
- Read canonical `RuntimeStateStore` row counts from a temp or configured state dir.
- Emit DEGRADED when `session_events > 100 and task_claims == 0`.
- Emit BLOCKER when `session_events > 1000 and task_claims == 0`.
- Add tests with temp `runtime.db`; no `~/.dharma` access.
- Do not mark Guardian complete until structured row-count checks exist.

### Slice 4 identity/routing

- Choose the migration truth: keep `AgentConfig` as canonical or rename through a tested migration.
- Add a duplicate identity class guard test.
- Migrate `AutonomousAgent` and `AgentProfile` only after runtime-spine producer tests are stable.
- Route `AutonomousAgent` through `runtime_provider` and shared routing policy instead of local direct-provider construction.
- Add a shared routing-memory contract test.
- Do not rebuild provider hierarchy; use `model_hierarchy.py`, `runtime_provider.py`, `ModelRouter`, and `RoutingMemoryStore`.

### Slice 5 Shakti/Darwin

- Add a direct test for `orchestrate_live._enqueue_shakti_escalations(..., proposals_path=tmp_path)`.
- Add an integration test for pending proposal JSONL -> `DarwinEngine.load_pending_proposals()` -> `run_cycle()` in shadow mode.
- Prove the main evolution loop consumes loaded pending proposals, not just logs them.
- Require Darwin proposals to cite runtime facts/events once Slice 2 memory producers exist.
- Record Darwin outputs as artifact/run results through existing runtime substrates.

### Slice 6 dashboard/API

- Expose claim/run counts by session through an existing telemetry projection or a narrow runtime-spine API read surface.
- Add an API/dashboard test that creates temp runtime rows, projects telemetry, and asserts visible claim/run counts.
- Add a test asserting API task state agrees with runtime claim/run state for the same task.
- Decide whether `api/routers/viz.py` is intended to be promoted; register only if it is real product surface.
- Keep dashboard promotion behind runtime-spine stability so health views cannot mask empty structured tables.

### Slice 7 docs/PKM

- Update `CYBERNETIC_LOOP_MAP.md` to distinguish Slice 1 bootstrap truth from full live LLM truth.
- Update `MODEL_ROUTING_MAP.md` for conductor fallback behavior and remaining hierarchy bypass.
- Update `AGENT_IDENTITY_UNIFICATION.md` to acknowledge `AgentConfig` as current code truth, or document a tested rename.
- Replace `make compile` references with `python -m compileall dharma_swarm tests` or add a real Make target.
- Add a small drift check for missing Make targets and stale canonical model names.

## 5. Top 10 do not build new, wire existing findings

1. Do not build a new work ledger. Use `RuntimeStateStore` plus `SessionLedger`.
2. Do not build a new event ledger. Index `SessionLedger` into `session_events`.
3. Do not build a new artifact registry. Use `RuntimeStateStore.artifact_records` and existing artifact store paths.
4. Do not build a new fact memory store for runtime truth. Use `RuntimeStateStore.memory_facts`.
5. Do not build a new context bundle table. Use `RuntimeStateStore.context_bundles`.
6. Do not build a new provider hierarchy. Use `model_hierarchy.py`, `runtime_provider.py`, and `ModelRouter`.
7. Do not build a new routing memory. Use `RoutingMemoryStore`.
8. Do not build a new Shakti/Darwin queue. Use `pending_proposals.py`.
9. Do not build another telemetry read model. Use `RuntimeTelemetryProjector` and `TelemetryPlaneStore`.
10. Do not promote a new identity schema by documentation alone. First reconcile with `AgentConfig` and existing runtime/API/profile identities.

## 6. Which existing substrates are canonical

| Concern | Canonical substrate |
|---|---|
| Task queue and task FSM | `dharma_swarm/task_board.py`, `TaskBoard.tasks` |
| Structured runtime lifecycle | `dharma_swarm/runtime_state.py`, `RuntimeStateStore` |
| Claims and runs | `task_claims`, `delegation_runs` |
| Session trace | `dharma_swarm/session_ledger.py`, JSONL ledgers |
| Searchable session events | `RuntimeStateStore.session_events` and FTS |
| Runtime artifacts | `RuntimeStateStore.artifact_records`, existing artifact store helpers |
| Runtime facts | `RuntimeStateStore.memory_facts` |
| Context bundles | `RuntimeStateStore.context_bundles` |
| Operator actions | `RuntimeStateStore.operator_actions` |
| Telemetry projection | `RuntimeTelemetryProjector`, `TelemetryPlaneStore` |
| Runtime agent constructor identity | `models.AgentConfig` |
| Runtime agent status | `models.AgentState` |
| Provider hierarchy | `model_hierarchy.py` |
| Provider construction | `runtime_provider.py` |
| Swarm routing | `providers.ModelRouter` |
| Learned route performance | `routing_memory.RoutingMemoryStore` |
| Stigmergy salience | `StigmergyStore` |
| Concept/object graph | `OntologyRegistry`, `ontology_runtime`, `GraphNexus` |
| Shakti/Darwin queue | `pending_proposals.py` |
| Darwin proposal/archive mechanics | `DarwinEngine` |
| Promotion discipline | `03_MATRIX_REVIEW.md`, `05_SLICE1_REVIEW.md`, this synthesis |

## 7. Which duplicate substrates should be quarantined

1. LF5-only governance modules absent from promotion baseline: `build_registry.py`, `build_authority.py`, `task_contract.py`, `task_board_mirror.py`, `frontier_council.py`, `ontology_context.py`.
2. Any registry that writes a parallel JSONL task/build ledger instead of projecting from `RuntimeStateStore`.
3. Any new session/event log that duplicates `SessionLedger` plus `session_events`.
4. Any new provider router that bypasses `ModelRouter`, `runtime_provider`, and `model_hierarchy.py`.
5. Any dashboard-only identity source that becomes authoritative over `AgentConfig` or live swarm state.
6. `autonomous_agent.AgentIdentity`, `profiles.AgentProfile`, `agent_registry.AgentIdentity`, and GraphQL `AgentIdentity` should be treated as migration surfaces until Slice 4 resolves ownership.
7. Any new Shakti queue that bypasses `pending_proposals.py`.
8. Any Guardian report path that is considered fresh without being generated from current state.
9. Any API/dashboard runtime health surface that claims lifecycle health without claim/run visibility.
10. Docs that name intended architecture as implemented truth without matching tests.

## 8. Immediate next 3 commits

1. `slice2-artifact-producer`
   - Patch only the completed-task result path.
   - Wire `_persist_result()` or the smallest adjacent completion path to `RuntimeStateStore.record_artifact()`.
   - Add a temp DB test asserting `artifact_records > 0` after execution and no duplicate artifact row on a second tick.

2. `slice2-memory-read-before-propose`
   - Add the smallest read-before-propose guard using `session_events` and/or `memory_facts`.
   - Add a test that fails if a proposal path has no runtime source citation.
   - Do not introduce a new memory substrate.

3. `slice3-ledger-watcher`
   - Add Guardian `LEDGER_WATCHER` against temp `runtime.db`.
   - Test DEGRADED and BLOCKER thresholds for empty structured rows.
   - Keep it read-only and independent of live `~/.dharma`.

## 9. Post-NeurIPS backlog

1. Full identity migration: reconcile `AgentConfig`, autonomous-agent identity, profiles, registry identity, and API DTOs.
2. Shared routing memory across dashboard chat, autonomous agents, conductors, and swarm `AgentRunner`.
3. Conductor model routing through the free/cheap/provider hierarchy.
4. Shakti/Darwin main-loop pending-proposal consumption and archive proof.
5. Darwin proposals citing runtime facts/events before evaluation.
6. Training flywheel ingestion from real delegation and artifact rows.
7. Recognition/strange-loop seed generation from real loop history.
8. Dashboard runtime table panels for claims, runs, artifacts, and facts.
9. Docs drift automation for Make targets, canonical identity names, and loop status claims.
10. Governance manifest check that blocks quarantined LF5-only modules from accidental slice promotion.

## 10. Exact files to inspect next

Slice 2 structured producers:

- `dharma_swarm/orchestrator.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/artifact_store.py`
- `dharma_swarm/runtime_artifacts.py`
- `dharma_swarm/context_compiler.py`
- `tests/test_bootstrap_loops.py`
- `tests/test_runtime_state.py`
- `tests/test_context_compiler_vnext.py`
- `tests/test_runtime_artifacts.py`

Slice 3 LEDGER_WATCHER:

- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/monitor.py`
- `dharma_swarm/doctor.py`
- `tests/test_loop_supervisor.py`
- `tests/test_runtime_telemetry_projector.py`
- new `tests/test_guardian_crew.py` if absent

Slice 4 identity/routing:

- `dharma_swarm/models.py`
- `dharma_swarm/autonomous_agent.py`
- `dharma_swarm/persistent_agent.py`
- `dharma_swarm/profiles.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/providers.py`
- `dharma_swarm/runtime_provider.py`
- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/routing_memory.py`
- `dharma_swarm/conductors.py`
- `api/routers/chat.py`
- `api/routers/agents.py`
- `api/routers/graphql_router.py`
- `tests/test_agent_runner_routing_feedback.py`
- `tests/test_model_router_routing_memory.py`
- `tests/test_dashboard_chat_router.py`

Slice 5 Shakti/Darwin:

- `dharma_swarm/shakti.py`
- `dharma_swarm/stigmergy.py`
- `dharma_swarm/pending_proposals.py`
- `dharma_swarm/evolution.py`
- `dharma_swarm/orchestrate_live.py`
- `tests/test_shakti.py`
- `tests/test_shakti_darwin_integration.py`
- `tests/test_evolution.py`

Slice 6 dashboard/API:

- `api/main.py`
- `api/routers/telemetry.py`
- `api/routers/commands.py`
- `api/routers/agents.py`
- `api/routers/chat.py`
- `api/routers/viz.py`
- `dharma_swarm/runtime_telemetry_projector.py`
- `dharma_swarm/telemetry_plane.py`
- `dashboard/src/lib/runtimeControlPlane.test.ts`
- `dashboard/src/lib/api.test.ts`
- `tests/test_api.py`
- `tests/test_runtime_telemetry_projector.py`

Slice 7 docs/PKM:

- `CYBERNETIC_LOOP_MAP.md`
- `INTERFACE_MISMATCH_MAP.md`
- `MODEL_ROUTING_MAP.md`
- `AGENT_IDENTITY_UNIFICATION.md`
- `LIVING_LAYERS.md`
- `README.md`
- `CLAUDE.md`
- `Makefile`
- `pyproject.toml`
- `docs/architecture/NAVIGATION.md`
