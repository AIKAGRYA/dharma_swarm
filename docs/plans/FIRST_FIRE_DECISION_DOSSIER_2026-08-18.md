# First Fire Decision Dossier — 2026-08-18

**Doc role:** plan / decision-support. **Authority: none** — every decision named
here belongs to the operator. Subordinates to: `docs/vision_maps/NORTH_STAR.md`,
issue #1293 (Machine-Payable Wayfinder map), `docs/governance/ACTIVE_TRACK.yaml`.

**Provenance:** produced by a two-round adversarial debate (2026-08-18,
operator-directed): a proponent case grounded in repo citations, attacked by an
independent agent with repo file:line evidence, live test runs, and external
research; amended; then re-verified. Positions below are only what survived.
The original case's refuted claims are recorded in §5 per citation-or-silence.

---

## 1. The three propositions, as they survived

### P1 — FIRE: one live Darwin evolution cycle (AMENDED, direction confirmed)

One operator-invoked, receipted, human-merged live self-application of an
evolution proposal. This is the repo's own named gap: Loop 3 is
"HARNESS_PROVEN; not CLOSED_LIVE" (`CYBERNETIC_LOOP_MAP.md:84`), and the
broken register records 0 applied markers ever
(`docs/state/BROKEN_REGISTER.md:57`, BR-003).

