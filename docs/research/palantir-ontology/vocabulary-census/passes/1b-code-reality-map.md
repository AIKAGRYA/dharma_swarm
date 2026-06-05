# Pass 1b — Code-Reality Map

**Produced by:** Pass 1b agent (code-walker)
**Date:** 2026-06-02
**Charter ref:** `00-swarm-charter.md`
**Posture:** Inhabit first, name second. No type proposals. Evidence only.

---

## 1. Files Walked

**Core runtime — dharma_swarm/**

| File | One-line purpose |
|---|---|
| `models.py` | The canonical schema contract: all shared enums and BaseModel types every module imports from. |
| `orchestrator.py` | Async task dispatcher — connects TaskBoard to AgentPool via fan-out/fan-in topology patterns. |
| `swarm.py` | SwarmManager — the lifecycle manager that integrates agent pool, task board, message bus, and orchestrator into one runnable surface. |
| `agent_runner.py` | The actual LLM turn-execution engine (~3,200 lines); AgentRunner runs one agent's full conversation loop; AgentPool manages a fleet. |
| `evolution.py` | DarwinEngine — the self-improvement loop: propose mutations, gate-check, write code, test, score fitness, archive, select parents. |
| `organism.py` | Organism + OrganismRuntime — the integration surface wiring VSM, AMIROS, memory, routing, and heartbeat lifecycle. |
| `providers.py` | Async LLM provider abstraction for 15+ backends (Anthropic, OpenAI, OpenRouter, Ollama, Groq, Cerebras, etc.). |
| `thinkodynamic_director.py` | Autonomous 3-altitude thinking system: SUMMIT (vision) → STRATOSPHERE (sense) → GROUND (delegate/execute) → ascend. |
| `startup_crew.py` | Defines the default agent roster: cartographer, surgeon, architect, validator + the cyber-* frontier agents (glm5, kimi25, codex/qwen3-coder, opus). |
| `context.py` | 5-layer context engine (Vision/Research/Engineer/Ops/Swarm) assembled for each agent turn; U-shaped placement logic. |
| `telic_seam.py` | Write-through seam between orchestrator/agent_runner and ontology: records ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution. |
| `pulse.py` | DGC Pulse daemon — the autonomous heartbeat: gather context → telos-gate → run Claude Code headless → subconscious + shakti living-layer wiring. |
| `models.py` | Already noted above. |
| `guardian_crew.py` | Three-agent background crew (AUDITOR/LOOP_WATCHER/ROUTER_PROBE) running on 4h cycle, checking interface contracts, loop health, router availability. |
| `autonomous_agent.py` | AutonomousAgent — higher-level agent wrapper with tool execution, AgentOrchestrator for multi-agent coordination. |
| `telos_gates.py` | 5 named dharmic safety gates: AHIMSA (Tier A), SATYA (Tier B), REVERSIBILITY/SVABHAAVA/WITNESS (Tier C). Variety expansion protocol lets new gates be proposed and approved. |
| `cron_runner.py` | Cron job runtime — reads `cron_jobs.json`, resolves schedule, telos-gates each job, runs via Claude Code headless. |
| `context_compiler.py` | ContextCompiler — assembles agent system prompts from modular sections. |
| `dgc_cli.py` | Primary CLI surface (`dgc` command) — the human-facing operator entry point for swarm control. |
| `ontology.py` | The ontology engine: ObjectType/OntologyObj/Link/ActionDef schema + OntologyRegistry (in-memory + SQLite backed). ~2,000 lines. |
| `signal_bus.py` | In-process SignalBus — the shared downbeat for loop-to-loop signaling (distinct from agent-to-agent message bus). |
| `runtime_contract.py` | RuntimeEnvelope — the canonical control-plane event shape (state.snapshot / memory.event / action.event / audit.event). |
| `vsm_channels.py` | VSM S1–S5 coordination: AlgedonicChannel, GatePatternAggregator, AgentViabilityMonitor, VSMCoordinator. |
| `stigmergy.py` | StigmergicMark + StigmergyStore — the pheromone-trail lattice agents leave observations on. |
| `shakti.py` | ShaktiLoop — perception engine that scans stigmergy marks, classifies by ShaktiEnergy (Maheshwari/Mahakali/Mahalakshmi/Mahasaraswati). |
| `shakti_executive/` | ShaktiExecutive — populates `opportunity_board.json` with scored OpportunityCandidate entries. |
| `witness.py` | WitnessAuditor — retrospective integrity checker for telos gate decisions. |
| `board/models.py` | Card + ClaimLease + AcceptanceCriterion + AuditEntry — the kanban-style work unit on the BoardStoreFacade. |
| `board/facade.py` | BoardStoreFacade — atomic claim/transition surface with CostCeilingExceededError, VersionConflictError guards. |
| `spine/receipt.py` | EvidenceReceipt — frozen dataclass: the one canonical artifact every dispatch attempt produces (OTel-exportable). |
| `spine/routing.py` | RoutingDecision — one canonical value object for every routing choice (consolidating 7 implicit routers). |
| `spine/invoke.py` | invoke_agent — the blessed invocation path; AgentInvoker protocol. |
| `a2a/agent_card.py` | AgentCard + AgentSkill + CardRegistry — A2A 1.0 spec implementation for agent capability advertisement. |
| `a2a/a2a_server.py` | A2AServer — HTTP server for agent-to-agent task delegation; A2ATask/A2AMessage/A2AArtifact shapes. |
| `a2a/a2a_client.py` | A2AClient + DelegationResult — client side of A2A task delegation. |
| `a2a/node_registry.py` | NodeRegistry + RemoteNode — discovery layer for remote A2A nodes. |
| `mission_contract.py` | MissionState + CampaignArtifact + ExecutionBrief + CompletionContract — the structured representation of a mission in flight. |
| `archive.py` | FitnessScore + ArchiveEntry + MAPElitesGrid + EvolutionArchive — evolutionary archive backend. |
| `economic_spine.py` | MissionState (enum), AgentBudget, MissionRecord, EconomicSpine — token-budget accounting per mission. |
| `shakti_executive/models.py` | OpportunityCandidate — the scored row on the opportunity board. |

**API layer — api/**

| File | One-line purpose |
|---|---|
| `api/main.py` | FastAPI app bootstrap — registers all routers, CORS, startup hooks. |
| `api/models.py` | API-layer request/response shapes (distinct from dharma_swarm/models.py). |
| `api/routers/agents.py` | Agent CRUD + spawn + chat endpoints. |
| `api/routers/chat.py` | Chat session management — longest router file (~48k). |
| `api/routers/ontology.py` | REST API over OntologyRegistry. |
| `api/routers/evolution.py` | Evolution cycle trigger and status. |
| `api/routers/stigmergy.py` | Stigmergy lattice read/write API. |
| `api/routers/telemetry.py` | OTel-compatible telemetry surface. |
| `api/routers/_agent_aliases.py` | AGENT_ALIASES dict normalizing model-specific slug names to canonical handles. |
| `api/module_truth.py` | Static module truth table (~49k bytes) — the ground truth about what the system believes it has. |

**Test suite — tests/**

~300+ test files. Key naming signals: `test_telic_seam`, `test_organism_lifecycle`, `test_evolution`, `test_shakti`, `test_stigmergy`, `test_board_facade`, `test_a2a`, `test_guardian_crew`, `test_authority_revenue_loop`, `test_ginko_*` (financial agent suite), `test_jikoku_*` (timing/performance), `test_br_closures` (behavior-requirement closures).

---

## 2. First-Class Objects in Code

### 2a. Orchestration and Runtime

**`models.py`**

- `Task` — unit of work: id, title, description, status (PENDING/ASSIGNED/RUNNING/COMPLETED/FAILED/CANCELLED), priority, assigned_to, depends_on, blocked_by, result, metadata.
- `AgentConfig` — canonical agent identity/configuration (marked "CANONICAL" in a docstring): id, name, role, provider, model, system_prompt, max_turns, tools, autonomy, temperature, context_budget, wake_interval. Has a `@model_validator` coercing legacy bare strings. References `AGENT_IDENTITY_UNIFICATION.md`.
- `AgentState` — runtime state of a running agent: id, name, role, status, current_task, turns_used, tasks_completed, provider, model, error.
- `SwarmState` — snapshot of the whole fleet: list of AgentState, task counters (pending/running/completed/failed), uptime, organism dict.
- `TaskDispatch` — assignment message from orchestrator to agent: task_id, agent_id, topology, timeout_seconds.
- `Message` — agent-to-agent message: from_agent, to_agent, subject, body, priority, status (UNREAD/READ/ARCHIVED).
- `LLMRequest` / `LLMResponse` — wrapper around a single provider invocation.
- `SandboxResult` — code execution outcome: exit_code, stdout, stderr, duration_seconds, timed_out.

**`orchestrator.py`**

- `Orchestrator` — the main dispatch loop. Internally tracks: task_board, agent_pool, message_bus, telic_seam. Implements gate-check-before-dispatch pattern.
- `TaskBoard` (Protocol) — duck-typed: get_ready_tasks / update_task / get.
- `AgentPool` (Protocol) — duck-typed: get_idle_agents / assign / release / get_result / get.

**`agent_runner.py`**

- `AgentRunner` — runs a single agent's LLM conversation loop; manages tool calls, sandbox execution, memory writes, routing decisions.
- `AgentPool` — manages a fleet of AgentRunners.
- `CompletionProvider` (Protocol) — what an LLM backend must expose.
- `RoutedCompletionProvider` (Protocol) — provider that knows routing context.
- `CodeSandbox` (Protocol) — what code execution requires.
- `CompletionAssessment` (`agent_runner_quality.py`) — quality verdict on a completion.

**`runtime_contract.py`**

- `RuntimeEnvelope` — frozen dataclass; canonical control-plane event shape: contract_version, event_id, event_type (state.snapshot / memory.event / action.event / audit.event), emitted_at, source, agent_id, session_id, trace_id, payload, checksum.
- `RuntimeEventType` — enum of 4 control-plane event types.

### 2b. Agents and Identity

**`models.py` (enums)**

- `AgentRole` — CODER, REVIEWER, RESEARCHER, TESTER, ORCHESTRATOR, GENERAL, CARTOGRAPHER, ARCHEOLOGIST, SURGEON, ARCHITECT, VALIDATOR, CONDUCTOR (PSMV cognitive roles), OPERATOR, ARCHIVIST, RESEARCH_DIRECTOR, SYSTEMS_ARCHITECT, STRATEGIST, WITNESS (constitutional topology), WORKER (ephemeral). Comments note "5-role agent briefings" and "6-agent stable roster."
- `AgentStatus` — IDLE → BUSY → STARTING → STOPPING → DEAD.
- `ProviderType` — ANTHROPIC, OPENAI, OPENROUTER, NVIDIA_NIM, LOCAL, CLAUDE_CODE, CODEX, OPENROUTER_FREE, OLLAMA, GROQ, CEREBRAS, SILICONFLOW, TOGETHER, FIREWORKS, GOOGLE_AI, SAMBANOVA, MISTRAL, CHUTES.
- `AutonomyLevel` — LOCKED → CAUTIOUS → BALANCED → AGGRESSIVE → FULL.
- `MemoryLayer` — IMMEDIATE, SESSION, DEVELOPMENT, WITNESS, META.

**`agent_registry.py`**

- `AgentIdentity` — runtime registry entry for a known agent.
- `AgentRegistry` — in-memory catalog of active agents.

**`autonomous_agent.py`**

- `AutonomousAgent` — wraps AgentRunner with higher-level execution patterns.
- `AgentResult` — structured result from one agent execution.
- `AgentIdentity` (second definition) — note: same name as in `agent_registry.py`; two independent definitions of agent identity exist.
- `AgentOrchestrator` — multi-agent coordination wrapper.

**`agent_constitution.py`**

- `AgentSpec` — specification for an agent instance (used in DynamicRoster).
- `DynamicRoster` — manages the "6-agent constitutional stable roster": operator, archivist, research_director, systems_architect, strategist, witness.
- `ConstitutionalLayer` — enum for the layer in which a spec lives.

**`a2a/agent_card.py`**

- `AgentCard` — A2A 1.0 spec agent card: id, name, url, version, description, capabilities, skills (list of AgentSkill), securitySchemes, supportedInterfaces, extensions. JWS signature support declared but not enforced at runtime.
- `AgentSkill` — advertised capability: id, name, tags, examples, inputModes, outputModes.
- `SecurityScheme` — auth mechanism declaration: APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect. Only APIKey enforced today.
- `CardRegistry` — stores and queries agent cards from `~/.dharma/a2a/cards/`.

**`a2a/node_registry.py`**

- `RemoteNode` — a discovered remote A2A peer: url, api_key, capabilities.
- `NodeRegistry` — discovery catalog of remote nodes.

### 2c. Telos and Gates

**`models.py` (enums)**

- `GateTier` — A (absolute block), B (strong block), C (advisory).
- `GateResult` — PASS / FAIL / WARN.
- `GateDecision` — ALLOW / BLOCK / REVIEW.

**`models.py` (models)**

- `GateCheckResult` — result of running the full gate suite: decision, reason, gate (which gate fired), gate_results (per-gate verdicts), timestamp.

**`telos_gates.py`**

- `GateProposal` — proposed custom gate for the variety expansion protocol: name, tier, justification, trigger_patterns, status (proposed/approved/rejected).
- `GateRegistry` — lifecycle manager for the gate variety expansion (propose → approve/reject → load_approved).
- The 5 active gates (as constants): AHIMSA (Tier A: harm + injection), SATYA (Tier B: deception + credential leak), REVERSIBILITY (Tier C: irreversible operation warning), SVABHAAVA (Tier C: telos alignment via Anekanta epistemological diversity), WITNESS (Tier C: mandatory think-point logging).

### 2d. The Metabolic Loop (TelicSeam + Ontology objects)

**`telic_seam.py`**

The seam documents its own loop as a docstring:
> need appears in ontology → action proposed → gates evaluate → orchestrator claims lease → agent executes → outcome recorded → value measured → fitness updated → routing changes → projections refresh

TelicSeam writes these ontology objects in sequence:

- **ActionProposal** — the metabolic loop entry point. Status lifecycle: proposed → gated → approved / rejected → executing → completed / failed.
- **GateDecisionRecord** — records the output of the gate suite for a given proposal. Links to ActionProposal via `has_gate_decision`.
- **ExecutionLease** — the active claim on execution: claim_id, agent_id, claimed_at, claim_timeout_seconds, dispatch_attempt. Links via `has_execution_lease`.
- **Outcome** — what the agent produced: success bool, result_summary, error, duration_ms, fitness_score. Links via `has_outcome`.
- **ValueEvent** — measures the value an Outcome produced: behavioral_signal, success_value, duration_efficiency, composite_value (0.4×behavioral + 0.4×success + 0.2×efficiency), scoring_method. Links via `has_value_event`.
- **Contribution** — assigns credit to an agent from a ValueEvent: credit_share, attributed_value, cell_id, task_type. Links via `has_contribution`.

Agent fitness is queried by Bayesian smoothing over Contribution records (prior weight 5 at 0.5).

### 2e. Ontology Schema (from `ontology.py` — the core types)

These are registered at boot in OntologyRegistry:

| Type | What it is |
|---|---|
| `ResearchThread` | A named research focus with domain, hypothesis, priority, status (active/paused/archived). |
| `Experiment` | A tracked experiment: name, config, status, model, prompt_set, results, fitness, r_v_value. |
| `Paper` | A research paper being written: title, venue, deadline, status, latex_path, claim_count. |
| `AgentIdentity` | An ontology-level agent record: name, agent_id, role, status, provider, model, swabhaav_capacity, fitness_average. |
| `CustodianRole` | A custodian agent specification: name, tier, model, status, total_runs, success_rate, files_healed. |
| `KnowledgeArtifact` | A stored knowledge unit: title, artifact_type, domain, content, file_path, confidence, verified. |
| `TypedTask` | Ontology-typed version of a Task: type, description, status, assigned_to, priority. Links: assigned_to → AgentIdentity, consumes/produces → KnowledgeArtifact. |
| `ActionProposal` | (See §2d above.) |
| `GateDecisionRecord` | (See §2d above.) |
| `ExecutionLease` | (See §2d above.) |
| `Outcome` | (See §2d above.) |
| `ValueEvent` | (See §2d above.) |
| `Contribution` | (See §2d above.) |
| `VentureCell` | "Fractal project container — first-class ontology object with its own agents, budgets, KPIs." Status: incubating → active → mature → divesting → archived. autonomy_stage 1–5. |

The meta-schema itself:
- `ObjectType` — schema for a class of entity: properties, links, actions, security, telos_alignment, shakti_energy, witness_quality.
- `OntologyObj` — a typed instance: id, type_name, properties, created_at, version.
- `Link` — a typed relationship: link_name, source_id, source_type, target_id, target_type, witness_quality.
- `ActionExecution` — audit record of an action being executed.
- `PropertyDef` / `LinkDef` / `ActionDef` / `SecurityPolicy` — the meta-level schema definitions.

`ShaktiEnergy` enum on ObjectType: MAHESHWARI / MAHAKALI / MAHALAKSHMI / MAHASARASWATI — every type is tagged with which creative force primarily drives it.

### 2f. Evolution

**`evolution.py`**

- `Proposal` — a proposed code change to the Darwin Engine: component, change_type (mutation/crossover/ablation), description, parent_id, diff, status (EvolutionStatus), predicted_fitness, actual_fitness (FitnessScore), gate_decision, reflection_attempts, evidence_tier, promotion_state.
- `EvolutionStatus` — PENDING → REFLECTING → GATED → WRITING → TESTING → EVALUATED → ARCHIVED / REJECTED.
- `CycleResult` — summary of one evolution cycle: proposals_submitted/gated/tested/archived, circuit_breakers_tripped, strategy_pivots, best_fitness, exploration_ratio, convergence_restart_triggered.
- `SealedPacketApplyResult` — outcome of ingesting a Build Protocol packet.

**`archive.py`**

- `FitnessScore` — multi-dimensional score: correctness, dharmic_alignment, swabhaav_alignment, performance (JIKOKU), utilization (JIKOKU), economic_value, elegance, efficiency, safety. Has `weighted()` method.
- `ArchiveEntry` — one evolution attempt in the archive: id, timestamp, parent_id, fitness, proposal_text, diff, test_results, notes.
- `MAPElitesGrid` — quality-diversity archive: cells indexed by behavior descriptors.
- `EvolutionArchive` — manages the archive storage backend.

**`execution_profile.py`** (imported by evolution.py)

- `EvidenceTier` — UNVALIDATED → STAGING → PRODUCTION.
- `PromotionState` — CANDIDATE → PROMOTED → RETIRED.

### 2g. Memory and Context

**`models.py`**

- `MemoryEntry` — entry in the "strange loop memory system": layer (IMMEDIATE/SESSION/DEVELOPMENT/WITNESS/META), content, source, tags, development_marker, witness_quality.

**`context.py`**

- `ContextBlock` — a positioned chunk of context for U-shaped assembly: name, position (lower = higher attention zone), content, char_count.

**`agent_memory.py`**

- `AgentMemoryEntry` — persistent memory entry for one agent.
- `AgentMemoryBank` — per-agent memory store.

**`agent_memory_manager.py`**

- `Memory` — a memory record with scope.
- `Scope` — enum for memory scope (SESSION/GLOBAL/...).
- `AgentMemoryManager` — manages memories across agents and scopes.

### 2h. Organism and VSM

**`organism.py`**

- `OrganismPulse` — single heartbeat of the legacy integration layer: fleet_health, zeitgeist_signals, anomalous_gate_patterns, algedonic_active, amiros_experiments_running, identity_coherence, concept_stats.
- `Organism` — legacy integration wiring VSM + AMIROS + memory + routing.
- `OrganismRuntime` — newer heartbeat runtime focused on Gnani/Samvara hold-processing.
- `HeartbeatResult` — result of one OrganismRuntime heartbeat cycle.

**`vsm_channels.py`**

- `AlgedonicSignal` — pain/pleasure signal from VSM: severity, description, source, timestamp.
- `GatePattern` — anomalous gate pattern observed by VSM S4.
- `AgentViability` — agent health assessment: health_score, is_viable, reason.
- `GateExpansionProposal` — proposed gate expansion from VarietyExpansionProtocol.
- `VSMCoordinator` — wires S1–S5 VSM channels together.

### 2i. Stigmergy and Shakti

**`stigmergy.py`**

- `StigmergicMark` — pheromone mark left on the lattice: agent, file_path, action, observation (≤200 chars), salience (0–1), connections (list), access_count, channel (general/cascade/strategy/dashboard/test), trace_id.
- `StigmergyStore` — file-backed JSONL store with decay; density computed from mark count.

**`shakti.py`**

- `ShaktiEnergy` (enum) — MAHESHWARI (structure/governance), MAHAKALI (destruction/transformation), MAHALAKSHMI (abundance/resources), MAHASARASWATI (precision/knowledge).
- `ShaktiPerception` — one classified observation: observation text, connection (to file/concept), energy (ShaktiEnergy), proposal (optional), impact_level (local/module/system), salience.
- `ShaktiLoop` — perception engine: scans stigmergy marks, classifies by keyword, emits ShaktiPerception list.

**`shakti_executive/`**

- `OpportunityCandidate` — scored opportunity entry for `opportunity_board.json`: opportunity_id, title, domain, thesis, factor_scores, final_score, evidence_signals, why_now, source_inputs.
- `ShaktiExecutive` — populates the opportunity_board from input signals.

### 2j. Board and Work Units

**`board/models.py`**

- `Card` — the stable unit of work on the BoardStoreFacade: id (CardId), parent_objective (ObjectiveId), title, body, status (CardStatus), claim_lease (ClaimLease | None), assignee_kind, capability_required, acceptance_criteria (list[AcceptanceCriterion]), receipt_refs, cost_ceiling_usd, audit_log, version, arjuna_weight, source_surface.
- `ClaimLease` — concurrency lock: lease_id, card_id, agent_id, agent_kind, claimed_at, expires_at, cost_burn_usd, capability_manifest.
- `AcceptanceCriterion` — completion gate: text, kind (test/doc/artifact/manual/external/receipt), required, verifier.
- `ReceiptRef` — pointer to durable receipt in any store: receipt_id, kind, store (runtime_state/event_log/roaming_mailbox/artifact_store/external).
- `AuditEntry` — event in card's audit log: actor_id, actor_kind (operator/agent/noticer/facade/admin), action, at, idempotency_key.
- `RenderHints` — display guidance for surfaces (kanban, table, Telegram, etc.).

`CardStatus` Literal: "pending" → "doing" → "done" (with "blocked", "cancelled").

### 2k. Spine (Canonical Dispatch Surface)

**`spine/receipt.py`**

- `EvidenceReceipt` — frozen dataclass, the canonical artifact of every dispatch: receipt_id, trace_id, span_id, parent_span_id, context_id, task_id, claim_id, agent_id, agent_card_version, provider, model, operation, status (ok/failed/dropped/timeout/cancelled), error_source (15 possible values), started_at, finished_at, latency_ms, input_tokens, output_tokens, cost_usd, routing_decision_id, attributes.
- `ErrorSource` — 14-value Literal type enumerating every way dispatch can fail.
- Exports to OTel span via `to_otel_span()`.

**`spine/routing.py`**

- `RoutingDecision` — frozen dataclass: decision_id, agent_id, provider, model, reason, scores, fallback_plan, router_name, context_id, task_id.

**`spine/invoke.py`**

- `AgentInvoker` (Protocol) — the blessed invocation signature.
- `invoke_agent()` — the one canonical invocation function.

### 2l. A2A Protocol

**`a2a/a2a_server.py`**

- `A2ATask` — a task received from a remote agent: id, agent_id, input_data, status (A2ATaskStatus), messages, artifacts.
- `A2AMessage` — message in a task thread: role, parts (list[A2APart]).
- `A2APart` — typed content part: type (A2APartType: text/data/file/tool_call/tool_result), content.
- `A2AArtifact` — produced artifact: artifact_id, content_type, data, description.
- `A2AExtension` — dharma-specific extension fields attached to tasks.
- `A2ATaskStatus` — SUBMITTED → WORKING → COMPLETED / FAILED.
- `A2AServer` — HTTP server handling incoming A2A task delegation.

**`a2a/a2a_client.py`**

- `A2AClient` — sends tasks to remote A2A servers.
- `DelegationResult` — result of delegating a task externally.

### 2m. Mission and Campaign

**`mission_contract.py`**

- `MissionState` — the structured state of a mission in flight: objective, constraints, success_criteria, current_phase, history.
- `CampaignArtifact` — the serialized campaign with its state.
- `ExecutionBrief` — brief given to agents before they execute: objective, context, constraints, acceptance_criteria.
- `CompletionContract` — formal contract for what "done" means.
- `DefensePacket` / `JudgeGate` / `JudgePack` / `HonorsCheckpoint` — review chain for quality assurance.
- `CampaignState` — the broader campaign's state (multiple missions).
- `SemanticBrief` — semantically enriched brief.

**`economic_spine.py`**

- `MissionState` (enum — different class from above): PLANNING / ACTIVE / PAUSED / COMPLETED / FAILED / ARCHIVED.
- `AgentBudget` — token budget allocation per agent.
- `MissionRecord` — economic record of a mission: missions completed, tokens spent, cost.
- `EconomicSpine` — budget accounting engine.

### 2n. Signal Bus

**`signal_bus.py`**

Named signal constants (loop-to-loop):
- `SIGNAL_AGENT_FITNESS`, `SIGNAL_WORKER_FITNESS`
- `SIGNAL_ANOMALY_DETECTED`
- `SIGNAL_CASCADE_EIGENFORM_DISTANCE`
- `SIGNAL_RECOGNITION_UPDATED`
- `SIGNAL_AGENT_REPLICATED`, `SIGNAL_AGENT_APOPTOSIS`, `SIGNAL_REPLICATION_PROPOSAL`
- `SIGNAL_DIVERSITY_HEALTH`, `SIGNAL_TRANSCENDENCE_MARGIN`
- `SIGNAL_ECC_INSTINCT`
- `SIGNAL_LIFECYCLE_COMPLETED`
- `SIGNAL_OUTCOME_RECORDED`, `SIGNAL_VALUE_EVENT_RECORDED` (correlation spine signals)

`SignalBus` — synchronous in-process event bus; supports subscriber callbacks per event_type; TTL-based event expiry.

---

## 3. NATS Subjects Actually in Use

The codebase does **not use NATS** as a message transport. The term "dharma." appears exclusively as **OpenTelemetry span attribute prefixes**, not as pub/sub subject strings.

Observed `dharma.*` attribute keys (on OTel spans):

| Attribute key | Where emitted | Semantic meaning |
|---|---|---|
| `dharma.context_id` | `spine/receipt.py` | Cross-request correlation context |
| `dharma.task_id` | `spine/receipt.py` | Task being executed |
| `dharma.agent_card_version` | `spine/receipt.py` | Which agent card version was used |
| `dharma.receipt_id` | `spine/receipt.py` | Canonical dispatch artifact ID |
| `dharma.status` | `spine/receipt.py`, `llm_burn.py`, tests | ok/failed/dropped/timeout/cancelled |
| `dharma.provider_attempted` | `spine/receipt.py` | Whether provider was actually called |
| `dharma.correlation_id` | `spine/receipt.py` | Same as trace_id (cross-layer alias) |
| `dharma.error_source` | `spine/receipt.py` | Enumerated failure cause |
| `dharma.error_detail` | `spine/receipt.py` | Human-readable error context |
| `dharma.claim_id` | `spine/receipt.py` | Board lease claim ID |
| `dharma.claim_status` | `spine/receipt.py` | Status of the claim lease |
| `dharma.routing_decision_id` | `spine/receipt.py` | Which RoutingDecision applied |
| `dharma.attr.*` | `spine/receipt.py` | Free-form attributes bag |
| `dharma.cost_source` | `llm_burn.py` | How cost was computed (estimated/actual) |
| `dharma.source` | `llm_burn.py` | Module emitting the cost record |
| `dharma.trace_id` | `llm_burn.py` | Trace ID for the LLM call |
| `dharma.span_id` | `llm_burn.py` | Span ID |

**Semgrep rules** also use `dharma.*` as rule IDs (e.g., `dharma.no-unauthorized-dharma-write`, `dharma.providers-canonical`) — these are governance enforcement rules, not runtime subjects.

The actual inter-loop communication uses two mechanisms:
1. **SignalBus** — in-process synchronous event bus (loop-to-loop).
2. **MessageBus** (`dharma_swarm/message_bus.py`) — agent-to-agent message routing.

No NATS client library was found in use. The "spine" the codebase refers to is the `dharma_swarm/spine/` directory (receipt/routing/invoke), not a NATS spine.

---

## 4. Agent Cards / Agent Identities

### Named agents in the startup_crew and constitution:

**Constitutional stable roster (6 agents — `agent_constitution.py`)**:
- `operator` (role: OPERATOR)
- `archivist` (role: ARCHIVIST)
- `research_director` (role: RESEARCH_DIRECTOR)
- `systems_architect` (role: SYSTEMS_ARCHITECT)
- `strategist` (role: STRATEGIST)
- `witness` (role: WITNESS)

**PSMV cognitive crew (from startup_crew.py)**:
- `cartographer` (role: CARTOGRAPHER)
- `surgeon` (role: SURGEON)
- `architect` (role: ARCHITECT)
- `validator` (role: VALIDATOR)

**Frontier / cyber-* agents (startup_crew.py)**:
- `cyber-glm5` — GLM-5 via Ollama cloud, thread: mechanistic
- `cyber-kimi25` — Kimi-K2.5 via Ollama cloud, thread: alignment
- `cyber-codex` — Qwen3-Coder 480B via Ollama cloud, thread: scaling (renamed "codex" despite not being OpenAI Codex)
- `cyber-opus` — Claude Opus (implied from pattern, not fully shown in sample)

**API alias normalization (`_agent_aliases.py`)**:
- `glm5-researcher` → `glm-researcher`
- `kimi-k25-scout` → `kimi-scout`
- `sonnet46-operator` → `sonnet-relay`
- `qwen35-surgeon` → `qwen-builder`

**A2A agent card registry** (`a2a/agent_card.py`): agents self-publish to `~/.dharma/a2a/cards/` directory. The CardRegistry indexes these.

**Agent names in providers (ProviderType enum)**:
Anthropic, OpenAI, OpenRouter, NVIDIA NIM, Local, Claude Code, Codex, OpenRouter Free, Ollama, Groq, Cerebras, SiliconFlow, Together, Fireworks, Google AI, SambaNova, Mistral, Chutes.

**Test suite signals**: `test_ginko_*` (a financial agent named "Ginko"), `test_dgm_loop.py` (DGM = "Darwin-Gnani-Monitor" likely).

### Agent cards in A2A layer:
`AgentCard` fields include: dharma-specific `extensions[]` for dharma-specific layers beyond A2A spec. The `CardRegistry` auto-generates cards from existing `AgentIdentity` / `AgentConfig`.

---

## 5. State Machines

### 5a. Task lifecycle (`models.py`)
`TaskStatus`: PENDING → ASSIGNED → RUNNING → COMPLETED / FAILED / CANCELLED.

### 5b. Agent lifecycle (`models.py`)
`AgentStatus`: IDLE ↔ BUSY (with STARTING → IDLE and STOPPING → DEAD transitions implied by swarm.py).

### 5c. Evolution Proposal lifecycle (`evolution.py`)
`EvolutionStatus`:
```
PENDING
  → REFLECTING  (gate pre-check / think phase)
    → REJECTED   (gate Tier A blocks)
    → GATED      (gate advisory, continues)
      → WRITING  (diff being applied)
        → TESTING  (tests running)
          → EVALUATED  (fitness scored)
            → ARCHIVED  (committed to archive)
          → REJECTED   (test failure)
```

### 5d. ActionProposal lifecycle (ontology, `telic_seam.py`)
Status enum values: `proposed → gated → approved / rejected → executing → completed / failed`.

### 5e. Card lifecycle (`board/models.py`)
`CardStatus` Literal: `pending → doing → done` (also `blocked`, `cancelled`).

### 5f. VentureCell lifecycle (ontology, `ontology.py`)
`autonomy_stage` 1–5 (integer), plus `status` enum: incubating → active → mature → divesting → archived.

### 5g. A2A Task lifecycle (`a2a/a2a_server.py`)
`A2ATaskStatus`: SUBMITTED → WORKING → COMPLETED / FAILED.

### 5h. Evidence / promotion lifecycle (`execution_profile.py`)
`EvidenceTier`: UNVALIDATED → STAGING → PRODUCTION.
`PromotionState`: CANDIDATE → PROMOTED → RETIRED.

### 5i. MemoryTruthState / SkillPromotionState (`contracts/common.py`)
`MemoryTruthState` enum — distinct lifecycle for memory entries.
`SkillPromotionState` enum — distinct lifecycle for skills being promoted.

### 5j. RunStatus / CheckpointStatus (`contracts/common.py`)
`RunStatus`, `CheckpointStatus` — contract-level execution lifecycle.

---

## 6. Message Envelopes

### 6a. RuntimeEnvelope (canonical control-plane)
**Defined in:** `runtime_contract.py`
```
RuntimeEnvelope:
  contract_version: str ("1.0.0")
  event_id: str
  event_type: RuntimeEventType  # state.snapshot | memory.event | action.event | audit.event
  emitted_at: str (ISO)
  source: str
  agent_id: str
  session_id: str
  trace_id: str
  payload: dict
  checksum: str (SHA-256 of canonical JSON)
```
Used by: CanonicalReplayEngine reads `read_envelopes()` to rebuild state from event log.

### 6b. EvidenceReceipt (dispatch artifact)
**Defined in:** `spine/receipt.py`
```
EvidenceReceipt (frozen dataclass):
  receipt_id: UUID
  trace_id, span_id, parent_span_id: str
  context_id, task_id: str
  claim_id, claim_status: Optional[str]
  agent_id, agent_card_version: str
  provider, model, operation: str
  provider_attempted: bool
  status: ReceiptStatus  # ok | failed | dropped | timeout | cancelled
  error_source: ErrorSource  # 14-value enum
  started_at, finished_at: datetime
  latency_ms: Optional[int]
  input_tokens, output_tokens: Optional[int]
  cost_usd: Optional[float]
  routing_decision_id: Optional[UUID]
  attributes: dict
```

### 6c. SignalBus events (in-process)
Raw dicts with `"type"` key. Typed by the 13 SIGNAL_* constants. Not structured (no BaseModel/dataclass). Examples:
```json
{"type": "OUTCOME_RECORDED", "outcome_id": "...", "proposal_id": "...", "task_id": "...", "agent_id": "...", "success": true, "trace_id": "...", "session_id": "..."}
{"type": "VALUE_EVENT_RECORDED", "value_event_id": "...", "outcome_id": "...", "agent_id": "...", "composite_value": 0.7, ...}
```

### 6d. BoardEvent (board facade)
**Defined in:** `board/event_log.py`
```
BoardEvent:
  kind: str  # "card_created" | "card_transitioned"
  card_id: CardId
  actor_kind: str  # "operator" | "agent" | "noticer" | "facade" | "admin"
  ...
```

### 6e. A2A protocol shapes
**Defined in:** `a2a/a2a_server.py`
```
A2AMessage:
  role: str
  parts: list[A2APart]

A2APart:
  type: A2APartType  # text | data | file | tool_call | tool_result
  content: Any

A2AArtifact:
  artifact_id: str
  content_type: str
  data: Any
  description: str
```

### 6f. GatewayMessage (`contracts/common.py`)
Internal gateway shape used by contracts layer.

---

## 7. Concepts the Code Models WELL

**The metabolic loop (TelicSeam)** is exceptionally well-articulated. The chain ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution has clear types, explicit ontology linkage, idempotency checks at every step, a lifecycle integrity report, and Bayesian fitness scoring. This is the most mature abstraction in the codebase.

**The gate system (telos_gates.py)** is clean and principled. Five named gates with clear tiers, keyword-matched trigger patterns, reflective reroute with bounded retries, and a formal variety-expansion protocol for proposing new gates. The naming (AHIMSA, SATYA, REVERSIBILITY, SVABHAAVA, WITNESS) is specific enough to reason about.

**The spine layer** (`spine/receipt.py`, `spine/routing.py`, `spine/invoke.py`) has a clear architectural intention — converge all dispatch through one canonical record. The files contain explicit references to a "CONVERGED_SEAM_AUDIT" doc and PR-labeled milestones (PR A/B/C).

**EvidenceReceipt** is the most complete typed object in the codebase. All 14 error sources are named. Every dispatch outcome maps to one of these.

**EvolutionStatus state machine** in `evolution.py` is explicit and complete — code transitions are traceable.

**StigmergicMark** has a focused, coherent model: agents leave short observations (≤200 chars) with salience, connections, and channel classification. The decay/density mechanism gives the lattice memory-like behavior.

**ShaktiEnergy classification** — 4 energies with keyword-based routing — is simple but consistent. The ontology also tags every ObjectType with a ShaktiEnergy.

**The ontology meta-schema** (ObjectType / OntologyObj / Link / ActionExecution) is principled: explicit schema-vs-instance separation, bidirectional link registration, per-type security policies, and audit records for every action.

**AgentRole enum** is richly expressive — 17 values covering operational, constitutional, cognitive, and ephemeral roles.

---

## 8. Concepts the Code Models POORLY or NOT AT ALL

**Agent identity is defined three times independently.** `models.py` has `AgentConfig` (declared canonical, referencing `AGENT_IDENTITY_UNIFICATION.md`). `agent_registry.py` has `AgentIdentity`. `autonomous_agent.py` has a second `AgentIdentity`. The ontology has a fourth `AgentIdentity` ObjectType. Four representations of the same concept, only one of which is declared canonical.

**MissionState is defined twice** in completely different modules with completely different semantics. `mission_contract.py` has a complex object tracking mission state in flight. `economic_spine.py` has a simple enum (`PLANNING/ACTIVE/PAUSED/COMPLETED/FAILED/ARCHIVED`). These would be confused by any agent reading only one file.

**The "opportunity" concept has no typed class.** The opportunity board (`meta/opportunity_board.json`) is a raw JSON file. `OpportunityCandidate` (`shakti_executive/models.py`) produces entries for it, but there is no `Opportunity` type in the ontology, no lifecycle (pending/dispatched/completed), no receipt linkage. The `opportunity_id` appears in `Task.metadata` (opaque dict).

**The "Venture Cell" concept exists in the ontology but is barely wired.** It appears in `fractal/room_bridge.py` with a `type_name="VentureCell"` write, but the autonomy_stage progression, the budget, and the KPI tracking are all defined in the schema and nowhere implemented in actual lifecycle management code.

**Thinkodynamic Director altitude model** (SUMMIT/STRATOSPHERE/GROUND) is articulated richly in prose but has no typed state machine. There are no typed structs for "altitude" or "ascent." The cycle is implicitly encoded in string prompts.

**Thread rotation** (mechanistic/phenomenological/architectural/alignment/scaling) lives as string constants in `daemon_config.py` with no typed `Thread` concept. Threads drive major behavioral branching but have no ontology presence.

**The "Gnani" concept** is referenced in test names (`test_phase4_gnani_field.py`, `GNANI_LODESTONE.md`) and in `organism.py` ("Gnani/Samvara hold-processing") but has no typed class anywhere in the main code path. It appears to be a moderator or verification concept that exists primarily in docs and test names.

**Memory has at least 4 parallel implementations**: `StrangeLoopMemory` (the named one), `AgentMemoryBank`, `AgentMemoryManager`, `MemoryPalace`, plus the contracts layer `MemoryPlane` protocol and `SovereignMemoryPlaneAdapter`. These don't clearly subsume each other.

**ArchiveEntry and KnowledgeArtifact both represent stored knowledge** but live in different subsystems (evolution archive vs. ontology knowledge store) with no formal link.

**The "circuit breaker" pattern** appears in 3 places: `daemon_config.py` (`CircuitBreaker` class), inline in `evolution.py` (referenced but not typed), and `guardian_crew.py` (ROUTER_PROBE measures). No shared `CircuitBreakerState` type.

---

## 9. Code vs. Vision Tension

These are signals only — Pass 2 will reconcile against vision docs.

**"Shakti" means two different things.** In `shakti.py`, Shakti is a perception/energy classification system (MAHESHWARI/MAHAKALI/MAHALAKSHMI/MAHASARASWATI). In `shakti_executive/`, Shakti is an executive that scores opportunities. The ShaktiEnergy classification is also used to annotate ObjectTypes in the ontology. Three distinct uses of the same Sanskrit word.

**"Swabhaav" appears in fitness scoring** (`swabhaav_alignment` in FitnessScore) and in `AgentIdentity` (`swabhaav_capacity`) but has no module, no typed concept, no tests. It's a measurable dimension that references something that hasn't been formalized.

**"Gnani"** is heavily referenced in doc/test names but absent from the core object model. If vision treats Gnani as a first-class actor (a verification or wisdom authority), code doesn't reflect that.

**"Witness" is overloaded**: MemoryLayer.WITNESS (a memory tier), AgentRole.WITNESS (a constitutional agent), WITNESS gate (a safety gate), WitnessAuditor (an audit class), witness_quality (a field on OntologyObj and Link). Five distinct code uses of the same word without a shared base concept.

**"Telos" is similarly diffuse**: TelicSeam (the metabolic loop seam), telos_gates (the safety gate system), telos_alignment (ObjectType field), AutonomyLevel (the freedom-to-act scale). The word "telos" in code most often means "safety gate" — but "telos" in Greek means "end/purpose" and the vision likely uses it more broadly.

**"Karma" / "dharma" / "dharmic" as field names**: `dharmic_alignment` in FitnessScore, `dharma_attractor.py`, `dharma_corpus.py`, `dharma_kernel.py`, the DHARMA_HOME path, `SecurityLevel.DHARMIC`. These are structural names embedded in actual code, suggesting the system has a real ontological commitment to these concepts — but they're untyped and scattered.

**The "spine" in `dharma_swarm/spine/`** is architectural (a convergence layer for dispatch), while doc filenames reference `CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`. The word "spine" might mean different things at different levels of description.

**"Colony R_V"** appears in `pulse.py` and `ouroboros.py` — an R_V measurement that feeds evolution — but `RV` is not defined in the main ontology. It's referenced as `system_rv` in `SystemVitals` (models.py) and as `r_v_value` on the Experiment ontology type. R_V seems to be a complexity/variety measure (Beer VSM R_V?) with multiple disconnected occurrences.

**The "Strange Loop"** is the name of the memory system (`StrangeLoopMemory`), the `cascade.py` `LoopEngine`, and a concept in `models.py` (`LoopDomain`, `LoopResult`). These are distinct but all reference the Hofstadter/self-referential loop idea without a shared abstraction.

---

## 10. Felt-Sense Summary

What does this system actually DO, in the language of its own code?

**The system is an autonomous software agent network that attempts to improve itself while working on real tasks.** At its core: an Orchestrator dispatches Tasks to AgentRunners, each runner executes an LLM conversation loop with tool calls, and every dispatch attempt produces an EvidenceReceipt. The TelicSeam records every dispatch event as a chain of ontology objects (ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution), maintaining a Bayesian fitness signal for each agent that influences future routing decisions. A DarwinEngine runs in parallel, continuously proposing code mutations, gate-checking them, applying diffs, running tests, scoring fitness across 9 dimensions (including economic value and JIKOKU performance), and archiving results into a quality-diversity grid. The Pulse daemon heartbeats every N hours: it gathers multi-layer context, checks it against 5 dharmic safety gates (AHIMSA first, SATYA second, then advisory gates), runs Claude Code headless, stores results in the strange-loop memory, triggers subconscious dream consolidation when stigmergy density spikes, and then runs Shakti perception to identify high-salience opportunities and feed them back into the lattice as new marks.

**The system models itself as a living organism with economic and ethical metabolic loops.** The Organism class integrates VSM channels (S1–S5 cybernetic coordination), AMIROS experiments, identity coherence monitoring, algedonic pain/pleasure signals, and concept graph tracking. A 6-agent constitutional roster (operator, archivist, research_director, systems_architect, strategist, witness) provides stable governance. A ShaktiExecutive populates an opportunity_board from synthesized signals, and the curriculum engine converts those opportunities into frontier tasks. Everything that crosses a boundary carries a receipt, a trace ID, and a gate verdict. The system is trying to be simultaneously a software development team, a research lab, a self-modifying organism, and an ethical actor — and the code reveals that these ambitions are real, actively implemented, and genuinely in tension with each other at the naming layer.

---

*Files walked: approximately 85 core Python files directly read or grepped, across dharma_swarm/ (75), api/ (10), spine/ (3), a2a/ (5). Class definitions catalogued: 300+. Signal constants identified: 13. Ontology types identified: 14 registered + 6 in the metabolic loop chain. State machines documented: 10. Agent identity definitions found: 4 independent.*
