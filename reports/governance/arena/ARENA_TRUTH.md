# Arena Truth — governance report surface (read-only)

**Schema:** `arena_truth_report.v1` · **Generated:** 2026-07-27T14:23:08Z
**Replay:** `python3 scripts/governance/arena_truth_report.py --check`

> **NO CAPABILITY CLAIM.** none — hermetic fixture harness only. The fixture pool is CONSTRUCTED so that specialist routing beats best-single (Krogh-Vedelsby by design), so the lift shown is a control-machinery existence proof on the frozen synthetic taskpack, NOT a production capability claim (track non-goal 1) and NOT commensurable with trust-gate C2 (which reads only live benchmark runs). Live-lane runs must carry the same best-single + budget-parity + significance controls before any claim.

## Search summary (zero-weight, seeded, hermetic)

- seed `0` · generations 12 · genomes evaluated 17
- MAP-Elites cells illuminated: 5 · winners (positive_lift_candidate): 2
- best genome: `genome-6f74d65b34c0424e` (synthesize over alpha-math, beta-code, gamma-logic)
- observed lift vs best-single at parity: 0.6250 (p=0.0000, significant=True, n=24)
- cold-start corpus: 48 labeled trace rows (`cold_start_corpus.jsonl`, sha256 `05a3692e3b02d928…`) — labels only, zero training (v1 doctrine)

---

# Arena v1 — Decision Packet

- task_pack: `76f69c2f2994dbe5…`
- task_manifest_hash: `76f69c2f2994dbe5…`
- scorer_hash: `5c5e5be906ed2e85…`
- candidate_genome_id: `genome-6f74d65b34c0424e`
- measurement_mode: `hermetic_fixture`
- **closeout_state: `positive_lift_candidate`**
- council_verdict: `corroborated`

## Scores at budget parity

| arm | score | total_compute | within_parity |
| --- | ----- | ------------- | ------------- |
| candidate | 1.0000 | 2400 | True |
| best_single_full_budget | 0.3750 | 2400 | True |
| best_single_parity_budget | 0.3750 | 2400 | True |
| same_budget_self_moa | 0.3750 | 2400 | True |
| random_or_static_ensemble | 0.3750 | 7200 | False |

## Best-single gate

- best_single_full_budget score: 0.3750
- candidate score: 1.0000
- observed_lift: 0.6250  ci95=[0.4167, 0.7917]  (p=0.0000, significant=True, n=24)
- budget_ref: 2400  ·  candidate_within_parity: True

## Budget-parity control (strongest seat at the swarm's call budget)

- control_model: `beta-code`  ·  parity_verified: **True** (fails closed on mismatch)
- calls: control=24 candidate=24 (match=True, per_call_cap=None)
- best_single_parity_budget score: 0.3750
- observed_lift: 0.6250  ci95=[0.4167, 0.7917]  (p=0.0000, significant=True, n=24)

## Dharma Power Index

- DPI: 0.000022
- verified_capability_delta: 1.2500
- decorrelation_bonus: 0.6250 (final_correct=True)
- trust_multiplier: 1.0000
- reuse_or_learning_value: logged=1.0000, active=False

## Verdict

✅ POSITIVE LIFT: the genome beats best-single at equal compute, with significance. Eligible for MAP-Elites promotion.

_Correctness authority: the deterministic scorer/test-oracle only. The Council verified trace integrity, contamination boundaries, and the 'beat controls' claim — never correctness._

