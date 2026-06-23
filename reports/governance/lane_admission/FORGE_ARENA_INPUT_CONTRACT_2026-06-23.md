# Forge / Arena Input Contract — 2026-06-23

## Purpose

Define what a future Dharma Forge / Orchestration Arena will consume, so it ingests clean evidence packets instead of raw git chaos. This is a CONTRACT, not an implementation. No Forge code is built yet.

## Hard precondition

Forge/Arena MUST consume only `CANONICAL_ORIGIN_MAIN` (or read-only `CLEAN_RECONCILIATION_WORKTREE`) facts for fitness decisions. Dirty/local/candidate state may be *visible* to Forge but MUST NOT drive selection, scoring, or mutation.

## Input primitives

- `CockpitCard` — observed organism state (existing v0.1 card)
- `LaneAdmissionPacket` — promotion-grade lane (schema v1, this folder)
- `ProductionReadinessVerdict` — {track_id, checker_status, production_verdict, closure_risk}
- `ReceiptRef` — pointer to a runtime/ack/test receipt with freshness + proof_state
- `ArenaTask` — frozen, hermetic, replayable task from a task battery
- `OrchestrationGenome` — the composed plan (models, tools, organs, prompts, topology, routing) for one attempt
- `VerifierJudgment` — decorrelation-Council adjudication of an attempt's output
- `PromotionDecision` — whether a genome/technique reproduces

## Fitness function (v1 definition, not yet implemented)

```
Power = VerifiedCapabilityDelta * Trust / (cost * latency * fragility)
```

- VerifiedCapabilityDelta = verified outcome improvement on ArenaTask (capability leads, trust multiplies — not headline)
- decorrelated correctness / marginal contribution is rewarded, not disagreement itself (Krogh–Vedelsby: team error = mean error − diversity)
- Trust = receipt-backed reliability multiplier, never the headline metric

## Cold-start flywheel (v1 has zero trained weights)

```
prompted+evolved v1 -> generates orchestration traces
-> Arena scores them (capture receipts)
-> winners become SFT corpus
-> small planner trained later (surgical GRPO when labels are real)
-> better traces -> repeat
```

No SFT/GPU required to start. Training is earned after the Arena produces labels.

## Build order (gated)

```
1. land/audit cockpit (#662-style seeing-organ + this backplane)
2. build the Arena (frozen task battery + outcome scorer + receipt capture, hermetic & replayable)
3. ship zero-weights prompted+evolved v1 with route-receipts
4. flywheel
5. surgical GRPO when labels are real
```

The Arena is the keystone: it is the single fitness function feeding evolution selection, SFT corpus, GRPO reward, and the Power Index. Build it before any training talk.

## What this contract requires from the backplane (this lane)

- canonicality taxonomy (done) — so Forge knows what is canonical
- lane admission schema (done) — so Forge knows what is promotable
- production-readiness contract (done) — so Forge does not build on un-hardened tracks
- receipt freshness semantics (proof_state, done) — so Forge does not learn from stale/contradicted truth
