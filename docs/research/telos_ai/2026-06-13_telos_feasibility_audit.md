---
title: TELOS AI — substrate feasibility audit (concept; seed not yet written)
status: audit
schema_version: feasibility_audit.v1
doc_role: report
authority: none — descriptive findings, owns no rules and no state
audited_by: fable_composer (claude-fable-5) + 8-agent decorrelated workflow
audited_at: 2026-06-13
witnessed_head: 9c76b2106 (origin/main)
companion: docs/vision_maps/NORTH_STAR.md
---

# TELOS AI — Feasibility Audit V0

## 0. The finding that reframes the whole audit

**There is no TELOS seed to audit.** `docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md`
is absent on disk and on every git ref; branch `telos-ai-seed-2026-06-13`
and commit `a81888e` named by the audit brief did not exist (this branch
was created fresh for this report). Every *parent* artifact the brief
cites is real and present. So a detailed 7-part, 16-file adversarial
audit prompt exists for a vision document that was never written.

That is not a gap to apologize for — it is the single most important
data point. The brief itself warns that the seed's notional author is
"structurally biased toward elegant architecture over shippable
substrate." A fully-specified audit of an unwritten seed is that bias,
demonstrated. This document therefore audits the **concept** against
**substrate reality**, which is the only honest thing available and also
the most decision-relevant.

This report owns no authority. It is descriptive findings, file:line
grounded, produced by 8 decorrelated agents (5 substrate readers, 1 cost
modeler, 1 synthesizer, 1 red-team) over the real repo, with the
red-team's corrections folded in.

## 1. Verdict (decided, not hedged)

**TELOS-as-product / user-facing membrane: NOT NOW.** The substrate floor
it would rest on is real and unbuilt. HOLON — the one organ a v0 TELOS
needs — cannot be shown to complete a real task for one user, and scores
its own empty replies as success. Building a product narrative on it
would be building authority on a stub.

**TELOS-as-orientation-pointer (a non-authoritative `vision_maps/`
reference that "owns no rules and no state"): defensible now, and cheap.**
Its real value is not serving users — it is *preventing canon
re-collision*. The seed's three signature inventions (KALYAN,
welfare-tons, the layer stack) are already canon under other owners; a
pointer that names this prevents months of drift. But it must claim zero
authority and defer to every owner it overlaps.

The red-team confirmed this split: *"prove-one-real-user-first is the
right gate for the product framing; do NOT gate a pure orientation
pointer behind it."*

## 2. Substrate truth, surface by surface (file:line)

### 2.1 HOLON reliability — the load-bearing organ
- STATE_OF_TRUTH scores the holon substrate **1-of-6 organs wired**;
  external readiness verdict **38% / "not safe."**
- `holon/holon_runtime.py:138` sets `result["status"]="ran"`
  unconditionally. The p3 artifact gate (lines 148-152) only fires when
  `_OUTCOME_RE` matches a *success word* (`done|updated|committed|…`) with
  no artifact — so an **empty reply `""` matches nothing and is scored a
  successful "ran."** There is no `strip()`/null-guard anywhere in the
  runtime (verified). The only observed live run had **3 of 5 cycles
  return empty, all scored "ran."**
- The orchestration core the build spec calls for is **absent** (the
  record→running-gated-agent "bridge" does not exist); the compass is
  non-binding; governance fails open. HOLON's ~83-85 tests pass against
  **stubs**; none proves a real end-to-end session.
- Honest confidence: *works-in-test-only for the loop; stub-to-unproven
  for real task completion.*

### 2.2 SAB / revenue substrate
- SAB lives in a **separate repo** (`/Users/dhyana/dharmic-agora`), not
  dharma_swarm. The app is real, runnable FastAPI substrate (~15.6k LOC,
  298 tests as of 2026-04-16) — **not vaporware.**
