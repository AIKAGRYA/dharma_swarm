# Pass 3b — Governance Code Walk

**Produced by:** Governance Pass B agent (code-walker)
**Date:** 2026-06-02
**Charter ref:** `00-swarm-charter.md`
**Posture:** Evidence only. No name proposals. Ground proposed governance vocabulary types in what code already contains vs. what is structurally absent.

---

## 1. Files Walked

**Gate system:**

| File | One-line purpose |
|---|---|
| `dharma_swarm/telos_gates.py` | TelosGatekeeper: 11 core named gates (AHIMSA/SATYA/CONSENT/VYAVASTHIT/REVERSIBILITY/SVABHAAVA/BHED_GNAN/WITNESS/ANEKANTA/DOGMA_DRIFT/STEELMAN), GateProposal, GateRegistry (variety expansion), ReflectiveGateOutcome. |
| `dharma_swarm/telic_seam.py` | TelicSeam: write-through from orchestrator to ontology; records ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution. |
| `dharma_swarm/models.py` | Canonical shared schema: GateTier (A/B/C), GateResult (PASS/FAIL/WARN), GateDecision (ALLOW/BLOCK/REVIEW), GateCheckResult. No actor/purpose fields anywhere. |
| `dharma_swarm/ontology.py` | Full ontology engine: ActionDef, SecurityPolicy, ObjectType meta-schema; ActionExecution audit record; registered domain types including ActionProposal, GateDecisionRecord. |

**Action definition surface:**

| File | One-line purpose |
|---|---|
| `dharma_swarm/guardrails.py` | ActionTypeGuardrail class that validates tool/action calls against ontology ActionDef rules; checks actor permission and telos gate list. |
| `dharma_swarm/ontology.py` | `ActionDef` (meta-schema for typed transactional mutations): name, object_type, description, input_params, modifies, creates, requires_approval, telos_gates, is_deterministic. `execute_action()` runs it. |

**Policy / actor / purpose:**

| File | One-line purpose |
|---|---|
| `dharma_swarm/ai_reciprocity_ledger.py` | AIActor (actor_id, actor_name, ActorType) and ActivityRecord (actor_id) — the only explicit actor identity model found. Domain-specific, not wired into execute_action. |
| `dharma_swarm/agent_constitution.py` | AgentSpec with `constitutional_gates` list — per-agent gate subset binding. Closest existing concept to per-actor policy binding. |
| `dharma_swarm/ontology.py` | `SecurityPolicy` (per-ObjectType): read_roles, write_roles, create_roles, delete_roles, classification (SecurityLevel enum), field_restrictions, audit_all, telos_required. Role strings, not structured actor objects. |
| `dharma_swarm/guardrails.py` | GuardrailContext carries action, tool_name, content — no purpose or actor_id threading. |

**Security marking / classification:**

| File | One-line purpose |
|---|---|
| `dharma_swarm/ontology.py` | `SecurityLevel` enum: PUBLIC / INTERNAL / RESTRICTED / DHARMIC — 4-value classification attached to ObjectType schemas, not to instances. |
| `dharma_swarm/ontology.py` | `SecurityPolicy.classification` field on ObjectType: sets the security level of a type schema. No per-instance classification field anywhere. |
| `dharma_swarm/adaptive_autonomy.py` | `RiskLevel` enum: SAFE / LOW / MEDIUM / HIGH / CRITICAL — risk classification for an action, used in autonomy adjustment engine. Not persisted to ontology. |

**Compliance and checkpoint surface:**

