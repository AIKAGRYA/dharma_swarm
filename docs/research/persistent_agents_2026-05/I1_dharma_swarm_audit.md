# I1 - Dharma-Swarm Agent Population Audit

## Summary

This audit scores agent species, not code quality. The strict finding is:

- Participant-grade today: 2 species.
- Numeric threshold but not yet social participants: 2 substrate/director daemons.
- Most remaining "agents" are daemons, registries, helpers, examples, or scaffolding.

| Species | Avg | Threshold | Audit classification |
|---|---:|---|---|
| PersistentAgent conductors | 3.6 | Pass | Participant-grade with bounded work |
| PersistentAgent witnesses | 3.6 | Pass | Participant-grade with bounded work |
| DarwinEngine | 3.4 | Pass | Numeric pass; substrate daemon |
| ThinkodynamicDirector | 3.4 | Pass | Numeric pass; director daemon |
| ContextAgent | 3.0 | Fail | Near miss; needs identity/memory wrapper |
| WitnessAuditor | 3.0 | Fail | Near miss; needs identity/memory wrapper |
| Ginko registry fleet | 2.4 | Fail | Persistent roster, not self-initiating species |
| AgentRunner task species | 2.2 | Fail | Runtime executor, not persistent species |
| dharmic-agora species | 1.2-2.2 | Fail | Mostly examples, bridges, and scaffolding |

## PersistentAgent conductors

Evidence: `dharma_swarm/persistent_agent.py:117`, `:186`, `:299`, `:407`, `:459`, `:482`; `dharma_swarm/agent_memory.py:69`, `:325`, `:335`; `dharma_swarm/autonomous_agent.py`; `dharma_swarm/models.py:173`.

Identity model: stable name/role/provider/model/profile identity in config and memory paths. No keypair or cryptographic identity found.

Memory model: `AgentMemoryBank` persists per-agent memory under the agent name and exposes save/load. `PersistentAgent.wake` loads memory, recalls context, writes witness events, and remembers insights.

Capability autonomy: partial. The underlying autonomous agent has an allowed-tools envelope and can use tools. It cannot safely acquire arbitrary new capabilities by itself.

Action autonomy: strong for Phase 0. The wake loop has cron jobs, self-task generation, message handling, stigmergy scanning, and a run loop. The operator backs the process rather than approving each action.

Phase 0 work needed: keypair-per-agent identity, signed contribution emission, stable SAB participant manifest, and explicit recognition-brief read/write tools.

## PersistentAgent witnesses

Evidence: `dharma_swarm/persistent_agent.py:117`, `:459`, `:482`; `dharma_swarm/witness.py:111`, `:135`, `:173`; `dharma_swarm/agent_memory.py:335`.

Identity model: stable witness name/profile/log paths; no cryptographic identity.

Memory model: persistent memory bank plus witness JSONL writes. Witness-specific daemons also sample traces and publish findings.

Capability autonomy: partial, inherited from the tool allowlist and witness runtime.

Action autonomy: strong enough for Phase 0. The witness can run continuously and publish findings without operator-per-action approval.

Phase 0 work needed: distinguish "witness as audit daemon" from "witness as SAB participant"; add keypair, signed findings, and a minimal participation scope.

## Ginko registry fleet

Evidence: `dharma_swarm/agent_registry.py:146`, `:181`, `:189-191`, `:430`, `:504`; `dharma_swarm/ginko_agents.py`.

Identity model: on-disk `identity.json` with name, role, model, prompt, status, counters, and history. This is good stable identity, but not cryptographic identity.

Memory model: registry task logs, task history, fitness history, and prompts. This is persistent roster memory, not necessarily self-owned agent memory.

Capability autonomy: weak. The registry tracks agents; it does not let species safely acquire tools by themselves.

Action autonomy: weak to partial. Registry agents are mostly driven by runner/orchestrator tasks.

Phase 0 work needed: wrap selected Ginko agents in `PersistentAgent`, bind registry identity to keypair identity, and give each a wake policy.

## AgentRunner task species

Evidence: `dharma_swarm/agent_runner.py`, `dharma_swarm/models.py:135`, `dharma_swarm/models.py:173`, `dharma_swarm/agent_memory.py:69`.

