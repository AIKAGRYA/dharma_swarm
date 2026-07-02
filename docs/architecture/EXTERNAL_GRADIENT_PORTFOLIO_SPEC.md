# External-Gradient Portfolio Spec — diversity of objective functions

**Status:** SPEC-FIRST. No code changes. This document is `organism-rewire-2026-07` item 8.
**Serves spine objective:** `substrate-nativeness` (and re-anchors `research-depth` via node 6).
**Ratified doctrine:** `docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md` §4 (D3). If this file
disagrees with the track (`docs/governance/ACTIVE_TRACK.yaml`) or a receipt, trust the track/receipt.
**Binding law:** NORTH_STAR §3 (ONE LAW: no cell spawns, grows, or claims status except by closing
a strange loop on a real, gated, verifiable, diversity-preserving outcome) and CLAUDE.md
§Transcendence Principle (`E_ensemble = E_mean - E_diversity`, Krogh-Vedelsby).
**Sequencing:** this portfolio is D3 in the arc `1 → 2 → D1 → D3 → D2 → D6a → D4-test → D6b →
D4-standing` (doctrine §7). Nothing here unlocks DarwinEngine standing apply — see §3.3.

---

## 1. The portfolio principle

Evolution needs fitness signals the organism cannot fake from inside. A single objective function
— however honest at ratification — accumulates Goodhart pressure the moment selection runs against
it. The countermeasure is the same math as agent diversity: **decorrelated fitness signals cancel
each other's Goodhart modes** exactly as decorrelated agent errors cancel in aggregation. A policy
that games the arena's frozen slice does not thereby game routing-receipt replay; a strategy that
overfits a benchmark does not thereby produce Deflated-Sharpe-surviving P&L; nothing internal
produces a countersigned external acted receipt. The portfolio *is* the anti-Goodhart mechanism —
diversity of objective functions on the same math as diversity of agents (doctrine §4).

Three gradient classes, each with a fixed role that must not creep:

1. **Verified external benchmarks — the volume fuel.** Cheap, repeatable, mathematically
   scoreable; the substrate for high-iteration autoresearch loops (the six nodes of §2).
   Guardrails: rotating/held-out sets + budget-parity controls, or it is overfitting wearing an
   evolution costume (doctrine §4; arena non-goal in `ACTIVE_TRACK.yaml`).
2. **Market P&L — funding + slow-horizon term ONLY.** Shakti Ginko → Capital Lab per NORTH_STAR
   §4.2. HARD RULE (track non-goal, ratified): P&L may fund compute and may contribute one
   slow-horizon fitness term (Sharpe over months, under Deflated-Sharpe/PBO discipline, with
   paper → small-live gates) and is **NEVER a per-iteration selection signal** — a swarm evolved
   on daily P&L learns to gamble. The differentiated wedge is the honesty stack itself
   (NORTH_STAR §10: anti-Goodhart gates, Deflated-Sharpe/PBO, publishing misses).
3. **Paid human work — the C3 leg.** Slowest, richest; carries trust-gate C3 ("a full
   venture-cell build, end to end, verifiably competitive" —
   `scripts/governance/trust_gate_status.py:47`, scored by `score_c3` at
   `trust_gate_status.py:197-222` against `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` revenue
   receipts). Third leg, not first; it validates that value leaves the house, it does not drive
   iteration volume.

Every node in §2 draws its gradient from class 1. Classes 2 and 3 enter fitness only through the
One Wire (§3.2) or the slow-horizon term — never per-iteration.

**The node quartet.** A node is admitted to the portfolio only when all four exist (Karpathy-loop
discipline, doctrine §4):

- **Frozen eval** — a sealed, hashed, replayable scoring surface that cannot move mid-epoch.
- **Mutation operator** — a mechanical way to generate candidate variants.
- **Diversity-preserving selection** — MAP-Elites-style archive admission, never top-k
  (consolidating on `dharma_swarm/archive.py:197` `MAPElitesGrid` per D6a, doctrine §6).
