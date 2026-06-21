# Sensemaking Organ — Architecture (design/handoff, NOT authority)

**Status:** design note · **Track:** `seeing-organ-2026-06` · **Authority:** none — this points to the real owners.
**Full vision:** `docs/vision_maps/2026-06-21_seeing_organ_master_synthesis.md`.

The Seer's optic nerve, wired stage by stage. Each stage closes one seam on real data with a receipt + a
bounded-replay check. No new truth store, no new authority surface; read-models project truth, they never own it.

## The seam map (owners)

```
world (untrusted)
  └─ INTAKE ............ dharma_swarm/world_radar/bronze.py  (raw receipt, content-hash, dedup, boundary signal)
  └─ STAGE 0 SAFETY .... dharma_swarm/world_radar/safety.py  ✅  (untrusted envelope verify + instruction/data fence)
  └─ STAGE 1 VERIFIER .. dharma_swarm/world_radar/frontier_council.py  ✅  (decorrelated cross-falsification → WorldSensemakingReceipt; NO action authority)
  └─ STAGE 2 READ ...... dharma_swarm/world_radar/warrant_handoff.py  ✅  (corroborated receipts → advisory warrant-pressure; DISPATCH_AUTHORITY stays False)
  └─ STAGE 3 PROPOSE ... WorldProposal → memory_kernel promotion gate / telos_gates (24h incubation, blast-radius-graded evidence)  ← future
  └─ OBSERVE ........... orientation_graph.py / make orient  (World Pulse + Sensemaking Health, read-only projection)  ← future
```

✅ = shipped (Stage 0 + Stage 1 + Stage 2). The verifier is the moat: corroboration is *earned* by ≥2 decorrelated
evaluator families AND ≥2 decorrelated source families, never *granted* by confident prose. Poisoned signals are
quarantined.

## Stage 2 — Shakti reads the world (read-only handoff) ✅

The eye conducts read-only: corroborated receipts become advisory pressure S4 *can* read, but the hands stay down.

- **Owner:** `dharma_swarm/world_radar/warrant_handoff.py` — a pure function
  `world_warrant_pressure(receipts) -> list[WorldWarrantPressure]`. No I/O, no owner mutation. Accepts receipt objects
  or the JSON dicts they serialise to.
- **Input:** corroborated `WorldSensemakingReceipt`s (verdict == `corroborated`, `no_action_authority == True`).
- **Output:** `WorldWarrantPressure` **data objects** — advisory magnitude in `[0, 1]` that rises with decorrelated
  agreement (never 1.0 from a single family). Each projection stamps `is_advisory=True`, `no_action_authority=True`,
  `dispatch_authority=False`.
- **Invariants (proved):**
  - `DISPATCH_AUTHORITY` is never set (stays `False`); stamped on every projection.
  - Refuted / insufficient / quarantined receipts produce **no** pressure.
  - A receipt that claims action authority (`dispatch_authority=True` or `no_action_authority` not True) is
    **defensively dropped** — the projector never trusts an upstream authority flag.
  - The function mutates no owner: not `ACTIVE_TRACK.yaml`, ontology, memory, or any doc.
- **Tests:** `tests/test_world_warrant_handoff.py` (5 proofs).
- **Bounded-replay check:** `scripts/governance/check_world_warrant_handoff.py` → `WORLD_WARRANT_HANDOFF=pass`
  (report under `reports/sensemaking_organ/stage2/<date>/`).
- **Gate to Stage 3:** only after Stage 2 is solid does a `WorldProposal` gain *gated* write-authority — through the
  **existing** Memory-Kernel promotion gate / telos gates, never a new apply path. The hands do not move yet.

## Receipt integration seam (Stage 1.5)

`WorldSensemakingReceipt` is currently emitted as a JSON object + replay report under
`reports/sensemaking_organ/stage0_1/<date>/`. It is **evidence, not authority** — a corroborated receipt can
*propose*, it cannot *dispatch*. Future durable integration projects it onto the existing
`spine.EvidenceReceipt` / `runtime_state.RuntimeReceipt` model — **not** a second receipt store.

## Doctrine (enforced)

Ingestion untrusted by default · external text never becomes tool-bearing instruction · no live outreach / posting /
payments / deploy / live-apply · `DISPATCH_AUTHORITY` False until explicit operator approval · no second receipt or
ontology authority · every claim carries provenance + content-hash + source-type + ingestion-time + trust-level ·
every stage has a bounded replay check.