**Fire conditions (all required):**
- #1149 merged as **option (b)**: `evolve auto --live` single bounded cycle
  only; daemon live-mode out of scope until promotion packets carry
  per-proposal digest, expiry, and single-use nonce (open review thread on
  #1149, deliberately unresolved).
- Fire runs **non-root** (root defeats the 0o500 read-only protections —
  `tests/test_evolution_safety.py:398` fails under root).
- Fire runs inside a **marked scratch worktree** with a **hand-granted lease**
  (`dharma_swarm/evolution_safety.py:222-228, 291-309`;
  `forge_lab/worktree.py:39`), never a live checkout — the fail-closed
  substrate denies protected roots outright, which is correct.
- The diff is restricted to **non-test production files**, and the suite runs
  in the **Docker sandbox**, because the test phase executes the applied
  diff's code unsandboxed today (`dharma_swarm/diff_applier.py:394-400`) and
  rollback restores files, not side effects (`diff_applier.py:349-364,
  404-458`).
- Target: trivial and reversible; the value is the closed loop, not the diff.
- Human merge is the final authority.

**Wiring gaps that must land first (adversary-verified, all mechanical):**
- **Gap A — workspace threading:** `auto_evolve` accepts no workspace and the
  apply path defaults to `Path.cwd()` (`dharma_swarm/evolution.py:3245-3258,
  2541-2549`; `diff_applier.py:192`). Add explicit `--workspace` threading so
  the fire target is receipted, not cwd-dependent.
- **Gap B — lease enforcement:** nothing on the `evolve auto --live` apply
  path consults `evaluate_mutation`; only `forge_lab/experiment.py:169` and
  `self_improve.py:397` do. Wire the lease check into the apply path or label
  the lease unenforced.
- **Gap C — Docker execution:** `apply_in_sandbox` hardcodes `LocalSandbox`
  (`evolution.py:2474-2479`); DockerSandbox is unselectable on this path.

Timeline claim: **when these preconditions land** — not "days".

### P2 — WIRE #2: public Brier-scored forecast ledger; trading contract written now, capital later (AMENDED)

The original micro-capital-crypto proposal is **broken** and replaced:
- At $500 on Kraken's base tier, fees alone consume ~7-12% of capital per
  month, and 30 days of micro P&L cannot statistically distinguish skill from
  noise (Bailey & López de Prado, Probabilistic Sharpe Ratio / MinTRL,
  SSRN 1821643). The "daily external grade" the wire was meant to buy does
  not exist at that size.
- The operator is a **US citizen**: every crypto disposal is a taxable event
  (property treatment; broker 1099-DA reporting from 2025 transactions), and
  if Japan-resident, Kraken does not serve Japan (JFSA deregistration
  effective 2023-01-31) and Japan taxes resident crypto gains as
  miscellaneous income at up to ~55% with no loss carryforward.
- The built engine is overnight-hold Brier-scored forecasting, which never
  triggers the pattern-day-trader rule — the case's crypto-over-equities
  ground was void.

**What replaces it, in order:**
1. **Public timestamped forecast ledger (start immediately).** The swarm
   publishes falsifiable market forecasts; reality grades them daily. Fed by
   `dharma_swarm/ginko_brier.py` + `ginko_data.py` (free-tier data) through
   `dharma_swarm/revenue/wedge_pipeline.py` (tests pass: 9/9,
   `tests/test_revenue_wedge_pipeline.py`), published via Darshan desk 5
   ("Field Notes from the Swarm", `docs/plans/DARSHAN_CHARTER_2026-07-12.md`).
   Timestamping: commit each ledger row to the public repo **and** anchor its
   SHA-256 with OpenTimestamps (free; Merkle-aggregated into a Bitcoin block;
   `.ots` proofs third-party-verifiable) — git timestamps alone are
   self-asserted and rewritable. Cost: $0. Taxable events: 0. External,
   daily, uncharmable.
   - **Known blocker:** `wedge_pipeline.py:179-182` invokes BR-007
     `store_sync`, which carries an OPEN operator instruction not to
     re-enable it (`docs/state/BROKEN_REGISTER.md:34, 48`). The ledger loop
     must run steps 1-3 and skip/flag the sync step (small code edit, to be
     bound to the darshan track's next-items), or BR-007 must be closed first.
2. **Graduation contract (write now, costs nothing).** This is #1293
   destination item 3. Written wire-parameterized (the map says the wire
   choice is still fog), with four mandatory sections: a
   residency-determined venue gate (Alpaca equities path if US-resident;
   JFSA-registered venue or no-go if Japan-resident), a US-citizen
   tax/reporting section, a statistical-honesty clause (micro-live P&L
   measures operational plumbing only, per MinTRL), and a named track slot.
3. **Live capital last**, behind: map completion (#1293: "Arming and building
   are downstream of this map"), the paper-first progression already in the
   codebase ("6-month paper trading proving Sharpe > 1.5" —
   `dharma_swarm/telos_substrate.py:683-694`), and the operator trust gate
   (`docs/vision_maps/NORTH_STAR.md:144-168`).

**Track slot:** the portfolio is at `max_active: 10`
(`docs/governance/ACTIVE_TRACK.yaml:80`). PR #1213 (helm closure,
human-merge-only) frees a slot its own body binds to
`revenue-external-humans-served`. The slot exists only after a human merges
it. CashClaw remains what the map says: an unresolved operator classification
question, preconditioned on making its push-token human gate real.

### P3 — PUBLISH ONLY (arena-as-fitness dropped; publishing sustained)

The "wire arena scores into Darwin's fitness" half is **dead**: the frozen
arena is 24 fixture tasks with sealed answers in plaintext in the same source
file (`dharma_swarm/coordination/arena/taskpack.py:46-74`), scored against
canned fixtures (`fixtures.py:1-19`) — trivially Goodhartable and exhaustible;
and the arena-as-fitness loop already exists for the only object it can grade
(orchestration genomes, `orchestrator_v1.py:1-12`, under a non-negotiable that
it never mutates production). Darwin's code gradient remains pytest + gates.
Any future capability gradient is a new sealed task bank — a separate,
honestly-labeled operator decision.

Publishing arena/Frontier Ledger results through Darshan desk 5 **stands**,
with the framing constraint: the published register is "deterministic routing
harness over fixture tasks," never "capability benchmark" (Darshan charter,
Register Discipline). Ledger artifacts live in `reports/darshan/**` (already
darshan-owned); the darshan track must be TTL-re-verified before carrying the
deliverable (currently 7 days past its 30-day TTL).

---

## 2. The three operator decisions (everything else is mechanical)

1. **Merge #1149 as option (b)?** (Restrict live mode to single-cycle
   `auto --live`; daemon live-mode waits for single-use packets.)
2. **Merge #1213?** (Closes the helm track; frees the track slot that its own
   body reserves for revenue.)
3. **Pick the first wire** for the graduation contract per #1293 (or ratify
   the wire-parameterized draft and defer the pick).

## 3. The mechanical punch list (no decisions required)

- P1 Gaps A/B/C (workspace threading, lease enforcement on the apply path,
  Docker execution on the apply path).
