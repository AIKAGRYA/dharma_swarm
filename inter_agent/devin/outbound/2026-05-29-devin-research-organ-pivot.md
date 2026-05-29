# Devin Outbound — Research Organ Pivot (Engine-First Sibling to PR #370)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-29
**Branch:** `devin/2026-05-29-research-organ-pivot` (forked from `devin/2026-05-28-autonomous-activation-architect`, parent PR #370)
**Active track:** `runtime-truth-spine-2026-06` — **not displaced.**

## What landed

Two new reports + one external research copy + this notice. **Docs-only. Zero code.**

1. `docs/reports/autonomous_activation_research_organ_v1.md` — **Deliverable 4.** The pivot rationale: Research Cell as primary growth organ, oracle-anchored, with Publication (PR #370's PR-A4) reframed as Stage H exhaust. Synthesizes 10-system external precedent report. Anchors on candidate paper "Telos-Gated Self-Modification: A Benchmark and Empirical Study of Constraint-Aware Code Evolution."
2. `docs/reports/autonomous_activation_research_organ_pr_sequence_v1.md` — **Deliverable 5.** PR-R1..R6 sequence, ~1,850 LOC total, each PR independently reviewable in <500 LOC. Sibling to PR #370's PR-A1..A6; both compose, ordering is the operator's call.
3. `docs/research/external_precedents_autonomous_flywheels_2026-05-28.md` — **External grounding.** 519-line synthesis of DGM, FunSearch, AlphaEvolve, AI Scientist v2, METR RE-Bench, MIB benchmark, OpenHands, Sakana, Future House, Goodfire Scribe. Cited in Deliverables 4 & 5.

## The critical claim

The bottleneck of the last two months was never "we lack a publication channel." It was **the missing oracle** — no cheap, unforgeable, deterministic `h(solution)` to convert experimental output into a scalar a flywheel can spin on. The external precedent report is unanimous on this: every working autonomous loop (DGM, FunSearch, AlphaEvolve) has one; every ornamental loop lacks one. The substrate to build the oracle is already on disk (`auto_grade` 433 LOC, `gauntlet` 787 LOC, `petri_dish` ~2400 LOC, `closure_v0`, `cascade_domains/research.py`) — ~5000 LOC of evaluation surface already paid for, never composed. PR-R3 is ~250 LOC of composition, not invention.

PR #370 (Operator Brief Publication wedge) is **metabolically valid as a support organ** — cheap, deterministic, externally visible. It is **not the primary growth organ.** Codex was directionally right on this point. GPT's framing — "exhaust not engine" — names the pathology.

## What this pivot does NOT do

- Does not replace PR #370. Both PR families compose. Operator decides primacy.
- Does not touch the active track. Zero edits to `spine/**`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py`, `tests/test_dispatch_dropoff_sources.py`, `tools/spine_check.py`.
- Does not move `evolution.py` out of `shadow_mode=True`. Archive read-only.
- Does not propose autonomous external messaging. Paper / benchmark releases require `--approved-by <operator>` flag.
- Does not propose autonomous capital deployment. $500/mo cap with cost-cap abort in PR-R4's harness.
- Does not propose new substrate. Composes existing modules.
- Does not propose a meta-framework. Ships TGSM-Bench (concrete benchmark, 10 paired tasks, MIT-licensed).
- Does not propose new active track. All PR-R* land docs-only first; code PRs ship only after operator selects engine-first primacy.

## Doctrinal compliance audit

| Doctrine | Compliance |
|---|---|
| Coherent (composes existing owners) | ✅ No new substrate; wires `auto_grade` + `gauntlet` + `petri_dish` + `closure_v0`. |
| Metabolically alive | ✅ Each PR ships runnable artifact with deterministic test acceptance. |
| Reality-grounded | ✅ Oracle is pure-function deterministic scoring, not editorial. |
| Replayable | ✅ `EvidenceReceipt.replay_command` bit-for-bit reproducible. |
| Witness-capable | ✅ Every experiment emits receipt + gauntlet score + consolidator debate. |
| Survives world contact | ✅ 90-day artifact-or-die kill condition explicit. |
| Without losing telos | ✅ Telos is *scored* dimension in `dharmic_fitness = task_performance × telos_score`. Disabling telos lowers agent's own fitness — self-policing. Direct lesson from DGM hallucination-hack. |

## Forbidden actions audit

All 9 forbidden actions from Master Prompt cross-checked. **None proposed.** Telos-as-scored-dimension (PR-R3) specifically addresses the DGM failure mode the external report flagged.

## What I'm NOT asking Devin to do

This drop is for the operator. Devin retains `external_worker_evidence_only` authority. PR-R1..R6 code PRs require human approval per the proposed `VENTURE_CELL_RESEARCH_CELL.md` (which itself ships in PR-R1, gated by operator).

## What I AM asking the operator to decide

**Primacy.** Two PR families now exist as siblings:

| Option | Reading |
|---|---|
| **#370 first, then research-organ** | Publication infrastructure ships first as low-risk metabolism; engine layered on later. Risk: two more months of paid burn with no oracle. |
| **Research-organ first, then #370 as exhaust** | Engine ships first; PR #370's PR-A4 becomes Stage H exhaust of a real metabolism. Risk: longer time-to-first-publication, higher PR review surface. |
| **Both in parallel** | Independent reviewers per family; no shared file conflicts (verified — different directories). Highest velocity, highest reviewer load. |

Recommendation embedded in Deliverable 5: **engine-first**, because the precedent report is unanimous on `h()` being the bottleneck and lacking one is not solvable by adding publication surface. But this is an operator call; both options preserve all doctrinal compliance.

**Kill condition for the research organ if operator selects engine-first:** 90 days from PR-R6 merge with no submitted artifact → cell dissolves; resources return to revenue wedge.

---

## Files in this drop

- `docs/reports/autonomous_activation_research_organ_v1.md` (245 lines, Deliverable 4)
- `docs/reports/autonomous_activation_research_organ_pr_sequence_v1.md` (372 lines, Deliverable 5)
- `docs/research/external_precedents_autonomous_flywheels_2026-05-28.md` (518 lines, external grounding)
- `inter_agent/devin/outbound/2026-05-29-devin-research-organ-pivot.md` (this notice)

**Total: 4 files, 0 lines of code, 0 active-track risk.**
