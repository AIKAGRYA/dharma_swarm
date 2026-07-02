from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from dharma_swarm.holon_canonical_state import project_canonical_holon_state
from dharma_swarm.holon_service_liveness import record_service_heartbeat


def _write_identity(agents_root: Path) -> None:
    agent = agents_root / "codex_composer"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "identity.json").write_text(
        json.dumps({"provider": "ollama", "model": "glm-5:cloud"}, sort_keys=True),
        encoding="utf-8",
    )


def _write_bridge_heartbeat(a2a_bus: Path, *, observed: datetime) -> None:
    path = a2a_bus / "bridge_heartbeats" / "codex_composer.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
                "timestamp": observed.isoformat().replace("+00:00", "Z"),
                "agent_uid": "codex_composer",
                "status": "IDLE",
                "subject": "dharma.agent.codex_composer.inbox",
                "stream": "DHARMA_FLEET",
                "consumer": "codex_composer_inbox",
                "last_receipt_path": "/tmp/bridge.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_canonical_state_projects_component_liveness_and_receipts(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    a2a_bus = tmp_path / "a2a_bus"
    state_dir = tmp_path / "semantic_responder"
    observed = datetime.now(UTC).replace(microsecond=0)
    _write_identity(agents_root)
    _write_bridge_heartbeat(a2a_bus, observed=observed)
    (a2a_bus / "state").mkdir(parents=True, exist_ok=True)
    (a2a_bus / "state" / "codex_composer.json").write_text(
        json.dumps(
            {
                "agent_uid": "codex_composer",
                "component_freshness": {"l4_service": "stale"},
                "launchd": {"label": "old-label", "pid": 99, "pid_known": True},
                "legacy_field": "preserve-me",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    semantic_receipt = state_dir / "receipts" / "semantic.json"
    semantic_receipt.parent.mkdir(parents=True, exist_ok=True)
    semantic_receipt.write_text(
        json.dumps(
            {
                "status": "DOMAIN_REPLY_PUBLISHED",
                "timestamp": observed.isoformat().replace("+00:00", "Z"),
                "packet_id": "packet-1",
                "reply_subject": "dharma.agent.codex_composer.inbox.reply.packet-1",
                "semantic_reply_claim": True,
                "domain_receipt_claim": True,
                "handler_ack_is_semantic_cognition": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact = agents_root / "codex_composer" / "artifacts" / "l4.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "claim_scope": {
                    "transport_reachable": True,
                    "orchestration_proven": True,
                    "live_model_call_claimed": False,
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        service_id="codex-composer-semantic-responder",
        status="idle",
        observed_at=observed,
    )
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        service_id="holon-l4-service",
        status="idle",
        observed_at=observed,
        proof_ref={
            "kind": "l4_service_cycle",
            "artifact": {
                "path": str(artifact),
                "digest": "sha256:l4",
            },
            "proof_digest": "sha256:proof",
        },
        claim_scope={
            "transport_reachable": True,
            "orchestration_proven": True,
            "live_model_call_claimed": False,
        },
    )

    state = project_canonical_holon_state(
        "codex_composer",
        agents_root=agents_root,
        a2a_bus=a2a_bus,
        semantic_responder_state_dir=state_dir,
        launchd_label="com.dharma.codex-composer-semantic-responder",
        pid=4242,
        now=observed,
    )

    assert state["legacy_field"] == "preserve-me"
    assert state["status"] == "operational"
    assert state["bridge_transport_reachable"] is True
    assert state["responder_alive"] is True
    assert state["l4_service_alive"] is True
    assert state["live_model_call_claimed"] is False
    assert state["latest_semantic_responder_receipt"]["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert state["latest_l4_proof_artifact"] == str(artifact)
    assert state["latest_l4_proof_digest"] == "sha256:l4"
    assert state["freshness"] == {
        "bridge": "fresh",
        "semantic_responder": "fresh",
        "l4_service": "fresh",
    }
    assert state["component_freshness"] == state["freshness"]
    assert state["launchd"] == {
        "label": "com.dharma.codex-composer-semantic-responder",
        "pid": 4242,
        "pid_known": True,
    }
    assert (a2a_bus / "state" / "codex_composer.json").is_file()


def test_canonical_state_refuses_wrong_agent_target(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    a2a_bus = tmp_path / "a2a_bus"
    _write_identity(agents_root)
    state_path = a2a_bus / "state" / "codex_composer.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"agent_uid": "hermes-m5"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    try:
        project_canonical_holon_state(
            "codex_composer",
            agents_root=agents_root,
            a2a_bus=a2a_bus,
        )
    except ValueError as exc:
        assert "expected 'codex_composer'" in str(exc)
    else:
        raise AssertionError("expected wrong-agent canonical state guard")
