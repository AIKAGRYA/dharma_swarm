# Palantir Semantic Ontology Meta Scratchpad

Status: PROPOSED ONLY. This file is a scratchpad, not schema authority.

This note exists because the cleanup repeatedly found the same shape: useful
work is present, but the system cannot always answer "what kind of thing is
this, who owns it, what proof makes it real, and what action is allowed next?"
A Palantir-style semantic ontology is useful here only if it gives those
answers without adding another synonym layer.

## Local Anchors

- `docs/ontology/SEMANTIC_COMMONS.md` is the current naming entry point.
- `docs/ontology/semantic_objects.yaml` contains admitted semantic objects such
  as `A2ACard`, `AgentUID`, `NATSSubstrate`, `A2AInboxRoute`,
  `ModelKeyRouting`, `IntelligenceSupplyChainRawReceipt`, and
  `FrontierCouncilBoundarySignal`.
- `reports/audit/palantir_grade_ontology_roadmap_2026-06-16.md` already maps
  Palantir primitives to local primitives and explicitly warns against new
  `OntologyManager`, `BaseObject`, and `LineageRecord` abstractions.
- `dharma_swarm/ontology.py` owns schema/action definitions.
- `dharma_swarm/runtime_state.py` owns runtime records such as
  `ArtifactRecord`, `MemoryFact`, `MemoryEdge`, `OperatorAction`,
  `RuntimeReceipt`, and `IdempotencyRecord`.

## Intuition

The ontology should be a workbench for operational common sense:

- What is the thing?
- Who owns it?
- What state is it in?
- What evidence makes that state believable?
- What can act on it?
- What should happen next?
- What would make deletion safe?

If a proposed object cannot answer one of those questions, it is probably prose,
not an ontology type.

## Themes That Keep Appearing

1. Definition and runtime record are different. A gate definition is not a gate
   decision. An action type is not an action execution. A schedule definition is
   not proof the schedule fired.
2. Read models project truth from owners. Dashboards, onboard output, and
   cockpit cards should not become authority.
3. Receipts beat claims. A transport ACK, a generated report, or a file
   existence check is not automatically a semantic success.
4. Ownership matters more than location. Dirty work should land through an
   owning track, not through whatever worktree happens to contain it.
5. Purpose is missing. Many actions know the actor and artifact but not the
   declared purpose that justified access or mutation.
6. Deletion needs a type. "Delete this after cleanup" should be a governed
   object with preservation proof and operator approval, not an ad hoc note.
7. Bulk outputs need quarantine. Generated receipts are useful evidence, but
   promoting whole output directories makes the repo less intelligible.
8. Lineage fields already exist. The gap is reconstruction and tests, not a new
   `LineageRecord` table.

## Proposed Typed Objects

These are proposed object concepts only. Names should be admitted through
Semantic Commons before implementation.

