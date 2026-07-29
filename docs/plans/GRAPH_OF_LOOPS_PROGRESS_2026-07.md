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

## Workstream ledger (2026-07-29, session 1 complete)

| PR | Branch | PR # | State |
|---|---|---|---|
| Design + this file | claude/graph-of-loops-audit-design-eh3lz5 | #1156 | draft, all green, awaiting operator |
| PR-B kill-switch | claude/loop-pr-b-killswitch | #1157 | draft, all green (guard 404-variant fixed live), awaiting operator |
| PR-C brief | claude/loop-pr-c-walking-brief | #1158 | draft, all green, awaiting operator |
| PR-D task join | claude/loop-pr-d-task-join | #1159 | draft, all green, awaiting operator |
| PR-A door | claude/loop-pr-a-door | #1160 | draft, all green (bootstrap case added live), **the constitutive hand-merge** |
| PR-E hardening lane | claude/loop-pr-e-hardening-lane | #1162 | draft; Semgrep taint arc resolved at head d7a40dc (prompt on stdin; argv purely literal) — verify next scan |
| PR-F watcher/canary | claude/loop-pr-f-watcher | #1163 | draft, opened, CI in flight |

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
