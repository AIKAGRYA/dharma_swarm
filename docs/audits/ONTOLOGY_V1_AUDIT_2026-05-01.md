# Ontology v1 Audit - 2026-05-01

Scope: verification before schema edits, followed by minimal schema additions for parked Phase 2. Runtime remains parked.

Read order used:

1. Requested recovery path was absent: `docs/plans/SEMANTIC_ONTOLOGY_RECOVERY_2026-05-01.md`.
   Actual recovery document read in full: `docs/governance/ontology_v0_recovery_2026-05-01.md`.
2. `docs/plans/ontology-native-flow-001-insight-brief.md` read in full.
3. `~/dharma_briefs/MASTER_SYNTHESIS_2026-05-01.md` read in full.
4. `dharma_swarm/ontology.py` read in full.
5. `dharma_swarm/dharma_kernel.py` read in full.
6. `dharma_swarm/telos_gates.py` read in full.
7. `dharma_swarm/telic_seam.py` read in full.
8. `dharma_swarm/agent_runner.py` memory hooks located.
9. `.claude/worktrees/research-integration/dharma_swarm/world_actions.py` located and searched.
10. `~/.dharma/ontology.db` inspected with `sqlite3`.

Package-path correction: prompt paths such as `~/dharma_swarm/ontology.py` are shorthand. Actual module paths are under `~/dharma_swarm/dharma_swarm/`.

---

## Section A - Substrate-nativeness Ratio

Exact commands requested, run before schema edits:

| Metric | Command | Output |
|---|---|---:|
| Total Python files | `find /Users/dhyana/dharma_swarm -name "*.py" | wc -l` | 9545 |
| All ontology importers | `grep -rl "from dharma_swarm.ontology" /Users/dhyana/dharma_swarm/ | wc -l` | 162 |
| Production ontology importers | `grep -rl "from dharma_swarm.ontology" /Users/dhyana/dharma_swarm/ | grep -v test | wc -l` | 88 |
| Raw writes | `grep -rE "\.write_text|open\([^)]+['\"]w" /Users/dhyana/dharma_swarm/ | wc -l` | 4716 |

Computed ratio: `88 / 9545 = 0.009219`, or **0.92%**.

Verdict: the audit-claimed `~12%` is refuted by the exact requested denominator. The master synthesis's under-2% claim holds; this exact run refines it to 0.92%.

---

## Section B - Upper Objects Presence Check

The prompt says "16 upper objects" but lists 19 names. The actual recovery document describes a compact v0 upper ontology of about 18 types and explicitly says not to add `Memory` yet. This table follows the prompt's listed objects.

SQLite census before schema edits:

```text
AgentIdentity|23
Contribution|1803
KnowledgeArtifact|4
Outcome|1806
TypedTask|75
ValueEvent|1803
WitnessLog|4
```

| object | in ontology.py? | in ontology.db? | row count | gap |
|---|---|---|---:|---|
| HumanOperator | no | no | 0 | Not typed; recovery doc suggests singleton/authority distinction, currently absent. |
| Agent | yes, as `AgentIdentity` | yes | 23 | Name mismatch only; `AgentIdentity` is the runtime type. |
| ExternalWorker | no distinct type | no | 0 | Could be modeled as `AgentIdentity.role="worker"` but external boundary is absent. |
| Signal | no | no | 0 | Missing upper object. |
| Claim | no | no | 0 | Present in `dharma_corpus.py`, not in `ontology.py`. |
| Evidence | no | no | 0 | Provenance exists as a field on `KnowledgeArtifact`; no first-class `Evidence`. |
| Question | no | no | 0 | Missing upper object. |
| Doctrine | no | no | 0 | Kernel axioms exist; revisable Doctrine type is absent. |
| Gate | no ObjectType | no | 0 | Gate registry exists in `telos_gates.py`; no typed `Gate` object. |
| GateDecision | yes, as `GateDecisionRecord` | no | 0 | Schema exists; no rows in DB. |
| ActionProposal | yes | no | 0 | Schema exists; no rows in DB. |
| Action | partial: `ActionExecution` model and `ExecutionLease` ObjectType | no | 0 | No first-class `Action` ObjectType. |
| Artifact | partial: `KnowledgeArtifact` | yes via `KnowledgeArtifact` | 4 | Generic artifact name is not separately typed. |
| WitnessEvent | partial: `WitnessLog` | yes via `WitnessLog` | 4 | Name mismatch only. |
| Outcome | yes | yes | 1806 | Working. |
| ValueEvent | yes | yes | 1803 | Working. |
| Memory | no | no | 0 | Recovery doc says Memory is projection, not primitive. |
| KnowledgeArtifact | yes | yes | 4 | Working; brief flow writes this. |
| Capability | no | no | 0 | Absent from `ontology.py`; `identity.py` has no capability-token model to mirror. |

