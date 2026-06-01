# Andon Slice C — Authority & Execution
**Agent:** perplexity-computer  
**Branch:** perplexity-grounding/1780289724-vocabulary-census  
**Verified at:** 2026-06-01  
**Slice covers:** C1 (5–7 ontology stores), C2 (execute_action log vs mutation), C3 (InterruptGate auto-approve), C4 (NATS bridge envelope)

---

## C1: "5–7 ontology/registry stores claim authority"

### Evidence

**All classes matching `class.*Store|Registry|Ontology|Catalog|Index`** in `dharma_swarm/` (non-test, production only) with ontology-adjacent scope:

| Class | File | Writes to it? | Reads from it? |
|---|---|---|---|
| `OntologyRegistry` | `dharma_swarm/ontology.py:300` | `register_type`, `register_link`, `register_action`, `create_object`, `update_object`, `delete_object`, `link_objects`, `execute_action` | `get_type`, `get_types`, `get_links_for`, `get_action_def`, `get_object`, etc. |
| `OntologyHub` | `dharma_swarm/ontology_hub.py:43` | `store_object`, `delete_object`, `store_link`, `store_action_execution`, `sync_from_registry` | `load_into_registry`, `search_objects` |
| `OntologyGraph` | `dharma_swarm/ontology_query.py:36` | None (read-only query facade wrapping a registry) | `traverse`, `find`, `shortest_path` |
| `OntologyObj` (not a registry) | `dharma_swarm/ontology.py:185` | N/A — Pydantic model, not a store | N/A |

**The singleton chain is explicit:**

- `dharma_swarm/ontology_runtime.py:22` declares `_SHARED_REGISTRY: OntologyRegistry | None = None` and `_SHARED_HUB: OntologyHub | None = None`.
- `get_shared_registry()` at `ontology_runtime.py:116` is the single factory: it calls `OntologyRegistry.create_dharma_registry()`, then hydrates from `OntologyHub` (SQLite at `~/.dharma/ontology.db`), and caches in `_SHARED_REGISTRY`.
- Every API caller routes through `get_shared_registry()`: `api/routers/ontology.py:40`, `api/routers/agents.py:45`, `api/routers/graphql_router.py:236`, `api/main.py:104`, `dharma_swarm/api.py:114`, `dharma_swarm/custodians.py:450`, `dharma_swarm/engine/store_sync.py:79`, `dharma_swarm/ontology_agents.py:102`.
- `OntologyHub` is the persistence layer **subordinate** to `OntologyRegistry`, not a competing authority. Its role is defined at `ontology_hub.py:43–50`: "Wraps the in-memory OntologyRegistry with a SQLite persistence layer."
- `OntologyGraph` (`ontology_query.py:36`) is a read-only query wrapper — it takes a registry as constructor arg and does not write.

**What is NOT a competing authority:**  
The grepping found 70+ `class.*Store/Registry` hits, but these are domain-specific stores (`ArtifactStore`, `CheckpointStore`, `StigmergyStore`, `RuntimeStateStore`, `ModelRegistry`, `AgentRegistry`, `BridgeRegistry`, `ConceptRegistry`, etc.) that operate in their own domains and do NOT hold or write ontology objects/types/actions. They are NOT competing ontology stores.

**Conclusion on C1:**  
The authoritative ontology plane is `OntologyRegistry` (in-memory, type system + object instances) backed by `OntologyHub` (SQLite persistence). These are one stack, not competitors. `OntologyGraph` is a read-only query lens. The claim of "5–7 stores claiming authority" cannot be grounded in the code — no 5–7 distinct classes hold or mutate ontology types/objects/actions.

**Verdict: overstated.** The actual structure is a two-layer singleton (`OntologyRegistry` + `OntologyHub`) with a single shared runtime accessor (`get_shared_registry`). Codex appears to have counted all store-like classes repo-wide, not just those touching the ontology object graph.

---

## C2: "`execute_action` at `ontology.py:637` logs success WITHOUT applying mutations"

### Evidence

**Full `execute_action` body** (`dharma_swarm/ontology.py:594–639`):

```python
def execute_action(
    self,
    object_type: str,
    action_name: str,
    object_id: str,
    params: dict[str, Any],
    executed_by: str = "system",
    gate_check: Callable[[str, dict[str, Any]], dict[str, str]] | None = None,
) -> ActionExecution:
    action_def = self.get_action_def(object_type, action_name)
    execution = ActionExecution(...)

    if action_def is None:
        execution.result = "failed"
        ...
        return execution

    # Telos gate check
    if gate_check and action_def.telos_gates:
        gate_results = gate_check(action_name, params)
        ...
        if any(v == "BLOCK" for v in gate_results.values()):
            execution.result = "blocked"
            ...
            return execution

    # Security check
    obj_type = self._types.get(object_type)
    if obj_type and obj_type.security.telos_required and not gate_check:
        execution.result = "blocked"
        ...
        return execution

    execution.result = "success"          # ← line 637
    self._action_log.append(execution)    # ← line 638
    return execution                      # ← line 639
```

