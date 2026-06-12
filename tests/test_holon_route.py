"""Verifier for the /holon/{name}/chat route (U2). TestClient + the criterion-#3
sentinel (the route must NEVER call _agentic_stream). Mounts the router on a minimal app."""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm import holon_bridge
from api.routers import holon as holon_router


class _StubProvider:
    async def stream(self, request):
        yield "Hello, "
        yield "I am opus_composer."


@pytest.fixture
def client(tmp_path, monkeypatch):
    d = tmp_path / "opus_composer" / "prompt_variants"
    d.mkdir(parents=True)
    (tmp_path / "opus_composer" / "identity.json").write_text(
        json.dumps({"model": "claude-opus-4-8", "provider": "anthropic_max"})
    )
    (d / "active.txt").write_text("I am opus_composer.")
    monkeypatch.setattr(holon_bridge, "AGENTS_ROOT", tmp_path)
    monkeypatch.setattr(holon_bridge, "get_holon_provider", lambda h, env=None: _StubProvider())
    app = FastAPI()
    app.include_router(holon_router.router)
    return TestClient(app)


def test_holon_chat_streams_own_model(client):
    r = client.post("/holon/opus_composer/chat", json={"message": "hi"})
    assert r.status_code == 200
    body = r.text
    assert "claude-opus-4-8" in body          # routed through the holon's OWN model
    assert "Hello, " in body and "I am opus_composer." in body
    assert '"done": true' in body.lower()


def test_holon_chat_does_not_call_agentic_stream(client, monkeypatch):
    """Criterion #3: the holon route must not delegate to the operator's agentic stream."""
    import api.routers.chat as chat

    def _boom(*a, **k):
        raise AssertionError("_agentic_stream must NOT be called by the holon route")

    monkeypatch.setattr(chat, "_agentic_stream", _boom, raising=False)
    monkeypatch.setattr(chat, "_subprocess_agentic_stream", _boom, raising=False)
    r = client.post("/holon/opus_composer/chat", json={"message": "hi"})
    assert r.status_code == 200  # no sentinel fired => route is independent


def test_holon_chat_404_unknown(client):
    r = client.post("/holon/nonexistent/chat", json={"message": "hi"})
    assert r.status_code == 404


def test_holon_chat_threads_history(client, monkeypatch):
    """Multi-turn continuity: prior history must flow through to the model (talk-as-itself)."""
    seen: dict = {}

    class RecordingProvider:
        async def stream(self, request):
            seen["messages"] = list(request.messages)
            yield "ok"

    monkeypatch.setattr(holon_bridge, "get_holon_provider", lambda h, env=None: RecordingProvider())
    hist = [{"role": "user", "content": "earlier Q"}, {"role": "assistant", "content": "earlier A"}]
    client.post("/holon/opus_composer/chat", json={"message": "follow-up", "history": hist})
    msgs = seen["messages"]
    assert msgs[0]["content"] == "earlier Q"      # history threaded, oldest first
    assert msgs[-1]["content"] == "follow-up"     # current message appended last


def test_holon_chat_surfaces_provider_error(client, monkeypatch):
    """A provider failure mid-stream must surface as an error SSE, not crash the connection."""
    class BoomProvider:
        async def stream(self, request):
            yield "partial "
            raise RuntimeError("provider exploded")

    monkeypatch.setattr(holon_bridge, "get_holon_provider", lambda h, env=None: BoomProvider())
    r = client.post("/holon/opus_composer/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert "partial " in r.text          # partial content still streamed
    assert "error" in r.text and "exploded" in r.text  # error surfaced, not a 500


def test_holon_chat_logs_conversation(client, monkeypatch):
    logged: list = []
    monkeypatch.setattr(
        "api.routers.holon.log_exchange",
        lambda role, content, **k: logged.append((role, k.get("interface"))),
    )
    client.post("/holon/opus_composer/chat", json={"message": "hi"})
    assert ("user", "holon") in logged
    assert ("assistant", "holon") in logged
