---
title: Holon Consolidation Plan — facade to real body
date: 2026-08-01
status: plan
supersedes_claims_in: docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md
---

# Holon Consolidation Plan — facade to real body

Produced by a 12-agent workflow (6 blind inventory sweeps → synthesis → 2 designs →
3 adversarial verifiers). **All three artifacts came back FLAWED.** This document
records only what survived verification, plus the corrections. Companion artifacts:
`docs/reports/hermes_persistent_agent_index_2026-08-01.md` and
`docs/architecture/PERSISTENT_AGENT_DESCRIPTOR.md` — both carry their own errata.

Nothing here has been executed. No file has been moved.

## 0. The finding that changes the plan

The move ordering originally proposed was **wrong, and the verifier reproduced the
break rather than arguing it.**

`dharma_swarm/holon_system/runtime/__init__.py:3-4` **eagerly** imports `.bridge` and
`.wake_cycle`, and `runtime/wake_cycle.py:3` imports back out to
`dharma_swarm.holon_runtime`. That circularity means the first four moves each leave
the repo unimportable:

| After | Failure (each tested in isolation) |
|---|---|
| MOVE 1 (persistence) | `holon_system.runtime` partially initialized |
| MOVE 2 (killswitch) | `import dharma_swarm.holon_runtime` → ImportError |
| MOVE 3 (budget_guard) | `ImportError: cannot import name 'CostLimitExceeded' from partially initialized module` **and** `holon_runtime` fails |
| MOVE 4 (compass) | same class of break |

### MOVE 0 — mandatory prerequisite

Convert `dharma_swarm/holon_system/runtime/__init__.py` to a PEP-562 lazy
`__getattr__` **before any body moves.** Verified: with the lazy `__init__` landed
first, MOVE 1 returns the suite to the exact pre-existing baseline (1 failed, 45
passed — the pre-existing textual failure only).

## 1. What verification confirmed holds

- All 23 source paths exist with **exactly** the stated line counts.
- All 10 named shims are genuinely pure re-exports (dumped and read individually).
- Importer lists for moves 1–7 are **complete** (independently re-grepped).
- `holon_system/` is **47 files / 1,345 lines** — correcting
  `HOLON_RUNTIME_FULL_ESTATE_MAP.md:332` ("43 files ... roughly 360 lines").
- Destination state is as described: `persistence`/`bridge`/`health`/`wake_cycle`
  shims exist; `killswitch`/`budget_guard`/`compass` do not.
- **MOVE 10 is a real live bug**: `pytest tests/test_holon_system_imports.py` FAILS
  on current checkout at `holon_system/authority/permissions.py:3`.

### The reversibility gate stays put — verified empirically

`dharma_swarm/operator_core/reversibility_gate.py` carries an operator ruling at
`:24-26` that it and its import chain stay stdlib-only, because
`scripts/governance/check_automerge_tier_policy.py:66-75` is a fail-closed hard
import run under bare `python3` from `automerge-tier-policy.yml:82` and
`codex-mention-router.yml:261`.

Verified by `sys.modules` diff, not by reading: importing `classify_action` via the
direct path, the facade path, and `holon_system.authority` each pulls **zero**
third-party modules. `risk_patterns.py` imports only `__future__` and `enum` (`:18-20`).

**DO NOT MOVE.** Make `holon_system/authority/reversibility_gate.py` an honest,
self-documenting facade instead.

## 2. Verified move plan

20 shims over 8 real implementations. Phase A sums to 1,032 lines (exact).

| # | From | To | Lines | Importers | Risk |
|---|---|---|---|---|---|
| **0** | `holon_system/runtime/__init__.py` | make lazy (PEP-562) | — | — | **prerequisite** |
| 1 | `holon_persistence.py` | `holon_system/runtime/persistence.py` | 97 | 5 | low |
| 2 | `holon_killswitch.py` | `holon_system/runtime/killswitch.py` | 58 | 7 | low |
| 3 | `holon_budget_guard.py` | `holon_system/runtime/budget_guard.py` | 36 | 2 | low |
| 4 | `holon_compass.py` | `holon_system/runtime/compass.py` | 60 | 3 | low |
| 5 | `holon_bridge.py` | `holon_system/runtime/bridge.py` | 419 | 11 | medium |
| 6 | `holon_health.py` | `holon_system/runtime/health.py` | 79 | 4 | low |
| 7 | `holon_runtime.py` | `holon_system/runtime/wake_cycle.py` | 283 | 9 | medium |
| 8–10 | dead shims: `gateway/operator_brief.py`, `observability/scoreboard.py`, `authority/permissions.py` | delete | 13 | 4 | low |

**Phase C (the four A2A scripts) is DEFERRED.** Its stated justification — that
moving bodies into `dharma_swarm/` fixes the `pyproject.toml:62-63` packaging
inversion — is **false**: all four bodies themselves import from `scripts/`
(`pr_merge_control.py`, `a2a_topology.py`), so the inversion survives the move. Phase C
needs its own design pass.

## 3. Ownership collisions (checked against ACTIVE_TRACK.yaml)