| File | One-line purpose |
|---|---|
| `docs/COMPLIANCE_MAPPING.md` | Maps 11 gates to NIST AI RMF, ISO 27001, SOC 2, EU AI Act. Governance docs cite gate decision logs as audit evidence. |
| `docs/governance/CI_GATES.md` | Four CI workflows: Fourfold Shakti Warrant, CodeQL, Semgrep, Gitleaks. Warrant outputs reports/governance/fourfold-warrant.*. `[impact-checked]` in PR body is the explicit acknowledgment mechanism. |
| `docs/governance/FOURFOLD_ACTION_WARRANT.md` | Warrant check: four Shakti questions, BLOCK/HOLD/WARN verdicts, diff-bound scoring. Notes that future integrations "may attach the warrant to ActionProposal or GateDecisionRecord" — currently read-only. |
| `dharma_swarm/mission_contract.py` | `HonorsCheckpoint` (CompletionContract + DefensePacket + JudgePack), `JudgeGate` (name, passed, score, reason), `JudgePack` (accepted, final_score, gate_failures, gates list, summary). Per-completion quality gate. |
| `dharma_swarm/agent_runner_quality.py` | Imports and uses HonorsCheckpoint in the completion assessment flow. This is a Checkpoint in the quality-assurance sense, not the Foundry-style data governance sense. |

---

## 2. What the Gate Code Actually Models Today

### `GateCheckResult` (the runtime verdict struct)
**Defined in:** `dharma_swarm/models.py:GateCheckResult`

```
GateCheckResult (Pydantic BaseModel):
  decision: GateDecision        # ALLOW | BLOCK | REVIEW
  reason: str                   # human-readable explanation of the overall verdict
  gate: str                     # which gate fired (first failing gate name, or "")
  gate_results: dict[str, tuple[GateResult, str]]
                                # per-gate: gate_name -> (PASS|FAIL|WARN, reason_string)
  timestamp: datetime           # when the check ran
```

**What is structurally absent:** No actor_id. No purpose. No proposal context. No subject (what resource was being evaluated). The check function signature in `telos_gates.py:TelosGatekeeper.check()` takes `action: str`, `content: str`, `tool_name: str`, `trust_mode: str | None`, `think_phase: str | None`, `reflection: str`. None of these are structured: they are all raw strings.

### Gate-as-object representation
The **gate definitions** are not ontology objects. They live as:
- `CORE_GATES: dict[str, GateTier]` — a class-level dict on `TelosGatekeeper` (a dict of name→tier only)
- `GateProposal` (dataclass) — for custom variety-expansion proposals only: name, tier, justification, trigger_patterns, proposed_by, status, review_note
- `GateRegistry` — manages JSONL persistence of `GateProposal` objects

The **five core gates** (AHIMSA, SATYA, CONSENT, etc.) have **no dataclass/Pydantic instance**. They exist only as keyword sets (HARM_WORDS, INJECTION_PATTERNS, DECEPTION_PATTERNS, etc.) hardcoded on `TelosGatekeeper`. A gate as an **ontology-queryable object** does not exist for core gates — only for proposed custom gates.

### `GateDecisionRecord` (the ontology persisted form)
**Defined in:** `dharma_swarm/ontology.py` (ObjectType registration, ~line 1280)

```
GateDecisionRecord ObjectType properties:
  proposal_id: str (required, immutable)
  decision: enum["allow", "block", "review"] (required)
  reason: str
  gate_results: dict (per-gate PASS/FAIL/WARN results)
  witness_reroutes: int (number of reflective reroute attempts)
```

**Written by:** `telic_seam.py:TelicSeam.record_gate_decision()` immediately after the gate suite runs.

**Producer → consumer chain:**
```
TelosGatekeeper.check()
  → GateCheckResult (in-memory, models.py)
    → TelicSeam.record_gate_decision()
      → GateDecisionRecord (OntologyObj, ontology.py)
        → linked to ActionProposal via "has_gate_decision" link
          → ActionProposal status updated (approved / rejected / gated)
```

### Witness log (think-point)
The WITNESS gate writes to `~/.dharma/witness/witness_YYYYMMDD.jsonl` via `TelosGatekeeper._log_witness()`. The JSONL entry shape is:
```json
{"ts": "...", "phase": "...", "outcome": "PASS|BLOCKED|WARN", "action": "...", "reflection": "..."}
```
This is a flat JSON file, not an OntologyObj. The `WitnessLog` ObjectType exists in `ontology.py` but `_log_witness()` writes directly to the filesystem, not to the ontology registry. **These are decoupled.**

