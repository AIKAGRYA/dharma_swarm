# 06 — Proof Gates (gate-ordered, not mythological)

**Custody: VERIFIED 2026-07-06. A gate is DONE only with a receipt/command.**

Future work is ordered by these gates. Do not skip. Do not claim a later gate
before an earlier one has a receipt. "Done" = a command output or artifact path,
never narration.

| # | Gate | Done when | Status |
|---|---|---|---|
| 1 | deterministic reversibility gate committed + tests pass | `reversibility_gate.py` tracked; `pytest tests/test_reversibility_gate.py` green | **DONE** (`f18fe8476`; 9 passed) |
| 2 | `load_holon` supports `@frontier` / `resolve_top_available_at_wake` | a resolver test: `@frontier` picks top-available model or logs honest fallback | **DONE** — `resolve_top_available_at_wake()` routes through `model_hierarchy.get_live_order()` + `runtime_provider`; `load_holon("sarathi")` resolved to `ollama/glm-5:cloud` on 2026-07-06 |
| 3 | Fugu provider drift resolved or modeled as external | `dgc agent status` emits no `sakana -> defaulting to claude_code` warning, OR `sakana` is a declared external provider | **OPEN** — warning still emitted |
| 4 | Fable standing semantic daemon proven | a fresh `fable_composer` service heartbeat + a semantic reply receipt from an unattended run | **OPEN** — `service_alive=false`, `heartbeat_seen=false` |
| 5 | Sarathi runtime surfaces created | `~/.dharma/a2a_bus/state/sarathi.json`, inbox dir, bridge heartbeat exist (as runtime, with repo map entries) | **OPEN** — all missing |
| 6 | Sarathi gateway wraps `holon_wake_cycle` | `holon_system/sarathi/gateway.py` calls `holon_wake_cycle(planned_action=...)` behind the gate | **PARTIAL** — the `planned_action` seam exists in `holon_runtime`; the gateway module is not built |
| 7 | Sarathi pulse reads Hermes + Codex + Fable/Fugu state | a `pulse.py` run produces a state bundle citing each seat's live liveness | **OPEN** |
| 8 | operator brief produced | a `brief.py` run writes a dated operator brief receipt | **OPEN** |
| 9 | overnight durability proof | one unattended lease-gated run leaves wake receipts across N hours; only then may `wake_loop_active` flip true | **OPEN** — do NOT flip before this |
| 10 | scoreboard: where Hermes wins vs where Sarathi wins | `scoreboard.py` emits a receipts-only comparison; no "we beat Hermes" claim without it | **OPEN** |

## Gate discipline

- Gate 1 is the keystone and it is done. Everything else composes on top.
- Gates 2-4 are substrate correctness (resolver, provider enum, one proven
  standing daemon) and should precede Sarathi-body gates 5-9.
- Gate 9 is the ONLY thing that authorizes `wake_loop_active=true`. Constraints
  #1 and #2 forbid claiming alive/active before it.
- Gate 10 is the ONLY thing that authorizes any "beats Hermes/OpenClaw" claim
  (constraint #3).

## Verification commands per gate

```bash
# gate 1
.venv/bin/python -m pytest tests/test_reversibility_gate.py -q

# gate 2
.venv/bin/python -m pytest tests/test_runtime_provider.py tests/test_holon_bridge.py -q
.venv/bin/python - <<'PY'
from dharma_swarm.holon_bridge import load_holon
h = load_holon("sarathi")
print(h.provider_type, h.model, h.identity.get("_runtime_model_resolution"))
PY

# gate 3 (observe the warning presence)
.venv/bin/python -m dharma_swarm.dgc_cli agent status --json 2>&1 | grep -i sakana || echo "no drift warning"

# gate 4 / 5 (liveness is receipts, not identity)
.venv/bin/python -m dharma_swarm.dgc_cli agent status --json

# gate 6 seam (already present)
.venv/bin/python -m pytest tests/test_holon_runtime.py -q

# anti-sprawl (must reach exit 0 after the holon/ fork collapse)
python3 scripts/governance/sprawl_guard.py
```
