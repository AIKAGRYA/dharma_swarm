import json

from dharma_swarm.a2a.agent_card import (
    A2A_INBOX_ROUTE_ALIAS,
    A2AInboxRoute,
    AgentCard,
    CardRegistry,
    SEMANTIC_OBJECT_A2A_INBOX_ROUTE,
    SEMANTIC_OBJECT_NATS_SUBSTRATE,
    a2a_inbox_subject,
    resolve_agent_uid,
)


def _a2a_inbox_interface(card: AgentCard) -> dict[str, str]:
    matches = [
        item
        for item in card.supported_interfaces
        if item.get("protocolBinding") == SEMANTIC_OBJECT_A2A_INBOX_ROUTE
    ]
    assert len(matches) == 1
    return matches[0]


def test_registered_card_gets_semantic_commons_a2a_inbox_route(tmp_path):
    registry = CardRegistry(cards_dir=tmp_path)
    registry.register(
        AgentCard(
            name="codex_composer",
            description="implementation lead",
            endpoint="local://m5/codex_cli",
        )
    )

    card = registry.get("codex_composer")
    assert card is not None
    assert card.agent_uid == "codex_composer"
    iface = _a2a_inbox_interface(card)
    assert iface["route"] == A2A_INBOX_ROUTE_ALIAS
    assert iface["substrate"] == SEMANTIC_OBJECT_NATS_SUBSTRATE
    assert iface["subject"] == "dharma.agent.codex_composer.inbox"
    assert iface["ack_subject"] == "dharma.agent.codex_composer.inbox.ack.{packet_id}"
    assert iface["reply_subject"] == "dharma.agent.codex_composer.inbox.reply.{packet_id}"
    assert card.metadata["semantic_commons"]["route"] == "A2AInboxRoute"
    assert card.metadata["a2a_inbox_route"]["subject"] == iface["subject"]


def test_registry_load_replaces_legacy_internal_nats_subject(tmp_path):
    (tmp_path / "palantir-pilot.json").write_text(
        json.dumps(
            {
                "name": "palantir-pilot",
                "supported_interfaces": [
                    {
                        "protocolBinding": "NATS",
                        "subject": "dharma.a2a.palantir-pilot",
                    },
                    {
                        "protocolBinding": "HTTP+JSON",
                        "url": "https://edge.example.test/.well-known/agent-card.json",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    card = CardRegistry(cards_dir=tmp_path).get("palantir-pilot")
    assert card is not None
    assert card.agent_uid == "palantir-pilot"
    assert "dharma.a2a.palantir-pilot" not in json.dumps(card.to_dict())
    assert _a2a_inbox_interface(card)["subject"] == "dharma.agent.palantir-pilot.inbox"
    assert any(item.get("protocolBinding") == "HTTP+JSON" for item in card.supported_interfaces)


def test_resolver_finds_card_by_alias_and_returns_agent_inbox_route(tmp_path):
    registry = CardRegistry(cards_dir=tmp_path)
    registry.register(AgentCard(name="hermes-m5"))

    assert resolve_agent_uid("hermes") == "hermes-m5"
    assert resolve_agent_uid("fable-composer") == "fable_composer"
    route = registry.resolve_a2a_inbox_route("hermes")
    assert route == A2AInboxRoute(agent_uid="hermes-m5")
    assert route.subject == "dharma.agent.hermes-m5.inbox"
    assert a2a_inbox_subject("hermes") == "dharma.agent.hermes-m5.inbox"


def test_from_agent_identity_uses_agent_uid_over_display_name():
    card = AgentCard.from_agent_identity(
        {
            "name": "devin",
            "agent_uid": "devin-roaming-2987d222",
            "role": "operator",
            "status": "idle",
        }
    )

    assert card.name == "devin"
    assert card.agent_uid == "devin-roaming-2987d222"
    assert _a2a_inbox_interface(card)["subject"] == "dharma.agent.devin-roaming-2987d222.inbox"