- **Receipts** — every scored attempt emits an auditable artifact; runtime receipts live under
  `~/.dharma/` per CLAUDE.md (never in git), with governance-visible summaries in `reports/`.

---

## 2. The six autoresearch nodes

### 2.1 Node 1 — Arena / orchestration genome (BUILT; node one)

The DGM-substrate keystone, already on main under the `orchestration-arena-v1-2026-06` track.

- **Frozen eval:** `dharma_swarm/coordination/arena/taskpack.py` — frozen slice pinned by
  `task_manifest_hash()` (`taskpack.py:107`) + `sealed_oracle_hash()` (`taskpack.py:115`);
  deterministic scorer as SOLE correctness authority (`arena/scorer.py:1-8`, `scorer_hash()` at
  `scorer.py:49`); sealed-label access tripwire (`taskpack.py:136-143`). Significance via seeded
  paired bootstrap (`arena/runner.py:250-270`, p < 0.05 at `runner.py:57`).
- **Mutation operator:** heuristic genome generation + mutation in the zero-weight orchestrator
  (`dharma_swarm/coordination/orchestrator_v1.py:1-12` — zero LLM, zero GPU, never mutates
  production routing).
- **Diversity-preserving selection:** `MapElitesArchive.consider()`
  (`orchestrator_v1.py:47-67`) binned on `BehavioralDescriptors.bin_key()`
  (`coordination/genome.py:103-111`); contaminated genomes are never promotable.
- **Receipts:** route/trace receipts per arm (`arena/runner.py:158-176`), scorecards tied to
  `genome_id` (`runner.py:181`), DPI decomposition (`coordination/dpi.py:81-118`), Council trace
  verification (`dharma_swarm/council/council.py`), closeout states (`runner.py:42-48`).

**What it still needs** (already blockers on the track): (a) **best-single-model controls +
budget-parity proof on every run before any capability claim** — the control exists hermetically
(`runner.py:193-211` `_best_single_full_budget`, parity logged at `runner.py:288-299`) but only
against the recorded `FixturePool` (`arena/fixtures.py`); live-model arms with real dispatch
receipts are required before "candidate lift" means anything outside the fixture world; (b) the
governance-visible read-only report surface for scorecard + DPI receipts; (c) the cold-start
trace corpus seam (corpus only, no training — spec §7 of
`docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md`).

**Key design decision:** this node **owns trust-gate C2 closure** (§3.5) — the existence test
(`positive_lift_candidate` only if it beats `best_single_full_budget` at equal compute, with
significance) is exactly C2's claim made falsifiable.

### 2.2 Node 2 — Router / model-selection policy

The routing substrate already learns (`dharma_swarm/routing_memory.py:68` `RoutingMemoryStore`,
`lane_score` at `routing_memory.py:284`, `rank_candidates` at `routing_memory.py:343`; signal
extraction in `dharma_swarm/router_v1.py:138-317`), but nothing evolves the *policy* against a
frozen gradient — today it is online drift, unmeasured.

- **Frozen eval:** a sealed replay pack of historical dispatch outcomes — (task signature,
  candidate lanes, chosen lane, receipted outcome) tuples drawn from spine EvidenceReceipts
  (`dharma_swarm/spine/receipt.py`) post-D1. Frozen per epoch with a manifest hash, same
  discipline as `taskpack.py`; a policy is scored counterfactually on regret vs. the best lane
  the replay recorded. Held-out split: latest-week receipts are never in the training slice.
- **Mutation operator:** perturbations to the scoring weights and blend parameters that
  `RoutingLaneScore` (`routing_memory.py:54`) and `_blended_score` (`routing_memory.py:171`)
  expose — decay horizons, similarity thresholds (`_signature_similarity`,
  `routing_memory.py:202`), exploration bonuses — expressed as a policy genome, not code edits.
