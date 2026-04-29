---
name: baseline-red-stabilizer
description: Use when clean origin/main has known failing tests that need narrow stabilization before feature work proceeds.
---

# Baseline Red Stabilizer

## Purpose

Fix known red baseline tests on a clean branch without mixing active feature work.

## Inputs

- Exact failing test names
- Clean `origin/main` SHA
- Known expected behavior
- Forbidden worktrees and modules

## Procedure

1. Create or use a clean worktree from current `origin/main`.
2. Reproduce only the named failing tests.
3. Read the failing code paths and adjacent tests.
4. Patch the smallest semantic cause.
5. Preserve the original test intent unless the test is clearly obsolete and related tests agree.
6. Run compileall and the named tests, then any closely related focused tests.
7. Write a stabilization report.

## Stop Conditions

- The fix requires broad architecture changes.
- The fix touches forbidden active feature branches.
- The fix weakens Telos gates, Guardian gates, rollback, provider safety, or dharma boundaries.
- The failure is not reproducible on clean `origin/main`.

## Required Final Report

- Failing tests reproduced
- Root cause
- Files changed
- Patch summary
- Tests run and results
- Remaining baseline failures
- Whether feature branches should rebase after merge

## Non-Goals

- No opportunistic test cleanup
- No feature implementation
- No dashboard work
- No memory promotion work
- No merge
