# Codex GPT-5.5 — Full-Power Executable Plan
## Phase: Runtime Spine Adoption Saturation

**Target model:** GPT-5.5 (Codex full-power mode, `/goal` invocation)
**Predecessor work:** v2 worktree at `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` (159 passing tests, 5 joined surfaces, 4 adapter-ready)
**Authority:** Master Spec at `02_master_spec.md` in same folder; Gap Matrix at `01_gap_matrix.md`
**Verification gate:** every slice must end with `git diff --check` clean and the test command in that slice passing

---

## 0. Preflight (run before any slice)

```bash
cd /Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2 || cd /Users/dhyana/dharma_swarm

# 1) Confirm baseline
git status
git log --oneline -1
git rev-parse HEAD  # expect 2737b26d or rebased

# 2) Run the existing v2 evidence suite — must be green before changes
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_truth_spine_v1.py \
  tests/test_runtime_truth_spine_v2_adapters.py \
  tests/test_runtime_truth_spine_v2_evidence.py \
  tests/test_runtime_truth_spine_v2_tollbooth.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py \
  tests/test_message_bus.py \
  tests/test_checkpoint.py \
  tests/test_orchestrator.py

# Expected: 159 passed (or rebased equivalent)

# 3) Confirm clean workspace before slicing
git diff --check
```

**Hard rule:** if preflight fails, STOP. Do not start Slice A on a non-green base. Open an issue and tag the operator.

---

## 1. SLICE A — Close the Legacy Ledger Bypass

**Goal (binary):** After this slice, `SELECT COUNT(*) FROM delegation_runs WHERE run_id NOT IN (SELECT run_id FROM execution_identities)` returns 0 on every canonical-path test fixture.

**Branch:**
```bash
git checkout -b spine-adoption/slice-a-legacy-bypass
```

### A.1 Modify `runtime_state.py` legacy sync helpers

**File:** `dharma_swarm/runtime_state.py` (lines `1595` and `1686`)

**Diff intent (pseudocode — Codex must produce actual diff):**

```python
# At runtime_state.py:1595 — create_task_claim_sync
def create_task_claim_sync(
    self,
    *,
    task_id: str,
    agent_id: str = "",
    # ... existing args ...
    identity: ExecutionIdentity | None = None,            # NEW
    legacy_no_identity_allowed: bool = False,             # NEW
) -> str:
    if identity is None and not legacy_no_identity_allowed:
        raise MissingExecutionIdentity(
            "create_task_claim_sync requires ExecutionIdentity. "
            "Pass identity=... or set legacy_no_identity_allowed=True to opt into quarantine."
        )
    if identity is not None:
        # Write execution_identities row FIRST, same transaction as claim insert
        self._record_execution_identity_sync_in_txn(identity, conn=conn)
        self._record_runtime_receipt_sync_in_txn(
            **runtime_receipt_kwargs(
                identity,
                receipt_type="legacy_sync_identity_attached",
                status="completed",
            ),
            conn=conn,
        )
    else:
        # legacy_no_identity_allowed=True path — emit quarantine receipt
        self._record_quarantine_receipt_sync(
            receipt_type="legacy_sync_no_identity",
            task_id=task_id,
            agent_id=agent_id,
        )
    # ... existing insert into task_claims ...
```

Same pattern for `create_delegation_run_sync` at `:1686`.

**Codex-specific note:** the existing function signatures are already long. Add new params **at the end**, keyword-only. Do **not** reorder existing params — every test that calls these positionally will break.

### A.2 Migrate `OpportunityDispatcher`

**File:** `dharma_swarm/opportunity_dispatcher.py:155-200` area (specifically `:184`, `:193`)

```python
# Construct one identity per opportunity dispatch
identity = ExecutionIdentity.new(
    task_id=opportunity.task_id,
    agent_id=opportunity.assigned_agent,
    session_id=opportunity.session_id or "",
    causation_id=opportunity.parent_task_id or "",
    metadata={"surface": "opportunity_dispatcher"},
)

# Pass through to both legacy helpers
claim_id = self.runtime_state.create_task_claim_sync(
    task_id=opportunity.task_id,
    agent_id=opportunity.assigned_agent,
    # ... existing args ...
    identity=identity,
)
run_id = self.runtime_state.create_delegation_run_sync(
    task_id=opportunity.task_id,
    claim_id=claim_id,
    # ... existing args ...
    identity=identity,
)
```

