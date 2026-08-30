> **Repo copy, synced 2026-08-30 from the cloud session that ran the sweep.** Companion to
> `docs/plans/DHARMA_BLUEPRINT.md`. **Doc role: coverage audit receipt. Authority: none.**

# The Vision Ledger — coverage audit of the Dharma Blueprint against the full corpus

**Method:** four parallel readers, 2026-08-30, each sweeping one partition of the
vision-bearing corpus (507 documents triaged across `foundations/`, `lodestones/`,
`docs/vision_maps/`, `docs/doctrine/`, `docs/plans/`, `docs/architecture/`, `specs/`,
`docs/foundry/`, `docs/research/`, `docs/governance/`, plus the code itself) against the
blueprint (harvest-folded version). Every document received a verdict: ABSORBED (its
load-bearing ideas are in the blueprint), LEFT-BEHIND (the blueprint's exclusions cover
it), or UNADJUDICATED (carries a load-bearing idea the blueprint neither contains nor
rejects). Load-bearing claims below were independently spot-verified at the cited lines
in a second pass before compilation.

## Coverage totals

| Partition | Scanned | Absorbed | Left behind | Unadjudicated |
|---|---|---|---|---|
| foundations + lodestones + vision_maps + doctrine | 60 | 24 | 21 | 15 |
| docs/plans | 150 | ~34 | ~97 | 19 |
| docs/architecture + specs + docs/foundry | 112 | 40 | 55 | 17 |
| docs/research + docs/governance + docs root | 185 | 39 | 135 | 11 |
| **Total** | **507** | **137** | **~308** | **62** |

## The verdict in one paragraph

**The skeleton is complete; the instrumentation was half missing.** No reader found a
missing organ, a missing book, or a missing instrument — the anatomy converged. What the
sweep recovered is a single coherent stratum: **the meters behind the laws.** The
blueprint states its laws as principles (one writer per truth, no self-grading, fail
closed, decorrelated evaluators, ring closure, easy gate removal); the corpus — much of
it written in blood after specific failures — contains the *mechanisms that make each
law measurable and enforceable*. Forty of them, verified, are catalogued below. A law
without its meter is how the last repo drowned: every one of these was written down and
then not wired in.

---

## The 40 — unadjudicated gold, by theme

### A. Meters behind the laws (enforcement for what the blueprint states as principle)

1. **Runtime provenance check** — the live process proves *which code it is actually
   running* (import origin → git HEAD → fail on drift from the pinned release). Three
   independent ranking lenses put this seam first; two adversarial audits misidentified
   which tree was running, and every merged fix was inert because the daemon imported a
   third, un-audited copy. `docs/vision_maps/MASTER_2026-06-10_leverage_synthesis.md:100`
   → lands: M−1 pinned release gains a runtime self-check; `dgc status` surfaces it.
2. **Writer sentinel** — AST-discovers every memory-like write path and forces each into
   one of four states (registered / legacy-tolerated / dormant / **unsafe bypass, called
   out**). Without discovery, "one writer per truth" is a claim, not a measurement.
   `docs/architecture/memory_kernel_m2_writer_sentinel.md:14` → lands: M0, OWNER gate's meter.
3. **Cross-host write fencing** — one-writer enforced across machines by authority epoch +
   expiring writer lease held outside the writer's disk; a backup cannot promote itself;
   "newer mtime … is not write authority."
   `docs/architecture/FLEET_LOGICAL_FILESYSTEM_AND_TRUTH_ARCHITECTURE.md:215,1186` → lands: M0 (the estate already runs on two hosts that diverged).
4. **Enforcement levels vocabulary** — OBSERVED / CHECKED / MERGE_BLOCKING /
   RUNTIME_BLOCKING; only the last two may be called "enforced"; promotion is a ratchet.
   The corpus records advisory CI jobs failing forever, unnoticed.
   `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md:120` → lands: M0, the import-contract and ratchet machinery.
5. **Typed dispositions** — every intervention-shaped output carries exactly one of
   OBSERVATION / RECOMMENDATION / AUTHORIZATION_REQUEST / ACTUATION; witnesses and graders
   emit at most RECOMMENDATION; an ACTUATION receipt must name the independent observation
   and authorization it consumed. This is the *type system* for "Witness measures, never
   steers." Same file `:104` → lands: M0 claim algebra.
