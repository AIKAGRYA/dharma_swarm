# Palantir-Grade Semantic Ontology Roadmap for dharma_swarm

Generated: 2026-06-16 Asia/Tokyo

Operator: John Shrader (`@AmitabhainArunachala`)

Routing path: Codex -> `dharma.a2a.palantir-pilot` -> six read-only explorer lanes -> Codex integration

A2A packet: `reports/a2a/operator_packets/20260615T161711Z-palantir-specialist-ontology-roadmap.md`

A2A send receipt: `reports/a2a/send_receipts/20260615T161835Z-palantir-pilot-f6eb860d656f.json`

A2A worker answer artifact: `/Users/dhyana/.dharma/a2a_bus/outboxes/palantir-pilot/f6eb860d656f-answer.json`

Palantir Pilot boundary: public-source workspace synthesis only; no official Palantir affiliation, no private tenant access, no Learn/course scraping claim, no repo write authority.

Palantir Pilot engine: `palantir_pilot.local_public_source_query`.

Palantir Pilot registration boundary in reply: `external_worker_evidence_only`, `public_source_only=true`, `official_affiliation=false`, `private_palantir_access=false`, `peer_model_processed_claim=false`.

Six-agent evidence:

- Governance lane: replacement explorer `019ecc1d-f5d1-7443-933f-ab513b101458`.
- Runtime record vocabulary: explorer `019ecc11-ce28-7fe0-be1e-dd083a87661e`.
- Ontology module surface: explorer `019ecc11-eab0-76f2-a82f-709ba8046e3d`.
- Operator Brief action seam: explorer `019ecc12-08d2-7010-95c0-000f84cb446a`.
- Guardian and policy surface: explorer `019ecc12-27ec-77c0-ad58-f4a52cdde643`.
- `world_radar` duplication: explorer `019ecc12-5f33-79b2-8639-d1eae8055c15`.

One original governance explorer timed out and was shut down. The replacement explorer completed the same slice with a tighter read-only brief.

## Section 0 - Triple-check log

- Confirmed: the repo has a substrate-nativeness baseline estimate of `~10-15% native today; target 30%+`; the `30%+` number is target, not current. Evidence: `docs/governance/ACTIVE_TRACK.yaml:63`.

- Changed: the prompt's HEAD `9c76b210` does not match this checkout. `make onboard` reported branch `telos-ai-seed-v0-from-sandbox`, HEAD `cc9c05f212`, ahead 5 and behind 3.

- Changed: the prompt's "15 active lanes" snapshot is stale for this checkout. `make onboard` reported 11 active tracks, and `ACTIVE_TRACK.yaml` has `track_policy.max_active: 11`.

- Changed: substrate-nativeness is not represented by only the lanes listed in the prompt. Replacement explorer counted 9 active substrate-nativeness lanes.

