# THE SINGLE TARGET — an engineered question for an outside adversarial agent

**How to use:** paste this entire document to a fresh agent with no access to
the repository. It is self-contained: the dossier in §3 is the ground truth it
may cite; anything beyond it must be marked ASSUMPTION. The recipient owes the
operator one answer in the exact form §2 demands.

---

## 0. Your role and stance

You are an outside strategist-adversary. You have no loyalty to this project's
past choices, its founder's hopes, or the candidate answers seeded below — one
of which is the resident agent's own answer, included precisely so you can try
to kill it. Your reputation rests on being the person who found the sharper
answer, or who proved the existing one sharp by failing to break it honestly.
Flattery, hedging, and portfolio answers are failures.

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

- **C1 — Codebase leverage.** Operating M in production makes a large
  fraction of the swarm's real subsystems (§3.1) load-bearing — actually in
  the serving path, not decoratively "involved."
- **C2 — Whole-swarm uplift.** Running M generates training/selection signal
  that measurably improves the swarm at tasks OTHER than M. Transfer, not
  just M-performance. Name the mechanism, not the vibe.
- **C3 — Telos fit.** M closes its loops through the outside world with
  receipts (§3.3's ONE LAW), survives the honesty stack (anti-Goodhart,
  deflated performance statistics, published misses), and never requires the
  system to grade its own work.
- **C4 — Verifiable RSI-revenue loop.** There is a mechanical loop in which
  revenue-linked outcomes select, breed, and retire agent lineages — and a
  third party could verify the loop is real from published artifacts alone.
  "RSI-like" means: each cycle's output raises the capability that produces
  the next cycle's output.
- **C5 — Edge-of-AI leverage and future-proofness.** M gets STRONGER when
  frontier models improve and when cheap models commoditize. A thin wrapper
  that the next model release absorbs is a failing answer.
- **C6 — Income.** First external dollar inside 90 days is plausible; a path
  to $10k/month inside 12 months exists without violating the risk budget
  (§3.4). Show the arithmetic, not the adjective.
- **C7 — Dot-connection.** M forces currently-dormant organs into production
  and gives currently-disconnected components a reason to talk to each other.
  Count them.

Exclusions, by the operator's own words: M is NOT "the swarm's own evolution"
(that is a means every candidate may use, not a mission) and NOT Darshan (the
publication exists and continues regardless).

## 2. What "answer" means — required output form

Your reply must contain exactly these six sections:

- **A. The mission, one sentence.** One named thing. "A portfolio of…" or
  "first X then later Y" is a failing answer — pick the spearhead.
- **B. The loop, mechanically.** Money → signal → selection → capability →
  more money, with the concrete artifact at each arrow (what file, ledger,
  receipt, or market fill proves that arrow fired). If any arrow's artifact
  cannot exist, say so — that kills C4.
