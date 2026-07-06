# Sarathi Apex Build — Front Door

**This is the obvious front door for the whole holon-system build.** Read the
numbered files in order. Legacy files are retained and linked at the bottom so
nothing is lost, but the numbered set is canonical.

## What we are building (one line)

Our own **Hermes-class holon system** — identity + provider routing + persistent
wake kernel + governed runtime + orchestration + A2A transport + semantic
responders + gateway + observability + packaging/CLI + proof gates. **Sarathi is
the apex continuity holon that sits on top of that system — not the whole build.**

## Read order (canonical)

1. [`00_START_HERE.md`](00_START_HERE.md) — orientation + the locked sentence + "alive" definition.
2. [`01_CURRENT_STATE.md`](01_CURRENT_STATE.md) — live snapshot (git, dgc, runtime counts, Sarathi surfaces).
3. [`02_CODEBASE_RUNTIME_BOUNDARY.md`](02_CODEBASE_RUNTIME_BOUNDARY.md) — dharma_swarm/ vs ~/.dharma vs ~/.hermes, and the drift.
4. [`03_HOLON_SYSTEM_CODE_MAP.md`](03_HOLON_SYSTEM_CODE_MAP.md) — Hermes-class organs → our code (exists/partial/scattered/missing).
5. [`04_PERSISTENT_AGENT_RELATION.md`](04_PERSISTENT_AGENT_RELATION.md) — the lineage ladder up to the apex.
6. [`05_SARATHI_APEX_MAP.md`](05_SARATHI_APEX_MAP.md) — what Sarathi is + its target source package.
7. [`06_PROOF_GATES.md`](06_PROOF_GATES.md) — gate-ordered next work; what authorizes "alive".
8. [`07_BACKLOG.md`](07_BACKLOG.md) — safe-to-change, next steps, do-not-touch.
9. [`90_ANTI_SPRAWL_HARNESS.md`](90_ANTI_SPRAWL_HARNESS.md) — the rules that stop the next map from scattering.

## Answer these in under 60 seconds

- What are we building? → this README + `03_HOLON_SYSTEM_CODE_MAP.md`
- Where is the code? → `03` (map) + `dharma_swarm/holon_system/` (facade package)
- Where is runtime state? → `02_CODEBASE_RUNTIME_BOUNDARY.md`
- Sarathi vs the holon system? → this README + `05_SARATHI_APEX_MAP.md`
- Hermes-m5 vs our lineage? → `02` + `04_PERSISTENT_AGENT_RELATION.md`
- Which organs exist / are missing? → `03_HOLON_SYSTEM_CODE_MAP.md`
- Next proof gate? → `06_PROOF_GATES.md`
- What can I safely change / not touch? → `07_BACKLOG.md`

## Non-negotiable current truth

- Sarathi's identity/mind exists under `~/.dharma/agents/sarathi`; its runtime
  body is **not alive** (`service_alive=false`, `wake_loop_active=false`).
- Code lives in git (`dharma_swarm/`); mutable runtime state lives under
  `~/.dharma`; `~/.hermes` is a third-party product we benchmark, not our lineage.
- No new `load_holon`, `holon_wake_cycle`, orchestrator, task store, model
  router, A2A bus, or receipt spine. Facades/wrappers over existing owners only.
- No "alive" or "beats Hermes" claim without a receipt (proof gates 9/10).

## Supporting / historical docs (linked, non-canonical)

- [`HOLON_SYSTEM_CODE_ORGANIZATION.md`](HOLON_SYSTEM_CODE_ORGANIZATION.md) — long-form organ map + scale comparison (backs doc 03).
- [`11_PERSISTENT_AGENT_RELATION.md`](11_PERSISTENT_AGENT_RELATION.md) — full file:line lineage table (backs doc 04).
- [`12_LOAD_HOLON_COLLAPSE_PLAN.md`](12_LOAD_HOLON_COLLAPSE_PLAN.md) — the holon_bridge fork collapse plan.
- [`91_SPRAWL_HARNESS_RUNBOOK.md`](91_SPRAWL_HARNESS_RUNBOOK.md) — how to run `sprawl_guard.py`.
- [`CURRENT_MAP_2026-07-06.md`](CURRENT_MAP_2026-07-06.md) — earlier working map draft.
- [`SCRATCHPAD_2026-07-06.md`](SCRATCHPAD_2026-07-06.md) — verification scratchpad.

## Executable guards

```bash
cd /Users/dhyana/dharma_swarm
.venv/bin/python -m pytest tests/test_holon_system_imports.py tests/test_reversibility_gate.py -q
python3 scripts/governance/sprawl_guard.py   # red until the holon/ fork collapse (doc 12)
```