### A.3 Write the invariant test

**File:** `tests/test_runtime_state_invariants.py` (NEW)

```python
"""Invariant: no run_id without execution_identity on canonical paths."""
import pytest
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.opportunity_dispatcher import OpportunityDispatcher
# ... existing fixtures ...

def test_no_run_id_without_execution_identity(canonical_fixture):
    """After canonical workflow, every delegation_runs.run_id has execution_identities row."""
    store = canonical_fixture["runtime_state"]
    # Run canonical opportunity dispatch fixture
    canonical_fixture["dispatch_one_opportunity"]()

    with store._conn() as conn:
        cur = conn.execute("""
            SELECT COUNT(*)
            FROM delegation_runs
            WHERE run_id NOT IN (SELECT run_id FROM execution_identities)
              AND run_id NOT IN (
                  SELECT json_extract(payload, '$.run_id')
                  FROM runtime_receipts
                  WHERE receipt_type = 'legacy_sync_no_identity'
              )
        """)
        orphan_count = cur.fetchone()[0]
    assert orphan_count == 0, f"Found {orphan_count} run_ids without execution_identity"


def test_legacy_no_identity_allowed_creates_quarantine_receipt(canonical_fixture):
    """When legacy_no_identity_allowed=True, a quarantine receipt is written."""
    store = canonical_fixture["runtime_state"]
    claim_id = store.create_task_claim_sync(
        task_id="legacy-test-1",
        agent_id="test-agent",
        legacy_no_identity_allowed=True,
    )
    with store._conn() as conn:
        cur = conn.execute("""
            SELECT COUNT(*) FROM runtime_receipts
            WHERE receipt_type = 'legacy_sync_no_identity'
        """)
        assert cur.fetchone()[0] > 0


def test_legacy_call_without_flag_raises(canonical_fixture):
    """When identity is None and legacy_no_identity_allowed=False, raises."""
    store = canonical_fixture["runtime_state"]
    with pytest.raises(MissingExecutionIdentity):
        store.create_task_claim_sync(task_id="test-2", agent_id="test")
```

### A.4 Run Slice A tests

```bash
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_state_invariants.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py \
  tests/test_opportunity_dispatcher_identity.py

git diff --check
```

**Done-when (Slice A):** All three new tests pass; existing `test_runtime_state.py` continues to pass; `git diff --check` clean.

**Commit:**
```bash
git add dharma_swarm/runtime_state.py dharma_swarm/opportunity_dispatcher.py \
  tests/test_runtime_state_invariants.py tests/test_opportunity_dispatcher_identity.py
git commit -m "spine(slice-a): close legacy ledger bypass with identity-or-quarantine gate

- create_task_claim_sync and create_delegation_run_sync now require ExecutionIdentity
  OR explicit legacy_no_identity_allowed=True flag
- OpportunityDispatcher constructs identity and passes through
- New invariant test: no run_id without execution_identity on canonical paths
- Quarantine receipt 'legacy_sync_no_identity' for audited bypass cases

Stage-1 evidence-only. References blast-radius audit §9 finding 1 and §14 Slice 1."
```

---

## 2. SLICE B — Adapter Saturation on 5 Missing Boundaries

**Goal (binary):** 5 boundaries (TaskBoard create, MessageBus send, MessageBus consume, ToolRegistry dispatch, RuntimeArtifactStore writes) gain `require_identity` toggle with `False` default; 5 tests prove `require_identity=True` raises on missing identity.

**Branch (after Slice A merged):**
```bash
git checkout main && git pull
git checkout -b spine-adoption/slice-b-adapter-saturation
```

### B.1 Boundary template

For each boundary, apply this pattern:

