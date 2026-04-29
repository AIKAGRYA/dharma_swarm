---
name: guardian-invariant-review
description: Use to review Guardian or invariant-check changes for correct severity, temp-state tests, and no safety weakening.
---

# Guardian Invariant Review

## Purpose

Review Guardian checks and runtime invariants so they catch real regressions without false authority or live-state coupling.

## Inputs

- Guardian diff or PR
- Intended invariant
- Thresholds and severity mapping
- Tests and reports

## Procedure

1. Read the invariant description and affected Guardian code.
2. Verify the check reads canonical substrates such as `RuntimeStateStore`, not duplicate reports when runtime state is available.
3. Confirm severity mapping is explicit: warning, degraded, blocker.
4. Check fix hints are concrete and point to existing producers or canonical paths.
5. Verify tests seed temp runtime state and do not touch live `~/.dharma`.
6. Confirm the check does not block healthy new work or weaken existing Telos/Guardian behavior.

## Stop Conditions

- The invariant cannot be explained in one sentence.
- The check requires live daemon state in tests.
- The patch suppresses or loosens an existing safety gate without explicit approval.

## Required Final Report

- Verdict
- Invariant reviewed
- Severity thresholds
- Canonical substrate used
- Test DB proof
- False-positive and false-negative risks
- Required fixes or follow-up issue

## Non-Goals

- No new Guardian architecture
- No runtime producer work
- No dashboard surfacing
- No Telos boundary changes
