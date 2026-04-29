# Dharma Swarm Agent Rules

Dharma Swarm is a dharmic multi-agent runtime for bounded autonomous software work, research metabolism, and governed self-improvement. Its working rule is simple: use existing canonical substrates, keep changes narrow, prove behavior with tests or reports, and leave a clean next action for the next agent or human.

## Canonical Truth Sources

- `RuntimeStateStore` in `dharma_swarm/runtime_state.py` is the canonical structured runtime state spine.
- `RuntimeLifecycle` in `dharma_swarm/runtime_lifecycle.py` is the canonical producer wiring helper for task lifecycle rows.
- `SessionLedger` in `dharma_swarm/session_ledger.py` is the session event trace.
- `ContextCompiler` in `dharma_swarm/context_compiler.py` is the canonical context bundle compiler.
- `GuardianCrew` in `dharma_swarm/guardian_crew.py` is the runtime invariant checker.
- `TelosGatekeeper` in `dharma_swarm/telos_gates.py` is the dharmic safety gate.
- `mode_pack/contracts/mode_pack.v1.json` is the canonical mode vocabulary.
- `docs/plans/`, `reports/`, and `specs/` hold bounded plans, proof packets, and durable specs respectively.

## No-Touch Zones

- Do not touch live state under `~/.dharma` unless the user explicitly asks and the task is operational state work.
- Do not touch dirty or live worktrees unless the user names them as the target.
- Do not modify active PR branches unless the user names that branch and scope.
- Do not stop daemons, kill processes, reset branches, clean worktrees, or push unless explicitly instructed.
- Do not broaden a task into dashboard, provider routing, Darwin/Shakti, memory promotion, docs drift, or runtime behavior unless that is the named scope.

## Branch And Worktree Discipline

- Start from current `origin/main` for new work unless the user names a different base.
- Use a separate worktree for each lane.
- Keep branch names scoped, for example `feature/<slug>`, `fix/<slug>`, `docs/<slug>`, or `promote/<slug>`.
- Inspect `git status --short --branch` before and after edits.
- Add files explicitly by path when committing. Do not use `git add -A` or `git add .`.
- Never revert user or agent work you did not create unless the user explicitly instructs it.

## Runtime Substrate Map

- Work ownership: `task_claims`
- Execution lineage: `delegation_runs`
- Result lineage: `artifact_records`
- Durable distilled knowledge: `memory_facts`
- Runtime prompt continuity: `context_bundles`
- Human/operator decisions: `operator_actions`
- Session exhaust and trace: `session_events`
- Canonical writer surface: `RuntimeStateStore`
- Canonical lifecycle adapter: `RuntimeLifecycle`
- Canonical context adapter: `ContextCompiler`
- Canonical watchdog: `GuardianCrew`

Do not create a new ledger, registry, memory table, context store, or report substrate when one of these surfaces can carry the work.

## Protected Dharma Boundary

Treat these files as high-risk boundary files:

- `dharma_swarm/telos_gates.py`
- `dharma_swarm/dharma_kernel.py`
- `dharma_swarm/evolution.py`
- `dharma_swarm/config.py`

Changes to these require an explicit user scope, focused tests, and a rollback note.

## Required Report Packet

For any non-trivial branch, write a concise report under `reports/` or `docs/plans/` with:

1. Files changed
2. Exact code paths or docs paths touched
3. Tests or validation run
4. Runtime/state safety notes
5. Scope intentionally left out
6. Remaining blocker or next unresolved gap
7. Exact next action
8. Review prompt for another agent

## Default Verification

Use the narrowest command set that proves the change:

```bash
python -m compileall dharma_swarm tests
python -m pytest tests/test_session_ledger.py tests/test_runtime_state.py tests/test_bootstrap_loops.py tests/test_guardian_crew.py -q --tb=short
git diff --check
git status --short
```

For docs/interface-only changes, `git diff --check` plus path inspection may be enough. Do not run live daemons or `dgc` unless explicitly requested.

## Merge Sequencing

- Stabilization and CI unblock work land before feature branches that depend on them.
- Runtime-spine changes land before dashboard/API surfacing.
- Guardian or Telos changes require review before dependent work merges.
- If two branches touch the same hot path, pause and rebase/review before continuing.
- Do not start the next slice until the current slice is reviewed and committed if the user has set that sequence.

## Scope Control

- Do exactly the named mission.
- Prefer hand-port patches over whole-file restores.
- Prefer existing helpers and canonical substrates over new abstractions.
- Do not fix unrelated tests opportunistically.
- If a task reveals a larger problem, report it as a follow-up issue or report gap.

## Spec Rule

Serious work should use:

```text
specs/<work-id>/PRODUCT.md
specs/<work-id>/TECH.md
```

`PRODUCT.md` defines behavior and invariants. `TECH.md` defines implementation plan, touched files, tests, risks, and rollback. Use `specs/_template/` as the starting point.

## Ending Rule

End every substantial task with:

- what changed
- what was verified
- what was intentionally not touched
- exact next action
- a review prompt another agent can run without guessing
