# Sarathi Apex / Holon System Front Door

Status: **v1.1 organization lane on `feat/holon-system-collapse-base`**. This
is a source/runtime organization and proof-gate lane, not a claim that Sarathi is
alive.

## Read order

1. [`00_START_HERE.md`](00_START_HERE.md) — locked thesis, current lane, and no-overclaim rules.
2. [`01_CURRENT_STATE.md`](01_CURRENT_STATE.md) — read-only state capture from this clean branch.
3. [`02_CODEBASE_RUNTIME_BOUNDARY.md`](02_CODEBASE_RUNTIME_BOUNDARY.md) — repo vs `~/.dharma` vs `~/.hermes`.
4. [`03_HOLON_SYSTEM_CODE_MAP.md`](03_HOLON_SYSTEM_CODE_MAP.md) — holon-system organs and Hermes comparison.
5. [`04_PERSISTENT_AGENT_RELATION.md`](04_PERSISTENT_AGENT_RELATION.md) — registry → persistent agent → living kernel → holon runtime → Sarathi.
6. [`05_SARATHI_APEX_MAP.md`](05_SARATHI_APEX_MAP.md) — what Sarathi is, what surfaces are still missing.
7. [`06_PROOF_GATES.md`](06_PROOF_GATES.md) — ten gates and current evidence.
8. [`07_BACKLOG.md`](07_BACKLOG.md) — exact next work by phase.
9. [`90_ANTI_SPRAWL_HARNESS.md`](90_ANTI_SPRAWL_HARNESS.md) — surface-claim policy.
10. [`91_SPRAWL_HARNESS_RUNBOOK.md`](91_SPRAWL_HARNESS_RUNBOOK.md) — one-command done gate.

Linked architecture maps that used to be orphaned:

- [`../architecture/AGENT_HOLON_CODE_MAP.md`](../architecture/AGENT_HOLON_CODE_MAP.md)
- [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md)

## Ten orientation answers in under 60 seconds

1. **What is the source branch?** `feat/holon-system-collapse-base`, created as a clean worktree from `origin/main`.
2. **Is `agent/magpie-seed` canonical?** No. It held the useful brick `f18fe8476`; this lane ports the brick and leaves that branch untouched.
3. **Is Sarathi alive?** No. Sarathi has identity/runtime traces, but no proof-backed unattended wake loop; `wake_loop_active=true` remains forbidden.
4. **What is the holon system?** `identity + provider routing + persistent wake kernel + governed runtime + orchestration + A2A transport + semantic responders + gateway + observability + packaging/CLI + proof gates`.
5. **What is Sarathi?** The apex occupant/wrapper of the holon system: reversibility gate + roster + brief + continuity surfaces over the existing substrate.
6. **What is the canonical runtime primitive home?** `dharma_swarm/holon_bridge.py::load_holon` and `dharma_swarm/holon_runtime.py::holon_wake_cycle`.
7. **What gets deleted in Phase B?** The standalone `holon/` fork after its two importers migrate. If `dharma_swarm/holon_system/` appears in this clean branch before Phase C, it must be a fresh facade package, not the dead scaffold.
8. **What proves collapse?** `python3 scripts/governance/sprawl_guard.py` exits `0` on this clean branch.
9. **Where does mutable runtime state live?** `~/.dharma`; source code, tests, schemas, and docs live in git; Hermes Agent lives under `~/.hermes` as a side ecosystem.
10. **What is the next exact step after Phase A?** Delete the duplicate `holon/` fork only after migrating its importers, then run the sprawl guard and scoped holon tests.

## Non-negotiable truths

- Code-deterministic reversibility gating is now ported to this clean branch in commit `8a3a2e657`.
- Runtime state is not committed here.
- New maps must be linked from this README or they are sprawl.
- Existing substrate is reused first; no second orchestrator, task store, model router, A2A bus, or receipt spine.
