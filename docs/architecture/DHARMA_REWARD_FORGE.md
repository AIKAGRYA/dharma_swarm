# Dharma Reward Forge — design (v0)

**Status:** v0 in progress, 2026-05-31. Locked by operator. Pending track activation (currently QUEUED; `goodworks-dgm-core` is the ACTIVE track and is shippable).
**One-line:** the Forge is the **loss-function spine** that makes the whole swarm evolve on unfakeable external receipts — not a new product layer. It runs **through the existing organ `ds-goal` / Sankalpa Organ** and the existing DGM/Darwin loop. We wire the engine we have to sealed holdouts + external receipts; we do not build a new engine.

## North star
> dharma_swarm becomes the organism that improves itself by solving verifiable tasks under sealed reward, telos gates, replayable lineage, and cost pressure — and every side-organ feeds it.

Objective optimized: **verified useful capability under causal telos constraints** — NOT raw capability.

## The organs and how they wire (verified file anchors)
| Role | Organ | Anchor | Status |
|---|---|---|---|
| Mission/intention/leases/receipts | Sankalpa Organ (`ds-goal`) | `docs/ops/AUTONOMY_SPINE.md` | real |
| Mutate → eval → archive → promote | DGM loop | `dharma_swarm/dgm_loop.py` | real, mostly shadow/provider-gated |
| Sealed benchmark receipts (train/val/holdout) | DharmaEval | `dharma_swarm/dharma_eval.py` | real; contamination guards added (this build) |
| Diversity-preserving lineage | Archive / MAP-Elites | `dharma_swarm/archive.py` | real |
| Multi-dim fitness | `FitnessScore` | `archive.py:107` | real; `from_external_receipt()` added (this build) |
| Promotion gate | `evaluate_promotion_request` | `dharma_swarm/evolution_promotion.py` | real; ends at `candidate_for_human_review` |
| Telos gates (tiered) | `TelosGatekeeper` | `dharma_swarm/telos_gates.py` | real; Tier A/B block, Tier C advisory; has REVERSIBILITY gate |
| Internal artifact quality | `quality_forge.py` | `dharma_swarm/quality_forge.py` | real |
| Cheap diff-safety scorer (not final oracle) | `verify/scorer.py` | `dharma_swarm/verify/scorer.py` | real |
| Outward metabolism | VentureCells | `fractal/fractal_room.py:161` (`VentureCellV1`) | real |

## The honest gaps (what is NOT yet real — the work)
1. **Closed fitness loop.** Bridge `FitnessScore.from_external_receipt()` shipped this build (anti-inward-machine: unconfirmed receipt → zero fitness). Still to wire: DGM promotion consuming it end-to-end.
2. **DGM is shadow/provider-gated** (`dgm_loop.py:~286`). Live mutation deliberately off.
3. **DharmaEval contamination.** manifest + suite contamination guards shipped this build; still to add: fixture-leak / split-leak checks at run time.
4. **Promotion ends at `candidate_for_human_review`** — autonomous promotion is intentionally not enabled.
5. **NATS is not live authority** (`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`). For now: tmux + `ds-goal` are real; NATS is future hot transport; A2A is the external edge.
6. **External dollar receipts = zero.** The metabolism layer (CashClaw / bounties / Goodworks MRV) is what supplies real external receipts; it must be load-bearing from v0, not bolted on.

## Telos gates = causal promotion physics (not moral brakes)
Extends the existing tiered gate. The gate asks: *what capability does this strengthen? who can use it? who can be harmed? is it reversible? is the scorer isolated? is the witness intact? does it preserve option value? what constraints let us learn safely?* Output is graded, not binary:
- **ALLOW** · **ALLOW_WITH_CONSTRAINTS** (sandbox/blast-radius bound) · **DEFER_FOR_EVIDENCE** · **DENY**.
- **Irreversible** actions → proof + hard gates (Tier A/B). **Reversible** experiments → reality + rollback + bounded blast radius + fast evidence (Tier C). **Uncertain** → constraints, not paralysis.
- **Promotion rule:** no child promotes unless it improves the **held-out** score AND passes causal telos checks (reversibility, harm gradient, consent, uncertainty, option value, welfare externalities). The Hobbling Test (`docs/reports/telosproof_spike_2026-05-30.md`) guards against gates that block benchmarkable reversible moves.

## The missing idea: `forge_feed_contract`
**No side quest without a forge-feed contract.** Every VentureCell / app / bounty / publication / Polsia-style shell is allowed — but each must declare how it feeds the Forge (tasks, outcomes, failures, receipts, or ontology objects). Seeded this build as an optional `VentureCellV1.forge_feed_contract` field + `forge_feed_contract_status()`; enforced at Forge-feed time (graded), not retroactively breaking existing cells.

