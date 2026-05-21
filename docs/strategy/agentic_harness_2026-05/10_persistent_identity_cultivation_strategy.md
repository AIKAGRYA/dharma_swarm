# 10 Persistent Identity Cultivation Strategy

Expert lens: persistent-agent cultivation architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Claude Code persistent subagent memory, Letta stateful agents, PEPA, STATE-Bench, GitHub Copilot custom agents, Cursor cloud agents.

## Core Claim

Dharma Swarm should cultivate persistent agents slowly. Only L4+ counts as a real persistent agent. Registered workers, scripts, disposable subagents, and wake loops without identity/memory/action evidence must not be inflated.

The strategic goal is not to anthropomorphize agents. It is to give durable roles enough identity, memory, environment, skill tracking, and evaluation to improve across weeks.

## Passport

Every candidate persistent agent should have an agent passport:

```yaml
agent_id: context_librarian
role: Context Librarian
tier: L2
mission: Keep high-signal context manifests, handoffs, and memory hygiene.
model_policy: provider-routed, no fixed secret values.
workspace_root: /Users/dhyana/dharma_swarm
memory_root: /Users/dhyana/.dharma/agents/context_librarian
allowed_tools:
  - read_files
  - context_tools
  - handoff_writer
forbidden_without_permission:
  - CI workflows
  - measurement harnesses
  - provider keys
  - agent promotion files
promotion_evidence:
  - context manifests
  - handoffs reused by other agents
  - stale-map corrections
```

## Personal Filesystem

Keep it dense:

- `PROFILE.md`: role, tier, authority, model/provider policy.
- `MISSION.md`: current mission and non-goals.
- `MEMORY.md`: curated high-signal role memory.
- `CONTEXT_MANIFEST.latest.json`: latest context quorum receipt.
- `DECISIONS.md`: durable decisions with source refs.
- `KNOWN_UNKNOWNS.md`: unresolved questions and stale assumptions.
- `RISK_LOG.md`: recurring hazards and protected surfaces.
- `HANDOFF.md`: current continuation packet.
- `receipts/`: raw tool and test receipts.

Avoid:

- Long uncurated transcripts.
- Repeating repo docs in agent memory.
- Memory files without source refs.
- Agent self-mythology.
- Per-agent copies of global policy.

## Promotion Path

L1 to L2:

- identity file.
- memory namespace.
- durable task log.

L2 to L3:

- registered wake loop.
- heartbeat.
- failure taxonomy.

L3 to L4:

- recent autonomous successful action.
- model/provider receipt.
- memory read/write receipt.
- environment receipt.
- observable logs.

L4 to L5:

- role continuity.
- stable preferences within role.
- self-reference to past work.
- skill/memory maintenance.
- multi-week behavior.

L5 to L6:

- arena evaluation.
- peer competition.
- skill acquisition.
- sandboxed environments.
- measurable improvement.
- auditability and retirement discipline.

## First Three To Cultivate

1. Repo Cartographer.
2. Context Librarian.
3. CI Measurement Guardian.

These are not necessarily the flashiest agents. They are the leverage agents. They reduce sprawl, improve future agent starts, and protect measurement integrity.

## Immediate Move

Do not promote any agent because it has a name or a folder. Require receipts. The first cultivation milestone is not "agent is alive"; it is "another agent successfully used its memory or handoff to do better work."