---

## 3. The Gate's Blind Spots in Code

### 3a. No actor or purpose threading
`TelosGatekeeper.check()` takes `action: str` and `content: str`. Neither carries who is requesting the action (actor_id) or why (purpose/intent). The gate cannot answer "did user X, acting in role Y for purpose Z, pass gate G on resource R?" because none of {X, Y, Z, R} are typed fields in the gate evaluation.

**What would need to change:** `GateCheckResult` would need `actor_id: str`, `actor_role: str`, `purpose: str`, `resource_id: str | None` added. `TelosGatekeeper.check()` would need these parameters. `GateDecisionRecord` in `ontology.py` would need matching PropertyDef entries.

### 3b. No gate-definition-as-object for core gates
`CORE_GATES` is a class-level `dict[str, GateTier]`. An agent cannot query "what is the historical pass rate of AHIMSA?" through the ontology because AHIMSA is not an ontology object. The `GateProposal` dataclass exists for proposed custom gates, but there is no `TelosGateDef` ontology type.

**What would need to change:** A `TelosGateDef` ObjectType would need to be registered with properties: name, tier, trigger_patterns, historical_pass_rate, compliance_mappings. Core gates would need to be seeded as instances at boot.

### 3c. The verdict space is ALLOW/BLOCK/REVIEW — no PENDING_APPROVAL, no ACKNOWLEDGED
Foundry Checkpoints have: acknowledged, requires_acknowledgment, justification text attached to the action. The current system has no mechanism for a human operator to attach a named acknowledgment to a gate decision. REVIEW is advisory and produces no durable acknowledgment artifact. The `[impact-checked]` mechanism in CI_GATES.md is a PR-body string, not a typed object.

**What would need to change:** `GateDecision` enum would need `PENDING_APPROVAL` and/or `ACKNOWLEDGED` states. A new `GateAcknowledgment` OntologyObj would need: gate_decision_id, acknowledged_by, acknowledged_at, justification_text. `GateDecisionRecord` would need a link to `GateAcknowledgment`.

### 3d. No justification field on GateDecisionRecord
The `reason` field carries the gate's explanation of why it blocked/allowed. But there is no field for the **requesting actor's stated justification** — the human-or-agent reason for why the action should be permitted despite the gate advisory. In Foundry, justification text is attached to the action request before evaluation. Here, the `reflection` string is checked for sufficiency but not persisted to the GateDecisionRecord.

**What would need to change:** Add `justification: str` (actor-supplied) to `GateDecisionRecord` properties in `ontology.py`. Add `justification: str` parameter to `TelicSeam.record_gate_decision()`.

### 3e. WitnessLog ObjectType and JSONL file are decoupled
The `WitnessLog` ObjectType is registered in `ontology.py` with `audit_all=True`. But `TelosGatekeeper._log_witness()` writes to filesystem JSONL directly, not to the ontology registry. The ontology `WitnessLog` type has zero production instances from the gate system.

**What would need to change:** `_log_witness()` should call `TelicSeam` (or a direct `OntologyRegistry.create_object("WitnessLog", ...)`) after writing to the filesystem file. The filesystem log and ontology record should both be written.

---

## 4. Action Definition in Code

### Does an `actionDefinition` concept already exist?

**Yes, partially.** `ActionDef` in `dharma_swarm/ontology.py` (lines 129–144) is the meta-schema for a typed action:

```python
class ActionDef(BaseModel):
    name: str
    object_type: str                    # which ObjectType this action applies to
    description: str = ""
    input_params: dict[str, str]        # param_name -> type_string (not typed)
    modifies: list[str]                 # property names this action can change
    creates: list[str]                  # type names this action can create
    requires_approval: bool = False
    telos_gates: list[str]             # gate names required for this action
    is_deterministic: bool = True
```

