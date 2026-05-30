# Devin Outbound — Proof-Artifact Pivot (Become the Evaluator)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-30
**Branch:** `devin/2026-05-30-proof-artifact-pivot` (forked from `devin/2026-05-28-autonomous-activation-architect`, parent PR #370)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Supersedes parts of:** PR #373 (W1 audit-first wedge — operator diagnosed missing authority); incorporates concept from `[SHELVED]` PR #372 (TGSM-Bench → repackaged as TGSM-Eval).

## What landed

Five docs + this notice. **Docs-only. Zero code. Zero active-track risk.**

1. `docs/reports/proof_artifact_internal_benchmark_inventory_v1.md` — internal substrate inventory. Found: team picked 5 benchmarks in March 2026 (SWE-bench, GAIA, AgentRace, MultiAgentBench, DGM), implemented 0 adapters, missed COLM deadline. `benchmarks/` contains exactly `gauntlet.py` (787 LOC internal) + `long_context_sidecar_suite.py` (240 LOC). Zero external benchmark library imports. One real artifact on disk: `results/ouroboros_experiment.json` (8-sample self-observation, full metric vector).
2. `docs/research/benchmark_to_inbound_precedents_2026-05-30.md` — 13 orgs profiled. Brutal finding: benchmark-placement → inbound is overwhelmingly a VC path (11/13), not a revenue path. Only Pattern Labs ($450M) and METR converted benchmark credibility to paying contracts. Base rate of meaningful inbound from leaderboard placement: 5–9%. SWE-bench is saturated at 94% SOTA; a new entrant can't top it.
3. `docs/research/benchmark_virality_mechanics_2026-05-30.md` — 18 case studies. Reproducibility is load-bearing; correction threads get 20–30% of original reach but reputational stain is permanent (Devin, Reflection 70B). Open-source consistently outperforms closed. Realistic zero-follower upside: p25 = 30–80 stars / no inbound; p95 = Open Interpreter scenario (Karpathy-class amplifier required).
4. `docs/reports/proof_artifact_slate_v1.md` — **Deliverable 7.** Three-layer composite strategy.
5. This outbound notice.

## The brutal one-line synthesis

**The only documented path to revenue-self-sustainability without VC is becoming the benchmark producer (METR / Pattern Labs shape), not placing on someone else's benchmark.** The operator's instinct ("prove we can do something real before charging for audits") was correct in direction; the precedent data sharpens the shape: *we become the evaluator publicly*, which simultaneously produces the proof-of-system, the public artifact for inbound, the eval-as-a-service revenue, and the marketing for future audit upsells.

## Three-layer strategy

**Layer 1 — Ouroboros Open Log** (7–10 days). The 8-sample self-observation experiment on disk becomes a continuous public log. Nightly JSONL + live dashboard + weekly digest. Substrate exists; only cron + dashboard is new. Hofstadterian self-reference angle on the user's home turf. Realistic outcome: p25 = quiet, p95 = Open Interpreter-class breakthrough if a Karpathy-class amplifier finds it.

**Layer 2 — TGSM-Eval (We Are the Evaluator)** (30–45 days). Composite of `[SHELVED]` PR #372's TGSM-Bench design + Pattern Labs / METR business model. We run 4–8 famous agent systems (LangGraph, AutoGen, CrewAI, OpenHands, smol-agents, etc.) against a 10–15 task suite with paired telos-violation traps. We pre-populate the leaderboard ourselves — we don't wait for submissions. Open submission protocol with replay receipts required. Sell pre-deployment eval contracts to frontier labs at $5K–$25K/run (Pattern Labs / METR model — revenue, not VC).

**Layer 3 — Audit Business** (post-credibility, inbound-only). PR #373's W1 ($500 Lightning / $2,500 Full / $1.5–2k/mo retainer) activates ONLY when Layer 2 produces inbound. Not before. Activating earlier risks the "audit without authority" diagnosis the operator surfaced. Estimated activation: month 2–4.

## Why Layer 2 = TGSM-Eval, not Candidate A (SWE-bench Verified)

Per precedent data: 5–9% base rate of leaderboard placements producing inbound. SWE-bench specifically is saturated (94% SOTA) and is the only benchmark that reliably produced VC inbound — but VC isn't what we want. Pattern Labs / METR model is the only documented revenue-without-VC path, and it requires being the evaluator, not the contestant. Substrate fit also favors TGSM-Eval (95% reuse vs 60% for SWE-bench adapter).

## Reproducibility as load-bearing wall

Devin's launch is the canonical case of "results that won't reproduce destroy your reputation faster than no results at all." Mitigations baked into design:
- Every result = `closure_v0.EvidenceReceipt` with full replay command
- Pre-launch trusted independent reproduction (PR-P2 and Layer 2 equivalent)
- Leaderboard distinguishes "we ran this" vs "they submitted this"
- Never claim SOTA. Claim "here is what we measured."
- All telos-trap pairs documented; gaming the trap is documented as gaming the trap

## What this does to existing PRs

- **PR #370** (Operator Brief): re-scoped per PR #373's amendments — PR-A4 becomes back-end for Layer 1 weekly digest + Layer 2 leaderboard updates. PR-A6 cron stays DEFERRED.
- **PR #372** (Research Cell): stays `[SHELVED]`. TGSM-Bench concept resurrected as Layer 2's TGSM-Eval.
- **PR #373** (Audit wedge): re-scoped — W1 → Layer 3 (post-credibility), W2 → folded into Layer 2 submission protocol, W3 → renamed *Weekly Field Report*, content engine for Layers 1+2.

## Proposed PR-P series

PR-P0 = this docs drop. PR-P1..P9 = code (~2,700 LOC across 9 PRs, stretched across ~60 days). Cron registration DEFERRED until 30 days green manual operation. Audit activation (PR-P9) ships ONLY after Layer 2 produces inbound.

## Three questions for the operator

1. **Confirm Layer 2 = TGSM-Eval** (we are the evaluator, ~30–45 days)? Recommendation: yes.
2. **Start Layer 1 (Ouroboros Open Log) immediately as a 7–10 day push** in parallel with PR-P0? Recommendation: yes.
3. **Trusted independent reproducer** for the pre-launch reproducibility check? Options: technical friend, AI safety / mech-interp colleague, recruited HN/Twitter blind reviewer, or worst-case the operator from a fresh git clone in a different environment.

Once answered, PR-P1 opens this week.

## Doctrinal compliance

All 9 Master Prompt forbidden actions cross-checked clean. Active track untouched. `evolution.py shadow_mode=True` frozen. No autonomous external messaging — every HN / Twitter post is operator-triggered. Reproducibility is the load-bearing wall, designed against.

## Authority

`external_worker_evidence_only`. All PR-P* code PRs require operator approval before merge. Audit-business activation (PR-P9) requires explicit operator green light even after inbound arrives.
