---
name: control-loop-pr-review
description: Use to review Dharma Control Loop pull requests for runtime-spine correctness, context-bundle safety, and scope discipline.
---

# Control Loop PR Review

## Purpose

Review control-loop changes as a reviewer, not an implementer, unless the user explicitly asks for patches.

## Inputs

- PR number or branch
- Expected control-loop spec or report
- Test results from the author

## Procedure

1. Compare the diff against the named spec or issue.
2. Verify `RuntimeStateStore`, `RuntimeLifecycle`, `SessionLedger`, `ContextCompiler`, and `GuardianCrew` remain canonical.
3. Check that context bundles are treated as evidence, not authority, and are injection-scanned before prompt use.
4. Check tests use temp runtime DBs, not live `~/.dharma`.
5. Confirm no dashboard, provider routing, Darwin/Shakti, or unrelated docs drift entered the PR.
6. Classify each concern as `fix-in-this-PR`, `follow-up-issue`, or `ignore`.

## Stop Conditions

- The PR diff includes broad runtime rewrites unrelated to the control-loop scope.
- The PR weakens Guardian, Telos, rollback, or runtime-state protections.
- The PR cannot be reviewed without running live state.

## Required Final Report

- Verdict: proceed, patch small, pause, or quarantine
- Diff scope assessment
- Behavior and invariant checks
- Test adequacy
- Required fixes
- Follow-up issues

## Non-Goals

- No new architecture
- No feature expansion
- No runtime implementation unless explicitly requested
- No dashboard/API review unless in scope
