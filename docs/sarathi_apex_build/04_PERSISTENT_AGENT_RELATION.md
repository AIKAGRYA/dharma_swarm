# 04 — Persistent-Agent Relation

> **Design lineage:** This composition sketch is retained for context. Current
> implementation and lifecycle boundaries are owned by
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md).

The stack is composition, not replacement:

```text
Registry / identity records
  -> PersistentAgent / AutonomousAgent lineage
  -> LivingAgentKernel durable wake ledger + leases + closeback
  -> Holon bridge/runtime/persistence/health
  -> Existing orchestrator fan-out/fan-in
  -> Sarathi apex wrapper: reversibility gate + roster + brief + continuity
```

| Layer | Existing code | Meaning | What it is not |
|---|---|---|---|
| Registry / identity | `dharma_swarm/agent_registry.py`; runtime `identity.json` files | Names, policy fields, admission metadata. | Liveness proof. |
| Persistent actor lineage | `dharma_swarm/persistent_agent.py`; `dharma_swarm/autonomous_agent.py` | Older standing/executing actor patterns. | The apex holon body by itself. |
| Living durable spine | `dharma_swarm/operator_core/living_agent_kernel*.py` | Wake ledger, leases, proof ledger, closeback, services. | Duplicate holon runtime. |
| Holon runtime | `dharma_swarm/holon_bridge.py`; `dharma_swarm/holon_runtime.py`; `dharma_swarm/holon_persistence.py`; `dharma_swarm/holon_health.py` | Identity-aware governed wake cycle. | Sarathi-specific chief-of-staff loop by itself. |
| Existing swarm orchestration | `dharma_swarm/swarm.py`; `dharma_swarm/agent_runner.py`; related orchestrator code | Load-bearing substrate for fan-out/fan-in and workers. | Something to collapse in this lane. |
| Apex safety | `dharma_swarm/operator_core/reversibility_gate.py`; execution leases | Deterministic envelope for unattended action. | Model opinion or self-approval. |
| Sarathi wrapper | Phase C `dharma_swarm/holon_system/sarathi/*` | Operator-facing apex package. | A parallel substrate. |

The legacy stack is substrate. The duplicate `holon/` package is not substrate;
it is a fork and must be removed after its importers are migrated.
