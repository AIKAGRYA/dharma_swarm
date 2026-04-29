---
name: promotion-packet-splitter
description: Use when moving local or LF5 work toward main by classifying changed files into narrow promotion slices.
---

# Promotion Packet Splitter

## Purpose

Turn a large local change set into small, reviewable promotion slices without restoring whole files or mixing unrelated surfaces.

## Inputs

- Source worktree or snapshot reports
- Clean destination branch or worktree
- User-approved slice list
- Existing audit reports and diffs

## Procedure

1. Confirm source and destination worktrees and branch names.
2. Read snapshot/status reports before reading code.
3. Classify every changed and untracked path into promotion slices.
4. Identify quarantine paths, duplicate substrates, and unrelated local work.
5. For the next slice only, define the minimal hand-port scope, tests, and proof report.
6. Do not restore whole source files unless the user explicitly approves.
7. Write the promotion matrix or slice report before implementation begins.

## Stop Conditions

- Snapshot or source-of-truth report is missing.
- The destination branch is dirty with unrelated work.
- The next slice would require dashboard, provider routing, Darwin/Shakti, memory promotion, or live state outside the approved scope.

## Required Final Report

- Files classified by slice
- Files quarantined
- Slice order
- Minimal next patch scope
- Tests required for the next slice
- Risks and blockers

## Non-Goals

- No broad LF5 restore
- No `git add -A`
- No push
- No live daemon changes
- No unrelated cleanup