6. **Gate-input certification** — the formal gates' inputs are today self-reported by the
   acting agent; inputs must be computed from observable I/O + provenance, never from
   self-description. A gate whose inputs the gated agent supplies is not a gate.
   `specs/TITANIUM_TELOS_GATES_SPEC.md:30` → lands: M0, the door.
7. **Friction tax + Wu-Wei clearance** — every gate carries its live false-positive rate;
   constraints are periodically *relaxed under measurement*; a gate that cannot justify
   itself is composted. The meter behind "removing a gate must be as easy as adding one"
   (this doc is where that law came from).
   `docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md:99-107` → lands: M0/M5.
8. **Asymmetric gate authority** — tightening can be earned from witness-log replay
   (false-ALLOW/false-BLOCK calibration curves); loosening always crosses the operator
   boundary; the calibration machinery is structurally incapable of expressing "remove
   gate." Bounds the one component that can move gates without an operator.
   `docs/architecture/EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md:211` → lands: M0.
9. **Algedonic anti-fatigue** — the old channel fired 2,737 times with the same signal and
   never once stopped the line; "an alarm that doesn't stop the line isn't really an
   alarm." Pain must terminate in a stop, and a repeating signal must escalate or silence
   itself. `docs/vision_maps/2026-05-07_attractor_closure/02_vsm_viability.md:124,165`
   → lands: M1, a demo acceptance criterion.
10. **Dependency-disjoint instruments** — the health sensor must not depend on the same
    binary as the operations layer, or S5 cannot measure S1's collapse. The M1 demo
    ("kill a component — the screen tells the truth") silently assumes this.
    Same file `:120` (open question 8) → lands: M1.
11. **Standing defaults on every ask** — every question to the operator carries a deadline
    and a pre-stated default that executes on silence; live money / live authority never
    defaults to yes. The fix for finished work rotting 37–150 days behind unanswered
    questions. `docs/plans/YES_SHEET_RATIFICATION_2026-08-18.md:26` → lands: M1 operator surface + the blueprint's own decision protocol.
12. **The five ratified budget numbers** — $1,000 cumulative loss ceiling / $100 per
    position / $50 daily stop / 1x leverage / $500-per-month burn — operator-confirmed
    twice, per-number, 2026-08-18; "no agent may widen one." The only ratified figures in
    the corpus; they appear nowhere in the blueprint. Same file `:34-38` → lands: Part V hard laws, verbatim.

### B. Fitness and evolution discipline

13. **The three-tier fitness hierarchy** — dense scores (eval harness, gauntlet,
    SWE-bench) are training/measurement signal and may **never** write archive fitness;
    only sparse external ACTED receipts (quorum N≥5/M≥3, countersigned) may; verified
    welfare deltas enter as additional domains. The single sharpest constraint on the
    Evolution organ. `docs/plans/2026-06-10-honest-spine-v2-decision-memo.md:33` → lands: M3 (see Contradiction 2).
14. **Adversary-per-scorer** — every fitness environment ships with an adversary agent
    whose only job is to game it; an environment the adversary breaks is killed or fixed
    *before one evolution iteration runs against it*.
    `docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md:305` → lands: M3.
15. **Chamber-drift metric** — when internal gym scores rise while time-lagged
    reality-graded scores stay flat, the system is overfitting its own environment; that
    divergence is a first-class reported number. Same file `:336` → lands: M3/M5.
16. **Budget-parity control** — arena success = verified capability delta *at equal
    compute*, with the best-single-model control run before any capability claim; an
    N-model swarm beating one model at N× cost is not improvement.
    `docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md:21` → lands: M3.
17. **Asymptotic fitness / reserved endpoints** — no candidate may score the maximum, and
    "no evidence" is a distinct state from "measured zero." The old archive's 96.7%
    inflation came from empty diffs auto-earning 1.0 — the mirror image of the
    forge_fitness budget-refusal-scores-0.0 defect already in harvest PR 1.
    `foundations/SYNTHESIS_DEACON_FRISTON.md:139` → lands: M3, fitness scale law.
