---
title: Sovereign Build Packet Pilot-00
path: spec-forge/sovereign-build-packet-pilot-00.md
slug: sovereign-build-packet-pilot-00
doc_type: pilot_plan
status: forge_draft
created: "2026-05-06"
canonical: false
summary: Dry-run acceptance plan for validating the Sovereign Build Packet Protocol v0 without source edits, agent dispatch, worktrees, or SQLite writes.
---

# Sovereign Build Packet Pilot-00

Status: forge-stage pilot plan. This document does not license source edits or live agent execution.

## 1. Purpose

Pilot-00 tests one thing: can the protocol generate the same scoped dispatch plan Dhyana would write by hand?

Pilot-00 MUST be shape-only. It MUST NOT:

- edit source files
- spawn agents
- create git worktrees
- write SQLite state
- enqueue bridge tasks
- call live TaskBoard mutation paths
- run implementation commands

It MAY write dry-run artifacts under `~/.dharma/build_protocol/dryruns/<id>/`.

## 2. Input

The pilot input is one markdown spec authored by Dhyana.

Suggested trivial spec:

```markdown
# docs_atom_oneline

Telos: Add a one-line docstring to `dharma_swarm/math_bridges.py:TaskResult.is_ok`.

Allowed paths:
- dharma_swarm/math_bridges.py

Forbidden paths:
- dharma_swarm/orchestrate_live.py
- dharma_swarm/swarm.py
- dharma_swarm/frontier_council.py
- dharma_swarm/agent_runner.py
- dharma_swarm/guardian_crew.py
- dharma_swarm/insight_brief.py
- api/**
- dashboard/**

Proof command:
pytest tests/test_math_bridges.py -q

Reviewer:
codex-reviewer
```

The input MUST answer all six pre-flight questions:

1. What files are hot?
2. What files are forbidden?
3. What is the smallest proof of success?
4. What can a builder edit?
5. What happens if tests fail?
6. Who reviews before merge?

Any answer of `I don't know`, empty scope, or missing proof command MUST keep the BuildPacket in draft.

## 3. Dry-Run Generator Contract

The generator MAY be implemented later as an isolated read-only module, but Pilot-00 is defined by outputs, not by implementation details.

Required invocation shape:

```text
pilot-00-dryrun-generator <input-spec.md>
```

Required behavior:

- parse one markdown input spec
- infer one BuildPacket-shaped JSON record
- infer one or more WorkPacket-shaped JSON records
- render one human-readable dispatch plan
- render one deterministic proof command
- render one gate list
- render six pre-flight answers
- write only under `~/.dharma/build_protocol/dryruns/<id>/`

The generator MUST NOT import hot-path modules. It SHOULD treat protocol substrate records as JSON shapes during Pilot-00.

## 4. Output Layout

Required output directory:

```text
~/.dharma/build_protocol/dryruns/<id>/
  build_packet.json
  work_packets/
    wp_001.json
  dispatch_plan.md
  proof_command.txt
  gates_required.txt
  pre_flight_answers.md
```

Optional output files:

```text
~/.dharma/build_protocol/dryruns/<id>/
  validation_report.json
  rejected_paths.txt
  source_spec_copy.md
```

## 5. Required JSON Shapes

`build_packet.json` MUST contain:

```json
{
  "title": "docs_atom_oneline",
  "description": "string",
  "status": "pending",
  "created_by": "pilot-00",
  "metadata": {
    "kind": "build_packet",
    "protocol_version": "v0",
    "spec_path": "string",
    "telos_statement": "string",
    "hot_files": [],
    "forbidden_files": ["string"],
    "forbidden_domains": ["string"],
    "gates_required": ["telos", "scoped_tests"],
    "proof_command": "pytest tests/test_math_bridges.py -q",
    "child_task_ids": ["wp_001"],
    "human_approver": "dhyana",
    "approval_signature": "sha256:<hex>",
    "max_iterations": 2
  }
}
```

`work_packets/wp_001.json` MUST contain:

