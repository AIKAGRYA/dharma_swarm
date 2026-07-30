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
## Beads fence status (2026-07-29)

The fence above was tested against the walking-mode plan's need for a
dependency-aware, git-shareable task medium and **AFFIRMED** — the need is
met by joining `task_board.py` ready-set semantics with the roaming
mailbox, not by adopting a dependency. The decision, its rationale, and
its falsifiable revisit criteria live in the dedicated record:
[`docs/architecture/ADRs/ADR-010-beads-fence-task-medium-join.md`](ADRs/ADR-010-beads-fence-task-medium-join.md).
(One authority role per file — this map stays a wiring map;
`docs/AGENTS.md`.)
