from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "examples/agents/codex_composer.registration.json"
CARD = ROOT / "examples/agents/codex_composer.agent-card.json"
MEMORY = ROOT / "examples/agents/codex_composer.memory.json"
INVARIANT = "sha256:47079c5f0971a1a1ebeaa10b80790602d8bee6d0576746da04ee0347c24f76e8"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_codex_composer_registration_has_one_identity_and_three_replicas() -> None:
    registration = _load(REGISTRATION)
    card = _load(CARD)
    memory = _load(MEMORY)

    assert {
        registration["agent_uid"],
        registration["callsign"],
        card["name"],
        card["agent_uid"],
        memory["agent_uid"],
    } == {"codex_composer"}
    assert registration["memory_namespace"] == memory["memory_namespace"]
    assert card["metadata"]["memory_namespace"] == "agent:codex_composer"
    assert registration["metadata"]["identity_invariant"]["digest"] == INVARIANT
    assert card["metadata"]["identity_invariant_digest"] == INVARIANT
    assert memory["identity_invariant_digest"] == INVARIANT

    replicas = registration["metadata"]["replica_contract"]["replicas"]
    assert {item["instance_id"]: item["role"] for item in replicas} == {
        "agni": "delivery_relay",
        "rushabdev": "hot_standby",
        "meghadharma": "orientation_primary",
    }
    assert (
        registration["metadata"]["replica_contract"]["canonical_presence_instance"]
        == "meghadharma"
    )
    assert registration["metadata"]["replica_contract"]["transport_principals"] == {
        "agni": "codex_composer_agni",
        "rushabdev": "codex_composer_rushabdev",
        "meghadharma": "codex_composer_primary",
    }
    assert registration["metadata"]["replica_contract"]["semantic_consumer_enabled"] is False
    assert memory["typed_boundary"]["rule"] == "ReplicaPresence does not imply ExecutionLease"


def test_codex_composer_card_advertises_presence_not_a_dead_inbox() -> None:
    card = _load(CARD)
    interface = card["supported_interfaces"][0]

    assert card["endpoint"] == "nats://dharma.agent.codex_composer.presence"
    assert interface["protocolBinding"] == "ReplicaPresencePublisher"
    assert interface["subject"] == "dharma.agent.codex_composer.presence"
    assert interface["semantic_consumer_enabled"] is False
    assert card["metadata"]["logical_nats_identity"] == "codex_composer"
    assert card["metadata"]["transport_principals"]["meghadharma"].endswith("_primary")
    assert card["metadata"]["execution_lease_required"] is True


def test_codex_composer_shared_files_contain_no_secret_values() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in (REGISTRATION, CARD, MEMORY)
    ).lower()

    assert "nats_password" not in combined
    assert "api_key" not in combined
    assert "bearer " not in combined
    assert "private_key" not in combined


def test_codex_composer_uses_a_distinct_git_seat() -> None:
    assert (ROOT / "inter_agent/codex_composer/inbound/README.md").exists()
    assert (ROOT / "inter_agent/codex/inbound").exists()
