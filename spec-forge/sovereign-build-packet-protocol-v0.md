---
title: Sovereign Build Packet Protocol v0
path: spec-forge/sovereign-build-packet-protocol-v0.md
slug: sovereign-build-packet-protocol-v0
doc_type: protocol_spec
status: forge_draft
created: "2026-05-06"
canonical: false
summary: Forge-stage protocol for dispatching scoped build work through DHARMA-owned task, bridge, checkpoint, audit, and gate primitives without inventing a parallel packet runtime.
---

# Sovereign Build Packet Protocol v0

Status: forge-stage draft. This document is not canonical repo truth until explicitly promoted from `spec-forge/` to `specs/`.

## 1. Purpose

The Sovereign Build Packet Protocol defines how DHARMA decomposes, dispatches, reviews, fixes, and seals scoped build work while reusing existing DHARMA primitives.

The protocol MUST prefer composition over invention. It MUST NOT introduce a parallel packet runtime, a new SQLite state model, or new source-code packet classes in v0.

The protocol exists to make build work:

- scoped before execution
- attributable during execution
- reviewable before merge
- gate-checked before seal
- human-approved before integration

## 2. Non-Goals

v0 MUST NOT automate:

- merge to main
- hot-file scope expansion
- provider or routing migration
- Operator Brief or Daily Insight work
- ontology refactor
- memory consolidation
- dashboard or API changes
- cross-packet cleanup
- recursive sub-BuildPackets
- self-modifying gate requirements

v0 MUST NOT edit these source modules as part of protocol implementation:

- `dharma_swarm/orchestrate_live.py`
- `dharma_swarm/swarm.py`
- `dharma_swarm/frontier_council.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/insight_brief.py`

## 3. Existing Substrate

v0 defines protocol representations over existing DHARMA-owned primitives.

| Protocol concept | Existing substrate | Location |
|---|---|---|
| BuildPacket | `Task`-shaped record with protocol metadata | `dharma_swarm/models.py` |
| WorkPacket | `OperatorBridgeTask`-shaped transport record | `dharma_swarm/operator_bridge.py` |
| ReviewPacket | `CheckpointRecord`-shaped record | `dharma_swarm/contracts/common.py` |
| FixupPacket | child `OperatorBridgeTask`-shaped transport record | `dharma_swarm/operator_bridge.py` |
| ProofPacket | `RuntimeEnvelope` with `event_type="audit.event"` | `dharma_swarm/runtime_contract.py` |
| Task FSM | `TaskBoard` transition policy | `dharma_swarm/task_board.py` |
| In-process events | `SignalBus` | `dharma_swarm/signal_bus.py` |
| Persistent events | `MessageBus` | `dharma_swarm/message_bus.py` |
| Telos gate | `check_with_reflective_reroute(...)` | `dharma_swarm/telos_gates.py` |
| Kernel guard | `check_kernel_integrity(...)` | `scripts/uplift_guards/kernel_guard.py` |
| Hot-path adversarial review | `DualAudit` | `dharma_swarm/dual_audit.py` |

These substrates are not identical to the protocol concepts. They are the storage, transport, audit, and gate surfaces that v0 maps onto.

## 4. Packet Representation

v0 packet names are protocol roles, not new Python classes.

### 4.1 BuildPacket

A BuildPacket MUST be represented as a `Task`-shaped record whose `metadata.kind` is `build_packet`.

Required metadata:

```json
{
  "kind": "build_packet",
  "protocol_version": "v0",
  "spec_path": "string",
  "telos_statement": "string",
  "hot_files": ["string"],
  "forbidden_files": ["string"],
  "forbidden_domains": ["string"],
  "gates_required": ["telos"],
  "proof_command": "string",
  "child_task_ids": ["string"],
  "human_approver": "dhyana",
  "approval_signature": "string",
  "max_iterations": 2,
  "created_at": "iso8601"
}
```

`approval_signature` is an integrity commitment over scope and telos. v0 MUST NOT treat it as strong identity unless a human-controlled signing mechanism exists.

### 4.2 WorkPacket

A WorkPacket MUST be transported as an `OperatorBridgeTask`-shaped record whose `payload.kind` is `work_packet`.

Required payload:

```json
{
  "kind": "work_packet",
  "protocol_version": "v0",
  "parent_build_packet_id": "string",
  "lead_agent": "string",
  "builder_agent": "string",
  "allowed_paths": ["string"],
  "forbidden_paths": ["string"],
  "worktree_path": "string",
  "scoped_tests": ["string"],
  "max_diff_lines": 200,
  "checkpoint_ids": ["string"]
}
```

Required constraints:

```json
["no_merge", "no_push", "no_shell_exec", "scope_locked"]
```

Required output contract:

```json
["diff", "test_output", "checkpoint_ref"]
```

### 4.3 ReviewPacket

A ReviewPacket MUST be represented as a `CheckpointRecord`-shaped record whose `metadata.kind` is `review_packet`.

Required metadata:

```json
{
  "kind": "review_packet",
  "protocol_version": "v0",
  "work_packet_id": "string",
  "reviewer_agent": "string",
  "builder_agent": "string",
  "diff_ref": "string",
  "gate_results": {
    "gate_name": {
      "result": "pass|fail|hold",
      "reason": "string",
      "evidence": "string"
    }
  },
  "findings": [
    {
      "finding_id": "string",
      "severity": "info|warning|error|blocker",
      "file": "string",
      "line": 0,
      "claim": "string",
      "evidence": "string",
      "gate_id": "string"
    }
  ],
  "decision": "pass|fixup|reject"
}
```

`decision="pass"` maps to `CheckpointStatus.APPROVED`.

`decision="reject"` maps to `CheckpointStatus.REJECTED`.

`decision="fixup"` maps to `CheckpointStatus.DRAFT` with `metadata.decision="fixup"` so the overload is explicit.

### 4.4 FixupPacket

A FixupPacket MUST be transported as a child `OperatorBridgeTask`-shaped record whose `payload.kind` is `fixup_packet`.

Required payload:

```json
{
  "kind": "fixup_packet",
  "protocol_version": "v0",
  "parent_work_packet_id": "string",
  "parent_review_checkpoint_id": "string",
  "original_builder_agent": "string",
  "fixup_agent": "string",
  "scoped_findings": ["string"],
  "fixup_allowed_paths": ["string"],
  "iteration": 1
}
```

### 4.5 ProofPacket

A ProofPacket MUST be represented as a `RuntimeEnvelope` with `event_type="audit.event"` and a payload whose `gate` is `proof_seal`.

Required payload:

```json
{
  "build_packet_id": "string",
  "gate": "proof_seal",
  "result": "pass|hold",
  "reason": "string",
  "gate_results_aggregate": {
    "gate_name": {
      "pass_count": 0,
      "fail_count": 0,
      "hold_count": 0
    }
  },
  "test_outputs_ref": "string",
  "diff_summary": {
    "files": 0,
    "added": 0,
    "removed": 0
  },
  "signed_by": ["string"],
  "witness_log_ref": "string",
  "child_checkpoint_ids": ["string"],
  "merge_decision": "seal|hold"
}
```

The envelope MUST pass `validate_envelope(...)`. Failure to validate MUST hold or abandon the build.

## 5. Lifecycle

The protocol lifecycle is:

```text
DRAFT
  -> DECOMPOSED
  -> DISPATCHED
  -> IN_PROGRESS
  -> REVIEW
  -> APPROVED | FIXUP_OPEN | REJECTED
  -> FIXUP_DONE
  -> REVIEW
  -> PROOF_SEALED
  -> MERGED | HELD | ABANDONED
```

`MERGED` is always a human action in v0. The protocol may produce a sealed ProofPacket, but it MUST NOT merge automatically.

Protocol lifecycle states are higher-level build states. Implementations that persist into `TaskBoard` MUST map them onto canonical `TaskStatus` values without bypassing the existing FSM.

## 6. Role Permissions

| Role | May issue | May write | May approve | Identity rule |
|---|---|---|---|---|
| Human approver | scope, hot files, final merge | metadata decisions | BuildPacket and merge | v0 human is Dhyana |
| Coordinator | decomposition proposal | metadata only | nothing | cannot self-approve hot scope |
| Lead | WorkPacket details | bridge dispatch records | builder selection | may equal coordinator in pilots |
| Builder | implementation diff | `allowed_paths` in own worktree | nothing | exactly one builder per WorkPacket |
| Reviewer | ReviewPacket | checkpoint record | pass, fixup, reject | MUST differ from builder |
| Fixup agent | scoped fixup diff | `fixup_allowed_paths` only | nothing | MUST differ from original builder in v0 |

