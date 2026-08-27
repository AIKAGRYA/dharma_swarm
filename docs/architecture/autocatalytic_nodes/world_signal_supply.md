---
title: World-Signal Supply Chain
status: active_reference
authority: local_evidence
---

# World-Signal Supply Chain

Producer: World Radar's Go bridge writes raw observations, typed signals, health, and ledgers. It is bound to `rsi-lab-meghadharma-2026-08` and `sublimation-forge-2026-08`.

Contract: consume `promoted_feedback`; apply `ground_feedback`; emit `grounded_signal` to [Persistent Agent / Sarathi](sarathi_runtime.md). During local rehearsal the initial input is explicitly a fixture, not a fresh world observation.

Proof surfaces: [`go_bridge.py`](../../../dharma_swarm/world_radar/go_bridge.py) and [`test_world_radar_go_bridge.py`](../../../tests/test_world_radar_go_bridge.py).

Current adapter projection: `world_radar.historical_receipt_projection` content-addresses the committed World Radar closure receipt and emits `historical_grounded_fixture`. It explicitly records `bronze_bound = false`, `fresh_signal_promoted = false`, and no causal join to the current input.

Promotion obligations:

- bind every promoted signal to a fresh bronze source receipt;
- preserve source/correlation identity into downstream work;
- resolve Chamber predictions against actual World Radar evidence.

Forbidden claim: repository code or a rehearsal artifact is not evidence that the external world was freshly sensed.

Operator page: `/dashboard/organism/world_signal_supply`.