```python
from dharma_swarm.spine.adapters import (
    adapt_execution_identity,
    runtime_receipt_kwargs,
)
from dharma_swarm.spine.identity import MissingExecutionIdentity

class <Boundary>:
    def __init__(self, *, require_identity: bool = False, **kwargs):
        # ... existing init ...
        self._require_identity = require_identity

    def <op>(self, carrier, ...):
        identity, carrier = adapt_execution_identity(
            carrier,
            surface="<surface_name>",
            require_existing=self._require_identity,
        )
        # Pre-side-effect idempotency guard
        if self.runtime_state is not None:
            began = self.runtime_state.try_begin_idempotent_side_effect_sync(
                idempotency_key=identity.idempotency_key,
                side_effect_key=f"{<surface>}:{<op>}",
            )
            if not began:
                return self._already_done_result(identity)
        try:
            # ... existing side-effect logic ...
            result = self._do_side_effect(carrier)
        finally:
            if self.runtime_state is not None:
                self.runtime_state.complete_idempotent_side_effect_sync(
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=f"{<surface>}:{<op>}",
                )
                self.runtime_state.record_runtime_receipt_sync(
                    **runtime_receipt_kwargs(
                        identity,
                        receipt_type=f"{<surface>}_{<op>}",
                        status="completed",
                    )
                )
        return result
```

### B.2 Per-boundary specifics

**B.2.1 TaskBoard** — `dharma_swarm/task_board.py:207` (`create`) and `create_batch`:
- Surface: `"taskboard"`
- Side-effect key: `f"task:{task_id}:create"`
- Persist full identity into task metadata (`task_board.py:212` currently only stores trace_id — extend to full identity payload).
- Test: `tests/test_runtime_truth_spine_adoption.py::test_taskboard_requires_identity`

**B.2.2 MessageBus.send** — `dharma_swarm/message_bus.py:184`:
- Surface: `"message_bus"`
- Side-effect key: `f"message:{message_id}:send"`
- Test: `test_message_bus_send_requires_identity`

**B.2.3 MessageBus.consume_events** — `dharma_swarm/message_bus.py:683`:
- Surface: `"message_bus_consume"`
- Side-effect key: `f"event:{event_id}:consume:{handler_id}"`
- **This is the Kafka idempotent-consumer pattern.** Receiver-side guard per (event_id, handler) tuple. Reference: [Lydtech](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox).
- Test: `test_message_bus_consume_idempotent_per_handler`

**B.2.4 ToolRegistry.dispatch** — `dharma_swarm/tool_registry.py:129`:
- Surface: `"tool"`
- Side-effect key: `f"tool:{tool_name}:{tool_call_id}"`
- Receipts: `side_effect_intent` BEFORE handler, `side_effect_complete` AFTER.
- Test: `test_tool_registry_requires_identity`

**B.2.5 RuntimeArtifactStore.create_text_artifact** — `dharma_swarm/artifact_store.py:40`:
- Surface: `"artifact_store"`
- Side-effect key: `f"artifact:{artifact_id}:write"`
- Make `run_id` and `trace_id` mandatory (currently optional default `""`).
- Test: `test_artifact_store_requires_run_id_and_trace_id`

### B.3 Engine artifact mapping (lightweight)

**File:** `dharma_swarm/engine/artifacts.py:90` (`create_artifact`)

Add optional `(run_id, trace_id)` params and a single call:

```python
def create_artifact(self, ..., run_id: str = "", trace_id: str = "") -> ArtifactRef:
    # ... existing artifact_id generation ...
    if run_id and trace_id and self._runtime_state is not None:
        self._runtime_state.record_engine_artifact_mapping(
            engine_artifact_id=artifact_id,
            run_id=run_id,
            trace_id=trace_id,
        )
    return ArtifactRef(...)
```

`record_engine_artifact_mapping` is a new method in `runtime_state.py` (lands in Slice C — Slice B just calls it via duck typing).

### B.4 Test file — `tests/test_runtime_truth_spine_adoption.py` (NEW)