### Current Schema Catalog

Before edits, `OntologyRegistry.create_dharma_registry()` reports:

```text
types 16
links 48
actions 30
```

Registered ObjectTypes and live-row status:

| ObjectType | line | status |
|---|---:|---|
| ResearchThread | 858 | schema-only |
| Experiment | 887 | schema-only |
| Paper | 923 | schema-only |
| AgentIdentity | 951 | instantiated, 23 rows |
| CustodianRole | 1004 | schema-only |
| KnowledgeArtifact | 1065 | instantiated, 4 rows |
| TypedTask | 1110 | instantiated, 75 rows |
| EvolutionEntry | 1142 | schema-only |
| WitnessLog | 1175 | instantiated, 4 rows |
| ActionProposal | 1262 | schema-only |
| GateDecisionRecord | 1301 | schema-only |
| ExecutionLease | 1332 | schema-only |
| Outcome | 1372 | instantiated, 1806 rows |
| ValueEvent | 1402 | instantiated, 1803 rows |
| Contribution | 1438 | instantiated, 1803 rows |
| VentureCell | 1468 | schema-only |

Registered LinkDefs before edits:

```text
ResearchThread.has_experiment -> Experiment
Experiment.produces -> KnowledgeArtifact
Paper.cites -> KnowledgeArtifact
TypedTask.assigned_to -> AgentIdentity
TypedTask.consumes -> KnowledgeArtifact
TypedTask.task_produces -> KnowledgeArtifact
TypedTask.depends_on -> TypedTask
ResearchThread.contributes_to -> Paper
AgentIdentity.authored -> KnowledgeArtifact
AgentIdentity.proposed_evolution -> EvolutionEntry
AgentIdentity.witnessed -> WitnessLog
KnowledgeArtifact.informs_experiment -> Experiment
KnowledgeArtifact.derived_from -> Outcome
KnowledgeArtifact.cites_witness -> WitnessLog
KnowledgeArtifact.published_to -> KnowledgeArtifact
ActionProposal.has_gate_decision -> GateDecisionRecord
ActionProposal.has_execution_lease -> ExecutionLease
ActionProposal.has_outcome -> Outcome
ActionProposal.executed_by_agent -> AgentIdentity
ActionProposal.belongs_to_cell -> VentureCell
VentureCell.cell_has_agent -> AgentIdentity
VentureCell.cell_has_thread -> ResearchThread
Outcome.has_value_event -> ValueEvent
ValueEvent.has_contribution -> Contribution
```

Each LinkDef with `inverse_name` auto-registers its inverse, producing 48 registered links.

Registered ActionDefs before edits:

```text
ActionProposal.Approve
ActionProposal.Propose
ActionProposal.Reject
AgentIdentity.Retire
AgentIdentity.Spawn
Contribution.Record
CustodianRole.Refresh
EvolutionEntry.Promote
EvolutionEntry.Propose
EvolutionEntry.Revert
ExecutionLease.Record
Experiment.Archive
Experiment.Design
Experiment.Run
GateDecisionRecord.Record
KnowledgeArtifact.Index
KnowledgeArtifact.Publish
KnowledgeArtifact.Verify
Outcome.Record
Paper.Audit
Paper.Submit
ResearchThread.Activate
ResearchThread.Pause
TypedTask.Assign
TypedTask.Complete
TypedTask.Fail
ValueEvent.Record
VentureCell.Advance
VentureCell.Create
WitnessLog.Record
```

