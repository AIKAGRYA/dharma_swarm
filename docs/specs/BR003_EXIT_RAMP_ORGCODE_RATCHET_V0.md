# BR-003 Exit Ramp — Org-Code Ratchet v0 (first live selection loop)

**Role:** seed spec (design-only). Subordinate to `docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md` (§4 external-gradient portfolio, §5 D4 sequencing) and `docs/governance/BUILD_SESSION_ENTRYPOINT.md` (item 8, D4 blocker). If this file disagrees with a receipt, `make onboard`, or those doctrine docs, trust them.
**Author:** warp_fable_weaver (evidence-only seat), 2026-07-03. Part of the approved Metabolic Loop Ignition plan (Improvement 4).
**Authorizes:** nothing at runtime. This spec defines the lawful exit ramp from BR-003 so it can be ratified *before* One Wire authority arrives. Activation requires the preconditions in §2 and an explicit operator lease.

## 1. Purpose

BR-003 holds the evolution apply gate shut (`DHARMA_EVOLUTION_SHADOW=1` default across `dgm_loop.py`, `orchestrate_live.py`, `benchmarks/gauntlet.py`, `guardian_crew.py`). Doctrine §5 is exact about why: apply unlocked against internal benchmarks = Goodhart convergence = diversity-term collapse. This spec defines the **first** live selection loop to open when external gradient exists — and it deliberately does **not** open Python mutation. The first genome is **org-code**: the configuration of the organization itself (rosters, topologies, role prompts, memory-sampling policy). This is doctrine §4's node (1) (arena/orchestration genome, "already built, node one") given its ratchet, plus the config-level subset of node (3).

Pattern reference: the Karpathy autoresearch loop (github.com/karpathy/autoresearch) — one mutable surface, one immutable eval, one metric, fixed per-iteration budget, commit-if-better / revert-if-not, git as the ratchet and audit trail. Its published lesson matches our own Forge v0 postmortem: agents execute well-scoped search brilliantly; the search space itself (`program.md` ≙ our org-code) is where design intelligence concentrates. We ratchet the org-code; we do not let the loop near the eval.

## 2. Activation preconditions (ALL required; each independently verifiable)

- **P1 — One Wire quorum granted.** A fresh `forge_measurement_guardian` receipt shows N≥5 confirmed external acted receipts across M≥3 domains and `fitness_authority_granted=true`. External receipts remain the only permitted quorum feed (doctrine §4). No threshold may be lowered to activate this spec (inherited anti-goal).
- **P2 — Honest gauge merged and exercised.** The arena parity harness (best-single-model control arm at asserted budget parity + significance gating, per the `orchestration-arena-v1-2026-06` track blocker) is on main with at least one receipted baseline run, whatever its sign.
- **P3 — D1 receipt stream standing.** Spine dispatch live and emitting EvidenceReceipts persistently (doctrine §5 requires the receipt stream before standing unlock).
- **P4 — Operator lease.** Written lease with spend cap, iteration cap, wall-clock cap, and stop conditions. No lease, no loop.

## 3. The genome (mutable surface — fenced, fail-closed)

Mutable: a dedicated config directory (proposed: `dharma_swarm/coordination/genome/`) containing serialized org-code only —
- seat roster: model/provider assignment per role;
- topology: star / planner-builder-verifier / debate / graph / blackboard variants already representable in the arena;
- per-role prompt configs (system-prompt fragments, skill selection);
- memory-sampling policy parameters (per doctrine §3: worker-seat first-token sampling must stay decorrelated — a mutation that broadcasts identical priors to worker seats is invalid by construction and rejected pre-run).

NOT mutable (loop write-access fenced to the genome dir; runner fails closed on any write outside it): any `*.py`, telos gates, CI ratchets, `archive.py` / One Wire logic, the eval harness, taskpacks, receipts, this spec.

## 4. The immutable eval

The Improvement-2 arena harness, hash-pinned per campaign: sealed taskpack (rotating sealed holdouts), best-single-model control arm, strict budget parity (instrumented and asserted; run fails closed on parity break). **Selection metric:** significance-gated paired lift vs the best-single control. Reported but never selected on: cost, latency, Krogh-Vedelsby diversity term (owner: `dharma_swarm/transcendence_metrics.py`; the MAP-Elites diversity archive lives in `archive.py` — the 2026-07-03 roadmap's attribution of the KV term to `archive.py` is a recorded discrepancy), cross-seat error correlation. Market P&L is never a per-iteration signal (standing non-goal).

## 5. Ratchet mechanics

1. Fixed per-iteration budget (tokens/calls and wall-clock), Karpathy-style, so iterations are comparable.
2. One genome mutation per iteration (single-change discipline for causal attribution).
3. Run the paired eval; compute lift with confidence interval.
4. **Commit** iff the CI lower bound beats the current champion, or the candidate is statistically non-inferior AND strictly cheaper (dominance rule stated in the runner). Otherwise **revert** (git reset on the genome dir).
5. Every iteration emits a receipt: `{genome_hash, parent_hash, taskpack_hash, lift, ci, cost, tokens, verdict, seat_roster}` — extending the arena's existing receipt surface. No new receipt system (standing anti-goal). Archive fitness moves only through the One Wire-authorized path in `archive.py`; the loop itself never writes fitness.

## 6. Diversity preservation (Transcendence Principle compliance)

Selection is MAP-Elites-style over behavior descriptors (topology class × cost band), not hill-climbing to a single champion: non-winning stepping stones are archived, not deleted (June kill-list "Hold, do not kill" doctrine). A mutation that improves lift but collapses the measured diversity term below its rolling floor is quarantined for review instead of auto-committed.

## 7. Stop conditions (any one halts the loop and pages the operator)

Budget/iteration/wall-clock cap reached; parity assertion failure; missing receipt fields; invalid-run rate >5%; three consecutive reverts with degenerate (near-identical) mutations; diversity floor breach; operator halt. Restart requires a fresh lease.

## 8. What this spec does NOT do

- Does not set, request, or imply `DHARMA_EVOLUTION_SHADOW=0` anywhere. Code-path mutation stays shadowed.
- Does not touch the D4 mechanism test (one canonical run, shadow=0, rollback receipt) — that remains separately gated and sequenced LAST per doctrine §5 and BUILD_SESSION_ENTRYPOINT D4.
- Does not create new governance machinery, truth stores, or receipt schemas.
- Does not authorize any public capability claim; internal wins stay Rung-1 language ("local research run") until official external submission or replayable bundle exists.

## 9. Acceptance for this spec itself

Ratified when: reviewed by the operator (or delegated council) with disagreements resolved by edit; referenced from the external-gradient portfolio work as node-one's ratchet design; preconditions P1–P4 each mapped to an existing verifiable instrument (guardian receipt, arena receipt, spine pulse, lease file). Until then it is a proposal and carries no authority.