## 7. Invariants

Each invariant has a required failure behavior.

| Invariant | Failure behavior |
|---|---|
| One builder per WorkPacket | reject duplicate claim |
| Builder edits only inside `allowed_paths` | reject WorkPacket |
| `forbidden_files` and all `allowed_paths` are disjoint | hold before dispatch |
| Hot files require explicit human scope approval | hold before dispatch |
| Reviewer differs from builder | reject ReviewPacket |
| Fixup scope is a subset of parent WorkPacket scope | reject FixupPacket |
| Fixup findings are a subset of parent review findings | reject FixupPacket |
| Fixup iteration is `<= max_iterations` | abandon or require human amendment |
| No merge without sealed ProofPacket and human approval | hold merge |
| Telos gate runs at decomposition and proof seal | hold transition |
| All live transitions emit on both buses | protocol violation; hold build |
| Worktree state is disposable | reject hidden dependency on worktree-only state |
| Diff line count is `<= max_diff_lines` | reject WorkPacket |
| Checkpoint exists before review | hold review |
| Forbidden domains never appear in allowed paths | hold before dispatch |
| Kernel guard passes for kernel-touching diffs | reject WorkPacket |
| ProofPacket envelope validates | hold or abandon |

## 8. Event Vocabulary

Live implementations MUST dual-publish every protocol transition:

- `SignalBus.get().emit({"type": "...", ...})`
- `MessageBus.emit_event("...", task_id=..., agent_id=..., payload=...)`

Closed v0 event set:

- `build.decomposed`
- `build.dispatched`
- `work.claimed`
- `work.heartbeat`
- `work.checkpoint`
- `work.review_ready`
- `review.signed`
- `fixup.dispatched`
- `fixup.completed`
- `proof.sealed`
- `build.merged`
- `build.rejected`
- `build.abandoned`

Unknown `build.*`, `work.*`, `review.*`, `fixup.*`, or `proof.*` events MUST be rejected by protocol helper code.

## 9. Quality Gates

Review MUST run gates in this order:

1. Scope check: changed paths, forbidden paths, and diff line budget.
2. AgentOps structural ban: no merge, push, no-verify, or unapproved shell execution in recorded builder actions.
3. Scoped tests: deterministic command or explicit test paths.
4. Telos gate: review action checked with reflective reroute.
5. Kernel guard: required for kernel-touching diffs.
6. DocOps integrity: required for manifest-affecting diffs.
7. DualAudit: required for hot-file diffs.
8. Guardian baseline: fail if a new blocker appears since BuildPacket creation.

Each gate MUST write evidence into the ReviewPacket. A gate without evidence is a failed gate.

## 10. Forbidden Domains

v0 decomposition MUST reject WorkPackets whose allowed paths touch:

- Operator Brief
- Daily Insight
- ontology refactor
- memory consolidation
- dashboard
- API
- provider or routing migration
- broad cleanup unrelated to the BuildPacket telos

The default forbidden source files include:

- `dharma_swarm/orchestrate_live.py`
- `dharma_swarm/swarm.py`
- `dharma_swarm/frontier_council.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/insight_brief.py`

## 11. Acceptance Criteria

v0 is acceptable only when Pilot-00 proves that the protocol can produce a human-readable dispatch plan for a trivial safe change without touching source, creating worktrees, spawning agents, or writing SQLite state.

Pilot-00 acceptance is defined separately in `spec-forge/sovereign-build-packet-pilot-00.md`.

## 12. Open Questions

These questions MUST be resolved before live mode:

- Whether `TaskBoard` and `OperatorBridge` need adapter glue for a clean BuildPacket to WorkPacket handoff.
- Where ProofPacket envelopes should be durably stored next to witness logs.
- Whether `approval_signature` should remain a scope hash or become an actual human signature.
- Whether `CheckpointRecord` status overloading for fixup is tolerable beyond v0.
- Which existing AgentOps banned-subcommand set is canonical for protocol reuse.
- How Guardian baseline deltas should be compared in a deterministic way.
