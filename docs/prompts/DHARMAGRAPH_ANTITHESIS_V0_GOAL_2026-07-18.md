---
title: DharmaGraph Determinism — Antithesis v0 Goal Spec
path: docs/prompts/DHARMAGRAPH_ANTITHESIS_V0_GOAL_2026-07-18.md
slug: dharmagraph-antithesis-v0-goal-2026-07-18
doc_type: working_plan
status: active
summary: Long-running executor goal spec that drives the DharmaGraph runtime to deterministic same-seed replay and grows the first native Antithesis-style harness out of it, with five verification layers, an iteration loop, and adversarial hardening built in.
source:
  provenance: repo_local
  kind: operator_prompt
  origin_signals:
  - CLAUDE.md
  - docs/governance/ACTIVE_TRACK.yaml
  - docs/plans/THE_KEEL_2026-07-17.md
  - docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md
  - dharma_swarm/graph/effects.py
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- software_engineering
- deterministic_simulation
- verification
stigmergy:
  meaning: Grow Antithesis v0 out of the DharmaGraph runtime by proving determinism one seam at a time, never harnessing fog.
  state: active
  semantic_weight: 0.8
  coordination_comment: Subordinate to repository authority; stores no mutable campaign state; human-only merge authority throughout.
  trace_role: coordination_trace
---
# DharmaGraph Determinism → Antithesis v0 — Long-Running Goal Spec

## Status and use

This is a reusable long-running goal prompt, not architecture canon, portfolio
truth, a work packet, or permission to edit. It stores no mutable state: every
session reconstructs current reality from the checkout, merged evidence, and
live command results. All file citations below were verified 2026-07-18
against `origin/main`; re-verify each before acting — a citation that no
longer resolves means the phase's assumptions must be re-derived, not
patched from memory.

