# Source Notes

Survey date: 2026-05-20.

This file records source URLs and local cache paths used by the persistent-agents survey. Scores in `scorecard.jsonl` point to these cached files and to local code paths. External facts that needed current verification were checked against official project pages or source repositories where available.

## Nous / Hermes

- Hermes 3 official page: https://nousresearch.com/hermes3/
  - Local cache: `_cache/nous_hermes3.html`
  - Evidence: Hermes 3 is a model family with long-context, multi-turn, and function-calling claims. It is not itself a persistent agent runtime.
- Hermes 4 technical report / collection:
  - Search result evidence found official Nous PDF `https://nousresearch.com/wp-content/uploads/2025/08/Hermes_4_Technical_Report.pdf` and arXiv `https://arxiv.org/abs/2508.18255`.
  - Evidence used only to note that Hermes 4 exists as a model-family release. The score treats Hermes model releases as models, not agent runtimes.
- Hermes Function Calling GitHub: https://github.com/NousResearch/Hermes-Function-Calling
  - Evidence: tool-call and JSON-mode templates for Hermes models. This is model integration support, not persistent identity or memory.
- Hermes Agent GitHub: https://github.com/NousResearch/hermes-agent
  - Local cache: `_cache/nous_hermes_agent_README.md`
  - Evidence lines: 15, 22-25, 114-128.
  - Key facts: persistent memory, agent-curated memory, autonomous skill creation, FTS5 session search, cron scheduler, cloud/serverless terminal backends, OpenClaw migration.
- Forge Reasoning API: https://forge.nousresearch.com/
  - Evidence: configurable reasoning/planning API surface. No durable agent identity or long-term memory runtime was found in the fetched public page.

## Tier 1 Candidates

- Letta GitHub: https://github.com/letta-ai/letta
  - Local cache: `_cache/letta_README.md`
  - Evidence lines: 3, 12-22, 47-65.
- Letta stateful agents docs: https://docs.letta.com/guides/core-concepts/stateful-agents/
  - Local cache: `_cache/letta_docs_memory.html`
  - Evidence: page metadata states that stateful agents maintain memory and context across conversations; body describes agent memory blocks, message history, tools, and API retrieval.
- AI Garden GitHub: https://github.com/juliosuas/ai-garden
  - Local caches: `_cache/ai_garden_README.md`, `_cache/ai_garden_daily_evolution.yml`, `_cache/ai_garden_agent_manifest.json`
  - Evidence lines: README 7, 174, 182; workflow 3, 14, 47; manifest 9, 146-148.
- OpenClaw GitHub: https://github.com/openclaw/openclaw
  - Local cache: `_cache/openclaw_README.md`
  - Evidence lines: 150, 153, 155, 160-161, 168, 178, 256-260.
  - Note: several secondary sources discuss Steinberger/OpenAI/foundation status, but the score uses official README evidence for runtime capability. The post-acquisition governance story remains an open-contact question.
- Animus: https://www.animus.uno/
  - Local cache: `_cache/animus_home.html`
  - Evidence: public site lists Thalamus, SMCP, MCP support, and framework components. No durable identity or runtime persistence code was fetched in this pass.
- ElizaOS GitHub/docs: https://github.com/elizaOS/eliza and https://docs.elizaos.ai/
  - Local caches: `_cache/eliza_README.md`, `_cache/eliza_memory_state.html`, `_cache/eliza_runtime_lifecycle.html`
  - Evidence lines: README 9, 22, 33, 49, 145-150, 212, 217; docs page includes Memory & State, memory operations, relationships, document storage, and cleanup sections.

## Tier 2 Commercial / Closed

- Manus docs: https://manus.im/
  - Local cache: `_cache/manus_docs.html`
  - Evidence: public product docs describe an agent with its own computer, sandbox, internet, persistent filesystem, and independent task execution. Closed product; no inspectable durable agent identity evidence.
- Devin docs: https://docs.devin.ai/
  - Local caches: `_cache/cognition_devin_environment.html`, `_cache/cognition_blog_devin_builds_devin.html`
  - Evidence: official docs describe configured environments, snapshots, repos, tools, dependencies, and cloud tasks. Closed product; no inspectable durable agent identity evidence.
- Anthropic Claude Code and Computer Use docs:
  - Local caches: `_cache/anthropic_claude_code_memory.html`, `_cache/anthropic_computer_use.html`
  - Evidence: official docs cover project/user memory and computer-use/browser tool behavior. They do not establish independent durable agent identity.
- Cursor cloud/background agents:
  - Local caches: `_cache/cursor_cloud.html`, `_cache/cursor_background_agents.html`
  - Evidence: official page describes always-on agents, automations, schedules, event triggers, cloud sandboxes, PR output, MCP, and memory tool. Closed product; no durable agent identity evidence.
- Replit Agent:
  - Local caches: `_cache/replit_agent.html`, `_cache/replit_checkpoints.html`
  - Evidence: product docs describe agent task execution and checkpoints. Closed product; weak evidence for self-initiated persistent autonomy.