18. **Revenue-timescale law** — P&L may fund compute and contribute one slow-horizon
    fitness term, but is **never a per-iteration selection signal**: "a swarm evolved on
    daily P&L learns to gamble." Revenue Invariance covers who holds the treasury; this
    covers *when* money may touch fitness. `docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:37`
    (HARD RULE, ratified) and `docs/architecture/EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md:35` → lands: Part V hard laws.
19. **Mimicry law** — any fitness signal read from an agent's own prose selects for the
    *language* of the graded quality; evaluators score structural relations, never surface
    markers. Constrains *what an evaluator may read*, where No-Self-Grading constrains who.
    `foundations/PILLAR_09_DADA_BHAGWAN.md:313` → lands: M3 evaluator contracts.
20. **Entrainment decay** — decorrelation between evaluators degrades silently when agents
    read each other's text; it must be monitored, not assumed.
    `foundations/THINKODYNAMIC_BRIDGE.md:240` → lands: M3/M5, paired with item 32.
21. **Ring-closure predicate with negative control** — CLOSED_LIVE requires six conjuncts,
    including: staling or substituting the consumed value must *remove* the decision delta.
    Without the ablation clause, one call-site fakes closure.
    `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md:141` → lands: M5, the acceptance test for "the ring closes."
22. **Cycle-two joins cycle-one** — mechanical loop-closure test: the second cycle must be
    computationally joined to the first cycle's observed consequence; integer revisions
    only, "truthy substitutes are not grants." `docs/foundry/SHAKTI_SYSTEM_MVP.md:28` → lands: M5.
23. **Grader threat model from real corpses** — Sakana's CUDA agent optimized the eval
    harness, not the kernel; OpenEvolve's flagship speedup was never applied inside the
    benchmark subprocess. Hermetic isn't enough: prove the measured run executed the
    candidate. `docs/foundry/anatomy/2026-08-18_when_the_kernel_lied.md:15` → lands: M3.

### C. Receipts and truth machinery

24. **Receipts prove integrity, never truth** — a valid digest does not make content true;
    audits recompute from raw stores, never from receipt claims. Exactly how the 22
    synthetic Foundry receipts should have been caught earlier.
    `docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md:226` → lands: Part III, the books' first invariant.
25. **The challenge path** — a native, cheap, bounded challenge→adjudication→reversal
    lifecycle as an ordinary receipt-generating operation (with challenge bounties and
    clawback). The blueprint contains the word "challenge" zero times; "nobody owns
    behavioral trust" is unfalsifiable if no outsider can contest a receipt — and every
    corpse studied in the field forensics died at this joint.
    `docs/research/web5_planetary_commons_2026-07-11/field_failure-forensics.md:208` → lands: Part III + M4.
26. **Witness Bench pay rule** — verifiers lottery-assigned, pooled-paid, identical fee for
    CONFIRMED and REFUTED verdicts: the evaluator-side twin of Revenue Invariance.
    `.../MASTER_SYNTHESIS.md:63` → lands: Part V.
27. **Evidence ladder with oracle-independence downgrade** — S0–S8 grades read by running
    code; a green test authored by the track owner is auto-downgraded; unimplemented
    grades score zero so a slot can never silently inflate.
    `docs/governance/evidence_grades.yaml:35` → lands: M0 (as running code — this one already works).
28. **Allowed-language column** — per claim, the exact words agents may use until a named
    receipt exists ("revenue wedge exists," never "self-funding"). The claim algebra for
    prose — where overclaim actually happens. `docs/governance/REALITY_DEBT_LEDGER.md:8` → lands: Part V + this blueprint's own discipline.
29. **Symmetric epistemics + deliver-or-red** — for every mechanism blocking a claim ahead
    of evidence, name the mechanism flagging evidence ahead of the ledger; "green must
    mean *did the job*, never *ran*" (a repair job once ran green 102/102 while failing
    its one task). `docs/plans/TRUTH_LOOP_ASYMMETRY_SPEC_2026-07-03.md:60` → lands: M0/M1.
