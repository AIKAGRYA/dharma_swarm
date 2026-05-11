---
name: testing-provenance-ontology
description: Test telic seam provenance, ontology schema changes, and task board/telos graph methods. Use when verifying changes to telic_seam.py, ontology.py, task_board.py, telos_graph.py, or agent_runner.py dispatch wiring.
---

# Testing Provenance & Ontology Changes

## Environment Setup

```bash
cd /home/ubuntu/dharma_swarm
source .venv/bin/activate
```

## Key Testing Commands

```bash
# Core provenance/ontology tests (fast, ~2s)
pytest tests/test_telic_seam.py tests/test_task_board.py tests/test_telos_graph.py -v --tb=short

# Full suite (slow, ~60s, expect ~74 pre-existing failures on main)
pytest tests/ -q

# Pre-commit hooks (skip semgrep if binary not installed)
SKIP=semgrep-local pre-commit run --all-files

# Hot-path files (agent_runner.py, orchestrator.py, etc.) require ACK
DHARMA_UPLIFT_ACK=impact-checked SKIP=semgrep-local git commit -m "msg [impact-checked]"
```

## Critical: Ontology Schema Enum Validation

When adding new enum values to ontology types (e.g., adding a new `action_type` to `ActionProposal`), you MUST update **both**:

1. The code-level whitelist (e.g., `telic_seam.py` topology check)
2. The ontology schema enum in `ontology.py` (e.g., `_ACTION_PROPOSAL` PropertyDef `enum_values`)

If only the code whitelist is updated, `OntologyRegistry.create_object()` will **silently return `(None, [error_list])`** instead of raising. This is easy to miss because the telic_seam `record_dispatch` method catches the None and returns None, which callers may ignore.

**Test this explicitly:** Create an `OntologyRegistry.create_dharma_registry()`, call `create_object` with the new enum value, and assert the result is not None.

## Test Fixture Construction

The `TelicSeam` constructor needs a proper registry and lineage:

```python
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.lineage import LineageGraph
from dharma_swarm.telic_seam import TelicSeam
from dharma_swarm.models import Task, TaskPriority

registry = OntologyRegistry.create_dharma_registry()
lineage = LineageGraph(db_path="/tmp/test_lineage.db")
seam = TelicSeam(registry=registry, lineage=lineage)
```

Do NOT use `TelicSeam(path=...)` for testing — the path-based constructor may not register all required ontology types.

## TaskPriority Enum Values

The enum is: `LOW`, `NORMAL`, `HIGH`, `URGENT` (not MEDIUM).

## Task Model

When constructing `Task` objects for tests, `status` is optional. The `id` field auto-generates if not provided.

```python
task = Task(title="test", description="desc", priority=TaskPriority.NORMAL)
```

## Test Class Paths

- `tests/test_task_board.py` — top-level functions: `test_get_by_title`, `test_get_by_title_dedup`
- `tests/test_telos_graph.py` — class-based: `TestCRUD::test_get_by_name`, `TestCRUD::test_get_by_name_dedup`
- `tests/test_telic_seam.py` — class-based: `TestLifecycleIntegrity::test_detects_proposal_without_outcome`

## Adversarial Test Patterns

1. **Topology whitelist test**: Record dispatch with a new topology value, then read the stored `action_type` property directly from the ontology object. Assert it equals the new value (not the fallback `"dispatch"`).

2. **Orphan proposal test**: Create a dispatch, set status to `"rejected"` directly on the proposal object, run `lifecycle_integrity_report()`, assert `proposals_without_outcome` is empty. Then create another dispatch (status stays `"proposed"`), assert it IS flagged.

3. **Method existence test**: Call the new method, assert it returns the expected object for a matching query and `None` for a non-matching query.

## Devin Secrets Needed

No secrets required for provenance/ontology testing — all tests run against in-memory or temp-dir stores.
