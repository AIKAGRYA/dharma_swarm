# X4 - Frameworks

Frameworks are not scored against the operator-distance rubric. They are substrates, not participants. This lane extracts persistence, identity, and autonomy patterns worth porting.

## AutoGen

Evidence: `_cache/autogen_state.html:580-583`, `_cache/autogen_state.html:586`, `_cache/autogen_state.html:664-671`, `_cache/autogen_state.html:776-790`, and Context7 notes from Microsoft AutoGen docs.

AutoGen's useful primitive is explicit state serialization. Agents and teams expose `save_state`/`load_state`; team state includes agent states and message thread state; the docs show writing that state to disk or a database.

Pattern to port: every dharma_swarm agent participant should have a single exported state object with version, identity, memory pointers, active task, and pending obligations. That object should be loadable without relying on implicit host files.

Risk: save/load state is not the same as autonomy. It solves resumability, not operator-distance.

## CrewAI

Evidence: `_cache/crewai_memory.html`, Context7 notes from CrewAI docs.

CrewAI's relevant primitive is its unified memory surface. Memory can be enabled on agents or crews, supports long-term memory and entity/context memory concepts, and uses scoring across semantic similarity, recency, and importance.

Pattern to port: merge dharma_swarm's current memory tiers, stigmergy, and operator notes behind an agent-facing recall API that can answer "what should I remember right now?" with scored evidence.

Risk: role-based crews can look like agent autonomy while still being fully operator-scripted.

## LangGraph

Evidence: `_cache/langgraph_persistence.html`, Context7 notes from LangGraph persistence docs.

LangGraph has the clearest substrate pattern: thread IDs plus checkpointers. A thread ID is the primary key for storing/retrieving checkpoints; state is saved at each step; durable execution can resume after failures or human-in-the-loop interruptions; per-thread persistence enables multi-turn memory across invocations.

Pattern to port: dharma_swarm needs a `participant_thread_id` that binds identity, memory checkpoints, wake cycles, and contribution IDs. Today identity is spread across names, profiles, task logs, and substrate attribution.

Risk: checkpointing a graph does not create a self-owned identity.

## Agno

Evidence: `_cache/agno_storage.html`.

Agno's surveyed docs emphasize session/storage and memory primitives. The useful pattern is ordinary but important: storage is not an afterthought; sessions are first-class records, and memory/search sits behind the agent API.

Pattern to port: make durable storage explicit in constructors and configs for dharma_swarm participants. Avoid hidden writes to many unrelated `~/.dharma` subdirectories unless they are indexed in a participant manifest.

## AutoGPT / SuperAGI / BabyAGI legacy

Evidence: `_cache/autogpt_README.md`, `_cache/superagi_README.md`, `_cache/babyagi_README.md`.

The 2023-2024 wave left three surviving patterns:

- Task queue loops are easy to build and easy to over-trust.
- Tool/plugin marketplaces matter only if capability installation is policy-bound.
- A visible agent UI is not evidence of operator-distance.

Pattern to port: keep task queues subordinate to identity and memory. A task loop without a durable participant identity should not be counted as a SAB agent.

## Extractable patterns

| Pattern | Source systems | Port priority |
|---|---|---|
| Thread/checkpoint identity | LangGraph, AutoGen | High |
| Unified scored memory API | CrewAI, Letta, Hermes Agent | High |
| Serializable agent state | AutoGen, LangGraph | High |
| Explicit storage/session constructors | Agno, LangGraph | Medium |
| Skill/plugin registry with policy | OpenClaw, ElizaOS, Hermes Agent | High |
| Human-in-the-loop state inspection | LangGraph, Codex, AutoGen | Medium |

The framework lane reinforces the same finding as the inward audit: dharma_swarm has many persistence stores, but not yet one explicit participant-state contract.