**Line 637 is the success assignment. Lines 638–639 append to audit log and return. There is no mutation call anywhere in this function body.** The `ActionDef` model carries a `modifies: list[str]` field (defined at `ontology.py:140`) that declares *which fields an action intends to modify*, but `execute_action` never reads `action_def.modifies` and never calls `update_object`. The mutation declared in the schema does not happen.

**Call sites and wrapping:**

- `dharma_swarm/logic_layer.py:254` (`ApplyAction.execute`): calls `registry.execute_action(...)`, inspects `execution.result` for `"blocked"` or `"failed"`, then marks its own `BlockResult` as `SUCCESS`. It does NOT call `registry.update_object` or any mutation after. The success path returns `{"action": ..., "object_id": ..., "gate_results": ...}` with no object state change.
- `dharma_swarm/api.py:229` (`execute_action` HTTP handler): calls `reg.execute_action(...)` and returns the `ActionExecution` object. No downstream mutation.
- `dharma_swarm/custodians.py:450`: reads from shared registry but does not call `execute_action`.

**Tests** (`tests/test_ontology_registry.py:345–404`):

```python
def test_execute_success(self, registry):
    obj, _ = registry.create_object("Experiment", {"name": "test", "status": "designed"})
    result = registry.execute_action("Experiment", "Run", obj.id, {"gpu": "A100"})
    assert result.result == "success"
```

No test asserts that `obj.properties["status"]` changed to any expected post-action value. Tests verify only `result.result == "success"` and gate/block behavior — not mutation effect. `test_action_history` (`ontology_registry.py:396–404`) verifies that `execute_action` calls appear in `action_history`, again without checking object-state change.

**Git history:** The `git log -p dharma_swarm/ontology.py` trace shows that `execute_action` was introduced in the v0.6.0 commit (`b442d0e`) alongside `ActionDef.modifies`. The `modifies` field was part of the original schema design but `execute_action` was never wired to apply those modifications. This was not a regression — the mutation was never implemented. The `modifies` field is purely declarative metadata for OAG/LLM context (`describe_type` at `ontology.py:695` surfaces it as `"deterministic"/"LLM"` annotation).

**Verdict: confirmed.** `execute_action` at `ontology.py:637` records `"success"` in the audit log without applying any field mutations to the target object. `ActionDef.modifies` (defined at `ontology.py:140`) lists intended mutations but is never consumed by the execution path. The gap is not a regression — it was never wired. Codex's claim is precisely correct on the mechanism.

**Sharpness note:** The claim says "logs success without applying mutations." The word "log" in Codex's framing is slightly off — line 638 appends to `_action_log` which is an audit trail, not a structured logger call. But the structural defect (declared mutations not applied) is correct.

---

## C3: "`InterruptGate` auto-approves without a handler (toy)"

### Evidence

**Full `InterruptGate.__init__`** (`dharma_swarm/checkpoint.py:97–106`):

```python
def __init__(
    self,
    callback: Callable[[InterruptRequest], Any] | None = None,
    timeout_seconds: float = 300.0,
    auto_approve: bool = True,
) -> None:
    self._callback = callback
    self._timeout = timeout_seconds
    self._auto_approve = auto_approve
    self._pending: dict[str, asyncio.Future[InterruptResponse]] = {}
```

**`auto_approve` defaults to `True`.**

**`interrupt()` method** (`dharma_swarm/checkpoint.py:108–152`):

```python
async def interrupt(self, request: InterruptRequest) -> InterruptResponse:
    if self._callback is None and self._auto_approve:
        return InterruptResponse(
            request_id=request.id,
            decision=InterruptDecision.APPROVE,
            reason="auto-approved (no interrupt handler registered)",
        )
    # ... callback path ...
```

When `callback=None` (the default) and `auto_approve=True` (the default), any interrupt request returns `APPROVE` immediately without any operator involvement. The module-level singleton in `cascade.py:36` is:

```python
_interrupt_gate = InterruptGate()
```

This is `InterruptGate()` with no arguments — `callback=None`, `auto_approve=True`. The singleton is used by every `LoopEngine` that does not explicitly pass its own gate (`cascade.py:117`: `self._gate = interrupt_gate or _interrupt_gate`).

**Handler attachment point:** Yes — `callback: Callable` is a constructor parameter. But it must be wired at instantiation. There is no `register_handler()` or `set_callback()` method. The `resolve()` method (`checkpoint.py:154`) resolves pending futures but cannot install a callback retroactively. The module-level singleton therefore permanently operates in auto-approve mode unless the `LoopEngine` caller supplies its own gate.

**What Codex calls "toy":** The docstring at `checkpoint.py:94–95` says explicitly: _"If no callback is set, interrupts auto-approve (backward compatible)."_ This is by design, not accidental. But the production singleton is wired without a callback, making every gate-phase interrupt in `cascade.py` auto-approve in practice.

**Tests** (`tests/test_checkpoint.py:142–209`): Cover `auto_approve=True` (no callback), `manual resolve`, `timeout auto-approve`, `timeout auto-reject`. Tests validate the behavior correctly — including that `InterruptGate(auto_approve=True)` with no callback returns `APPROVE`. No test verifies that a handler is registered before use in production cascade runs.