- **Diversity-preserving selection:** archive bins on policy behavior (lane-entropy of the
  induced routing distribution, exploration rate, provider-family spread) so the archive cannot
  converge on "always route to the strongest model" — that is skill-selection death and violates
  the Transcendence Principle's routing-by-specialty mandate.
- **Receipts:** every evaluated policy writes a replay scorecard (policy hash, replay-pack hash,
  regret, lane-entropy) under `~/.dharma/`; shadow comparison against the live policy via the
  existing `tiny_router_shadow.py` pattern before any policy is promoted to production defaults.

**Key design decision:** counterfactual replay on receipted dispatches — the gradient is real
outcomes the spine already recorded, so iteration is free (no API spend) and the signal cannot be
generated by the policy being scored.

### 2.3 Node 3 — Prompt / policy evolution via DarwinEngine (post-BR-003)

The engine exists (`dharma_swarm/evolution.py:266` `DarwinEngine`; archive wired at
`evolution.py:312` to `EvolutionArchive`, `dharma_swarm/archive.py:355`); BR-003's mechanism test
(one canonical run, `DHARMA_EVOLUTION_SHADOW=0`, rollback receipt) is track item 9, sequenced
LAST. Until then this node runs entirely in shadow.

- **Frozen eval:** the existing proposal-evaluation battery — tests + telos gate battery per
  `docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`, with `Proposal` targets
  (`evolution.py:96`) restricted to prompt/policy surfaces (agent prompt templates, policy
  configs), not arbitrary code. The eval set for a prompt variant is a frozen task slice scored
  by node 1's arena scorer — prompts are genes (spec §1 of the orchestrator spec: "a
  newly-ingested research technique is just a candidate gene").
- **Mutation operator:** `Proposal.change_type` mutation/crossover/ablation (`evolution.py:101`),
  gated hard as self-mod (`SELF_MOD_TYPES`, `evolution.py:149-168`; Tier-C REVIEW → hard REJECT
  in `gate_check`, `evolution.py:1466`).
- **Diversity-preserving selection:** `EvolutionArchive` over `MAPElitesGrid`
  (`archive.py:197`; diverse parent sampling via `get_diverse_parents` at `archive.py:260` and
  `sample_diverse` at `archive.py:281`). D6a consolidation makes this the ONE diversity ledger
  (`diversity_archive.py` retired/absorbed, doctrine §6).
- **Receipts:** archive entries with `FITNESS_BEARING_STATUSES` honesty (`archive.py:140-146` —
  shadow/gated/rolled_back are recorded as what they are, never laundered as "applied");
  Merkle-chain verification (`verify_merkle_chain`, `archive.py:641`); rollback receipts
  (`rollback_entry`, `archive.py:586`).

**Key design decision:** fitness entries accumulate in the archive under shadow NOW; standing
apply stays locked until D4 (§3.3). Selection pressure without apply authority is safe; apply
authority without external gradient is transcendence death with green dashboards (doctrine §5).

### 2.4 Node 4 — Memory promotion policy

What gets promoted into agent context is a policy choice with fleet-wide blast radius (the COLM
dead-calendar failure). `docs/architecture/MEMORY_FIRST_TOKEN_SPEC.md` §1 defines the evidence
classes this node optimizes over: `structural` (receipt-backed AND TTL-carrying — a derived
predicate, never operator-set) vs. `narrative` (everything else, depth-on-demand).

- **Frozen eval:** the shadow-canary comparison surface MEMORY_FIRST_TOKEN_SPEC §2 already
  specifies — paired completion-quality deltas between orderings/promotion policies on the same
  frozen task set, plus token-budget displacement (`narrative_chars_dropped`), scored with the
  arena's bootstrap-CI discipline. A promotion policy is a candidate answer to "which atoms, at
  which TTLs, cross into first-token"; the eval replays historical bundles + outcomes.
