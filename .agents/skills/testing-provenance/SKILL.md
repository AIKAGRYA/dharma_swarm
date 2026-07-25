---
name: testing-provenance-ontology
description: Test telic seam provenance, ontology schema changes, and task board/telos graph methods. Use when verifying changes to telic_seam.py, ontology.py, task_board.py, telos_graph.py, or agent_runner.py dispatch wiring.
---

# Testing Provenance & Ontology Changes

**Purpose:** prove that a change to the telic seam / ontology surface actually persists provenance — not just that the code imports. The #1 failure mode on this surface is silent: `OntologyRegistry.create_object()` returns `(None, [errors])` instead of raising, so a broken schema looks green unless you assert on the created object.

## Environment Setup

Always run from the repo root of the checkout under test. Never hardcode a home directory — checkouts live in different places on different hosts (Mac worktrees, `/home/ubuntu`, remote containers).

```bash
cd "$(git rev-parse --show-toplevel)"
[ -f .venv/bin/activate ] && source .venv/bin/activate   # else: python3 -m pip install -e ".[dev]"
```

## Procedure

1. **Targeted tests first** (fast, ~2s):
   ```bash
   pytest tests/test_telic_seam.py tests/test_task_board.py tests/test_telos_graph.py -v --tb=short
   ```
2. **If the change touches an ontology enum**, run the round-trip check in "Ontology Schema Enum Validation" below. This is mandatory, not optional.
3. **Run the adversarial patterns** relevant to the change (see below) — at least one per changed behavior.
4. **Full suite last**, as a regression sweep:
   ```bash
   pytest tests/ -q
   ```
   Compare failures against `git stash && pytest tests/ -q` (or a clean main checkout) — never against a remembered failure count. Pre-existing-failure tallies rot; only a same-session baseline diff is evidence.
5. **Commit gates** (when committing from this checkout):
   ```bash
   SKIP=semgrep-local pre-commit run --all-files
   # hot-path files (agent_runner.py, orchestrator.py, ...) require the ACK:
   DHARMA_UPLIFT_ACK=impact-checked SKIP=semgrep-local git commit -m "msg [impact-checked]"
   ```

## Critical: Ontology Schema Enum Validation

When adding an enum value to an ontology type (e.g. a new `action_type` on `ActionProposal`), you MUST update **both**:

1. The code-level whitelist (e.g. the `telic_seam.py` topology check)
2. The ontology schema enum in `ontology.py` (e.g. `_ACTION_PROPOSAL` PropertyDef `enum_values`)

If only the code whitelist is updated, `create_object()` silently returns `(None, [error_list])`, `record_dispatch` swallows the None, and callers never notice. **Test it explicitly:**

```python
from dharma_swarm.ontology import OntologyRegistry
registry = OntologyRegistry.create_dharma_registry()
obj, errors = registry.create_object(..., action_type="<new-value>", ...)
assert obj is not None, f"schema rejected new enum value: {errors}"
```

## Test Fixture Construction

The `TelicSeam` constructor needs a real registry and lineage:

```python
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.lineage import LineageGraph
from dharma_swarm.telic_seam import TelicSeam
from dharma_swarm.models import Task, TaskPriority

registry = OntologyRegistry.create_dharma_registry()
lineage = LineageGraph(db_path=str(tmp_path / "test_lineage.db"))
seam = TelicSeam(registry=registry, lineage=lineage)
```

- Do NOT use `TelicSeam(path=...)` in tests — the path-based constructor may not register all required ontology types.
- Use pytest `tmp_path`, not a shared `/tmp` file — parallel runs must not share a db.
- `TaskPriority` values are `LOW`, `NORMAL`, `HIGH`, `URGENT` (there is no MEDIUM).
- `Task(title=..., description=..., priority=...)` is enough; `status` is optional and `id` auto-generates.

## Adversarial Test Patterns

1. **Topology whitelist round-trip:** record a dispatch with the new topology value, read the stored `action_type` property back off the ontology object, assert it equals the new value — not the silent fallback `"dispatch"`.
2. **Orphan proposal:** create a dispatch, set `status="rejected"` on the proposal, run `lifecycle_integrity_report()`, assert `proposals_without_outcome` is empty; then create a second dispatch left at `"proposed"` and assert it IS flagged.
3. **Method existence:** call the new method with a matching query (assert expected object) and a non-matching query (assert `None`).

## Output Format

End every run with this verdict block — every line backed by a command you actually ran:

```
PROVENANCE TEST VERDICT: PASS | FAIL
- targeted tests: <N passed / M failed> (exit <code>)
- enum round-trip: <ok | not applicable | FAILED: created object was None>
- adversarial patterns run: <which of 1/2/3, results>
- full-suite delta vs baseline: <+N new failures | none>
```

A FAIL verdict must name the failing test/assert and the file:line it implicates.

## Do NOT

- Do not assert against remembered/frozen failure counts ("~74 pre-existing failures") — always diff against a same-session baseline.
- Do not treat `record_dispatch` returning without exception as success — read the stored object back.
- Do not construct `TelicSeam` via `path=` in fixtures.
- Do not skip the schema-enum half of a whitelist change because "the code check passes".
- No secrets are needed on this surface — if a test seems to need one, the test is wrong.