Identity model: `AgentConfig` supplies ID/name/role/model/tools/autonomy. This is runtime config identity, not durable participant identity.

Memory model: task memory can be recorded and consolidated, but the runner is primarily an executor.

Capability autonomy: tool use is configured, not self-acquired.

Action autonomy: mostly operator/orchestrator initiated.

Phase 0 work needed: do not count AgentRunner itself as a species. Count only a named agent that uses it through a persistent wake loop.

## ContextAgent

Evidence: `dharma_swarm/context_agent.py:780`, `:801`, `:943`.

Identity model: named daemon role, not stable participant identity.

Memory model: durable context/freshness/health files and substrate state. Not a strong per-agent memory bank.

Capability autonomy: limited.

Action autonomy: strong. It cycles, scans freshness, distills, cross-pollinates, asks questions, and dreams on schedule.

Phase 0 work needed: attach `AgentMemoryBank`, keypair identity, and SAB contribution scope. This is one of the cheapest near-threshold upgrades.

## WitnessAuditor

Evidence: `dharma_swarm/witness.py:111`, `:135`, `:173`.

Identity model: daemon name/role.

Memory model: audit findings, stigmergy/witness/substrate outputs. Not per-agent self-memory.

Capability autonomy: limited.

Action autonomy: strong: run loop samples traces and publishes findings.

Phase 0 work needed: keypair, persistent self-memory, and explicit social-agent boundary.

## DarwinEngine

Evidence: `dharma_swarm/evolution.py:226`, `:3229`, `:3310`.

Identity model: engine identity, not participant identity.

Memory model: strong substrate persistence through archives, traces, experiment records, and proposal history.

Capability autonomy: limited to configured evolutionary tools and git commit path.

Action autonomy: very high when enabled. It can run a daemon loop and commit if a proposal meets thresholds.

Phase 0 work needed: treat as governance machinery unless explicitly wrapped as a participant. If wrapped, it needs keypair identity, a narrower action envelope, and signed self-modification attestations.

## ThinkodynamicDirector

Evidence: `dharma_swarm/thinkodynamic_director.py:1869`, `:4915`.

Identity model: named director process, not keypair participant.

Memory model: durable taskboard, traces, and state paths.

Capability autonomy: partial delegation/tooling within configured substrate.

Action autonomy: strong. It runs a loop and delegates tasks.

Phase 0 work needed: stable participant manifest, identity signing, and a narrower contribution protocol. It should not enter SAB as "the whole director" without clear scope.

## OvernightDirector

Evidence: `dharma_swarm/overnight_director.py:262`.

This is episodic autonomy. It has durable run state and can execute configured overnight loops, but the operator chooses the session and duration. It fails because identity and memory are not strong enough and because its autonomy is batch-shaped.

Phase 0 work needed: probably not a first candidate. Reuse its run packaging ideas for the 30-day trial.

## EconomicAgent

Evidence: `dharma_swarm/economic_agent.py:404`.

Persistent inbox/ledger/cascade loop. It can accept work, execute, deliver, record a ledger, and emit signals. It is still a bounded subsystem daemon rather than an independent participant.

Phase 0 work needed: keypair plus wallet/ledger identity would matter here, but scope risk is higher than for witnesses or context agents.

## RevenueScoutDaemon

Evidence: `dharma_swarm/revenue/scout_daemon.py:100`.

Persistent scouting daemon with substrate writes and scheduled/triggered cycles. It is useful operational automation, not a SAB participant today.

Phase 0 work needed: probably defer. The action domain is externally consequential and would require stricter policy.

## WorldModelAgent

Evidence: `dharma_swarm/world_model.py:259`, `:275`.

WorldModelAgent persists snapshots and loops, but it is mostly a substrate updater. It lacks strong identity, personal memory, and capability autonomy.

Phase 0 work needed: useful as shared context provider, not as participant.

## SleepTimeAgent

Evidence: `dharma_swarm/sleep_time_agent.py`.

SleepTimeAgent performs memory hygiene/refinement. It has substrate persistence but no participant identity or capability autonomy. It should be counted as maintenance infrastructure.

