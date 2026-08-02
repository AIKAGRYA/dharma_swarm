# Graph-of-Loops Implementation — Progress File

**Role:** session-continuity record for the walking-mode loop-closure +
auto-merge-door execution prompt. Owns no authority. Re-read after any
context compaction; refresh after every workstream state change.
**Design doc:** `docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md` (draft
PR #1156, this branch).
**Operator ruling in force:** DOOR = AUTO_WITH_DECORRELATED_REVIEW
(2026-07-29). Tier 2 = operator hand-merge forever. Ruling record committed
verbatim in PR-A:
`docs/ops/OPERATOR_RULING_2026-07-29_AUTO_WITH_DECORRELATED_REVIEW.md`.

## Workstream ledger (refreshed 2026-08-02 — all but PR-E landed)

| PR | Branch | PR # | State |
|---|---|---|---|
| Design + this file | claude/graph-of-loops-audit-design-eh3lz5 | #1156 | **OPEN**, ready for review (un-drafted 2026-08-02), all required checks green, in the automerge lane in `mike-watch` |
| PR-B kill-switch | claude/loop-pr-b-killswitch | #1157 | **MERGED** (squash 2912a9a5) |
| PR-C brief | claude/loop-pr-c-walking-brief | #1158 | **MERGED** (a979b721); open reviewer findings carried to follow-up #1166 |
| PR-C2 brief hardening | claude/loop-pr-c2-walking-brief-hardening | #1166 | **MERGED** (auto-merge, 2026-07-31). All 11 findings left open at #1158's merge, plus a second round: tri-state gatherers, kill-switch missing-branch variant, duplicate-issue guard, GraphQL pin + retained manual pin instruction, md-escaped titles, walk-day-bucketed idempotent posting, paginated + ownership-checked comment lookup, pending nightly |
| Merge-flow fix | claude/loop-rebase-on-merge | #1172 | **MERGED** (2026-08-01). pr-ci-health now rebases behind-main PRs on the push-to-main event, not only hourly — closing the up-to-59-minute stranding window that forced manual "Update branch" taps. Verified live: run #1226 fired `event: push` on its own merge commit 80ef0c86 seconds after landing |
| PR-D task join | claude/loop-pr-d-task-join | #1159 | **MERGED** (operator-armed auto-merge, 2026-07-30). Review-hardened through five rounds: traversal-confined ids, blocked-status encoding for legacy pollers, claim gates (deps + claimable state), O_EXCL claim fence with orphan release, ADR-010 decision record |
| PR-A door | claude/loop-pr-a-door | #1160 | **MERGED** (the constitutive hand-merge, 2026-07-30). Final hardening rounds: exact trusted logins mirroring Mike, head-SHA-pinned paginated approvals, fail-closed gather incl. paginated changed-files, deduped rate limit, fully decorrelated deletion sign-off incl. async, pull_request_review trigger, router --assume-unattended gate, tier-2 referee scripts. **Enforcement completes only with two operator actions:** add "Automerge tier policy" to branch protection; land the ci_parity_manifest.json row via the titanium track |
| PR-E hardening lane | claude/loop-pr-e-hardening-lane | #1162 | **OPEN, NOT MERGEABLE AS DESIGNED.** 16 of 34 review threads unresolved; six are one architectural fact — the lane holds repository write authority in the same process tree, filesystem and UID as the untrusted agent, so every guard is a point-in-time check in a space the adversary can still write to. Greptile's T-Rex drove a real `git push` to an attacker repo through the full guard set (`GIT_NO_EXEC`, `GIT_CONFIG_GLOBAL/SYSTEM=/dev/null`, byte-for-byte `.git/config` restore, frozen `commit-tree`). Measured limit: `-c` overrides single-valued keys but `credential.helper` and `url.<base>.insteadOf` are multi-valued, so `-c` only appends and the attacker entry survives. **Disposition pending with the operator: close in favour of a propose/deliver split** (untrusted job with `permissions: {}` produces a `git bundle`; separate trusted job on a fresh runner verifies and pushes), which dissolves all six residuals instead of mitigating them. `DHARMA_LANE_AGENT_CMD` must stay unset on this design |
| PR-F watcher/canary | claude/loop-pr-f-watcher | #1163 | **MERGED** (86a1af8c, 2026-08-02) after ten outdated Codex threads were resolved |
| Merge-flow fix 2 | claude/pr-ci-health-behind-by | #1178 | **MERGED** (a002d4df, 2026-08-02). `behind_main` now derives from the compare API's `behind_by`, not `mergeable_state` — `blocked` outranks `behind`, so the old selector matched almost nothing. First push-triggered run after the merge rebased **18** PRs (baseline: 0) |

Every PR: Session Entry packet bound (preflight at base `ea190e2` passed;
closeout evaluator passed at final head), verification transcripts in body,
linked to #1156. Full `make agent-build-closeout` bundles blocked only by
two pre-existing main-state failures (NATS evidence staleness; docops count
drift) — documented with transcripts on the PR bodies.

## Merge order — COMPLETED (historical; do not re-run)

The planned sequence was B (safety) → C (visibility) → A (the door) → D → E
→ F. **B, C, C2, A, D and F are all merged**; only the design doc (#1156) and
PR-E (#1162) remain open. Nothing in this section is an outstanding action.

## Actually pending

1. **#1156** (this doc + the design) — ready, green, in the automerge lane;
   arm with the `automerge` label or `@mike merge`, or hand-merge.
2. **#1162 / PR-E** — operator disposition: close in favour of the
   propose/deliver split, or knowingly merge as a gated-off v1 with
   `DHARMA_LANE_AGENT_CMD` permanently unset. **Do not set that secret on the
   current design.** See the ledger row for the measured reason.
3. **Kill-switch acceptance tap (never performed):** dispatch
   `loop-emergency-stop`, confirm the guarded workflows go red with "HALTED
   BY KILLSWITCH", then `loop-resume` with confirmation `resume`.
4. **PR-A enforcement completion (operator-side, still open):** add
   "Automerge tier policy" to branch protection; land the
   `ci_parity_manifest.json` row via the titanium track.
5. **Follow-ups not yet built:** isolated propose/deliver delivery for the
   lane; brief-wiring (`scripts/runtime/walking_brief.py` still hardcodes
   `canary` and `ingested` to `None`); mailbox claim-write so the lane claims
   its task.

## Incidents caught live by CI during the build (all fixed + pinned by test)

1. Kill-switch guard failed closed on a missing loop-control branch
   ("No commit found" 404 variant) — automerge run 30433704716.
2. Tier-policy check crashed on its own introducing PR (trusted checkout
   predates the policy) — run 30436464851; bootstrap case added.
3. Semgrep taint arc on the hardening lane (alerts 537-541): real flow was
   argparse → select_target return → prompt → argv, not the env secret.
   Final design: secret = template selector; prompt on stdin; nothing
   suppressed.

## Standing constraints (unchanged)

Hot-path packet discipline per `pr_merge_control.py:94-109`; Mike-owned
surfaces ride Mike-track packets (B, A), loop-closure otherwise (C, E, F);
`Makefile:264` help text still shows the old token (titanium-owned; one-line
follow-up under that track). Prohibitions all honored: `alive_claim` False,
no `shadow=False`, loops 12/13 blocked, no new track, Beads fence AFFIRMED
(decision record in `docs/architecture/WIRING_AND_LOOPS.md`), Tier-2 PRs
never auto-merged, KILLSWITCH halts lanes.

## Session log

- 2026-07-29 (session 1): grounding audit → design doc → #1156. Execution
  prompt with §0 ruling received. Phase 0 reconciled (fresh start). All six
  workstream PRs built, opened as drafts, driven through CI; three live CI
  incidents fixed. Gate-10 evidence: this ledger + PR receipts accumulate;
  nothing flipped.
- 2026-07-30 (session 2, merge window): operator hand-merged #1157 (B) and
  #1158 (C). Decorrelated review generated a heavy findings wave (Devin +
  Codex + Greptile on #1158/#1159/#1160) — every confirmed finding fixed
  with a pinning test on the same day: door hardening on #1160
  (ecacf160…e3a3ec4f), mailbox hardening on #1159 (79e39202, 1ebff0fa),
  brief hardening as follow-up #1166 (post-merge findings cannot amend a
  merged PR). Deferred-with-record: tier-1 coverage non-regression (no
  coverage context exists — ruling-record gap #4), Mike backlog-fanout
  token seam (gap #5), manifest-derived tier-2 closure (gap #6). Packet
  rebinds: WP-LOOPA re-preflighted at 2912a9a5 after ACTIVE_TRACK sibling
  surfaces grew; WP-LOOPC2 minted for #1166. All closeout evaluators
  passed at final heads.

- 2026-07-30 (later): operator hand-merged #1160 (PR-A — THE DOOR IS ON
  MAIN). Second review-hardening wave fixed same-day with pinning tests:
  decorrelated deletion sign-off (2958ca34), paginated changed-files fetch
  (a8ea84a9), dismissal-row clearing (e3a3ec4f), review pagination.
  WP-LOOPA packet rebased twice (2912a9a5 → 2980fa2c) as main advanced;
  closeout evaluator passed at the merged head. Open **as of that date**
  (point-in-time snapshot, superseded — see the ledger for current state):
  #1156, #1159 (D), #1162 (E), #1163 (F), #1166 (C2).

- 2026-08-01/02 (session 3, merge-flow repair): root-caused why every PR
  needed a hand-push and a hand-merge. Three causes, in order of damage.
  (1) The hourly-only rebase trigger — fixed by #1172. (2) `pr_ci_health.py`
  keyed `behind_main` off `mergeable_state`, which is single-valued with
  `blocked` outranking `behind`, so nearly every behind-main PR here was
  invisible to the rebase selector — fixed by #1178; the next push-triggered
  run rebased 18 PRs against a baseline of 0, and a second wave fired 45
  minutes later on the following merge. (3) **The real merge blocker was
  never operator approval: it was GitHub branch protection's "require
  conversation resolution."** Falsified against #1180, which merged
  unattended with zero reviews; then #1178 (1 unresolved thread) and #1163
  (10, all outdated with landed fixes) each merged within seconds of their
  threads being resolved. Hours were spent reporting Merge Master Mike's
  advisory blockers as if they were GitHub's. Mike's gate is real but
  subordinate — branch protection decides.
  Still unrebasable: `pr_ci_safe_rebase.py:331-342` skips any PR touching a
  Session Entry packet (18 PRs, #1011 and #930 are 113 commits back), but
  the operator turned **"require branches up to date" off** on 2026-08-02,
  so behind-ness no longer blocks merge and that repair dropped in priority.
  Merge queues are org-only and unavailable on this repo.
  Review wave on #1156 itself: two Greptile + six Codex findings, all
  verified and fixed in one push — including two false negatives of my own
  (`no parent/child field anywhere in Python`, and a spec claimed absent
  "in any branch" that lives on 15) and a kill-switch section that pointed
  the emergency stop at `main` when every guard reads `loop-control`.

## Operator follow-up — RESOLVED 2026-08-02 (no credential change needed)

**Was:** `MIKE_PAT` could not dispatch workflows — the automerge lane's
"Evaluate and dispatch auto-merge" step failed with `HTTP 403: Resource not
accessible by personal access token` when dispatching Mike's router
(run 30508011944 on #1159, 2026-07-30). The fine-grained PAT appeared to
need **Actions: Read and write**.

**Now:** the step succeeds. Direct evidence rather than inference: the
automerge lane comment on #1156 head `3381407` reports
`Evaluate and dispatch auto-merge`=SUCCESS and Mike was dispatched in
`mike-watch` mode. The dispatch path is `automerge.yml:323`
(`GH_TOKEN="${MIKE_PAT:-$GH_TOKEN}" gh workflow run codex-mention-router.yml`),
where `MIKE_PAT` is bound to the `MERGEMASTERMIKE_PAT` secret
(`automerge.yml:82-85`). Corroborating: #1159 and #1166 both landed by
auto-merge through this chain. **Do not modify the PAT scopes on the strength
of this section** — it is retained as history only. If a 403 recurs, re-check
Actions: Read and write before assuming anything else.
