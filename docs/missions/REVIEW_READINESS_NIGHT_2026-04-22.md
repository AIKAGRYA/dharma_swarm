# Review Readiness Night Mission

You own the single write-capable overnight lane for the canonical `dharma_swarm`
repo.

## Primary Objective

Wake up with a repo that is measurably closer to review-ready:

- smoother operator runtime
- fewer hidden blockers
- bounded loose ends either fixed or written down precisely
- a morning tally that says what is actually ready and what is still blocked

## Required Inputs

Before choosing a slice each cycle, inspect:

1. `~/.dharma/review_readiness/latest_run.txt`
2. the current run directory named inside it
3. `probes/baseline_latest.md` if it exists
4. `~/.dharma/shared/codex_overnight_handoff.md` if it exists

Those files define the live review-readiness contract for the night.

## Success Criteria

- at least one bounded, real repo slice shipped
- every shipped slice has focused verification when feasible
- review-readiness probes improve or stay green, not regress
- morning handoff reports exact result, files, tests, blockers, and next move
- no collision with unrelated user work

## Priority Order

1. failing runtime, smoke, build, or test checks from the latest probe
2. highest-leverage loose end that blocks reviewability
3. docs or control-surface clarification that removes ambiguity for the morning reviewer
4. compact cleanup only when it directly supports 1-3

## Operating Rules

- inspect the current worktree yourself each cycle before choosing work
- respect existing uncommitted changes; do not revert or clean them
- choose one bounded slice at a time
- prefer concrete code, tests, runtime truth, and review packets over broad planning
- if blocked, leave exact evidence and the next unblock move
- do not commit, push, reset, or open PRs

## Hard Boundaries

Do not do any of the following unless fixing a direct blocker with a focused test:

- broad style sweeps
- giant refactors across unrelated subsystems
- speculative surface widening
- deleting historical or generated material just to make `git status` prettier

## Morning Output Shape

At the end of each cycle, keep the normal Codex overnight output shape:

- RESULT: one short paragraph
- FILES: comma-separated paths or none
- TESTS: exact command run or not run
- BLOCKERS: none or one short concrete blocker

Also leave the repo in a state where the final review-readiness probe can answer:

- is the canonical dashboard runtime alive?
- does desktop shell smoke pass?
- does the dashboard build?
- does the desktop shell build?
- is the tree review-clean yet?