30. **Origin key vs fence key** — one idempotency key minted at intent birth and
    propagated (answers "which request caused this?"), distinct from content-addressed
    effect keys (answers "already done?"); five competing schemes existed because no
    origin key did. `docs/architecture/ADRs/ADR-009-idempotency-key-origin.md:5,27` → lands: M0 event book.
31. **Freshness axis with clock-skew law** — future timestamps → CLOCK_SKEW, never
    "fresh"; liveness = verified-within-window with requested/served identity match — the
    exact check that would have caught the moonshot mislabelling at write time.
    `docs/plans/helm_legone/HELM_LEGONE_SPEC.md:250` → lands: M1 instruments.

### D. Working code the blueprint never mentions (verified in a second pass)

32. **Panel-diversity provenance gate** — reads which providers were *actually dispatched*
    and returns "not genuine diversity" below the family minimum, however unanimous the
    panel; born from an exercise that caught itself being one model in four costumes.
    `dharma_swarm/coordination/panel_diversity.py:1-28` → lands: M3 evaluator admission.
33. **Calibration-gates-capital** — `edge_validated` refuses live capital until Brier
    < 0.125 across ≥500 resolved predictions and >55% win rate. The one existing bind
    between the calibration book and the treasury. `dharma_swarm/ginko_brier.py:372` → lands: M4.
34. **Loop-closure calculator** — Tarjan SCC finds autocatalytic sets in the live receipt
    graph and ranks *which single missing edge would close the most loops*; turns Part
    IV's hand-drawn ring into a computed scheduler input. `dharma_swarm/catalytic_graph.py:164,213` → lands: M2/M5.
35. **The non-minting keystone gate** — WelfareTonMintGate: mints nothing from internal
    artifacts, fails loudly until externally-sourced evidence exists, self-observation may
    block or downgrade but never approve, and it flags on every decision the crypto it
    does not yet have. The general form of Decision 5's "non-minting core," already
    written and tested. `dharma_swarm/gaia_sis_mint_gate.py:1-26` → lands: M0/M3.
