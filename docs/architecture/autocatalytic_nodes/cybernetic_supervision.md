---
title: Cybernetic Supervision and Loop Closure
status: active_reference
authority: local_evidence
---

# Cybernetic Supervision and Loop Closure

Producer: the Cybernetics Codex inspects receipts and loop state; its audit is deliberately read-only. This node is bound to `loop-closure-2026-06`.

Contract: consume `execution_receipt`; apply `diagnose_closure`; emit `closure_gap` to [Live Evaluation & Routing Feedback](arena_selection.md).

Proof surfaces: [`cybernetics_codex.py`](../../../dharma_swarm/cybernetics_codex.py) and [`test_cybernetics_codex.py`](../../../tests/test_cybernetics_codex.py).

Current adapter projection: `cybernetics_codex.committed_audit_projection` projects every non-`CLOSED_LIVE` loop in the content-addressed audit and emits `closure_gaps_observed`. The predecessor execution receipt is not represented as causally joined.

Promotion obligations:

- produce a current-daemon witness that distinguishes receipt presence from domain closure;
- route diagnosed gaps into an owned downstream consumer;
- keep auditor and dispatcher authority separate.

Forbidden claim: a rendered audit or `completed` task row cannot prove external loop closure.

Operator page: `/dashboard/organism/cybernetic_supervision`.
