# Titanium Runtime Hardening — Anchor Drift Receipt

**Doc role (per `docs/AGENTS.md`):** `witness` — current-state receipt for the `hardening/five-pillar-synthesis` worktree. Subordinate to `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md` and `docs/plans/TITANIUM_RUNTIME_HARDENING_WPS_2026-07-17.md`.

**Worktree:** `/Users/dhyana/ds-wt-hardening-20260717`  
**Branch:** `hardening/five-pillar-synthesis`  
**Purpose:** prevent stale audit anchors from driving unsafe implementation.

## Summary

The old audit anchor for TIT-020 (`_ATTEMPT_IDENTITY_METADATA_KEYS` / `_clear_attempt_identity_metadata`) is **not present** on the current hardening branch. That means the exact earlier patch (“remove `idempotency_key` from the attempt wipe list”) is already structurally drifted away. The invariant still matters: future retry-cleanup code must not remove `idempotency_key` or equivalent intent keys.

## Verification commands

```bash
grep -R "_ATTEMPT_IDENTITY_METADATA_KEYS\|_clear_attempt_identity_metadata\|pop(.*idempotency_key\|del .*idempotency_key" -n dharma_swarm/orchestrator.py dharma_swarm | head -120
.venv/bin/python -m pytest -q tests/governance/test_titanium_runtime_hardening_fitness.py
```

## Observed result

- No current source hit for the old retry-cleanup helper/list in `dharma_swarm/orchestrator.py`.
- Added `tests/governance/test_titanium_runtime_hardening_fitness.py` to lock the TIT-020 invariant structurally.
- The same guard locks the frontier-capacity-first doctrine so WP-A does not regress into cost-minimizing model downgrades.

## Resulting implementation guidance

- WP-B/TIT-020 should not blindly apply the stale “remove list entry” patch on this branch.
- Next WP-B code step should focus on positive intent-key derivation and provider/message-bus propagation, not only deletion of the old cleanup list.
- WP-A/TIT-016 should implement a `FrontierCapacityGate`-compatible rail name or wrapper; retaining `check_global_cost_cap()` internally is acceptable only if docs/tests prove it cannot downgrade authorized frontier lanes.
