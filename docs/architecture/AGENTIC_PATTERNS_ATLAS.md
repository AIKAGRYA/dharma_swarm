# Agentic Design Patterns Atlas

**Status:** SEEDED (inaugural, 2026-07-01)
**Slot:** MEGAFILE Slot 4 (Limbs Atlas) substrate reference — the "which limb
implements which named agentic pattern" lens. Linked from
[`LIMBS_ATLAS.md`](LIMBS_ATLAS.md).
**Source frame:** Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to
Building Intelligent Systems* (21 chapters + 7 appendices). This atlas maps the
book's 21 patterns onto the dharma_swarm substrate (~770 modules).
**Provenance:** claude-code deep-read + full repo coverage audit, 2026-07-01.
Companion to the DRAFT track
[`proposed_tracks/agentic-design-patterns-cognition-2026-07.yaml`](../governance/proposed_tracks/agentic-design-patterns-cognition-2026-07.yaml).

> **Doc decays — check before citing (Axiom A6).** Verdicts below were current at
> the audit date. Before treating any row as settled fact, confirm the cited
> path against the code (`make xray`, GitNexus, or a direct read). A verdict is a
> pointer, not a guarantee.

---

## Why this atlas exists

The book is a comprehensive catalogue of the patterns that make an "AI system" an
*agent*. Mapping it against the repo answers one question precisely: **for each
named pattern, does the substrate already implement it, and how well?** The
answer sharpens where new work has leverage and — just as important — where it
would be redundant.

**The headline finding:** dharma_swarm is **STRONG at the multi-agent /
infrastructure layer** (how the swarm coordinates) and **PARTIAL at the
intra-agent cognition layer** (how a single agent reasons before the swarm
coordinates it). That asymmetry is the map's main signal.

Per the Transcendence Principle (`CLAUDE.md`), the swarm's aggregation math only
pays off when each agent is genuinely competent (condition 1, *diversity of
competence*). The PARTIAL cluster below is exactly that per-agent competence.

---

## The 21-pattern coverage map

Coverage legend: **STRONG** = mature + tested; **PARTIAL** = exists but
incomplete/implicit/scattered; **OUT-OF-SCOPE** = intentionally not built here
(owned elsewhere or excluded by doctrine).

