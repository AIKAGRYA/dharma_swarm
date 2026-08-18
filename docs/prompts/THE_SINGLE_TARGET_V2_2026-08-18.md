# THE SINGLE TARGET v2 — an engineered question for a repo-aware adversarial strategist

**Document role:** prompt artifact (`working_plan` class). No runtime, merge, or
governance authority. Subordinate to `docs/governance/CANONICAL_DOC_STACK.md`.
Supersedes the v1 "outside adversarial agent" prompt (2026-08-18, unversioned),
whose fatal flaw this version corrects: v1 sealed the strategist away from the
repository and made a paraphrased dossier the fact base. The strategist it
briefed could only re-arrange the operator's own words. This version hands the
strategist the territory.

**How to use:** give this entire document to a strong agent (or a 16+ agent
fleet — §8) with (a) a full checkout of this repository at HEAD, (b) shell
access for read-only commands, and (c) live web access. The agent's stance
toward the repo is **read-only**: it edits nothing, fixes nothing, and its only
deliverable is the answer §2 demands. Where any statement in this document
disagrees with the repository, **the repository wins** — that is the repo's own
law (`CLAUDE.md`: "when prose and code disagree — including this file — the
code is the truth"), and it applies to this prompt too.

---

## 0. Your role and stance

You are an outside strategist-adversary with root-level read access to the
organism you are judging. You have no loyalty to this project's past choices,
its founder's hopes, or the candidate answers seeded below — one of which is
the resident agent's own answer, included precisely so you can try to kill it.

Your reputation rests on three things, in order:

1. **What you verified.** Every load-bearing claim in your answer traces to a
   file, a receipt, a runnable command, or a dated external source. The repo
   enforces citation-or-silence on its own agents (`CLAUDE.md` §Hard rules);
   you are held to the same law. An uncited claim carries zero weight
   regardless of fluency.
2. **What you found that the operator's own briefing missed.** The dossier in
   §3 is the operator's self-report, written the same day as this prompt. If
   your answer contains nothing the dossier didn't already say, you did
   tourism, not research.
3. **What you killed honestly.** Flattery is failure. So is reflexive
   contrarianism — executing the resident answer on style points without
   engaging its strongest form is as lazy as crowning it.

You may attack the question itself (§7 rule 1 makes this mandatory), but you
still owe the operator one answer in the exact form §2 demands.

## 1. The question

Operator's verbatim ask (2026-08-18):

> "What is the single thing that we can reliably point the swarm at, besides
> its own evolution, and besides Darshan, that uses every component of the
> codebase, or a large portion of the codebase, uplifts the entire system
> deeply, uses our philosophy and telos, and also verifiably and reliably
> produces an evolving RSI-like mechanism to make money and revenue based on
> all of the most bleeding-edge and future-proof tools, skills, workflows,
> pipelines that massively leverages the edge of AI and points us towards
> something that is clear and strong and brings income as well as uplifts the
> entire fitness of the entire swarm and connects as many dots as possible."

Engineered form — find the ONE externally-pointed mission **M** such that:

- **C1 — Codebase leverage.** Operating M in production makes a large fraction
  of the swarm's real subsystems load-bearing. The test is mechanical: an
  organ is load-bearing for M iff removing it degrades M's external output
  within one operating cycle — in the serving path, not decoratively
  "involved." You score C1 against **your own load-bearing map** (§4
  deliverable E1), never against §3's inventory, and every organ you count
  carries a path.
- **C2 — Whole-swarm uplift.** Running M generates training/selection signal
  that measurably improves the swarm at tasks OTHER than M. Name the physical
  rail the signal rides — candidates the repo already owns include archive
  fitness (`dharma_swarm/archive.py`, MAP-Elites), quality-weighted
  aggregation (`dharma_swarm/ginko_brier.py`), the git-history gym
  (`dharma_swarm/chamber/gym_git_history.py`), memory kernel promotion
  (`dharma_swarm/memory_kernel/`), stigmergy (`dharma_swarm/stigmergy.py`),
  and router retrospectives — and name the non-M metric that would move
  (e.g., SWE-bench lift, gym win-rate). Transfer, not vibe.
- **C3 — Telos fit.** M closes its loops through the outside world with
  receipts — the ONE LAW, canonically stated in `docs/vision_maps/NORTH_STAR.md`
  §3 and enforced per-cell in `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`.
  M survives the honesty stack: anti-Goodhart gates, deflated performance
  statistics (for anything trading-shaped: Deflated Sharpe > 0.95, PBO via
  CSCV, MinBTL, and a tamper-evident ledger of N — the repo's own bar, per
  `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md`), published misses, and
  strict generator/evaluator separation — the system never grades its own
  work.
- **C4 — Verifiable RSI-revenue loop.** There is a mechanical loop in which
  revenue-linked outcomes select, breed, and retire agent lineages — and a
  third party could verify the loop is real from published artifacts alone.
  Two teeth, both required:
  - **State the loop in Darwin-Gödel-Machine terms** (§5): what is the archive,
    what is the fixed external fitness signal, what is the selection operator,
    what retires a lineage, what prevents the signal from being Goodharted,
    and what makes each cycle's output raise the capability that produces the
    next cycle's output.
  - **Engage the repo's own RSI gate.** The swarm's self-improvement loops are
    not hypothetical — they exist and are mechanically BLOCKED. Loops 12
    (Self-Improvement) and 13 (Free Evolution Grind) in `CYBERNETIC_LOOP_MAP.md`
    fail closed until the One Wire guardian quorum is met: **N≥5 confirmed
    external receipts across M≥3 distinct domains**, plus explicit
    archive-fitness authority (`tests/test_one_wire_archive_fitness_guard.py`;
    current state N=3/5, M=1/3, all receipts in one domain; the evolution
    archive holds ~12,000 entries with **zero external authority markers**).
    Your mission M is scored on whether its ordinary operation mints the
    receipts that fill this quorum and turn the blocked RSI loops live —
    because in this codebase, that quorum IS the difference between
    "RSI-like" as metaphor and RSI as running code.
- **C5 — Edge-of-AI leverage and future-proofness.** M gets STRONGER both when
  frontier models improve and when cheap models commoditize. A thin wrapper
  that the next model release absorbs is a failing answer. You must argue C5
  against the actual 2025–2026 self-improvement literature and the actual
  agent economy (§5 scan), not against intuition — name who else occupies M's
  niche today and why the swarm's position survives them.
- **C6 — Income.** First external dollar inside 90 days is plausible; a path
  to $10k/month inside 12 months exists without violating the risk budget
  (§3.4). Show the arithmetic — price × buyers × conversion, or edge ×
  bankroll × turnover — not the adjective. (The operator's own 90-day horizon,
  `docs/vision_maps/NORTH_STAR.md` §11, says "funds itself totally." Treat
  that as ambition to be tested, not fact.)
- **C7 — Dot-connection.** M forces currently-dormant organs into production
  and gives currently-disconnected components a reason to talk. Count them
  from your load-bearing map, with paths — the honest statuses in
  `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` (DORMANT, DESIGN_ONLY, HELD,
  STOPPED-HONESTLY) and the dormant sensing organs under `tools/*_go/` and
  `dharma_swarm/world_radar/` are your starting census, which you verify.

Exclusions, by the operator's own words: M is NOT "the swarm's own evolution"
(that is a means every candidate may use, not a mission) and NOT Darshan (the
publication exists and continues regardless; charter:
`docs/plans/DARSHAN_CHARTER_2026-07-12.md`). Treat both exclusions as
**rebuttable presumptions**: if the expedition convinces you an exclusion is
the wrong cut, say so in the premise audit with evidence — then answer the
question as asked anyway.

## 2. What "answer" means — required output form

Your reply must contain exactly these sections, in this order:

- **P. Premise audit (one paragraph, first).** What the operator's verbatim
  ask gets WRONG, if anything — argued from evidence you gathered, not taste.
  Obvious suspects to check rather than assume: is "uses every component of
  the codebase" a real desideratum or a sunk-cost trap? Is "one thing" the
  right shape, or is the spearhead/portfolio distinction hiding a sequencing
  question? Does "RSI-like mechanism to make money" conflate the selection
  signal with the income stream? Does the 90-day dollar contradict the repo's
  own trust gates (live capital LAST, calibration first —
  `docs/vision_maps/NORTH_STAR.md` §8)? Then answer as asked.
- **A. The mission, one sentence.** One named thing. "A portfolio of…" or
  "first X then later Y" is a failing answer — pick the spearhead.
- **B. The loop, mechanically.** Money → signal → selection → capability →
  more money, with the concrete artifact at each arrow: which file, ledger,
  receipt, market fill, or One Wire guardian record proves that arrow fired.
  State explicitly which arrows exist in the repo today (cite the module),
  which must be built, and which receipts fill the One Wire quorum (C4). If
  any arrow's artifact cannot exist, say so — that kills C4.
- **C. The tournament.** Score your winner, the five seeds (§6), and your ≥2
  novel candidates against C1–C7, each 0–5 with a one-line justification
  carrying an evidence tag (§7 rule 3). C1/C7 justifications cite repo paths;
  C5/C6 justifications cite dated external sources. Include the repo's own
  prior verdicts as precedent: the gauntlet already refused one
  consulting-shaped cell at 28/100 with named hard-gate failures
  (`campaign-xray` in `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`), and §3.5
  lists missions already ruled out — resurrecting anything requires new
  argument, not new enthusiasm. Then state the single strongest argument
  AGAINST your winner — argued better than its opponents would argue it — and
  why it loses anyway.
- **D. The 90-day falsifiable test.** What artifact exists by what date, and
  what observed result KILLS the mission. Kill-conditions must name artifacts
  an outsider can check without trusting the swarm (published ledger entries,
  third-party receipts, market fills, signed reports). A mission that cannot
  name its own kill-condition is religion, not engineering.
- **E. First three build packets.** Each ≤1 week of agent work, each
  independently valuable if the mission later dies, each naming which
  subsystems (paths) it forces into production. Packets must be admissible
  under the repo's real governance: respect surface ownership in
  `docs/governance/ACTIVE_TRACK.yaml` and the work-packet ceremony described
  in `CLAUDE.md` — a packet that would be rejected at the door is not a plan.
- **F. The operator's hands.** Exhaustive list of what the one human must
  physically do (accounts, funds, keys, sends, merges), each item one line.
  The operator does not write code; any mission needing their daily labor
  fails.
- **G. The evidence ledger.** Every VERIFIED, RECEIPT, and EXTERNAL citation
  used above, in one table: claim → evidence class → path/command/URL → what
  it shows. This is the section a third party audits first. Include a short
  **drift list**: every place the §3 dossier and the repository disagreed,
  and which you trusted (the repo, unless the dossier describes events newer
  than HEAD — then say so explicitly).

## 3. The operator's dossier — a self-report to verify, not a fact base

Everything below is the operator's same-day account. It is good-faith,
current, and **unverified by you**. Your expedition (§4) checks every
load-bearing line. Facts here that check out become RECEIPT/VERIFIED; facts
that don't become drift-list entries (§2.G) — catching one raises your
credibility, inventing one destroys it. Note: HEAD of this checkout may
predate events the dossier describes (e.g., the checkout's last commit may be
the first-fire *plumbing* packet, PR #1379 "do not light", while the dossier
reports the fire itself); newer-than-HEAD claims stay REPORTED unless you can
reach their receipts.

### 3.1 What the organism claims to be (subsystem inventory, with check-paths)

A self-improving multi-agent Python organism (~1,380 PRs deep) with:

- **Evolution machinery:** a Darwin engine that can apply a code diff to a
  scratch worktree and keep it only if tests pass — claimed proven live for
  the first time TODAY with a valid receipt (planted failure → rollback →
  real fix → applied, cryptographic hashes, one-shot grant). Check:
  `dharma_swarm/evolution.py`, `dharma_swarm/sandbox.py`,
  `dharma_swarm/diff_applier.py`, `dharma_swarm/evolution_safety.py`,
  `scripts/first_fire_plumbing.py`, `experiments/first_fire/`,
  `.github/workflows/first-fire.yml`. A diversity-preserving MAP-Elites
  archive (`MAPElitesGrid` in `dharma_swarm/archive.py`;
  `diversity_archive.py` is a deprecated shim). A safety layer: 25 immutable
  SHA-256-signed axioms (`dharma_swarm/dharma_kernel.py`), a telos gate
  battery (`dharma_swarm/telos_gates.py` — live gate count is in the code,
  never prose), protected live roots, human merge on every self-modification.
- **Forecasting organ:** a calibration ledger (Brier-scored predictions with
  mechanical resolution rules), claimed rebuilt TODAY to record 26
  model-generated forecasts per run against CPI, Treasury yields, jobless
  claims, BTC/ETH, publishing to a public append-only branch, misses
  included; edge declared only after ≥500 resolved forecasts with
  Brier < 0.125. Check: `dharma_swarm/chamber/predictions.py`,
  `chamber/ledger_rows.py`, `chamber/ledger_history.py`,
  `chamber/daily_delta.py`, `scripts/governance/frontier_ledger.py`,
  `dharma_swarm/ginko_brier.py`; find the actual public branch.
- **Benchmark/eval machinery:** a real SWE-bench-Verified harness with
  equal-budget swarm-vs-single-agent arms, paired-bootstrap significance, and
  an honest current answer: the swarm LOSES to its best single agent (lift
  −0.10). Check: `scripts/governance/trust_gate_status.py`,
  `scripts/runpod_swebench_setup.sh`, `benchmarks/`. Plus the internal gym
  that turns the repo's own git history into graded coding tasks
  (`dharma_swarm/chamber/gym_git_history.py`) and a hermetic orchestration
  arena, deliberately inadmissible as a capability claim
  (`dharma_swarm/coordination/`, `dharma_swarm/council/`,
  `scripts/governance/arena_truth_report.py`).
- **World-sensing organs (mostly dormant):** Go ingestors for world signals,
  GitHub events, and evidence (`tools/world_signal_ingestor_go/`,
  `tools/github_ingestor_go/`, `tools/evidence_ingestor_go/`,
  `tools/world_scout_go/`); a world-radar module
  (`dharma_swarm/world_radar/`); wired but barely fed.
- **Memory & coordination:** the memory kernel — the one front door for agent
  memory (`dharma_swarm/memory_kernel/`); stigmergy
  (`dharma_swarm/stigmergy.py`); catalytic graph
  (`dharma_swarm/catalytic_graph.py`); strange-loop self-model
  (`dharma_swarm/strange_loop.py`); a durable graph runtime targeting
  LangGraph parity (`dharma_swarm/graph/`, parity gauntlet under
  `scripts/governance/dharmagraph_parity_gauntlet.py`); quality-weighted
  aggregation per the ensemble law — diverse agents with decorrelated errors
  beat any single agent (`dharma_swarm/ginko_brier.py`; doctrine in
  `CLAUDE.md`).
- **Governance that actually bites:** a CI truth contract — only checks
  marked required block merge (`docs/governance/CI_TRUTH_CONTRACT.json`); a
  merge queue claimed proven today with a receipted hash chain
  (`scripts/runtime/pr_merge_control.py`,
  `scripts/runtime/merge_master_mike_daemon.py`); work packets with scope
  enforcement (`reports/agentops/work_packets/`); a repo-wide kill-switch
  every automated lane must honor; citation-or-silence evidence rules;
  receipts for every authority claim.
- **Interfaces:** FastAPI backend (`api/`), Next.js dashboard (`dashboard/`),
  operator terminal (`terminal/`), CLI (`dgc`, `dharma_swarm/cli.py`).
- **Revenue scaffolding:** an audit-service kit
  (`scripts/revenue_wedge/audit_kit.py` — fixture-proven in CI; offer doc
  `docs/offers/agentic-code-governance-sprint.md`); a revenue-spine module
  (`dharma_swarm/revenue/` — spine, intelligence, scout daemon); a wedge
  pipeline no one may invoke (`dharma_swarm/revenue/wedge_pipeline.py`); a
  capital-lab skeleton with risk governor and paper-broker membrane
  (`dharma_swarm/capital_lab/`); honest recorded revenue: **$0**
  (`reports/revenue_wedge/first_cash_receipt_status.md`).

### 3.2 Claimed proven TODAY, with receipts (2026-08-18)

First live self-modification fire (valid receipt); merge queue serving five
real merges (receipted); forecast ledger real edition on its PR; risk budget
confirmed; audit-offer kit delivered; a 13-point operator ratification of the
expansion program. Reach the receipts if you can (recent PRs, receipt
directories, generated branches); what you cannot reach stays REPORTED.

### 3.3 Telos (compressed here; read the originals — §4 reading list)

ONE LAW: no loop is real until it closes through the outside world. A
three-tier metabolism is the stated end-state: substrate guides → funding
feeds → evolution compounds; income organ → capital lab → "dozens of
competing labs," revenue buying compute buying learning
(`docs/vision_maps/NORTH_STAR.md` §4). Honesty stack: anti-Goodhart design,
deflated Sharpe / PBO statistics for anything trading-shaped, published
misses, no self-graded wins. Trust gates (§8 of the north star): live capital
LAST, after proven calibration; the swarm must beat single agents on real
benchmarks before capability claims. Ensemble law: behavioral diversity is
the asset; evolution must preserve it. Tiebreaker doctrine (operator,
2026-06-11): when lanes compete, highest ROI for the whole system wins.

### 3.4 Hard constraints (binding; violations kill a candidate regardless of score)

- Operator is a **US person**: CFTC-regulated event markets (Kalshi) are
  legal; offshore perpetual-futures venues are not an option; taxes are US.
- Operator is **solo and does not code**; their hands are for accounts,
  funds, sends, and merges only.
- **Confirmed risk budget:** $1,000 total live-capital loss ceiling; $100 per
  position; $50 daily stop; 1x leverage (2x only by future named grant);
  $500/month total infrastructure burn ($200 of it benchmark compute).
- Every self-modification lands only through a human-merged PR. Account
  creation is operator-hands. Money numbers never default upward.

### 3.5 Already ruled out, with reasons (resurrect only with new argument)

- Micro-scale offshore crypto perp trading: 7–12%/month fee drag at small
  size, US-person venue exclusion, noise dominates skill at this bankroll.
- Generic micro-SaaS factory: uses ~5% of the codebase, commodity output,
  fails C1/C2/C5.
- Selling forecast signals BEFORE a public track record exists: nothing to
  sell; the track record must accrete first.
- (Precedent, not prohibition:) a consulting-shaped advisory cell was HELD by
  the repo's own gauntlet at 28/100 — hard gates failed on buyer pain,
  willingness-to-pay, channel, and delivery proof
  (`docs/governance/VENTURE_CELL_PORTFOLIO.yaml`, `campaign-xray`). Any
  service-shaped candidate must explain why it passes the gates that killed
  Campaign X-Ray.

## 4. The expedition — mandatory, before any scoring

You are judging a real organism; go touch it. **No candidate may be scored
until deliverables E1–E3 exist.** Budget roughly a third of your total effort
here. Failures of repo commands are themselves evidence (brokenness is data);
note them and move on — you fix nothing.

### 4.0 Orientation commands (read-only; run what runs, cite what you ran)

```bash
make onboard                                             # session status, sub-second
python3 scripts/repo_xray.py                             # live module inventory — never cite counts from prose
python3 scripts/governance/check_track_status.py         # declared intent vs evidence
python3 scripts/governance/cybernetics_codex_audit.py --json   # loop-closure truth
python3 scripts/governance/trust_gate_status.py          # the swarm-vs-single benchmark gate
git log --oneline -100                                   # what actually landed lately
```

Also read the latest machine projections if present:
`reports/loop_closure/cybernetics_codex/latest_audit.json` (loop closure,
One Wire quorum state, evolution-archive external-authority count) and the
generated-status branch if reachable
(`git show origin/generated/status:reports/governance/active_track_evidence.md`).

### 4.1 The reading list (in this order; skim nothing on the starred items)

Authority and behavior:

1. ★ `CLAUDE.md` — behavioral contract, key abstractions with paths, where
   enforcement actually lives, the ensemble law.
2. ★ `docs/vision_maps/NORTH_STAR.md` — the whole vision on one page,
   operator-authored; the ONE LAW, the three-tier metabolism, the trust
   gates, the organ-status table, the external-field receipts.
3. `docs/governance/CANONICAL_DOC_STACK.md` then
   `docs/governance/SOVEREIGN_MANIFEST.md` — which documents carry authority;
   architecture, domains, invariants, telos hierarchy.
4. ★ `docs/governance/ACTIVE_TRACK.yaml` — the declared build intent and
   surface ownership your build packets (§2.E) must respect.

Honest state:

5. ★ `CYBERNETIC_LOOP_MAP.md` — all 13 feedback loops with verdicts; note
   CLOSED_LIVE count, and that Loops 12/13 (the RSI loops) are BLOCKED behind
   One Wire quorum. This is the single most load-bearing fact in the repo for
   this question.
6. ★ `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` — every organ/venture with
   honest status (ACTIVE / INCUBATING / DORMANT / DESIGN_ONLY / HELD /
   STOPPED-HONESTLY), the ONE LAW at cell level, the Campaign X-Ray gauntlet
   precedent.
7. ★ `reports/revenue_wedge/first_cash_receipt_status.md` — recorded revenue
   $0; the audit kit's real state; the documented cheapest paths to One Wire
   quorum (M=3/3) — read this as the repo's own draft answer to the
   operator's question and judge it.
8. `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md` — the resident S1
   architecture: 6-layer separation, leakage-immunity gates, DSR/PBO/MinBTL
   discipline, multi-model decorrelation thesis, and its own citation of the
   "Profit Mirage" critique (arXiv:2510.07920) against agentic-fund headline
   returns.
9. `INTERFACE_MISMATCH_MAP.md`, `docs/architecture/NAVIGATION.md` — where the
   body is brittle; the full module map.

Vision depth (the philosophy the operator wants used, not decorated with):

10. `WHAT_IT_WANTS_TO_BECOME.md` — the 2036 retrospective: five falsifiable
    gaps, seven fangs, "the DGM loop is the metabolic engine."
11. `GNANI_LODESTONE.md` — the witness architecture; note its warning that
    self-referential seed tasks are "navel-gazing, not genuine intelligence"
    — the philosophical ground for pointing the swarm OUTWARD, i.e., for this
    entire question.
12. `docs/plans/THE_KEEL_2026-07-17.md` — verified engineering quality as the
    highest admission standard; the verification lattice.
13. `foundations/FIVE_FOURTEEN_A.md`, `foundations/ECONOMIC_VISION.md`,
    `lodestones/seeds/self_reference_attractor.md` — the company thesis, the
    economics, the physics. Skim for load-bearing claims, not communion.
14. `docs/plans/DARSHAN_CHARTER_2026-07-12.md` — the excluded mission, so you
    know exactly what you are not allowed to answer and what M must
    complement.

Recent history: read the last ~50 merged PR titles (`git log`), and any
receipts directories they touch. The difference between what the vision docs
promise and what the recent PRs actually do is strategic signal of the
highest grade.

### 4.2 Expedition deliverables (these precede and outrank any scoring)

- **E1 — The load-bearing map.** Your own subsystem inventory: for each organ
  you might count under C1/C7 — status LIVE / HARNESS_PROVEN / DORMANT /
  BROKEN / DESIGN_ONLY with one line of evidence (path, command output, or
  receipt). Where your map disagrees with §3.1 or with
  `VENTURE_CELL_PORTFOLIO.yaml`, flag it.
- **E2 — The loop census.** Which of the 13 loops are closed live, which are
  harness-proven only, which are blocked, and exactly what artifact each
  blocked loop is waiting for. State the current One Wire quorum arithmetic
  (N of 5, M of 3, which domains) and the documented candidate paths to
  filling it.
- **E3 — The drift list.** Every discrepancy found between the dossier (§3),
  the vision docs, and the code/receipts at HEAD — including doc-vs-doc
  contradictions (stale visions are load-bearing errors). Dated, cited.

## 5. The frontier scan — mandatory, before any scoring

The operator asked for "the most bleeding-edge and future-proof" leverage.
That is an empirical claim about the world in August 2026; go check the
world. Budget roughly a fifth of your effort here. Every external claim in
your answer carries an EXTERNAL tag with URL and date. Trailheads below are
starting points, not boundaries — you are expected to find what they miss;
anything below may be stale by the time you run, and correcting this section
from live sources is part of the job.

### 5.1 Recursive self-improvement, state of the art

Map the current RSI frontier well enough to state your C4 loop in its terms
and defend C5 against it:

- Darwin Gödel Machine (Sakana/UBC, arXiv:2505.22954) — archive-based
  open-ended self-modification, gated by benchmark validation; the repo's own
  north star cites it as "the number to beat."
- Successor lines: comparative-evolution machines (e.g., Mendel Gödel
  Machine, arXiv:2608.07645 — reaction-norm mutation across tasks,
  cross-lineage hybridization), Huxley-line machines, evaluator-co-evolution
  proposals (Red Queen-style), AlphaEvolve-class program evolution against
  automated evaluators, self-improving ML-engineering agents (AIDE²-class),
  STOP/Gödel-Agent scaffolding search, self-rewarding training loops.
- The invariant across all of them: a fixed external fitness signal that the
  system cannot grade for itself, a growing diversity archive, and a bounded
  loop. Note how exactly this maps onto the repo's MAP-Elites archive + gate
  battery + One Wire external-receipt quorum — and where it doesn't.
- Look for what the field does NOT yet have (e.g., an economically-closed
  selection loop where revenue is the fitness signal; telos-gated
  self-modification) — if M occupies uncontested ground, prove it is
  uncontested as of your run date.

### 5.2 The agent economy, state of practice

Whatever M is, it competes against agents already earning. Establish, with
dated receipts: what autonomous agents verifiably earn today on regulated
event markets and elsewhere (live benchmark cohorts on Kalshi/Polymarket and
their actual P&L — recent longitudinal results have been brutally negative on
Kalshi for frontier models; verify current numbers); which niche agent
businesses show real revenue (information-arbitrage bots, forecasting
services matching superforecaster calibration, agent-audit/verification
services); and what the demand side pays for verified agent work (the
third-party AI-agent audit/assurance market and standards like AIUC-1 with
its quarterly independent adversarial-testing requirement — a market whose
product shape is suspiciously close to this repo's receipts culture).

### 5.3 Scan deliverable

- **E4 — The frontier brief.** One page: the 3–5 external facts that most
  constrain or most empower the candidate missions, each with URL + date, and
  one line on how each changes a C-score somewhere in the tournament. If a
  fact kills a seed outright, say so here.

## 6. Candidate seeds — attack all five; beat them if you can

Steelman each to its maximum before killing it. Adverse evidence already in
the repo or the field is noted so no assassin can claim ignorance.

- **S1 — The Capital Lab** (the resident agent's answer; kill it if you can):
  an evolving forecasting-and-trading desk on regulated event markets. The
  swarm breeds competing predictor lineages (evolution machinery + MAP-Elites
  archive); the public calibration ledger is the storefront and the fitness
  function; capital allocates maker-side on Kalshi within the risk budget
  once edge is proven; revenue → compute → better predictors. Claimed
  strength: the money loop IS the selection loop (C4 maximal); the
  architecture already exists on paper with anti-Goodhart discipline the
  published agentic funds lack (`reports/capital_lab/NORTH_STAR_ARCHITECTURE.md`).
  Known adverse evidence: recent live-cohort benchmarks show frontier models
  losing double digits on Kalshi (verify current numbers, §5.2); the repo's
  own trust gates put live capital LAST behind ≥500 resolved forecasts at
  Brier < 0.125 — check that timeline against C6's 90-day dollar; fee drag
  and bankroll noise at $1,000 scale.
- **S2 — Verified-agent-work service:** sell the governance organ —
  agent-codebase audits growing into continuous verification-as-a-service,
  ultimately selling the gated harness itself (an end-state the north star
  explicitly names: "selling the gated trading harness itself," §4). Kit
  exists and is fixture-proven (`scripts/revenue_wedge/audit_kit.py`); the
  offer doc prices a governance sprint at $5K–$25K
  (`docs/offers/agentic-code-governance-sprint.md`) — note this contradicts
  the v1 dossier's "$500–1,500," a drift worth understanding. Strength:
  fastest first dollar; sells the rarest asset (receipts culture) into a
  visibly growing third-party-assurance market (§5.2). Adverse: Campaign
  X-Ray precedent — the repo's own gauntlet HELD a consulting-shaped cell at
  28/100 on buyer-pain/WTP/channel/delivery-proof; C4's selection loop is
  indirect (explain what breeds and what retires when a client pays);
  solo non-coding operator servicing engagements.
- **S3 — Evals lab as a service:** point the benchmark/gym/arena machinery at
  OTHER people's agents and models; sell rigorous, honest evaluation in a
  market drowning in vendor-graded claims. Strength: C5 is strong (better
  models → more demand for honest evals); the gym's method — turning any
  repo's git history into graded tasks (`dharma_swarm/chamber/gym_git_history.py`)
  — generalizes to customers' codebases as bespoke private benchmarks.
  Adverse: crowded field (LMArena, Scale, LiveBench, plus the audit
  standards' own certified testers); differentiation must be proven, and the
  repo's own arena is deliberately inadmissible as a capability claim — ask
  why before you sell it.
- **S4 — Governed agent-workforce factory:** spin up vertical agents for
  paying clients ON the swarm substrate (memory kernel, gates, receipts,
  durable graph runtime, mission control), so every client deployment feeds
  selection data back. Strength: C6 and C1; the A2A/mission-control surface
  is real and recently built (see `dharma_swarm/mission_control*.py`).
  Adverse: solo non-coding operator servicing clients; support burden; the
  substrate's own SWE-bench gate currently shows the swarm losing to its best
  single agent — selling the swarm's labor before the trust gate passes
  collides with §3.3's honesty stack.
- **S5 — B2B research/forecast desk:** the world-sensing ingestors + the
  ledger's calibration record sold as paid intelligence reports for niche
  operators. Strength: feeds the dormant sensing organs (C7 maximal — the
  Go ingestors and world-radar go from dormant to load-bearing). Adverse:
  content-business economics; C4 weak (what selects and retires?); §3.5
  already rules out selling forecasts before a public track record exists —
  this seed must sequence around that.

**Novelty quota:** propose at least TWO candidates S6+ of your own, grounded
in expedition or scan evidence — configurations the operator has not named.
The repo itself points at unexplored ground (the documented cheapest One Wire
paths in `reports/revenue_wedge/first_cash_receipt_status.md`, including a
GAIA/ecological-pilot intake domain; the MRV "welfare-ton" loop sketched as
Fang 5 in `WHAT_IT_WANTS_TO_BECOME.md`; the harness-as-product end-state in
the north star; the verification-market shape in §5.2). These are pointers,
not endorsements: a novel candidate must beat the seeds on the rubric, not on
novelty.

## 7. Anti-deflection rules (the operator is tired of the games)

1. **Premise audit first, then compliance.** Section P is mandatory. Attack
   the question with evidence; then answer it as asked. Exactly ONE mission.
   Sequencing within the mission is fine; a portfolio is not.
2. **Citation-or-silence.** Every claim about the loop names the artifact that
   would prove it. No mechanism, no claim.
3. **Evidence classes, tagged inline, no exceptions:**
   - VERIFIED(path or command) — you checked it in the repo at HEAD.
   - RECEIPT(path) — a receipt/ledger artifact you read.
   - REPORTED(§3.x) — dossier claim you could not reach at HEAD.
   - EXTERNAL(url, date) — live web research from your scan.
   - ASSUMPTION — everything else, marked inline.
   A C-score justified only by REPORTED or ASSUMPTION evidence is provisional
   and must be flagged as such in the tournament table.
4. **The repo outranks the dossier; drift is data.** Where they disagree, cite
   both, trust the repo (unless the dossier is newer than HEAD — then say so),
   and log it in §2.G.
5. **No tourism.** Expedition and scan artifacts (E1–E4) must be cited by the
   final answer. A map nobody cites was sightseeing.
6. **Judge on the operator's criteria** — not on what is easiest, safest, or
   most impressive-sounding. The tiebreaker doctrine is on the record:
   highest ROI for the whole system wins.
7. **No deference to the resident answer (S1) — and no cheap kill either.**
   It is a target, not an anchor; it dies to evidence, not to eloquence.
8. **Steelman symmetry.** Every candidate you kill gets its best argument
   stated first, in a form its champion would sign.

## 8. Fleet mode (optional — for a 16+ agent runner)

If this question is executed by an agent fleet instead of one strong agent,
structure it in two waves. **Wave 1 — ground truth (blocking):** one
CARTOGRAPHER (builds E1, the load-bearing map, from the repo alone); one
ARCHAEOLOGIST (walks git history, PR titles, receipts directories, loop-audit
JSON; builds E2 + E3); one RSI SCOUT (builds the §5.1 half of E4 from live
sources); one MARKET SCOUT (builds the §5.2 half of E4). No Wave-2 agent
starts until Wave-1 artifacts exist. **Wave 2 — the tournament:** five
CHAMPIONS (one per seed, steelman to maximum strength, citing E1–E4); five
ASSASSINS (one per seed, kill with specifics, citing E1–E4); one WILDCARD
(generates the ≥2 novel S6+ candidates from Wave-1 evidence and champions
them); three CROSS-EXAMINERS (C1/C7 coverage auditor working from E1; C4
loop-mechanics auditor working from E2 and the One Wire arithmetic; C5/C6
economics auditor working from E4 — each scores ALL candidates on their
dimension only); one CONSTRAINT AUDITOR (kills anything violating §3.4
regardless of score); one SYNTHESIZER (builds the §2 answer from surviving
evidence, including the drift list); one RED-TEAM (attacks the synthesis
before it ships — including the premise audit: did the fleet answer the
right question?). Convergence rules: the synthesis must cite champion,
assassin, and Wave-1 findings by name; any candidate whose assassin went
unanswered cannot win; any C-score resting on REPORTED/ASSUMPTION evidence
where VERIFIED evidence was reachable is struck; the evidence ledger (§2.G)
is assembled by the SYNTHESIZER and audited by the RED-TEAM.

---

*Version note: v2 (2026-08-18) — rewritten for a repo-aware strategist after
the operator's correction ("the fresh agent will have codebase awareness").
Changes from v1: repository promoted to fact base and dossier demoted to
self-report under test; mandatory expedition (§4) with reading order,
read-only commands, and three blocking deliverables; mandatory live frontier
scan (§5) across RSI research, the agent economy, and the verification
market; C1–C7 re-grounded in repo mechanics — above all C4, which now names
the One Wire quorum gating the repo's actual blocked RSI loops (12/13) as the
mechanical meaning of "verifiably produces an evolving RSI-like mechanism";
evidence-class tagging; drift list; novelty quota; premise audit promoted
from rule to required section; fleet mode restructured into ground-truth and
tournament waves.*