| Surface | Owner | Effect |
|---|---|---|
| `dharma_swarm/orchestrator.py` | `dharmagraph-engine-2026-07` | **HARD BLOCK** — track records "do not edit beyond the minimal seam call". Do not move; `holon_system/orchestration/fanout.py:3` stays a pointer. |
| `dharma_swarm/autonomous_agent.py` | `repository-titanium-hardening-2026-07` | Collides with MOVE 5 — `:304` has a lazy `from dharma_swarm.holon_bridge import load_holon`. One line, but needs that track's consent. |
| `Makefile:826` | `repository-titanium-hardening-2026-07` | Collides with deferred Phase C. Mitigation (CLI stub) must be **run**, not assumed. |
| `pyproject.toml` | `dharmagraph-engine-2026-07` | Not edited by this plan. |
| `automerge.yml`, `pr_merge_control.py` | `merge-master-mike-d4-2026-06` | Not touched — because the gate does not move. |

**Tier-2 paths this plan touches: none.** (`automerge_tier_policy.json:50`,
`reversibility_gate.py:70`, `risk_patterns.py:73`, `proof_gates.py:75`, `a2a/**:77`.)

Everything in Phase A matched **no** owned-surface glob of any of the 10 active tracks.

## 4. Estate-map corrections to apply

Verified ABSENT (`test -e` false) — purge from `HOLON_RUNTIME_FULL_ESTATE_MAP.md`:
`holon_service_liveness.py`, `holon_canonical_state.py`, `holon_truth_projection.py`
(`:343-344`), `scripts/runtime/fugu_ultra_semantic_responder.py`,
`scripts/runtime/a2a_resident_executor.py` (`:345`).

Verified PRESENT but listed absent: `scripts/runtime/codex_composer_semantic_responder.py`
(1,411 lines). Fix `:344` to name only Fugu.

**Stale claim at `:333-334`** — "no production consumers outside the facade itself"
is now FALSE: `sarathi_wake_daemon.py:81,85,86` and `sarathi_proof_window.py:43-55`
import `holon_system.sarathi.{plan,roster,wake,delegate,proof}`, and
`.github/workflows/sarathi-wake-lane.yml:152,160` runs both under bare `python3`.
`holon_system/sarathi/` is already load-bearing.

## 5. Packet 1 — corrections before building it

The Packet 1 spec also failed verification. Two findings change its shape:

**The kernel→A2A binder already exists.** The spec claimed nothing joins
`build_task_receipt` to runtime truth. False:
`dharma_swarm/operator_core/living_agent_kernel.py:2085` imports it, and
`LivingAgentKernel._closeback_a2a` (`:2058-2145`) calls it at `:2092`. Packet 1 must
reconcile with that, not duplicate it.

**Confirmed absences** (repo-wide grep): no type named `ExecutionLease` — it is
dict-payload based (`build_execution_lease:116`, `validate_execution_lease:187`,
`find_execution_lease_for_task:315`); no A2A receipt *type* — `build_task_receipt`
(`a2a_task_lifecycle.py:102`) returns a dict; no `RuntimeState` type; and
`reversibility_class`, `verifier_identity`, `GovernedEffectProven`, `ReceiptBound`
are genuinely absent.

**No live `spend_fn` exists.** The hook at `holon_runtime.py:229,:255` has zero
production callers; `scripts/holon_run.py:73-75` passes `cap_usd=0.0`, which
`holon_budget_guard.py:30-31` treats as **unbounded**; `sarathi_wake_daemon.py:387`
reads `result['cost_usd']`, which nothing in `dharma_swarm` sets; `cost_tracker.log_cost`
(`:70`) has only test callers. Budget enforcement is currently decorative.

**Two more traps the spec missed:**
- `execution_lease.py:177-178,:241` — empty `allowed_paths` / `allowed_actions` mean
  **permit-all**, silently defeating `effect_scope` if a lease is built without them.
- `living_agent_kernel.py:1030,:1086,:1135,:1166` — a **second** lease concept (wake
  leases) that must be reconciled with `execution_lease`, since both are called leases.
- `closure_v0.py:69 ClosureEvidenceReceipt` — a third correlation layer named at
  `a2a_task_lifecycle.py:13`, omitted from the proposed `ReceiptBound` conjunction.

The proposed acceptance test is **not runnable as written** (`close_task` raises
`A2ATaskLifecycleError` because the fixture never seeds a queue row) and **not
hermetic** (`KernelRunStore` defaults to `Path.home()/.dharma/living_agent_kernel`
at `living_agent_kernel.py:51` and mkdirs at `:788`).

## 6. Order of work

1. MOVE 0 — lazy `runtime/__init__.py`, prove the suite returns to baseline.
2. Phase A moves 1–7, one commit each, suite green between every one.
3. Delete the three dead shims (fixes the live `test_holon_system_imports.py` failure).
4. Apply the §4 estate-map corrections.
5. Re-run the index sweep for the surfaces §the errata lists as missed (cron subsystem,
   `browser_agent`, `synthesis_agent`, `sleep_time_agent`, `garden_daemon`, the sixth registry).
6. Re-spec Packet 1 against §5, then build it.