**Verdict: partially_confirmed.** The auto-approve-without-handler behavior is real and present at `checkpoint.py:114–119`. The module-level singleton at `cascade.py:36` runs permanently in this mode. However, "toy" overstates — the design is intentional backward-compatibility scaffolding, and a full callback path with timeout + filesystem persistence exists at `checkpoint.py:121–150`. The defect is that the production singleton does not wire a callback; it is architectural incompleteness, not toy code.

---

## C4: "NATS bridge publishes without canonical envelope (bypasses spine)"

### Evidence

**NATS does not exist in this branch's codebase.**

A comprehensive search across all Python files in the repo (`find . -name "*.py" | xargs grep -l "nats\|NATS"`) returns exactly **one file**: `dharma_swarm/a2a/node_gateway.py:20`, which mentions NATS only in a comment:

```python
# Not yet implemented (future follow-up):
#   - gRPC / NATS transport bindings (Tier 2)
```

There is no `nats_a2a_bridge.py`, no `a2a_nats_contact.py`, no `nc.publish`, no `js.publish`, no `NatsBridge` class, no NATS client import anywhere in the codebase on this branch.

**Git history context:** NATS implementation files (`nats_a2a_bridge.py`, `a2a_nats_contact.py`, `a2a_durable_projection.py`, `a2a_stale_claim_reaper.py`) are referenced in `docs/agent_tasks/claude_guidance_perplexity_computer_2026-05-31.md:11` as **Codex's untracked files on a local working tree** — they are not on `main` and not on this branch. The NATS substrate was formally scoped out of the current active tracks until the doctrine amendment (#396, merged 2026-05-31) and is listed as a proposed concurrent track (`proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml`, `proposed_tracks/spine-adoption-2026-06.yaml`) not yet declared active.

**Verdict: wrong.** There is no NATS bridge in the repo on this branch. The Codex claim audited a snapshot that included Codex's own local untracked working-tree files, not the committed codebase. The claim cannot be evaluated against the current branch state because the subject of the claim does not exist here. If and when `nats_a2a_bridge.py` is merged, the envelope enforcement question becomes live — but on this branch, C4 is categorically wrong.

---

## Slice C Headline

Three of four Codex claims in Slice C have grounding in the code, but accuracy varies sharply. **C2 is the only fully confirmed claim and the sharpest defect**: `execute_action` at `ontology.py:637` unconditionally records `"success"` and appends to the audit log without applying field mutations declared in `ActionDef.modifies`, and no test exercises mutation effect. **C3 is partially confirmed**: `InterruptGate` does auto-approve without a handler, the production singleton in `cascade.py` is wired without a callback, but this is intentional backward-compat scaffolding with a real callback path present. **C1 is overstated**: the repo has one canonical ontology stack (`OntologyRegistry` + `OntologyHub`) accessed through a single shared singleton (`get_shared_registry` in `ontology_runtime.py`); Codex appears to have conflated domain-specific stores (artifact, stigmergy, checkpoint, etc.) with ontology authority stores. **C4 is wrong**: no NATS bridge exists in the committed codebase on this branch — Codex audited its own untracked local files.

---

## What Codex Did NOT Flag

1. **`ActionDef.modifies` is a dead schema field.** Ninety-plus `modifies=[...]` declarations exist across `ontology.py` (e.g., `ontology.py:910`, `:914`, `:878`, `:1599`) but the field is never consumed at execution time. The entire "typed, transactional mutation" promise in the `ActionDef` docstring (`ontology.py:130–135`: _"Every mutation is an Action that commits atomically... auditable, reversible, and gated"_) is aspirational, not operative. Codex flagged the symptom (log without mutation) but not the systemic implication: the ontology action model presents as a transaction system but provides no actual mutation guarantee on any object field anywhere in the execution path.

2. **`OntologyHub.sync_from_registry` is called only at persist time, not at action-execute time.** Writes to `OntologyRegistry._objects` (via `create_object`, `update_object`) ARE persisted via `persist_shared_registry` → `hub.sync_from_registry` (`ontology_runtime.py:141–159`). But `execute_action` never calls this path. If a caller invokes `execute_action` and the process crashes before `persist_shared_registry` is called, the action execution is lost from SQLite even though `_action_log` had it in memory. This is an action-log durability gap distinct from the mutation gap.

3. **`InterruptGate.resolve()` has no authentication.** `checkpoint.py:154–163`: `resolve(response)` accepts any `InterruptResponse` from any caller that knows a `request_id`. Since `request_id` is a UUID hex written to a filesystem directory (`INTERRUPT_DIR`), any process with filesystem read access can forge approval of any pending interrupt. No caller identity is verified.

4. **`execute_action` is the only write path without a security role check.** `create_object` and `update_object` in `OntologyRegistry` are guarded by `check_security` calls (referenced in `ontology.py:280–292`). `execute_action` at `ontology.py:594–639` checks `telos_required` but NOT `write_roles` — a caller with no write permission can execute any action on any object as long as it passes telos gates or the type is not `telos_required`.
