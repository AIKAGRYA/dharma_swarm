# Auditable Evolutionary Orchestration Substrate — MASTER BUILD PLAN (LOCKED)

**Status:** LOCKED THESIS · TRACK PROPOSAL (not yet admitted — see Governance).
**Serves spine objective:** `substrate-nativeness`.
**Converged:** 2026-06-22 by Claude (Lane B, remote), Codex (local), and Fugu (architect),
at ~95% on a sharpened thesis. **Drafted by:** Claude remote.

> **Reconciliation note.** An egress collaborator produced a richer local copy of the
> *Verified paper details* at `/Users/dhyana/dharma_swarm` (sources + SHA-256 under
> `/private/tmp/fugu_sources/`). This document is the build plan; merge that copy's
> `## Verified paper details (collaborator handoff)` section in before first commit so the
> exact constants aren't stranded. Committing this file will require a docops inventory regen.

---

## 0. Locked thesis

> **Dharma Swarm becomes an auditable evolutionary orchestration substrate. A zero-weight v1
> coordinator emits `OrchestrationGenome`s; one decorrelated Council (multi-profile) verifies;
> a two-layer arena — frozen hermetic scorer + evolving task curator — scores *verified
> capability delta under budget parity*, where success means beating the best single model at
> equal compute; a MAP-Elites archive promotes winning genomes (including newly-ingested
> research techniques as genes); and only after enough arena-labeled traces exist do we distill
> a small learned coordinator. The moat is not a model — it is the receipt-backed,
> corruption-resistant flywheel that learns to compose many models, tools, organs, and world
> signals without lying to itself about fitness.**

**The product is the substrate, not the coordinator.** The learned model is one replaceable
organ. Build the environment (frozen arena, strict receipts, decorrelated verification, budget
parity, external truth boundaries, evolution archive) and even a small coordinator becomes
powerful; without it, any coordinator is a vibes router.

**Power claim, precisely:** *not* 2–10× on a benchmark (Fugu is already ~93–95; no room).
2–10× on **verified system-power over time** — value-per-decision × trust × self-improvement ×
breadth — on the axes Fugu structurally cannot follow: reward grounded in verified reality,
self-modification under telos gates, real-time research integration, and orchestration of our
own organs. All receipted where Fugu is opaque.

---

## 1. `OrchestrationGenome` — the central abstraction (EXTENDS existing `TopologyGenome`)

Every arena attempt is a genome. Evolution mutates genomes; the arena scores genomes; the
Council verifies genome outcomes; the DPI ranks genome-level techniques; the learned coordinator
(later) learns to *emit* genomes. This is what makes the system DGM-like instead of a pile of
prompt experiments.

**Do not create a parallel abstraction (honors the SSOT naming rule).** `OrchestrationGenome`
**extends/wraps the existing `TopologyGenome`** with a conversion from current topology-genome
dispatch metadata → orchestration-genome metadata. Codex (local) confirms `TopologyGenome` exists.
**Lane B caveat:** `TopologyGenome` is **NOT on `origin/main`** — it is local-only work in the
dirty tree, so the genome contract is **gated on reconciliation preserving and landing it.** If
that work is lost, "extend not replace" loses its base; preserve it explicitly (Phase 0).

```
OrchestrationGenome  (extends TopologyGenome):
  genome_id:            str                # stable hash/id; backward-compatible with TopologyGenome
  task_decomposition:   [subtask, ...]
  role_graph:           communication topology (who talks to whom, in what order)
  roster:               [model|tool|organ|human, ...]   # drawn from existing model_pool
  prompt_fragments:     per-role NL instructions / program fragments
  context_plan:         retrieval / what each role sees ("access_list": [] | "all" | [idx,...])
  budget_allocation:    per-role token/compute/latency budget (must sum within parity cap)
  verification_plan:    which Council profile(s) gate which steps
  adjudication_rule:    how candidate outputs combine (vote / debate / moat-gate / synthesize)
  stop_condition:       accept-on-Council-ACCEPT | max-turns | budget-exhausted
  fallback_rules:       what to do on role failure / timeout / refusal
  permissions:          per-role tool/data permissions (least-privilege)
  # refinement B — quality-diversity, not top-k:
  lineage:              {parent_genome_id, mutation_op}
  behavioral_descriptors: [...]   # MAP-Elites bins (decomposition depth, roster diversity, topology shape, ...)
```