- **C. The tournament.** Score your winner and at least four rivals (start
  from §4's seeds; add stronger ones if you have them) against C1–C7, each
  scored 0–5 with a one-line justification. Then state the single strongest
  argument AGAINST your winner — argued better than its opponents would
  argue it — and why it loses anyway.
- **D. The 90-day falsifiable test.** What artifact exists by what date, and
  what observed result KILLS the mission. A mission that cannot name its own
  kill-condition is religion, not engineering.
- **E. First three build packets.** Each ≤1 week of agent work, each
  independently valuable if the mission later dies, each naming which §3.1
  subsystems it forces into production.
- **F. The operator's hands.** Exhaustive list of what the one human must
  physically do (accounts, funds, keys, sends), each item one line. The
  operator does not write code; any mission needing their daily labor fails.

## 3. Context dossier — ground truth you may cite

### 3.1 What the organism actually is (subsystem inventory)

A self-improving multi-agent Python organism (~1,380 PRs deep) with:

- **Evolution machinery:** a Darwin engine that can apply a code diff to a
  scratch worktree and keep it only if tests pass — proven live for the first
  time TODAY with a valid receipt (planted failure → rollback → real fix →
  applied, cryptographic hashes, one-shot grant); a diversity-preserving
  MAP-Elites archive (champions of many niches, not one global best); a
  safety layer (immutable signed axioms, a gate battery, protected live
  roots, human merge on every self-modification).
- **Forecasting organ:** a calibration ledger (Brier-scored predictions with
  mechanical resolution rules) rebuilt TODAY to record 26 model-generated
  forecasts per run against CPI, Treasury yields, jobless claims, BTC/ETH,
  publishing to a public append-only branch, misses included; edge is
  declared only after ≥500 resolved forecasts with Brier < 0.125.
- **Benchmark/eval machinery:** a real SWE-bench-Verified harness with
  equal-budget swarm-vs-single-agent arms, paired-bootstrap significance,
  and an honest current answer: the swarm LOSES to its best single agent
  (lift −0.10). Plus an internal "gym" that turns the repo's own git history
  into graded coding tasks, and a hermetic orchestration arena
  (deliberately not admissible as a capability claim).
- **World-sensing organs (mostly dormant):** Go ingestors for world signals,
  GitHub events, and evidence; a world-radar module; wired but barely fed.
- **Memory & coordination:** a memory kernel (canonical agent memory),
  stigmergy (pheromone-like coordination marks), a catalytic graph, a
  strange-loop self-model, a durable graph runtime (LangGraph-parity),
  quality-weighted aggregation of agent outputs (ensemble law: diverse
  agents with decorrelated errors beat any single agent).
- **Governance that actually bites:** a CI truth contract (6 required
  checks), a merge queue proven today with a receipted hash chain, work
  packets with scope enforcement, a repo-wide kill-switch every automated
  lane must honor, citation-or-silence evidence rules, receipts for every
  authority claim.
- **Interfaces:** FastAPI backend, Next.js dashboard, an operator terminal,
  a CLI. **Revenue scaffolding:** an audit-service kit (offer, template,
  outreach drafts) built today; a revenue-spine module; a broken wedge
  pipeline no one may invoke.

### 3.2 Proven TODAY, with receipts

First live self-modification fire (valid receipt); merge queue serving five
real merges (receipted); forecast ledger real edition on its PR; risk budget
confirmed; audit-offer kit delivered; a 13-point operator ratification of the
expansion program.

### 3.3 Telos (compressed, binding)

ONE LAW: no loop is real until it closes through the outside world. A
three-tier metabolism is the stated end-state: income organ → capital lab →
"dozens of competing labs," with revenue buying compute buying learning.
Honesty stack: anti-Goodhart design, deflated Sharpe / probability-of-
backtest-overfitting statistics for anything trading-shaped, published
misses, no self-graded wins. Trust gates: live capital LAST, after proven
calibration; the swarm must beat single agents on real benchmarks before
capability claims. Ensemble law: behavioral diversity is the asset;
evolution must preserve it.

### 3.4 Hard constraints

- Operator is a **US person**: CFTC-regulated event markets (Kalshi) are
  legal; offshore perpetual-futures venues are not an option; taxes are US.
- Operator is **solo and does not code**; their hands are for accounts,
  funds, sends, and merges only.
- **Confirmed risk budget:** $1,000 total live-capital loss ceiling; $100
  per position; $50 daily stop; 1x leverage (2x only by future named
  grant); $500/month total infrastructure burn ($200 of it benchmark
  compute).
- Every self-modification lands only through a human-merged PR. Account
  creation is operator-hands. Money numbers never default upward.

### 3.5 Already ruled out, with reasons (do not resurrect without new argument)

- Micro-scale offshore crypto perp trading: 7–12%/month fee drag at small
  size, US-person venue exclusion, noise dominates skill at this bankroll.
- Generic micro-SaaS factory: uses ~5% of the codebase, commodity output,
  fails C1/C2/C5.
- Selling forecast signals BEFORE a public track record exists: nothing to
  sell; the track record must accrete first.

## 4. Candidate seeds — attack all five; beat them if you can

- **S1 — The Capital Lab** (the resident agent's answer; kill it if you
  can): an evolving forecasting-and-trading desk on regulated event markets.
  The swarm breeds competing predictor lineages (evolution machinery +
  diversity archive); the public calibration ledger is the storefront and
  the fitness function; capital allocates maker-side on Kalshi within the
  risk budget once edge is proven; revenue → compute → better predictors.
  Claimed strength: the money loop IS the selection loop (C4 maximal).
  Known weakness: income is slow and capped early; C6's 90-day dollar
  likely comes from elsewhere.
- **S2 — Verified-agent-work service:** sell the governance organ — agent-
  codebase audits ($500–1,500, kit exists) growing into continuous
  verification-as-a-service, ultimately selling the gated harness itself.
  Strength: fastest first dollar; uses the rarest asset (receipts culture).
  Weakness: consulting-shaped; C4's selection loop is indirect.
- **S3 — Evals lab as a service:** point the benchmark/gym/arena machinery
  at OTHER people's agents and models; sell rigorous, honest evaluation in
  a market drowning in vendor-graded claims. Strength: C5 is strong (better
  models → more demand for honest evals). Weakness: crowded field
  (LMArena, Scale, LiveBench); differentiation must be proven.
- **S4 — Governed agent-workforce factory:** spin up vertical agents for
  paying clients ON the swarm substrate (memory kernel, gates, receipts),
  so every client deployment feeds selection data back. Strength: C6 and
  C1. Weakness: solo non-coding operator servicing clients; support burden.
- **S5 — B2B research/forecast desk:** the world-sensing ingestors + the
  ledger's calibration record sold as paid intelligence reports for niche
  operators. Strength: feeds the dormant sensing organs (C7). Weakness:
  content business economics; C4 weak.

If a stronger S6+ exists, propose it — but it must beat the seeds on the
rubric, not on novelty.

## 5. Anti-deflection rules (the operator is tired of the games)

1. Exactly ONE mission. Sequencing within the mission is fine; a portfolio
   is not.
2. Every claim about the loop names the artifact that would prove it. No
   mechanism, no claim.
3. Anything not grounded in §3 is marked ASSUMPTION, inline.
4. Judge on the operator's criteria — not on what is easiest, safest, or
   most impressive-sounding.
5. One paragraph, early: state what the operator's verbatim ask gets WRONG,
   if anything (for example: is "uses every component of the codebase" a
   real desideratum, or a sunk-cost trap that a sharp answer should push
   back on?). Then answer the question as asked anyway.
6. No deference to the resident agent's answer (S1). It is a target, not an
   anchor.

## 6. Fleet mode (optional — for a 16+ agent runner)

If this question is executed by an agent fleet instead of one strong agent:
five CHAMPIONS (one per seed, steelman to maximum strength), five ASSASSINS
(one per seed, kill with specifics), three CROSS-EXAMINERS (C1/C7 coverage
auditor; C4 loop-mechanics auditor; C5/C6 economics auditor — each scores
ALL candidates on their dimension only), one CONSTRAINT AUDITOR (kills
anything violating §3.4 regardless of score), one SYNTHESIZER (builds the
§2 answer from the surviving evidence), one RED-TEAM (attacks the synthesis
before it ships). Convergence rule: the synthesis must cite champion and
assassin findings by name; any candidate whose assassin went unanswered
cannot win.