Structure:
- 5 tests for `require_identity=True` raising `MissingExecutionIdentity`
- 5 tests for duplicate idempotency not repeating side effects
- 1 test that all 5 boundaries with `require_identity=False` still work (backward compat)

### B.5 Run Slice B tests

```bash
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_truth_spine_adoption.py \
  tests/test_message_bus.py \
  tests/test_runtime_state.py \
  tests/test_runtime_truth_spine_v2_adapters.py

git diff --check
```

**Done-when (Slice B):** 5 new adoption tests pass; existing tests still green; no boundary's default behavior changes for callers that don't set `require_identity=True`.

**Commit:**
```bash
git commit -m "spine(slice-b): adapter saturation on 5 missing boundaries

Boundaries gain require_identity toggle (default False, fail-closed when True):
- TaskBoard.create / create_batch
- MessageBus.send (raw)
- MessageBus.consume_events (receiver-side idempotency per handler)
- ToolRegistry.dispatch (side_effect_intent/complete receipts)
- RuntimeArtifactStore.create_text_artifact (run_id+trace_id mandatory)

Adds 5 require_identity tests + 5 idempotency tests + 1 backward-compat test.
Lightweight engine artifact mapping hook (mapping itself lands in Slice C).

Implements Kafka idempotent-consumer pattern on receive path (see master spec §4 Slice B).
References blast-radius audit §10 (canonical/adapt/quarantine table) and §14 Slice 2."
```

---

## 3. SLICE C — Mapping Receipts for Parallel Lineages

**Goal (binary):** 5 mapping receipt types implemented; `get_run_ledger(run_id)` includes foreign IDs; 5 new query helpers return correct results.

**Branch (after Slice B merged):**
```bash
git checkout main && git pull
git checkout -b spine-adoption/slice-c-mapping-receipts
```

### C.1 New receipt types in `runtime_state.py`

Add to the receipt vocabulary section (`runtime_state.py:308` area):

- `workflow_started` (workflow_id, run_id, trace_id, workflow_type)
- `workflow_checkpointed` (workflow_id, checkpoint_id, run_id)
- `proposal_created` (proposal_id, run_id, trace_id, proposal_type)
- `event_emitted` (event_id, run_id, trace_id, subject)
- `event_consumed` (event_id, run_id, handler_id, status)
- `ontology_action_requested` (ontology_action_id, run_id, action_name, object_type, object_id)
- `ontology_action_applied` (ontology_action_id, status)
- `engine_artifact_recorded` (engine_artifact_id, run_id, trace_id, artifact_path)

### C.2 Helper methods in `RuntimeStateStore`

Add to `runtime_state.py` (around line 2364 self-mod helpers area):

```python
def record_workflow_mapping(self, *, workflow_id, run_id, trace_id, workflow_type=""): ...
def record_proposal_mapping(self, *, proposal_id, run_id, trace_id, proposal_type=""): ...
def record_event_mapping(self, *, event_id, run_id, trace_id, subject, kind): ...
def record_ontology_action_requested(self, *, ontology_action_id, run_id, action_name, object_type="", object_id=""): ...
def record_ontology_action_applied(self, *, ontology_action_id, status): ...
def record_engine_artifact_mapping(self, *, engine_artifact_id, run_id, trace_id, artifact_path=""): ...

# Query helpers
def get_runs_by_workflow_id(self, workflow_id: str) -> list[str]: ...
def get_runs_by_proposal_id(self, proposal_id: str) -> list[str]: ...
def get_runs_by_ontology_action_id(self, ontology_action_id: str) -> list[str]: ...
def get_runs_by_event_id(self, event_id: str) -> list[str]: ...
def get_runs_by_engine_artifact_id(self, engine_artifact_id: str) -> list[str]: ...
```

### C.3 Wire mapping callsites (mapping only — no enforcement changes)

**C.3.1 Workflow** — `dharma_swarm/workflow.py:231` (`CompiledWorkflow.__init__`), `workflow_graph.py:240` (`WorkflowGraph.execute`), `durable_execution.py:99`:
- If `runtime_state` is in scope and identity is derivable, call `record_workflow_mapping`.
- Add `runtime_state` kwarg if missing.