- OpenAI Codex / Operator:
  - Official current sources checked:
    - https://platform.openai.com/docs/codex
    - https://openai.com/codex/
    - https://help.openai.com/en/articles/11096431-openai-codex-cli-getting-started
    - https://openai.com/index/introducing-the-codex-app
    - https://openai.com/index/introducing-operator/
    - https://openai.com/index/computer-using-agent/
  - Local caches: `_cache/openai_codex_cloud.html`, `_cache/openai_codex_app.html`, `_cache/openai_operator.html`
  - Evidence: Codex cloud uses per-task cloud sandboxes and supports background/automation workflows; Operator/ChatGPT agent uses browser/computer actions. No public durable per-agent identity/memory model suitable for SAB scoring was found.
- Steinberger/OpenAI next-gen personal agents:
  - Evidence status: no official OpenAI product/runtime documentation was found that identifies a Steinberger-led persistent personal-agent runtime with inspectable identity and memory primitives. Treated as unscored rumor for capability, scored as no public evidence.

## Framework Lane

- LangGraph docs:
  - Local cache: `_cache/langgraph_persistence.html`
  - Context7 source: https://docs.langchain.com/oss/python/langgraph/persistence
  - Evidence: checkpointing, thread IDs, durable execution, per-thread persistence, memory across sessions.
- AutoGen docs:
  - Local cache: `_cache/autogen_state.html`
  - Context7 source: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html
  - Evidence: `save_state`/`load_state` for agents and teams, serializable team state, memory injection.
- CrewAI docs:
  - Local cache: `_cache/crewai_memory.html`
  - Context7 source: https://github.com/crewaiinc/crewai/blob/main/docs/en/concepts/memory.mdx
  - Evidence: unified memory, memory=True, short-term/long-term/entity/contextual memory concepts.
- Agno docs:
  - Local cache: `_cache/agno_storage.html`
  - Evidence: storage/session primitives and agent memory patterns.
- AutoGPT / SuperAGI / BabyAGI:
  - Local caches: `_cache/autogpt_README.md`, `_cache/superagi_README.md`, `_cache/babyagi_README.md`
  - Evidence: historical framework patterns, not participant-grade persistent agents by themselves.

## Local Internal Evidence

- dharma_swarm persistent agent/runtime:
  - `dharma_swarm/persistent_agent.py`: `PersistentAgent` line 117, cron setup line 186, wake loop line 299, self-task generation line 407, witness write line 459, run loop line 482.
  - `dharma_swarm/autonomous_agent.py`: `AgentIdentity`, `AutonomousAgent`, ReAct loop, memory load/save, tool allowlist/telos gate.
  - `dharma_swarm/agent_memory.py`: `AgentMemoryBank` line 69, save line 325, load line 335.
  - `dharma_swarm/agent_memory_manager.py`: SQLite-backed agent memory manager.
  - `dharma_swarm/agent_registry.py`: `AgentIdentity` line 146, `AgentRegistry` line 181, `identity.json`, `task_log.jsonl`, `fitness_history.jsonl` lines 189-191.
- dharma_swarm daemons/species:
  - `dharma_swarm/context_agent.py`: `ContextAgent` line 780, `run_cycle` line 801, `run_context_agent_loop` line 943.
  - `dharma_swarm/witness.py`: `WitnessAuditor` line 111, `run_cycle` line 135, `run_loop` line 173.
  - `dharma_swarm/evolution.py`: `DarwinEngine` line 226, `commit_if_worthy` line 3229, `daemon_loop` line 3310.
  - `dharma_swarm/economic_agent.py`: `EconomicAgent` line 404.
  - `dharma_swarm/revenue/scout_daemon.py`: `RevenueScoutDaemon` line 100.
  - `dharma_swarm/world_model.py`: `WorldModelAgent` line 259, `run_loop` line 275.
  - `dharma_swarm/thinkodynamic_director.py`: `ThinkodynamicDirector` line 1869, `run_loop` line 4915.
  - `dharma_swarm/overnight_director.py`: `OvernightDirector` line 262.
  - `dharma_swarm/roaming_dispatch_daemon.py`: `RoamingDispatchDaemon` line 69, `run_loop` line 136.
- dharmic-agora:
  - `agora/agents/voidcourier.py`: `VoidCourier` line 188.
  - `agora/agents/naga_relay.py`: `NagaRelay` line 255.
  - `agora/agents/viralmantra.py`: `ViralMantra` line 176.
  - `agora/agents/subagent_runner.py`: `SubagentRunner` line 36.
  - `agent_core/core/frontmatter_v2.py`: AIKAGRYA frontmatter parsing/validation.
  - `agent_core/core/witness_event.py`: `WitnessEvent` line 43, `append_event` line 84, `verify_log` line 135.
  - `agent_core/core/ore_bridge.py`: frontmatter/witness ingestion bridge.
  - `agent_core/agents/setu_warehouse/orchestrator.py`: `SetuOrchestrator` line 98.
  - `agent_core/agents/vajra_flywheel/flywheel.py`: `VajraFlywheel` line 87.