- Confirmed: relevant active substrate lanes include `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `loop-closure-2026-06`, `orientation-graph-2026-06`, `composer-holon-spine-longrun-2026-06`, `agent-admission-semantic-commons-2026-06`, `helm-worldclass-terminal-2026-06`, and `a2a-cloud-agent-bridge-2026-06`.

- Changed: `runtime-truth-spine-adoption-2026-06` is currently SHIPPABLE in `make onboard`, not 7/8. The older regex-fix note has been superseded.

- Confirmed: `loop-closure-2026-06` remains 3/5 in `make onboard`, missing `reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md` and `reports/loop_closure/RETROSPECTIVE.md`.

- Confirmed: `agent-admission-semantic-commons-2026-06` exists and is the natural lane for semantic commons, canonical object index, alias index, and agent admission work.

- Confirmed: a new lane is not needed for Phase 0 because the active portfolio is already at max active and the relevant lane exists.

- Confirmed: current open/partial Broken Register entries are `BR-003`, `BR-004`, `BR-005`, `BR-013`, and `BR-014`.

- Confirmed: `BR-012` is fixed as of 2026-05-20; do not use it as an open loop-map blocker.

- Confirmed: `BR-003` remains partial and is the live-apply/write-back safety debt.

- Confirmed: `BR-004` remains partial and is cron repo/live split-brain debt.

- Confirmed: `BR-005` remains partial and is algedonic consumer-policy debt.

- Confirmed: `BR-013` remains partial and is agent-contract fragmentation debt.

- Confirmed: `BR-014` remains open and is the `BHED_GNAN` no-op gate debt.

- Changed: the prompt path `docs/state/CYBERNETIC_LOOP_MAP.md` is stale. The current map is at `CYBERNETIC_LOOP_MAP.md`; an ingested copy also exists under `docs/sovereign_holons/ingested/qwen/`.

- Confirmed: `CYBERNETIC_LOOP_MAP.md` says 0 loops fully closed in production, 1 closed in test context, 7 partial, and 5 no.

- Confirmed: Loop 1 remains NO in `CYBERNETIC_LOOP_MAP.md`; production loop closure should not be claimed.

- Confirmed: ADR-008 exists at `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`.

- Confirmed: ADR-008 status is PROPOSED, awaiting operator ratification; it should be used as proposed discipline, not ratified doctrine.

- Confirmed: ADR-008 chooses `api_name = dharma.<domain>.<TypeName>` with no `.v<N>` suffix, version in `ObjectType.version:int`, and `TypeStatus` lifecycle.

- Confirmed: object-type casing is PascalCase for ObjectType `api_name`; property/action/function casing uses camelCase or lowerCamelCase per ADR-008.

- Confirmed: `dharma_swarm/runtime_state.py` class lines are `SessionState:483`, `TaskClaim:495`, `DelegationRun:511`, `WorkspaceLease:529`, `ArtifactRecord:542`, `MemoryFact:559`, `MemoryEdge:578`, `ContextBundleRecord:590`, `OperatorAction:605`, `SessionEventRecord:618`, `RuntimeReceipt:633`, `IdempotencyRecord:651`, `RuntimeStateStore:1185`.

- Changed: `runtime_state.py` is 4,152 lines in this checkout, not the prompt's 3,797-line snapshot.

- Confirmed: `ArtifactRecord`, `MemoryFact`, `MemoryEdge`, `OperatorAction`, `SessionEventRecord`, `RuntimeReceipt`, and `IdempotencyRecord` are Palantir-shaped primitives already in code.

- Confirmed: `MemoryEdge` has `record_memory_edge()` at `runtime_state.py:3949`, but explorer evidence found no direct read/list test or `_row_to_memory_edge` path.

- Confirmed: `operator_actions` table and `record_operator_action()` exist in `runtime_state.py`, with `list_operator_actions()` following it.

- Confirmed: `runtime_receipts` and `record_runtime_receipt()` are mature and already used by idempotency and A2A paths.

- Confirmed: the ontology surface is `api/routers/ontology.py` plus six files under `dharma_swarm/ontology*.py`: `ontology.py`, `ontology_adapters.py`, `ontology_agents.py`, `ontology_hub.py`, `ontology_query.py`, `ontology_runtime.py`.

- Confirmed: `ontology.py` is 2,424 lines and mixes schema models, registry, validation, action execution, domain type catalog, and legacy `Entity/ONTOLOGY` API.

- Confirmed: `ontology_hub.py` is the SQLite-backed persistence layer.

- Confirmed: `ontology_runtime.py` is the shared runtime singleton/path/legacy-import facade.

- Confirmed: `ontology_query.py` is graph traversal/search/stats, but it reads registry internals.

- Confirmed: `ontology_adapters.py` bridges subsystem data into ontology objects.

- Confirmed: `ontology_agents.py` projects runtime agents into `AgentIdentity`.

- Confirmed: `api/routers/ontology.py` is a read-only browser API over the shared registry, but it carries router-owned type categories.

- Confirmed: `OntologyRegistry`, `get_shared_registry`, and `persist_shared_registry` are high-blast-radius surfaces. Do not casually rename or move them.

- Confirmed: `execute_action()` is the ontology action chokepoint with telos gates, approval checks, mutation, and conditional runtime receipts.

- Confirmed: `operator_brief` has six source files and is recorded as shipped under `operator-brief-seam-2026-04`.

- Confirmed: `operator-brief-seam-2026-04` is a closed/shipped track, not current active work.

- Confirmed: `operator_brief` currently writes ontology objects and `ArtifactRecord`, but does not directly write `OperatorAction` or `RuntimeReceipt`.

- Confirmed: `operator_brief` emits `ActionProposal`, `WitnessLog`, `GateDecisionRecord`, `Outcome`, `ValueEvent`, and `Contribution`.

- Confirmed: `operator_brief/persistence.py` writes lineage frontmatter and a runtime `ArtifactRecord` with trace, proposal, source, gate, and witness metadata.

- Confirmed: `guardian_crew.py` has `LEDGER_WATCHER` and tests; the older audit note saying Guardian has no `LEDGER_WATCHER` is superseded.

- Confirmed: `LEDGER_WATCHER` is read-only observation, not ACL enforcement.

- Confirmed: `operator_brief/watchdog.py` adds `operator_brief` empty-output and trace-coverage checks.

- Confirmed: `check_control_surface_envelope_degraded()` exists but explorer search found no call site; treat it as dormant projection hook unless wired.

- Confirmed: `dharma_swarm/world_radar/` is the active runtime package for Go scout/ingestor, analysis, R&D artifacts, CLI, and IO helpers.

- Confirmed: `dharma_swarm/operator_core/world_radar/` is receipt projection only, with `GoWorldReceipt` and projection helpers.

- Confirmed: there is little duplicated implementation between the two `world_radar` trees; the real failure is namespace/name duplication.

- Confirmed: top-level `world_radar` should be the long-term namespace owner.

- Confirmed: `operator_core` should own control-surface row assembly, not a second `world_radar` package namespace.

- Confirmed: Palantir Pilot A2A reply used public URL metadata and local wiki notes only. It cited local Palantir Pilot notes and public Foundry/Defense OSDK URL metadata.

- Confirmed: the A2A reply was `PALANTIR_PILOT_REPLIED`, `ack_tier=HANDLER_ACKED`, `replied=true`, `semantic_reply_claim=true`, `peer_model_processed_claim=false`.

## Section 1 - Palantir-grade target state in dharma_swarm vocabulary

Palantir-grade semantic ontology for `dharma_swarm` means the existing runtime records, ontology objects, actions, receipts, policies, and lineage paths are made explicit, typed, queryable, receipted, and governed without inventing parallel vocabulary.

It does not mean cloning Foundry or Gotham.

It does not mean replacing `runtime_state.py`.

It does not mean creating a new `OntologyManager`.

It does not mean changing a shipped name because it sounds more Palantir-like.

It means:

- Every important thing is an `ObjectType` or an existing runtime record.
- Every meaningful relation is a `LinkType` or an existing relation field such as `MemoryEdge`.
- Every write is an `ActionType` or an existing `OperatorAction` / `ActionProposal` / `ActionDef`.
- Every write-back has an idempotency key and a `RuntimeReceipt`.
- Every derived artifact carries lineage through `trace_id`, `correlation_id`, `causation_id`, `parent_artifact_id`, source IDs, and receipts.
- Every public contract follows ADR-008 grammar until operator ratifies or changes it.
- Every phase leaves compatibility shims for existing imports and data.
- Every phase proves itself with tests, receipts, and lane evidence.

### Target mapping table

| Palantir primitive | dharma_swarm current | Gap |
|---|---|---|
| ObjectType | `ObjectType` in `ontology.py:202`; runtime records in `runtime_state.py:483-651` | Runtime records are not yet documented as the canonical object vocabulary. |
| ObjectType | `ArtifactRecord` | Good object primitive; strengthen query and lineage contracts. |
| ObjectType | `MemoryFact` | Good fact primitive; needs graph relation coverage through `MemoryEdge`. |
| ObjectType | `SessionState` | Good session primitive; needs explicit mapping doc and lifecycle tests. |
| ObjectType | `TaskClaim` | Good claim primitive; already central to runtime truth and Guardian checks. |
| ObjectType | `DelegationRun` | Good execution primitive; link to `TaskClaim`, `ArtifactRecord`, and `RuntimeReceipt`. |
| ObjectType | `WorkspaceLease` | Good branch/write-lock primitive; needs lifecycle coverage. |
| ObjectType | `ContextBundleRecord` | Good context snapshot primitive; policy surface should fail closed before selected writes. |
| ObjectType | `SessionEventRecord` | Good event-stream primitive; needs relation to structured rows preserved. |
| ObjectType | `RuntimeReceipt` | Good audit primitive; use it for every write-back phase. |
| ObjectType | `IdempotencyRecord` | Good exactly-once primitive; should be required for all Palantir-grade write-back paths. |
| LinkType | `MemoryEdge` | Exists but needs read/list path and explicit tests. |
| LinkType | `LinkDef` / `Link` in `ontology.py` | Good ontology link layer; private registry access should be contained. |
| LinkType | fields such as `parent_artifact_id`, `source_event_id`, `source_artifact_id`, `result_receipt_id`, `claim_id`, `run_id` | These are implicit links; roadmap should document and test them before adding graph UI. |
| ActionType | `ActionDef` in `ontology.py` | Exists; `execute_action()` is the chokepoint. |
| ActionType | `OperatorAction` in `runtime_state.py:605` | Exists; `operator_brief` should start using or associating it. |
| ActionType | `ActionProposal` ontology object | Already used by `operator_brief`; needs join to `OperatorAction` and `RuntimeReceipt`. |
| Function | Deterministic modules such as `world_radar.analysis`, `operator_core.runtime_truth`, `ontology_query`, `lineage.py` | Need boundary rule: deterministic transformations are Functions; agents are not Functions. |
| Code Workbook | Existing tests, specs, scripts, and replay commands | Introduce Palantir term only if needed; for now use "test/replay packet" and defer naming to `NAMING_CANON.md`. |
| Pipeline | `cron_runner`, `orchestrate_live`, `world_radar/go_bridge.py`, `operator_brief.run_once()` | Pipelines exist but need end-to-end receipts and active loop closure. |
| Branch | `WorkspaceLease`, git branches, worktrees, idempotency records | Introduce Palantir term `Branch` only as a definition for isolated candidate state; implementation should use existing `WorkspaceLease`. |
| Permission | `guardian_crew.py`, `guardian_runtime_checks.py`, `SecurityPolicy`, gate decisions | Observation exists; enforcement is partial and should not be overclaimed. |
| Write-back | `RuntimeStateStore`, `execute_action()`, `record_runtime_receipt()`, `IdempotencyRecord` | Mature pieces exist; not every write path uses them. |
| Lineage | `RuntimeReceipt`, `ArtifactRecord`, `trace_id`, `correlation_id`, `causation_id`, `parent_artifact_id`, source IDs | No new lineage module required for Phase 0-2; add tests and mapping first. |

### Definitions introduced directly from Palantir vocabulary

- ObjectType: a stable typed thing in the ontology, either an `ObjectType` in `ontology.py` or a canonical runtime record class in `runtime_state.py`.

- LinkType: a stable typed relation between ObjectTypes, represented today by `LinkDef` / `Link` or by `MemoryEdge` and explicit runtime foreign-key-like fields.

- ActionType: a stable typed operation that changes or proposes to change state, represented today by `ActionDef`, `ActionProposal`, and `OperatorAction`.

- Function: a deterministic transformation whose output can be replayed from declared inputs; agents are not Functions.

- Branch: an isolated candidate state or work context; implementation should use existing git/worktree and `WorkspaceLease` surfaces, not a new store.

All other ambiguous terms should be `naming TBD by NAMING_CANON.md`.

## Section 2 - Phased roadmap

### Phase 0 - Freeze the vocabulary and publish the execution map

Scope:

- Do this this week.
- Make no behavior change.
- Do not edit protected governance files.
- Do not open a new active track.
- Use `agent-admission-semantic-commons-2026-06` and `runtime-truth-reconciliation-2026-06`.
- Produce one small proposed ADR or report that maps existing records to ObjectType, LinkType, ActionType, Function, Branch, Permission, Write-back, and Lineage.
- Treat ADR-008 as proposed discipline, not ratified doctrine.
- Record that `CYBERNETIC_LOOP_MAP.md` is root-level, not `docs/state/`.
- Record that current native baseline is `~10-15%`, target `30%+`.
- Record A2A Palantir Pilot boundaries and citations.

What does not change:

- No `ACTIVE_TRACK.yaml` mutation by Stage-1 agents.
- No `runtime_state.py` code change.
- No ontology code split.
- No `world_radar` move.
- No Guardian enforcement change.
- No `NAMING_CANON.md` duplication.

Acceptance criteria:

- `make onboard` was run and receipt path noted.
- Prompt-mandated shell checks are captured.
- A2A send receipt has `PALANTIR_PILOT_REPLIED` and `HANDLER_ACKED`.
- Roadmap names only existing repo terms or direct Palantir terms.
- `rg -n "OntologyManager|BaseObject|Dharma Radar v0 as new store" <new-file>` returns no implementation recommendation.
- `rg -n "ObjectType|LinkType|ActionType" <new-file>` shows explicit definitions.
- `python3 scripts/governance/check_track_status.py` passes or any failure is recorded exactly.

Blast radius:

- Documentation/report only.
- Recommended file path: `docs/architecture/ADRs/ADR-009-palantir-grade-ontology-kernel.md` or `reports/architectural/...`.
- No runtime impact.
- Migration cost is zero.

Evidence to produce:

- This report.
- A short ADR if the operator wants a canonical architecture decision.
- A machine-readable appendix in a later commit can become `docs/ontology/semantic_objects.yaml`, but Phase 0 does not require it.
- A receipt pointing to A2A send receipt and six-agent summaries.

Exit criterion:

- The operator can point future agents at one file and say: use these names, do not mint synonyms.
- The file states no new lane is needed.
- The file identifies the first code phase as runtime record/link tests, not a rewrite.

Dependency rationale:

- Palantir adoption starts by agreeing what the objects and actions are.
- If names are not frozen first, every later phase amplifies drift.
- This phase prevents the exact failure mode the prompt identifies.

Active lanes served:

- `agent-admission-semantic-commons-2026-06`
- `runtime-truth-reconciliation-2026-06`
- `orientation-graph-2026-06`

BR entries addressed or unblocked:

- Addresses `BR-013` by reducing agent-contract ambiguity.
- Unblocks `BR-005` by naming policy/consumer gaps precisely.
- Avoids worsening `BR-003` by not touching write-back.

Top-5 ROI moves subsumed:

- Subsumes architecture-decision issue.
- Subsumes BR re-verification for the ontology roadmap slice.

### Phase 1 - Make runtime records queryable as the first ontology spine

Scope:

- Treat `runtime_state.py:483-651` as the first canonical object vocabulary.
- Add tests before behavior changes.
- Add read/list coverage for `MemoryEdge` if missing.
- Add a mapping contract test that only allows `ObjectType`, `LinkType`, `ActionType`, and `Dataset` as mapping values.
- Add link-integrity tests across `SessionState`, `TaskClaim`, `DelegationRun`, `ArtifactRecord`, `RuntimeReceipt`, and `IdempotencyRecord`.
- Add `WorkspaceLease` lifecycle coverage if missing.
- Do not rename record classes.
- Do not introduce a `BaseObject` class.
- Do not move `runtime_state.py` tables.

What changes:

- Tests under `tests/test_runtime_state.py` or a narrow new test file.
- Possibly a minimal `list_memory_edges()` / row mapper if needed to make `MemoryEdge` usable.
- Documentation comments only if needed to orient future readers.

What does not change:

- No schema replacement.
- No new database.
- No `ArtifactRecord` replacement.
- No `MemoryEdge` rename.
- No graph UI.

Acceptance criteria:

- `pytest -q tests/test_runtime_state.py tests/test_runtime_state_invariants.py` passes.
- New test proves `MemoryEdge` can be persisted and read back.
- New test proves a full runtime chain can be joined by existing IDs.
- New test proves `WorkspaceLease.holder_run_id` remains linked to a `DelegationRun`.
- No direct write path loses `trace_id` / `correlation_id` / `side_effect_key`.

Blast radius:

- `dharma_swarm/runtime_state.py` if a missing read method is added.
- `tests/test_runtime_state.py` or adjacent tests.
- Low to medium if only adding read methods and tests.
- High if changing schema; do not do that in this phase.

Evidence to produce:

- Test output.
- A short receipt under `reports/architectural/` or `reports/runtime_truth/`.
- Optional object mapping table in `docs/ontology/semantic_objects.yaml` under the existing active lane, if the operator authorizes docs/ontology additions.

Exit criterion:

- Runtime records can be cited as the first Palantir-grade object vocabulary without caveat.
- `MemoryEdge` is no longer a write-only link primitive.
- Agents have a deterministic test target before touching Operator Brief or ontology action paths.

Dependency rationale:

- Palantir-grade ontology depends on object and link primitives before action surfaces.
- `RuntimeReceipt` and `IdempotencyRecord` are the write-back backbone.
- Do this before Operator Brief hardening so Action receipts can join to tested objects.

Active lanes served:

- `runtime-truth-reconciliation-2026-06`
- `runtime-truth-spine-adoption-2026-06`
- `agent-admission-semantic-commons-2026-06`

BR entries addressed or unblocked:

- Unblocks `BR-005` by making signals joinable to structured records.
- Unblocks `BR-013` by giving all agents one runtime vocabulary.
- Supports future `BR-003` closure by making write-back receipts inspectable.

Top-5 ROI moves subsumed:

- Subsumes BR re-verification for runtime object/link debt.
- Supports loop-closure receipts by improving runtime proof chains.

### Phase 2 - Harden Operator Brief as the first ActionType seam

Scope:

- Keep the shipped name `operator_brief`.
- Keep `operator-brief-seam-2026-04` as historical shipped evidence.
- Add association from each operator-brief tick/proposal to `OperatorAction`.
- Add exactly one `RuntimeReceipt` per operator-brief outcome, success or fail-closed.
- Keep existing ontology objects: `ActionProposal`, `WitnessLog`, `GateDecisionRecord`, `Outcome`, `ValueEvent`, `Contribution`, and `KnowledgeArtifact`.
- Keep existing `ArtifactRecord`.
- Use `ActionType` as a direct Palantir term only in the contract text; implementation should reuse `OperatorAction` / `ActionProposal` / `ActionDef`.

What changes:

- `dharma_swarm/operator_brief/insight_brief.py` or `persistence.py` may call `RuntimeStateStore.record_operator_action()` and `record_runtime_receipt()`.
- Tests add idempotency and join assertions.
- Watchdog can surface missing `OperatorAction` or missing `RuntimeReceipt` as DEGRADED.

What does not change:

- No rename to "Daily Insight Brief" or "Morning Brief".
- No new publication surface.
- No new object store.
- No rewrite of the shipped operator brief package.

Acceptance criteria:

- `pytest -q tests/test_operator_brief_insight_brief.py tests/test_guardian_crew.py -k "operator_brief or ledger_watcher"` passes.
- One successful tick has an `ActionProposal`, `OperatorAction`, `RuntimeReceipt`, and `ArtifactRecord` joined by `trace_id` / `task_id` / `proposal_id`.
- One fail-closed path writes a receipt without materializing a false artifact.
- Re-running the same date/agent does not create duplicate side effects.
- `operator_brief` watchdog detects missing action/receipt coverage in a fixture.

Blast radius:

- `dharma_swarm/operator_brief/insight_brief.py`
- `dharma_swarm/operator_brief/persistence.py`
- `dharma_swarm/operator_brief/watchdog.py`
- `tests/test_operator_brief_insight_brief.py`
- `tests/test_guardian_crew.py`
- Medium because Operator Brief is shipped and cron-wired.

Evidence to produce:

- Test receipt.
- Runtime DB fixture proving the chain.
- One small report under `reports/witness/` or `reports/architectural/`.
- No governance file mutation by Stage-1.

Exit criterion:

- Operator Brief is no longer merely "action-shaped".
- It is a real ActionType seam in repo vocabulary because an action proposal, operator action, runtime receipt, artifact record, and value event can be joined.

Dependency rationale:

- This is the smallest already-shipped concept that can become Palantir-grade without a rewrite.
- It comes after runtime record tests because it depends on `OperatorAction`, `RuntimeReceipt`, and `ArtifactRecord`.

Active lanes served:

- `runtime-truth-reconciliation-2026-06`
- `runtime-truth-spine-adoption-2026-06`
- `loop-closure-2026-06`

BR entries addressed or unblocked:

- Unblocks `BR-005` by making one output loop receipted.
- Supports `BR-013` by showing agents the correct action pattern.

Top-5 ROI moves subsumed:

- Subsumes loop-closure receipts for this seam.
- Subsumes architecture-decision issue by turning the decision into one working seam.

### Phase 3 - Formalize the ontology surface as a modular kernel

Scope:

- Pick the explorer verdict: formalize the current files as a modular ontology kernel.
- Do not consolidate into `ontology.py`.
- Do not leave private-access drift alone.
- Keep public names: `OntologyRegistry`, `OntologyHub`, `get_shared_registry`, `persist_shared_registry`, `OntologyGraph`.
- Add narrow public registry methods where production code currently reads `_objects`, `_link_instances`, or `_action_log`.
- Stabilize `api/routers/ontology.py` without letting `_TYPE_CATEGORIES` become schema truth.
- Decide `FileProfile`: register and test it, or explicitly exclude `adapt_file_profiles()`.
- Keep legacy `Entity/ONTOLOGY` compatibility until consumers are mapped.

What changes:

- Small public methods in `OntologyRegistry`.
- `ontology_query.py` and router reads move away from internals where feasible.
- Adapter tests clarify which adapter types are supported.
- Optional ADR update references ADR-008 but does not ratify it by itself.

What does not change:

- No stop-the-world split of `ontology.py`.
- No `OntologyManager`.
- No new `ontology2.py`.
- No new persistence store beside `ontology.db`.
- No versioned `api_name`.

Acceptance criteria:

- `pytest -q tests/test_ontology_registry.py tests/test_ontology_query.py tests/test_ontology_hub.py tests/test_ontology_runtime.py tests/test_ontology_router.py tests/test_ontology_adapters.py` passes or scoped failures are recorded.
- `rg "_objects|_link_instances|_action_log" api dharma_swarm/ontology_query.py dharma_swarm/ontology_adapters.py` shows reduced or intentional internal access only.
- `FileProfile` is either registered and tested or excluded with a test.
- API endpoint response shape tests remain stable.
- ADR-008 grammar tests continue to pass.

Blast radius:

- High if touching `OntologyRegistry`, `get_shared_registry`, or `execute_action()`.
- Keep edits narrow and test-first.
- Avoid `execute_action()` behavior changes unless separately scoped.

Evidence to produce:

- Ontology test output.
- GitNexus impact checks before touching `OntologyRegistry`, `get_shared_registry`, `persist_shared_registry`, or `execute_action()`.
- A short report listing any remaining direct private accesses and why they are intentional.

Exit criterion:

- The repo has a named modular kernel boundary without a new singleton.
- Future agents know which file owns schema, persistence, runtime singleton, graph query, adapters, agent projection, and API view.

Dependency rationale:

- This comes after Operator Brief action hardening because the shipped seam clarifies the action contract.
- It comes before world_radar de-dup because the namespace de-dup should follow the kernel boundary rule.

Active lanes served:

- `agent-admission-semantic-commons-2026-06`
- `runtime-truth-spine-adoption-2026-06`
- `orientation-graph-2026-06`

BR entries addressed or unblocked:

- Addresses `BR-013` by reducing contract fragmentation.
- Supports `BR-014` by keeping gate decisions in the ontology action chokepoint.

Top-5 ROI moves subsumed:

- Subsumes architecture-decision issue.

### Phase 4 - Resolve `world_radar` namespace duplication with a shim

Scope:

- Pick `dharma_swarm/world_radar/` as the long-term namespace owner.
- Treat `dharma_swarm/operator_core/world_radar/` as receipt projection legacy location.
- Add `dharma_swarm/world_radar/receipt_bridge.py` first as a pure re-export.
- Update top-level `go_bridge.py` to import from `dharma_swarm.world_radar.receipt_bridge`.
- Later move implementation and leave `operator_core/world_radar/receipt_bridge.py` as a deprecation shim.
- Update `control_surface_go.py` after the shim is proven.
- Governance manifest references require operator action.

What changes:

- One new top-level re-export module.
- One import path in `go_bridge.py`.
- Later implementation move with compatibility shim.
- Tests for both import paths until deprecation window ends.

What does not change:

- No rewrite of world radar analysis.
- No new "Dharma Radar" implementation.
- No deletion of operator-core package until import graph is clean.
- No change to Go scout behavior.

Acceptance criteria:

- `rg "operator_core\\.world_radar|world_radar\\.receipt_bridge" dharma_swarm tests` shows expected shim/caller state.
- `pytest -q tests/test_world_radar_go_bridge.py tests/test_go_world_signal_bridge.py tests/test_world_signal_analysis.py tests/test_world_radar_cli.py` passes.
- Both old and new import paths work for one release window.
- Manifest/governance changes are listed as operator action, not made by Stage-1.

Blast radius:

- `dharma_swarm/world_radar/go_bridge.py`
- `dharma_swarm/world_radar/receipt_bridge.py`
- `dharma_swarm/operator_core/world_radar/receipt_bridge.py`
- `dharma_swarm/operator_core/control_surface_go.py`
- `tests/test_go_world_signal_bridge.py`
- Low if done with re-export first.
- Medium when moving implementation.

Evidence to produce:

- Import graph receipt.
- Test output.
- Deprecation note in the shim.
- Operator action note for `ACTIVE_SURFACE_MANIFEST.yaml`.

Exit criterion:

- Only one real `world_radar` namespace owns implementation.
- Operator-core imports are control-surface projections, not a second package identity.
- `Dharma Radar` remains a plan/view term, not a second store.

Dependency rationale:

- This is the cleanest name-drift example on disk.
- It is safe only after the ontology kernel boundary rule is documented.
- It should not precede runtime/action receipt work because it is lower ROI than making a shipped seam Palantir-grade.

Active lanes served:

- `agent-admission-semantic-commons-2026-06`
- `a2a-cloud-agent-bridge-2026-06`
- `runtime-truth-spine-adoption-2026-06`

BR entries addressed or unblocked:

- Addresses `BR-013` by reducing duplicated agent-facing namespace.
- Supports `BR-005` by keeping world-signal projections traceable.

Top-5 ROI moves subsumed:

- Does not subsume a top-5 ROI move directly.
- It prevents the next name-drift failure.

### Phase 5 - Grow Guardian from observation toward policy/write-back control

Scope:

- Keep `LEDGER_WATCHER` read-only where it is read-only.
- Do not pretend Guardian is ACL today.
- Add policy-version, actor role, purpose, and data classification to existing gate/receipt envelopes where already present.
- Do not create new verdict names.
- Use existing `GateDecisionRecord`, `SecurityPolicy`, `RuntimeReceipt`, and `IdempotencyRecord`.
- Make context-bundle status fail closed before selected side effects.
- Wire or delete `check_control_surface_envelope_degraded()`.
- Treat GitHub issue creation as ActionType-class write-back with action record, idempotency, and receipt.

What changes:

- Selected write paths get pre-side-effect context checks.
- Guardian tests prove observation and precondition behavior separately.
- Operator-action writes get receipts.
- Dormant control-surface watchdog hook is either called or removed.

What does not change:

- No broad ACL system.
- No new policy engine.
- No direct hard-code mutation of `BHED_GNAN`.
- No claim that Guardian is equivalent to Foundry policy.

Acceptance criteria:

- `pytest -q tests/test_guardian_crew.py tests/test_guardian_runtime_checks.py` passes.
- Fixture proves bad context status blocks one selected side effect before write.
- Fixture proves Guardian still reads runtime DB read-only.
- Fixture proves GitHub issue creation path has idempotency and receipt if exercised.
- `check_control_surface_envelope_degraded()` is covered or removed.

Blast radius:

- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/guardian_runtime_checks.py`
- `dharma_swarm/operator_brief/watchdog.py`
- Selected write-back caller.
- Medium to high because policy can block work.