**C.3.2 Proposal** — search `dharma_swarm/evolution.py` and `sealed_packet_apply.py` for `proposal_id` generation sites:
- At creation, call `record_proposal_mapping`.

**C.3.3 Event** — `message_bus.py:603` (emit path after `event_id` generation), `message_bus.py:683` (consume path):
- Call `record_event_mapping` with `kind="emitted"` / `kind="consumed"`.

**C.3.4 Ontology action** — `dharma_swarm/ontology.py:763` (`execute_action`):

```python
import uuid

def execute_action(self, action_name, params, executed_by, ...):
    ontology_action_id = f"oa_{uuid.uuid4().hex[:16]}"
    # Try to extract identity from params metadata
    identity_meta = params.get("metadata", {}).get("execution_identity") or {}
    run_id = identity_meta.get("run_id", "")

    if self._runtime_state is not None and run_id:
        self._runtime_state.record_ontology_action_requested(
            ontology_action_id=ontology_action_id,
            run_id=run_id,
            action_name=action_name,
            object_type=params.get("object_type", ""),
            object_id=params.get("object_id", ""),
        )

    # ... existing telos gate logic, action mutation, success log ...

    if self._runtime_state is not None and run_id:
        self._runtime_state.record_ontology_action_applied(
            ontology_action_id=ontology_action_id,
            status="completed" if success else "failed",
        )

    return result
```

**Important:** this is **mapping only**. The C2 ontology tollbooth (enforce `ActionDef.modifies` / `requires_approval`) is the **next** phase. This slice generates `ontology_action_id` and records the mapping so the next phase has a join key.

**C.3.5 Engine artifact** — `dharma_swarm/engine/artifacts.py:90` already received the hook in Slice B. Slice C just lands the `record_engine_artifact_mapping` method it calls.

### C.4 Extend `get_run_ledger`

**File:** `runtime_state.py:2765`

Extend `get_run_ledger(run_id)` return value with new keys:
- `workflow_mappings`: list of workflow_ids mapped to this run
- `proposal_mappings`: list of proposal_ids
- `ontology_action_mappings`: list of ontology_action_ids with status
- `event_mappings`: list of (event_id, kind, subject) tuples
- `engine_artifact_mappings`: list of engine_artifact_ids

### C.5 Test file — `tests/test_spine_mapping_receipts.py` (NEW)

Tests:
- `test_workflow_started_mapping_recorded`
- `test_proposal_created_mapping_recorded`
- `test_event_emitted_and_consumed_mapping_recorded`
- `test_ontology_action_requested_and_applied_recorded`
- `test_engine_artifact_mapping_recorded`
- `test_get_run_ledger_returns_all_mappings`
- `test_get_runs_by_workflow_id_returns_correct_runs`
- (one query test per mapping type — 5 total)

### C.6 Run Slice C tests

```bash
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_spine_mapping_receipts.py \
  tests/test_runtime_state.py \
  tests/test_message_bus.py \
  tests/test_runtime_truth_spine_v2_evidence.py

git diff --check
```

**Commit:**
```bash
git commit -m "spine(slice-c): mapping receipts for parallel lineages

Adds 5 mapping receipt types + 5 query helpers to RuntimeStateStore:
- workflow_id -> run_id (workflow_started, workflow_checkpointed)
- proposal_id -> run_id (proposal_created)
- event_id -> run_id (event_emitted, event_consumed)
- ontology_action_id -> run_id (generates ID + records requested/applied)
- engine_artifact_id -> run_id (engine_artifact_recorded)

get_run_ledger(run_id) now returns mapped foreign IDs.

NOTE: ontology mapping only generates ontology_action_id and records mapping.
Enforcement of ActionDef.modifies / requires_approval is the next phase
(C2 ontology tollbooth — explicitly out of scope here per master spec NG1).

References blast-radius audit §8 (linkage map) and §14 Slice 3.
References Palantir Action Log: https://palantir.com/docs/foundry/action-types/action-log/
References Temporal WorkflowId+RunId tuple: https://docs.temporal.io/workflow-execution/workflowid-runid"
```

