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

## Workstream ledger (2026-07-30, session 2 — merge window open)

| PR | Branch | PR # | State |
|---|---|---|---|
| Design + this file | claude/graph-of-loops-audit-design-eh3lz5 | #1156 | draft, all green, awaiting operator |
| PR-B kill-switch | claude/loop-pr-b-killswitch | #1157 | **MERGED** (squash 2912a9a5) |
| PR-C brief | claude/loop-pr-c-walking-brief | #1158 | **MERGED** (a979b721); open reviewer findings carried to follow-up #1166 |
| PR-C2 brief hardening | claude/loop-pr-c2-walking-brief-hardening | #1166 | draft; fixes all 11 reviewer findings left open at #1158's merge (tri-state gatherers, kill-switch missing-branch variant, duplicate-issue guard, GraphQL pin, md-escaped titles, idempotent posting, pending nightly) |
| PR-D task join | claude/loop-pr-d-task-join | #1159 | ready-for-review (operator); review-hardened at 1ebff0fa: traversal-confined ids, blocked-status encoding for legacy pollers, claim gates (deps + claimable state), decision record moved to ADR-010 |
| PR-A door | claude/loop-pr-a-door | #1160 | review-hardened at e3a3ec4f (exact trusted logins mirroring Mike, head-SHA-pinned paginated approvals, fail-closed gather, deduped rate limit, trusted-only deletion sign-off incl. async, pull_request_review trigger, router --assume-unattended gate, tier-2 referee scripts); **the constitutive hand-merge** |
| PR-E hardening lane | claude/loop-pr-e-hardening-lane | #1162 | draft; Semgrep taint arc resolved at head d7a40dc (prompt on stdin; argv purely literal) — verify next scan |
| PR-F watcher/canary | claude/loop-pr-f-watcher | #1163 | draft, all green, awaiting operator |

Every PR: Session Entry packet bound (preflight at base `ea190e2` passed;
closeout evaluator passed at final head), verification transcripts in body,
linked to #1156. Full `make agent-build-closeout` bundles blocked only by
two pre-existing main-state failures (NATS evidence staleness; docops count
drift) — documented with transcripts on the PR bodies.

## Recommended merge order for the operator

B (safety) → C (visibility) → A (the door; then: add "Automerge tier
policy" to branch protection + titanium-track manifest row) → D → E (then
set the `DHARMA_LANE_AGENT_CMD` secret to `claude`, `claude-npx`, or
`codex`) → F. After B+C: dispatch loop-emergency-stop, watch the chain go
red, loop-resume — the kill-switch acceptance tap.

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

## New operator follow-up (found 2026-07-30, not fixable from the repo)

`MIKE_PAT` cannot dispatch workflows: the automerge lane's
"Evaluate and dispatch auto-merge" step fails with
`HTTP 403: Resource not accessible by personal access token` when it
tries to dispatch Mike's router (run 30508011944 on #1159). The fine-
grained PAT needs **Actions: Read and write** on this repo — until then
the Mike dispatch chain (and therefore the door's unattended lane) cannot
fire, independent of everything PR-A fixes.