## External operators (Polsia / Cofounder / OpenClaw / Hermes)
Help with shell, ops, schedule, drafts, GTM, workflows, observation. They do **not** get final authority over truth, claims, source trust, publishing, money, or core secrets (`docs/research/venture_operator_systems/README.md`). Every interaction becomes a logged observation / benchmark / failure mode / task pattern for the **native** Dharma operator runtime (the eventual Hermes/OpenClaw-equivalent that absorbs tmux + ds-goal ledgers + A2A/NATS-when-live + skills + receipts + gates + sandboxed execution).

## Palantir move: OAG over RAG
The ontology (`dharma_swarm/ontology.py`) is the typed substrate all organs see the same world through — not a dashboard above the Forge. Agents operate over typed objects/actions/gates/receipts/relationships, not just retrieved text. Object graph holds: VentureCells, RevenueTargets, WorkPackets, ValueEvents, EvidenceRefs, GateDecisions, PromotionRequests, ExternalReceipts, Forecasts, ReproducibilityClaims, CashClaw opportunities, Darshan source packs, Goodworks MRV outcomes.

## v0 acceptance criteria
- [x] DharmaEval scoreboard rejects mixed manifest hashes (`build_scoreboard` guard + test).
- [x] DharmaEval scoreboard rejects suite contamination (guard + test).
- [x] `FitnessScore.from_external_receipt()` bridge with anti-inward-machine discipline (+ tests).
- [x] `forge_feed_contract` seeded on `VentureCellV1` (+ status helper + test).
- [ ] One sealed task run end-to-end through `ds-goal` → DGM → DharmaEval → promotion gate, producing a receipt with: patch hash, manifest hash, score, cost, command, exit code; promotion returns `candidate_for_human_review` only if telos + replay + holdout pass.
- [ ] Robustness hardening per the running Stanford-PhD research pass (DGM reward-gaming, sealed-holdout discipline, OAG-vs-RAG, reversibility-gated promotion).

## Robustness requirements (research-hardened)
From a Stanford-PhD literature pass (DGM/RSI safety, verifiable-reward anti-gaming, OAG-vs-RAG, reversibility gates). The five invariants that defeat BOTH failure attractors — the Goodhart benchmark-climber and the beautiful inward machine:

1. **Sealed scorer, off-gradient gate.** Oracle, holdout tasks, scoring logs, and the promotion gate run where the candidate cannot read or write them. DGM removed its own hallucination-detection markers when they were on the reward path ([arXiv 2505.22954](https://arxiv.org/abs/2505.22954)); the gate must be causal physics the optimizer cannot route around (Orseau–Armstrong safe interruptibility, UAI 2016).
2. **Transfer-gated promotion, not score-gated.** A child is "improved" only if it beats the parent on a rotating, post-dated holdout AND the gain replicates under a perturbation it never optimized against (different base model / seed / shard). SWE-bench collapses 76%→53% on unseen repos ([arXiv 2506.12286](https://arxiv.org/abs/2506.12286)); only cross-model/cross-task transfer is real capability (DGM Claude-3.7 19→59.5). Holdout = one-time pad: every promotion query spends statistical budget.
3. **No model-judge in the promotion path.** Deterministic oracle only, cost-normalized, with a parent-only/no-op baseline ablation per child. The AI Scientist's self-reviewer missed its own flaws ([arXiv 2502.14297](https://arxiv.org/abs/2502.14297)); AlphaEvolve resists hacking because its evaluator is deterministic. Bounded reward shape (upper bound + rapid-growth/slow-convergence).
4. **Lineage archive + cheap mandatory rollback, open-ended retention.** Every child links to its parent; only compiling + still-self-editable children survive; non-latest branches are kept so a contaminated/regressed generation can be backed out. Rollback cost is a policy input — autonomy ∝ reversibility.
5. **External-receipt binding (the anti-inward-machine invariant).** No improvement escalates to autonomous promotion unless it produces an external receipt (real outcome / payment / human-confirmed delivery); inward-only gains cap at ALLOW_WITH_CONSTRAINTS. Formal grounding: Krakovna AUP / option-value preservation ([arXiv 2010.07877](https://arxiv.org/abs/2010.07877)). `FitnessScore.from_external_receipt()` enforces this in the type (unconfirmed → zero fitness).

**Meta-point the literature is unanimous on:** no one has shown the recursive loop closes *without a human* (Hassabis, WEF 2026). v0/v0.1 keeps a human at the highest-autonomy rung — promotion ends at `candidate_for_human_review`, which `evolution_promotion.py` already does. Do not aim for full autonomy.

## First mission
```
ds-goal init --goal "Reward Forge v0: one sealed holdout improvement on DharmaEval manifest integrity"
```
The command/name to remember is `ds-goal`. The organ is the **Sankalpa Organ**. The north-star build is the **Dharma Reward Forge**.
