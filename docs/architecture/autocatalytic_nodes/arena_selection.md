---
title: Live Evaluation and Routing Feedback
status: active_reference
authority: local_evidence
---

# Live Evaluation and Routing Feedback

Producer: Arena measures candidates with parity and seeded significance controls. It is bound to `rsi-lab-meghadharma-2026-08` and `sublimation-forge-2026-08`; the superseded Orchestration Arena track remains historical evidence.

Contract: consume `closure_gap`; apply `select_bounded_experiment`; emit `selected_experiment` to [Chamber Research](chamber_research.md).

Proof surfaces: [`measure.py`](../../../dharma_swarm/coordination/arena/measure.py) and [`test_arena_parity_controls.py`](../../../tests/test_arena_parity_controls.py).

Current adapter projection: `arena.hermetic_truth_receipt` validates and snapshots the Arena truth receipt. It emits `candidate_only_not_selected`; the hermetic candidate is not a live measurement, selected experiment, or promotion authority.

Promotion obligations:

- connect significant live measurements to a bounded routing/selection consumer;
- retain `promotion_authorized = false` until an independent authority gate passes;
- keep the labeled corpus from silently changing routing.

Forbidden claim: a measurement receipt, winning score, or model consensus does not authorize promotion.

Operator page: `/dashboard/organism/arena_selection`.