| # | Pattern (book chapter) | Coverage | Key modules | Notes |
|---|---|---|---|---|
| 1 | Prompt Chaining | PARTIAL | `prompt_builder.py`, `autonomous_agent.py` (ReAct loop), `cascade.py` | Chaining is implicit in the ReAct message accumulator; no first-class composable pipeline unit. |
| 2 | Routing | **STRONG** | `orchestrator.py`, `provider_policy.py`, `router_v1.py`, `spine/routing.py` | Policy-driven dispatch + provider selection + topology-aware assignment. |
| 3 | Parallelization | **STRONG** | `orchestrator.py` (fan-out/fan-in), `workflow_graph.py` (DAG), `workflow.py`, `yoga_node.py` | Async orchestration with concurrent exec + topological ordering. |
| 4 | Reflection | PARTIAL | `telos_gates.py` (`check_with_reflective_reroute` — a real critique→revise→recheck loop, up to `max_reroutes`), `reflexion.py` (verbal-RL self-correction, Shinn et al.), `neural_consolidator.py` (advocate/critic), `verify/` | STRONGER than a first pass suggests: a genuine self-correction loop exists in the gate layer + `reflexion.py`. Gap is that it is **not a first-class composable agent organ** (no `cognition/reflection.py`), bounded to witness-recovery on mandatory think phases. |
| 5 | Tool Use | **STRONG** | `tool_registry.py`, `autonomous_agent.py`, `agent_runner.py` (tool-call parsing), `langgraph_parity/tools.py` | Full ReAct-style tool calling: schema collection, dispatch, result integration. |
| 6 | Planning | PARTIAL | `auto_research/planner.py`, `cascade.py`, `coordination/genome.py` (Subtask) | Decomposition is domain-specific (research) or manual/heuristic; no general goal→subtree planner. |
| 7 | Multi-Agent | **STRONG** | `a2a/`, `council/council.py`, `coordination/`, `swarm.py` | A2A protocol + council verification + topologies. |
| 8 | Memory Management | **STRONG** | `agent_memory_manager.py` (tiered), `agent_memory.py`, `memory_kernel/` | Scoped memory, SQLite persistence, TTL expiry, token-budgeted context. |
| 9 | Learning & Adaptation | OUT-OF-SCOPE (this track) | `trajectory_collector.py` → `strategy_reinforcer.py` → `training_flywheel.py` (behavioral-RL flywheel), `archive.py`, `diversity_archive.py` (MAP-Elites), `sleep_time_agent.py` | Correction: a real **behavioral** adaptation loop exists (trajectory→score→UCB strategy selection→prompt injection). It is zero **trained-weight** by design — parametric RL (RLVR/GRPO) belongs to `orchestration-arena-v1-2026-06`, not this cognition track. |
| 10 | Model Context Protocol (MCP) | PARTIAL | `mcp_server.py` (`create_mcp_server`, exposes swarm tools), `dharma_context_mcp.py`, `chetana/mcp_server.py` | Correction: MCP servers DO exist and expose tools (not merely "named"). Gap is dynamic tool discovery / capability negotiation (tools are hard-coded in `list_tools`) and MCP-as-routing-signal. Not this cognition track's scope. |
| 11 | Goal Setting & Monitoring | PARTIAL | `operator_core/operating_facts.py`, `operator_core/runtime_truth.py`, `world_radar/`, `telos_substrate.py` | Goal state exists; monitoring is observational, no explicit progress-closure tracking. |
| 12 | Exception Handling & Recovery | **STRONG** | `resilience.py` (RetryPolicy, CircuitBreaker, `run_with_retry`), `agent_runner.py` (error classification), `agent_runner_quality.py` | Retry + backoff/jitter + circuit breaker + provider fallback chains. |
| 13 | Human-in-the-Loop | **STRONG** | `telos_gates.py`, `verify/`, `operator_core/`, `pr_merge_control.py` | Approval gates, reviewer lanes, escalation via governance. |
| 14 | Knowledge Retrieval (RAG) | **STRONG** | `vector_store.py` (TF-IDF + sqlite-vec + FTS5 hybrid), `knowledge_ops/`, `memory_kernel/context_admission.py` | Bi-temporal vector store, semantic + FTS fusion, retrieval ranking, confidence decay. |
| 15 | Inter-Agent Communication (A2A) | **STRONG** | `a2a/` (A2AServer, A2AMessage, A2ABridge), `a2a/node_gateway.py`, `a2a/agent_card.py`, `spine/receipt.py` | Task lifecycle, agent discovery via cards, NATS-ready transport, evidence receipts. |
| 16 | Resource-Aware Optimization | **STRONG** | `cost_tracker.py`, `provider_policy.py`, `coordination/genome.py`, `yoga_node.py` | Token/latency budgets, cost tracking, model-aware selection, per-role compute envelopes. |
| 17 | Reasoning Techniques | PARTIAL | `autonomous_agent.py` (ReAct), `reflexion.py` (verbal RL), `thinkodynamic_director.py` | Confirmed PARTIAL: grep finds **no** CoT / ToT / self-consistency orchestration anywhere; reasoning is model-delegated via the ReAct accumulator. `reflexion.py` adds retry-with-reflection but not multi-path sampling+voting. This is the single highest-leverage cognition gap. |
| 18 | Guardrails / Safety | **STRONG** | `telos_gates.py` (11 gates + variety expansion), `anekanta_gate.py`, `prompt_builder.py` (injection sanitization), `telos_payload_classifier.py` | Pattern-based blocking, input validation, payload classification, witness audit. |
| 19 | Evaluation & Monitoring | **STRONG** | `verify/scorer.py`, `verify/reviewer.py`, `langgraph_parity/benchmark_runner.py`, `operator_core/runtime_truth.py`, `jikoku_instrumentation.py` | Deterministic scoring, benchmark evals, spine-receipt observability, telemetry plane. |
| 20 | Prioritization | PARTIAL | `models.py` (TaskPriority), `agent_runner.py` (PRIORITY_SALIENCE), `knowledge_ops/memory_promotion_queue.py`, `cron_scheduler.py` | Priority affects salience weighting; no queue-based scheduling per se. |
| 21 | Exploration and Discovery | **STRONG** | `diversity_archive.py` (MAP-Elites), `archive.py`, `coordination/orchestrator_v1.py`, `ucb_selector.py` | Quality-diversity archive, behavioral descriptors, novelty search, bandit selection. |