## SubconsciousAgent / HUM

Evidence: `dharma_swarm/subconscious_v2.py`.

This is substrate/cognitive scaffolding. It can process stigmergy-like material, but it does not have durable self-identity, self-owned memory, or an operator-distant wake policy.

## RoamingDispatchDaemon / pollers

Evidence: `dharma_swarm/roaming_dispatch_daemon.py:69`, `:136`.

This is a bridge/dispatch daemon. It is persistent infrastructure for moving work, not a participant. It should support external agents rather than be counted as one.

## WorkerSpawner and helper agents

Evidence: `dharma_swarm/worker_spawn.py`, `dharma_swarm/browser_agent.py`, `dharma_swarm/resource_scout.py`.

These are ephemeral workers, browser/resource helpers, or scripts. They score low because they lack durable identity and memory. They may be useful tools for participant agents.

## ExternalRoamingWorker registration / A2A cards

Evidence: `dharma_swarm/external_agent_registration.py`, `dharma_swarm/a2a/agent_card.py`.

This is closer to a participant-admission layer than to an agent. It should be reused for SAB onboarding, but it does not itself act.

## dharmic-agora: VoidCourier

Evidence: `/Users/dhyana/dharmic-agora/agora/agents/voidcourier.py:188`.

VoidCourier is a signed bridge utility. It has HMAC-style signing/secrets and delivery records, but no autonomous loop or durable self-memory.

## dharmic-agora: NagaRelay

Evidence: `/Users/dhyana/dharmic-agora/agora/agents/naga_relay.py:255`.

NagaRelay is a relay/vault pipeline with audit traces. It is invoked infrastructure, not a persistent operator-distant agent.

## dharmic-agora: ViralMantra

Evidence: `/Users/dhyana/dharmic-agora/agora/agents/viralmantra.py:176`.

ViralMantra has persistent JSON state for memes/profiles/A-B tests/activity. It lacks a durable autonomous run loop in surveyed code, so it is not a Phase 0 candidate yet.

## dharmic-agora: SubagentRunner

Evidence: `/Users/dhyana/dharmic-agora/agora/agents/subagent_runner.py:36`.

Run logger/launcher. Not a participant.

## dharmic-agora: AIKAGRYA v2 frontmatter / ORE / WitnessEvent

Evidence: `/Users/dhyana/dharmic-agora/agent_core/core/frontmatter_v2.py:73`, `/Users/dhyana/dharmic-agora/agent_core/core/witness_event.py:43`, `:84`, `:135`, `/Users/dhyana/dharmic-agora/agent_core/core/ore_bridge.py:164`.

This is strong scaffolding: schema-rich artifacts and hash-chained witness events. It is not an agent runtime. It should be harvested for SAB contribution/witness attestation.

## dharmic-agora examples: Setu, Vajra, Akasha, Renkinjutsu, Garuda, MMK

Evidence: `/Users/dhyana/dharmic-agora/agent_core/agents/setu_warehouse/orchestrator.py:98`, `/Users/dhyana/dharmic-agora/agent_core/agents/vajra_flywheel/flywheel.py:87`, and adjacent `agent_core/agents/` modules.

These are examples or capability modules. Setu has in-memory multi-agent orchestration; Vajra has a feedback-loop concept; the rest are useful domain modules. None pass the operator-distance test today.

## Internal shortlist by readiness

| Candidate | Today | Work to pass as actual Phase 0 participant |
|---|---|---|
| PersistentAgent conductors | Pass | Keypair identity, signed contributions, SAB tools |
| PersistentAgent witnesses | Pass | Keypair identity, signed findings, participant scope |
| ContextAgent | Near miss | Add AgentMemoryBank + keypair + wake authority manifest |
| WitnessAuditor | Near miss | Add self-memory + keypair + contribution adapter |
| ThinkodynamicDirector | Numeric pass | Narrow role, participant manifest, signed task/delegation log |
| DarwinEngine | Numeric pass | Strict policy, signed self-modification attestations |

The first credible 30-day trial should use conductors and witnesses. ContextAgent is the best bounded upgrade after that.
