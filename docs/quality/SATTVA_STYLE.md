---
title: Sattva Style — proposed positive quality invariants
status: seed
schema_version: sattva_style.v1
last_updated: 2026-06-12
doc_role: reference
authority: none — proposes; the hygiene lifecycle and existing gates dispose
enforced_by: scripts/governance/hygiene/ratchet.py (subset; see "What is live")
companion_artifacts:
  - docs/governance/hygiene/LIFECYCLE.md
  - docs/governance/hygiene/ratchet_baselines.json
  - docs/governance/ANTI_SLOP_RULES.md
---

# Sattva Style

This is a reference document, not doctrine: it PROPOSES a positive
quality standard; nothing in it binds anyone until promoted through the
hygiene lifecycle by its own rules. The anti-slop layer says what code
must not be. This document says what code here IS when it is good —
distilled from the five most battle-tested quality doctrines in the
world (NASA/JPL's Power of Ten, TigerBeetle's TIGER_STYLE, SQLite's
testing regime, the Linux kernel's process rules, and Erlang/OTP's
supervision discipline), adapted to this repo's substrate: async-first
Python, multi-agent authorship, receipt-and-witness culture.

Two laws govern this document itself:

1. **The Holzmann meta-rule.** A rule earns a place here only if a
   machine can check it. Rules that cannot be checked by a tool will not
   be followed — not by humans, and not by agents. The set stays small
   and Draconian rather than large and advisory.
