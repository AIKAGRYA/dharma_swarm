from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
import pytest

from api.routers import chat as chat_router
from api.ws import _dashboard_websocket_session_matches


def _dashboard_session(secret: str, expires: int) -> str:
    payload = f"v1.{expires}"
    digest = hmac.new(
        secret.encode(),
        f"dharma-dashboard-ws-session.v1:{payload}".encode(),
        hashlib.sha256,
    ).digest()
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{payload}.{signature}"


def _chat_client() -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(chat_router.ws_router)
    return TestClient(app)


def _read_sse_payloads(response) -> list[object]:
    payloads: list[object] = []
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if data == "[DONE]":
            payloads.append(data)
            continue
        payloads.append(json.loads(data))
    return payloads


def test_chat_status_advertises_session_websocket_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    client = _chat_client()
    resp = client.get("/api/chat/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["chat_ws_path_template"] == "/ws/chat/session/{session_id}"


def test_chat_session_websocket_requires_configured_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_API_KEY", "fixture-token-not-live")
    client = _chat_client()

    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect("/ws/chat/session/no-token"):
            pass
    assert rejected.value.code == 4401

    with pytest.raises(WebSocketDisconnect) as query_rejected:
        with client.websocket_connect(
            "/ws/chat/session/query-token?token=fixture-token-not-live"
        ):
            pass
    assert query_rejected.value.code == 4401


def test_chat_session_websocket_accepts_dashboard_subprotocol_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = "fixture-token-not-live"
    encoded = base64.urlsafe_b64encode(credential.encode()).decode().rstrip("=")
    monkeypatch.setenv("DASHBOARD_API_KEY", credential)
    client = _chat_client()

    with client.websocket_connect(
        "/ws/chat/session/with-subprotocol",
        subprotocols=["dharma-auth", f"dharma-bearer.{encoded}"],
    ) as websocket:
        assert websocket.accepted_subprotocol == "dharma-auth"
        assert credential not in websocket.accepted_subprotocol
        assert websocket.receive_json()["event"] == "chat_snapshot"


def test_dashboard_websocket_session_digest_matches_browser_contract() -> None:
    token = "v1.1700000300.S2MVkDTomFFWCy9ot2PT-W1NobJepZ6LJze6ZR9Z_kI"

    assert _dashboard_websocket_session_matches(
        token,
        "fixture-token-not-live",
        now=1_700_000_000,
    )
    assert not _dashboard_websocket_session_matches(
        token,
        "different-secret",
        now=1_700_000_000,
    )
    forged_empty = _dashboard_session("", 1_700_000_300)
    assert not _dashboard_websocket_session_matches(
        forged_empty,
        "",
        now=1_700_000_000,
    )


def test_chat_session_websocket_accepts_short_lived_same_origin_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = "fixture-token-not-live"
    token = _dashboard_session(credential, int(time.time()) + 300)
    monkeypatch.setenv("DASHBOARD_API_KEY", credential)
    client = _chat_client()

    with client.websocket_connect(
        "/ws/chat/session/browser-cookie",
        headers={
            "origin": "http://127.0.0.1:3420",
            "cookie": f"dharma_ws_session={token}",
        },
    ) as websocket:
        assert websocket.accepted_subprotocol is None
        assert websocket.receive_json()["event"] == "chat_snapshot"


def test_chat_session_websocket_accepts_ipv6_loopback_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = "fixture-token-not-live"
    token = _dashboard_session(credential, int(time.time()) + 300)
    monkeypatch.setenv("DASHBOARD_API_KEY", credential)
    client = _chat_client()

    with client.websocket_connect(
        "/ws/chat/session/browser-cookie-ipv6",
        headers={
            "origin": "http://[::1]:3420",
            "cookie": f"dharma_ws_session={token}",
        },
    ) as websocket:
        assert websocket.receive_json()["event"] == "chat_snapshot"


def test_chat_session_websocket_fails_closed_for_blank_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = _dashboard_session("", int(time.time()) + 300)
    monkeypatch.setenv("DASHBOARD_API_KEY", "   ")
    client = _chat_client()

    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect(
            "/ws/chat/session/blank-key",
            headers={
                "origin": "http://127.0.0.1:3420",
                "cookie": f"dharma_ws_session={token}",
            },
        ):
            pass
    assert rejected.value.code == 1011


def test_chat_session_websocket_rejects_untrusted_browser_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)
    client = _chat_client()

    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect(
            "/ws/chat/session/cross-site",
            headers={"origin": "https://evil.example"},
        ):
            pass
    assert rejected.value.code == 4403


def test_chat_stream_emits_session_id_and_replays_session_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_router, "_new_session_id", lambda: "dash-test-session", raising=False
    )

    async def fake_brief() -> str:
        return "context ok"

    call_count = 0

    async def fake_call_openrouter(messages, runtime_settings):
        del messages
        del runtime_settings
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Recon started.",
                            "tool_calls": [
                                {
                                    "id": "tc-1",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"/tmp/demo.txt"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {
                        "content": "Patch complete.",
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    async def fake_execute_tool(name, args):
        assert name == "read_file"
        assert args == {"path": "/tmp/demo.txt"}
        return "demo contents"

    monkeypatch.setattr(chat_router, "_gather_brief_context", fake_brief)
    monkeypatch.setattr(chat_router, "_call_openrouter", fake_call_openrouter)
    monkeypatch.setattr(chat_router, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(chat_router, "_log_conversation", lambda *args, **kwargs: None)

    client = _chat_client()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "profile_id": "codex_operator",
            "messages": [{"role": "user", "content": "inspect the canonical path"}],
        },
    ) as response:
        assert response.status_code == 200
        payloads = _read_sse_payloads(response)

    first_payload = next(
        payload
        for payload in payloads
        if isinstance(payload, dict) and "session_id" in payload
    )
    assert first_payload["session_id"] == "dash-test-session"
    assert any(
        isinstance(payload, dict)
        and payload.get("tool_call", {}).get("name") == "read_file"
        for payload in payloads
    )
    assert any(
        isinstance(payload, dict) and payload.get("content") == "Patch complete."
        for payload in payloads
    )

    with client.websocket_connect("/ws/chat/session/dash-test-session") as websocket:
        snapshot = websocket.receive_json()

        assert snapshot["event"] == "chat_snapshot"
        assert snapshot["session_id"] == "dash-test-session"
        replay_events = [item["event"] for item in snapshot["events"]]
        assert replay_events[:4] == [
            "chat_session_ready",
            "chat_user_turn",
            "chat_tool_call",
            "chat_tool_result",
        ]
        assert "chat_assistant_turn" in replay_events
        assert replay_events[-1] == "chat_done"

        first_replayed = websocket.receive_json()
        assert first_replayed["event"] == snapshot["events"][0]["event"]