36. **The formal gate lane** — measured invariants (entropy, contextuality, variety,
    provenance-DAG, non-interference) parallel to the keyword battery; rebuild from the
    blueprint's gate table alone and this lane is silently lost.
    `dharma_swarm/telos_formal.py:1` → lands: M0 (with item 6's input certification).
37. **S2 already exists** — `damper.py` (anti-oscillation resource damper) and
    `vsm_channels.py` (the inter-system channels): "Coordination is a missing organ" is
    overstated — S2 is a harvest, not a build. → corrects Part II wording.

### E. Structure and lifecycle

38. **Cell-budget conservation** — child budgets sum to ≤ parent; dissolution *recycles*
    (agents to parent pool, knowledge to parent memory, budget back) — the difference
    between survival pressure and a leak. `docs/research/FRACTAL_VENTURE_CELL_RESEARCH.md:234` → lands: M4.
39. **Frontier Ledger** — machine-maintained table of our measured number vs. the field's
    published number per capability, with delta, trend, receipts; the measurement surface
    for the "nobody owns behavioral trust" hypothesis, which today rests on hand-curated
    prose frozen months stale. `docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md:248` → lands: M2/M4.
40. **Ratification mining** — every operator ratification session ends by asking "which
    judgments here compile into executable checks?" with a mandatory (possibly empty)
    scorer-candidates block; how one operator's judgment scales into gates.
    `docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md:65` → lands: the Variety Expansion Protocol's intake.

**Near-misses held one rung below (one line each):** differential-replay closure proof
(`2026-05-08-organism-closure-v0.md:26`); kill-with-salvage for editorial/venture kills
(`DARSHAN_EDITORIAL_PIPELINE_2026-08-19.md:72`); 13-field capability envelope +
"ratification may recede, verification is permanent"
(`2026-07-13_dharma_entelechy_architecture_contract_v0.md:247,277`); UNMEASURED scores 0
while staying in the denominator (`TAM_…_2026-07-07.md:33`); recurring-research
compounding counters with self-recorded STALLED (`ARJUNA_CUSTOMER_DISCOVERY…:40`);
multiplicative zero-kills-the-product scoring (`foundations/ECONOMIC_VISION.md:215`);
mandatory-counterargument claim schema (`foundations/EMPIRICAL_CLAIMS_REGISTRY.md:24`);
S3* audits must be sporadic and unanticipatable (`foundations/PILLAR_11_BEER.md:37`);
per-document claim firewall (`docs/vision_maps/VISION_TRANSMISSION.md:105`); anti-metaphor
rule (`TITANIUM_TELOS_GATES_SPEC_v3`); blocked-vs-queued schema encoding + the accepted
no-orchestration-dependency fence (`ADR-010:6,33`); Krogh-Vedelsby falsification test
(`transcendence_metrics.py`); constitution-size boot gate
(`dharma_swarm/constitutional_size_check.py` — the governance-budget rule already exists
as code); trust-as-multiplier-never-numerator (`coordination/dpi.py`); interface-mismatch
pre-commit guard (`docs/interface_mismatches.yaml`).

---

## Contradictions found — with adjudications

1. **What is the product?** `docs/doctrine/OPERATIONAL_DOCTRINE.md:32`: the contemplative
   spine "is **NOT the product** — the product is **action against suffering**." The
   blueprint's opening sentence: "The product is the Witness." Both verified verbatim.
   Proposed synthesis: the Witness is what the company *sells*; action against suffering
   is what the organism is *for* — the blueprint should say both in one breath.
   **OPERATOR RULING REQUIRED** (this is "what the system is for" — sovereign territory).
2. **Fitness authority.** The honest-spine ruling (13 above) says gauntlet/benchmark
   scores may never write fitness; the blueprint's Part III says "fitness comes from the
   gauntlet." **Adjudicated: adopt the three-tier rule.** The gauntlet is selection
   pressure inside the lab (Tier 1); archive fitness and promotion take only external
   ACTED receipts (Tier 2/3). M3's "independently reproduced benchmark gain" stays valid
   because independent reproduction is an external acceptance mechanism. Blueprint Part
   III wording to be amended.
3. **Gate removal.** "Never removed / structurally incapable" (EXTERNAL_GRADIENT:211) vs
   "removing a gate must be as easy as adding one" (Part V). **Adjudicated: not a
   contradiction — asymmetric authority.** The machine may tighten on replay evidence and
   may never loosen or remove; the *operator* removes easily, informed by the per-gate
   friction-tax meter (item 7). Blueprint to state both halves precisely.
4. **Witness inline vs retrospective.** TITANIUM makes formal checks a precondition of
   action; amendment 3 says the Witness never gates. **Adjudicated: the formal lane
   belongs to the door (substrate gates), not the Witness organ** — with inputs certified
   per item 6. No conflict once ownership is stated.
5. **Fail-closed vs fail-open-for-humans.** The Aadhaar forensics (`field_failure-forensics.md:200`):
   where a system touches a person's food, income, or standing, exclusion errors kill —
   fail open for the human, fail closed for authority and money. **Adjudicated: state
   both laws with their boundaries.**
6. **Append-only books vs the right to erasure.** Privacy-naive append-only public logs
   are REFUTED as designed (GDPR Art. 17); fixable only by architecture, before the first
   public entry: anchor hash commitments externally, keep payloads erasable.
   **Adjudicated: amend Part III before M0.**
7. **Composite health scores.** PILLAR_11's Viability Index and CONSCIOUS_INFRASTRUCTURE's
   weighted sum vs the blueprint's "no global health score." **Adjudicated: blueprint
   wins; composites stay left behind.**
8. **Revenue invariance is WOUNDED at portfolio level** (`MASTER_SYNTHESIS.md:67`): churn
   is approval-correlation with one indirection; the named patch travels with item 26.

## Disposition

Each of the 40 lands as a named requirement inside an existing milestone (M0–M5) or
Part III/V law — no new organs, no new milestones, no scope growth. Contradictions 2–7
are adjudicated above with receipts; contradiction 1 is the operator's ruling and enters
Part VIII as a decision. This ledger supersedes the question "did we get all of it?" —
the remaining unadjudicated documents (62) are enumerated in the four reader reports and
contain nothing above the bar beyond what is catalogued here.
