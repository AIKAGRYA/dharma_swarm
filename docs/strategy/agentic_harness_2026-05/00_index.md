# Agentic Harness Strategy Pack

Date: 2026-05-21
Scope: strategy only. No runtime code, schema, agent promotion, or command-plane implementation is made by this packet.

## Plain-English Thesis

Dharma Swarm does not need one larger prompt or one magic codebase-context tool. It needs a strategy brain and an agentic harness that force persistent agents to gather evidence from multiple imperfect sources, preserve the useful conclusions, act only inside role and trust boundaries, and measure whether their work improves the repo instead of merely increasing activity.

The user-supplied transcript frames the current inflection correctly: Software 3.0 makes the model, prompt, tools, and context window part of the programmable substrate. The repo-specific implication is blunt: do not build more software 1.0 plumbing around tasks a frontier model can already do with a prompt and tool call. Build agent-first infrastructure, verifiable loops, repo context manifests, memory discipline, and coordination surfaces that let many agents work without turning the repo into unreviewable sprawl.

## What This Folder Is

This folder is the first strategy-brain layer for Dharma Swarm. It should help new agents and the principal answer:

- What should we build first?
- What should we refuse to build yet?
- Which context tools matter, and how should they work together?
- How do we keep multi-agent work from becoming repo sprawl?
- What current frontier systems are teaching us?
- How do we turn persistent agents into measured, governed contributors?

## Files

Shared base:

- `00_local_evidence_base.md`: 33 local files/modules read before this synthesis.
- `00_external_research_sources.md`: current external sources used for strategy calibration.

Expert strategy memos:

- `01_software_3_strategy_brain.md`: Software 3.0 product and moat strategy.
- `02_context_quorum_harness_strategy.md`: context quorum and agentic harness design.
- `03_repo_cartography_and_ontology_strategy.md`: codebase map, ontology, and anti-sprawl strategy.
- `04_memory_palace_strategy.md`: memory as a governed operating system, not a dump.
- `05_governance_and_security_strategy.md`: trust boundaries, MCP/tool safety, and protected surfaces.
- `06_measurement_and_verifiability_strategy.md`: Omega, HP, CI, and performance proof.
- `07_command_plane_operator_strategy.md`: observatory/cockpit command-plane implications.
- `08_multi_agent_coordination_strategy.md`: coordination without over-centralization.
- `09_tool_ecosystem_and_router_strategy.md`: large-context tool routing and cost discipline.
- `10_persistent_identity_cultivation_strategy.md`: L1 to L4/L5 cultivation path.

## Master Recommendation

Build a small reliable coordination spine before any more ambitious agent autonomy:

1. Keep `make onboard` as the entrypoint.
2. Make context manifests and handoffs mandatory for Q2+ work.
3. Promote the runtime spine objects before abstract philosophy terms.
4. Treat memory writes as governed artifacts with source refs and expiry.
5. Route agents through protected-file policy, CI evidence, and measurement gates.
6. Use cloud/background agents only when their work can land as reviewable PRs with logs and artifacts.
7. Maintain a strategy folder like this as the high-level brain that prunes distraction.

The goal is not 20 agents running at once. The goal is three to five role-clear agents producing evidence-backed, reviewable, measurable work without exhausting the human operator.
