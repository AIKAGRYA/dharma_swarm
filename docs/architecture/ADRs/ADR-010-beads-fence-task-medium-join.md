# ADR-010: Beads Fence Affirmed — Task-Medium Joined Natively

> **Date:** 2026-07-29
> **Status:** ACCEPTED (operator-ratified walking-mode plan, PR-D)
> **Decision:** The "No Beads, LangGraph, CrewAI, or other orchestration
> dependency" fence stands. The walking-mode lanes' need for a
> dependency-aware, git-shareable task medium is met by JOINING two
> substrates this repo already owns — `dharma_swarm/task_board.py`
> (ready-set semantics) and `dharma_swarm/roaming_mailbox.py` (git-native
> one-JSON-file-per-task medium) — via a `depends_on` field and a
> `ready_tasks()` reader. No new store class, no external dependency, no
> new board file.

---

## Context

The walking-mode loop-closure plan (PR-D;
`docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md` §2.2 — lands with
PR #1156; until that merges, see the PR itself) needs a dependency-aware,
git-shareable task medium for its lanes. The Beads fence in
`docs/architecture/WIRING_AND_LOOPS.md` was read in full before this
change, not routed around.

## Decision

The fence is **AFFIRMED**. `task_board.py` contributes the ready-set
semantics (dependencies must be complete before a task is claimable —
`task_board.py` `_READY_QUERY`); `roaming_mailbox.py` contributes the
git-native shareable medium. The join is a `depends_on` field plus a
`ready_tasks()` reader on the mailbox (Anti-Slop Rule 2: no new store
class; the fence's own third clause: no new board file).

Dependent tasks are written with status `blocked` (not `queued`) so that
legacy pollers — older checkouts that ignore the `depends_on` field and
claim anything `queued` — structurally cannot claim a task whose
prerequisite is unanswered.

## Falsifiable revisit criteria

Reopen the Beads question explicitly, in a dated amendment to this
record, if ANY of the following is observed after 2–3 weeks of
hardening-lane operation:

1. **ready-set misbehavior:** a lane claims a blocked task or starves a
   ready one, attributable to the join rather than to task authoring;
2. **a real cross-repo sharing need:** a second repository must consume
   the same task graph and git-sync of `roaming_mailbox/` proves
   insufficient;
3. **persistent agent fumbling:** lane or subagent sessions repeatedly
   mis-handle the bespoke board where a standard tool's conventions would
   have been understood.

Absent those observations, the fence stands and silent adoption of an
orchestration dependency remains a governance violation.

## Consequences

- `roaming_mailbox.py` gains `depends_on`, `ready_tasks()`,
  `validate_dependencies()`, dependency enforcement in `claim_task`, and
  the `blocked` status encoding; `tests/test_roaming_mailbox.py` pins the
  contract.
- The wiring map (`docs/architecture/WIRING_AND_LOOPS.md`) links here
  instead of hosting the decision, keeping one authority role per file
  (`docs/AGENTS.md`).
