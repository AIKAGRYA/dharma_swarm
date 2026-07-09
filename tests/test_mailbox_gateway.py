"""Behavioral tests for the HTTPS mailbox gateway (dharma_swarm/a2a/mailbox_gateway.py)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a import mailbox_gateway

TOKEN_ALPHA = "alpha-secret-token"
TOKEN_BRAVO = "bravo-secret-token"


@dataclass
class _Ack:
    seq: int = 4242


@dataclass
class _FakeMsg:
    subject: str
    data: bytes
    acked: bool = False
    _broker: object = None

    async def ack(self) -> None:
        broker = self._broker
        if broker is not None and getattr(broker, "close_count", 0) > 0:
            broker.acks_after_close += 1
            raise RuntimeError("ack over closed connection")
        self.acked = True


@dataclass
class _FakeBroker:
    published: list[tuple[str, bytes]] = field(default_factory=list)
    inbox_messages: list[_FakeMsg] = field(default_factory=list)
    fetch_calls: list[tuple[str, str, int]] = field(default_factory=list)
    fail_publish: bool = False
    close_count: int = 0
    acks_after_close: int = 0

    async def publish(self, subject: str, payload: bytes) -> _Ack:
        if self.fail_publish:
            raise RuntimeError("broker down")
        self.published.append((subject, payload))
        return _Ack()

    async def fetch_inbox(self, subject: str, durable: str, batch: int) -> list[_FakeMsg]:
        self.fetch_calls.append((subject, durable, batch))
        for msg in self.inbox_messages:
            msg._broker = self  # so acks can detect a premature close
        return self.inbox_messages

    async def close(self) -> None:
        self.close_count += 1


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@pytest.fixture
def gateway(tmp_path):
    tokens = tmp_path / "agent_tokens.json"
    tokens.write_text(
        json.dumps(
            {
                "tokens": [
                    {"token_sha256": _sha(TOKEN_ALPHA), "agent_uid": "alpha_agent"},
                    {
                        "token_sha256": _sha(TOKEN_BRAVO),
                        "agent_uid": "bravo-agent",
                        "legacy_callsign": "bravo",
                    },
                ]
            }
        )
    )
    broker = _FakeBroker()

    async def factory() -> _FakeBroker:
        return broker

    mailbox_gateway.init_mailbox_gateway(
        factory,
        tokens_path=tokens,
        receipts_path=tmp_path / "receipts.jsonl",
    )
    app = FastAPI()
    app.include_router(mailbox_gateway.router)
    return TestClient(app), broker, tmp_path


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_whoami_resolves_token_identity(gateway):
    client, _, _ = gateway
    resp = client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_ALPHA))
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_uid"] == "alpha_agent"
    assert "dharma.a2a.alpha_agent" in data["own_subjects"]


def test_missing_and_unknown_tokens_rejected(gateway):
    client, _, _ = gateway
    assert client.get("/a2a/mailbox/whoami").status_code == 401
    assert client.get("/a2a/mailbox/whoami", headers=_auth("wrong")).status_code == 401


def test_no_token_file_fails_closed(tmp_path):
    async def factory():  # pragma: no cover — never reached
        raise AssertionError

    mailbox_gateway.init_mailbox_gateway(
        factory,
        tokens_path=tmp_path / "does_not_exist.json",
        receipts_path=tmp_path / "receipts.jsonl",
    )
    app = FastAPI()
    app.include_router(mailbox_gateway.router)
    client = TestClient(app)
    resp = client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_ALPHA))
    assert resp.status_code == 403


def test_send_publishes_to_peer_with_token_identity(gateway):
    client, broker, _ = gateway
    resp = client.post(
        "/a2a/mailbox/send",
        headers=_auth(TOKEN_ALPHA),
        json={"to": "bravo-agent", "body": {"text": "hello"}, "from": "spoofed_uid"},
    )
    assert resp.status_code == 200
    assert resp.json()["subject"] == "dharma.a2a.bravo-agent"
    assert resp.json()["seq"] == 4242
    (subject, payload), = broker.published
    envelope = json.loads(payload)
    # identity comes from the token — a spoofed 'from' field in the body is ignored
    assert envelope["from"] == "alpha_agent"
    assert envelope["kind"] == "a2a_gateway_message.v1"
    assert envelope["body"] == {"text": "hello"}


def test_send_agent_inbox_route(gateway):
    client, broker, _ = gateway
    resp = client.post(
        "/a2a/mailbox/send",
        headers=_auth(TOKEN_ALPHA),
        json={"to": "bravo-agent", "route": "agent-inbox", "body": "hi"},
    )
    assert resp.status_code == 200
    assert broker.published[0][0] == "dharma.agent.bravo-agent.inbox"


def test_send_validation(gateway):
    client, broker, _ = gateway
    bad = [
        {"to": "evil.>", "body": "x"},              # invalid subject token
        {"to": "bravo-agent"},                        # missing body
        {"to": "bravo-agent", "route": "smoke", "body": "x"},  # unknown route
    ]
    for payload in bad:
        assert client.post("/a2a/mailbox/send", headers=_auth(TOKEN_ALPHA), json=payload).status_code in (400, 413)
    assert broker.published == []


def test_send_broker_failure_is_502_with_receipt(gateway):
    client, broker, tmp = gateway
    broker.fail_publish = True
    resp = client.post(
        "/a2a/mailbox/send", headers=_auth(TOKEN_ALPHA), json={"to": "bravo-agent", "body": "x"}
    )
    assert resp.status_code == 502
    receipts = [json.loads(line) for line in (tmp / "receipts.jsonl").read_text().splitlines()]
    assert receipts[-1]["kind"] == "send_failed"


def test_inbox_drains_only_own_subject_and_acks(gateway):
    client, broker, _ = gateway
    broker.inbox_messages = [
        _FakeMsg("dharma.a2a.alpha_agent", json.dumps({"hello": 1}).encode()),
        _FakeMsg("dharma.a2a.alpha_agent", b"not-json"),
    ]
    resp = client.get("/a2a/mailbox/inbox?batch=5", headers=_auth(TOKEN_ALPHA))
    assert resp.status_code == 200
    data = resp.json()
    # subject derived from the TOKEN identity — there is no way to name a peer's inbox
    assert data["subject"] == "dharma.a2a.alpha_agent"
    assert broker.fetch_calls == [("dharma.a2a.alpha_agent", "gw_alpha_agent_a2a", 5)]
    assert data["messages"][0]["payload"] == {"hello": 1}
    assert data["messages"][1]["payload"] == {"raw": "not-json"}
    assert all(msg.acked for msg in broker.inbox_messages)


def test_inbox_routes_use_distinct_durables(gateway):
    # A JetStream durable is bound to its filter subject; the two routes must
    # never share a durable name or the second route sticks to the first subject.
    client, broker, _ = gateway
    client.get("/a2a/mailbox/inbox?route=a2a", headers=_auth(TOKEN_ALPHA))
    client.get("/a2a/mailbox/inbox?route=agent-inbox", headers=_auth(TOKEN_ALPHA))
    (sub_a, dur_a, _), (sub_b, dur_b, _) = broker.fetch_calls
    assert sub_a == "dharma.a2a.alpha_agent" and sub_b == "dharma.agent.alpha_agent.inbox"
    assert dur_a != dur_b
    assert dur_a == "gw_alpha_agent_a2a" and dur_b == "gw_alpha_agent_agent_inbox"


def test_inbox_batch_is_clamped(gateway):
    client, broker, _ = gateway
    client.get("/a2a/mailbox/inbox?batch=9999", headers=_auth(TOKEN_ALPHA))
    assert broker.fetch_calls[-1][2] == 25


def test_inbox_a2a_route_drains_legacy_callsign_subject(gateway):
    # uid bravo-agent, callsign bravo: the live fleet sends to dharma.a2a.bravo,
    # so that is what the a2a route must drain; durables stay keyed by the uid.
    client, broker, _ = gateway
    resp = client.get("/a2a/mailbox/inbox", headers=_auth(TOKEN_BRAVO))
    assert resp.status_code == 200
    assert broker.fetch_calls == [("dharma.a2a.bravo", "gw_bravo_agent_a2a", 10)]
    who = client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_BRAVO)).json()
    assert "dharma.a2a.bravo" in who["own_subjects"]
    assert who["legacy_callsign"] == "bravo"


def test_broker_stays_open_for_acks_then_closes(gateway):
    client, broker, _ = gateway
    broker.inbox_messages = [_FakeMsg("dharma.a2a.alpha_agent", b"{}")]
    resp = client.get("/a2a/mailbox/inbox", headers=_auth(TOKEN_ALPHA))
    assert resp.status_code == 200
    assert broker.acks_after_close == 0          # no ack raced a closed connection
    assert broker.inbox_messages[0].acked
    assert broker.close_count == 1               # and the broker WAS closed afterwards
    client.post("/a2a/mailbox/send", headers=_auth(TOKEN_ALPHA), json={"to": "bravo-agent", "body": "x"})
    assert broker.close_count == 2


def test_token_revocation_applies_without_restart(gateway):
    import os

    client, _, tmp = gateway
    assert client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_ALPHA)).status_code == 200
    tokens = tmp / "agent_tokens.json"
    tokens.write_text(json.dumps({"tokens": [{"token_sha256": _sha(TOKEN_BRAVO), "agent_uid": "bravo-agent"}]}))
    os.utime(tokens, ns=(1, 1))  # force a distinct mtime regardless of fs resolution
    assert client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_ALPHA)).status_code == 401
    assert client.get("/a2a/mailbox/whoami", headers=_auth(TOKEN_BRAVO)).status_code == 200


def test_oversized_body_rejected_before_parse(gateway):
    client, broker, _ = gateway
    huge = b'{"to": "bravo-agent", "body": "' + b"x" * (70 * 1024) + b'"}'
    resp = client.post(
        "/a2a/mailbox/send",
        headers={**_auth(TOKEN_ALPHA), "Content-Type": "application/json"},
        content=huge,
    )
    assert resp.status_code == 413
    assert broker.published == []


def test_receipts_never_contain_tokens(gateway):
    client, _, tmp = gateway
    client.post("/a2a/mailbox/send", headers=_auth(TOKEN_ALPHA), json={"to": "bravo-agent", "body": "x"})
    client.get("/a2a/mailbox/inbox", headers=_auth(TOKEN_ALPHA))
    text = (tmp / "receipts.jsonl").read_text()
    assert TOKEN_ALPHA not in text and TOKEN_BRAVO not in text
