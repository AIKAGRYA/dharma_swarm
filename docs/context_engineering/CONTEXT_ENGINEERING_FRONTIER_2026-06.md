# Context Engineering Frontier, Late June 2026

Status: repo-local synthesis for Dharma Swarm packet design.
Cutoff: late June 2026 research/practice scan.
Purpose: turn the frontier into concrete integration rules for this repo.

## Executive Synthesis

Context engineering is the design of the full information environment an agent
uses at inference time: instructions, task state, examples, retrieved material,
memory, tools, schemas, permissions, traces, and proof requirements. It is not
just writing a better prompt. For Dharma Swarm, the high-ROI move is not another
wiki. It is a set of organ-specific context packets that force agents to load
the right owners, probes, retrieval scopes, and receipts before acting.

The practical frontier points to eight rules:

1. Treat context as a runtime surface, not a text blob.
2. Keep authority boundaries explicit: intent, surface, state, receipts.
3. Do not trust long context alone; use routing, summaries, anchors, and tests.
4. Make retrieval adaptive: ask whether retrieval is needed, what source family
   is authoritative, and whether the result is relevant enough to use.
5. Combine vector, lexical, graph, and live probes; each catches different
   failures.
6. Model memory as a write -> manage -> read loop with filtering, contradiction
   handling, privacy, and forgetting.
7. Route by tools and capabilities, not coarse agent names.
8. Evaluate the context layer itself with traces, receipts, and narrow gates.

## Source Notes

- Simon Willison's June 2025 writeup records the shift from "prompt
  engineering" to "context engineering" and cites the framing that industrial
  LLM apps require filling the context window with the right task description,
  examples, RAG, tools, state, history, and compaction:
  https://simonwillison.net/2025/Jun/27/context-engineering/
- A 2025 survey defines Context Engineering as systematic optimization of the
  inference-time information payload and organizes the field into retrieval and
  generation, processing, management, RAG, memory, tool reasoning, and
  multi-agent systems:
  https://arxiv.org/abs/2507.13334
- A March 2026 context engineering paper frames context as the agent's operating
  system and names five context quality criteria: relevance, sufficiency,
  isolation, economy, and provenance:
  https://arxiv.org/abs/2603.09619
- Anthropic's "Building Effective Agents" emphasizes simple composable patterns,
  the augmented LLM with retrieval/tools/memory, and choosing workflows versus
  agents based on the task:
  https://www.anthropic.com/engineering/building-effective-agents
- OpenAI Agents SDK docs organize agent design around specialist definitions,
  runtime state, sandboxing, orchestration, handoffs, guardrails, human review,
  tools, MCP, traces, and evals:
  https://developers.openai.com/api/docs/guides/agents
  https://developers.openai.com/api/docs/guides/tools
- Model Context Protocol specifies Resources, Prompts, and Tools from servers,
  plus Sampling, Roots, and Elicitation from clients, with explicit user consent
  and tool safety principles:
  https://modelcontextprotocol.io/specification/2025-06-18
- A2A 1.0 defines agent cards, tasks, messages, parts, artifacts, streaming, and
  async task management for opaque agent interoperability:
  https://a2a-protocol.org/latest/specification/
- GraphRAG shows why baseline vector RAG fails for "connect the dots" and
  holistic questions, and uses entity/relationship extraction, community
  summaries, and query modes:
  https://microsoft.github.io/graphrag/
- Self-RAG shows the value of adaptive retrieval and reflection instead of
  always retrieving a fixed number of passages:
  https://arxiv.org/abs/2310.11511
- Lost in the Middle, RULER, and LV-Eval show that larger context windows do
  not guarantee robust use of information, especially with middle-position
  facts, multi-hop tasks, distractors, and long sequences:
  https://arxiv.org/abs/2307.03172
  https://arxiv.org/abs/2404.06654
  https://arxiv.org/abs/2402.05136
- A 2026 agent-memory survey formalizes memory as write -> manage -> read and
  stresses contradiction handling, latency budgets, privacy, and multi-session
  evaluation:
  https://arxiv.org/abs/2603.07670
- Tool-to-Agent Retrieval argues that routing by coarse agent descriptions
  dilutes tool capability, and improves retrieval by embedding tools and parent
  agents in a shared space:
  https://arxiv.org/abs/2511.01854
- LangGraph's current memory docs reinforce a useful practical split: short-term
  thread checkpoints and long-term cross-thread stores:
  https://docs.langchain.com/oss/python/langgraph/persistence

## Dharma Swarm Integration Thesis

Dharma Swarm already has the hard pieces: `make onboard`, active tracks,
semantic aliases, memory retrieval, wiki/vector ingest, A2A/NATS, runtime
receipts, tmux substrate, live provider telemetry, and many agent seats. The
failure mode is not absence of context. The failure mode is that an agent can
ignore the right context because it is diffuse.

The next layer should therefore be packets, not another authority:

- packet = bounded context contract for one organ;
- index = route to the packet by aliases, surfaces, commands, and mission;
- live probes = force fresh state before claims;
- handoff receipt = preserve provenance and next action;
- retrieval scope = make wiki/vector/graph useful by naming exact queries and
  source families.

## Design Rules For Packets

1. Begin with the packet's authority model: what owns intent, surface, state,
   and proof.
2. Name the minimum first reads. Do not list everything.
3. Name live probes before build commands.
4. Put the highest-value facts at the top and bottom of the context payload.
   Long-context evaluations show the middle is fragile.
5. Include retrieval queries with reason and source family.
6. Include non-goals and forbidden claims.
7. Include a concrete done contract and handoff receipt shape.
8. Include the tool/agent routing decision: when to use a specialist, when to
   keep the manager in control, and when to require operator approval.
9. Preserve secrets boundaries and external-action consent boundaries.
10. Keep each packet updateable independently.

## Highest-ROI Build Path

1. Add this packet library and start using it manually.
2. Add a lightweight router that maps touched files or user intent to packet ids
   using `CONTEXT_PACKET_INDEX.json`.
3. Extend `make onboard` with a "recommended packets" section, read-only.
4. Teach `agent_onboard.py` or a new read-only command to emit a chosen packet
   plus live probe results as JSON.
5. Feed packet id, touched surfaces, retrieval diagnostics, and handoff receipt
   into evals so the system can measure context-use quality.

The first step is this documentation package. It is intentionally non-invasive:
it changes no runtime ownership and creates no new truth store.