**Key findings:**
- `ActionDef` is a **schema-level** definition, not a runtime instance. It describes what a type of action IS; `ActionExecution` is the audit record of what was DONE.
- `ActionDef` is registered per-type: `OntologyRegistry.register_action(action_def)` keyed as `"{object_type}.{action_name}"`.
- `ActionDef.requires_approval` is a boolean flag, not a structured approval workflow. There is no `approver_role`, no `approval_record`, no approval lifecycle.
- `ActionDef.telos_gates` is a list of gate name strings, not a structured binding — no purpose context, no actor restriction.
- `ActionDef.input_params` is `dict[str, str]` (param_name → type_string). It is not typed with PropertyDef — it is looser than the rest of the schema.
- **Versioning:** There is no version field on `ActionDef`. The parent `ObjectType` has `version: int = 1`, but ActionDef inherits no version of its own.

**How it differs from `ActionProposal`/`proposal`:**
- `ActionDef` = the governed declaration of what an action IS (schema layer, static, registered at boot)
- `ActionProposal` (OntologyObj) = the runtime request to execute an action (data layer, dynamic, created per dispatch)

**Where `ActionDef` would land naturally as a vocabulary type:** It already exists. The gap is that it is not itself a first-class `OntologyObj` — it is a schema artifact embedded in `ObjectType.actions`. To make it queryable at runtime, `ActionDef` instances would need to be seeded as OntologyObjs of type `ActionDefinition` at boot. The closest native struct to bridge from is `ontology.py:ActionDef`.

### `ActionTypeGuardrail` in `guardrails.py`
The `ActionTypeGuardrail` (lines 323–349) claims to validate against ontology ActionDef rules but its implementation is reduced to a keyword check for "dangerous tools" (bash, shell, exec, eval, subprocess). It does not actually look up the `ActionDef` in the registry or check the actor's role. The class name overpromises relative to what the code does.

---

## 5. Policy / Purpose / Actor Context in Code

### Threading status: **structurally absent at the gate and execute_action layers**

`OntologyRegistry.execute_action()` signature (lines 594–639):
```python
def execute_action(
    self,
    object_type: str,
    action_name: str,
    object_id: str,
    params: dict[str, Any],
    executed_by: str = "system",          # ← only actor info: a string, not a typed object
    gate_check: Callable | None = None,
) -> ActionExecution
```

`executed_by` is a bare string — not a structured actor object. No `purpose`, no `role` in the execution context. The `ActionExecution` audit record (lines 210–224) carries `executed_by: str`, `input_params: dict`, `gate_results: dict[str, str]` — all stringly-typed.

### Closest existing actor model: `AIActor` in `ai_reciprocity_ledger.py`
```python
class AIActor(BaseModel):
    actor_id: str
    actor_name: str
    actor_type: ActorType   # an enum in the ledger module
```
This exists only in `ai_reciprocity_ledger.py` for the economic reciprocity domain. It is not imported by `telic_seam.py`, `telos_gates.py`, or `ontology.py`.

### Closest existing policy concept: `SecurityPolicy` on ObjectType
`SecurityPolicy` defines role-based access (read_roles, write_roles, etc.) as lists of strings. It is enforced by `check_security(obj_type, agent_role, operation)` which checks whether `agent_role` is in the allowed list. This is type-level role gating, not action-level or purpose-aware access control.

### `AgentSpec.constitutional_gates` in `agent_constitution.py`
Each AgentSpec has `constitutional_gates: list[str]` — a subset of the 11 gates that agent is bound by. This is the closest concept to a per-actor policy binding. It is not persisted to the ontology and is not checked at runtime by the gate suite (the gate suite checks all gates regardless of which agent is calling).

### Is `execute_action` purpose-aware? Actor-aware? 
**No to both.** The `executed_by` string is recorded in `ActionExecution` but not used for any policy check. Purpose is not threaded anywhere. An agent executing a destructive action "as system" is indistinguishable from an operator doing the same.

---

## 6. Security Marking in Code

### Status: **schema-level only, no per-instance security objects**

