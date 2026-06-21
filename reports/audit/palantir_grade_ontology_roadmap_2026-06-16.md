# Palantir-Grade Ontology Roadmap for dharma_swarm

Date: 2026-06-16 Asia/Tokyo  
Runtime: local Codex audit on `/Users/dhyana/dharma_swarm`  
Local branch: `telos-ai-seed-v0-from-sandbox`  
Local HEAD: `cc9c05f212b3536965661200c39484bc2bcd7bcf`

This roadmap is evidence-only. It recommends governance edits, but does not
touch governance files. It reuses on-disk names or Palantir terms directly.

## 0. Triple-check log

- Repo HEAD: changed. Prompt said HEAD `9c76b210`; local checkout is `cc9c05f21` (`git log -1`). PR #609 contains `9c76b210`-era commits plus later commits.
- Active tracks: changed. `docs/governance/ACTIVE_TRACK.yaml` has 11 `active_tracks`, not 15. Raw statuses are all `ACTIVE`.
- Computed shippable tracks: changed. `reports/governance/track_portfolio.json` marks 5 tracks shippable: `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `orientation-graph-2026-06`, `composer-holon-spine-longrun-2026-06`.
- `runtime-truth-spine-adoption-2026-06`: changed. Prompt said 7/8; local computed report says 9/9 and shippable.
- `runtime-truth-spine-2026-06`: changed. Prompt called it possible near-duplicate; local `ACTIVE_TRACK.yaml` has it in closed tracks with `status: SHIPPED` at line 1302.
- `loop-closure-2026-06`: confirmed. Computed report says 3/5, matching prompt.
- New substrate tracks: changed. Local active substrate tracks also include `agent-admission-semantic-commons-2026-06`, `helm-worldclass-terminal-2026-06`, and `a2a-cloud-agent-bridge-2026-06`.
- Broken Register entries: mostly confirmed. `BR-003`, `BR-004`, `BR-005`, and `BR-013` are `PARTIAL`; `BR-014` is `OPEN` in local `docs/state/BROKEN_REGISTER.md`, not `PARTIAL`.
- Runtime record vocabulary: confirmed with shifted file length. `runtime_state.py` has `ArtifactRecord`, `MemoryFact`, `MemoryEdge`, `OperatorAction`, `SessionEventRecord`, `RuntimeReceipt`, and `IdempotencyRecord` at lines 542-651; file is now 4,152 lines, not 3,797.
- Ontology API grammar: confirmed. ADR-008 states `api_name = dharma.<domain>.<TypeName>`, no `.v<N>` suffix, version lives in `ObjectType.version`.
- Ontology surface: confirmed. The surface is seven files: `ontology.py`, `ontology_hub.py`, `ontology_runtime.py`, `ontology_query.py`, `ontology_adapters.py`, `ontology_agents.py`, and `api/routers/ontology.py`.
- Operator brief surface: changed. It is 6 Python files, but 1,734 LOC locally, not 1,579. It records `KnowledgeArtifact` plus `ArtifactRecord` with trace, gate, witness, and source metadata.
- Operator brief lane: confirmed. `operator-brief-seam-2026-04` is in closed tracks with `status: SHIPPED`.
- Guardian policy surface: confirmed. `guardian_crew.py` has `GuardianFinding`, `AUDITOR`, `LOOP_WATCHER`, `ROUTER_PROBE`, and `LEDGER_WATCHER`; operator brief watchdog checks artifact output and trace coverage.
- Master audit ontology-native estimate: confirmed as governance input. `ACTIVE_TRACK.yaml` cites the audit estimate `~10-15% native today; target 30%+` at lines 60-63.
- Cybernetic loop map path: refuted. Prompt path `docs/state/CYBERNETIC_LOOP_MAP.md` does not exist. Current root file is `CYBERNETIC_LOOP_MAP.md`; an ingested copy exists at `docs/sovereign_holons/ingested/qwen/CYBERNETIC_LOOP_MAP.md`.
- Cybernetic loop content freshness: changed. Root map still says provider availability blocks Loop 1, but this local machine now has a working `zai_coding` key from separate dkeys verification; treat provider statements in the root map as stale until re-audited from live runtime.
- `world_radar` duplication: confirmed. `dharma_swarm/world_radar/` has 1,960 Python LOC; `dharma_swarm/operator_core/world_radar/` has 282 Python LOC.
- `world_radar` ownership shape: clarified. Top-level `world_radar` owns execution/scoring/briefing; `operator_core/world_radar/receipt_bridge.py` is a read-only Go evidence receipt projection bridge.
- PR #609: changed. It is open and `UNSTABLE`; it has 8 commits in the GitHub view, not 5. Failing check: `detect-br-collision`.
- `stash@{0}`: changed. Current `stash@{0}` is `what-not-to-do mandala cockpit attempt 2026-06-16`, not the four naming amendments described in the prompt.
- `docs/governance/NAME_DRIFT_REPORT.md`: changed. It is absent locally.
- Naming-canon work: partially confirmed. `scripts/governance/name_drift_preflight.py` is untracked locally; `NAMING_CANON.md` is not present.
- Required shell probes: run. They confirmed `RuntimeStateStore` class at line 1185, ontology git history including OMS hardening and action tollbooth commits, ontology module total 8,862 LOC, and ADR files only ADR-006 through ADR-008.

## 1. Palantir-grade target state in dharma_swarm vocabulary

Palantir-grade does not mean "build a Palantir clone." For this repo it means:
typed objects, typed links, typed actions, deterministic functions where possible,
lineage for every mutation, branch/write-back discipline, and policy gates that are
receipted through existing runtime substrates.

| Palantir primitive | dharma_swarm current | Gap |
|---|---|---|
| ObjectType | `ObjectType` in `ontology.py`; `ArtifactRecord`, `MemoryFact`, `TaskClaim`, `DelegationRun`, `WorkspaceLease`, `ContextBundleRecord`, `SessionEventRecord`, `RuntimeReceipt`, `IdempotencyRecord` in `runtime_state.py` | Code has two object vocabularies: ontology schema objects and runtime record dataclasses. Formalize the mapping before adding new types. |
| LinkType | `LinkDef`/`Link` in `ontology.py`; `MemoryEdge` in `runtime_state.py`; `correlation_id`, `causation_id`, `parent_run_id`, `parent_artifact_id` fields | Link discipline exists but is not uniformly projected as typed `LinkDef` or `MemoryEdge`. |
| ActionType | `ActionDef`/`ActionExecution` in `ontology.py`; `OperatorAction` in `runtime_state.py`; operator brief gate/outcome/value objects | There is no single tested rule saying when a runtime mutation must be an `ActionDef`, `OperatorAction`, or both. |
| Function | Deterministic helpers: `ontology_query.OntologyGraph`, `world_radar.analysis`, `operator_brief.watchdog`, guardian checks | Boundary is implicit. Agents and nondeterministic LLM work must not be labeled as deterministic Functions. |
| Code Workbook | No direct analogue. Closest current surfaces are test-backed scripts and reports, plus `reports/audit/*` | Introduce Palantir term "Code Workbook" only if needed later; Phase 0 should not mint a bespoke name. |
| Pipeline | `ontology_adapters.py`, `operator_brief.persistence`, `world_radar.go_bridge`, `engine/store_sync.py` | Pipeline receipt contracts are inconsistent. Use existing `RuntimeReceipt` and `ArtifactRecord`, not a new pipeline ledger. |
| Branch | Git branches/PRs, `WorkspaceLease`, `IdempotencyRecord`, `RuntimeReceipt.side_effect_key` | Minimum viable branch is a workspace lease plus idempotent write-back receipt, not a Foundry branch clone. |
| Permission | `SecurityPolicy`, `guardian_crew.py`, `LEDGER_WATCHER`, `telos_gates.py`, `ActionDef.requires_approval` | Policy surfaces are scattered; grow them through Guardian and Action gates, not a new ACL service. |
| Write-back | `OntologyRegistry.execute_action`, `RuntimeStateStore.record_*`, operator brief artifact materialization, `IdempotencyRecord` | Write-back exists but lacks a uniform "receipt before side effect, receipt after side effect" acceptance rule. |
| Lineage | `ActionExecution.lineage_inputs/lineage_outputs`, `RuntimeReceipt.correlation_id/causation_id`, `ArtifactRecord.metadata`, operator brief frontmatter | Enough fields exist. Do not add `LineageRecord`; add tests and query helpers over current receipts. |

Target state:

1. `runtime_state.py` remains the canonical structured runtime state store.
2. `ontology.py` remains the schema/action definition module.
3. `ontology_hub.py` remains the persistence layer for ontology instances.
4. `ontology_runtime.py` remains the shared loading/persistence access point.
5. `ontology_query.py` remains the graph query layer.
6. `ontology_adapters.py` remains the adapter/pipeline bridge.
7. `ontology_agents.py` remains the live-agent projection layer.
8. `api/routers/ontology.py` remains a read API until write-back gates are tested.
9. Runtime record dataclasses become the first formal ObjectType mapping surface.
10. `ArtifactRecord`, `MemoryEdge`, `OperatorAction`, `RuntimeReceipt`, and `IdempotencyRecord` are upgraded by tests and receipts, not renamed.

Primary promotion candidates:

- `ArtifactRecord`: first operational ObjectType analogue because operator brief already writes it.
- `MemoryEdge`: first operational LinkType analogue because it already represents binary relation.
- `OperatorAction`: first operational ActionType analogue because it represents the receipted operator move.
- `RuntimeReceipt`: first write-back/audit primitive because side effects already need proof.
- `IdempotencyRecord`: first branch/write-back safety primitive because retries must not duplicate side effects.

Deferred candidates:

- `TaskClaim`, `DelegationRun`, and `WorkspaceLease` should be mapped in Phase 1, but not promoted until write-back idempotency tests pass.
- `SessionEventRecord` should remain the event primitive, not be renamed to an Event Object until `NAMING_CANON.md` exists.
- `ContextBundleRecord` should remain a context-bundle primitive, not be folded into artifact lineage.

Non-goals:

- No new universal base class.
- No new canonical ledger.
- No new action registry outside `ontology.py`.
- No direct conversion of every runtime row into an ontology object in one pass.
- No mutation endpoint in `api/routers/ontology.py` before policy and idempotency are proven.

## 2. Phased roadmap

### Phase 0: Freeze the adoption grammar and record mapping

Scope:

- Do this this week under Stage-1 authority.
- Add one ADR or report that maps Palantir primitives to existing repo names.
- Add no new ontology names except Palantir terms `ObjectType`, `LinkType`, `ActionType`, `Function`, `Pipeline`, `Branch`, `Permission`, `Write-back`, and `Lineage`.
- Do not edit off-limits governance files.
- Do not change runtime behavior.

Serves active lanes:

- `runtime-truth-reconciliation-2026-06`
- `orientation-graph-2026-06`
- `agent-admission-semantic-commons-2026-06`

BR entries:

- Unblocks `BR-013` by giving non-Claude agents a stable ontology vocabulary.
- Avoids making `BR-014` worse by not changing gate behavior directly.

Routing-agent top-5 ROI:

- Subsumes the "architecture-decision issue" move.
- Does not block PR #609 or loop closure.

Acceptance criteria:

- One ADR in `docs/architecture/ADRs/` or one report in `reports/audit/`.
- It cites `runtime_state.py:542-651`, `ontology.py:202-232`, `ontology.py:774-977`, and `ADR-008`.
- It explicitly says "no `OntologyManager` singleton."
- It says `LineageRecord` is not introduced.
- It includes an operator-action subsection for any future `ACTIVE_TRACK.yaml` changes.

Blast radius:

- Documentation only.
- No deprecations.
- No migrations.
- No governance writes by Stage-1 agents.

Evidence to produce:

- `docs/architecture/ADRs/ADR-009-palantir-grade-ontology-adoption.md` or equivalent report.
- A short command transcript with the required probes from this prompt.
- Optional test sketch, but no runtime test required.

Concrete implementation notes:

- Prefer ADR-009 over a broad audit document because ADRs are already the repo's architectural decision surface.
- Keep ADR-009 under 500 LOC; the point is to freeze names, not review every subsystem.
- Cite `ADR-008` as upstream grammar, not as a replacement decision.
- Include an explicit "operator actions" section for governance files.
- Include an explicit "forbidden new abstractions" section naming `OntologyManager`, `BaseObject`, and `LineageRecord`.

Validation commands:

```bash
python -m py_compile dharma_swarm/runtime_state.py dharma_swarm/ontology.py dharma_swarm/ontology_runtime.py
grep -R "class OntologyManager\\|class LineageRecord\\|class BaseObject" dharma_swarm tests
```

Expected result:

- `py_compile` passes.
- `grep` returns no new matches.

Exit criterion:

- Operator can point future agents to one file that says which existing names map to Palantir primitives.
- Future phases cannot invent a new object/link/action vocabulary without citing that decision.

Why this phase before the next:

- Palantir adoption order starts with stable ontology vocabulary. Without this, every later phase creates another synonym set.

### Phase 1: Promote runtime records as ObjectType mappings

Scope:

- Treat the runtime dataclasses in `runtime_state.py:483-651` as the first object catalog for operational truth.
- Add a small read-only projection test or script that lists required runtime record classes and their Palantir primitive role.
- Do not add new record classes.
- Do not move `runtime_state.py`.

Serves active lanes:

- `runtime-truth-reconciliation-2026-06`
- `runtime-truth-spine-adoption-2026-06`
- `composer-holon-spine-longrun-2026-06`

BR entries:

- Addresses the runtime side of `BR-013`.
- Unblocks future `BR-005` action-consumption work by clarifying event/fact/action objects.

Routing-agent top-5 ROI:

- Reinforces spine-adoption and loop-closure receipts.

Acceptance criteria:

- Test asserts these names exist in `dharma_swarm.runtime_state`: `SessionState`, `TaskClaim`, `DelegationRun`, `WorkspaceLease`, `ArtifactRecord`, `MemoryFact`, `MemoryEdge`, `ContextBundleRecord`, `OperatorAction`, `SessionEventRecord`, `RuntimeReceipt`, `IdempotencyRecord`.
- Test asserts no `LineageRecord` or `BaseObject` class was introduced.
- Test or report maps:
  - `ArtifactRecord` -> ObjectType analogue
  - `MemoryEdge` -> LinkType analogue
  - `OperatorAction` -> ActionType analogue
  - `RuntimeReceipt` -> audit/write-back receipt
  - `IdempotencyRecord` -> write-back idempotence

Blast radius:

- New tests or docs only.
- No schema migration.
- No `runtime_state.py` rewrite.

Evidence to produce:

- `tests/test_runtime_record_ontology_mapping.py`
- Output of `pytest tests/test_runtime_record_ontology_mapping.py -q`
- Optional generated JSON under `reports/audit/runtime_record_ontology_mapping.json`

Concrete implementation notes:

- The test should use `hasattr()` and dataclass introspection, not line-number assertions.
- The mapping should be data-driven so a future agent can extend it without editing test logic.
- The test should fail if a new `BaseObject` or `LineageRecord` appears.
- The test should not require a runtime DB.
- The report JSON, if added, should be generated evidence, not the source of truth.

Candidate mapping file shape:

```python
RUNTIME_RECORD_ONTOLOGY_MAPPING = {
    "ArtifactRecord": "ObjectType",
    "MemoryEdge": "LinkType",
    "OperatorAction": "ActionType",
    "RuntimeReceipt": "Write-back",
    "IdempotencyRecord": "Write-back",
}
```

Do not introduce `ObjectKind` or another new enum for this phase.

Exit criterion:

- Agents can no longer claim there is no object vocabulary for runtime truth.

Why this phase before the next:

- Action/write-back lineage needs stable object identities first.

### Phase 2: Use Operator Brief as the first ActionType reference workflow

Scope:

- Treat `dharma_swarm/operator_brief/` as the first shipped Action-shaped workflow.
- Tighten receipts around its existing behavior.
- Do not rename Operator Brief variants until `NAMING_CANON.md` exists.
- Do not create another brief surface.

Serves active lanes:

- `runtime-truth-reconciliation-2026-06`
- `loop-closure-2026-06`
- `orientation-graph-2026-06`

BR entries:

- Helps `BR-005` by turning sensed events into receipted operator-facing action.
- Helps `BR-013` because it gives agents an executable example.

Routing-agent top-5 ROI:

- Subsumes loop-closure receipts if it produces missing receipt artifacts.

Acceptance criteria:

- Existing tests confirm operator brief writes:
  - `KnowledgeArtifact`
  - `ArtifactRecord`
  - gate decision ids
  - witness log ids
  - trace id or explicit legacy trace alias
- Add or keep watchdog coverage for:
  - `LEDGER_WATCHER:operator_brief_empty`
  - `LEDGER_WATCHER:operator_brief_trace_coverage`
- A one-page operator brief ActionType note states:
  - `ActionDef` is the schema-level action.
  - `OperatorAction` is the runtime operator move.
  - `RuntimeReceipt` is the audit/write-back proof.

Blast radius:

- Tests in `tests/test_operator_brief_insight_brief.py` and `tests/test_guardian_crew.py`.
- Possible doc in `reports/audit/`.
- No schema migration.

Evidence to produce:

- `pytest tests/test_operator_brief_insight_brief.py tests/test_guardian_crew.py -q`
- Operator brief sample artifact under `~/.dharma/artifacts/operator_brief/` or temp HOME in tests.
- Runtime DB rows for `artifact_records`.

Concrete implementation notes:

- Do not rename `operator_brief`, `insight_brief.py`, or `KnowledgeArtifact` in this phase.
- Add assertions around existing fields before adding new fields.
- Treat `trace_id_source` as a migration clue, not as a new canonical term.
- Use temp HOME/temp runtime DB in tests so receipt proof does not depend on local operator state.
- Prefer strengthening `operator_brief/watchdog.py` findings over adding another checker.

Minimum proof chain:

1. An operator brief input produces a `KnowledgeArtifact`.
2. The artifact is materialized on disk.
3. `ArtifactRecord` records path/checksum/trace metadata.
4. Guardian or watchdog can detect missing output or missing trace coverage.

Stop condition:

- If existing tests already prove this, Phase 2 should add only a short reference note and avoid code churn.

Exit criterion:

- Operator brief becomes the reference for "an agent action produces a receipted artifact."

Why this phase before the next:

- It is already shipped. Palantir adoption should harden a shipped action before adding abstract ontology machinery.

### Phase 3: Make lineage a receipt query, not a new object

Scope:

- Build lineage from existing fields:
  - `RuntimeReceipt.correlation_id`
  - `RuntimeReceipt.causation_id`
  - `RuntimeReceipt.parent_run_id`
  - `ArtifactRecord.parent_artifact_id`
  - `ArtifactRecord.metadata`
  - `ActionExecution.lineage_inputs`
  - `ActionExecution.lineage_outputs`
- Add read-only query helpers or tests.
- Do not introduce `LineageRecord`.

Serves active lanes:

- `runtime-truth-reconciliation-2026-06`
- `runtime-truth-nats-2026-06`
- `loop-closure-2026-06`
- `a2a-cloud-agent-bridge-2026-06`

BR entries:

- Helps `BR-004` by making cron/runtime split-brain visible through receipts.
- Helps `BR-005` by requiring action consumption lineage.

Routing-agent top-5 ROI:

- Subsumes BR re-verification and loop-closure receipt work.

Acceptance criteria:

- A temp runtime DB test creates a task/run/artifact/receipt chain and queries it back without a new table.
- Operator brief lineage test verifies `cited_fact_ids`, `source_event_ids`, `memory_fact_ids`, `gate_decision_ids`, and `witness_log_ids` survive in `ArtifactRecord.metadata`.
- A2A or NATS path test verifies retry does not create a second `RuntimeReceipt` for the same idempotency key.

Blast radius:

- Tests plus a small read-only helper if needed.
- No DB migration unless a missing index is proven necessary.
- No new canonical ledger.

Evidence to produce:

- `tests/test_runtime_lineage_receipts.py`
- `pytest tests/test_runtime_lineage_receipts.py -q`
- A report snippet with one reconstructed chain.

Concrete implementation notes:

- Start with one chain: task claim -> delegation run -> artifact record -> runtime receipt.
- Include negative coverage: a broken correlation should return "incomplete lineage" rather than silently passing.
- Keep query code read-only.
- If a helper module is needed, place it near existing runtime/query code and keep it narrow.
- Do not use graph databases or external lineage services in this phase.

Candidate query return shape:

```json
{
  "artifact_id": "...",
  "trace_id": "...",
  "nodes": ["TaskClaim", "DelegationRun", "ArtifactRecord", "RuntimeReceipt"],
  "missing": []
}
```

Failure rule:

- Missing lineage is an actionable Guardian finding, not an automatic migration.

Exit criterion:

- A future operator can ask "why does this artifact exist?" and get a chain from existing receipts.

Why this phase before the next:

- World radar and policy upgrades both need traceability before they can safely write back.

### Phase 4: Resolve the two `world_radar/` packages by ownership and shim

Scope:

- Pick top-level `dharma_swarm/world_radar/` as the product package.
- Move or mirror receipt bridge ownership to `dharma_swarm/world_radar/receipt_bridge.py`.
- Leave `dharma_swarm/operator_core/world_radar/receipt_bridge.py` as a deprecation shim until imports are migrated.
- Keep names already on disk: `GoWorldReceipt`, `WorldRadarGoResult`, `ZeitgeistSignal`, `world_signal`.
- Do not introduce "Dharma Radar" as a new code name.

Serves active lanes:

- `orientation-graph-2026-06`
- `runtime-truth-reconciliation-2026-06`
- `a2a-cloud-agent-bridge-2026-06`

BR entries:

- Directly addresses the name/package drift class described by `BR-013`.
- Helps `BR-005` by clarifying world-signal action consumption.

Routing-agent top-5 ROI:

- Supports the architecture-decision issue and BR re-verification moves.

Acceptance criteria:

- `from dharma_swarm.world_radar.receipt_bridge import GoWorldReceipt` works.
- Existing imports from `dharma_swarm.operator_core.world_radar.receipt_bridge` still work and warn or document deprecation.
- Tests cover receipt projection from Go evidence receipts to world-feed rows.
- `grep -R "Dharma Radar" dharma_swarm tests docs` does not add a new code-package synonym.

Blast radius:

- Add one new module or move with shim.
- Update imports only where touched.
- No runtime behavior change.
- No deletion until at least one release/PR cycle later.

Evidence to produce:

- `tests/test_world_radar_receipt_bridge.py`
- Import compatibility test for both paths.
- A deprecation note in the shim docstring.

Concrete implementation notes:

- Add `dharma_swarm/world_radar/receipt_bridge.py` first.
- Make `dharma_swarm/operator_core/world_radar/receipt_bridge.py` re-export from the top-level path.
- Keep public names unchanged: `GoWorldReceipt`, `WorldEventType`, `GO_EVIDENCE_SCHEMA_V0`, `project_world_signal_receipts`, `world_feed_row_from_signal_receipt`, `summarize_go_world_receipts`.
- Update internal imports only where tests cover them.
- Do not delete `operator_core/world_radar` in the same phase.

Compatibility target:

```python
from dharma_swarm.world_radar.receipt_bridge import GoWorldReceipt
from dharma_swarm.operator_core.world_radar.receipt_bridge import GoWorldReceipt as LegacyGoWorldReceipt
assert GoWorldReceipt is LegacyGoWorldReceipt
```

Deprecation wording:

- "Compatibility shim for the former operator_core world_radar receipt bridge. New imports should use dharma_swarm.world_radar.receipt_bridge."

Exit criterion:

- There is one product package path and one legacy shim path, not two conceptual owners.

Why this phase before the next:

- Palantir ObjectTypes require one owner per concept. World radar is the cleanest current fractured ObjectType example.

### Phase 5: Grow policy through Guardian and Action gates

Scope:

- Treat `guardian_crew.py` plus `operator_brief/watchdog.py` as the policy reporting plane.
- Treat `ActionDef.requires_approval`, `ActionDef.telos_gates`, `SecurityPolicy`, and `telos_gates.py` as the policy execution plane.
- Do not directly edit `telos_gates.py` to close `BR-014`; use the existing gate proposal/policy route.

Serves active lanes:

- `agent-admission-semantic-commons-2026-06`
- `runtime-truth-reconciliation-2026-06`
- `loop-closure-2026-06`

BR entries:

- Directly addresses `BR-014`.
- Supports `BR-005` by assigning consumer policy to algedonic actions.
- Supports `BR-013` by making agent policy discoverable.

Routing-agent top-5 ROI:

- Subsumes BR re-verification and the spine-adoption evidence gate.

Acceptance criteria:

- Guardian emits findings for empty structured runtime rows, missing context bundles, operator brief artifact gaps, and trace coverage.
- A policy test proves an action with declared telos gates cannot silently pass without gate evidence.
- A proposal path exists for `BHED_GNAN` improvement without hard-coded mutation.
- Algedonic action classes are assigned one of: log-only, prompt-context, scheduling bias, review, hold, dispatch stop.

Blast radius:

- `guardian_crew.py`, `operator_brief/watchdog.py`, tests.
- Possible proposal artifact under reports.
- No direct governance mutation by Stage-1 agents.

Evidence to produce:

- `pytest tests/test_guardian_crew.py tests/test_ontology.py -q`
- A `GateRegistry.propose()` or equivalent proposal artifact for `BHED_GNAN`.
- A small action-consumer matrix for algedonic actions.

Concrete implementation notes:

- Use Guardian findings as policy evidence, not as the policy authority itself.
- Keep `LEDGER_WATCHER` focused on runtime evidence.
- Keep action approval requirements in `ActionDef`/gate policy surfaces.
- Add a failing regression test before changing any gate behavior.
- For `BR-014`, produce a proposal artifact if operator authority is required.

Algedonic action consumer matrix:

| Action class | Minimum consumer |
|---|---|
| log-only | `RuntimeReceipt` plus Guardian visibility |
| prompt-context | context-bundle inclusion receipt |
| scheduling bias | scheduler decision receipt |
| review | `OperatorAction` or review artifact |
| hold | gate decision receipt |
| dispatch stop | explicit stop receipt plus operator-visible finding |

Policy rule:

- A pass without evidence is not a pass; it is either a warning or a blocked action depending on gate severity.

Exit criterion:

- Policy is visible as receipts/findings, not buried in prose.

Why this phase before the next:

- Branch/write-back is unsafe until policy can block, degrade, or warn with receipts.

### Phase 6: Add minimum viable branch and write-back discipline

Scope:

- Use existing Git branch/PR boundaries for code changes.
- Use `WorkspaceLease` for workspace ownership.
- Use `IdempotencyRecord` for exactly-once side effects.
- Use `RuntimeReceipt` before and after side effects.
- Do not build a Foundry branch clone.

Serves active lanes:

- `runtime-truth-nats-2026-06`
- `a2a-cloud-agent-bridge-2026-06`
- `helm-worldclass-terminal-2026-06`

BR entries:

- Helps `BR-003` because self-evolution apply needs lease, idempotency, and receipt gates.
- Helps `BR-004` because cron writes become receipt-backed side effects.

Routing-agent top-5 ROI:

- Follows after PR #609 finalization and loop-closure receipt work.

Acceptance criteria:

- A write-back path records:
  - `WorkspaceLease`
  - pre-side-effect `RuntimeReceipt`
  - `IdempotencyRecord`
  - post-side-effect `RuntimeReceipt`
  - `ArtifactRecord` if an artifact is created
- Retrying the same side-effect key is idempotent.
- Failed write-back leaves an inspectable receipt.

Blast radius:

- Runtime writer paths only.
- No new write ledger.
- Possible DB index, but no new canonical table unless a performance test proves it.

Evidence to produce:

- `tests/test_runtime_writeback_idempotency.py`
- A report chain showing one successful and one retried write-back.

Concrete implementation notes:

- Start with one low-risk write-back path, not every writer.
- Choose a path that already has `side_effect_key` or equivalent idempotency material.
- Assert retry behavior with the same idempotency key.
- Assert failed write-back preserves enough receipt state for inspection.
- Do not expose HTTP write endpoints until this phase passes in tests.

Minimum write-back contract:

1. Acquire or validate `WorkspaceLease`.
2. Record pre-side-effect `RuntimeReceipt`.
3. Check or create `IdempotencyRecord`.
4. Execute side effect.
5. Record post-side-effect `RuntimeReceipt`.
6. Record `ArtifactRecord` if a file or durable artifact was produced.

Cost control:

- If a writer cannot satisfy this contract, leave it out of Phase 6 and record the omission explicitly.

Exit criterion:

- Agent writes can be audited and replay-protected using current runtime records.

Why this phase before the next:

- Full ontology promotion requires safe writes. Branch/write-back is the last primitive before operator-tier promotion.

### Phase 7: Operator-tier promotion and governance wiring

Scope:

- Operator-only.
- Ratify `ADR-008` if not already ratified.
- Add `NAMING_CANON.md` once the naming agent lands it.
- Promote selected `ObjectType` contracts to `TypeStatus.PROMOTED`.
- Update `ACTIVE_TRACK.yaml`, `ANTI_SLOP_RULES.md`, and related governance files manually.

Serves active lanes:

- All substrate-nativeness tracks.

BR entries:

- Closes or narrows `BR-013` if agent contract discoverability is fixed.
- Narrows `BR-014` only if the gate proposal is accepted.

Routing-agent top-5 ROI:

- Comes after PR #609 and Phase 0-6 evidence. Do not do it first.

Acceptance criteria:

- `NAMING_CANON.md` exists and CI fails on forbidden synonyms.
- Promoted ObjectTypes have stable `api_name` values matching ADR-008.
- Governance files render from canonical sources, not hand-written duplicate names.
- Operator explicitly approves any `ACTIVE_TRACK.yaml` lane change.

Blast radius:

- Governance files.
- CI gates.
- Potential deprecation shims.
- Operator authority required.

Evidence to produce:

- CI pass for name-drift lint.
- ADR status update.
- Governance render output.

Concrete implementation notes:

- Ratify only the contracts already proven by Phase 1-6 tests.
- Keep `TypeStatus.PROMOTED` rare.
- Promote `ArtifactRecord` before more speculative object types.
- Treat governance edits as operator actions, not as Stage-1 cleanup.
- Update onboarding after CI enforcement exists, not before.

Promotion checklist:

- Stable name in `NAMING_CANON.md`.
- Stable `api_name` under ADR-008.
- Read tests.
- Write-back or lineage tests where applicable.
- Guardian or policy visibility where applicable.
- Deprecation shim for old import/name if any exists.

Exit proof:

- A new agent can read onboarding, run the lint, and avoid introducing a synonym without asking the operator.

Exit criterion:

- The ontology grammar is enforceable in CI and socially enforceable in onboarding.

Why this phase last:

- Palantir promotion freezes contracts. Freezing before lineage, policy, and write-back are tested would preserve the wrong shape.

## 3. Cross-cutting concerns

### Lineage

Use existing receipt chains. `RuntimeReceipt` already has `correlation_id`,
`causation_id`, `parent_run_id`, `trace_id`, and `idempotency_key`.
`ArtifactRecord` already has `parent_artifact_id`, `trace_id`, `checksum`, and
metadata. `ActionExecution` already has `lineage_inputs` and `lineage_outputs`.
The missing piece is not a new class; it is query/test discipline over these
fields.

Decision: no `LineageRecord`.

Minimum implementation: a read-only helper that reconstructs chains from current
runtime rows and returns a JSONable path. If it cannot reconstruct a chain, it
emits a Guardian warning instead of inventing a new ledger.

### Branching and write-back

Palantir branching is heavier than dharma_swarm needs now. The minimum viable
analogue is:

- Git branch or PR for code changes.
- `WorkspaceLease` for local workspace ownership.
- `IdempotencyRecord` for exactly-once side effects.
- `RuntimeReceipt` for pre/post side-effect proof.
- `ArtifactRecord` for produced files.

Cost: moderate. Most fields already exist; the cost is wiring and tests.

### Policy and ACL

`guardian_crew.py` is the reporting surface. `ActionDef`, `SecurityPolicy`,
`telos_gates.py`, and `operator_brief/watchdog.py` are the execution/checking
surfaces. Grow policy by adding Guardian findings and tests, not by creating a
separate ACL daemon.

`BR-014` must go through gate proposal/policy mechanics. A direct hard-code edit
to `telos_gates.py` would violate the governance route described in the Broken
Register.

### Functions vs agents

Functions are deterministic, replayable, and testable. In this repo:

- Functions: `OntologyGraph.traverse`, `OntologyGraph.shortest_path`,
  `build_world_signal_board`, `project_world_signal_receipts`, Guardian checks.
- Agents: LLM generation, operator brief drafting, Darwin proposals, world scout
  fetch/classification when LLM-backed.

Rule: deterministic Functions may write receipts after validation; agents must
propose or produce artifacts that are gated and receipted.

### The two `world_radar/` packages

Resolve in Phase 4. Top-level `dharma_swarm/world_radar` becomes the owner.
`dharma_swarm/operator_core/world_radar` becomes a compatibility shim for
operator-core receipt projection until imports move. Do not rename to "Dharma
Radar" in code.

### The ontology surface

Do not consolidate into a singleton. Formalize the current modular kernel:

- `ontology.py`: schema, ObjectType, LinkDef, ActionDef, registry.
- `ontology_hub.py`: SQLite persistence.
- `ontology_runtime.py`: shared registry access.
- `ontology_query.py`: graph query functions.
- `ontology_adapters.py`: adapters from subsystem rows into ontology objects.
- `ontology_agents.py`: live agent projection.
- `api/routers/ontology.py`: read API.

The current split matches Palantir-style separation better than a new
`OntologyManager` would.

## 4. Anti-pattern register

1. Do not introduce `OntologyManager`. It would hide the useful existing split between schema, persistence, query, adapters, and API.
2. Do not replace `ArtifactRecord` with a new `BaseObject`. `ArtifactRecord` is already the runtime artifact primitive and operator brief writes it today.
3. Do not add `LineageRecord`. Lineage fields already exist; adding a table would create another truth store.
4. Do not model agent decisions as deterministic Functions. LLM-backed behavior must remain proposed, gated, and receipted.
5. Do not rename Operator Brief variants before `NAMING_CANON.md`. That is exactly the synonym drift failure mode.
6. Do not delete `operator_core/world_radar` first. Add a top-level owner path and compatibility shim, then migrate imports.
7. Do not promote ObjectTypes before write-back/idempotency tests. Promotion freezes contracts; frozen weak contracts become permanent debt.

## 5. Open decisions

1. Should `ADR-008` be ratified as-is, or does operator want one more grill on status authority?
2. Should `NAMING_CANON.md` own all concept names, or only forbidden synonyms for governance/product surfaces?
3. Should `api/routers/ontology.py` ever expose write-back, or remain read-only permanently?
4. Which `ObjectType` contracts are first eligible for `TypeStatus.PROMOTED`?
5. Should `world_radar` receipt bridge migration happen in the current PR stream or wait for a dedicated PR?
6. What operator action is acceptable for `BR-014`: proposal-only now, or a guarded gate policy PR?
7. Does the operator want a new active lane for Palantir ontology adoption, or should Phase 0 ride existing substrate-nativeness lanes?

## 6. Recommended first commit

Commit title:

`docs(ontology): add Palantir-grade adoption ADR`

Scope:

- Under 500 LOC.
- One ADR maximum.
- No governance file edits.
- No new active lane.

Files:

1. `docs/architecture/ADRs/ADR-009-palantir-grade-ontology-adoption.md`
2. Optional: `tests/test_runtime_record_ontology_mapping.py`

ADR content sketch:

```md
# ADR-009: Palantir-Grade Ontology Adoption Without Name Drift

Status: PROPOSED
Date: 2026-06-16

## Decision

dharma_swarm upgrades toward Palantir-grade ontology by formalizing existing
runtime and ontology primitives. It does not introduce `OntologyManager`,
`BaseObject`, or `LineageRecord`.

## Mapping

| Palantir term | dharma_swarm primitive |
|---|---|
| ObjectType | `ObjectType`, `ArtifactRecord`, `MemoryFact`, `TaskClaim`, `DelegationRun` |
| LinkType | `LinkDef`, `MemoryEdge`, correlation/causation fields |
| ActionType | `ActionDef`, `OperatorAction` |
| Write-back | `RuntimeReceipt`, `IdempotencyRecord`, `WorkspaceLease` |
| Lineage | existing receipt/artifact/action fields |

## Rules

1. Reuse on-disk names before introducing new names.
2. Use Palantir terms directly when a new term is necessary.
3. No new synonym for Operator Brief, world_radar, runtime truth, or ontology.
4. No new canonical ledger while `RuntimeStateStore` can carry the receipt.
5. Promote only after tests prove lineage, policy, and idempotency.

## Operator actions

Any `ACTIVE_TRACK.yaml`, `ANTI_SLOP_RULES.md`, or `NAMING_CANON.md` edits are
operator-tier changes, not Stage-1 agent writes.
```

Optional test sketch:

```python
def test_runtime_records_are_the_operational_object_vocabulary():
    import dharma_swarm.runtime_state as rs
    required = [
        "SessionState", "TaskClaim", "DelegationRun", "WorkspaceLease",
        "ArtifactRecord", "MemoryFact", "MemoryEdge", "ContextBundleRecord",
        "OperatorAction", "SessionEventRecord", "RuntimeReceipt",
        "IdempotencyRecord",
    ]
    for name in required:
        assert hasattr(rs, name)
    assert not hasattr(rs, "LineageRecord")
    assert not hasattr(rs, "BaseObject")
```

Acceptance lint:

```bash
python -m py_compile dharma_swarm/runtime_state.py dharma_swarm/ontology.py dharma_swarm/ontology_runtime.py
pytest tests/test_runtime_record_ontology_mapping.py -q
grep -R "class OntologyManager\\|class LineageRecord\\|class BaseObject" dharma_swarm tests
```

Expected grep result:

- No matches for newly introduced `OntologyManager`, `LineageRecord`, or `BaseObject`.

Lane entry:

- No new lane needed for the first commit.
- Operator action only if desired later: attach ADR-009 as evidence under existing `substrate-nativeness` tracks, likely `runtime-truth-reconciliation-2026-06` or `orientation-graph-2026-06`.
