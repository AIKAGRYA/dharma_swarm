# Graph-of-Loops Implementation — Progress File

**Role:** session-continuity record for the walking-mode loop-closure +
auto-merge-door execution prompt. Owns no authority. Re-read after any
context compaction; refresh after every workstream state change.
**Design doc:** `docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md` (draft
PR #1156, branch `claude/graph-of-loops-audit-design-eh3lz5`).
**Operator ruling in force:** DOOR = AUTO_WITH_DECORRELATED_REVIEW
(§0 of the execution prompt, 2026-07-29). Tier 2 = operator hand-merge
forever. Ruling record to be committed verbatim in PR-A.

## Reconciled state (Phase 0, 2026-07-29)

- No prior progress file existed (`git ls-files | grep -i progress` — only
  unrelated capital_lab artifact and a loop template).
- No open branches or PRs matched the six workstreams (checked all 30 open
  PRs on 2026-07-29; #1156 is the design doc itself). Fresh start.
- PR #1156: open, draft, all 43 checks green, mergeable_state clean.
- `docs/ops/loop_control/` does not exist yet (PR-B creates it).
- `make onboard`: READY on this checkout.

## Workstream ledger

| PR | Branch | State | PR # | Notes |
|---|---|---|---|---|
| PR-B kill-switch | — | NOT STARTED | — | first: safety before capability |
| PR-C brief | — | NOT STARTED | — | depends on PR-B label vocabulary only |
| PR-A door | — | NOT STARTED | — | operator hand-merge only |
| PR-D task join | — | NOT STARTED | — | read WIRING_AND_LOOPS.md:64 first |
| PR-E hardening lane | — | NOT STARTED | — | after PR-D ready-set |
| PR-F watcher/ingest/canary | — | NOT STARTED | — | canary duty per §9 |

## Standing constraints (verified on disk this session)

- Hot paths (`.github/`, `scripts/runtime/`, `scripts/governance/`,
  `Makefile`) require packet-bound preflight
  (`scripts/runtime/pr_merge_control.py:94-109`;
  `docs/governance/BUILD_SESSION_ENTRYPOINT.md:67-74`).
- Surface-ownership tension, flagged not hidden: automerge.yml,
  codex-mention-router.yml, pr_merge_control.py are owned by track
  `merge-master-mike-d4-2026-06`; the execution prompt lands everything
  under `loop-closure-2026-06`. PR-A/PR-B bodies must name this and the
  operator adjudicates at hand-merge.
- Prohibitions in force: `alive_claim` stays False; no `shadow=False` near
  `verify_promotion`; loops 12/13 stay BLOCKED; no new track; no Beads
  adoption (PR-D records the fence decision); Tier-2 PRs never
  auto-merged; KILLSWITCH presence halts all lane/automation work.

## Session log

- 2026-07-29 (session 1): grounding audit → design doc → PR #1156 (green,
  draft). Execution prompt received with §0 ruling. Phase 0 reconciliation
  complete; this file created. Next: PR-B.
