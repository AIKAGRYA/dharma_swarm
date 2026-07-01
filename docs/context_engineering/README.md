# Context Engineering Packet Library

This directory is the repo-local context engineering layer for Dharma Swarm.
It does not create a new truth store. It gives agents precise, bounded context
contracts over the owners that already exist: `make onboard`,
`docs/governance/ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, runtime
receipts, reports, wiki/vector projections, and code.

## What This Solves

Generic onboarding is good for orientation, but it is not enough when an agent
is pointed at one organ. These packets answer:

- which files own the truth for this organ;
- what live state must be probed before acting;
- which retrieval queries are worth running;
- which commands verify reality;
- what must never be claimed without receipts;
- what a useful handoff looks like.

## Files

- `CONTEXT_ENGINEERING_FRONTIER_2026-06.md`: current research and practice
  synthesis through late June 2026, with source links.
- `PACKET_SCHEMA.md`: reusable packet shape and quality bar.
- `CONTEXT_PACKET_INDEX.json`: routing index for agents and scripts.
- `packets/*.md`: ten organ-specific context packets.

## Default Use

Treat a packet as a bounded work contract, not background reading.

1. Run `make onboard`.
2. Choose one packet from `CONTEXT_PACKET_INDEX.json` or the router.
3. Load the packet's `Vision Anchors`, `Current Reality Anchors`, and `Dense Docs`.
4. Read only the required first-read paths for the scoped task.
5. Probe live state before modifying code or making claims.
6. Do one bounded task.
7. Verify narrowly.
8. Leave the packet's required handoff receipt shape.
9. Run `make offboard` with the packet id, verification, artifacts, claims not
   made, residual risk, and next step.

If packet content disagrees with `make onboard`, the filesystem, git log, or the
declared owner files, trust the owners and update the packet.

Use owner files for intent and design claims, probes for current state, receipts
for proof, and retrieval/report artifacts for historical context. Label
inferences as inferences. Do not cite model memory, stale prose, or private
material as authority.

## Router

Use the read-only router when you know a topic or touched path but not the packet
id:

```bash
python3 scripts/governance/context_packet_router.py "SAB first spark witness"
python3 scripts/governance/context_packet_router.py --path dharma_swarm/runtime_provider.py
python3 scripts/governance/context_packet_router.py --id ctx.sab-flywheel --print-packet
python3 scripts/governance/context_packet_router.py --id ctx.model-provider-routing --show-anchors
python3 scripts/governance/context_packet_router.py "provider fallback" --path dharma_swarm/runtime_provider.py --json --hydrate
```

## Packet Evolution Rule

When evolving these packets, request a multi-agent/model review council when
practical, with at least five distinct lanes requested. If fewer than five lanes
respond, or no council is run, record the skip or failure reason in a handoff
receipt. Packet changes must preserve explicit vision anchors, current-reality
anchors, dense docs, work-lane anchors, evidence boundaries, and future-agent
review hooks.

Current metabolized handoff for this packet-system upgrade:

- `reports/handoffs/CONTEXT_PACKET_SYSTEM_METABOLIZED_2026-07-02.md`
