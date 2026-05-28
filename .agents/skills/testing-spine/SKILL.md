---
name: testing-spine
description: Test the Runtime Truth Spine (EvidenceReceipt, RoutingDecision, invoke_agent, anti-accretion gate). Use when verifying changes to dharma_swarm/spine/, tools/spine_check.py, or tests/test_dispatch_dropoff_sources.py.
---

# Testing the Runtime Truth Spine

## Environment Setup

```bash
cd /home/ubuntu/repos/dharma-swarm
```

No special dependencies needed beyond the project's standard pytest setup.

## Key Testing Commands

```bash
# Spine acceptance tests (11 tests, <1s)
pytest tests/test_dispatch_dropoff_sources.py -v --tb=short

# Anti-accretion CI gate
python3 tools/spine_check.py

# Provenance regression (tests task dispatch area)
pytest tests/test_telic_seam.py tests/test_task_board.py tests/test_telos_graph.py -v

# Opportunity loop regression
pytest tests/test_authority_revenue_loop.py -v

# A2A regression (NOTE: file is test_a2a.py, NOT test_a2a_e2e.py)
pytest tests/test_a2a.py tests/test_a2a_spec_conformance.py -q
```

## Anti-Accretion Gate Behavior

The gate (`tools/spine_check.py`) enforces that files importing `sqlite3` or `aiosqlite` must declare a `# spine:` header comment. **Critical detail:** In PR A, the gate only enforces on files under `dharma_swarm/spine/`. All other files are grandfathered via `_is_grandfathered()`. Future PRs will shrink the grandfather list.

To test REJECT behavior, create a violation file under `dharma_swarm/spine/` (not `dharma_swarm/` root):

```bash
# REJECT case: no declaration
cat > dharma_swarm/spine/test_violation_temp.py << 'EOF'
import sqlite3
def bad(): pass
EOF
python3 tools/spine_check.py  # Should exit 1

# PASS case: proper declaration
cat > dharma_swarm/spine/test_declared_temp.py << 'EOF'
# spine: writes EvidenceReceipt
import sqlite3
def good(): pass
EOF
python3 tools/spine_check.py  # Should exit 0 (after removing violation file)

# Cleanup
rm -f dharma_swarm/spine/test_violation_temp.py dharma_swarm/spine/test_declared_temp.py
```

## Spine Type Verification

```python
# Frozen immutability check
from dharma_swarm.spine import EvidenceReceipt, RoutingDecision
r = EvidenceReceipt(agent_id="test")
try:
    r.agent_id = "mutated"  # Must raise FrozenInstanceError
except Exception as e:
    assert "frozen" in str(type(e)).lower() or "FrozenInstanceError" in str(type(e))

# OTel export shape
span = r.to_otel_span()
assert "gen_ai.operation.name" in span["attributes"]
assert "dharma.receipt_id" in span["attributes"]

# JSON round-trip
import json
d = r.to_dict()
json_str = json.dumps(d, default=str)
parsed = json.loads(json_str)
assert parsed["agent_id"] == "test"
```

## invoke_agent Protocol

The `invoke_agent` function is a thin pass-through in PR A. It calls the provided `AgentInvoker` and returns whatever receipt the invoker returns. Testing it requires creating an async invoker:

```python
import asyncio
from dharma_swarm.spine import invoke_agent, EvidenceReceipt, RoutingDecision

async def test_invoker(task, agent_id, context_id, routing):
    return EvidenceReceipt(agent_id=agent_id, context_id=context_id, task_id=task.get("id", ""))

routing = RoutingDecision(agent_id="a1", provider="anthropic", model="claude-4")
result = asyncio.run(invoke_agent({"id": "t1"}, "a1", "ctx1", routing, invoker=test_invoker))
assert result.agent_id == "a1"
```

## Known Test Expectations

- `test_authority_revenue_loop.py`: Expect 22 passed, 1 skipped (orphan ValueEvent test is a documented pre-existing skip)
- `test_a2a_spec_conformance.py`: ~76 tests
- `test_a2a.py`: ~59 tests
- `test_dispatch_dropoff_sources.py`: 11 tests covering all 5 doctrine §11 scenarios

## Doctrine Reference

The spine is defined in `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` (commit 325cd02c). §11 lists the 5 acceptance scenarios:
1. Normal path → status="ok", error_source="none"
2. Task missing → status="failed", error_source="task_missing"
3. Runner missing → status="failed", error_source="runner_missing"
4. Both missing → status="failed", error_source="task_and_runner_missing"
5. Provider failure → error_source="provider_failed" (not confused with dispatch dropoff)

## Devin Secrets Needed

No secrets required — all spine tests run against in-memory stores and dataclass instantiation.