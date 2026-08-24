"""WP-02: one shared A2A send-envelope schema kills the dead-letter drift.

Red-before-fix: `dharma_swarm.a2a.envelope_schema` does not exist, so the
operator send surface and the inbox drain each define the
`dharma.a2a.send.v1` contract independently and can silently diverge into a
MALFORMED_ENVELOPE dead-letter loop.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.a2a.envelope_schema import (
    SEND_SCHEMA_VERSION,
    EnvelopeValidationError,
    build_send_envelope,
    validate_send_envelope,
)


def test_built_envelope_round_trips_through_shared_validator():
    env = build_send_envelope(
        packet_id="abc123",
        sender="operator",
        to="hermes-m5",
        subject="dharma.agent.hermes-m5.inbox",
    )
    assert validate_send_envelope(env) is env
    assert env["schema_version"] == SEND_SCHEMA_VERSION
    assert env["ack_subject"] == "dharma.agent.hermes-m5.inbox.ack.abc123"
    assert env["packet_id"] == "abc123"


def test_sender_built_envelope_contains_ack_subject(tmp_path: Path):
    from scripts.runtime import a2a_send

    packet = tmp_path / "packet.md"
    packet.write_text("hello fleet\n", encoding="utf-8")
    env = a2a_send.build_envelope(
        to="devin",
        file_path=packet,
        sender="operator",
        kind="fleet.packet",
        packet_id="pkt-42",
    )
    assert env["schema_version"] == SEND_SCHEMA_VERSION
    assert env["ack_subject"] == "dharma.a2a.devin.ack.pkt-42"
    # a real sender envelope is accepted by the shared validator
    assert validate_send_envelope(env) is env


def test_sender_and_bridge_share_one_schema_module():
    from scripts.runtime import a2a_inbox_bridge, a2a_send
    from dharma_swarm.a2a import envelope_schema

    assert a2a_send.build_send_envelope is envelope_schema.build_send_envelope
    assert (
        a2a_inbox_bridge.validate_send_envelope
        is envelope_schema.validate_send_envelope
    )


def test_negative_control_missing_ack_subject_still_fails_validation():
    # DLQ path preserved: an envelope without ack_subject must be rejected.
    env = build_send_envelope(
        packet_id="pkt-1",
        sender="operator",
        to="hermes-m5",
        subject="dharma.agent.hermes-m5.inbox",
    )
    env.pop("ack_subject")
    with pytest.raises(EnvelopeValidationError):
        validate_send_envelope(env)


def test_negative_control_bridge_dead_letters_missing_ack_subject():
    from scripts.runtime import a2a_inbox_bridge

    payload = {
        "schema_version": SEND_SCHEMA_VERSION,
        "packet_id": "pkt-9",
        "subject": "dharma.agent.hermes-m5.inbox",
        "content": "x",
    }
    message = SimpleNamespace(
        data=json.dumps(payload).encode("utf-8"), subject="s"
    )
    with pytest.raises(a2a_inbox_bridge.MalformedEnvelope):
        a2a_inbox_bridge._parse_envelope(message)
