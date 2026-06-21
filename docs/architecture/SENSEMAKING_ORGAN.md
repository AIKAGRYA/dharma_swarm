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
  └─ STAGE 2 READ ...... dharma_swarm/shakti_zeitgeist_executive.py  (reads corroborated receipts → advisory warrant-pressure; DISPATCH_AUTHORITY stays False)  ← design below
  └─ STAGE 3 PROPOSE ... WorldProposal → memory_kernel promotion gate / telos_gates (24h incubation, blast-radius-graded evidence)  ← future
  └─ OBSERVE ........... orientation_graph.py / make orient  (World Pulse + Sensemaking Health, read-only projection)  ← future
```

✅ = shipped (Stage 0 + Stage 1). The verifier is the moat: corroboration is *earned* by ≥2 decorrelated evaluator
families AND ≥2 decorrelated source families, never *granted* by confident prose. Poisoned signals are quarantined.

## Stage 2 — Shakti reads the world (read-only handoff design — NOT yet implemented)

The seam, defined so the next PR is obvious and safe:

- **Input:** corroborated `WorldSensemakingReceipt`s (verdict == `corroborated`, `no_action_authority == True`).
- **Adapter (future):** a pure function `world_warrant_pressure(receipts) -> list[WarrantPressureProjection]` added near
  `shakti_zeitgeist_executive`. It reads receipts, emits a **read-only advisory pressure** data object. It must:
  - NOT set `DISPATCH_AUTHORITY` (stays `False`).
  - NOT mutate `ACTIVE_TRACK.yaml`, ontology, memory, or any owner doc.
  - Produce a *proposal/pressure data object*, never a dispatch or a mutation.
- **Tests (future, `tests/test_shakti_reads_world.py`):** corroborated → advisory pressure only; refuted/quarantined →
  no pressure; `DISPATCH_AUTHORITY` remains False; output is a data object, not a mutation.
- **Gate to Stage 3:** only after Stage 2 is solid does a `WorldProposal` gain *gated* write-authority — through the
  **existing** Memory-Kernel promotion gate / telos gates, never a new apply path.

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
