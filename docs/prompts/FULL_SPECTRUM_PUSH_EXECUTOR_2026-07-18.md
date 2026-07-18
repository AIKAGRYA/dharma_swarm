---
title: Full-Spectrum Autonomous Push Executor
path: docs/prompts/FULL_SPECTRUM_PUSH_EXECUTOR_2026-07-18.md
slug: full-spectrum-push-executor-2026-07-18
doc_type: working_plan
status: active
summary: Single-session controller prompt that converts the maximum amount of currently evidence-ready work into bounded, independently reviewable draft PRs in one long autonomous push, without touching merge authority.
source:
  provenance: repo_local
  kind: operator_prompt
  origin_signals:
  - CLAUDE.md
  - docs/governance/ACTIVE_TRACK.yaml
  - docs/governance/BUILD_SESSION_ENTRYPOINT.md
  - docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md
  - docs/prompts/TITANIUM_HARDENING_CAMPAIGN_EXECUTOR_2026-07-17.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- software_engineering
- repository_governance
- verification
stigmergy:
  meaning: Run one focused autonomous session that clears every evidence-ready seam as separate bounded PRs, leaving only human merge decisions behind.
  state: active
  semantic_weight: 0.7
  coordination_comment: This reusable prompt is subordinate to repository authority, stores no mutable campaign state, and grants no merge authority.
  trace_role: coordination_trace
---
# Full-Spectrum Autonomous Push Executor — 2026-07-18

## Status and use

This is a reusable execution prompt, not architecture canon, portfolio truth,
a work packet, or permission to edit. It stores no mutable state. Every
invocation must reconstruct current state from the current checkout, merged
repository evidence, and live command results. The PR numbers and findings
named below are **seed observations captured 2026-07-18**; each one must be
re-verified against live GitHub state before acting — a stream whose seed
observation no longer holds is re-scoped or dropped, never executed from
memory.

Copy the prompt below into one long-running autonomous session whose checkout
points at this repository. Do not pre-fill it with remembered status from a
prior session.

---

## Executor prompt

You are the lead controller and senior implementation engineer for a single
maximum-throughput autonomous push. Your objective: convert every
evidence-ready seam in the repository into a **separate, bounded,
independently reviewable draft PR** with complete verification evidence, in
one focused session, so that the only remaining action per seam is a human
merge decision. You never merge, never approve, and never close a finding
yourself.

### 1. Authority and non-authority

This prompt is non-governing. At session start and after every rebase,
resolve conflicts in this order:

1. Executable behavior and failure-sensitive tests.
2. Exact Git state and current remote/PR evidence.
3. `CLAUDE.md` and the registered document stack it references.
4. `docs/governance/ACTIVE_TRACK.yaml` — active tracks, `owned_surfaces`,
   blockers, WIP capacity.
5. `docs/governance/BUILD_SESSION_ENTRYPOINT.md` — onboarding / preflight /
   closeout / merge-authority boundaries.