**Tally:** 13 STRONG · 7 PARTIAL · 1 OUT-OF-SCOPE (this cognition track).

> **Deeper-audit correction (2026-07-01).** A first-pass map understated four
> patterns. A follow-up capability inventory found `reflexion.py`,
> `neural_consolidator.py`, `sleep_time_agent.py`, a real behavioral-RL flywheel
> (`trajectory_collector`→`strategy_reinforcer`→`training_flywheel`), and live
> MCP servers (`mcp_server.py`). Rows 4, 9, 10, 17 were corrected above. Net:
> the substrate is richer than the book's flat pattern list implies — roughly
> 60-65% of the 2025-2026 bleeding edge — with the genuine gaps concentrated in
> explicit multi-path reasoning (CoT/ToT/self-consistency) and first-class
> composable cognition organs. See the frontier roadmap in
> `reports/audit/AGENTIC_FRONTIER_AUDIT_2026-07-01.md`.

---

## Out-of-scope for THIS cognition track (owned elsewhere)

- **Pattern 9 — Learning & Adaptation.** A **behavioral** adaptation loop already
  exists (`trajectory_collector`→`strategy_reinforcer`→`training_flywheel`:
  score trajectories, UCB-select strategies, inject prompt fragments). What is
  deliberately out of scope is **parametric/trained-weight** learning (RLVR,
  GRPO, SFT) — that is `orchestration-arena-v1-2026-06`'s domain ("Do not
  introduce trained weights in v1"). Building learned weights in the cognition
  track would violate that track's non-goals.
- **Pattern 10 — MCP.** MCP servers exist (`mcp_server.py`,
  `dharma_context_mcp.py`, `chetana/mcp_server.py`) and expose tools, so this is
  PARTIAL, not absent. Deepening it (dynamic tool discovery, capability
  negotiation, MCP-as-routing) is an integration/transport concern that belongs
  with the A2A/NATS lanes, not the cognition track.

---

## The PARTIAL cluster = the implementation target

Six PARTIAL patterns form a single coherent surface — **the intra-agent
reasoning loop**: Prompt Chaining (1), Reflection (4), Planning (6), Goal
Setting & Monitoring (11), Reasoning Techniques (17), Prioritization (20). They
exist today only *implicitly*, emergent from the ReAct loop + cascade domains,
never as first-class, composable, tested organs.

The DRAFT track
[`agentic-design-patterns-cognition-2026-07`](../governance/proposed_tracks/agentic-design-patterns-cognition-2026-07.yaml)
proposes making the highest-leverage four first-class in a new, surface-disjoint
`dharma_swarm/cognition/` package (Reflection, Reasoning, Planning, Chain), each
spine-routed via `invoke_agent()`, tested, and benchmarked under budget parity
before any capability claim. Goal-Monitoring and Prioritization are lower-leverage
(they lean toward the scheduling/governance surfaces already owned elsewhere) and
are deferred.

---

## Appendices (book) → repo

The book's 7 appendices are reference material, largely already covered:
Advanced Prompting (`prompt_builder.py`), Agentic Frameworks overview
(`langgraph_parity/` benchmarks LangGraph-style runtimes), CLI agents
(`claude_cli.py`, `codex_cli.py`, `dgc_cli.py`), Coding agents (`build_engine.py`,
`agent_runner.py`, the whole swarm), and Reasoning Engine internals (the
Pattern-17 gap above). No appendix motivates net-new scope beyond the cognition
cluster.

---

## Keeping this atlas fresh

This atlas is a candidate recurring-ingestion target: the same external
agentic-engineering literature that produced it (design-pattern catalogues,
framework docs, agent-research papers) can be pulled on a cadence through the
`world_radar` ingestion pipeline so this map is refreshed as the field moves
rather than frozen at one read. See the ingestion wiring registered alongside
this track.
