# Wiring And Loops - Slot 5

Status: active wiring map. Updated 2026-05-07.

This file names the canonical spinal bridge for build work. It does not create
a new orchestrator, board, dashboard, dependency, or packet format.

## Canonical Build Spine

```text
signals / scouts / zeitgeist / operator directive
-> ShaktiExecutive
-> opportunity_board.json
-> opportunity_refill
-> frontier_tasks_pending.jsonl
-> opportunity_dispatcher
-> TaskBoard
-> TelicSeam
-> Outcome / ValueEvent / Contribution
-> ShaktiExecutive feedback
```

Build packets use the same spine after the operator chooses one move:

```text
OpportunityCandidate or morning briefing
-> Pilot-00 compatible spec
-> BuildPacket / WorkPacket dry run
-> ReviewPacket / ProofPacket seal
-> DarwinEngine.apply_sealed_packet(shadow=True)
-> evolution archive
-> ShaktiExecutive feedback
```

## Adapter Map

| Adapter | File | Job | Boundary |
|---|---|---|---|
| Sealed Packet -> Darwin Shadow | `tools/build_protocol/cli.py` | Adds `shadow-apply <dryrun_root>` and calls `DarwinEngine.apply_sealed_packet(..., shadow=True)` | Shadow-only; live apply remains explicitly gated |
| Outcome -> Shakti Feedback | `dharma_swarm/shakti_executive/inputs.py` | Reads TelicSeam ontology objects, dispatcher health, campaign manifests, and sealed packet archive entries as `ExecutiveSignal`s | Shakti remains selector/intake brain, not executor |
| Opportunity -> Build Spec | `tools/build_protocol/opportunity_to_spec.py` | Converts one `opportunity_board.json` row into the same Pilot-00 markdown spec shape | No second packet format |

## Operator Commands

Installed command shape:

```bash
dharma-build opportunity-to-spec --opportunity-id <id>
dharma-build plan ~/.dharma/build_protocol/specs/<spec>.md
dharma-build seal ~/.dharma/build_protocol/dryruns/<run>
dharma-build shadow-apply ~/.dharma/build_protocol/dryruns/<run>
```

Module fallback from repo root:

```bash
python -m tools.build_protocol.cli opportunity-to-spec --opportunity-id <id>
python -m tools.build_protocol.cli shadow-apply ~/.dharma/build_protocol/dryruns/<run>
```

## Guardrails

- No new swarm manager.
- No Beads, LangGraph, CrewAI, or other orchestration dependency.
- No new board file.
- No runtime mutation from Pilot-00.
- `shadow-apply` never live-applies; it archives a Darwin shadow evaluation.
- Live apply remains behind the existing Darwin guards and explicit autonomy gates.
- TelicSeam remains the feedback and memory source.
- Shakti ranks and selects; it does not execute.

## Closed Edges

BR-003 now has a concrete sealed-packet consumer: `dharma-build shadow-apply`
loads `build_packet.json`, `review_packet.json`, and `proof_packet.json`,
reruns the proof command, gates through Darwin, and archives the result without
applying the diff.

BR-002 now has a feedback reader edge: `ShaktiExecutive` sees `Outcome`,
`ValueEvent`, `Contribution`, dispatcher health, campaign manifests, and sealed
packet archive entries as scored signals on the next selector pass.

## Dogfood Evidence

On 2026-05-07, a temp opportunity board row under `/tmp` was converted through
the full bridge without mutating repo source:

```text
opportunity_board.json
-> dharma-build opportunity-to-spec
-> dharma-build plan
-> dharma-build seal
-> dharma-build shadow-apply
-> ShaktiExecutive read sealed packet archive feedback
```

The Darwin shadow result accepted the packet, did not apply it live, reran the
fresh proof command with exit code 0, and archived the result with pass_rate
1.0. The follow-on Shakti read surfaced it as `darwin_archive` /
`sealed_packet_archive`.

## Still Open

- Live apply is intentionally not opened here.
- Cron/runbook wiring belongs in Slot 8 only after cron restart safety remains
  verified.
- VentureCell polymorphism is not solved here.
- Ontology/runtime store synchronization is not solved here.
## Decision record — Beads fence AFFIRMED, task-medium joined natively (2026-07-29)

**Context:** the walking-mode loop-closure plan (PR-D;
`docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md` §2.2) needs a
dependency-aware, git-shareable task medium for its lanes. The fence above
("No Beads, LangGraph, CrewAI, or other orchestration dependency") was
read in full before this change, not routed around.

**Decision:** the fence is **AFFIRMED**. The need is met by joining two
substrates this repo already owns instead of adopting a dependency:
`dharma_swarm/task_board.py` contributes the ready-set semantics
(dependencies must be complete before a task is claimable —
`task_board.py` `_READY_QUERY`), and `dharma_swarm/roaming_mailbox.py`
contributes the git-native, one-JSON-file-per-task shareable medium. The
join is a `depends_on` field plus a `ready_tasks()` reader on the mailbox
— no new store class (Anti-Slop Rule 2), no external dependency, no new
board file (this fence's own third clause).

**Falsifiable revisit criteria** — reopen the Beads question explicitly,
in a dated amendment to this record, if ANY of the following is observed
after 2–3 weeks of hardening-lane operation:

1. ready-set misbehavior: a lane claims a blocked task or starves a ready
   one, attributable to the join rather than to task authoring;
2. a real cross-repo sharing need: a second repository must consume the
   same task graph and git-sync of `roaming_mailbox/` proves insufficient;
3. persistent agent fumbling: lane or subagent sessions repeatedly
   mis-handle the bespoke board where a standard tool's conventions would
   have been understood.

Absent those observations, the fence stands and silent adoption of an
orchestration dependency remains a governance violation.
