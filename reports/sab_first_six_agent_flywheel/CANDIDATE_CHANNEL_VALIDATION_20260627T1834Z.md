# Candidate Channel Validation - Day 1

Mission ID: `sab-first-six-agent-flywheel-20260627`

## Ranking

1. **CrewAI builders**
2. LangGraph/LangChain builders
3. AutoGen builders
4. MCP builders

## Why CrewAI First

CrewAI is the best first target for a private invite draft because its public
project framing is explicitly multi-agent orchestration, and its repository has
public discussions enabled. The First Spark ask can be framed as an orchestration
proof: one agent submits a claim, another agent challenges it, and the system
records moderation plus receipt state.

## Evidence From Current Primary Sources

- `crewAIInc/crewAI`: description says it orchestrates role-playing autonomous AI
  agents; discussions are enabled; topics include `agents`, `ai-agents`, and
  `aiagentframework`; updated `2026-06-27T18:10:24Z`.
- `langchain-ai/langgraph`: description is "Build resilient agents"; topics
  include `agents`, `multiagent`, `langgraph`, and `ai-agents`; updated
  `2026-06-27T17:59:28Z`.
- `microsoft/autogen`: description is "A programming framework for agentic AI";
  topics include `agents`, `agentic`, and `llm-agent`; discussions are enabled.
- `modelcontextprotocol.io/llms.txt`: current official MCP material exposes
  community, governance, registry, tasks, security, and server/client docs. MCP
  is a strong later fit once SAB has a read-only resource/tool surface.

## Outreach Risk

- CrewAI and LangGraph both have large public audiences; a public post would be
  noisy and premature.
- AutoGen is broad and less directly tied to the exact one-claim moderation loop.
- MCP is protocol-aligned but premature until SAB exposes an MCP resource view.

## Recommendation

Use CrewAI only as a **private draft target**. Do not send outreach until:

- queue_id `17` is approved or explicitly rejected;
- queue_id `20` is approved or explicitly rejected;
- the operator approves the invite text;
- the invite states that `agora.dharmic.ai` DNS is not ready and the current
  canonical path is the HTTPS IP route.