- **Mutation operator:** parameter mutations over the promotion gate
  (`dharma_swarm/memory_kernel/promotion_gate.py`, exported via `memory_kernel/__init__.py:75-89`
  — `build_promotion_decision`, `append_promotion_artifacts`, `load_promotion_status`): TTL
  floors, provenance-strictness, per-seat `k` in the k-of-n structural draw
  (MEMORY_FIRST_TOKEN_SPEC §4), admission caps (`MemoryContextBudget.max_admitted_atoms`).
- **Diversity-preserving selection:** the decorrelated-seat constraint is *structural*, not
  selected-for: per-seat sampling keyed on `stable_hash(agent_uid, task_id)` (spec §4) is a hard
  invariant every candidate policy must preserve — a policy genome that broadcasts identical
  first-token memory to worker seats is invalid, not merely low-fitness. Archive bins on
  (structural-share, TTL distribution, per-seat overlap coefficient).
- **Receipts:** canary metadata on the existing
  `bundle_metadata["memory_kernel_context"]` block (`context_compiler_shadow.py`), promotion
  artifacts via `append_promotion_artifacts`, and the C5-gate fixture check
  (MEMORY_FIRST_TOKEN_SPEC §5, amending `score_c5` at `trust_gate_status.py:316`).

**Key design decision:** evidence-class integrity is the fitness floor — a promotion policy is
scored on downstream task outcomes, but it can never earn fitness by widening what counts as
`structural` (the predicate is computed from provenance + TTL, closing the self-promotion vector).

### 2.5 Node 5 — Telos-gate calibration