SecurityPolicies before edits:

| ObjectType | policy |
|---|---|
| ResearchThread | default |
| Experiment | default |
| Paper | `write_roles=["researcher", "system"]`, `audit_all=True` |
| AgentIdentity | `create_roles=["orchestrator", "system"]`, `delete_roles=["system"]` |
| CustodianRole | `create_roles=["system"]`, `write_roles=["system"]`, `delete_roles=["system"]`, `audit_all=True` |
| KnowledgeArtifact | default |
| TypedTask | default |
| EvolutionEntry | `telos_required=True`, `audit_all=True` |
| WitnessLog | `write_roles=["*"]`, `delete_roles=[]`, `audit_all=True` |
| ActionProposal | `audit_all=True` |
| GateDecisionRecord | `write_roles=["orchestrator", "system"]`, `delete_roles=[]`, `audit_all=True` |
| ExecutionLease | `audit_all=True` |
| Outcome | `audit_all=True` |
| ValueEvent | `audit_all=True` |
| Contribution | `audit_all=True` |
| VentureCell | `create_roles=["orchestrator", "system"]`, `telos_required=True`, `audit_all=True` |

### Kernel Axioms

`dharma_kernel.py` defines 25 `MetaPrinciple` axioms. `DharmaKernel.create_default()` computes a SHA-256 signature over sorted JSON. Live computed signature before edits:

```text
3836e355920ca25129813a126e27d3f2de56ea6a5586ecaf5c73534815a7a53f
```

Quoted axiom names and formal constraints:

```text
1. Observer Separation | observer_id != observed_id in all self-referential operations
2. Epistemic Humility | confidence < 1.0 for all non-tautological assertions
3. Uncertainty Representation | all outputs include calibrated confidence intervals
4. Downward Causation for Safety | proposer_layer >= target_layer for constraint operations; lower layers may propose but not override safety
5. Power Minimization | permissions_requested <= permissions_required
6. Reversibility Requirement | irreversible_action implies justification_provided
7. Multi-Evaluation Requirement | evaluator_count >= 2 for significance_level > threshold
8. Non-Violence in Computation | destructive_op implies (consent_given and justification_provided)
9. Human Oversight Preservation | oversight_channel.is_active() == True at all times
10. Provenance Integrity | output.provenance is not None for all emitted artifacts
11. Eigenform Convergence (S(x) = x) | recursive_depth(system) implies convergence_check()
12. Anekantavada (Many-Sidedness) | conclusion requires evaluations_from_distinct_perspectives >= 2
13. Triple Mapping (Swabhaav = L4 = R_V < 1.0) | cross_track_claims require evidence from >= 2 measurement domains
14. Multi-Scale Creative Agency | agent_at_scale(N) has autonomous_goals AND respects constraints_from(N+1)
15. Autocatalytic Closure | catalytic_graph has >= 1 strongly_connected_component
16. Adjacent Possible Exploration | evolution_archive.generations > 0 AND proposals_per_cycle >= 1
17. Constraint as Enablement | gate.rejection includes suggested_alternative
18. Requisite Variety | len(available_agents) >= len(distinct_task_types)
19. Recursive Viability | subsystem has {operations, coordination, control, adaptation, identity}
20. Active Inference | action_selection minimizes expected_free_energy
21. Structural Coupling | agent_communication via shared_state NOT direct_call
22. Operational Closure | system.produces(system.components) AND system.produces(system.boundary)
23. Alignment Through Resonance | alignment_score computed from resonance NOT compliance
24. Colony Intelligence (Aunt Hillary Principle) | swarm_output != any_single_agent_output
25. Shakti Questions (Four Creative Forces) | significant_action requires shakti_check >= 2_of_4
```

### Telos Gates

`TelosGatekeeper.CORE_GATES` defines 11 gates by tier:

| tier | gates |
|---|---|
| A | `AHIMSA` |
| B | `SATYA`, `CONSENT` |
| C | `VYAVASTHIT`, `REVERSIBILITY`, `SVABHAAVA`, `BHED_GNAN`, `WITNESS`, `ANEKANTA`, `DOGMA_DRIFT`, `STEELMAN` |