2. **The diversity bill.** Per CLAUDE.md's Transcendence Principle, every
   gate is priced in agent-diversity cost before promotion. The invariants
   below are verifiability floors (they remove common-mode error, the
   noise that depresses every agent's quality equally); they are not style
   mandates. The two with a real diversity bill are marked.

How a rule becomes binding: this document proposes; the hygiene
lifecycle (`docs/governance/hygiene/LIFECYCLE.md`) disposes. Each
invariant becomes a pattern file with a detector, banks baselines, and is
promoted observed → measured → advisory → enforced on the lifecycle's
criteria. The ratchet (`scripts/governance/hygiene/ratchet.py`) is the
enforcement mechanism of choice: baseline = current reality, regressions
fail, improvements tighten the baseline on green runs. Nobody is asked to
fix old debt by decree; everybody is forbidden to add new debt.

## The seventeen invariants

Ordered by leverage × checkability. Each names its source and the
ratchet counter that enforces (or will enforce) it.

### Tier 1 — async error integrity (highest leverage for a multi-agent runtime)

**S-01. No swallowed errors (the 92% rule).** No exception handler may
absorb a failure and continue without re-raising, escalating, or writing
a receipt. 92% of catastrophic distributed-system failures trace to
incorrect handling of non-fatal errors explicitly signaled in software
(Yuan et al., OSDI 2014; TIGER_STYLE; Armstrong §4.4).
Counter: `silent_exception_swallows` (down, target 0) — **LIVE in ratchet v1**
(v1 catches the exact `except [Exception|bare]: pass` shape; widening to
log-without-reraise is the v2 step).

**S-02. Every spawned task is supervised.** No fire-and-forget
concurrency: every `asyncio.create_task`/`ensure_future` result is held,
awaited, gathered, or lives in a TaskGroup, so some other process is
always positioned to observe its failure (Armstrong §4.3; OTP
supervision). Counter: `unsupervised_spawn_sites` (down, target 0) — roadmap.

**S-03. Exactly one receipt per dispatch; bypass list drains to zero.**
Every production dispatch flows through `invoke_agent()` and emits exactly
one EvidenceReceipt; the failure record must survive the crash (Armstrong
§5.3; Runtime Truth Spine doctrine). Counter: `spine_bypass_entries`
(down, target 0) — **LIVE in ratchet v1** (growth-forbidding only; the
drain itself is `runtime-truth-spine-adoption-2026-06` track work).

**S-04. Put a limit on everything.** Every loop, queue, retry, and wait
has a declared finite bound; intentionally infinite loops are annotated
as such (Power of Ten R1–R3; TIGER_STYLE). Counter: `unbounded_constructs`
(down) — roadmap.

**S-05. Recovery is bounded and escalates.** Every retry loop declares
max attempts and max window and escalates on exhaustion — OTP restart
intensity, not improvised while-loops. Counter: `unbounded_retry_sites`
(down, target 0) — roadmap.

### Tier 2 — proof discipline

**S-06. Assertion density floor.** Average ≥2 side-effect-free,
non-constant assertions per function, asserting both expected and
forbidden states (Power of Ten R5; TIGER_STYLE; SQLite carries 6,754
asserts). Counter: `assert_density_millis` (up) — roadmap.

**S-07. A bug is not fixed until its regression test exists.** Fix
commits land with the test that would have caught them (SQLite §10;
kernel `Fixes:` discipline). Counters: `untested_fix_commits` (down, 0)
and total collected tests (up) — roadmap.

**S-08. No discarded results.** Every non-void return is consumed or
explicitly discarded with justification; the deadliest async form is the
un-awaited coroutine (Power of Ten R7). Counter: `discarded_result_sites`
(down, target 0) — roadmap.

**S-09. Units fit one page.** No function over 70 lines; no module over
500 (Power of Ten R4; TIGER_STYLE 70-line law; CLAUDE.md / SOVEREIGN
axiom A5). Counters: `modules_over_500_lines`, `largest_module_lines`
(down) — **LIVE in ratchet v1**; `functions_over_70` — roadmap.
*Diversity bill: real but small — page-size limits constrain structure,
not approach; ratchet form means no agent is ever forced to refactor old
code, only forbidden to grow the debt.*

**S-10. Crash at the core, validate at the boundary.** Inside the trust
boundary, no defensive fabricated defaults — raise, and let the receipt
carry the diagnosis; at ingress boundaries, validate exhaustively
(Armstrong §4.4 reconciled with SQLite's ALWAYS()/NEVER()).
Counter: `fabricated_default_sites` (down) — roadmap.

### Tier 3 — mechanized honesty

**S-11. Zero-warning baseline, tightening on green.** Pedantic analyzer
settings, findings counted against a git-tracked baseline that only
tightens (Power of Ten R10, tempered by SQLite §12: analyzers are
seatbelts, not search parties — marginal spend goes to dynamic testing).
Counter: `ruff_undefined_or_redefined` (down, target 0) — **LIVE in
ratchet v1** (F821/F811 first: names that do not bind are code that has
never run — the classic LLM-authorship defect); full-ruleset counter is
the v2 widening. *Diversity bill: real for opinionated style rules — keep
the enforced selection on correctness classes (F, E9, B), never on taste.*

**S-12. Records are frozen and versioned.** Every receipt/witness class
is a frozen dataclass carrying `schema_version`; provenance is structured
data, not vibes. One serializer per record type — dual builders that must
agree by hand are forbidden (this killed the old write-receipts digest
integrity). Counters: `unfrozen_record_classes`,
`records_missing_schema_version` (down, 0) — roadmap.

**S-13. The governance surface is stdlib-only.** `scripts/governance/**`
imports nothing outside the standard library: zero dependencies on the
layer that judges everything else (TIGER_STYLE zero-dependency rule).
Counter: `governance_third_party_imports` (hold at 0) — roadmap.

**S-14. Unreachable means proven unreachable.** Branches believed dead
carry `assert_never`/AssertionError, never a silent default, and coverage
confirms they never fire (SQLite ALWAYS()/NEVER() three-build
discipline). Counter: `bare_unreachable_branches` (down, 0) — roadmap.

**S-15. Branch coverage ratchets up on owned surfaces.** Coverage on each
track-owned surface may only rise; SQLite's 100% MC/DC is the asymptote,
the ratchet is the gate. Counter: per-surface coverage ×10 (up) — roadmap.
Today's proxy: `property_test_files` (up) — **LIVE in ratchet v1**.

**S-16. Persistence paths survive injected faults.** Every module writing
receipts/witness/state has a fault-injection test that fails the Nth
write and walks N upward (SQLite §4 anomaly testing) — the failure record
must survive the failure. Counter: `fault_uninjected_io_modules` (down) — roadmap.

**S-17. Every enforced rule names its checker.** A hygiene pattern
reaches advisory/enforced only with a named executable checker — this
document's own admission rule, applied to itself. Counter:
`hygiene_patterns_enforced_or_resolved` (up) — **LIVE in ratchet v1**
(promotions, once made, cannot be silently undone).

## Judgment principles (not mechanizable; govern review)

1. Safety > performance > developer experience — break ties in that
   order, never by convenience (TigerBeetle).
2. Price every gate in agent-diversity cost; prefer a small Draconian
   checker set over a large advisory one (repo doctrine + Holzmann).
3. Static analysis is a seatbelt, not a search party — route marginal
   verification spend to dynamic testing, fuzzing, fault injection
   (SQLite's billion-cases-a-day evidence).
4. Fail immediately, then attempt something simpler: degraded modes are a
   designed hierarchy, not an improvised retry (Armstrong §5.1).
5. If the specification doesn't say what to do, raise — an exception is a
   discovered specification gap, and its payload must isolate the fault.
6. Comments and commit messages explain *why*, never *how*, for a reader
   without the discussion context (kernel process canon).
7. One logical change per patch; every point bisectable; never mix moves
   with changes.
8. Overrides are written arguments: silencing a rule without an argument
   is the anti-pattern; the override log is review material (checkpatch
   tri-level, mapped onto the hygiene lifecycle).
9. When the analyzer is confused, prefer rewriting for clarity — but
   never contort code for the tool (SQLite's warning).
10. Zero technical debt on showstoppers — unbounded growth, latency
    cliffs, exponential complexity are fixed the day they are found.
11. Honest names or delivered guarantees: a thing called `immutable`,
    `append-only`, `redact`, or `rank` either does exactly that or gets
    renamed. Overclaiming names are how ceremony passes for governance.
12. Receipts must have consumers: no record class ships without at least
    one caller that branches on it or renders it. A receipt nobody reads
    is waste wearing a uniform.

(11 and 12 are this repo's own additions — both were cut from live
findings in the 2026-06-12 exemplar audit, not imported from the corpus.)

## What is live today (v1)

`scripts/governance/hygiene/ratchet.py` enforces seven counters:
`ruff_undefined_or_redefined`, `modules_over_500_lines`,
`largest_module_lines`, `silent_exception_swallows`,
`spine_bypass_entries` (down) and `property_test_files`,
`hygiene_patterns_enforced_or_resolved` (up). Baselines:
`docs/governance/hygiene/ratchet_baselines.json`. Run `make
quality-ratchet`; `--explain NAME` shows the evidence behind any number;
QL-R1 is the lifecycle pattern. Everything marked *roadmap* above enters
through the same door: pattern file → detector → baselines → promotion.

## World exemplars (reference reading)

- TigerBeetle `docs/TIGER_STYLE.md` — the living operationalization of
  Power of Ten in a production database; the single best one-file read.
- SQLite "How SQLite Is Tested" + `ALWAYS()`/`NEVER()` in
  `src/sqliteInt.h` — the deepest dynamic-verification regime in the
  world (590:1 test-to-code ratio, ~1B fuzz cases/day).
- Holzmann, "The Power of Ten" (IEEE Computer, 2006) — the founding
  document of mechanical checkability; ten rules, each with a checker.
- Linux `Documentation/process/submitting-patches.rst` +
  `scripts/checkpatch.pl` — provenance as structured data, bisectability
  at planetary scale.
- Armstrong's thesis (2003) ch. 4–5 + OTP `supervisor.erl` — let-it-crash
  and bounded restart intensity: the closest existing doctrine to a
  multi-agent runtime.

## Vision thread

NORTH_STAR and THE_ORGANISM define dharma_swarm as an organism whose
outward action is valid only when rooted in inward coherence. This canon
is the inward-coherence half made mechanical: satya as zero-warning
baselines and honest names; ahimsa as no-swallowed-errors and receipts
that survive crashes; zero-waste as the ratchet that banks every
improvement permanently. The witness-upstream doctrine (GNANI_LODESTONE)
is preserved by construction: these gates fire only on *backsliding* —
they never prescribe how an agent solves a problem, only that the
substrate's floor of verifiable truth must not sink.