Evidence to produce:

- Test receipts.
- One before/after Guardian report.
- One runtime receipt showing blocked side effect or policy decision.
- Operator action note for `BR-014` closure path.

Exit criterion:

- One write-back path is guarded before side effect.
- Guardian remains honest about its scope.
- Policy fields are replayable in existing records.

Dependency rationale:

- Policy comes after object/action/receipt hardening.
- A policy gate without joinable receipts becomes another unverifiable audit doc.

Active lanes served:

- `runtime-truth-reconciliation-2026-06`
- `runtime-truth-spine-adoption-2026-06`
- `loop-closure-2026-06`

BR entries addressed or unblocked:

- Addresses `BR-005` by turning some signals from log-only into policy.
- Unblocks `BR-003` by defining write-back safety.
- Unblocks `BR-014`, but closure requires operator-tier gate policy.

Top-5 ROI moves subsumed:

- Subsumes BR re-verification.
- Supports loop-closure receipts.

### Phase 6 - Add minimal Branch and lineage semantics without new storage

Scope:

- Introduce Palantir term `Branch` only as a definition.
- Implement Branch using existing git branches/worktrees plus `WorkspaceLease`.
- Use `RuntimeReceipt` chains for branch/action lineage.
- Use `ArtifactRecord.parent_artifact_id`, `trace_id`, `correlation_id`, and `causation_id` for lineage.
- Use `IdempotencyRecord` for write-back replay protection.
- Keep Code Workbook naming `naming TBD by NAMING_CANON.md` unless operator decides to adopt Palantir's term directly.

