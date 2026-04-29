---
name: global-repo-reckoning
description: Use when asked to assess the current Dharma Swarm repo, active branches, PRs, worktrees, and safest next action without implementing features.
---

# Global Repo Reckoning

## Purpose

Produce a current-truth map of active Dharma Swarm work without changing code.

## Inputs

- Target repo or worktree path
- Named PRs, branches, or issue numbers
- Any user-stated no-touch zones

## Procedure

1. Read `AGENTS.md`, `CLAUDE.md`, and relevant recent reports first.
2. Run read-only status commands for each relevant worktree.
3. For each branch or PR, record base SHA, dirty status, changed files, tests claimed, tests verified, and scope drift.
4. Classify failures as baseline, branch-caused, environment-caused, or unknown.
5. Quarantine huge diffs, dirty unknown worktrees, scope drift, runtime rewrites, dashboard rewrites, Darwin/Shakti rewrites, and test weakening.
6. Produce a ranked merge queue and warning list.

## Stop Conditions

- A command would modify files, checkout branches, stop daemons, or touch live state.
- The branch has unknown dirty changes that would be overwritten or mixed.
- The user asked for review only.

## Required Final Report

- Worktree path
- Branch
- Base SHA
- Dirty status
- Files changed
- Tests run and results
- Failure classification
- Merge recommendation: merge, review, quarantine, or discard
- Single safest next action

## Non-Goals

- No code edits
- No commits
- No merges
- No branch cleanup
- No feature implementation