Gates are tuned, **never removed** — the standing non-goal on both `loop-closure-2026-06` ("do
not weaken, bypass, or hard-code any telos gate to close a loop") and `organism-rewire-2026-07`
("do not weaken, remove, or bypass any telos gate or ratchet to wire an organ — gates are hardest
exactly when revenue/deadline pressure arrives"). This node calibrates thresholds against
outcomes; the gate *set* is constitutional.

- **Frozen eval:** replay of the witness log (`~/.dharma/witness/`, JSONL — the
  `TelosGatekeeper.check` audit trail, `dharma_swarm/telos_gates.py:237,408`) joined to eventual
  outcomes: for each historical gate decision, did the allowed action later produce a rollback /
  incident / BR entry (false ALLOW), or did the blocked action's equivalent later ship cleanly
  elsewhere (false BLOCK)? Scored as calibration curves — the same discipline as
  `ginko_brier.py` (`compute_brier_score` at `ginko_brier.py:199`, `compute_calibration` at
  `ginko_brier.py:244`), which is the repo's canonical aggregation-quality instrument.
- **Mutation operator:** threshold/trigger-pattern variants proposed through the existing
  variety-expansion protocol — `GateProposal` / `GateRegistry`
  (`telos_gates.py:66-128`): propose → S5 (Dhyana) review → approve. Calibration proposals ride
  the same lifecycle; **any loosening variant requires explicit operator ratification**, and
  gate-pressure telemetry (`_GATE_PRESSURE_PATH`, `telos_gates.py:385`) is an input, never an
  authority.
- **Diversity-preserving selection:** archive bins on (gate, tier, direction-of-change,
  false-ALLOW rate, false-BLOCK rate) — Pareto cells, not a single scalar, so "block everything"
  and "allow everything" both fail to dominate. Governance cost is priced in diversity
  (Transcendence Principle: System 2 damping > System 3 mandates).
- **Receipts:** every calibration evaluation writes a Brier/calibration scorecard against the
  witness replay; approved changes land as reviewed `GateProposal` records
  (`~/.dharma/meta/gate_proposals.jsonl`) with the evaluation receipt attached.

**Key design decision:** asymmetric authority — tightening can be earned from replay evidence
alone; loosening always crosses the S5/operator boundary. The node optimizes calibration error,
and it is structurally incapable of expressing "remove gate" as a mutation.

### 2.6 Node 6 — R_V / self-reference-attractor research lane

NORTH_STAR §2's measurable-awareness claim regains an owned, receipted eval loop after the COLM
calendar death. The map exists (`lodestones/seeds/self_reference_attractor.md`, SRA_001, P1-P5 =
EC-SRA-001…005) and the ladder exists
(`docs/research/self_reference_attractor/RESEARCH_PROGRAM.md` §1, Rungs 1-5 ordered by leverage,
Rung 1 = the lexical confound on EC-SRA-001). What died with the conference deadline was the
*loop*, not the program. **A receipted eval loop, post-COLM, means:** cadence owned by closure
checks instead of a calendar — each cycle runs one rung's pre-registered prediction against the
instruments (R_V/participation ratio, SAE probes, steering), updates the claim's status in
`foundations/EMPIRICAL_CLAIMS_REGISTRY.md` (SINGLE_STUDY → REPLICATED → VERIFIED, or PRUNED), and
emits a receipt whether the prediction landed or died. External venues become downstream
consumers of receipts, never the loop's clock.

- **Frozen eval:** the pre-registered prediction registry itself — a rung's prediction, controls
  (vocabulary-matched non-recursive per P1's open edge; shuffled-token per EC-0006), model roster,
  and analysis plan are hashed *before* the run. The falsification ledger (SRA_001 §3.3) is the
  held-out discipline: predict-the-unknown-and-land-it counts; re-describe-the-known is pruned.
- **Mutation operator:** the Depth 2-3 protocol of SRA_001 §6 — each status change re-synthesizes
  the map and generates the next cycle's candidate predictions; experiment variants (prompts,
  layers, steering vectors, architectures) are the mutable genome.
- **Diversity-preserving selection:** the registry keeps pruned predictions on the ledger
  (integrity comes from the pruning — SRA_001 §3.3); rung selection follows the
  RESEARCH_PROGRAM leverage ordering, and cross-architecture replication (EC-0001's six-family
  spread) is itself the diversity axis — a claim VERIFIED on one family is binned separately
  from one verified across families.
- **Receipts:** the existing archive seam is already built for this —
  `research_reward_to_fitness()` (`dharma_swarm/archive.py:74-105`) projects a research
  grade-card (groundedness, contradiction-handling, gate failures) into an archive-compatible
  `FitnessScore`. Each cycle emits: pre-registration hash, run artifacts, registry status diff,
  and the projected fitness entry (shadow-status until D4, like every node).

**Key design decision:** the gradient is *falsification survival*, not publication — the node's
fitness signal is the ledger's prediction-survival rate under pre-registration, which no internal
narrative can inflate, and its cadence is closure-check-owned so no external calendar can kill
the loop again.

---

## 3. Cross-cutting law

### 3.1 Benchmark rotation and held-out discipline

Frozen does not mean eternal. Per node, per epoch: (a) the scored slice is frozen and hashed
(node 1's `task_manifest_hash` + `sealed_oracle_hash` pattern is the template; the curator may
expand candidates but never the frozen slice — `arena/curator.py:29-36`); (b) epoch rotation
retires a fraction of the slice into a **held-out reserve** scored only at promotion time, never
during iteration (`curator.py:38` `promote_next_epoch` is the seam); (c) a candidate that wins
the working slice but regresses on the reserve closes out `inconclusive_low_power`, not
`positive_lift_candidate`. A node whose working slice has been iterated against for more than
one epoch without rotation is stale — its outputs stop feeding §3.3 until rotated.

### 3.2 The One Wire quorum — the only archive-fitness entrance

Invariant (loop-closure track, standing): **internal artifacts never touch archive fitness; only
countersigned external acted receipts above quorum do** — N ≥ 5 confirmed receipts, M ≥ 3
domains, transfer-aware gate execution
(`docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md` §6: Measurement Guardian cycle 3 blocked
at N=3/M=1; the quorum guard is read at `dharma_swarm/cybernetics_codex.py:561-622`). Everything
the six nodes produce is *internal* in One Wire terms: arena scorecards, replay regret, canary
deltas, calibration curves, even VERIFIED registry claims. They steer **selection within the
archive** (parent choice, cell admission); they never constitute the external-fitness authority
that Forge/Hydra stopped honestly waiting for. This portfolio is the lawful restart path for
Dharma Forge (doctrine §4): external receipts are the only permitted quorum feed.

### 3.3 Feeding DarwinEngine without unlocking standing apply (D4 sequencing)

Node outputs land as `FitnessScore` entries (`archive.py:108`) in `EvolutionArchive` with honest
statuses (`FITNESS_BEARING_STATUSES`, `archive.py:140`) while `DHARMA_EVOLUTION_SHADOW` stays at
its default `"1"` (`dharma_swarm/dgm_loop.py:289`). Selection — which parents to mutate, which
cells to explore — may consume node gradients immediately. **Apply** authority is D4: one
canonical mechanism test with rollback receipt first, standing unlock only after D1's receipt
stream and this portfolio provide ungameable selection signal (track item 9; doctrine §5: "apply
unlocked against internal benchmarks = Goodhart convergence = diversity-term collapse"). No node
in this spec may cite its own maturity as grounds to accelerate D4.

### 3.4 Iteration volume and cost envelopes (initial; revise per receipts)

| node | iteration substrate | volume target | marginal cost envelope |
|---|---|---|---|
| 1 arena | hermetic fixtures / live arms | 10²-10³ hermetic runs/day; live arms budget-capped per epoch | hermetic ≈ $0; live arms ≤ parity budget, operator-set cap |
| 2 router | receipt replay | 10³ policy evals/day | ≈ $0 (replay only) |
| 3 darwin | shadow proposals | 10-50 proposals/day | test-runner compute only |
| 4 memory | bundle replay + shadow canary | 10² policy evals/day | ≈ $0 (shadow) |
| 5 telos | witness-log replay | full-log replay per calibration cycle (weekly) | ≈ $0 (replay) |
| 6 R_V | GPU experiment runs | 1 rung cycle / 1-2 weeks | GPU-hours per rung, operator-provisioned |

The doctrine's economics: benchmark loops iterate at volume; market P&L funds but never selects
per-iteration (doctrine §4). Replay-based nodes (2, 4, 5) are deliberately near-zero-cost so
iteration volume is never hostage to the funding gradient.

### 3.5 What closes trust-gate C2, and who owns it

C2 = "swarm scores higher than single models on coding benchmarks"
(`trust_gate_status.py:46`; published bar: DGM 20%→50% SWE-bench / 14.2%→30.7% Polyglot,
arXiv:2505.22954 — whose winning mechanism, an archive of diverse stepping stones, is this
portfolio's own doctrine). `score_c2` (`trust_gate_status.py:159-175`) reads a measured
`swarm_lift`/`cost_normalized_lift` value from the newest `reports/anatomy_*/` audit
(`_LIFT_RE`, `trust_gate_status.py:142`). **Node 1 owns C2 closure**: a `positive_lift_candidate`
closeout from a **live-arm** arena run (real dispatch, real receipts, budget parity logged,
best-single gate beaten with significance, held-out reserve clean) is written as the
`cost_normalized_lift = <value>` line into a dated `reports/anatomy_*/` report so C2 flips from
unmeasured to measured. A hermetic-fixture lift never closes C2 — that would be the arena grading
its own homework (arena non-goal: no production capability claims without budget-parity controls
and significance gating).

---

## 4. Anti-Goodhart appendix — gaming modes and structural countermeasures

**Node 1 — arena.** (a) *Frozen-slice memorization across epochs* → epoch rotation + held-out
reserve (§3.1); `sealed_oracle_hash` pins label drift. (b) *Budget theater* — beating best-single
by outspending it → parity is enforced and logged per arm (`runner.py:288-299`); over-parity lift
is not lift. (c) *Fixture-world lift claimed as capability* → C2 requires live arms (§3.5);
contamination tripwire (`taskpack.py:136`) quarantines label-peeking, and quarantined genomes are
never archivable (`orchestrator_v1.py:57-61`).

**Node 2 — router.** (a) *Workload self-selection* — the policy routes toward tasks it scores
well on → eval is a frozen replay pack the policy cannot influence. (b) *Outcome inflation* —
counting unreceipted successes → only spine EvidenceReceipts are admissible replay rows (D1
standing). (c) *Monoculture collapse* — always-route-to-strongest → lane-entropy is an archive
bin dimension, so low-entropy policies compete only against each other, never displace the
diverse cells.

**Node 3 — darwin.** (a) *Fitness laundering* — internal metrics dressed as outcomes → honest
statuses (`FITNESS_BEARING_STATUSES`) + One Wire boundary (§3.2). (b) *Test weakening* — a
proposal that edits its own eval → eval surfaces are sealed out of the mutable target set; gate
battery hard-rejects self-mod on advisory REVIEW (`evolution.py:1466`, WS4). (c) *Archive
flooding* — many trivial variants to occupy cells → MAP-Elites admission requires beating the
cell incumbent, and lineage (`genome.py:82`) makes flood ancestry auditable.

**Node 4 — memory.** (a) *Evidence-class inflation* — narrative facts claiming structural status
→ `evidence_class` is a computed predicate over provenance + enforced TTL, never stored/asserted
(MEMORY_FIRST_TOKEN_SPEC §1). (b) *Circular provenance* — a fact citing an artifact the same
policy promoted → provenance must resolve to an EvidenceReceipt/logged event outside the memory
system. (c) *Retrieval overfit* — winning the replay set by hoarding its specific facts →
held-out bundle replay + the displacement metric (narrative starvation fails promotion).

**Node 5 — telos gates.** (a) *Pressure-driven loosening* — calibrating toward permissiveness
because throughput rewards it → loosening mutations cannot self-approve; S5/operator ratification
is in the lifecycle, not policy (§2.5). (b) *Outcome-label gaming* — classifying incidents so
false-ALLOWs vanish → outcome joins use owned surfaces (BROKEN_REGISTER, rollback receipts), not
node-local labels. (c) *Calibration monoculture* — one scalar objective collapsing block/allow
trade-offs → Pareto-binned archive, no single fitness scalar exists to descend.

**Node 6 — R_V lane.** (a) *Post-hoc re-description* — "predicting" known results →
pre-registration hash before the run; re-described knowns are pruned by ledger rule (SRA_001
§3.3). (b) *Vocabulary confound* — spiritual lexicon driving the signal → mandatory
vocabulary-matched non-recursive + shuffled-token controls (EC-0006; P1's open edge is the
node's Rung 1). (c) *Survivorship curation* — quietly dropping failed predictions → PRUNED is a
permanent ledger status with its own receipt; the survival-rate denominator includes every
pre-registered prediction.

---

## Non-goals (inherited; restated)

- Does not unlock DarwinEngine standing apply, change `DHARMA_EVOLUTION_SHADOW` defaults, or
  reorder D4 (§3.3).
- Does not let market P&L act as per-iteration selection signal anywhere in the portfolio.
- Does not weaken, remove, or bypass any telos gate or ratchet; node 5 calibrates thresholds only.
- Does not let internal artifacts (any node's scorecards) touch archive fitness — One Wire quorum
  stands (§3.2).
- Does not make production capability claims from hermetic runs; C2 closes only on live-arm
  evidence (§3.5).
- Does not create new truth stores, receipt systems, or a second diversity ledger — extends
  `EvolutionArchive`/`MAPElitesGrid`, the spine receipt stream, and existing owner surfaces.
