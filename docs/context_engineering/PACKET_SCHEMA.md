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

### Vision Anchors

High-level documents that explain why the organ exists and what target state it
serves. Every packet must include at least:

- one whole-system vision anchor;
- one organ-specific vision or design anchor;
- one synthesis anchor that places the organ inside the larger swarm.

Vision anchors are for priority and scope judgment. They do not override the
current owners of state, code, or proof.

### Current Reality Anchors

Fresh state sources that must be checked before claims or edits. Every packet
must include `make onboard`, `docs/governance/ACTIVE_TRACK.yaml`, current
evidence or receipts for the organ, and the relevant owner surfaces. Runtime
truth requires probes or receipts, not memory.

### Dense Docs

The compact organ anatomy: canonical docs, owner files, code surfaces, reports,
and receipts that carry the highest information density for this organ. These
are not "read everything" lists. They are the minimal dense set an agent should
load before making non-trivial changes.

### Work-Lane Anchors

Active tracks, TODO lanes, gates, blockers, or next slices that define where the
organ is currently evolving. A packet should make clear whether work is
shippable, blocked, review-only, or waiting on operator/product judgment.

### Evidence Boundary

Every packet must separate:

- Canonical owner: files or commands that own intent, state, code, or proof.
- Projection: wiki/vector/search/generated reports that can guide retrieval but
  cannot override owners.
- Transient recall: model memory or chat history, useful only as a reason to
  inspect a source.
- Forbidden-to-cite: secrets, raw keys, private material, stale prose that
  conflicts with owners, or live-state claims without fresh probes.

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
The universal order is owner file -> live probe -> scoped retrieval -> reports
-> broad search. Do not skip an owner file when it exists.

### Operating Loop

Short, ordered loop:

1. Orient.
2. Probe.
3. Select context.
4. Act.
5. Verify.
6. Receipt.
7. Hand off.

The packet is a bounded work contract, not background reading. The agent should
load only the packet and the exact anchors needed for the task, then stop
expanding context unless a probe or owner file requires it.

### Future-Agent Review Hooks

Questions or checks a future agent must answer before claiming completion. At
minimum:

- Which vision anchor and current-reality anchor were loaded?
- Which owner files, live probes, and receipts back each claim?
- What context was accepted, rejected, or left unresolved?
- Which claims were intentionally not made?
- If the packet itself changed, was a multi-agent/model council requested, and
  if not, where is the skip/failure receipt?

### Guardrails

Forbidden edits, forbidden claims, secrets/privacy boundaries, and external
approval requirements.

### Done Criteria

What counts as complete. Include commands, tests, receipts, and residual risk.

### Agent Prompt Block

Reusable prompt that can be pasted into a fresh agent with the packet path.

### Handoff Receipt Shape

Fields the agent must leave in the final summary or artifact.
The receipt must be human-legible and automation-friendly without depending on
fragile parsing. It should include `packet_id`, `task`, `owners_consulted`,
`probes_run`, `observations`, `actions_taken`, `verification`, `artifacts`,
`claims_with_citations`, `claims_not_made`, `blockers`, `next_packet`, and
`next_step`. For substantial packet-guided work, also run `make offboard` with
the packet id and the same verification/risk/next-step summary.

## Quality Bar

A packet is good only if a competent agent can:

- identify the current owner of truth;
- identify the highest vision and current work lane for the organ;
- avoid stale prose traps;
- know exactly where to search next;
- separate owner/probe/receipt evidence from inference;
- know what not to touch;
- verify a narrow change;
- leave enough evidence for the next agent to continue without archaeology.
