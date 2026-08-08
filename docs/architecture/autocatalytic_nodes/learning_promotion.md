---
title: Learning and Promotion Membrane
status: active_reference
authority: projection_only
---

# Learning and Promotion Membrane

Producer: Arena corpus and routing-feedback primitives exist, but the corpus explicitly does not promote itself into routing. This candidate node binds `orchestration-arena-v1-2026-06` and `organism-rewire-2026-07`.

Contract: consume `external_outcome`; apply `promote_verified_learning`; emit `promoted_feedback` to [World-Signal Supply](world_signal_supply.md), closing the ring.

Proof surfaces: [`corpus.py`](../../../dharma_swarm/coordination/arena/corpus.py) and [`test_agent_runner_routing_feedback.py`](../../../tests/test_agent_runner_routing_feedback.py).

Current adapter projection: `arena.zero_weight_learning_gate` verifies the Arena receipt-to-corpus digest and emits `promotion_blocked`. The routing-weight delta is exactly zero; no independent external outcome or routing authority is present.

Promotion obligations:

- require independent outcome evidence and attenuated routing authority;
- make rollback and expiration part of the promotion value;
- preserve provenance into the next world-signal cycle.

Forbidden claim: model consensus, transport ACK, self-authored confidence, identity attestation, or social activity confers neither truth nor standing.

Operator page: `/dashboard/organism/learning_promotion`.
