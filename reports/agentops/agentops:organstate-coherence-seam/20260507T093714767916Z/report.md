# AgentOps Report: agentops:organstate-coherence-seam

- Status: passed
- Base ref: `HEAD`
- Branch: `chore/agent-truth-spine`
- Worktree: `/Users/dhyana/dharma_swarm_truth_spine`
- Commit hash: ``
- Approval before commit: `True`
- Approval before merge: `True`

## Intent

Validate the OrganState coherence seam as a bounded operating-facts/command-spine change.

## Scope

- Scope passed: `True`
- Changed files: `13`
- Violations: `0`

## Gates

| Gate | Exit | Result |
|---|---:|---|
| compile-coherence-seam | 0 | PASS |
| focused-coherence-tests | 0 | PASS |
| operator-core-regression-tests | 0 | PASS |
| diff-check | 0 | PASS |

## Final Git Status

```
 M .github/PULL_REQUEST_TEMPLATE.md
 M dharma_swarm/operator_core/__init__.py
 M dharma_swarm/operator_core/command_spine.py
 M docs/governance/AGENTOPS_DAILY_OPERATING_BRIEF_BRIDGE.md
 M tests/test_operator_command_spine.py
?? dharma_swarm/daily_operating_brief.py
?? dharma_swarm/fractal/
?? dharma_swarm/operator_core/operating_facts.py
?? docs/governance/FRACTAL_ROOM_MEMBRANE.md
?? docs/governance/ORGAN_ENCAPSULATION.md
?? tests/test_fractal_room.py
?? tests/test_operating_facts_and_daily_brief.py
```
