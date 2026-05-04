# AgentOps Work Packets

AgentOps in this repo starts as an enforcement wrapper, not a daemon.
The goal is to make the manual multi-agent workflow repeatable without
giving any agent broad repo authority.

The first executable surface is:

```bash
python3 scripts/governance/run_agent_work_packet.py --packet .dharma/agentops/jobs/example.yaml
```

The runner verifies worktree identity, checks dirty-file scope before
and after each command, rejects mutating git commands, runs explicit
argv-based gates, and writes a JSON witness report under
`.dharma/agentops/runs/` by default.

It does not create worktrees, launch agents, stage files, commit, push,
reset, clean, stash, or merge. Those remain separate human or integrator
decisions.

## Packet Shape

```yaml
id: phase2-agentrunner-verify
title: Verify AgentRunner Phase 2 extraction
agent_profile: sentinel

worktree:
  path: /Users/dhyana/dharma_swarm_phase2_verify
  branch: chore/phase2-verify
  head: 94f79b4

approval:
  required: true
  token: APPROVED:phase2-agentrunner-verify

preflight:
  require_clean: true

scope:
  allowed_files:
    - dharma_swarm/agent_runner.py
    - dharma_swarm/execution_pipeline.py
    - tests/test_agent_runner*.py
  forbidden_files:
    - api/**
    - dashboard/**
    - dharma_swarm/providers.py
    - dharma_swarm/telos_gates.py
    - dharma_swarm/dharma_kernel.py

commands:
  - name: focused-agentrunner-tests
    argv:
      - /Users/dhyana/dharma_swarm/.venv/bin/python
      - -m
      - pytest
      - -q
      - tests/test_agent_runner.py
      - tests/test_agent_runner_deep_research.py
    timeout_seconds: 900

  - name: diff-check
    argv: [git, diff, --check]

report:
  path: .dharma/agentops/runs/{packet_id}.json
```

JSON and TOML packets are also supported. YAML requires PyYAML.

## Persistent Profiles

Persistent agents should be represented as committed profiles, not as
unbounded personalities with ambient authority.

Recommended starting profiles:

| Profile | Authority | Typical packet |
|---|---|---|
| `conductor` | Decompose work and write packets; no product-code edits | planning/check-only |
| `surgeon` | Edit one narrow allowed-file set | focused implementation |
| `sentinel` | Run tests, brakes, and scope checks | verification |
| `integrator` | Human-approved explicit pathspec staging/commit only | future separate runner |
| `witness` | Summarize reports and residual risk | read-only/reporting |

This first runner supports `agent_profile` as report metadata. Hard role
policy can be added after the packet contract proves useful.

## Invariants

- Every job has a bounded `scope.allowed_files`.
- Dirty files outside scope fail preflight or postflight.
- `scope.forbidden_files` overrides allowed globs.
- Commands must use `argv`; shell strings are rejected.
- Mutating git commands are rejected by default.
- Human approval is represented by an explicit packet token when needed.
- Reports are written as machine-readable witness artifacts.

The missing larger layer is orchestration: creating the worktree,
assigning the packet to an agent profile, and queuing integration after
green gates. That should reuse `runtime_state`, `operator_bridge`, and
the existing governance scripts rather than bypassing them.
