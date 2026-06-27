"""Verifier for the /holon/{name}/chat route (U2). TestClient + the criterion-#3
sentinel (the route must NEVER call _agentic_stream). Mounts the router on a minimal app."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm import holon_bridge
from dharma_swarm.models import ProviderType
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
        json.dumps({"model": "claude-opus-4-8", "provider": "openai"})
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


def test_holon_chat_refuses_agentic_subprocess_provider(tmp_path, monkeypatch):
    d = tmp_path / "codex_composer" / "prompt_variants"
    d.mkdir(parents=True)
    (tmp_path / "codex_composer" / "identity.json").write_text(
        json.dumps({"model": "gpt-5.5", "provider": "codex"}),
        encoding="utf-8",
    )
    (d / "active.txt").write_text("I am codex_composer.", encoding="utf-8")
    monkeypatch.setattr(holon_bridge, "AGENTS_ROOT", tmp_path)

    app = FastAPI()
    app.include_router(holon_router.router)

    r = TestClient(app).post("/holon/codex_composer/chat", json={"message": "hi"})

    assert r.status_code == 409
    assert "no safe non-agentic provider" in r.json()["detail"]


def test_holon_dialogue_provider_allows_explicit_safe_override(monkeypatch):
    class SafeProvider:
        pass

    def fake_resolve(provider_type, *, model=None, env=None, **kwargs):
        assert provider_type == ProviderType.OLLAMA
        assert model == "llama3.2:latest"
        return SimpleNamespace(
            provider=ProviderType.OLLAMA,
            default_model=model,
            available=True,
        )

    def fake_create(config):
        provider = SafeProvider()
        provider.runtime_provider_type = config.provider.value
        provider.runtime_default_model = config.default_model
        return provider

    import dharma_swarm.runtime_provider as runtime_provider

    monkeypatch.setattr(runtime_provider, "resolve_runtime_provider_config", fake_resolve)
    monkeypatch.setattr(runtime_provider, "create_runtime_provider", fake_create)
    holon = holon_bridge.RunningHolon(
        name="codex_composer",
        model="gpt-5.5",
        system_prompt="I am codex_composer.",
        provider_type="codex",
        identity={"dialogue_provider": "ollama", "dialogue_model": "llama3.2:latest"},
    )

    provider = holon_bridge.get_holon_dialogue_provider(holon, env={})

    assert provider.runtime_provider_type == "ollama"
    assert provider.runtime_default_model == "llama3.2:latest"
    assert provider.holon_dialogue_provider_override is True


def test_holon_chat_threads_history(client, monkeypatch):
    """Multi-turn continuity: prior history must flow through to the model (talk-as-itself)."""
    seen: dict = {}

    class RecordingProvider:
        runtime_provider_type = "stub_safe"
        runtime_default_model = "stub-dialogue-model"

        async def stream(self, request):
            seen["messages"] = list(request.messages)
            seen["system"] = request.system
            seen["model"] = request.model
            yield "ok"

    monkeypatch.setattr(holon_bridge, "get_holon_provider", lambda h, env=None: RecordingProvider())
    hist = [{"role": "user", "content": "earlier Q"}, {"role": "assistant", "content": "earlier A"}]
    client.post("/holon/opus_composer/chat", json={"message": "follow-up", "history": hist})
    msgs = seen["messages"]
    assert msgs[0]["content"] == "earlier Q"      # history threaded, oldest first
    assert msgs[-1]["content"] == "follow-up"     # current message appended last
    assert seen["model"] == "stub-dialogue-model"
    assert "Current LivingDock Context" in seen["system"]
    assert "policy_ceiling: read_only_dialogue_no_privileged_action" in seen["system"]


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
    assert "error" in r.text             # error surfaced, not a 500
    assert "provider error" in r.text
    assert "exploded" not in r.text      # raw provider details stay server-side


def test_holon_chat_logs_conversation(client, monkeypatch):
    logged: list = []
    monkeypatch.setattr(
        "api.routers.holon.log_exchange",
        lambda role, content, **k: logged.append((role, k.get("interface"))),
    )
    client.post("/holon/opus_composer/chat", json={"message": "hi"})
    assert ("user", "holon") in logged
    assert ("assistant", "holon") in logged


def test_holon_chat_writes_living_dock_conversation_receipt(client, tmp_path):
    r = client.post("/holon/opus_composer/chat", json={"message": "hi"})

    assert r.status_code == 200
    ledger = tmp_path / "opus_composer" / "talk_receipts.jsonl"
    strict_dir = tmp_path / "opus_composer" / "dialogue" / "conversation_receipts"
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert row["schema_version"] == "dharma.holon_conversation_receipt.v1"
    assert row["policy_ceiling"] == "read_only_dialogue_no_privileged_action"
    assert row["protected_action_claim"] is False
    assert strict_dir.exists()
    assert list(strict_dir.glob("*.json"))


def test_holon_chat_history_reads_living_dock_receipts(client):
    client.post("/holon/opus_composer/chat", json={"message": "hi"})

    r = client.get("/holon/opus_composer/chat/history")

    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "dharma.holon_chat_history.v1"
    assert body["receipt_count"] == 1
    assert body["receipts"][0]["holon"] == "opus_composer"
