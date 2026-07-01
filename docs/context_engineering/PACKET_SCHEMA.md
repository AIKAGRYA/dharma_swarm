# Context Packet Schema

Use this schema for every organ packet in `packets/`.

## Required Sections

### Packet Header

- `Packet ID`: stable id.
- `Use When`: routing criteria.
- `Do Not Use When`: boundaries.
- `Authority Model`: intent owner, surface owner, state owner, proof owner.

### Mission

Plain-language purpose for the organ. Include the local repo interpretation,
not a generic domain description.

### First Reads

Small ordered stack:

- L0 Safety: global behavior and live state.
- L1 Route: active track or organ index.
- L2 Owner: code/docs that own the organ.
- L3 Evidence: reports, receipts, dashboards.
- L4 Search: targeted retrieval queries.
- L5 Seat: optional named-agent identity.

### Live Probes

Commands or file checks that must run before claims. Prefer read-only probes.
Flag which probes may touch network, external systems, or live services.

### Retrieval Contract

Queries to run against wiki, vector, memory, repo search, graph, or reports.
For each query, state why it is useful and what source family is authoritative.

### Operating Loop

Short, ordered loop:

1. Orient.
2. Probe.
3. Select context.
4. Act.
5. Verify.
6. Receipt.
7. Hand off.

### Guardrails

Forbidden edits, forbidden claims, secrets/privacy boundaries, and external
approval requirements.

### Done Criteria

What counts as complete. Include commands, tests, receipts, and residual risk.

### Agent Prompt Block

Reusable prompt that can be pasted into a fresh agent with the packet path.

### Handoff Receipt Shape

Fields the agent must leave in the final summary or artifact.

## Quality Bar

A packet is good only if a competent agent can:

- identify the current owner of truth;
- avoid stale prose traps;
- know exactly where to search next;
- know what not to touch;
- verify a narrow change;
- leave enough evidence for the next agent to continue without archaeology.