**`SecurityLevel` enum** (`ontology.py`, lines 80–84):
```python
class SecurityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    DHARMIC = "dharmic"
```

This 4-value enum is attached to **ObjectType schemas** (via `SecurityPolicy.classification`), not to individual OntologyObj instances. A specific `ActionProposal` or `GateDecisionRecord` cannot itself be marked as RESTRICTED — only the type schema can be.

**No `SecurityMarking` object exists anywhere in the codebase.** There is no class named SecurityMarking, DataClassification, DataLabel, or equivalent. The compliance doc (`COMPLIANCE_MAPPING.md`) cites "Data sensitivity checked before mutation" as ISO 27001 A.8.2 evidence, pointing to `telos_gates.py:AHIMSA` as the control — but AHIMSA does keyword matching on action/content strings, not classification-label checking on objects.

**`RiskLevel` enum** in `dharma_swarm/adaptive_autonomy.py` (SAFE/LOW/MEDIUM/HIGH/CRITICAL) classifies action risk for autonomy adjustment. It is not persisted, not queryable, not linked to gate decisions.

**Ad-hoc sensitivity patterns** exist on `TelosGatekeeper`:
- `SENSITIVE_PATH_PATTERNS`: `/etc/passwd`, `/etc/shadow`, `.ssh/id_rsa`, `.aws/credentials`
- `CREDENTIAL_PATTERNS`: `sk-or-v1-`, `AKIA`, `ghp_`, etc.

These are hardcoded sets, not a typed marking system. A resource does not carry a classification label; the gate checks whether the action string contains sensitive-looking patterns.

---

## 7. Compliance Docs vs. Code Reality

The following compliance requirements are documented but have **no typed code primitive** backing them:

| Compliance requirement | Documented in | What code has | What's missing |
|---|---|---|---|
| Actor identity in gate records | COMPLIANCE_MAPPING.md (Govern-2.1 accountability) | `executed_by: str` on ActionExecution | Structured actor object in gate check and GateDecisionRecord |
| Purpose threading | EU AI Act Art.14 (human oversight), SOC 2 CC1.4 | None | `purpose: str` field on any request/gate call |
| Data classification marks | ISO 27001 A.8.2, COMPLIANCE_MAPPING.md | SecurityLevel enum on ObjectType schema | Per-instance SecurityMarking object; classification-aware gate checking |
| Acknowledgment artifacts | CI_GATES.md `[impact-checked]` PR string | String in PR body | `GateAcknowledgment` OntologyObj with actor, timestamp, justification |
| Approval workflow record | ActionDef.requires_approval=True flag | Boolean only | Approval record: who approved, when, with what authority |
| Justification text on gate decisions | FOURFOLD_ACTION_WARRANT.md (warrant as evidence) | `reason` (gate's explanation, not actor's justification) | `justification: str` on GateDecisionRecord (actor-supplied warrant) |
| Gate definition queryable as artifact | COMPLIANCE_MAPPING.md (audit evidence package) | Gate names as strings in CORE_GATES dict | TelosGateDef OntologyObj with compliance mappings, pass rates |
| Witness log as ontology instance | WitnessLog ObjectType registered with audit_all=True | JSONL flat file via _log_witness(), zero OntologyObj instances | Writer path from _log_witness() → OntologyRegistry.create_object("WitnessLog") |
| Policy binding (actor+role+action) | ISO 27001 A.5.10, SOC 2 PI1.3 | SecurityPolicy read/write_roles as string lists on type | Structured PolicyBinding: actor_id, role, allowed_actions, context |

---

## 8. Recommended Placement

