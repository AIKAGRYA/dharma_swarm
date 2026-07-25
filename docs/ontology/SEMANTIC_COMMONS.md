# Semantic Commons

Semantic Commons is the naming and identity source of truth for Dharma Swarm
runtime objects. Code and cards must resolve existing names here before adding
new terms.

Claim-maturity vocabulary for promotion language lives in
[`CLAIM_MATURITY_VOCABULARY.md`](CLAIM_MATURITY_VOCABULARY.md). It keeps
workflow status separate from evidence-backed claims.

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

## Canonical Model/Key Routing Vocabulary

| Object | Meaning | Runtime projection |
| --- | --- | --- |
| `ModelKeyRouting` | The one routing contract for provider keys, runtime provider creation, model order, and routing memory. | `docs/ops/MODEL_KEY_ROUTING.md` |
| `DKeysKeyStore` | Provider key lookup source. | `dharma_swarm/api_keys.py` via `dkeys` and `~/.dharma/agent_keys.env` |
| `RuntimeProvider` | Single provider resolution and creation door. | `dharma_swarm/runtime_provider.py` |
| `ModelHierarchy` | Canonical most-powerful-first model and route order. | `dharma_swarm/model_hierarchy.py` |
| `ProviderPolicyRouter` | Provider-family policy and escalation layer. | `dharma_swarm/provider_policy.py` |
| `ModelRouter` | Runtime router for executing provider calls under the canonical contract. | `dharma_swarm/providers.py` |
| `RoutingMemory` | Provider-learning evidence store for route outcomes. | `dharma_swarm/routing_memory.py` |

Deprecated names resolve back into `ModelKeyRouting`; do not create a
`parallel model routing layer`, read `project .env keys`, instantiate a
`direct provider factory`, or maintain `scattered model order`.

## Boundary

NATS is the internal fleet transport. A2A HTTP and public Agent Cards remain
the external discovery and cross-vendor edge. Internal A2A cards may advertise
external HTTP interfaces, but their durable fleet contact binding must include
`A2AInboxRoute`.

## Model Routing Vocabulary

Model and provider routing names resolve through `ModelKeyRouting`. Provider
credentials belong behind `DKeysKeyStore` and `RuntimeProvider`; model ordering
belongs behind `ModelHierarchy`; policy routing belongs behind
`ProviderPolicyRouter`; runtime routing belongs behind `ModelRouter`; and
routing outcomes belong behind `RoutingMemory`.

Do not introduce deprecated aliases such as `parallel model routing layer`,
`project .env keys`, `direct provider factory`, or `scattered model order` as
live architecture names.