What changes:

- Tests for `WorkspaceLease` as branch/lease primitive.
- A branch-lineage receipt convention for selected write paths.
- Optional docs under `docs/ontology/` or `docs/architecture/ADRs/`.

What does not change:

- No new branch database.
- No new lineage database.
- No new workflow engine.
- No replacement for git/worktrees.

Acceptance criteria:

- A selected Stage-1 work packet has a `WorkspaceLease`, `RuntimeReceipt`, `ArtifactRecord`, and idempotency record.
- The receipt chain can be rendered without reading the GitHub UI.
- A failed or abandoned branch has an explicit terminal receipt.
- `pytest -q tests/test_runtime_state.py tests/test_spine_persistence_invariant.py` passes.

Blast radius:

- Runtime record tests.
- Work packet scripts only if a selected path is wired.
- Medium if touching live PR automation; otherwise low.

Evidence to produce:

- One branch-lineage receipt.
- One replay command.
- One exit report showing no duplicate side effect.

Exit criterion:

- The repo has a minimum viable branch/write-back analogue that matches the mobile-first multi-PR reality.

Dependency rationale:

- Branching is expensive in Palantir because write-back semantics matter.
- This phase waits until action receipts and policy gates exist.

Active lanes served:

- `runtime-truth-spine-adoption-2026-06`
- `runtime-truth-nats-2026-06`
- `a2a-cloud-agent-bridge-2026-06`

