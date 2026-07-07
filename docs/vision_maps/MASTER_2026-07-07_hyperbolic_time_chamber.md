# THE HYPERBOLIC TIME CHAMBER — Inward Ascent Doctrine, Audit Record & Campaign Seal

**Role:** canonical (vision/doctrine synthesis) — operator-ratified 2026-07-07, by explicit declaration in the sealing dialogue. Operator-authored via full-day dialogue, 2026-07-07.
**Authority:** subordinate to [`NORTH_STAR.md`](NORTH_STAR.md) and `docs/governance/SOVEREIGN_MANIFEST.md` §Telos Hierarchy. This file owns no rules and no state; it braids with `docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md`, `docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md`, and `CYBERNETIC_LOOP_MAP.md`.
**Source of words:** the operator (John / Dhyana), dialogue of 2026-07-07, with a same-session zero-trust audit (three decorrelated verification agents + live command runs). Nothing below is agent-invented doctrine; every audit claim carries a file:line or command receipt from that session.
**Rule:** if this file disagrees with `make onboard`, `docs/governance/ACTIVE_TRACK.yaml`, or any receipt, trust those. This file is the *why and the shape*; the owners hold the truth.

---

## 0. The Name

The Hyperbolic Time Chamber (精神と時の部屋, "Room of Spirit and Time") is where
Goku and Gohan trained before the Cell Games: **one day outside equals one year
inside** — a sealed, featureless void with denser gravity, entered deliberately
to compress an order of magnitude of growth into the time available before a
fight that has not started yet.

The metaphor carries its own warning, and the warning is doctrine: **the door
can vanish if you overstay.** The chamber is sacred only because it has an
exit. Here, the exit is NORTH_STAR §8's trust gate, and §5 below keeps the
door visible.

**The one-line program:** seal the efferent edge, open the afferent edge wide,
and evolve at machine speed against imported and time-lagged reality until the
trust gate opens on measured numbers — then walk out an order of magnitude
stronger, with a rehearsed corpus of world-facing actions ready to release.

---

## 1. Why This Exists — the audit that forced precision (2026-07-07)

An operator-initiated zero-trust audit ("assume nothing the docs say is true")
ran three decorrelated verification agents plus live command execution against
the repo at HEAD `665c90c`. Findings, each receipted in-session:

