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

    async def ack(self) -> None:
        self.acked = True


@dataclass
class _FakeBroker:
    published: list[tuple[str, bytes]] = field(default_factory=list)
    inbox_messages: list[_FakeMsg] = field(default_factory=list)
    fetch_calls: list[tuple[str, str, int]] = field(default_factory=list)
    fail_publish: bool = False

    async def publish(self, subject: str, payload: bytes) -> _Ack:
        if self.fail_publish:
            raise RuntimeError("broker down")
        self.published.append((subject, payload))
        return _Ack()

    async def fetch_inbox(self, subject: str, durable: str, batch: int) -> list[_FakeMsg]:
        self.fetch_calls.append((subject, durable, batch))
        return self.inbox_messages


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
                    {"token_sha256": _sha(TOKEN_BRAVO), "agent_uid": "bravo-agent"},
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
    assert broker.fetch_calls == [("dharma.a2a.alpha_agent", "gw_alpha_agent", 5)]
    assert data["messages"][0]["payload"] == {"hello": 1}
    assert data["messages"][1]["payload"] == {"raw": "not-json"}
    assert all(msg.acked for msg in broker.inbox_messages)


def test_inbox_batch_is_clamped(gateway):
    client, broker, _ = gateway
    client.get("/a2a/mailbox/inbox?batch=9999", headers=_auth(TOKEN_ALPHA))
    assert broker.fetch_calls[-1][2] == 25


def test_receipts_never_contain_tokens(gateway):
    client, _, tmp = gateway
    client.post("/a2a/mailbox/send", headers=_auth(TOKEN_ALPHA), json={"to": "bravo-agent", "body": "x"})
    client.get("/a2a/mailbox/inbox", headers=_auth(TOKEN_ALPHA))
    text = (tmp / "receipts.jsonl").read_text()
    assert TOKEN_ALPHA not in text and TOKEN_BRAVO not in text
