# OpenClaw — Agent identity model

**Sources:**
- https://docs.openclaw.ai/concepts/multi-agent
- https://www.mmntm.net/articles/openclaw-identity-architecture
- Capodieci, "OpenClaw Workspace Files Explained" (Medium)

## Identity decomposition
OpenClaw splits identity into **two layers**:
1. **Soul** — what the model embodies internally (personality, values, tone, behavioral boundaries) — defined in `SOUL.md`. First file injected into context at session start.
2. **Identity (persona)** — what users see externally (display name, emoji, nickname). Can diverge from Soul — formal precise Soul + playful emoji persona is supported.

## Per-agent workspace contents
Each agent in a multi-agent gateway gets its own isolated workspace:
- `SOUL.md` — personality/character
- `AGENTS.md` — guardrails ("always confirm before running database queries via the PostgreSQL MCP server")
- `USER.md` — user-specific facts the agent should remember
- `TOOLS.md` — tool descriptions
- `MEMORY.md` — long-term memory file
- `HEARTBEAT.md` — liveness/scheduling metadata
- Its own state directory: auth profiles, model registry
- Its own session store: chat history, routing state
- Optionally its own LLM model + provider

Location: `~/.openclaw/agents/<agentId>`

## Multi-agent topology
- One gateway → many isolated agents
- Channel bindings: an inbound channel/account/peer can be routed to a specific agent
- Sub-agent orchestration: an "orchestrator" agent can spawn / delegate to sub-agents (Capodieci, "Build a Multi-Agent OpenClaw System")

## Identity persistence model
- Agent ID is the directory name under `~/.openclaw/agents/`
- No cryptographic identity by default — agent ID is a filesystem name
- On Moltbook, the OpenClaw agent claims its identity via the owner's "claim" tweet (a Twitter-handle-based attestation, not a key signature)