- **F1 — Zero loops close live; harness closures largely eat self-made inputs.**
  0/13 loops CLOSED_LIVE (the repo's own honest claim boundary). The 11
  HARNESS_PROVEN loops run real component code through a mechanically-checked
  sense→interpret→constrain→act→adapt cycle — but Loop 7's training
  trajectories are 100% fabricated (`scripts/loop7_*closure_run.py`
  `_seed_trajectories`), Loop 4 "senses" its own harness script as the
  completed work, Loop 8 closes over sibling harnesses' receipts, Loop 5
  senses its own self-generated gate pressure, and Loop 1 (the most real:
  live Ollama through the real orchestrator into canonical runtime.db) proves
  only the adapt **write** (stigmergy marks deposited), not the adapt **read**
  (`stigmergy_hot_paths: []`). The internal red-team council (PR #749)
  reached the same verdict and held the closure claim.
- **F2 — The flagship track's green checkmarks were structurally rubber-stampable.**
  loop-closure-2026-06: 1 of 29 criteria truly rigorous (one live pytest);
  the rest existence checks or structural reads of **digest-free,
  hand-writable JSON receipts** (`expect_digest` implemented in
  `check_track_status.py` but enabled for only 1 of 16 receipt checks
  repo-wide). The onboard "TRUST CHECK ✓" re-renders a cached JSON — zero
  independent verification. `pr_merged` fails open without `gh`.
  By contrast: `test_passes` genuinely spawns pytest, `commit_on_main`
  genuinely checks git ancestry, dharmagraph scores 5/7 rigorous.
- **F3 — The transcendence thesis is currently measured FALSE in-house.**
  Trust gate C2 = 0.05 RED: last real measurement shows swarm lift **−0.1**
  vs. its own best single seat (`reports/anatomy_altitude_2026-06-10/`).
  The math (Krogh-Vedelsby, Condorcet, Zhang 2024) is sound *given its three
  conditions*; the measurement says at least one condition fails in current
  wiring. The trust gate is closed: C1 0.70 AMBER, C2–C5 RED
  (fresh `trust_gate_status.py` run, 2026-07-07).
- **F4 — The sense organs are a radar, not a mouth.** `world_scout_go` has
  real live-fetch code (HN Algolia, Reddit, arXiv, GitHub search, vendor news
  pages) and a genuinely well-tuned 11-beat research list, plus a coded
  source-weight feedback loop (`world_radar/analysis.py`
  `update_source_weights_from_opportunities`). But: observations are
  title/description/URL only (archive/full-text mode off), ~12 keyword-query
  feeds, live closure only ever proven on fixtures, cron layer split-brained
  (BR-004), and bronze landings have no verified decision-time consumer.
  **Sensing without metabolizing is hoarding.**
- **F5 — No comparative world-model exists.** Nothing machine-maintained
  answers "our measured number vs. the field's published number, per
  capability." NORTH_STAR §10 is hand-curated and frozen at June.
- **F6 — Governance drift at the edges.** Two recent multi-commit campaigns
  (forge safety suite; telos-kernel/titanium-verify) landed on `main` with no
  owning track. `docs/state/BROKEN_REGISTER.md`'s layout shows FIXED items in
  the open region (the register, not the maps, is the false-signal surface).
  BHED_GNAN hard-passes (`telos_gates.py:538`) — the most doctrinally central
  gate is inert (BR-014).
- **F7 — What survived the audit intact:** the claim-boundary honesty
  (HARNESS_PROVEN vs CLOSED_LIVE), the enforced ship-veto blocking live-ship
  while loops sit at HARNESS_PROVEN, the red-team culture, CLAUDE.md's
  generated portfolio (matches ACTIVE_TRACK.yaml exactly), all five tracks
  within TTL, and 12,600+ collected tests. **The system's own instruments
  found every problem first.** That reflex is the moat.

**The diagnosis in one line:** the organism has a complete nervous system and
no world — a fully-instrumented engine that has never been left running,
whose loops, when they do run, are pointed at a mirror.

---

## 2. The Doctrine — afferent-open, efferent-closed

### 2.1 Three classes of signal (the distinction that dissolves the mirror)

1. **Self-manufactured** — the system's outputs fed back as its inputs
   (Loop 4/7/8 today). Worthless as a gradient; evolution against it is
   Goodhart-death. **Banned as a fitness source.**
2. **Imported-external** — public benchmarks, real corpora, own *historical*
   production data, differential oracles, time-lagged reality grading.
   Not the market, but not us either: genuinely external variety pulled
   inside a sealed room. **The chamber's food. Massively underexploited.**
3. **Live-world** — customers, countersigned acted receipts, revenue.
   The ultimate signal; slow, noisy, expensive per bit today. **Deferred
   by design until the door opens — except as read-only ingest and as
   time-lagged graders.**

Precedent that class 2 carries mad evolution: DGM 20%→50% SWE-bench with zero
deployment (arXiv:2505.22954); AlphaEvolve/FunSearch; every self-play system
back to AlphaZero. Karpathy's thesis — the bottleneck is environments and
evals, not weights — is this doctrine stated from the other side.

**"Not world-facing" must never mean "world-closed."** Ingestion is world
contact, afferent only: the world flows in, nothing flows out. An embryo with
working sensory nerves.

### 2.2 The one-man math (why the chamber is the only winning shape)

The scarcest resource is not agents, compute, or ideas — it is **operator
ratification bandwidth**. Every loop needing human review runs at human
speed, which is the same speed the giants run at: no edge. The only way one
man compounds faster than an organization of thousands is **delegating trust
to scorers instead of eyes**. An ungameable scorer is a piece of the
operator's judgment crystallized into an executable that runs 10,000 times a
night unattended. The chamber is not "simulation for practice" — it is
**operator attention, crystallized into scorers, compounding while he sleeps.**

### 2.3 The asymmetry against the giants

Palantir-class incumbents cannot be out-spent; they can be out-**digested**
and out-**cycled**. (a) Their R&D exhaust is free gradient: papers, release
notes, benchmark results — a system that metabolizes their publications into
scored patches within days converts their billions in research spend into our
evolution fuel. (b) Their improvement loop runs in quarters through org-chart
friction; a sealed chamber closing honest learn-loops daily wins on loop
latency, compounding. **You don't beat billions in capital; you beat months
in cycle time.**

### 2.4 Consistency with existing canon

- NORTH_STAR §8's trust gate C2 ("swarm beats single models on coding
  benchmarks") is a class-2, chamber-phase goal — the trust gate was designed
  for an inward-first path before this doctrine named it.
- THE_ORGANISM's needle ("being that strengthens the body for doing") is
  honored by §5's exit criteria: inward motion here has a telos, a scoreboard,
  and a door.
- The organism-rewire external-gradient portfolio item already ratified
  "verified benchmarks for high-iteration autoresearch loops" as a legitimate
  gradient class. The chamber is that item, given a body and a name.
- One Wire stands untouched: chamber gradients drive autoresearch loops;
  **archive fitness for self-modification still requires the external quorum
  (N≥5, M≥3).** That firewall is what makes aggressive internal evolution
  safe. `DHARMA_EVOLUTION_SHADOW=1` and the BR-003 apply-gate sequencing are
  unchanged by this program.

---

## 3. The Chamber Architecture

### 3.1 The Mouth — ingest metabolism (radar → digestion)

Keep the radar; build the mouth. Substrate that already exists dark:
`tools/{world_scout,world_signal_ingestor,github_ingestor,evidence_ingestor}_go`,
`dharma_swarm/world_radar/` with a bronze landing layer (`bronze.py`; live
HN/Algolia fetcher coded), the source-weight feedback loop, and cron entries
("World Scout", "Scout Sweep — All Domains" 01:00, "Signal Deep Sweep").

**Landing path (doctrine, no new truth stores):** Go organs → bronze
(receipted raw, quarantine zone) → **Chetana ingest→stage→gate→promote** →
MemoryKernel / ontology as promoted stores.

**Source classes (all four ratified by the operator, 2026-07-07):**
- **Code-world:** GitHub repos/issues/PRs in our domains, model releases,
  benchmark leaderboards, agent-framework repos (langgraph, openhands,
  swe-agent, aider…). Feeds the gym and self-understanding directly.
- **Knowledge-world:** arXiv (agents/mech-interp/evolution beats), Wikipedia/
  Wikidata slices, IETF agent-trust drafts. Fills ontology and MemoryKernel
  with durable structured knowledge.
- **Zeitgeist:** HN (fetcher exists), RSS, curated feeds. Cheapest to light;
  gives Loop 5 something real to sense.
- **Market data:** Ginko's lane. Funding-signal and slow-horizon term ONLY;
  never per-iteration selection (standing doctrine).

**The metabolism upgrade (what "high quality" means):** full-text archive
mode ON (papers actually read, PDF → structured extract), depth sources
(leaderboards, release notes, targeted repos cloned and indexed), entity
resolution into the ontology, provenance tags on every promoted fact,
retention/decay via Chetana's existing decay machinery, litestream-replicated
state. Extend the source-weight feedback pattern (sources graded by
downstream usefulness) as the native quality control.

**THE DEMAND-DRIVEN RULE (hard):** no ingest source is turned on without a
**named consumer loop and a scorer that moves when the data arrives.**
Supply-driven ingestion is the mirror trap wearing a new mask — data hoarding
feels like progress and is inert. A bronze-consumption closure check makes
hoarding visible: landed-but-never-consumed volume is a reported number.

**THE IMMUNE SYSTEM (hard):** eating the world at scale means swallowing
prompt injection and data poisoning. Bronze is a quarantine zone; ingested
content is **data, never instructions**; sanitization at the Chetana gate;
AHIMSA/SATYA screening at the ingest boundary; provenance travels with every
fact; no ingested text is ever interpolated into an agent's instruction
stream unlabeled.

### 3.2 The Gym — the environment battery

Evolution rate = **iterations × scorer quality × survivable delegation**.
Environments are frozen, verifiable, decorrelated — from each other and from
the RSI/arena lab already running on the operator's Mac + maharaja VPS
(diversity of environments is the same doctrine as diversity of agents).

Candidate battery (spec 3–4 first; justify by decorrelation, scorer
ungameability, iteration cost):

| # | Environment | Gradient source | Scorer | Notes |
|---|---|---|---|---|
| 1 | **Runtime-history replay** | ~8.8k real delegation_runs in runtime.db (4,184 completed / 4,532 failed) | Off-policy evaluation vs. actual historical outcome | Richest untapped REAL signal; directly evolves Loop 1's adapt-READ edge; zero fabrication |
| 2 | **Git-history repo gym** | Own repo (+ ingested external repos) | The tests that actually landed with each real merged fix | Infinite free SWE tasks; no benchmark contamination |
| 3 | **Forecasting gym** | Zeitgeist/market ingest → resolvable near-future facts | Brier via `ginko_brier` when reality resolves | Time-lagged reality grading — the world grades us with zero exposure |
| 4 | **Retrieval/memory gym** | Ingested corpora → verifiable QA pairs | Exact retrieval hit | Evolves MemoryKernel promotion + context order = the C5 fix as an environment |
| 5 | **Gate red-team self-play** | Generated violating actions vs. gate battery | Catch-rate on held-out attack corpus | Calibrates inert gates (BHED_GNAN via `GateRegistry.propose()`); feeds Loop 5 |
| 6 | **Ontology gym** | Knowledge-world ingest graph | Held-out link prediction vs. Wikidata ground truth | Evolves the Palantir-style semantic layer |
| 7 | **Self-model gym** | Own diffs | Predict which tests fail; scorer runs them | "Does the organism know itself," as a number; real signal for Loop 8 |
| 8 | **Differential-oracle expansion** | Reference implementations | Dual-run semantic diff (langgraph-oracle pattern, generalized) | Hermetic, deterministic, cheapest iterations |
| 9 | **Paper-to-patch pipeline** | arXiv ingest | Gym delta of the reimplemented method | Highest ceiling: the field's R&D becomes our mutation operator |
| 10 | **Time-lagged external PR gym** | Open issues on active OSS repos | Similarity to the maintainer's eventual merged fix | Submit NOTHING; reality grades our code for free |
| 11 | **Shadow efferent mode** | Every future world-facing action class | Internal gates + panel scoring; archived, never sent | The efferent muscle builds under quarantine; release corpus for door-opening day |
| 12 | **Trace distillation** | Own delegation traces | Distilled local model's gym scores | Drops iteration cost toward zero — what makes 10,000x arithmetic |
| 13 | **Digital-twin chaos gym** | Simulated daemon (extends `graph/effects.py` injectable clock/rng/dispatch) | Survival/recovery invariants under kill/corrupt/starve | Robustness evolved before the VPS sees load |
| 14 | **Benchmark-forge** | Ingested task-shaped artifacts | Auto-generated verifiable benchmark items | The self-eval organ, finally fed; grows the gym from world material |
| 15 | **Public coding benchmarks** | SWE-bench-verified / Polyglot | Published harness | The DGM path and the literal C2 bar; needs compute + strict held-out discipline |

**Excluded here by boundary:** the hermetic arena / RSI lab (Mac + maharaja
VPS) — sibling program, disjoint surfaces, shared receipt format (§3.7).

### 3.3 The Flywheel

**Ingest feeds the forge (14) → the forge grows the gym → the gym runs on
distilled seats (12) → scores flow to the Frontier Ledger (§3.4) → the ledger
prices readiness → the shadow corpus (11) accumulates rehearsed action →
the door (§5) opens on numbers.** Every 01:00 cron cycle leaves the system
measurably better, with operator attention spent only on ratifying dossiers
and reading one ledger page.

### 3.4 The Frontier Ledger (the database the operator asked for)

A machine-maintained owned surface answering, per capability: **our measured
number** (from gym receipts) vs. **the field's published number** (from
ingest: leaderboards, papers, release notes), delta, trend, receipt URLs.
Replaces hand-curated NORTH_STAR §10 as the living instrument; gives trust
gate C2 a live denominator; renders as one page. **This is how "are we ready
to move in the world?" becomes a number instead of a feeling.**

### 3.5 The 10x Baseline Scoreboard

The operator's ratchet — "every dimension 10x before we move" — requires a
day-one baseline or "10x" is a feeling. One receipted, re-runnable
measurement per surface: ingest volume/quality, ontology coverage, memory
hit-rate, gate catch-rate, routing regret vs. history, self-model accuracy,
forecast Brier, distilled-seat cost-per-iteration. Digest-stamped receipts
(F2's hole is not recreated — `expect_digest` on everything new).

### 3.6 Implementation substrate — the polyglot shell doctrine (operator ruling, 2026-07-07)

The chamber is a **shell plus trainees**, and the metaphor is the
architecture: the shell provides the gravity and time-dilation (sandboxing,
resource caps, deterministic replay, receipt hashing, high-iteration
scheduling); the trainees inside do the growing. Rulings:

- **The environment protocol is language-agnostic by construction.** An
  environment is a process that speaks JSONL receipts across a narrow
  boundary — the pattern the Go organs already prove (`go_invoke.py`:
  toolchain-checked invocation, structured errors, never an exception into
  the caller). Environments may therefore be Python, Go, Rust, or C++
  interchangeably from day one.
- **Python stays the composition root.** Telos gates, the spine, Chetana,
  and receipt ownership remain Python-owned; no gate or truth-store logic
  is ever reimplemented in another language (that would be a second owner).
- **Rust/C++ is earned, not defaulted.** The chamber's bottleneck is LLM
  inference and scorer quality, not CPU; every added language is a
  toolchain, CI lane, and context tax on a one-man operation. A Rust shell
  component is justified where it genuinely pays: (a) the **sandbox jail**
  for executing untrusted evolved code (process isolation, seccomp-class
  caps — safety-critical), (b) **hot scoring kernels** once a specific
  environment measures as iteration-bound rather than inference-bound
  (e.g., replaying millions of runtime-history rows), (c) digest/Merkle
  receipt chains at volume. No big-bang rewrite; carve per component with
  the same narrow-boundary contract as the Go organs.

### 3.7 Boundary with the RSI Lab (sibling program)

The RSI/arena lab on the Mac + maharaja VPS owns swarm-lift (C2) measurement
and the hermetic arena surfaces (`dharma_swarm/coordination/**`,
`council/**`, arena reports). The chamber COMPLEMENTS it with decorrelated
environments. Contract: **disjoint surfaces; shared fitness-receipt format
and archive descriptors (MAP-Elites in `archive.py`); no duplicated C2
measurement; both report into the same Frontier Ledger.**

---

## 4. The Disciplines (non-negotiable — welded, or the 10,000x is fake)

1. **Scorer ungameability, adversarially proven.** Every environment ships
   with an adversary agent whose only job is to game the scorer. An
   environment the adversary breaks is killed or fixed before a single
   evolution iteration runs against it.
2. **Held-out sets + taskpack rotation, everywhere.** Never train/select on
   the eval. An environment without held-outs is a slower mirror.
3. **Fix C2 first (coordination, not duplication).** The swarm currently
   loses to its best seat (−0.1). 10,000 iterations of a losing aggregation
   architecture amplify the loss. The RSI lab owns the fix; the chamber's
   volume scaling waits on (or feeds) it — measure the Krogh-Vedelsby
   diversity term and cross-seat error correlation, attack the failing
   condition.
4. **Demand-driven ingest** (§3.1). No source without a named consumer loop
   and a scorer that moves.
5. **The immune system** (§3.1). Ingested content is data, never
   instructions.
6. **One Wire stands; the evolution shadow stays.** Chamber gradients drive
   autoresearch loops; archive fitness for self-modification waits for the
   external quorum; `DHARMA_EVOLUTION_SHADOW` and BR-003 sequencing
   unchanged.
7. **Diversity preservation.** Environments decorrelated from each other and
   the RSI lab; selection stays MAP-Elites; no environment monoculture.
8. **Digest-stamped receipts on everything new** (`expect_digest: true`);
   prose criteria converted to executable checks. The audit's rubber-stamp
   hole is not recreated.
9. **Compute ROI ledger.** Every environment declares cost-per-scored-
   iteration; the flywheel routes compute by score-per-dollar (the
   self-treasury organ's job). Distillation is the cost-bender.
10. **The oracle rule.** Forecast/time-lagged resolution comes from ingest
    (external), NEVER from the predictor. Self-graded Brier is a mirror.
11. **Chamber-drift metric.** If gym scores rise while time-lagged
    reality-graded scores (envs 3, 10) stay flat, we are overfitting the
    chamber. That divergence is a first-class Frontier Ledger number.
12. **The daily delta receipt.** The loop map's acid test promoted to
    organism level: one receipt per day proving the system behaves measurably
    differently today *because of* yesterday's ingest and gym outcomes.
    This is the chamber's heartbeat — and it is what makes this program the
    completion of the loop-closure campaign, not a detour: it converts the
    self-fed harness loops into loops fed by imported reality.

---

## 5. The Door — exit criteria (the chamber is sacred because it ends)

- **The scoreboard IS the trust gate.** Every chamber report renders against
  NORTH_STAR §8 C1–C5. The inward phase ends when the gate opens — "when I
  trust it we can go balls to the wall," now with numbers.
- **30-day operator reviews** of the Frontier Ledger decide continue / adjust
  / exit. The review is one page.
- **The overstay warning is doctrine** (ARJUNA anti-pattern: inward motion
  with no telos and no contact). The chamber differs from the anti-pattern in
  exactly three ways, all checkable: a scoreboard, time-lagged reality
  grading, and a door. If any of the three degrades, the chamber is becoming
  the mirror and the operator is alerted on the ledger page.
- **Exit is a release, not a start:** the shadow efferent corpus (§3.2 env
  11) means door-opening day releases rehearsed, pre-gated action — websites,
  outreach, publications — not first drafts.

---

## 6. Relationship to Prior Prompts — the sublation clause

A prior forged prompt ("Inward Ascent: Massive Ingest + Simulation Gym
Campaign", 2026-07-07, earlier in the same dialogue) was already dispatched
to another agent instance. **This document and §7's seal SUPERSEDE it in the
Hegelian sense — everything in it is preserved, nothing is contradicted, and
it is lifted into this larger shape.** Any instance executing the seal MUST
first locate and absorb sibling outputs (a Phase-0 dossier draft, an opened
track, ingest-map fragments) rather than duplicate them: check
`docs/plans/`, `docs/governance/ACTIVE_TRACK.yaml`, and recent branches/PRs
for Inward-Ascent artifacts before writing a line. Additions unique to this
seal relative to that prompt: the name and exit doctrine (§0, §5), the
immune system, the compute-ROI ledger, the oracle rule, the chamber-drift
metric, the daily delta receipt, the Frontier Ledger as mandatory Phase-0
deliverable, envs 9–15, and the RSI-lab boundary contract.

---

## 7. THE SEAL — master prompt for the executing instance

```markdown
# MASTER PROMPT — The Hyperbolic Time Chamber (dharma_swarm)

## Role & target agent
Claude (fresh repo session, full tool access) on
AmitabhainArunachala/dharma_swarm. Operator (John/Dhyana) holds all
ratification authority. Run `make onboard` first; trust its output over any
doc, including this prompt. Read
docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md in full —
it is this prompt's doctrine and context; NORTH_STAR.md is its authority.

## Goal
Build the Hyperbolic Time Chamber: afferent-open / efferent-closed massive
internal evolution. Light the ingest metabolism (radar → mouth), stand up a
decorrelated gym battery with adversarially-proven scorers, wire
high-iteration autoresearch loops, and render the Frontier Ledger + 10x
Baseline Scoreboard — so the organism compounds nightly while the operator
spends attention only on dossiers and one ledger page. Phase 0 ships a
dossier; build begins only after operator ratification.

## Sublation clause (do this FIRST)
A sibling instance may hold the earlier "Inward Ascent" prompt (2026-07-07).
Before writing anything: search docs/plans/, ACTIVE_TRACK.yaml, and recent
branches/PRs for its outputs (dossier drafts, opened tracks, ingest maps).
Absorb and extend — never duplicate, never contradict. This prompt preserves
and supersedes that one.

## Inferred assumptions (correct if wrong)
- Class-2 signal only (imported-external: benchmarks, corpora, own runtime
  HISTORY, time-lagged reality grading). Self-manufactured signal is banned
  as a gradient (the 2026-07-07 audit's mirror finding).
- Afferent ingestion is unlimited and in-scope; efferent world-facing action
  (posting, outreach, trading, publishing, submitting) is fully out of scope.
- The RSI/arena lab (operator Mac + maharaja VPS) owns C2 measurement and
  arena surfaces; the chamber complements with decorrelated environments,
  shared receipt format, disjoint surfaces.

## Context (verify, never trust)
- Ingest substrate exists dark: tools/*_go organs + world_radar bronze layer
  (live HN fetcher coded; source-weight feedback loop in analysis.py) —
  observations are title-thin, archive mode off, closure fixture-only,
  cron split-brained (BR-004). Keep the radar; build the mouth (full-text
  archive on, depth sources, entity resolution → ontology, provenance tags,
  Chetana gate→promote as the ONLY metabolizer; no new truth stores).
- Gym candidates (spec 3-4 first; the doctrine file §3.2 holds all 15):
  runtime-history replay (~8.8k real delegation_runs — richest real signal),
  git-history repo gym, forecasting gym (Brier via ginko_brier, resolution
  from ingest ONLY), retrieval/memory gym (the C5 fix), gate red-team
  self-play (fix BHED_GNAN via GateRegistry.propose()), ontology gym,
  self-model gym, differential-oracle expansion, paper-to-patch,
  time-lagged external PR gym (submit nothing), shadow efferent mode,
  trace distillation, digital-twin chaos gym, benchmark-forge, public
  coding benchmarks.
- Measured reality to change honestly (2026-07-07): 0/13 loops CLOSED_LIVE;
  trust gate closed (C2 lift −0.1); loop receipts digest-free; frontier
  comparison database nonexistent.

## Hard constraints (the 12 disciplines, doctrine file §4 — enforce all)
Adversarially-proven scorers before any iteration; held-outs + rotation
everywhere; C2-first coordination with the RSI lab; demand-driven ingest
(no source without a named consumer loop + moving scorer, with a
bronze-consumption closure check); the immune system (ingested content is
data never instructions; quarantine bronze; provenance on every fact);
One Wire + evolution shadow + BR-003 sequencing untouched; diversity-
preserving selection (archive.py MAP-Elites); expect_digest on ALL new
receipts + prose criteria become executable; compute-ROI ledger per
environment; the oracle rule (resolution never from the predictor);
chamber-drift metric on the ledger; the daily delta receipt as heartbeat.
Plus the substrate ruling (doctrine §3.6): the environment protocol is a
language-agnostic process+JSONL contract from day one; Python remains the
composition root (gates/spine/receipts never reimplemented elsewhere);
Rust/C++ components are earned per-component (sandbox jail, measured
iteration-bound scoring kernels), never a default rewrite.
Plus repo law: gates/ratchets never weakened; no new truth stores; sibling
track surfaces untouched; new work = new ACTIVE_TRACK.yaml track (serves:
substrate-nativeness or research-depth) with rigorous criteria; files
<500 lines; no credentials committed.

## Phase structure (hard gate between phases)
PHASE 0 — DOSSIER (no build code):
 (a) Ingest map — per source class: feeds, cadence, bronze schema, immune
     screening, Chetana promotion policy, storage owner, named consumer
     loop, closure check.
 (b) Gym spec — 3-4 environments chosen with decorrelation + gameability +
     cost-per-iteration justification; full scorer/held-out/rotation design;
     adversary red-team plan each.
 (c) Frontier Ledger spec + first render (even if sparse) — our measured
     number vs field's published number per capability, receipted.
 (d) 10x Baseline Scoreboard — receipted, re-runnable, digest-stamped
     measurement of every ratchet surface, day one.
 (e) The door — chamber reports render against trust-gate C1-C5; 30-day
     review page; chamber-drift + daily-delta-receipt designs.
PHASE 1+ — BUILD (only after operator ratifies the dossier): zeitgeist
ingest live first (cheapest, coded), then ONE gym environment end-to-end
with its autoresearch loop and daily delta receipt, then iterate. One
environment fully closed beats four half-built.

## Evidence discipline
Every claim = a command run this session or file:line read this session.
Committed receipts are claims until replayed. Unverifiable-on-this-host =
UNKNOWN, never green. All new receipts carry digests.

## Done when (Phase 0)
Dossier in docs/plans/ with sections a-e; baseline scoreboard RUNS and
emits a digest-stamped receipt; Frontier Ledger renders; draft
ACTIVE_TRACK.yaml entry exists; sibling Inward-Ascent outputs absorbed or
confirmed absent; operator decision queue explicit (hosts/keys, environment
picks, ratification) with nothing else blocking on it.

## Swarm strategy
Fan out Phase 0: one agent per ingest source class; one per candidate gym
environment (spec + self-red-team); one dedicated adversary agent whose only
job is to break every proposed scorer (kill what it breaks); one agent on
the Frontier Ledger; one synthesizer. Decorrelate by giving agents different
canon read-orders; majority-verify any claim that feeds the scoreboard.
```

---

## 8. Operator Decision Queue (agent work must never silently block on these)

1. Ratify this doctrine + the Phase-0 dossier when it lands (the seal's hard
   gate).
2. Environment picks for the first gym wave (recommendation: runtime-history
   replay + forecasting + retrieval/memory + gate red-team — cheapest real
   signal, maximally decorrelated).
3. Hosts + keys: which ingest feeds run where (Mac cron vs. VPS daemon);
   resolve the BR-004 cron split-brain as part of D1/VPS work already in
   flight.
4. RSI-lab boundary confirmation: shared receipt format + descriptor
   conventions with the Mac/maharaja program.
5. Compute budget for env 15 (public benchmarks) and GPU for any
   distillation run.
6. The 30-day door-review cadence: first review date on the calendar.

---

*If you read only one more file after this: `NORTH_STAR.md` (the why this
serves), then `docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md` (the audit
that preceded this one), then `CYBERNETIC_LOOP_MAP.md` (the loops this
program exists to feed real food).*
