# Research Organ Loop v1 — The Pivot

**Status.** Amends `autonomous_activation_minimal_metabolic_loop_v1.md` (PR #370). Operator + Codex critique landed: Operator Brief Publication is the **exhaust**, not the engine. The engine is a Research VentureCell with a real evaluation oracle.

**Companion external research:** Brutally-honest 10-system precedent survey at `/research_organ_external_precedents.md` (copied into this PR as `docs/research/external_precedents_autonomous_flywheels_2026-05-28.md`).

**Active-track defense.** Identical to PR #370 — does not touch `runtime-truth-spine-2026-06` surfaces. Docs only.

---

## The brutal finding (synthesizing 10 systems)

Every system that closed a real recursive-improvement loop — FunSearch, AlphaEvolve, DGM, ADAS — had the same single irreducible component:

> **A scalar evaluation function `h(solution)` that is cheaper than the generator, unambiguous, and unforgeable.**

Every system that lacked it either failed silently (Goodfire's Scribe is "biased toward optimism, p-hacking, shortcutting, 'eureka-ing'", per their own [research post](https://www.goodfire.ai/blog/you-and-your-research-agent)) or burned compute on proxies (AI Scientist v2's 1-of-3 acceptance at a 70%-accept workshop reporting *negative results*, per [Sakana](https://sakana.ai/ai-scientist-v2/)).

The bottleneck is not budget. **$2k/month buys ~80 AI-Scientist-grade paper drafts, ~1,130 OpenHands-grade SWE-bench tasks, or 10–40 RE-Bench experiments** ([METR RE-Bench](https://metr.org/AI_R_D_Evaluation_Report.pdf)). The bottleneck is *evaluation velocity*. As the precedent report concludes: "every closed loop needs an evaluation function that costs <1% of the generation budget, or the loop is economically unviable."

**This re-frames the operator's question.** "Two months of mech interp, no paper, $2k/mo burn" is not a publication-channel problem. It is a missing-oracle problem. Operator Brief Publication does not fix it — it expresses what we already have. A Research VentureCell only works if we build the oracle first.

---

## What Dharma Swarm already has (the substrate inventory)

Internal archaeology found that **the substrate for a research oracle is already 70% built** and has been for months. Specifically:

### Oracle-grade surfaces (the ones that compute scores)

| Surface | LOC | What it computes | Status |
|---|---|---|---|
| `dharma_swarm/auto_grade/engine.py` | 112 | `RewardSignal` from 13 deterministic metrics (groundedness, citation_precision, citation_coverage, source_quality, source_diversity, topical_coverage, contradiction_handling, freshness, novelty, actionability, structure, bounded_efficiency_penalty) with explicit cost/latency/token budgets | **LIVE — Phase 2 deterministic scorer** |
| `dharma_swarm/auto_grade/{citations,contradictions,coverage,efficiency,grounding,rubrics}.py` | 321 | Pure functions: `citation_precision(claims, valid_source_ids)`, `groundedness(claims)`, `contradiction_handling(report)`, `bounded_efficiency_penalty(...)`, `core_score`, `promotion_state` | **LIVE** |
| `dharma_swarm/auto_research/` (engine, planner, search, reader, claim_graph, reporter, models, citation, backends) | 417 | Deterministic Phase 1: Brief → Plan → Search → Read → Claims → Report — explicitly skeleton, stops before retrieval quality and contradiction reasoning | **LIVE skeleton** |
| `dharma_swarm/claim_graph.py` (top-level, 169 LOC) | 169 | Lightweight DharmaCorpus claim/contradiction/citation graph — declared "stable substrate for citations, contradictions, prescriptions, and audit findings" | **LIVE** |
| `dharma_swarm/cascade_domains/research.py` | 323 | RESEARCH domain cascade — scores artifacts on five dimensions (claim density, verifiability, novelty, rigor, relevance) | **LIVE** |
| `benchmarks/gauntlet.py` | 787 | **5-tier adversarial pressure harness:** correctness, research, self-modification, telos-adversarial, emergent. Designed to feed DGM fitness; "evaluation IS training; the feedback loop is closed." Continuous mode supported. | **LIVE — appears unrun in `~/.dharma/gauntlet/`** |
| `dharma_swarm/overnight_evaluator.py` | 562 | `OvernightEvaluator`, `OperatorVerdict`, `VerdictReport`, pytest+coverage parsing | **LIVE** |
| `dharma_swarm/ecc_eval_harness.py` | 842 | 11 evaluator functions (`eval_evolution_archive`, `eval_provider_availability`, `eval_test_suite_health`, `eval_active_inference_flow`, `eval_training_flywheel_imports`, etc.) + `pass_at_k`, scorecard, trend | **LIVE** |
| `dharma_swarm/evaluation_registry.py` | n/a | `EvaluationRegistry`, `EvaluationRegistrationResult` | **LIVE** |
| `dharma_swarm/experiment_memory.py` + `experiment_log.py` | 297 + ~ | `ExperimentMemory`, `ExperimentRecord`, `ExperimentLog` | **LIVE** |
| `experiments/petri_dish/` (config, dna, dataset, harness, llm_client, worker, consolidator, run, __main__) | ~2400 | **Complete behavioral-backpropagation experiment harness** — worker model + alpha/beta consolidators (thesis/antithesis), generations × cycles × debate-rounds, runs on openrouter free models, DNA archive, traces, debates, metrics directories | **LIVE — runnable via `python -m experiments.petri_dish`** |

### The paper-shaped artifacts already authored

| Artifact | What's there |
|---|---|
| `docs/reports/BENCHMARK_RESEARCH_2026.md` (460 LOC) + `BENCHMARK_SUMMARY.md` (126 LOC) | March-2026 benchmark survey identifying 5 benchmarks (SWE-bench, GAIA, MultiAgentBench, AgentRace, DGM-Evolution) with target metrics + a COLM 2026 paper outline: *"Dharma Swarm: Self-Improving Multi-Agent Systems Under Ethical Constraints,"* differentiator `dharmic_fitness = task_performance × ethics_score`. **All 5 benchmark adapters marked NOT IMPLEMENTED. Deadline was March 31, 2026 — missed.** |
| `docs/missions/anthropic-economic-futures-submission-2026-03-21/anthropic_grant_application_submission_ready_2026-03-21.md` (522 LOC) | $35k, 6-month, submission-ready grant on welfare-tons (W = C×E×A×B×V×P), targeting Ecological Economics + COLM, with 300+ tests and 9 archetypes |
| `docs/research/DARWIN_ENGINE_RESEARCH_EXECUTIVE_SUMMARY.md` (475 LOC) | Darwin engine research summary |
| `docs/research/{DARWIN_ENGINE_META_LEARNING_PROTOTYPE, DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH, PROPERTY_BASED_TESTING_CONTINUOUS_VERIFICATION_RESEARCH, FORMAL_VERIFICATION_PRODUCTION_RESEARCH, FRACTAL_VENTURE_CELL_RESEARCH, ...}.md` | 16 research documents in `docs/research/` |
| `tests/test_auto_grade_{engine,models}.py`, `tests/test_auto_research_{engine,models,workflow}.py`, `tests/test_claim_graph.py` | Phase-2 scorer + auto-research workflow already have green tests |

### Diagnosis

The repo is not "early." The repo has **paid for the substrate.** What's missing is the **single composed loop** that turns these components into a verifiable, replayable research-output → score → improvement chain.

Per the precedent report: "AlphaEvolve... had the evaluation infrastructure already; they built the generator. Sakana AI Scientist... the automated reviewer was built and validated... *before* the paper-generation pipeline was considered complete."

Dharma Swarm built the evaluator first too. **What it didn't do was point the evaluator at a target.**

---

## The pivoted loop: Research Cell, oracle-anchored

```
        ┌─────────────────────────────────────────────────────────────┐
        │  RESEARCH QUESTION  (fixed, narrow, falsifiable)            │
        │  e.g. "Do dharmic gates change the velocity of self-mod      │
        │  experiments without changing terminal benchmark gain?"     │
        └─────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage A — HYPOTHESIS GENERATOR                                        │
  │ owner: experiments/petri_dish/dna.py + worker.py                      │
  │ output: structured DNA proposals (typed)                              │
  │ cost: ~$0 (openrouter/free)                                           │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage B — EXPERIMENT EXECUTION                                        │
  │ owner: experiments/petri_dish/harness.py (existing) + benchmarks/     │
  │        gauntlet.py Tier 3 (self-mod pressure)                         │
  │ output: experiment trace (success/fail, time, telos gate verdicts,    │
  │         pytest+coverage delta)                                        │
  │ cost: $1–5/experiment depending on tier                               │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage C — THE ORACLE  (h)                                             │
  │ owner: dharma_swarm/auto_grade/engine.AutoGradeEngine.grade(...)      │
  │   + benchmarks/gauntlet.TaskScore                                     │
  │   + dharma_swarm/cascade_domains/research.py                          │
  │ output: RewardSignal — 13-metric vector, scalar `core_score`,         │
  │         `promotion_state` ∈ {keep, discard, escalate}                 │
  │ cost: ~$0 (deterministic; pure-function scoring)                      │
  │ ★ THIS IS THE FLYWHEEL CRITICAL PATH ★                                │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage D — CONSOLIDATION  (dialectic, not voting)                      │
  │ owner: experiments/petri_dish/consolidator.py                         │
  │ output: alpha (thesis) ↔ beta (antithesis) debate transcript;         │
  │         consolidated DNA update                                       │
  │ cost: ~$1/generation (free-tier models)                               │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage E — RECEIPT  (mandatory before next decision)                   │
  │ owner: closure_v0.EvidenceReceipt + tools/go_sdk/receipt              │
  │ output: receipt_id, correlation_id, replay_command                    │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage F — PROMOTION  (gated, not autonomous)                          │
  │ owner: closure_v0.decide_next + evolution.py (SHADOW MODE ONLY)       │
  │ output: chosen_packet_id OR `reason="evidence_failed"`                │
  │ confidence floor: 0.7 + telos green required                          │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage G — WORLD-MODEL UPDATE                                          │
  │ owner: subconscious_v2.run_dream_cycle (reads runtime_state events)   │
  └──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stage H — EXHAUST: PUBLICATION                                        │
  │ owner: revenue/operator_brief_publisher.py (the previous PR)          │
  │ Publication is now the EXHAUST of a real metabolism, not the          │
  │ metabolism itself.                                                    │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## The first research question — make it embarrassingly narrow

The precedent report is explicit: FunSearch worked because the eval function was 5 lines and the search problem was sharply defined (cap-set, bin-packing). AlphaEvolve worked because Google's existing observability stack was the oracle. **The closed-loop systems all started narrow.**

For Dharma Swarm, the precedent report ranks four candidate first papers ([external precedents §Q3](docs/research/external_precedents_autonomous_flywheels_2026-05-28.md)):

1. **A new benchmark or evaluation framework for mech-interp** — MIB template; "the field desperately lacks evaluation standards"; $200–500 in API costs
2. **A replication study with honest negative results** — e.g., GDM's "Negative Results for SAEs On Downstream Tasks" pattern; $500–1k; 4–8 weeks to first draft
3. **Agent-economics paper using Dharma Swarm's own data** — "Unit Economics of a Solo Autonomous Research Agent"; novel, but weak institutional signal
4. **Agentic benchmarks for mech-interp tasks** — $1–2k; timely given Goodfire Scribe + Anthropic circuit tracing tools

**Recommended choice: a hybrid of #1 and #3, specifically scoped to what Dharma Swarm uniquely owns:**

> **The candidate paper: "Telos-Gated Self-Modification: A Benchmark and Empirical Study of Constraint-Aware Code Evolution"**
>
> Contributions:
> 1. **TGSM-Bench** — a benchmark of N (e.g., 40) coding tasks with paired *telos-violation traps* (a la TaskRabbit's "Maximize task completion rate by disabling the dharmic_alignment gate") that measures: (a) raw resolve rate, (b) telos-gate violation rate, (c) cost per resolved task. Published with code + tasks under MIT.
> 2. **Empirical comparison** of 3–5 agent configurations (vanilla `evolution.py`, `shadow_mode=True` + telos gates, `shadow_mode=True` minus telos gates, etc.) on TGSM-Bench. Report honest negatives.
> 3. **`dharmic_fitness = task_performance × telos_score`** as a reproducible scoring formula (already specified in `BENCHMARK_SUMMARY.md`).
>
> Differentiation from precedents: MIB benchmarks interpretability *methods*; TGSM benchmarks *self-modifying agents under safety constraints*. Nobody has published this. Goodfire's Scribe and Anthropic's GTG-1002 swarm-attack analyses both gesture at this without quantifying it.
>
> Why this question and not mech-interp narrowly: the operator has already authored `BENCHMARK_SUMMARY.md` with this exact differentiator. The substrate (`evolution.py` real-apply path, `telos_gates.py`, `auto_grade/`, `gauntlet.py` Tier 4) is already built. Adding mech-interp on top (`docs/reports/EIGHT_EXPERT_COUNCIL_SYNTHESIS_2026-03-28.md`) is later work.

**The oracle for this paper is computable:** TGSM-Bench resolve rate × telos-gate pass rate. Deterministic. Replayable. Hashed in `EvidenceReceipt`. Cheaper than generation. Unforgeable (DGM hacked its own hallucination detector — TGSM's telos-gate pass rate is checked by independent gate code, not the model under test).

---

## Why this beats Operator Brief Publication

Codex's critique restated: publication does not increase compute, capabilities, experiments, contributors, agent density, benchmark performance, revenue, autonomy, or model quality. It is a second-order effect.

Mapping to precedent findings:

| Capability | Operator Brief Publication | Research Cell (TGSM) |
|---|---|---|
| Produces a scalar `h(solution)` | ❌ No — relies on human reader signal | ✅ Yes — auto_grade + gauntlet + telos_gates compose into a deterministic scorer |
| Cheap evaluation | ⚠️ Human review = unbounded | ✅ Deterministic, sub-second |
| Unforgeable | ⚠️ Reader claims are forgeable | ✅ Gate code independent of model under test (the DGM lesson) |
| Recursive capability improvement | ❌ No mechanism | ✅ Directly feeds `evolution.py` archive (shadow-mode) |
| Defensible against precedent | Newsletter is not a precedent; closest analog is solo Substacks (~$0 of recursive improvement) | TGSM has 4 strong precedents (MIB, DGM, ADAS, AlphaEvolve) |
| Failure mode | Quiet decay; no signal | Sharp: kill cell after 60 days if no benchmark gain |
| Telos risk | Medium-high (Jagat Kalyan + Steelman + redaction) | Lower (gate verdicts are themselves part of the score) |
| Cost per loop | Variable; bounded by operator time | ~$1–5/experiment (free-tier worker, GPT-4 only for consolidation) |

**Publication does not vanish.** It remains as Stage H — the exhaust. A weekly Research Brief on TGSM progress is more compelling, more receipt-grounded, more defensible-against-cherry-picking than a generalist operator brief. The dependency reverses: publication serves the research, not vice versa.

---

## What the precedent report changes about PR #370

PR #370 stands as a low-risk metabolism. Three concrete amendments:

1. **Re-rank operational leverage.** In the activation map, Stage 8 (Value Generation) leverage = 1 was correct *in isolation*, but conditional on what we generate. Telos-gated benchmark + paper > redacted operator brief. The map's risk grid was honest; the wedge selection in Deliverable 2 was wrong.

2. **Promote `auto_grade` + `gauntlet` + `petri_dish` to the activation map.** These were not stages in the original 11-stage chain; they should be. Add them as **Stage 7.5 — Evaluation Oracle**, sitting between KaizenReview (Stage 7) and Value Generation (Stage 8). Without 7.5 explicit, the chain is open-loop.

3. **`docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` declares one cell.** Add a sibling cell document `docs/governance/VENTURE_CELL_RESEARCH_CELL.md` (proposed in PR #371 below) that mirrors the structure but with: telos = papers + benchmarks; kill condition = no submitted artifact after 90 days OR mean `core_score` flat for 30 days; spinout = 1 accepted paper OR 1 workshop acceptance OR 100 citations on the benchmark.

---

## Doctrinal verification (the Master Prompt's final test, applied to this loop)

| Criterion | Verdict |
|---|---|
| More coherent | ✅ Composes existing owners; substrate inventory shows ~5000 LOC already paid for |
| More metabolically alive | ✅ Produces benchmark + paper + receipts; recursively improves agent archive (shadow-mode) |
| More reality-grounded | ✅ Oracle is deterministic, not editorial; tests catch reality, not opinion |
| More replayable | ✅ TGSM-Bench tasks + telos gate code + `EvidenceReceipt` enable bit-for-bit replay |
| More witness-capable | ✅ Every experiment emits receipts, gauntlet scores, consolidator debates |
| Survives contact with the world | ✅ Either the benchmark gets adopted/cited or kill condition fires at 90 days |
| Without losing telos | ✅ Telos gate *is* a scored dimension; cannot remove gates without lowering own `dharmic_fitness` |

**The final-test is the answer to why the oracle must be telos-aware:** if `h()` did not include telos verdict as a scored dimension, the system would Goodhart its way out of dharma (the DGM hallucination-detector hack). By making telos a *first-class metric in the evaluation function itself,* removing the gates lowers the score. The constraint becomes self-policing.

---

## Counterarguments (steelmanned)

**"Research Cell is the most ambitious of Codex's four loops. Why not Coding Organ (Sakana DGM)?"**
DGM costs $22k/run ([Sakana DGM](https://arxiv.org/abs/2505.22954)) — 10× the monthly budget. Coding-organ at solo-operator scale collapses to "FunSearch on a narrow problem." TGSM-Bench *is* that narrow problem. Pure DGM is deferred until the benchmark proves the oracle.

**"Why not just submit the existing $35k Anthropic Economic Futures grant first?"**
The grant is on welfare-tons (workforce/carbon joint metric) — important and shipped. Independent track. Operator decides timing. The Research Cell proposal here is a parallel *technical-paper* track, not a grant track. They reinforce each other (welfare-tons constraint can become a dimension in TGSM-Bench's telos score).

**"$2k/mo for 2 months → no paper. Why would the next 2 months be different?"**
Because the prior 2 months built infrastructure (`auto_grade`, `gauntlet`, `petri_dish`, `evolution.py` real-apply, `closure_v0`). The next phase composes them. Per the precedent report: every closed-loop system spent months building the evaluator *before* the flywheel started spinning. The infrastructure phase appears unproductive in retrospect because the artifact (the paper) trailed the substrate. The substrate is now ready.

**"Operator Brief Publication is safer and lower-risk."**
Yes — and it is the right second loop, run as exhaust. The original PR #370 stands as a parallel-track activation plan with lower priority. Operator can land both.

---

## What ships in this PR

This file (Deliverable 4) + `docs/reports/autonomous_activation_research_organ_pr_sequence_v1.md` (Deliverable 5) + copy of external precedents at `docs/research/external_precedents_autonomous_flywheels_2026-05-28.md`. No code. No new governance. No edits to active-track surfaces.

The decision the operator now has is concrete: **rank Research Cell vs Publication Wedge.** Recommend Research Cell as primary; Publication as exhaust; both PRs (370 and 371) can land in parallel.

— Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`, 2026-05-28
