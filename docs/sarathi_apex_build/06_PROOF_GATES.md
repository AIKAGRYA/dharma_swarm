# 06 — Proof Gates

## Ten gates

| Gate | Requirement | Current status |
|---:|---|---|
| 1 | Deterministic reversibility gate committed and tested. | **DONE-on-fork** at `f18fe8476`; **PORTED-in-Phase-A** at `8a3a2e657`; scoped test command below passed. |
| 2 | `holon_wake_cycle()` gates caller-supplied `planned_action` before work. | Done in `dharma_swarm/holon_runtime.py`; tests cover safe and blocked actions. |
| 3 | Sarathi is registered as a wake profile without forking the wake shell. | Done in `scripts/runtime/codex_composer_wake_loop.py`; tests cover `sarathi`. |
| 4 | Code/runtime boundary is documented and runtime state is not committed. | Done in `02_CODEBASE_RUNTIME_BOUNDARY.md`; no runtime state added. |
| 5 | Hermes-organ comparison distinguishes exists/partial/missing/scattered. | Done in `03_HOLON_SYSTEM_CODE_MAP.md`. |
| 6 | Orphan maps are metabolized. | `AGENT_HOLON_CODE_MAP.md` and `HOLON_RUNTIME_FULL_ESTATE_MAP.md` are committed under `docs/architecture/` and linked from README. |
| 7 | Duplicate holon fork removed after importer migration. | Pending Phase B. |
| 8 | `sprawl_guard.py` exits `0` on the clean branch. | Pending Phase B; expected to fail until `holon/` is removed. |
| 9 | Sarathi facade/package/runtime wrapper exists without source-in-runtime. | Pending Phase C. |
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