---

## 4. SLICE D — Metric + CI Gate

**Branch (after C merged):**
```bash
git checkout main && git pull
git checkout -b spine-adoption/slice-d-metric-ci-gate
```

### D.1 Adoption metric script

**File:** `tools/spine_adoption_metric.py` (NEW)

```python
"""Deterministic spine adoption metric.

Enumerates 16 named surfaces, runs static checks, classifies each.
Output: reports/governance/spine_adoption_metric.json
"""
import json
import subprocess
from pathlib import Path

SURFACES = [
    {"name": "a2a_local_submit", "check": "rg -q 'require_execution_identity' dharma_swarm/a2a/a2a_server.py"},
    {"name": "runtime_lifecycle_task_claim", "check": "rg -q 'require_identity=True' dharma_swarm/runtime_lifecycle.py"},
    # ... 14 more surfaces from blast-radius audit §10 ...
]

def classify(surface) -> str:
    rc = subprocess.run(surface["check"], shell=True, capture_output=True).returncode
    if rc == 0:
        return "joined" if "v2_joined_marker" in surface else "adapter-ready"
    return "missing"

def main():
    results = []
    for s in SURFACES:
        results.append({"name": s["name"], "status": classify(s)})
    joined = sum(1 for r in results if r["status"] == "joined")
    adapter = sum(1 for r in results if r["status"] == "adapter-ready")
    total = len(results)
    metric = {
        "version": "1.0",
        "total_classified": total,
        "joined": joined,
        "adapter_ready": adapter,
        "joined_or_adapter_ready_pct": round((joined + adapter) / total * 100, 2),
        "surfaces": results,
    }
    out = Path("reports/governance/spine_adoption_metric.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metric, indent=2, sort_keys=True))
    print(json.dumps(metric, indent=2))

if __name__ == "__main__":
    main()
```

### D.2 Test the metric

**File:** `tests/test_spine_adoption_metric.py` (NEW)

```python
import json
import subprocess
from pathlib import Path

def test_adoption_metric_generates():
    subprocess.run(["python", "tools/spine_adoption_metric.py"], check=True)
    out = Path("reports/governance/spine_adoption_metric.json")
    assert out.exists()
    metric = json.loads(out.read_text())
    assert metric["joined_or_adapter_ready_pct"] >= 95.0, (
        f"Adoption regression: {metric['joined_or_adapter_ready_pct']}% < 95%"
    )
```

### D.3 Wire into CI

Find existing `.github/workflows/*.yml` job that runs pytest. Add:

```yaml
- name: Spine invariant tests
  run: |
    pytest tests/test_runtime_state_invariants.py
    pytest tests/test_runtime_truth_spine_adoption.py
    pytest tests/test_spine_mapping_receipts.py
    pytest tests/test_spine_adoption_metric.py
```

### D.4 Commit

```bash
git commit -m "spine(slice-d): adoption metric + CI invariant gates

- tools/spine_adoption_metric.py: deterministic 16-surface coverage script
- reports/governance/spine_adoption_metric.json: generated artifact
- tests/test_spine_adoption_metric.py: asserts ≥95% joined-or-adapter-ready
- CI runs all four spine invariant test files on every PR

Phase exit gate met."
```

---

## 5. Final Verification

After all four slices merge to main:

```bash
git checkout main && git pull

# Full v2 evidence suite + new tests
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_truth_spine_v1.py \
  tests/test_runtime_truth_spine_v2_adapters.py \
  tests/test_runtime_truth_spine_v2_evidence.py \
  tests/test_runtime_truth_spine_v2_tollbooth.py \
  tests/test_runtime_state.py \
  tests/test_runtime_state_invariants.py \
  tests/test_runtime_lifecycle.py \
  tests/test_runtime_truth_spine_adoption.py \
  tests/test_spine_mapping_receipts.py \
  tests/test_spine_adoption_metric.py \
  tests/test_message_bus.py \
  tests/test_checkpoint.py \
  tests/test_orchestrator.py

# Confirm metric
cat reports/governance/spine_adoption_metric.json

# Expected: joined_or_adapter_ready_pct >= 95.0
```