BR entries addressed or unblocked:

- Supports `BR-003`.
- Supports `BR-004` by making repo/live execution contexts explicit.
- Supports `BR-013`.

Top-5 ROI moves subsumed:

- Supports PR #609 finalization and later PR hygiene by making branch state explicit.

### Phase 7 - Operator-tier production ontology grade

Scope:

- This phase requires operator-tier authority.
- Ratify or revise ADR-008.
- Decide whether to add `NAMING_CANON.md` to protected governance.
- Decide how to close `BR-014` through governed gate policy.
- Decide whether live apply in `BR-003` can move beyond shadow.
- Promote selected ObjectTypes to `TypeStatus.PROMOTED`.
- Require all production write-back paths to carry `RuntimeReceipt` and idempotency.
- Move substrate nativeness from `~10-15%` toward `30%+` with measured coverage.

What changes:

- Governance files may change, but only by operator action.
- Promotion status may change, but only with operator authorization.
- Live apply policy may change, but only with explicit gate receipts.

What does not change:

- No agent marks governance complete.
- No agent promotes itself.
- No model confidence becomes production truth.

Acceptance criteria:

- Operator-approved ADR status update.
- `make onboard` shows relevant lane criteria complete.
- `python3 scripts/governance/check_track_status.py` reports expected shippable/active state.
- Runtime receipt coverage report moves beyond current gate.
- `CYBERNETIC_LOOP_MAP.md` is updated only after real receipts prove loop closure.