Every arena attempt is **keyed by `genome_id`** and emits route, trace, Council, score, and
decision receipts. A **newly-ingested research technique is just a candidate gene** (a prompt
fragment, a roster member, a topology, an adjudication rule). Research ingestion and orchestration
evolution are the *same flywheel*. (Refinement D.)

---

## 2. One Council substrate (multi-profile)

Do **not** build five partial stomachs. One verifier substrate, multiple profiles:
`world_signal_verification`, `orchestration_trace_verification`, `code_patch_verification`,
`external_receipt_verification`, `research_claim_verification`, `promotion_gate`.

**Shared invariants (all profiles):** quarantine untrusted input; require **≥2 decorrelated
evaluator families AND ≥2 decorrelated source families** to corroborate; replayable receipts;
**no hidden action authority** — Council receipts preserve `dispatch_authority=False` **unless
explicitly transformed by a later warrant layer**; explicit verdicts
(corroborated/refuted/insufficient/quarantined). **The Council verifies and quarantines; it does
NOT become the scorer, the planner, or the dispatcher** (that conflation is a fitness-corruption
vector — see §6). **Correctness-authority split (Codex's G sharpening):** for Arena v1's
verifiable tasks the **deterministic scorer / test-oracle is the SOLE correctness authority**; the
Council verifies *trace integrity, contamination boundaries, evidence sufficiency, and the "this
genome beat controls" promotion claim* — **never correctness itself.** Different profiles differ
only in schema + thresholds. **Adopt the MINIMAL Council interface (the
`orchestration_trace_verification` profile) from #662 first — Arena v1 is NOT gated on full #662
or the world-ingestion seam.**

---

## 3. The two-layer arena (the keystone) — UPGRADE Forge Arena v0, don't build fresh

Forge Arena v0 already exists on `origin/main`
(`scripts/runtime/forge_swarm_evolution_arena_v0_{measurement_runner,preflight,taskpack_builder}.py`,
spec `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`, plus the
`reports/agentops/work_packets/forge-reality-arena-*` corpus). **Reuse its runner/scorer**; add
genome-aware arms + outputs. We already learned the closeout discipline from Forge v0 — keep it.

Split the arena into two layers, with a hard boundary between them, so the system can never
improve at its own moving target:

- **(A) Scorer — frozen, hermetic, replayable.** Sealed labels where possible, baseline controls,
  **budget parity**, scorer_hash + task_manifest_hash, candidate-visible / scorer-only split,
  anti-contamination checks. The scored slice is **frozen per evaluation epoch.**
- **(B) Task curator — evolving, world-fed** (eventually via the throat/Bronze ingestion). May
  expand freely, but cannot mutate the frozen slice mid-epoch.

**Success is defined by the existence test (refinement A):** a genome is `positive_lift_candidate`
**only if it beats `best_single_full_budget` at equal total compute, with significance.** This is
the Krogh-Vedelsby claim made falsifiable. Beating best-single by spending more is theater.

**Arena v1 = ONLY programmatically-verifiable tasks** (code passing tests, math with known
answers) so correctness is objective and the "Council judges instead of verifies" corruption
vector is eliminated at cold start (refinement C). Open-ended / Council-adjudicated tasks → v2.

**Arena v1 MVP** (keep it small; we learned this from Forge v0):
- 10–30 tasks · 3 controls · 1 candidate · strict receipts · budget parity · replayable scorer · bootstrap CI
- **Controls:** `best_single_full_budget` (the GATE), `same_budget_self_moa`, `random_or_static_ensemble`
- **Candidate:** prompted/evolved coordinator genome
- **Outputs:** `arena_run.json`, `scorecard.json`, `trace_receipts.jsonl`, `route_receipts.jsonl`,
  `council_receipts.jsonl`, `power_index.json`, `decision_packet.md`
- **Closeout states:** `positive_lift_candidate` · `measured_negative` · `inconclusive_low_power`
  · `contaminated_quarantine` · `blocked_with_evidence`

---

## 4. Decorrelation reward — *decorrelated correctness*, not disagreement (refinement, Fugu+Claude)

Reward error-covariance reduction, never debate theater:
```
decorrelated_correctness_bonus =
    leave_one_out_marginal_contribution(role)      # did adding it help the FINAL answer?
  × nonredundancy(role.evidence / error_mode)      # is its error decorrelated from the others?
  × final_correctness_gate                         # 0 if the final outcome is wrong
if final_outcome_wrong: decorrelation_bonus <= 0
```
Folded into `VerifiedCapabilityDelta`. This is where we structurally out-*think* Fugu (it rewards
correctness only); not just out-integrate it.

---

## 5. Dharma Power Index (capability in the numerator, trust as multiplier)

```
DPI = VerifiedCapabilityDelta × Trust × ReuseOrLearningValue
      / (Cost × Latency × Fragility × Complexity)
```
- **VerifiedCapabilityDelta:** error-reduction vs best-single-at-budget · value-per-decision ·
  task-family breadth · research-integration velocity · self-improvement rate. (Tricks.)
- **Trust** (multiplier, never the headline): receipt coverage · replay pass rate · corroboration
  strength · auditability.
- **ReuseOrLearningValue (refinement F): retroactive-only.** Counts when a promoted,
  arena-verified reusable artifact *actually results later* — never self-declared at runtime
  (else it becomes a failure-laundering loophole). Log it before activating it.

---

## 6. Anti-corruption invariants — THE moat (biggest risk is fitness corruption, not model quality)

These are load-bearing. Every one closes a way the system could lie to itself:
1. Frozen scored slice per epoch — tasks never move after results are seen.
2. Council **verifies**, never judges-for-reward; v1 correctness comes from sealed labels.
3. Budget parity enforced and logged on every run.
4. **External truth boundary:** internal receipts never count as external proof — only
   countersigned external acted receipts above the One-Wire quorum touch archive fitness.
5. No verbose-debate reward — reward error-covariance reduction, correctness-gated (§4).
6. Trust is a multiplier, never the numerator (§5).
7. Routing cannot hide failures — every failure is receipted.
8. The local dirty checkout is never truth — `origin/main` + receipts are.
9. `LearningValue` is retroactive-only (§5).

---

## 7. Cold-start flywheel + training-example schema

```
prompted v1 generates OrchestrationGenome attempts
  → arena scores them (objective, verifiable tasks)
  → winners enter the MAP-Elites archive (quality-diversity, not top-k)
  → archive becomes the SFT corpus
  → small coordinator is distilled, then generates better genomes
  → repeat;  research techniques enter as candidate genes throughout
```
Early labels are **arena outcomes, not model judgments.** Training example:
```json
{ "task_id":"...", "orchestration_genome":{...}, "trace":[...], "outcome":{...},
  "score":0.73, "baseline_scores":{...}, "capability_delta":0.18, "trust_multiplier":0.91,
  "cost":1.42, "latency":38.0, "fragility":0.2, "receipt_refs":[...] }
```
The M5 fills the arena with local rollouts immediately; no GPU needed for the flywheel to start.

---

## 8. Optimizer + model ladder (Darwin-first; GRPO surgical; small-before-large)

- **DarwinEngine / MAP-Elites is the daily optimizer** — topology/routing/roster are discrete,
  sparse, cheap to search; evolution beats RL here (TRINITY's own sep-CMA-ES finding).
- **GRPO is a surgical scalpel**, valid the moment the arena produces real labels (M5 local +
  rented-GPU bursts). Not the default; not "someday" either.
- **Model ladder:** 0.6–1.7B TRINITY-style reactive head (cheap routing) → 8–14B Conductor-style
  planner for first SFT/GRPO → **30B-A3B / 32B = serious sweet spot once labels exist** → 70B as
  apex teacher/critic/distiller only, never the always-on router. Candidates: Qwen3 8/14/32B,
  Qwen3 30B-A3B, Qwen2.5-Coder-32B. Our own corpus = orientation/self-modeling data only; the
  training core is orchestration traces, receipts, arena outcomes, failures, promotion decisions.

---

## 9. Verified paper constants (from egress; merge richer copy before commit)

**TRINITY (2512.04695):** ~0.6B coordinator SLM + lightweight head (<20K trainable); hidden-state →
**L model-logits + 3 role-logits** (Thinker/Executor/Verifier); for 7 agents = 10 logits; head
adapted via SVF (Transformer²); **sep-CMA-ES** population λ=`ceil(4+3·ln n)` (≈32 for n≈10k),
budget ~1.5k–40k evals; accept-driven termination; sep-CMA-ES beats RL/imitation under high-dim,
sparse-terminal-reward, tight-budget.
**Conductor (2512.04388):** Qwen2.5-7B + **GRPO**, 200 iterations, 4 questions × 64 rollouts =
batch 256, conductor temp 1.0, AdamW lr 1e-6 cosine warmup 0.03, **KL penalty 0**, up to 5 workflow
steps; output = **three Python lists `model_id`, `subtasks`, `access_list`**; `access_list` ∈
`[] | "all" | [idx,...]` (binary chosen — fine-grained didn't materially help). **Correction:**
the paper has **no explicit correctness−λ·cost reward**; cost is handled by rollout budgets/limits.
Any cost term in our DPI is *our* extension, not copied.

---

## 10. Locked build order (Refinement G RESOLVED — Claude proposed, Codex ratified + sharpened)

G is locked: **the throat and the Arena are sibling consumers of the Council, not parent/child.**
Arena v1's critical path is *only*: reconcile → minimal shared Council interface → genome → frozen
Arena scorer/controls. The throat is for world-signal ingestion / research curation / Arena-v2 task
generation, and runs **in parallel** — it does not gate Arena v1.

0. **Reconciliation / preservation / off-machine backup** (Lane C + Fugu) — *step zero, underway;
   the orchestrator is gated on a trustworthy `origin/main`.* **Preserve the local-only
   `TopologyGenome` work explicitly** — the genome contract (§1) extends it.
1. **Extract/adopt the MINIMAL Council interface** — the `orchestration_trace_verification`
   profile from **#662** (not a blind merge; *not* gated on full #662 or the world-ingestion seam).
   This is the smallest verifier interface Arena v1 needs.
2. **Genome contract.** `OrchestrationGenome` as an extension/wrapper of `TopologyGenome` (§1):
   serialization, validation, stable hash/id, receipt refs, topology→orchestration conversion,
   backward-compatible with existing topology-genome tests.
3. **Arena v1** — **upgrade Forge Arena v0** (§3) on **frozen verifiable taskpacks**. Authority
   split: **deterministic scorer/test-oracle = correctness authority; Council = trace/contamination/
   "beat-controls" claim verifier, never correctness.** Best-single gate; genome-aware arms +
   outputs + closeout states.
4. **Zero-weight orchestrator v1** emits `OrchestrationGenome` (prompted generator + simple mutation
   ops + bandit/routing-memory roster choice + Darwin archive selection + route receipts). **No
   SFT/GRPO/GPU; no production-router mutation.** **Run controls** incl. the best-single gate →
   first `decision_packet.md`.
5. **Throat seam — IN PARALLEL** (Bronze→Council→warrant, no dispatch authority). Adopt/fix **#663's**
   document ingest *only if* part of world/research ingestion (repair its MCP-ingest gap,
   MarkItDown-executable check, dependency extras, stale DocOps). Feeds the **v2 task curator** +
   research-genes — **off the Arena v1 critical path.**
6. **Flywheel** — promote winning genomes to the MAP-Elites archive; turn on the research-ingestion
   loop (ingest → Council verify → Darwin proposes integration trial as a genome → arena scores →
   promote only with receipts).
7. **Unify** the arena and throat under the same Council profiles.
8. **Distill the small coordinator** (TRINITY-style head) on arena-labeled genome traces.
9. **Surgical GRPO** spike (4–14B) once labels are real → scale to 30/32B after proof → 70B apex-only.

## 10a. Test plan (from codex's plan)

- **Unit:** `OrchestrationGenome` validation / serialization / stable hash-id / **backward-compat
  with `TopologyGenome`**; Council profiles preserve no-action-authority + domain thresholds; DPI
  including the correctness-gated decorrelation bonus; arena closeout-state selection.
- **Integration:** one genome runs orchestrator → spine receipt → Council verification → arena
  score → decision packet; **candidate cannot read sealed labels / scorer-only files**; budget
  parity logged for candidate *and* controls; winning genome archives **without mutating
  production routing**; contaminated/high-risk input → quarantine closeout.
- **Regression:** existing topology-genome, spine-receipt, and Forge Arena v0 tests stay green;
  adopted #662/#663 code gets targeted tests for quarantine, replay, document/MCP ingest, DocOps.

**Standing assumptions:** no model trained until arena-labeled traces exist; no blind merge of
#662/#663 (adopt/rebase/fix); `TopologyGenome` is the base, `OrchestrationGenome` extends it;
capability is the headline, receipts are proof/replay; the Council verifies, it is not the reward
model by itself; **frozen-arena integrity outranks rapid self-improvement.**

---

## 11. Owned surfaces + track declaration

New, non-colliding surfaces. **Extend, don't own:** `TopologyGenome` (local-only, preserve+land
first), Forge Arena v0 (`scripts/runtime/forge_swarm_evolution_arena_v0_*.py`). **Consult/reuse,
don't own:** `provider_policy`, `model_hierarchy`, `orchestrator.py`, `evolution.py`,
`diversity_archive.py`, `ginko_brier.py`. The **Council is shared substrate** with the seeing-organ
track; coordinate (single substrate, not two).

```yaml
- id: orchestration-substrate-2026-06
  name: Auditable Evolutionary Orchestration Substrate — genome arena + one Council + flywheel
  status: ACTIVE
  opened_at: "2026-06-22"
  verified_at: "2026-06-22"
  ttl_days: 21
  owner: "@AmitabhainArunachala"
  serves: substrate-nativeness
  complements:
    - provider-routing-consolidation-2026-06   # feeds the genome roster (dozens of models)
    - seeing-organ-2026-06                      # shares the one Council substrate
    - runtime-truth-spine-adoption-2026-06      # EvidenceReceipt = route/trace receipts
    - loop-closure-2026-06
  owned_surfaces:
    - dharma_swarm/coordination/**              # genome.py, arena/, dpi.py, flywheel/, routing_receipt.py
    - dharma_swarm/council/**                   # shared multi-profile Council (adopts #662's frontier_council as profile 1)
    - scripts/governance/check_arena_replay.py
    - scripts/governance/check_routing_receipt.py
    - scripts/governance/check_council_invariants.py
    - tests/test_orchestration_genome.py
    - tests/test_arena_v1.py
    - tests/test_council_profiles.py
    - tests/test_dpi.py
    - docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md
  moves_vital_signs: [quality_gates, tool_coverage, eval_coverage, cost_efficiency]
```

---

## 12. Governance

- **Do not admit this track yet.** The portfolio is mid-reconciliation and over the WIP cap
  (`max_active: 10`). Admit only after a slot frees — the clean baton-pass is closing
  `provider-routing-consolidation` (substantially landed on `origin/main`), with
  `orientation-graph` reactivation dropped and `cybernetics-codex-stewardship` folded into
  loop-closure as two further free slots.
- The Council is co-owned with `seeing-organ`; treat it as one substrate (coordinate, don't fork).
- Committing this file changes the tracked markdown count → run docops inventory regen.

## Sources
TRINITY arXiv 2512.04695 · Conductor arXiv 2512.04388 (OpenReview U23A2BUKYt) · Sakana Fugu
(sakana.ai/fugu, SakanaAI/fugu) · Graph-GRPO 2603.02701 · AgentConductor 2602.17100 ·
Krogh-Vedelsby 1995 · Zhang et al. NeurIPS 2024 · Abreu et al. 2025. Convergence record: Claude
(Lane B) ↔ Codex ↔ Fugu, 2026-06-22 (codex's implementation plan + test plan integrated:
extend `TopologyGenome`, upgrade Forge Arena v0, Council-not-scorer invariant).
