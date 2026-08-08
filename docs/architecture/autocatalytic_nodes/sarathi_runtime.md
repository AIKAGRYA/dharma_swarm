---
title: Persistent Agent / Sarathi Runtime
status: active_reference
authority: local_evidence
---

# Persistent Agent / Sarathi Runtime

Producer: the Sarathi wake daemon consumes grounded signals and the read-only cybernetic audit backlog. It is bound to `organism-rewire-2026-07` and `loop-closure-2026-06`.

Contract: consume `grounded_signal`; apply `prioritize_grounded_work`; emit `prioritized_work` to [DharmaGraph Durable Execution](dharmagraph_execution.md).

Proof surfaces: [`sarathi_wake_daemon.py`](../../../scripts/runtime/sarathi_wake_daemon.py) and [`test_sarathi_wake_daemon.py`](../../../tests/test_sarathi_wake_daemon.py).

Current adapter projection: `sarathi.pure_bootpack_plan` calls the deterministic `build_plan` seam and the read-only pulse projection. It emits `planned_not_accepted`; dispatch, wake-loop liveness, and restart recovery remain unproven.

Promotion obligations:

- prove restart recovery and one real identity-bound dispatch from a persistent daemon;
- retain the source receipt and loop-audit correlation chain;
- distinguish planned backlog from accepted work.

Forbidden claim: a boot pack, scheduled wake, or local A2A hop is not proof of a continuously living chief-of-staff runtime.

Operator page: `/dashboard/organism/sarathi_runtime`.
