# Semantic Commons

Semantic Commons is the naming and identity source of truth for Dharma Swarm
runtime objects. Code and cards must resolve existing names here before adding
new terms.

## Canonical A2A Contact Vocabulary

| Object | Meaning | Runtime projection |
| --- | --- | --- |
| `A2ACard` | Agent discovery and capability card. | `dharma_swarm.a2a.agent_card.AgentCard` |
| `AgentUID` | Stable durable agent identifier. | NATS subject token under `dharma.agent.<agent_uid>` |
| `NATSSubstrate` | Internal live fleet transport. | JetStream-backed NATS runtime |
| `A2AInboxRoute` | Internal hot-contact route for agent inbox delivery. | alias `agent-inbox` |

`A2AInboxRoute` has this concrete shape:

```yaml
route: agent-inbox
subject: dharma.agent.<agent_uid>.inbox
ack_subject: dharma.agent.<agent_uid>.inbox.ack.<packet_id>
reply_subject: dharma.agent.<agent_uid>.inbox.reply.<packet_id>
```

A remote or local caller should be able to say `codex_composer`, and the
resolver must map:

```text
codex_composer -> A2ACard -> AgentUID -> A2AInboxRoute -> dharma.agent.codex_composer.inbox
```

## Canonical Model Routing Vocabulary

| Object | Meaning | Runtime projection |
| --- | --- | --- |
| `ModelKeyRouting` | One-way contract that keeps provider keys and model selection behind canonical routing surfaces. | `dharma_swarm.model_routing` plus `dharma_swarm.runtime_provider` |
| `DKeysKeyStore` | Durable key material source; feature code must not read project-local provider secrets directly. | `dharma_swarm.api_keys` |
| `RuntimeProvider` | Runtime provider adapter selected by policy, not by scattered model literals. | `dharma_swarm.runtime_provider.RuntimeProvider` |
| `ModelHierarchy` | Canonical model tier and fallback catalog. | `dharma_swarm.model_hierarchy` |
| `ProviderPolicyRouter` | Policy layer that chooses allowed providers for a task/context. | `dharma_swarm.model_routing.ProviderPolicyRouter` |
| `ModelRouter` | Public model routing facade used by callers instead of direct provider factories. | `dharma_swarm.model_routing.ModelRouter` |
| `RoutingMemory` | Receipt and memory layer for routing decisions and drift checks. | `dharma_swarm.model_routing` |

Deprecated routing descriptions must not become live architecture names:
`parallel model routing layer`, `project .env keys`, `direct provider factory`,
and `scattered model order`.

## Boundary

NATS is the internal fleet transport. A2A HTTP and public Agent Cards remain
the external discovery and cross-vendor edge. Internal A2A cards may advertise
external HTTP interfaces, but their durable fleet contact binding must include
`A2AInboxRoute`.
