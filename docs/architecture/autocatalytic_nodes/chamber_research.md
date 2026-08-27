---
title: Chamber Research and Evolution
status: active_reference
authority: local_evidence
---

# Chamber Research and Evolution

Producer: Chamber trace and prediction machinery turns bounded experiments into falsifiable proposals and Frontier Ledger evidence. It is bound to `rsi-lab-meghadharma-2026-08` and `sublimation-forge-2026-08` as the two active research lanes.

Contract: consume `selected_experiment`; apply `research_falsifiable_change`; emit `proposed_change` to [Assurance & Merge](assurance_merge.md).

Proof surfaces: [`traces.py`](../../../dharma_swarm/chamber/traces.py) and [`test_chamber_traces.py`](../../../tests/test_chamber_traces.py).

Current adapter projection: `chamber.receipt_corpus_projection` uses `read_corpus` to validate row digests and snapshots the transcendence, G1, and Frontier receipts. It emits `blocked_no_proposal`; no authorized experiment or proposed change exists.

Promotion obligations:

- isolate untrusted live solvers at process, filesystem, and network boundaries;
- resolve predictions against source-linked World Radar receipts;
- preserve the distinction between a hypothesis, proposal, and verified change.

Forbidden claim: novelty, transcendence scoring, or a trace corpus is not proof that a proposed change is safe or effective.

Operator page: `/dashboard/organism/chamber_research`.