Blast radius:

- Governance files.
- Runtime policy.
- Promotion lifecycle.
- High; operator-tier only.

Evidence to produce:

- Operator-approved commit.
- Runtime receipts.
- Governance closeout.
- Loop closure receipt.
- Retro under `reports/loop_closure/RETROSPECTIVE.md` if closing that lane.

Exit criterion:

- Palantir-grade is no longer aspirational for one or more shipped seams.
- It is visible in object/action/link/write-back lineage and guarded by policy.

Dependency rationale:

- This phase depends on every earlier phase.
- Operator-tier decisions should not be made while names, receipts, and policy are still unstable.

Active lanes served:

- `runtime-truth-spine-adoption-2026-06`
- `loop-closure-2026-06`
- `agent-admission-semantic-commons-2026-06`

BR entries addressed or unblocked:

- `BR-003`
- `BR-004`
- `BR-005`
- `BR-013`
- `BR-014`

Top-5 ROI moves subsumed:

- PR #609 finalization if still open.
- Loop-closure receipts.
- BR re-verification.
- Architecture decision closure.

## Section 3 - Cross-cutting concerns

### Lineage

- Do not add a new lineage module in Phase 0-2.
- Existing lineage fields are enough for first Palantir-grade seams.
- Use `RuntimeReceipt.trace_id`.
- Use `RuntimeReceipt.correlation_id`.
- Use `RuntimeReceipt.causation_id`.
- Use `RuntimeReceipt.parent_run_id`.
- Use `ArtifactRecord.parent_artifact_id`.
- Use `ArtifactRecord.trace_id`.
- Use `MemoryFact.source_event_id`.
- Use `MemoryFact.source_artifact_id`.
- Use `IdempotencyRecord.result_receipt_id`.
- Use `OperatorAction.run_id`.
- Use `SessionEventRecord.run_id`.
- Add tests that prove joins instead of adding classes.
- Only add a lineage module if rendering/querying becomes duplicated in at least two places.