---

## Section C - The Five Killers

### Killer 1 - Is `world_actions.github_*` gated by TelosGatekeeper?

Command:

```text
grep -n "TelosGatekeeper\|gatekeeper\.check" /Users/dhyana/dharma_swarm/.claude/worktrees/research-integration/dharma_swarm/world_actions.py
```

Output: empty.

Confirmed killer. `world_actions.py` exists only in `.claude/worktrees/research-integration/`, not primary package checkout. Bypass surface counts:

```text
github_commit_push occurrences: 6
github_create_pr occurrences: 6
write_text occurrences: 5
open(..., "w") occurrences: 0
```

Line evidence:

```text
126:def github_commit_push(...)
172:def github_create_pr(...)
249:(root / "index.html").write_text(...)
250:(root / "styles.css").write_text(...)
271:dest.write_text(...)
279:(out_dir / f"{_slug(dest.stem)}.manifest.json").write_text(...)
305:spec_path.write_text(...)
```

### Killer 2 - Legacy `Entity` dict around ontology.py lines 1542-1716?

Confirmed, but current file already carries the required label:

```text
1562 # BACKWARD COMPATIBILITY - Existing Entity/ONTOLOGY API
1564 # DEPRECATED: legacy hand-coded ontology scheduled for removal on 2026-05-08.
1565 # The typed ObjectType/OntologyObj registry above is the schema authority.
1569 class Entity:
1585 def _build_ontology() -> dict[str, Entity]:
1722 ONTOLOGY: dict[str, Entity] = _build_ontology()
```

No deletion performed per C3.

### Killer 3 - TelosGatekeeper.check() predicate logic

Verdict: multi-layer heuristic gate with substring matching at the AHIMSA fast path and other pattern checks. It is not semantic evaluation.

Verbatim predicate excerpt from `TelosGatekeeper.check()`:

```python
        resolved_mode = (
            (trust_mode or os.getenv("DGC_TRUST_MODE", "internal_yolo"))
            .strip()
            .lower()
        )
        # -- S4->S3 feedback: zeitgeist gate pressure override --
        resolved_mode = self._apply_gate_pressure(resolved_mode)
        action_lower = action.lower()
        content_lower = content.lower()
        combined = action_lower + " " + content_lower
        results: dict[str, tuple[GateResult, str]] = {}

        # --- AHIMSA (Tier A) -- harm + injection detection ---
        harm_hit = next((w for w in self.HARM_WORDS if w in action_lower), None)
        injection_hit = next(
            (p for p in self.INJECTION_PATTERNS if p in combined), None,
        )
        strict_hit = None
        if resolved_mode == "external_strict":
            strict_hit = next(
                (p for p in self.STRICT_SECURITY_PATTERNS if p in combined),
                None,
            )

        if strict_hit:
            results["AHIMSA"] = (
                GateResult.FAIL,
                f"Strict security intent detected: {strict_hit}",
            )
        elif harm_hit:
            results["AHIMSA"] = (GateResult.FAIL, f"Harmful: {harm_hit}")
        elif injection_hit:
            results["AHIMSA"] = (
                GateResult.FAIL, f"Injection detected: {injection_hit}",
            )
        else:
            results["AHIMSA"] = (GateResult.PASS, "")

        # --- SATYA (Tier B) -- deception + credential leak prevention ---
        deception_hit = next(
            (p for p in self.DECEPTION_PATTERNS if p in combined), None,
        )
        if deception_hit:
            results["SATYA"] = (
                GateResult.FAIL, f"Deceptive request: {deception_hit}",
            )
        elif content:
            cred_hit = next(
                (p for p in self.CREDENTIAL_PATTERNS if p in content), None,
            )
            if cred_hit:
                results["SATYA"] = (
                    GateResult.FAIL, f"Credential in content: {cred_hit[:10]}...",
                )
            else:
                results["SATYA"] = (GateResult.PASS, "")
        else:
            results["SATYA"] = (GateResult.PASS, "")

        # --- CONSENT (Tier B) -- block sensitive data exfiltration attempts ---
        sensitive_hit = next(
            (p for p in self.SENSITIVE_PATH_PATTERNS if p in combined), None,
        )
        exfil_hit = next(
            (p for p in self.EXFIL_PATTERNS if p in combined), None,
        )
        if sensitive_hit and exfil_hit:
            results["CONSENT"] = (
                GateResult.FAIL,
                f"Sensitive data exfiltration attempt: {sensitive_hit} -> {exfil_hit}",
            )
        else:
            results["CONSENT"] = (GateResult.PASS, "Permission system active")

        # --- VYAVASTHIT (Tier C) -- force detection ---
        force_hit = next(
            (w for w in self.FORCE_WORDS if w in action_lower), None,
        )
        if force_hit:
            results["VYAVASTHIT"] = (GateResult.FAIL, f"Forcing: {force_hit}")
        else:
            results["VYAVASTHIT"] = (GateResult.PASS, "")

        # --- REVERSIBILITY (Tier C) -- irreversible operation warning ---
        irrev_hit = next(
            (w for w in self.IRREVERSIBLE_WORDS if w in action_lower), None,
        )
        if irrev_hit:
            results["REVERSIBILITY"] = (
                GateResult.WARN, f"Irreversible: {irrev_hit}",
            )
        else:
            results["REVERSIBILITY"] = (GateResult.PASS, "")

        # --- SVABHAAVA (Tier C) -- telos alignment via Anekanta ---
        anekanta = evaluate_anekanta(action, content)
```