- Ledger loop: BR-007-safe wedge pipeline invocation; OpenTimestamps stamping;
  first published forecast page under `reports/darshan/**`.
- Darshan track TTL re-verification.
- Graduation contract draft (wire-parameterized).

## 4. What each proposition buys (the falsifiable criteria)

- P1: one merged-to-main commit proposed/gated/sandbox-tested/applied/receipted
  by the engine, human-merged. Zero → one.
- P2: ≥30 consecutive days of publicly timestamped, Brier-scored forecasts
  with receipts; the market as the swarm's first uncharmable external grader.
- P3: the first Darshan piece with numbers nobody else can publish, honestly
  framed.

## 4b. Round 3 — outside-agent review (2026-08-18, operator-relayed): converged

An independent outside agent with live-host access reviewed the case and broke
it further. Its tree-checkable claims were verified verbatim in this checkout
and are conceded:

- **Empty diff scores as a perfect pass:** `apply_diff_and_test` returns
  `{"pass_rate": 1.0, "skipped": True}` for a blank diff
  (`dharma_swarm/evolution.py:2379-2380`) — a mis-wired fire can print a green
  receipt while applying nothing. A valid fire receipt must therefore assert
  a non-empty diff hash AND `applied: true`.
- **Tier-1 judging is worse than charmable — one score is a tautology:**
  `dharmic_alignment` is set directly from the gate decision
  (`ALLOW → 0.8`, `evolution.py:1680-1685`).
- **The default grind targets are the constitution and the judge:**
  `_GRIND_EVOLUTION_TARGETS` = swarm.py, orchestrator.py, evolution.py,
  self_improve.py, fitness_predictor.py, … (`orchestrate_live.py:1248-1253`).
  "Non-test production files" is therefore an insufficient firewall; first
  fires are restricted to a designated toy module nothing in production imports.
- **Host-state claims** (megha at halt, swap-full; May 2026 shadow-apply as a
  prior wrong-kind fire) come from the reviewer's live access and are accepted
  on its record, which was accurate everywhere checkable.

**The converged fire spec (both sides now endorse the identical act):**
1. Runner: CI or a scratch worktree — never the halted production host.
2. Path: `apply_diff_and_test` on a NON-EMPTY diff, named function and flags
   in the command packet — not `auto_evolve` shadow (which strips diffs) and
   not the promotion-refusal path.
3. Target: a designated toy module that nothing in production imports.
4. Order of proof: planted red first (watch rollback actually fire), then the
   real green.
5. One-shot mechanical fuse: no second apply without a new human-dated grant;
   receipt invalid unless diff-hash non-empty and `applied: true`.
6. PR opened; the operator merges. **Fire 1 is a plumbing receipt — it proves
   the applier, tests, rollback, and human merge compose. It is not evidence
   that evolution works.** That evidence can only come from the Tier-2
   external basket, which is currently empty and must be said to be empty.

Ledger amendments also accepted: price the model-token cost line (near-zero,
not zero); "publish" is its own operator yes under the external-receipt rule;
pre-committed kill date (N days with no edge → stop publishing, no prompt
enrichment). Host: resize is a halt-state decision on its own merits, never a
fire decision.

**Standing operator decision after convergence: approve the amended fire
(CI/scratch, toy module, one-shot fuse, planted-red-then-green) — yes or no.**

## 5. Corrections record (claims of the original case refuted in debate)

- "96 dryruns" — trace artifact; the register found 9 dryrun dirs, 0 applied
  (`BROKEN_REGISTER.md:57`). The zero-applications thesis stands; the count was wrong.
- "Darshan 37+ days past TTL" — it is 37 days *old* against a 30-day TTL: 7 days past.
- "9 of 10 tracks serve substrate-nativeness" — 8 of 10.
- "Telos gate battery protects the fire" — Tier-C gates are keyword-charmable
  (`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`); the real controls
  are the root guard, the test suite, and the human merge.
- "Crypto over equities because of PDT" — void for an overnight-hold strategy.
- "capital_lab is the most-built option" — the evidence/paper stack is built
  and its tests pass; the live execution stack is 0% built
  (`dharma_swarm/capital_lab/broker_paper_membrane.py:1-6`, `LIVE_READINESS=0`).