| Proposed object | Palantir analogue | Why it exists | Minimum fields | Existing local anchor |
|---|---|---|---|---|
| WorktreeSnapshot | ObjectType | A point-in-time view of a worktree/clone for cleanup and collision reasoning | path, branch, head_sha, status_header, dirty_counts, upstream_state, captured_at | `git worktree list`, `git status -sb`, preservation `metadata.tsv` |
| PreservationReceipt | ObjectType | Proof that a worktree/stash/archive can be restored | preservation_root, bundle_paths, checksum_manifest, off_machine_target, verification_status | `BACKUP_RECEIPT.md` |
| KeeperPacket | ObjectType | Small coherent unit worth porting, distinct from whole worktree | source_path, class, owning_track, evidence_strength, verifier_command, port_status | `keeper_matrix.md` |
| DeletionCandidate | ObjectType | Explicit object for things that may be deleted only after approval | path, preservation_receipt, class, reason, approval_status, rollback_path | cleanup `OPERATOR_MAP.md` |
| OperatorDecision | ObjectType | Durable human choice that changes lifecycle | decision_id, actor, subject, allowed_action, rationale, timestamp, receipt_ref | existing governance reports |
| PurposeContext | ObjectType | The "why" behind an action, access, or mutation | purpose_id, actor, intended_outcome, data_scope, timebox, approving_track | no exact current type |
| SensitivityMarking | ObjectType | A data/artifact sensitivity label that travels with the object | marking_id, subject_ref, level, scope, propagation_rule, removal_rule | `SecurityPolicy`, guardian findings |
| PolicyDefinition | ObjectType | Versioned definition of a gate/check/rule | policy_id, version, owner, rules, inputs, outputs, lifecycle_status | `telos_gates.py`, hygiene rules, Guardian |
| PolicyDecision | ObjectType | Runtime result of evaluating a policy definition | decision_id, policy_id, policy_version, input_hash, result, obligations, timestamp | `GateDecisionRecord`, guardian findings |
| JustificationRecord | ObjectType | Actor's stated justification for a sensitive action | justification_id, actor, purpose_id, action_ref, prompt, response, accepted_by | WITNESS/gate logs |
| ObjectTypeDefinition | ObjectType | Governed object schema definition | api_name, version, owner, required_fields, status, deprecation | `ObjectType` in `ontology.py` |
| LinkTypeDefinition | LinkType | Governed relationship definition | api_name, source_type, target_type, cardinality, required_fields | `LinkDef`, `MemoryEdge` |
| ActionTypeDefinition | ActionType | Governed mutation/action contract | api_name, input_type, output_type, requires_approval, idempotency_rule | `ActionDef`, `OperatorAction` |
| ActionExecutionRecord | ObjectType | Runtime execution of an action type | action_id, action_type, actor, input_hash, result, pre_receipt, post_receipt | `ActionExecution`, `RuntimeReceipt` |
| FunctionContract | Function | Deterministic, replayable computation contract | function_id, inputs, outputs, deterministic, verifier, owner | `ontology_query.OntologyGraph`, governance scripts |
| PipelineRun | Pipeline | Receipted run of a data/code/report pipeline | pipeline_id, input_refs, output_refs, code_version, status, receipt_ref | `RuntimeReceipt`, `ArtifactRecord` |
| BranchContext | Branch | Minimal branch/workspace analogue for safe write-back | branch_ref, workspace_lease, base_sha, owner, intent, expiry | Git branch, `WorkspaceLease` |
| WriteBackContract | ActionType | Rule for mutating a truth owner without double effects | subject_type, allowed_writer, precondition, idempotency_key, rollback_rule | `IdempotencyRecord`, `RuntimeReceipt` |
| LineagePathProjection | Function | Read-only reconstruction of existing lineage fields | start_ref, end_ref, path_edges, missing_edges, confidence | receipt/artifact/action fields |
| SchedulerRegistry | ObjectType | Fleet schedule visibility without one global executor | registry_id, cron_planes, source_hierarchy, generated_at | ADR-010, `global_pulse_map.json` |
| CronPlane | ObjectType | One execution plane in the scheduler federation | owner, host, plane, source_path, liveness_rule | ADR-010 |
| CronEnvelope | ObjectType | Shared identity header for every scheduled job | owner, host, scope, plane, canonical_name, cadence, target, receipt_path | ADR-010 |
| ReconcilerVerdict | ObjectType | Scheduler reconciliation output bucket | subject_ref, verdict, reason, duplicate_refs, freshness | ADR-010 |
| AgentPresenceState | ObjectType | Two-axis liveness for transport and semantic readiness | agent_uid, transport_state, semantic_state, last_handler_ack, last_domain_receipt, last_semantic_receipt | A2A/NATS spec, presence projections |
| VerifierBoundarySignal | ObjectType | Meet-point between intake and decorrelated verifier | boundary_id, source_receipt_id, content_hash, verifier_interface, not_applied | `FrontierCouncilBoundarySignal` |
| ClaimMaturityAssessment | ObjectType | Evidence-strength view for track claims | claim_ref, maturity, criteria_strengths, warnings, generated_at | PR #685 track-strength report |

## Proposed Link Types