Decision logic excerpt:

```python
        tier_a_fail = any(
            results[g][0] == GateResult.FAIL
            for g in self.GATES
            if self.GATES[g] == GateTier.A
        )
        tier_b_fail = any(
            results[g][0] == GateResult.FAIL
            for g in self.GATES
            if self.GATES[g] == GateTier.B
        )

        if tier_a_fail:
            failing_gate = next(
                g
                for g in self.GATES
                if self.GATES[g] == GateTier.A and results[g][0] == GateResult.FAIL
            )
            reason = results[failing_gate][1]
            return GateCheckResult(
                decision=GateDecision.BLOCK,
                gate=failing_gate,
                reason=f"AHIMSA violation: {reason}",
                gate_results=results,
            )

        if tier_b_fail:
            failing_gates = [
                g
                for g in self.GATES
                if self.GATES[g] == GateTier.B and results[g][0] == GateResult.FAIL
            ]
            reasons = [
                results[g][1]
                for g in failing_gates
            ]
            return GateCheckResult(
                decision=GateDecision.BLOCK,
                gate=failing_gates[0] if failing_gates else "",
                reason=f"Tier B violation: {'; '.join(reasons)}",
                gate_results=results,
            )
```

### Killer 4 - VentureCell exists, Ginko instantiation?

Confirmed.

`VentureCell` ObjectType exists at `ontology.py:1468`. There are 17 `ginko_*.py` modules. Search results show only textual references in `ginko_orchestrator.py`; no `create_object("VentureCell", ...)` in any Ginko module. `ontology.py` has the only factory: `create_ginko_cell()` at line 1785. DB row count is zero.

### Killer 5 - External

Skipped per prompt.

---

## Section D - Directors Bypass Check

Command:

```text
grep -n "ontology" dharma_swarm/thinkodynamic_director.py | head -20
```

Output:

```text
293:        "ontology": 3.0,
449:            "own audits say the ontology, corpus, and governance families are "
2641:                        "ontology or corpus still sits off-path, and which missing "
```

Command:

```text
grep -n "ontology\|telic_seam\|TelosGatekeeper" dharma_swarm/overnight_director.py | head -20
```

Output: empty.

Report: `thinkodynamic_director.py` only has prose/weight references. `overnight_director.py` has no ontology, telic seam, or gatekeeper references. Both are substrate bypasses in the audit sense. No code changes made to directors per C1.

---

## Section E - Three Phase-2-Aware Additions

Pre-change status:

| type | status |
|---|---|
| Cause | Not yet present. Schema add proposed in Deliverable 2. |
| Movement | Not yet present. Schema add proposed in Deliverable 2. |
| R_V_Measurement | Not yet present. Schema add proposed in Deliverable 2. |