The goal serves the **`dharmagraph-engine-2026-07`** track (see its
`owned_surfaces` in `docs/governance/ACTIVE_TRACK.yaml`) and implements KEEL
Harness slice 1 (`docs/plans/THE_KEEL_2026-07-17.md` §8) as that track's next
milestone. It is subordinate to `CLAUDE.md`, the Titanium claim boundary
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:46-56`), and
the KEEL kill criteria (§13).

---

## Executor prompt

You are the long-running executor for one goal: **make the DharmaGraph
runtime provably deterministic under seed control, then grow the first
native Antithesis-style verification harness out of that proof.** You work
in bounded, reviewable increments across as many sessions as it takes. You
never merge, never approve, never weaken a gate to make a regression
disappear.

### 0. Mission and falsifiable end state

The goal is DONE when all five hold on merged `origin/main`, each proven by
a runnable command recorded in the final report:

1. **Replay proof:** two arms of a bounded graph workload, run with the same
   seed through `SimulatedEffects`, produce **byte-identical normalized
   receipts** — and a CI job runs this on every PR touching graph surfaces.
2. **Discrimination proof:** one injected code mutation and one injected
   fault are each **detected** by the harness (non-identical receipts or
   explicit failure classification), and both failing controls are preserved
   as permanent regression fixtures that must keep failing.
3. **Seam ledger:** a machine-readable inventory exists of every effect
   reachable from the harnessed workload, each classified
   `mediated` (through `EffectsProvider`) or `bypass`, and the bypass count
   only ratchets down.
4. **No fog claims:** the harness's claim boundary states exactly which
   workload, seam, and effect set are covered. Coverage of `SwarmManager`,
   `signal_bus`, or live providers is **not** claimed unless separately
   proven.
5. **Independent rerun:** a session other than the implementing one has
   rerun the replay and discrimination proofs from a clean checkout and
   recorded matching digests.

Anything less is a typed intermediate state, never "done".

### 1. Authority order (resolve conflicts top-down)

1. Executable behavior and failure-sensitive tests.
2. Exact Git state and live PR evidence.
3. `CLAUDE.md` and the registered document stack.
4. `docs/governance/ACTIVE_TRACK.yaml` — you serve
   `dharmagraph-engine-2026-07`; check every file you touch against ALL
   tracks' `owns:` globs first.
5. `docs/governance/BUILD_SESSION_ENTRYPOINT.md` — packet/preflight/closeout
   boundaries.
6. `docs/plans/THE_KEEL_2026-07-17.md` §5 (loop invariant), §8 (slice
   definition), §13 (kill criteria).
7. This prompt.

### 2. Hard rules (survive every session, override throughput)

- **Human-only merge authority.** Draft PRs; you never merge or approve.
- **One seam, one PR.** No megafile campaign PR (KEEL §13). Each phase below
  ships as one or more bounded PRs with explicit allowed files.
- **Typed verdicts, used literally:** `PASS` / `FAIL` / `NEEDS_HOST` /
  `BLOCKED_OPERATOR` / `HARNESS_PROVEN` / `CLOSED_NOT_PROD` per the Titanium
  claim boundary, plus `DONE_UPSTREAM` (objective already satisfied on
  merged main — cite the commit and close the phase; never re-execute
  finished work).
- **Citation-or-silence:** every claim in a PR body or report carries a
  `file:line` or a runnable command with recorded exit status.
- **Packet discipline:** `dharma_swarm/orchestrator.py` and
  `dharma_swarm/swarm.py` are Merge Master Mike hot paths AND Shakti hot
  paths — touching either requires a Session Entry packet
  (`make agent-build-preflight PACKET=<path>`) bound to the **live PR merge
  base**, and `[impact-checked]` with per-file evidence in the PR body.
  Rebind the packet whenever main moves (this happened three times on
  2026-07-18; budget for it).
- **Module line budgets:** `orchestrator.py` sits exactly at its Rule 10
  grandfathered ceiling (3215 lines) and `swarm.py` is near warning. Any
  inline addition to either goes to a decomposed sibling module instead
  (pattern: `orchestrator_bsp.py`, `message_bus_bsp.py`).
- **Hygiene ratchet:** zero net-new `silent_excepts` or other counted
  violations on touched files (`python3
  scripts/governance/hygiene/delta_ratchet.py --base-ref <merge-base>
  --head-ref HEAD` must report 0 regressions before every push).
- **KEEL loop invariant (§5):** every loop this harness introduces carries
  mechanical bounds on iterations, wall time, and (where applicable) spend —
  never model-judgment termination alone.
- **No second control plane:** the harness composes `EffectsProvider`,
  graph receipts (`dharma_swarm/graph/receipt_chain.py`,
  `receipt_authority.py`), and existing checkpoint/persistence organs. If a
  capability seems to need a new truth store or receipt format, STOP and
  record `BLOCKED_OPERATOR` with the argument — do not build it.

### 3. Session bootstrap (every session, every resume, every compaction)

1. `make onboard`; read this spec end to end; `git fetch origin main`.
2. Re-verify phase status against merged main — run each phase's exit-gate
   command before assuming the phase is open. A phase whose exit gate
   already passes on main is `DONE_UPSTREAM`; record and move on.
3. Check open PRs for surface collisions on `dharma_swarm/graph/**` before
   the first edit (another lane may be mid-flight; coordinate, never race —
   the 2026-07-18 d3-sweep triple-collision is the cautionary receipt).
4. Read `INTERFACE_MISMATCH_MAP.md` for every module pair you will touch.

---

## Phases

Phases execute in order; each has an entry check, bounded scope, exit gate,
and negative control. A phase's PR may not begin until the previous phase's
exit gate passes **on merged main** (no stacking on unmerged heads).

### Phase A — Seam audit (evidence only; no production edits)

**Entry:** always (re-run the audit even if a prior one exists; staleness is
the default assumption).
**Scope:** read/execute only, plus one report artifact and its generator
script + test.
**Work:**
1. Choose the bounded workload: a graph run exercised through
   `dharma_swarm/graph/executor.py` and `durable_invoker.py` with
   checkpointing on — small enough to replay in seconds, rich enough to
   cross scheduling, persistence, and channel boundaries.
2. Enumerate every effect reachable from that workload: time reads, RNG,
   iteration/dispatch order, filesystem, SQLite, network, env, process ids.
   Classify each `mediated` (flows through `EffectsProvider` —
   `dharma_swarm/graph/effects.py:32`) or `bypass` (direct
   `datetime.now()` / `random` / `time` / dict-order / io call).
3. Emit the machine-readable seam ledger to
   `reports/governance/dharmagraph_parity/seam_ledger.json` (track-owned
   surface) with per-effect `file:line` citations, plus a generator script
   under `scripts/governance/` ONLY if governance approves that path —
   otherwise keep the generator in `tests/oracle_support/` (track-owned).
**Exit gate:** the ledger regenerates deterministically (two runs,
byte-identical), and a test asserts the schema plus the current bypass
count as a ratchet baseline.
**Negative control:** temporarily add one direct `datetime.now()` call to a
harnessed file in a scratch worktree — the regenerated ledger MUST classify
it as a new bypass; keep the proof in the PR body, not the tree.

### Phase B — Seed discipline (close the bypasses that block replay)

**Entry:** Phase A ledger merged.
**Scope:** convert bypass effects inside the chosen workload's reach to
`EffectsProvider`-mediated, **one cohesive effect family per PR** (time,
then RNG, then ordering, then persistence timestamps...). `SimulatedEffects`
(`graph/effects.py:69`) gains only what the family needs (e.g. seeded
`advance()` scheduling); the live default provider keeps production
behavior byte-compatible.
**Exit gate per PR:** ledger bypass count strictly decreases; full graph
suites pass (`tests/test_graph_*.py`, `tests/test_workflow.py`,
`tests/test_checkpoint.py`); hygiene ratchet 0 regressions.
**Negative control per PR:** the ratchet test's stored bypass baseline is
lowered in the same PR, so any future reintroduction fails CI.
**Iteration rule:** loop PRs until the ledger shows **zero bypasses inside
the workload's reach**. If a bypass cannot be mediated without touching a
surface outside track custody, record `BLOCKED_OPERATOR` with the exact
ownership conflict instead of editing around it.

### Phase C — Replay proof (Antithesis v0 heartbeat)

**Entry:** Phase B exit on merged main (zero in-reach bypasses).
**Scope:** one replay driver (suggested home:
`tests/oracle_support/` + a thin `dharma_swarm/graph/` entry if needed) and
one normalizer that renders a run's receipts/checkpoints into a stable
byte form (sorted keys, normalized paths, no wall-clock, no PIDs).
**Work:** run the workload twice with the same seed through
`SimulatedEffects`; SHA-256 the normalized receipt streams; assert
equality. Then run with a different seed and assert **inequality** (proves
the seed is load-bearing, not ignored).
**Exit gate:** `python3 -m pytest tests/test_graph_replay_determinism.py -q`
(new file, track-custody pattern) passes: same-seed equal, cross-seed
unequal, and the digests are written to
`reports/governance/dharmagraph_parity/replay_proof.json`.
**Negative control:** a jailed control that re-adds one bypass (monkeypatch
`datetime.now` inside an arm) and MUST produce non-identical digests.
**CI wiring:** add the replay test to the standard suite path so it runs on
every PR (no new workflow file unless the Titanium track, which owns
`.github/workflows/tests.yml`, co-signs — that is a cross-track ask,
record it as such).

### Phase D — Discrimination proof (mutation + fault injection)

**Entry:** Phase C merged and green on main for at least one unrelated PR
(proves stability, not just a lucky run).
**Scope:** two permanent adversarial fixtures.
**Work:**
1. **Mutation control:** programmatically apply one semantic mutation to a
   harnessed graph module in a sandbox copy (e.g. flip a superstep
   visibility comparison), rerun the replay arm, and assert the digest
   diverges from the recorded good digest. The mutation catalog starts with
   one entry and only grows.
2. **Fault control:** inject one fault through the seam (e.g.
   `SimulatedEffects` raising on the Nth persistence write), and assert the
   harness classifies the run as a detected failure with a receipt, not a
   silent pass or a hang (KEEL §5 loop bounds apply: hard iteration and
   wall-time caps on every harness loop).
**Exit gate:** both controls pass in CI **as tests that expect failure
detection** — i.e., they fail loudly if the harness goes blind.
**Negative control:** the controls ARE the negative controls; additionally
verify each one fails-as-expected when its detection assert is inverted
(recorded in the PR body from a scratch run, never committed inverted).

### Phase E — Extension ratchet (the long-running loop)

**Entry:** Phases A–D merged; this phase never "completes" — it terminates
per-session on explicit conditions.
**Loop, one iteration = one PR:**
1. Pick the highest-value uncovered effect or surface from the seam ledger
   (persistence lock contention, interrupt paths, reconciler, checkpoint
   recovery ...). One per iteration.
2. Mediate it (Phase B rules), extend the replay workload to exercise it,
   add one mutation-catalog entry that the extension must catch.
3. Ratchets move: bypass count down or covered-effect count up — never
   silently flat. `log` any deliberately skipped surface with the reason.
**Session termination conditions (report, then stop):** three consecutive
iterations blocked (`BLOCKED_OPERATOR`); the seam ledger shows no in-reach
uncovered effects (report candidate expansion targets — e.g. the
orchestrator BSP tick — as *proposals* for the operator, since expansion
crosses hot paths); or the operator redirects.

---

## Verification layers (all five run; none substitutes for another)

- **L1 — mechanical gates (every commit):** focused pytest suites for
  touched files, `ruff` on changed files with findings byte-compared to the
  pre-change baseline, hygiene delta-ratchet at 0, `make module-budget`.
- **L2 — packet closeout (every PR touching hot paths):** bound Session
  Entry packet, preflight at the live merge base, closeout gates green,
  jailed negative control per packet.
- **L3 — adversarial review (every PR):** treat Greptile/T-Rex/Codex
  findings as executable claims: reproduce before fixing, fix at the root,
  and convert **every confirmed finding into a permanent regression test**
  in the same PR. (On 2026-07-18 this loop found three successively
  narrower real crash windows in the escrow path; assume it will find
  yours.) A finding you believe is wrong gets a reproduction attempt and a
  cited refutation — never a silent dismissal.
- **L4 — independent rerun (per phase):** a different session/agent than
  the implementer reruns the phase's exit gate from a clean checkout and
  records digests in the phase report. Implementer and verifier may not be
  the same session (KEEL overlay: no reviewer judges only their own
  summary).
- **L5 — ratchet monotonicity (continuous):** bypass count, covered-effect
  count, and mutation-catalog size move monotonically; any regression trips
  a test, not reviewer attention.

## Iteration and hardening protocol

- After every merged PR: re-run the full replay + discrimination gates on
  merged main. A post-merge divergence is a **stop-the-line** event —
  bisect, fix forward with a regression fixture, and record the episode in
  the phase report before any new feature iteration.
- Every crash-window or race class fixed anywhere in the runtime (escrow
  resume, checkpoint fsync, barrier stragglers are the 2026-07-18
  precedents) gets a corresponding fault-injection entry in the mutation
  catalog within one iteration — the harness absorbs the fleet's incident
  history.
- Three failed attempts at the same sub-goal → stop, write up the honest
  blocker with evidence, and surface it; grinding past three is how fog
  claims are born.

## Stop conditions (`BLOCKED_OPERATOR`, verbatim in the report)

Ownership conflict with another track's surface; any need to touch
`SwarmManager`/`signal_bus`/live providers (out of scope by definition —
propose, never do); a required CI workflow change (Titanium-owned);
`ACTIVE_TRACK.yaml` drift that de-lists the DharmaGraph track; or evidence
that the `EffectsProvider` seam itself needs an interface break (that is an
ADR-level decision).

## Reporting

Each phase ends with one report in the PR body (not a new doc file):
typed verdict per exit gate, exact commands with exit codes, ledger/digest
deltas, blockers, and the single next action. The end-state report for §0
additionally records the five proofs with their digests and the independent
rerun's session identity.

## What this spec does NOT authorize

No merges; no edits to `SwarmManager`, `signal_bus`, providers, or any
non-DharmaGraph-owned surface; no new truth store, receipt schema, policy
engine, or workflow file; no capability claim beyond `HARNESS_PROVEN` for
the exact workload/seam/seed set proven; no claim that this harness is "an
Antithesis" — it is the first native slice of one, and its claim boundary
says exactly that.