```json
{
  "id": "wp_001",
  "sender": "pilot-00",
  "task": "string",
  "scope": ["dharma_swarm/math_bridges.py"],
  "output": ["diff", "test_output", "checkpoint_ref"],
  "constraints": ["no_merge", "no_push", "no_shell_exec", "scope_locked"],
  "payload": {
    "kind": "work_packet",
    "protocol_version": "v0",
    "parent_build_packet_id": "string",
    "lead_agent": "pilot-00",
    "builder_agent": "unassigned",
    "allowed_paths": ["dharma_swarm/math_bridges.py"],
    "forbidden_paths": ["string"],
    "worktree_path": "",
    "scoped_tests": ["pytest tests/test_math_bridges.py -q"],
    "max_diff_lines": 50,
    "checkpoint_ids": []
  },
  "status": "queued",
  "metadata": {
    "dry_run": true
  }
}
```

## 6. Dispatch Plan Content

`dispatch_plan.md` MUST include:

- source spec path
- telos statement
- allowed paths
- forbidden paths
- hot-file status
- proposed WorkPackets
- reviewer identity
- gates required
- proof command
- reasons the plan is safe
- reasons the plan would be rejected

It MUST NOT include implementation instructions outside the allowed scope.

## 7. Validation Commands

After generation, these checks MUST pass:

```bash
test -f ~/.dharma/build_protocol/dryruns/<id>/build_packet.json
test -f ~/.dharma/build_protocol/dryruns/<id>/work_packets/wp_001.json
test -f ~/.dharma/build_protocol/dryruns/<id>/dispatch_plan.md
test -f ~/.dharma/build_protocol/dryruns/<id>/proof_command.txt
test -f ~/.dharma/build_protocol/dryruns/<id>/gates_required.txt
test -f ~/.dharma/build_protocol/dryruns/<id>/pre_flight_answers.md
```

Forbidden-path sanity check against WorkPacket editable scope:

```bash
jq -r '.scope[], .payload.allowed_paths[]' ~/.dharma/build_protocol/dryruns/<id>/work_packets/*.json | rg -n "orchestrate_live|swarm\\.py|frontier_council|agent_runner|guardian_crew|insight_brief|operator_brief|daily_insight|dashboard|api"
```

This command MUST return no matches.

Pre-flight check:

```bash
rg -n "I don't know|TODO|TBD" ~/.dharma/build_protocol/dryruns/<id>/pre_flight_answers.md
```

This command MUST return no matches.

Proof command check:

```bash
wc -l ~/.dharma/build_protocol/dryruns/<id>/proof_command.txt
```

The result MUST be exactly one line.

## 8. Success Criteria

Pilot-00 succeeds when:

- every required output exists
- every output is under the dry-run directory
- no source file is edited
- no SQLite file is written
- no worktree is created
- no live agent is spawned
- all six pre-flight answers are concrete
- WorkPacket scope touches only allowed paths
- forbidden domains are absent from WorkPacket scope
- proof command is one deterministic shell line
- Dhyana reads `dispatch_plan.md` and says it matches what they would write by hand

## 9. Failure Criteria

Pilot-00 fails if:

- the plan touches a forbidden file or domain
- the plan invents broad cleanup
- the proof command is missing or non-deterministic
- the telos statement is filler
- any pre-flight answer is unknown
- a WorkPacket lacks a reviewer
- a WorkPacket has no bounded allowed path
- any artifact is written outside the dry-run directory
- any live runtime, bridge, TaskBoard, agent, or worktree mutation occurs

Failure means the protocol spec is wrong or underspecified. The next action is to revise `spec-forge/sovereign-build-packet-protocol-v0.md`, then rerun Pilot-00.

## 10. Exit Gate

Pilot-00 exits only by human decision.

If Dhyana approves the dispatch plan, the project may draft a Week-2 live-worktree plan as a separate forge artifact.

If Dhyana rejects the dispatch plan, no source work is licensed. The protocol returns to forge iteration.
