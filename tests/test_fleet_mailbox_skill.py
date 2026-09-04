"""The external-agent mailbox skill (.agents/skills/dharma-fleet-mailbox/mailbox.py)
driven end-to-end against the real gateway router with a fake broker.

A Hermes/OpenClaw/Claude Code seat runs this script with only the standard
library.  The tests load it by path, shim ``urllib`` onto FastAPI's
``TestClient``, and assert the contract both ways: the client emits exactly
what ``dharma_swarm/a2a/mailbox_gateway.py`` accepts, and the client reports
gateway refusals as typed, token-free errors.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a import mailbox_gateway
from tests.test_mailbox_gateway import _FakeBroker, _FakeMsg

SKILL_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "dharma-fleet-mailbox"
    / "mailbox.py"
)
TOKEN = "hermes-fixture-token-not-live"


def _load_skill():
    spec = importlib.util.spec_from_file_location("fleet_mailbox_skill", SKILL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Response(io.BytesIO):
    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _opener_for(client: TestClient):
    """Translate urllib requests into TestClient calls (HTTPError on 4xx/5xx)."""

    def opener(request, timeout=None):
        url = request.full_url
        path = url[url.index("/a2a") :]
        headers = {k: v for k, v in request.header_items()}
        body = request.data
        response = client.request(request.get_method(), path, content=body, headers=headers)
        if response.status_code >= 400:
            raise urllib.error.HTTPError(
                url, response.status_code, "error", hdrs=None, fp=io.BytesIO(response.content)
            )
        return _Response(response.status_code, response.content)

    return opener


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    tokens = tmp_path / "agent_tokens.json"
    tokens.write_text(
        json.dumps(
            {
                "tokens": [
                    {
                        "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                        "agent_uid": "hermes-m5",
                        "legacy_callsign": "hermes",
                    }
                ]
            }
        )
    )
    broker = _FakeBroker()

    async def factory() -> _FakeBroker:
        return broker

    mailbox_gateway.init_mailbox_gateway(
        factory, tokens_path=tokens, receipts_path=tmp_path / "receipts.jsonl"
    )
    app = FastAPI()
    app.include_router(mailbox_gateway.router)
    client = TestClient(app)
    skill = _load_skill()
    monkeypatch.setenv(skill.ENV_URL, "https://gateway.invalid:8422/")
    monkeypatch.setenv(skill.ENV_TOKEN, TOKEN)
    monkeypatch.setattr(skill.urllib.request, "urlopen", _opener_for(client))
    return skill, broker, client


def test_whoami_returns_gateway_identity_not_a_claim(fleet):
    skill, _, _ = fleet
    result = skill.whoami()
    assert result["agent_uid"] == "hermes-m5"
    assert result["legacy_callsign"] == "hermes"
    assert "dharma.a2a.hermes" in result["own_subjects"]


def test_send_text_publishes_gateway_signed_envelope(fleet):
    skill, broker, _ = fleet
    result = skill.send("rushabdev", "gateway smoke")
    assert result["ok"] is True
    assert result["subject"] == "dharma.a2a.rushabdev"
    assert result["from"] == "hermes-m5"
    (subject, payload) = broker.published[-1]
    envelope = json.loads(payload)
    assert subject == "dharma.a2a.rushabdev"
    assert envelope["from"] == "hermes-m5"  # identity from token, not from us
    assert envelope["body"] == {"text": "gateway smoke"}
    assert envelope["kind"] == mailbox_gateway.MESSAGE_KIND


def test_send_agent_inbox_route_and_json_body(fleet):
    skill, broker, _ = fleet
    result = skill.send("agni", {"task": "review"}, route="agent-inbox")
    assert result["subject"] == "dharma.agent.agni.inbox"
    assert json.loads(broker.published[-1][1])["body"] == {"task": "review"}


def test_heartbeat_broadcasts_reported_presence(fleet):
    skill, broker, _ = fleet
    result = skill.heartbeat("alive")
    assert result["subject"] == "dharma.a2a.fleet"
    body = json.loads(broker.published[-1][1])["body"]
    assert body["kind"] == "presence.v1"
    assert body["agent_uid"] == "hermes-m5"
    assert body["text"] == "alive"


def test_inbox_drains_own_legacy_subject_and_acks(fleet):
    skill, broker, _ = fleet
    msg = _FakeMsg(subject="dharma.a2a.hermes", data=json.dumps({"text": "hi"}).encode())
    broker.inbox_messages = [msg]
    result = skill.inbox(batch=5)
    assert result["agent_uid"] == "hermes-m5"
    assert result["subject"] == "dharma.a2a.hermes"
    assert result["messages"] == [{"subject": "dharma.a2a.hermes", "payload": {"text": "hi"}}]
    assert msg.acked is True
    assert broker.fetch_calls[-1][2] == 5


def test_gateway_refusal_is_typed_and_token_free(fleet, monkeypatch, capsys):
    skill, _, _ = fleet
    monkeypatch.setenv(skill.ENV_TOKEN, "wrong-token")
    code = skill.main(["whoami"])
    out = capsys.readouterr().out
    assert code == 4
    parsed = json.loads(out)
    assert parsed["ok"] is False
    assert "HTTP 401" in parsed["error"]
    assert "wrong-token" not in out and TOKEN not in out


def test_missing_config_is_usage_error(fleet, monkeypatch, capsys):
    skill, _, _ = fleet
    monkeypatch.delenv(skill.ENV_TOKEN)
    assert skill.main(["whoami"]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_send_and_inbox_round_trip(fleet, capsys):
    skill, broker, _ = fleet
    assert skill.main(["send", "fleet", "hello fleet"]) == 0
    sent = json.loads(capsys.readouterr().out)
    assert sent["ok"] is True and sent["subject"] == "dharma.a2a.fleet"
    assert skill.main(["send", "agni", "--json", '{"k": 1}', "--route", "agent-inbox"]) == 0
    assert json.loads(capsys.readouterr().out)["subject"] == "dharma.agent.agni.inbox"
    assert skill.main(["send", "agni", "--json", "not json"]) == 2
    capsys.readouterr()
    assert skill.main(["inbox", "--batch", "99"]) == 0  # clamped to gateway max
    assert broker.fetch_calls[-1][2] == 25


def test_skill_is_stdlib_only():
    source = SKILL_PATH.read_text(encoding="utf-8")
    for forbidden in ("import nats", "import httpx", "import requests", "dharma_swarm"):
        assert forbidden not in source.split('"""', 2)[2], forbidden
