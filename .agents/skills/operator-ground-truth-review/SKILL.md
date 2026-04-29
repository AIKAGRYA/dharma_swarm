---
name: operator-ground-truth-review
description: Use to review operator-facing branches for truthful runtime views, canonical state use, and no duplicated operator substrate.
---

# Operator Ground Truth Review

## Purpose

Ensure operator surfaces display and modify canonical Dharma Swarm runtime truth instead of parallel or stale state.

## Inputs

- PR number or branch
- Operator surface touched
- Claimed runtime tables or APIs
- Test results

## Procedure

1. Identify every operator-visible field in the diff.
2. Trace each field to `RuntimeStateStore`, `SessionLedger`, `ContextCompiler`, or documented canonical adapters.
3. Check that writes to operator state use `operator_actions` or the approved bridge path.
4. Verify no new SQLite DB, JSON ledger, dashboard-only cache, or local file substrate became canonical.
5. Confirm tests avoid live `~/.dharma`.
6. Classify review findings by severity and scope.

## Stop Conditions

- Operator UI or CLI claims cannot be traced to canonical runtime truth.
- The branch creates a duplicate operator ledger.
- The review would require live daemon mutation.

## Required Final Report

- Verdict
- Canonical truth trace
- Duplicate substrate risks
- Tests verified
- Required fixes
- Follow-up gaps

## Non-Goals

- No dashboard redesign
- No runtime behavior changes
- No provider routing changes
- No memory promotion changes