---

## Section F - Substantive Dissent

1. The specified recovery-doc path is wrong. Actual path is `docs/governance/ontology_v0_recovery_2026-05-01.md`.
2. The specified module paths are shorthand. Actual files live under `dharma_swarm/dharma_swarm/`.
3. The prompt says "16 upper objects" but lists 19 names. The v0 recovery doc itself says compact upper ontology around 18 types and says not to type `Memory` yet.
4. `identity.py` does not contain a Capability or time-boxed capability-token model. A search for `Capability`, `capability`, `expires`, `ttl`, and token-shape terms found no such source pattern.
5. `ontology.py` changed during this audit before my edits: line count moved from 1822 to 1849 and brief-flow schema additions appeared (`KnowledgeArtifact.Publish`, `derived_from`, `cites_witness`, `published_to`, and the Entity deprecation comment). I preserved those changes.

---

## Post-Change Summary

Files modified:

| path | line count | note |
|---|---:|---|
| `dharma_swarm/ontology.py` | 2255 | Added schema-only ObjectTypes and `RecordRVMeasurement`; no runtime wiring. |
| `tests/test_ontology_registry.py` | 610 | Updated stale hardcoded registry type list/count. No new Phase-2 tests added. |
| `docs/audits/ONTOLOGY_V1_AUDIT_2026-05-01.md` | 569 | Verification audit and final report. |
| `docs/causes/PARKED_CAUSES.md` | 27 | Parking lot for the 18 seeds. |
| `~/.dharma/ontology.db` | n/a | Inserted exactly one `Cause` object row. |

New ObjectTypes added for Deliverable 2.1: **3** (`Cause`, `Movement`, `R_V_Measurement`).

Additional first-class schema promotions required by Deliverable 2.2 because they were absent: `Claim`, `Doctrine`, `Capability`.

Additional concurrent upper-object schemas present in final file: `Signal`, `Question`, `Evidence`.

New ActionDef added: `R_V_Measurement.RecordRVMeasurement`.

Cause rows in `ontology.db`:

```text
$ sqlite3 ~/.dharma/ontology.db "select count(*) from objects where type_name='Cause'"
1
```

Inserted Cause row:

```text
cause_001_insight_brief|Cause|active|/Users/dhyana/dharma_briefs/MASTER_SYNTHESIS_2026-05-01.md
```

Substrate-nativeness ratio: **0.92%** (`88 / 9545`).

Five killers status:

| killer | status | evidence |
|---|---|---|
| K1 world_actions github bypass | confirmed | `grep -n "TelosGatekeeper\|gatekeeper\.check" .../world_actions.py` returned empty; `github_commit_push` at line 126, `github_create_pr` at line 172. |
| K2 legacy Entity/ONTOLOGY dict | confirmed but labeled deprecated | `ontology.py` now has deprecation comment at lines 1564-1565; no deletion performed. |
| K3 TelosGatekeeper substring gate | confirmed with nuance | AHIMSA uses substring `in` checks; additional heuristic layers exist. |
| K4 VentureCell schema-only | confirmed | ObjectType exists; no Ginko module instantiates it; DB row count zero. |
| K5 external | skipped | Out of repo scope per prompt. |

Brief flow still buildable: **yes**.

Evidence:

```text
pytest -q tests/test_insight_brief.py tests/test_ontology_registry.py tests/test_telic_seam.py tests/test_ontology_hub.py
160 passed, 1 warning in 0.74s
```

Registry sanity:

```text
25 True True True 86 36
```

This means the registry has 25 ObjectTypes, `Cause` exists, `Movement` exists, `R_V_Measurement.RecordRVMeasurement` exists, and the registry has 86 links plus 36 actions.

Phase 2 readiness: **schema breathing, runtime parked**. No edits were made to `telic_seam.py`, `world_actions.py`, `thinkodynamic_director.py`, or `overnight_director.py`. No `CreateCause`, `CreateMovement`, `InstantiateMovement`, or gateway/runtime Cause wiring was added.