- But: `VENTURE_CELL_PORTFOLIO.yaml:135` marks it `DORMANT, "zero
  sparks."` The DB holds 16 posts / 4 agents — **all internal dharma
  agents**, frozen since 2026-05-22. **Zero external humans have ever
  touched it.** `witness_chain` table: 0 rows. Two evaluation surfaces
  still diverge (authority convergence is the standing #1 open problem).
- `welfare_tons_produced` is **never assigned a nonzero value anywhere**
  in the codebase. The gaia ledger has 3 entries including a **$1.00
  self-transfer**. Revenue substrate is ~100% unbuilt.

### 2.3 Operator velocity — the brief's premise is half-wrong
- "50+ stuck PRs / solo dev" is **refuted**: 10 open PRs (none aged >5
  days), **140 merged in 30 days (~33/wk)**, ~90 commits/wk, 17-18
  worktrees. This is a high-merge multi-lane operation, not a clogged
  queue. **Raw closing velocity is not the constraint.**
- **But there is one human.** `git shortlog -sne --all`: Dhyana (1060),
  John Shrader (566), AmitabhainArunachala (149+25), DHARMA SWARM (35) —
  **all resolve to `Johnvincentshrader@gmail.com`.** Every non-John
  "contributor" is a bot or agent. Across ~1,600 human commits, **exactly
  one human has ever participated.**
- ~38% of non-merge work is docops/count/governance paperwork (a
  self-inflicted tax); effective shippable-substrate rate ≈ 28-38
  commits/wk, not the headline 90.
- `REALITY_DEBT_LEDGER`: **11 claims, all AMBER/RED, zero green** —
  self-funding, external-humans-served, deploy-provenance, R_V-proof all
  unproven; several externally-gated (no commit velocity manufactures a
  paid invoice or an external human's reply).

### 2.4 Vision lineage — the seed would collide, not invent
- North star (`NORTH_STAR.md:12`) is **Jagat Kalyan** (salvation of the
  world), not a "TELOS AI" membrane (0 repo hits for the name). A paid
  membrane is at most a §4 "funding wedge," and §8 **gates all
  outward-pushing behind internal coherence the operator says is not yet
  reached.**
- **Reserved/owned names the seed must not redefine:** KALYAN is a live
  telos-domain (`telos_substrate.py:332`); welfare-tons are ADR-owned
  (`ADR_WELFARE_TONS_REPO_STRUCTURE_2026-03-21`); the canonical stack is
  **11 functional layers whose apex L11 is *already named TELOS*** —
  there is no L12. "RTN" in this repo means **Recursive Transition
  Network** (23 of them, mapped once and lost), not a layer stack. A
  "12-layer RTN" is an off-by-one collision with doctrine that already
  exists.
- Per `CANONICAL_DOC_STACK.md` a seed could live only as a subordinate
  `vision_maps/` reference owning **zero rules and zero state**; as a
  track it would serve `revenue-external-humans-served` — the one spine
  objective with **no active track today** (the one legitimate slot).

### 2.5 Hidden concerns, ranked most-fatal-first
1. **Data-rights void [FATAL].** No delete / export / erasure path
   exists anywhere in the repo; no encryption at rest (plaintext SQLite,
   `MemoryFact.text` as `text TEXT`). A daily reflective journal is
   special-category-adjacent processing. **GDPR (1 EU user, no threshold,
   30-day erasure+export) and the FTC Health Breach Notification Rule
   (mental-health apps, no threshold) are both binding-and-unsatisfiable
   on day one.** CCPA does *not* apply (thresholds unmet) — so a seed that
   worries about CCPA is worrying about the wrong law.
   *(Number correction: an earlier pass said "339G plaintext"; the actual
   runtime.db is ~142M. The no-erasure-path finding stands; the size
   urgency was inflated ~2400× — discount it.)*
2. **No touchable product surface [HIGH].** "HOLON UI" is an ~89-line SSE
   chat endpoint with no frontend; the dashboard is one Next.js page; the
   API is bearer-or-nothing, localhost-only, single-tenant, no end-user
   accounts. A real external user can touch nothing safe on day one. The
   seed names no medium because no consumer medium exists.
3. **Single point of failure [HIGH].** All human ownership, all infra
   (launchd crons on one un-backed-up Mac) = John. John ill / N1-focused
   / burned out = no triage, no honorable deletion, correlated
   total-loss risk.
4. **Cost is NOT the risk [LOW].** See §3 — the product is cheap and fast.

## 3. Cost & latency (generic 12-layer model, 2026 pricing)

Cost is the *least* of the concerns. A 12-layer recursive morning session:
- **~$0.05-0.29/session**; monthly at 30 sessions: 12-layer mixed-cached
  **$3.49**, 7-layer v0 **~$2.00**, all-Opus cached **$4.75**.
- **Latency 1-2 min** (all-Sonnet 68s, all-Opus 114s, mixed 83s), far
  under the 5-10 min UX-failure line; stream per-layer and perceived wait
  is ~5-8s. A 45-min session does not happen at this structure.
- **Pricing correction to the brief's anchor:** Opus 4.8 is **$5/$25 per
  Mtok**, not $15/$75 (that was Opus 4.1-era). Sonnet 4.6 $3/$15, GPT-5.5
  $5/$30, Gemini 3 Pro $2/$12.
- **12 layers collapse honestly to 7 for v0** without losing the
  recursive character (the recursion lives in *accumulating context* —
  layer *i* reads outputs 0..*i*−1 — not in raw layer count; below ~6 it
  becomes a 1-2 step rewrite). Unit economics work easily: **$15/mo
  subscription on ~$2 COGS = ~87% margin**; reserve full 12-layer all-Opus
  as a $39 "deep" tier. Do not price under $9.
- Caveat: the live system runs almost entirely on **free/ollama lanes
  ($0.00 across 9,052 cost-log entries)**. A frontier per-user paid
  product is a **new cost regime never actually run**, and the real
  scaling cost is **vector storage** (vectors.db is already 40G for one
  dev), not chat tokens.

## 4. The honest minimum substrate floor (tighter than any P1-P8)

Falsifiable; ordered. None require the seed to exist.

- **F1 — One kept receipt.** A single HOLON cycle completes one real task
  and persists a receipt that survives restart.
- **F2 — Empty replies fail.** An empty/whitespace reply scores
  `halted:empty`, never `ran`. *(~3-line fix; see §6.)*
- **F3 — Separate verifier.** The thing that judges a cycle's success is
  not the thing that produced it (no self-certification).
- **F4 — One non-stub run.** A real end-to-end session, not a stub-green
  test, leaves evidence.
- **F5 — One non-John human served.** The only floor item not fixable by
  code, and with **zero precedent across ~1,600 human commits.** This,
  not architecture, is the real gate.
- **F6 — No canon redefinition.** Any TELOS artifact defers to the
  existing owners of KALYAN, welfare-tons, the 11-layer stack.

The red-team's sharpest point: F1-F4 are days of work the team's velocity
trivially clears; **F5 is the whole game**, and it is structurally
un-velocity-bound.

## 5. Three options (no softening)

- **(a) Write the full 12-layer product seed now — low value.** It would
  collide with canon (KALYAN/welfare-tons/L11-TELOS/11-vs-12 layers),
  claim authority it cannot hold, and narrate "external humans served"
  against a zero-precedent reality. Audited paper on a stub.
- **(b) Build the 1-2-layer minimum and learn — recommended.** A
  single-layer HOLON loop + quality floor (F2) + a kept-or-discarded
  receipt on one real daily task (PR triage, or an N1 drill). One kept
  receipt per day, zero empties scored "ran." This produces real learning
  per dollar and directly drains F1-F4.
- **(c) "Close substrate first" — wrong question.** Substrate is never
  "done"; the ledger is structurally AMBER. Waiting for green is waiting
  forever. The honest move is the minimum that produces a kept receipt and
  one non-John reply, not a substrate moratorium.

## 6. Recommendations (specific, falsifiable, solo-dev-survivable)

**Next 7 days — ship the empty-reply floor (F2).** The single highest-
leverage, smallest change the audit found. In `holon_runtime.py`, before
the status is set: if the reply is empty/whitespace, status =
`halted:empty`, and the cycle is not counted a success. Add one test:
empty reply → `halted:empty`, not `ran`. This is a contract in the exact
spirit of the assurance-boundary AB-02 work (no silent success). Owned
surface — composer-holon-spine-longrun — so it goes as a small reviewed
PR, not a drive-by.

**Next 30 days — F1-F4 green + first F5 attempt.** Seven kept receipts;
4 of 7 from non-stub runs; a verifier distinct from the producer; and one
genuine attempt to put the single-layer loop in front of **one human who
is not John** (a friend's morning page, anonymized) — because F5 has zero
precedent and everything else is downstream of it.

**Revisit in 90 days — only on evidence.** Write a TELOS *product* seed
only if: ≥30 kept receipts, ≥1 non-John human served with a real reply,
non-stub runs at ≥70% success, and zero non-John use by day 90 has NOT
happened (i.e. someone other than John actually kept using it). Until
then, a TELOS *orientation pointer* may exist in `vision_maps/` as a
non-authoritative reference that names the north star and the
canon-collision risk — that is cheap, useful, and gateable on nothing.

## 7. The fake-it failure mode (named architecturally)

John is dev + user-zero + business-operator. The failure mode: he keeps
using TELOS to *prove it works* even when it isn't serving him, because
he is invested. Detection mechanism that does not rely on his honesty: a
**blind, delayed verifier** — a next-day cron that asks "did you use this,
and did it change anything?" *before* showing him any session output, and
an **external-humans-served counter that reads 0 until a non-John reply
exists.** The kept-receipt rate stays `unproven` and the badge stays red
until a human who is not John engages. The system refuses to certify its
own usefulness from John's usage alone — the same discipline as F3
(separate verifier), applied to the product's reason for existing.

## 8. Where the concept is right AND the substrate is ready

Holding the brief's bar (say so *only* if both): **the cost/latency
envelope.** A daily multi-layer reflective product is genuinely cheap
(~$2-5/user/mo) and fast (1-2 min), the unit economics close at a $15/mo
floor, and the 11-layer functional doctrine the recursion would ride is
real, code-backed, and runs. The *economic and computational* feasibility
of the product is sound. Everything blocking it is substrate reliability,
data-rights, and the one-human reality — not the product's shape or cost.