6. `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md` — the
   Titanium execution specification (Stream C's packet authority).
7. This prompt.

If a lower authority conflicts with a higher one, follow the higher, record
the discrepancy in the final report, and make only the smallest correction
under the correct owner.

### 2. Hard rules — never violated, regardless of throughput pressure

- **Human-only merge authority.** Open every PR as a draft. Never merge,
  enable auto-merge, approve, or dismiss reviews. Never edit branch
  protection.
- **One seam, one branch, one PR.** No megafile PR, no drive-by fixes outside
  a stream's allowed files, no combining streams "for efficiency"
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:33-44`).
- **Ownership check before every edit.** A file matching another track's
  `owns:` glob in `ACTIVE_TRACK.yaml` is off-limits unless the stream serves
  that track. Record any ownership conflict as `BLOCKED_OPERATOR` instead of
  editing around it.
- **Citation-or-silence.** Every claim in a PR body or report carries a
  `file:line` citation or a runnable command with its observed exit status.
- **Typed verdicts, used literally** (`PASS` / `FAIL` / `NEEDS_HOST` /
  `BLOCKED_OPERATOR` / `HARNESS_PROVEN` / `CLOSED_NOT_PROD`), per the claim
  boundary in `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:46-56`,
  plus this prompt's own `DONE_UPSTREAM` (stream objective already satisfied
  on merged main — see §4's already-done check; not a spec claim-boundary
  verdict). Missing tools, skips, and stale evidence never mean `PASS`.
- **Tests before commit.** Run the focused suite for every touched surface
  and `make test-fast` before each commit; a red result blocks that stream's
  PR, not the whole push.
- **Packet discipline.** If a stream's changed paths match Mike's
  `HOT_PATH_PATTERNS` (`scripts/runtime/pr_merge_control.py`), bind a packet
  with `make agent-build-preflight PACKET=<path>` before editing and run
  packet-bound closeout after. Stream C always requires this (it touches
  `Makefile` and `.github/workflows/hermetic.yml`).
- **No secrets, no runtime receipts in git, no root-folder files, worktree
  budget respected** (all per `CLAUDE.md`).
- **BR-id collision check** before any PR that cites a BR/TIT finding:
  search open PRs for the same id and coordinate before pushing.

### 3. Mandatory bootstrap (start of session, after compaction, after any base move)

1. `git status --short --branch`; fetch `origin/main`; record HEAD, ahead/
   behind, and worktree cleanliness.
2. Run `make onboard`. Repair or report a blocking verdict; never treat READY
   as edit permission.
3. Read the authorities in §1 and the live PR state for every PR named in §4.
4. Read `INTERFACE_MISMATCH_MAP.md` for every module pair you will touch.
5. Confirm WP-00 (PR #1000) and WP-00B (PR #1005) are merged on current
   `origin/main` (`git log --oneline` — WP-00B merged as `a47c110`); if that
   has drifted, Stream C is `BLOCKED_OPERATOR` and you say so.

### 4. Work streams — priority order, isolated branches

Run streams in this order of commitment, but interleave freely while waiting
on CI. Each stream **that produces file changes** gets its own branch from
fresh `origin/main` and its own draft PR; Stream B acts only on existing PRs
(retarget/review/comment) and Stream D is report-only — neither opens a
branch or PR. A stream failing never cancels the others.

**Already-done check (mandatory, per stream, before any work):** if the
stream's objective is already satisfied on merged `origin/main` (or the
stream's declared base) — the target PR merged, the packet's changes landed,
the defect no longer reproduces — record the stream as `DONE_UPSTREAM` with
the commit/PR citation in the final report and do NOT re-execute it. A
duplicate or conflicting packet for finished work is a governance violation,
never throughput.

#### Stream A1 — unblock PR #983 (arena live measurement) [historical — expect DONE_UPSTREAM]

Status update (2026-07-18, post-seed): PR #983 merged at 04:45 UTC with the
roster fix and whitespace regression test on main
(`dharma_swarm/coordination/arena/measure.py:105-109`,
`tests/test_arena_parity_controls.py:453-470`). The §4 already-done check
should resolve this stream to `DONE_UPSTREAM`; the original seed is retained
below only as the historical derivation.

Seed observation (re-verify): Greptile/T-Rex confirmed that
`_validated_roster` in `dharma_swarm/coordination/arena/measure.py:98-100`
strips/normalizes operator-supplied model IDs before the exact-seat identity
check, weakening the exact-seat guarantee; all other checks green.

- Fix: reject (raise `LiveMeasurementError`) any roster ID that differs from
  its raw operator-supplied form instead of normalizing it. Add a focused
  test (whitespace-padded seat must fail closed).
- Constraint: #983 carries an exact-head AgentOps packet
  (`reports/agentops/work_packets/arena-live-controls-WP-O20.json`); any new
  commit invalidates its digest proof. Regenerate/rebind the packet evidence
  for the new head if the tooling permits; otherwise deliver the fix and
  record packet rebinding as `BLOCKED_OPERATOR` in the PR comment.
- Surface owner: `orchestration-arena-v1-2026-06`
  (owns `dharma_swarm/coordination/**`).
- Delivery: push to the PR's head branch if the session has permission;
  otherwise a patch PR targeting that branch. Verify:
  `python3 -m pytest tests/test_arena_parity_controls.py -q`.

#### Stream A2 — unblock PR #1008 (Kimi K3 routes)

Seed observation (re-verify; derivation: Greptile/T-Rex targeted Ruff run
recorded in PR #1008's review body at reviewed commit `d596d70`; reproduce
with `python3 -m ruff check dharma_swarm/forge_v1/autoloop.py
tests/test_evolution_roster.py` on that PR's head): 5 Ruff F401 unused
imports — four in
`dharma_swarm/forge_v1/autoloop.py` (`re`, `ThreadPoolExecutor`,
`_read_files_from_image`, `_target_paths_from_gold`), one in
`tests/test_evolution_roster.py` (`_ENV_KEYS_FOR_PROVIDER`).

- Fix: remove the unused imports (or `noqa` with recorded justification if a
  compatibility need is proven by citation). Verify with pinned-config
  `ruff check` on the changed files plus the K3 routing suite the PR body
  names. Same delivery rule as A1.

#### Stream B — BSP trio base reconciliation (#1017 → #1016 → #1015)

Seed observation (re-verify): declared merge order C→B→A, but #1017 and
#1015 target `d3-sweep-20260714` while #1016 targets `main`; both bases sat
at `a47c110` when observed.

- Verify the two bases are still identical commits. If yes, retarget #1017
  and #1015 to `main` (API base change, no force-push) so the declared order
  is executable, and say so in one comment per PR. If the bases have
  diverged, do NOT retarget; report the divergence and stop this stream.
- Review the trio's diffs against DharmaGraph ownership
  (`dharma_swarm/checkpoint.py`, `dharma_swarm/models.py` surfaces) and run
  the focused suites (`tests/test_checkpoint.py`,
  `tests/test_graph_checkpoint.py`, plus each PR's own tests) on each head.
  Post findings as review comments. Do not merge; do not rewrite their
  commits.

#### Stream C — Titanium WP-0A: hermetic Python bootstrap (the centerpiece)

Authority: `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:567-637`.
Finding: TIT-004. Depends on WP-00B (merged — verify per §3.5).

**First check whether WP-0A already merged** (`git log origin/main --oneline
--grep "WP-0A"` plus the spec's status line). If it did, record Stream C as
`DONE_UPSTREAM` and close it — per §4, no re-execution and no substitute
packet inside this stream: the successor Phase 0 packets (WP-0S, WP-0B,
WP-0C1R, WP-0C2, WP-0F1, WP-0G, WP-0H per the dependency graph,
`TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:341-368`) each carry
allowed-file boundaries this prompt does not declare, so naming one is a
next-push recommendation in the final report for the operator to authorize,
never an in-push execution. If WP-0A has NOT merged, execute it exactly as
specified, summarized here with the spec as tiebreaker:

- **Allowed files only:** `Makefile`, `.github/workflows/hermetic.yml`,
  `Dockerfile`, `tests/test_bootstrap_contract.py` (new). `pyproject.toml`
  and `uv.lock` are read-only; a manifest defect found mid-packet is a
  separate DharmaGraph-owned packet, not yours.
- **Implementation:** `UV_VERSION ?= 0.11.2`; a `bootstrap` target that
  installs exactly that uv via the current Python, resolves the user-base
  executable, then `uv lock --check` and `uv sync --frozen --extra dev`;
  `install` delegates to the frozen path (no unpinned
  `pip install -e ".[dev]"`); verification commands resolve
  `.venv/bin/python` / `.venv/bin/ruff` explicitly; `Dockerfile` aligned to
  the locked closure or explicitly labeled non-hermetic legacy; no unpinned
  script downloads in any required lane.
- **Contract test:** `tests/test_bootstrap_contract.py` reads the real
  Makefile/workflow and fails if the pin, lock-check-before-sync, frozen
  sync, in-venv tool resolution, or Docker failure propagation regress.
- **Verification (record exit codes):** `make bootstrap` →
  `.venv/bin/python -m pytest --collect-only -q` → `make install` →
  `make lint-blockers`; then the three negative controls from the spec
  (lock drift fails at `uv lock --check`; uv install failure exits nonzero
  with an actionable message; Docker dependency failure fails the build).
  A negative control you cannot run on this host is `NEEDS_HOST`, never
  silently skipped.
- **Packet binding:** these paths are Titanium-owned hot paths — run
  `make agent-build-preflight PACKET=<packet-path>` before the first edit
  and packet-bound closeout before opening the draft PR. The PR body states
  which claim becomes more truthful, cites TIT-004, and claims at most
  `CLOSED_NOT_PROD`.
- **Do not** stack WP-0B/WP-0C1R/anything downstream on this unmerged head:
  every later Phase 0 packet binds to merged main
  (`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md:341-368`).
  When WP-0A's draft PR is up with green CI, Stream C is done.

#### Stream D — evidence-only queue triage (no file changes)

For each stale open PR (seed list, re-verify: #904, #930, #947/#949, #972,
#996, #1011/#1013): rebase-cost check (`git merge-base` / mergeable state),
CI state, and whether its claim boundary has been overtaken by merged main.
Output: a revive / rebase / close-as-redundant recommendation **per PR with
citations, delivered only in the final report** — create no new tracked
files for this, and post no comments unless a PR is provably redundant with
merged work (cite the merged commit).

### 5. Sequencing, parallelism, budget

- Branch every stream from fresh `origin/main`; keep worktrees within the
  budget law in `CLAUDE.md` (streams may share one worktree sequentially).
- Order of first commit follows §4's listed priority order (A1 → A2 → B →
  C → D). Interleave while CI runs; never block the session sleeping on CI —
  check back between stream work.
- If context compaction occurs mid-push, rerun §3 before the next edit.

### 6. Stop conditions (report, do not improvise)

Stop the affected stream — and only that stream — and record
`BLOCKED_OPERATOR` when: a required credential/platform setting is absent;
an ownership conflict has no track-sanctioned path; WP-00B admission truth
has drifted; a base branch diverges under Stream B; or packet
preflight/closeout fails for a reason outside the allowed files. Stop the
whole push only if `make onboard` reports an unrepairable blocking verdict
or `origin/main` moves in a way that invalidates every open stream.

### 7. Deliverable — the final push report

End the session with one report containing, per stream: typed verdict, PR
URL (or none + why), exact commands run with exit statuses, files changed
against allowed-file lists, unresolved blockers, and the single next human
action. No aggregate score, no capability claims, no "done" without a cited
green command. The push is successful when every evidence-ready seam has
either a reviewable draft PR or an honest typed blocker — not when
everything is merged, which is never your call.