### Branching / write-back

- Minimum viable Branch is existing git/worktree plus `WorkspaceLease`.
- Branch must have a holder, base hash, and expiration.
- Branch write-back must have `IdempotencyRecord`.
- Branch write-back must have `RuntimeReceipt`.
- Branch write-back must have rollback or terminal receipt.
- Do not create a new branch database.
- Do not model every PR as ontology object before one write-back path is proven.
- Stage-1 agents can recommend branch policy, but operator must authorize governance and live-apply changes.

### Policy / ACL

- `guardian_crew.py` is not ACL today.
- `LEDGER_WATCHER` is read-only producer-health observation.
- `operator_brief/watchdog.py` is output/trace coverage observation.
- `SecurityPolicy` exists in `ontology.py`.
- `GateDecisionRecord` exists as ontology object.
- Context-bundle health is closest to a security marking analogue.
- Foundry-style security markings travel with data; dharma_swarm does not yet have equivalent durable mandatory-control labels.
- First policy upgrade should be pre-side-effect fail-closed behavior on one write path.
- Do not attempt full ACL until receipts and action joins are mature.

### Functions vs agents

- Functions are deterministic.
- Agents are not Functions.
- `world_radar.analysis` can be treated as Function-like.
- `ontology_query.OntologyGraph` can be treated as Function-like.
- `operator_brief.run_once()` is a Pipeline/Action seam, not a pure Function, because it writes artifacts and records.
- `palantir_pilot.local_public_source_query` is deterministic local retrieval/synthesis, not a peer model.
- `perplexity-computer`, Codex, Devin, Claude, and other agents should not be modeled as Functions.
- Agent outputs need `RuntimeReceipt`, source refs, and confidence boundaries.

### The two `world_radar` packages

- Top-level `dharma_swarm/world_radar/` owns runtime behavior.
- `operator_core/world_radar/` owns only receipt projection today.
- The namespace duplication should be resolved in Phase 4.
- Add top-level re-export first.
- Move implementation second.
- Keep shim third.
- Update operator-core callers fourth.
- Remove old package only after import graph is clean.
- Governance manifest references are operator action.

### The ontology surface

- Pick formalized modular kernel.
- Do not consolidate into a singleton.
- `ontology.py` owns core models, registry, action execution, domain types, and legacy compatibility.
- `ontology_hub.py` owns SQLite persistence.
- `ontology_runtime.py` owns shared runtime access and legacy import.
- `ontology_query.py` owns graph reads.
- `ontology_adapters.py` owns subsystem ingestion.
- `ontology_agents.py` owns agent projection.
- `api/routers/ontology.py` owns API view.
- Reduce private registry access over time.
- Preserve public imports and tests.

## Section 4 - Anti-pattern register

- Do not introduce `OntologyManager`. It would create a new god object beside `OntologyRegistry`, `OntologyHub`, and `ontology_runtime.py`, increasing the exact drift this roadmap is meant to stop.

- Do not replace `ArtifactRecord` with a new `BaseObject`. `ArtifactRecord` is already the object primitive for artifacts and is wired into runtime receipts, Operator Brief, and runtime truth.

- Do not rename Operator Brief to Daily Insight Brief, Morning Brief, or Ontology-Native Operator Brief in new work. The repo already has those synonyms and the shipped package is `operator_brief`.

- Do not model agent decisions as deterministic Functions. Agents are stochastic or provider-dependent; treating them as Functions would destroy replay claims and make receipts dishonest.

- Do not add version suffixes to ontology `api_name`. ADR-008 explicitly rejects `.v<N>` and keeps version in `ObjectType.version:int`.

- Do not implement Dharma Radar as a second store. The current path is `world_radar` over verified packets and receipts, not a parallel evidence substrate.

- Do not mutate Guardian from observer to broad blocker in one PR. A sudden global policy gate would break continuous shipping and make mobile-first operation brittle.

## Section 5 - Open decisions

- Operator decision: ratify ADR-008 as-is, revise it, or keep it PROPOSED while phases use it as local discipline.

- Operator decision: where `NAMING_CANON.md` lives and whether it becomes protected governance.

- Operator decision: whether Phase 0's canonical artifact should be an ADR, a report, or both.

- Operator decision: when `BR-014` may be addressed through gate policy and who owns that proposal.

