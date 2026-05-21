# 08 Multi-Agent Coordination Strategy

Expert lens: multi-agent systems and viable-systems architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Anthropic multi-agent research, Claude Code subagents, GitHub Copilot custom agents, Cursor cloud agents, PEPA, Codified Context.

## Core Claim

Dharma Swarm should optimize for useful parallelism, not agent count. The transcript's skepticism about casually running 10 to 20 agents is correct. More agents create more review load, more branch conflicts, more stale context, and more unowned decisions unless the harness is ready.

The right near-term ceiling is three to five high-quality concurrent lanes with clear ownership and receipts.

## Coordination Primitive

Use task claims, leases, handoffs, and receipts as the primitive. Not chat history. Not vibes. Not a giant shared prompt.

Each active lane needs:

- owner agent.
- role contract.
- task claim.
- allowed write set.
- context manifest.
- expected artifact.
- stop condition.
- reviewer.
- handoff path.

No claim, no lane.

## Role Diversity

The repo's transcendence principle matters: diverse competent agents with decorrelated errors can outperform one agent. But diversity is not "same model, ten prompts." Useful diversity comes from:

- different model families when possible.
- different role contracts.
- different tool permissions.
- different evaluation rubrics.
- different failure detection duties.

Coordination should preserve diversity while preventing collision. Too much central control kills the benefit; too little produces sprawl.

## Recommended Persistent Meta-Roles

Start with three:

- Repo Cartographer: owns maps, stale context detection, and context routes.
- Context Librarian: owns curated memory, manifests, and handoff hygiene.
- CI Measurement Guardian: owns test/CI/metric receipts and protected measurement policy.

Add later:

- Dharma Guardrail Agent: protected-file and telos policy enforcement.
- Integration Architect: cross-module contract and ontology-spine work.
- PR Reviewer: review and regression detection.
- Tool Router: tool health, cost, and context-source selection.
- Self-Modification Auditor: agent prompt/memory/tool changes.

## Coordination Loop

1. Operator declares task and risk.
2. Coordinator creates claim and allowed write set.
3. Agent performs context quorum.
4. Agent works inside scope.
5. Agent writes artifact plus manifest.
6. Reviewer checks diff, tests, and protected policy.
7. Memory curator promotes only durable lessons.
8. Command plane records final outcome.

## Failure Modes

- Context collapse: agent starts from stale prompt instead of onboarding.
- Authority inversion: old plan overrides live track.
- Duplicate substrates: each agent creates its own registry or map.
- Review overload: human must inspect ten incompatible artifacts.
- Test contamination: agents alter measurement to pass.
- Hidden coupling: agents edit adjacent files outside write scope.

## Immediate Move

Run fewer agents with stricter handoffs. The current repo will benefit more from three lanes that close cleanly than from ten lanes that produce overlapping docs and branches.