If all pass: **phase complete**. NATS-broadcast `phase_complete` envelope, open final PR with merge candidate.

---

## 6. Failure-Mode Playbook

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Slice A invariant test fails on existing fixtures | Test fixture uses legacy sync without identity | Update fixture to use canonical path, OR explicitly mark fixture as legacy and exclude from invariant test |
| Slice B test for `require_identity=True` raises in unrelated test | New default leaking | `require_identity=False` default must be preserved; check constructor of failing test |
| Slice C mapping receipt write fails because `runtime_state is None` | Workflow created without runtime_state plumbed | Gracefully no-op when runtime_state is None — mappings are best-effort, not required for workflow to run |
| Slice D metric reports <95% | Phase incomplete | Identify which surfaces dropped; re-run failing slice |
| Tests take longer than 12s (baseline was 11.99s) | Mapping receipt writes adding I/O | Add SQLite index on (foreign_id, run_id); batch receipts in single transaction where possible |
| Workflow versioning gap surfaced as blocker | This phase explicitly did not address (NG2) | Open follow-up phase doc; reference Restate immutable deployments + Temporal worker versioning |

---

## 7. Process Discipline — Codex 5.5 Specific

- **No invented file paths.** Every file Codex writes to must already exist OR be a NEW file that's listed in this plan. If Codex sees a need for an unplanned file, STOP and ask.
- **No removing existing tests.** Existing 159 tests must remain green. If a test conflicts with new behavior, **add a new test for the new behavior** and mark the conflict with `pytest.mark.xfail(reason="...")` until operator decides.
- **One slice per PR.** Slices A → B → C → D land sequentially as four PRs. No mega-PR.
- **Conventional commit format.** `spine(slice-x): <one-liner>` followed by blank line + bullet description + reference to blast-radius audit section.
- **Cite primary sources in PR description.** Each PR description cites the relevant master spec section AND the external grounding source (Temporal/Palantir/Kafka outbox/strangler-fig).
- **Test before commit, always.** No commit without a green `pytest -q` and clean `git diff --check`.
- **If stuck >30 min on one slice, escalate.** Open a comment on the slice PR tagging the operator. Do not invent solutions.

---

## 8. Quick-Reference: External Grounding Sources

When writing PR descriptions, cite the relevant source:

- **Idempotency contract:** [Temporal: Idempotency and Durable Execution](https://temporal.io/blog/idempotency-and-durable-execution)
- **WorkflowId+RunId tuple:** [docs.temporal.io: Workflow Id and Run Id](https://docs.temporal.io/workflow-execution/workflowid-runid)
- **Workflow ID as idempotency key:** [DBOS: Idempotency Tutorial](https://docs.dbos.dev/tutorials/idempotency-tutorial)
- **Immutable deployments / versioning:** [Restate: Solving Durable Execution's Immutability Problem](https://www.restate.dev/blog/solving-durable-executions-immutability-problem)
- **Idempotent consumer + outbox:** [Lydtech: Kafka Idempotent Consumer + Transactional Outbox](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox)
- **Action Log (one log object per action):** [Palantir Foundry Docs: Action Log](https://palantir.com/docs/foundry/action-types/action-log/)
- **Action Types overview:** [Palantir Foundry Docs: Action Types](https://palantir.com/docs/foundry/action-types/overview/)
- **Strangler-fig façade:** [Microsoft Azure Architecture Center: Strangler Fig Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- **Migration playbook:** [DBOS migration playbook](https://thinhdanggroup.github.io/migrate-temporal-to-dbos/)

---

**End of Codex 5.5 Plan.** Hand this to GPT-5.5 with the `/goal` invocation: *"Execute the Runtime Spine Adoption Saturation phase per `03_codex_55_plan.md`. Read `01_gap_matrix.md` and `02_master_spec.md` first. Land one slice per PR. Use blast-radius audit for file:line targets."*
