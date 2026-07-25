# 06 — Proof Gates

> **Collapse-lane gate record:** Gates 1–9 describe the work that landed through
> PR #821. The current promotion ladder and remaining effect/service proof are
> owned by
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md).

## Ten gates

| Gate | Requirement | Current status |
|---:|---|---|
| 1 | Deterministic reversibility gate committed and tested. | **DONE-on-fork** at `f18fe8476`; **PORTED-in-Phase-A** at `8a3a2e657`; scoped test command below passed. |
| 2 | `holon_wake_cycle()` gates caller-supplied `planned_action` before work. | Done in `dharma_swarm/holon_runtime.py`; tests cover safe and blocked actions. |
| 3 | Sarathi is registered as a wake profile without forking the wake shell. | Done in `scripts/runtime/codex_composer_wake_loop.py`; tests cover `sarathi`. |
| 4 | Code/runtime boundary is documented and runtime state is not committed. | Done in `02_CODEBASE_RUNTIME_BOUNDARY.md`; no runtime state added. |
| 5 | Hermes-organ comparison distinguishes exists/partial/missing/scattered. | Done in `03_HOLON_SYSTEM_CODE_MAP.md`. |
| 6 | Orphan maps are metabolized. | `AGENT_HOLON_CODE_MAP.md` and `HOLON_RUNTIME_FULL_ESTATE_MAP.md` are committed under `docs/architecture/` and linked from README. |
| 7 | Duplicate holon fork removed after importer migration. | Done in Phase B: `scripts/verify_holon_harness_prod.py` now imports `dharma_swarm.holon_runtime`; `holon/` removed. |
| 8 | `sprawl_guard.py` exits `0` on the clean branch. | Done in Phase B; output below. |
| 9 | Sarathi facade/package/runtime wrapper exists without source-in-runtime. | Done in Phase C: repo source under `dharma_swarm/holon_system/`; runtime wrapper is thin and imports repo code. |
| 10 | Unattended proof exists before any `wake_loop_active=true` claim. | Pending; no alive claim made. |

## Verification already run in Phase A

```text
$ cd /Users/dhyana/ds_holon_collapse_20260707
$ .venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon_runtime.py tests/test_codex_composer_wake_loop.py -q
.......................................                                  [100%]
39 passed in 0.62s
```

## Anti-sprawl harness contract

Every new map must be linked from `README.md` or it is sprawl. The collapse
spine is not considered done by prose; it is done only when:

```bash
python3 scripts/governance/sprawl_guard.py
```

exits `0` on `feat/holon-system-collapse-base`.

## Phase B verification

```text
$ python3 scripts/governance/sprawl_guard.py; echo EXIT=$?
[1] SINGLETON SYMBOLS
  OK   def load_holon -> dharma_swarm/holon_bridge.py
  OK   def holon_wake_cycle -> dharma_swarm/holon_runtime.py
[2] FORBIDDEN IMPORTS
  OK   no runtime import of holon.holon_bridge
  OK   no runtime import of holon.holon_runtime
[3] COPY DRIFT
  holon_bridge.py: 1 tracked copies, 1 DISTINCT contents
  holon_runtime.py: 1 tracked copies, 1 DISTINCT contents
RESULT: CLEAN — no sprawl findings.
EXIT=0

$ .venv/bin/python -m pytest tests/test_holon*.py tests/test_reversibility_gate.py tests/test_codex_composer_wake_loop.py -q
108 passed, 1 warning in 1.16s
```

## Phase C verification

```text
$ python3 scripts/governance/sprawl_guard.py
RESULT: CLEAN — no sprawl findings.

$ .venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon*.py tests/test_codex_composer_wake_loop.py tests/test_holon_system_imports.py -q
116 passed, 1 warning in 1.12s

$ DHARMA_SWARM_REPO=/Users/dhyana/ds_holon_collapse_20260707 ~/.dharma/agents/sarathi/gateway/sarathi_gateway.py
schema_version=dharma.sarathi.gateway_snapshot.v1
wake_loop_active=false
alive_claim=false
```