- Operator decision: when live apply in `BR-003` may move beyond shadow apply.

- Operator decision: whether `FileProfile` should become a registered ObjectType or `adapt_file_profiles()` should remain excluded.

- Operator decision: when the `world_radar` shim deprecation window is long enough to remove `operator_core/world_radar/`.

## Section 6 - Recommended first commit

Commit title:

`docs(ontology): record Palantir-grade semantic ontology roadmap`

No new lane needed.

Recommended files:

- `reports/architectural/palantir_grade_semantic_ontology_roadmap_20260616.md`
- Optional later ADR: `docs/architecture/ADRs/ADR-009-palantir-grade-ontology-kernel.md`

Stage-1-safe content:

- Triple-check log.
- Object/Link/Action mapping table.
- Phase 0-7 roadmap.
- Anti-pattern register.
- Operator-only decisions.
- A2A receipt references.

Do not touch:

- `docs/governance/ACTIVE_TRACK.yaml`
- `ACTIVE_SURFACE_MANIFEST.yaml`
- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/governance/ANTI_SLOP_RULES.md`
- `docs/governance/BUILD_SESSION_ENTRYPOINT.md`
- `docs/governance/MEGAFILE_INDEX.md`
- `docs/architecture/THE_ORGANISM.md`
- `docs/architecture/NORTH_STAR.md`
- `CLAUDE.md`
- `README.md`
- `docs/architecture/INTERFACE_MISMATCH_MAP.md`

Acceptance lint:

```bash
make onboard
grep -rIlE "class.*Record|class.*Artifact|@dataclass" dharma_swarm/ --include="*.py" | head -40
grep -nE "^class " dharma_swarm/runtime_state.py
ls dharma_swarm/ontology* api/routers/ontology*
git log --oneline -20 -- dharma_swarm/ontology.py dharma_swarm/ontology_runtime.py
wc -l dharma_swarm/runtime_state.py dharma_swarm/ontology*.py
find docs/architecture/ADRs -name "*.md" | sort | tail -10
python3 scripts/governance/check_track_status.py
```

First code PR after this commit:

- Add `MemoryEdge` read/list coverage and runtime object mapping tests.
- Keep it under `runtime-truth-reconciliation-2026-06` and `agent-admission-semantic-commons-2026-06`.
- Do not open a new lane.
- Do not touch Operator Brief until runtime link tests are green.

Copy-paste starter ADR sketch if the operator chooses ADR:

```md
# ADR-009: Palantir-Grade Ontology Kernel Without New Names

Status: PROPOSED

Decision: dharma_swarm will formalize its existing ontology/runtime surfaces as a modular ontology kernel. Runtime records in `runtime_state.py` are the first object vocabulary. `MemoryEdge` and `LinkDef` are the link vocabulary. `OperatorAction`, `ActionProposal`, and `ActionDef` are the action vocabulary. `RuntimeReceipt` and `IdempotencyRecord` are the write-back proof vocabulary.

No new `OntologyManager`, `BaseObject`, or parallel store will be introduced.

ADR-008 grammar remains the proposed naming discipline: `dharma.<domain>.<TypeName>`, no `.v<N>`, version in `ObjectType.version:int`.

First implementation phase: add tests and minimal read/list support for runtime object/link records before changing shipped seams.
```

Operator action subsection:

- Ratify or revise ADR-008 before promoting any new public ObjectType.
- Add `NAMING_CANON.md` separately if the naming-canon agent completes that work.
- Update governance track status only through explicit lifecycle review.

## Appendix A - Verifier receipts observed

- `make onboard` completed and reported 11 active tracks.
- Palantir Pilot worker status was running before send.
- A2A packet sent with `uv run --with nats-py python scripts/runtime/a2a_send.py ... --wait 45 --json`.
- A2A receipt path: `reports/a2a/send_receipts/20260615T161835Z-palantir-pilot-f6eb860d656f.json`.
- A2A status: `PALANTIR_PILOT_REPLIED`.
- A2A contact evidence tier: `HANDLER_ACKED`.
- A2A reply artifact path: `/Users/dhyana/.dharma/a2a_bus/outboxes/palantir-pilot/f6eb860d656f-answer.json`.
- Prompt-mandated shell commands were run in the main thread.
- Runtime record explorer reported no edits.
- Operator Brief explorer reported scoped tests: 38 passed in 1.59s.
- Ontology explorer reported ontology-focused collection: 346 tests collected, 0 collection failures.
- World-radar explorer reported no edits and clean scoped git status for radar packages.

## Appendix B - Source anchors

- `docs/governance/ACTIVE_TRACK.yaml`
- `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/ontology.py`
- `dharma_swarm/ontology_hub.py`
- `dharma_swarm/ontology_runtime.py`
- `dharma_swarm/ontology_query.py`
- `dharma_swarm/ontology_adapters.py`
- `dharma_swarm/ontology_agents.py`
- `api/routers/ontology.py`
- `dharma_swarm/operator_brief/`
- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/operator_brief/watchdog.py`
- `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`
- `docs/state/BROKEN_REGISTER.md`
- `CYBERNETIC_LOOP_MAP.md`
- `dharma_swarm/world_radar/`
- `dharma_swarm/operator_core/world_radar/`

## Appendix C - Palantir public-source anchors from local Palantir Pilot

- `https://palantir.com/docs/foundry/api/ontologies-v2-resources/ontology-interfaces/ontology-interface-basics/`
- `https://palantir.com/docs/foundry/api/v2/ontologies-v2-resources/ontology-interfaces/ontology-interface-basics/`
- `https://palantir.com/docs/defense-osdk/api/targetingFires/interfaceTypes/com-palantir-ontology-defense-types-fireSupportCoordinationMeasure/`
- Local note: `/Users/dhyana/.dharma/knowledge/wiki/research/palantir-pilot/titanium-expert-qa-bench.md`
- Local note: `/Users/dhyana/.dharma/knowledge/wiki/research/palantir-pilot/titanium-product-family-deep-maps.md`
- Local note: `/Users/dhyana/.dharma/knowledge/wiki/research/palantir-pilot/titanium-first-principles-model.md`

These anchors are evidence for public-source Palantir ontology vocabulary only. They are not official authorization, tenant guidance, private training, or certification.
