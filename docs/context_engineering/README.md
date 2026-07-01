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

1. Run `make onboard`.
2. Choose one packet from `CONTEXT_PACKET_INDEX.json`.
3. Read only that packet plus its required first-read paths.
4. Probe live state before modifying code or making claims.
5. Leave the packet's required handoff receipt shape.

If packet content disagrees with `make onboard`, the filesystem, git log, or the
declared owner files, trust the owners and update the packet.

## Router

Use the read-only router when you know a topic or touched path but not the packet
id:

```bash
python3 scripts/governance/context_packet_router.py "SAB first spark witness"
python3 scripts/governance/context_packet_router.py --path dharma_swarm/runtime_provider.py
python3 scripts/governance/context_packet_router.py --id ctx.sab-flywheel --print-packet
```