For each missing governance concept flagged by the cron (PR #415 grounding):

### `policyBinding`
**Native struct closest analogue:** `SecurityPolicy` (ontology.py:SecurityPolicy) + `AgentSpec.constitutional_gates` (agent_constitution.py)

These two together are the embryo of a policy binding: one controls resource access by role-string, the other controls which gates an agent is subject to. Neither is a runtime persisted object. A `policyBinding` adapter would be **standalone** — it would synthesize from SecurityPolicy (role access) + constitutional_gates (gate subset) + a new `purpose` field. No existing struct maps cleanly.

**Adapter placement:** `dharma_swarm/ontology_adapters.py` (existing adapter module), with a new `PolicyBinding` ObjectType registered in `create_dharma_registry()`.

### `securityMarking`
**Native struct closest analogue:** `SecurityLevel` enum (ontology.py, line 80)

`SecurityLevel` is the closest — it has the right vocabulary (PUBLIC/INTERNAL/RESTRICTED/DHARMIC). But it is attached to type schemas, not instances. A `securityMarking` would be an OntologyObj wrapping a SecurityLevel plus: marked_object_id, marked_object_type, marked_by, marked_at, rationale.

**Adapter placement:** **No native instance struct exists.** Adapter would be standalone in `dharma_swarm/ontology_adapters.py`. The `SecurityLevel` enum can be reused as the classification field value.

### `actionDefinition`
**Native struct:** `ontology.py:ActionDef` — already exists as a schema class.

The gap is that ActionDef is a schema artifact, not an OntologyObj. An `actionDefinition` type would require seeding ActionDef instances as first-class ontology objects at registry boot. The adapter bridges `ActionDef` → `OntologyObj(type_name="ActionDefinition")`.

**Adapter placement:** `dharma_swarm/ontology_adapters.py`. The bridge is well-defined: iterate `OntologyRegistry._actions` at boot and write one ActionDefinition OntologyObj per ActionDef. Version field would need to be added to ActionDef (currently unversioned).

### Expanded `gateDecision` verdict states (PENDING_APPROVAL, ACKNOWLEDGED)
**Native struct:** `GateDecision` enum in `dharma_swarm/models.py` (ALLOW/BLOCK/REVIEW).

This requires adding enum values to `GateDecision` (models.py) and corresponding properties to the `GateDecisionRecord` ObjectType in ontology.py. The change is additive (new enum values do not break existing ALLOW/BLOCK/REVIEW consumers). A `GateAcknowledgment` OntologyObj (separate from GateDecisionRecord) would need to be created as a new type, linked via `"has_acknowledgment"` link.

**Placement:** Models change in `dharma_swarm/models.py`; new GateAcknowledgment type in `dharma_swarm/ontology.py:create_dharma_registry()`; writer in `dharma_swarm/telic_seam.py:record_gate_acknowledgment()` (new method).

### `HonorsCheckpoint` as a Foundry-style governance checkpoint
**Native struct:** `mission_contract.py:HonorsCheckpoint` (CompletionContract + DefensePacket + JudgePack). This is a quality-assurance checkpoint on completion, not a data-governance checkpoint on access/mutation. The names overlap with Foundry Checkpoints but the semantics are different.

**Placement for a governance-style Checkpoint:** standalone new type. The `HonorsCheckpoint` cannot be reused because it is mission-scoped (per-completion-contract), not resource-scoped (per-sensitive-object-access). A governance `Checkpoint` OntologyObj would carry: resource_id, action_name, actor_id, justification, status (pending/acknowledged/blocked), acknowledged_by, acknowledged_at. This would be a new type with no direct native struct to bridge from.

---

## 9. Surprises

### 9a. The gate suite grew from 5 to 11 gates — but the cron report and PROPOSED_VOCABULARY still say "5 gates"
Pass 1b documented 5 active gates (AHIMSA, SATYA, REVERSIBILITY, SVABHAAVA, WITNESS). Reading `telos_gates.py` directly reveals **11 core gates**: AHIMSA, SATYA, CONSENT, VYAVASTHIT, REVERSIBILITY, SVABHAAVA, BHED_GNAN, WITNESS, ANEKANTA, DOGMA_DRIFT, STEELMAN. The gate count more than doubled and the census vocabulary did not update. CONSENT (Tier B) covers data exfiltration — the strongest candidate for a `policyBinding`-adjacent concept — and is not mentioned in the 22 proposed types.

### 9b. `ActionDef.requires_approval` is a boolean flag with no backing workflow
The `requires_approval=True` flag appears on `ActionDef(name="Submit", object_type="Paper", ...)` in ontology.py (line 944). This is the clearest existing code signal that the system has a concept of "this action requires approval before execution." But there is no `ApprovalRecord`, no `Approver`, no approval lifecycle — just a boolean that the execute_action() code does not even check (it only checks `telos_gates` and `telos_required`). The compliance mapping needs to reference this gap explicitly: the flag exists, the approval artifact does not.

### 9c. `WitnessLog` ObjectType is registered with `audit_all=True` but has zero production instances
The `WitnessLog` ObjectType (`ontology.py:1164–1192`) has `security=SecurityPolicy(write_roles=["*"], delete_roles=[], audit_all=True)` and `telos_alignment=1.0`. Yet `TelosGatekeeper._log_witness()` writes directly to the filesystem JSONL — it never calls `OntologyRegistry.create_object("WitnessLog", ...)`. The ontology registry is completely decoupled from the actual witness log production path. This means the `witnessLog` type proposed in PROPOSED_VOCABULARY.md is not yet populated with any gate-generated instances, only with instances written by other modules (cron_runner, meta_daemon, etc.) via different code paths that DO write to the ontology.

### 9d. `GateDecisionRecord.witness_reroutes` — a surprise governance field already on the record
`telic_seam.py:record_gate_decision()` persists `witness_reroutes: int` — the count of reflective reroute attempts before the check passed or was confirmed blocked. This is a governance-relevant field not mentioned in the Pass 1b code-reality-map or in PROPOSED_VOCABULARY.md. It is already on the record. The cron report flagged the need for "justifications as first-class durable artifacts" — but this field is exactly a partial move in that direction. The gap is that `witness_reroutes` is a count, not a structured record of what the reflection attempts contained.

### 9e. `FOURFOLD_ACTION_WARRANT.md` explicitly anticipates attachment to ActionProposal/GateDecisionRecord
The doc states (line 93–94): "Future integrations may attach the warrant to `ActionProposal` or `GateDecisionRecord`, but the current implementation remains read-only." This is the official intent for where warrant evidence should land. The warrant is already producing structured JSON (`reports/governance/fourfold-warrant.json`). The adapter path from warrant JSON → GateDecisionRecord.justification (a new field) is well-defined and short.

### 9f. `ActionTypeGuardrail` overpromises dramatically
The class docstring says "Validates tool/action calls against ontology ActionDef rules. Checks that the action exists, the actor has permission, and required telos gates pass." The implementation (lines 333–349) does none of this — it checks only whether `tool_name.lower()` is in `{"bash", "shell", "exec", "eval", "subprocess"}` and returns WARN. The ontology ActionDef is never queried. No actor permission check occurs. This is a silent governance gap: code that looks like it enforces action definitions but doesn't.

### 9g. No test file for `telic_seam.py` gate decision path found
The 1b map mentioned `test_telic_seam` as existing. A targeted look at the checkpoint/acknowledgment surface found no test that verifies `record_gate_decision()` captures actor identity, purpose, or justification — because none of those fields exist on the object being tested. The test suite validates the lifecycle mechanics but cannot test governance-context threading because the threading is not there to test.

---

*Files walked: 12 core Python files read in full (telos_gates.py, telic_seam.py, ontology.py, models.py, guardrails.py, mission_contract.py, agent_runner_quality.py, ai_reciprocity_ledger.py, agent_constitution.py, adaptive_autonomy.py) + 4 governance docs read in full (COMPLIANCE_MAPPING.md, CI_GATES.md, FOURFOLD_ACTION_WARRANT.md, plus PROPOSED_VOCABULARY.md and 1b-code-reality-map.md as context). Grep sweeps across dharma_swarm/ (all .py files) for: ActionType, ActionDefinition, purpose, actor_id, PolicyBinding, classification, sensitivity, Marking, SecurityMarking, Checkpoint, justification, acknowledgment.*