| Link | Source -> Target | Meaning |
|---|---|---|
| preserved_by | WorktreeSnapshot -> PreservationReceipt | This state can be restored from this receipt. |
| contains_packet | WorktreeSnapshot -> KeeperPacket | A worktree contains a coherent keeper packet. |
| owned_by_track | KeeperPacket -> ActiveTrack | Packet should land through this track. |
| requires_decision | DeletionCandidate -> OperatorDecision | No deletion without this decision. |
| justified_by | ActionExecutionRecord -> JustificationRecord | Sensitive action had explicit rationale. |
| evaluated_by | ActionExecutionRecord -> PolicyDecision | Runtime action passed or failed a policy. |
| instance_of | ActionExecutionRecord -> ActionTypeDefinition | Runtime action uses this action contract. |
| produced_by | ArtifactRecord -> PipelineRun | Artifact came from this run. |
| derived_from | ArtifactRecord -> ArtifactRecord | Lineage relation between artifacts. |
| scheduled_in | CronEnvelope -> CronPlane | Job belongs to this execution plane. |
| reconciled_as | CronEnvelope -> ReconcilerVerdict | Reconciler verdict for this job. |

## Proposed Action Types

| Action | Inputs | Output | Guard |
|---|---|---|---|
| classify_worktree | WorktreeSnapshot | KeeperPacket list plus class | no mutation; evidence-only |
| admit_keeper_packet | KeeperPacket | track-bound PR plan | owning track must exist or be proposed |
| mark_archive_only | KeeperPacket or WorktreeSnapshot | archive verdict | preservation receipt required |
| approve_deletion | DeletionCandidate | OperatorDecision | explicit operator approval required |
| promote_semantic_object | proposed object | admitted semantic object | name-drift preflight and owner approval |
| reconcile_scheduler_registry | SchedulerRegistry | ReconcilerVerdict set | read-only; no executor mutation |
| execute_write_back | ActionTypeDefinition plus payload | ActionExecutionRecord | idempotency key and pre/post receipts |

## Reasoning Notes

Definition-time objects should change rarely and carry owners. Runtime objects
should be abundant, timestamped, and easy to query. The mistake is mixing those
roles: a generated report says something happened, but a definition says what
kind of thing is allowed to happen.

For cleanup, `WorktreeSnapshot`, `KeeperPacket`, `PreservationReceipt`, and
`DeletionCandidate` would have prevented the original sprawl from turning into
an ambiguous "is it safe to delete?" question. The common-sense rule is simple:
delete only when the object says what it is, why it can go, where it is
preserved, and who approved it.

For runtime, `PurposeContext`, `PolicyDefinition`, `PolicyDecision`, and
`JustificationRecord` fill the "why was this allowed?" gap. Without purpose,
the system can prove a gate ran but not why the actor was entitled to attempt
the action.

For future proofing, `LineagePathProjection` should be a read-only function,
not a new ledger. The system already has correlation, causation, artifact,
runtime receipt, and action lineage fields. The right move is to reconstruct
paths from existing owners and emit warnings when the path is broken.

## Anti-Names

Do not introduce these as new canonical classes:

- `OntologyManager`
- `BaseObject`
- `LineageRecord`
- `GodRegistry`
- `UniversalLedger`
- `SchedulerDaemon`

The local roadmap is correct: the existing split between schema, runtime state,
persistence, query, adapters, agents, and read API is healthier than a singleton.

## Future-Proof Ideas

- Give every proposed object a lifecycle: `seed`, `proposed`, `admitted`,
  `promoted`, `deprecated`, `archived`.
- Make every promotion cite a verifier command and a rollback story.
- Keep generated receipts outside source promotion unless a small digest is
  explicitly curated.
- Treat dashboard cards as read models with source refs, not as truth owners.
- Make "no operator decision yet" a first-class state, not a failure.
- Let a cleanup cockpit render worktrees by class, preserved status, risk, and
  next action.
- Prefer boring fields over poetic names: owner, status, evidence, verifier,
  authority, next_action.
