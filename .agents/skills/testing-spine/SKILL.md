---
name: testing-spine
description: Test the Runtime Truth Spine (EvidenceReceipt, RoutingDecision, invoke_agent, anti-accretion gate). Use when verifying changes to dharma_swarm/spine/, tools/spine_check.py, or tests/test_dispatch_dropoff_sources.py.
---

# Testing the Runtime Truth Spine

**Purpose:** verify changes to the spine's core types (`EvidenceReceipt`, `RoutingDecision`), the `invoke_agent` dispatch seam, and the anti-accretion gate (`tools/spine_check.py`). The spine is the repo's truth layer — a regression here corrupts every downstream receipt, so both directions get tested: the happy path AND that the gate still rejects violations.

## Environment Setup

```bash
cd "$(git rev-parse --show-toplevel)"
```

No dependencies beyond the project's standard pytest setup. No secrets — all spine tests run against in-memory stores and dataclass instantiation.

## Procedure

1. **Spine acceptance tests** (fast, <1s):
   ```bash
   pytest tests/test_dispatch_dropoff_sources.py -v --tb=short
   ```
   These cover the five doctrine §11 scenarios (see Doctrine Reference below). All must pass.
2. **Anti-accretion gate, both directions** (see next section):
   ```bash
   python3 tools/spine_check.py
   ```
3. **Type invariants** (frozen-ness, OTel shape, JSON round-trip — snippets below).
4. **Regression sweeps** for adjacent surfaces the spine feeds:
   ```bash
   pytest tests/test_telic_seam.py tests/test_task_board.py tests/test_telos_graph.py -v
   pytest tests/test_authority_revenue_loop.py -v
   pytest tests/test_a2a.py tests/test_a2a_spec_conformance.py -q   # NOTE: test_a2a.py, not test_a2a_e2e.py
   ```
   Judge these by diff against a same-session clean baseline, not remembered counts. (Known documented skip: the orphan ValueEvent test in test_authority_revenue_loop.py.)

## Anti-Accretion Gate: test REJECT, not just PASS

The gate enforces that files importing `sqlite3`/`aiosqlite` declare a `# spine:` header. Enforcement scope grows over time via the shrinking `_is_grandfathered()` list — **read `tools/spine_check.py` in your checkout to see the current scope** before assuming where enforcement applies. A gate change that only gets a PASS-side test is untested: prove it still rejects.

```bash
# REJECT case — must exit 1
cat > dharma_swarm/spine/test_violation_temp.py << 'EOF'
import sqlite3
def bad(): pass
EOF
python3 tools/spine_check.py; echo "exit=$?"
rm -f dharma_swarm/spine/test_violation_temp.py

# PASS case — must exit 0
cat > dharma_swarm/spine/test_declared_temp.py << 'EOF'
# spine: writes EvidenceReceipt
import sqlite3
def good(): pass
EOF
python3 tools/spine_check.py; echo "exit=$?"
rm -f dharma_swarm/spine/test_declared_temp.py
```

Cleanup is part of the test — a leftover `test_violation_temp.py` breaks the next person's gate run.

## Spine Type Verification

```python
from dharma_swarm.spine import EvidenceReceipt, RoutingDecision
import json, pytest

r = EvidenceReceipt(agent_id="test")

# 1. Frozen immutability — mutation must raise (FrozenInstanceError or equivalent)
with pytest.raises(Exception):
    r.agent_id = "mutated"

# 2. OTel export shape
span = r.to_otel_span()
assert "gen_ai.operation.name" in span["attributes"]
assert "dharma.receipt_id" in span["attributes"]

# 3. JSON round-trip
parsed = json.loads(json.dumps(r.to_dict(), default=str))
assert parsed["agent_id"] == "test"
```

## invoke_agent Protocol

`invoke_agent` is a thin pass-through: it calls the provided `AgentInvoker` and returns the invoker's receipt. Test with an async stub:

```python
import asyncio
from dharma_swarm.spine import invoke_agent, EvidenceReceipt, RoutingDecision

async def test_invoker(task, agent_id, context_id, routing):
    return EvidenceReceipt(agent_id=agent_id, context_id=context_id, task_id=task.get("id", ""))

routing = RoutingDecision(agent_id="a1", provider="anthropic", model="claude-fable-5")
result = asyncio.run(invoke_agent({"id": "t1"}, "a1", "ctx1", routing, invoker=test_invoker))
assert result.agent_id == "a1"
```

## Doctrine Reference

The spine is defined in `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`. §11's five acceptance scenarios:

1. Normal path → `status="ok"`, `error_source="none"`
2. Task missing → `status="failed"`, `error_source="task_missing"`
3. Runner missing → `status="failed"`, `error_source="runner_missing"`
4. Both missing → `status="failed"`, `error_source="task_and_runner_missing"`
5. Provider failure → `error_source="provider_failed"` (never conflated with dispatch dropoff)

## Output Format

```
SPINE TEST VERDICT: PASS | FAIL
- acceptance (dropoff sources): <N passed> (all 5 §11 scenarios covered)
- gate REJECT case: exit=<1?>   gate PASS case: exit=<0?>   temp files removed: <yes>
- type invariants: frozen=<ok> otel=<ok> json-roundtrip=<ok>
- regression sweeps: <delta vs baseline per file>
```

## Do NOT

- Do not test only the gate's PASS side — the REJECT case is the point of a gate.
- Do not leave temp violation files behind.
- Do not assert on frozen test counts from this doc — re-derive from a same-session baseline.
- Do not "fix" a gate failure by widening `_is_grandfathered()` or deleting a `# spine:` requirement; that's weakening the gate, which is doctrine-forbidden.
- Do not add new sqlite stores to dodge the gate — extend existing spine owners.
