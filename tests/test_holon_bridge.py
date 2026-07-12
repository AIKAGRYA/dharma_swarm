"""Verifier for the read-only sovereign holon bridge (Step 2, first brick).

Runnable form of the hardened acceptance criteria from 02_FIRST_BRICK_SPEC.md, plus
regression tests for the defects an adversarial detonation found on 2026-06-09:
  - provider_type must be a VALID lowercase ProviderType value (was uppercase → would crash)
  - read-only holon_reply must STREAM and must NOT refuse natural conversational language
`pytest tests/test_holon_bridge.py` exit-0 is the longrun verifyCmd.
"""
from __future__ import annotations

import json

import pytest

from dharma_swarm import holon_bridge
from dharma_swarm.holon_bridge import (
    HolonDialogueProviderError,
    build_livingdock_dialogue_context,
    guard_outcome_claim,
    load_holon,
)
from dharma_swarm.models import LLMRequest


def _make_agent(tmp_path, name="opus_composer", model="claude-opus-4-8",
                provider="anthropic_max", active="I am opus_composer.", with_active=True):
    d = tmp_path / name
    (d / "prompt_variants").mkdir(parents=True)
    (d / "identity.json").write_text(
        json.dumps({"model": model, "provider": provider, "system_prompt": "FALLBACK PROMPT"})
    )
    if with_active:
        (d / "prompt_variants" / "active.txt").write_text(active, encoding="utf-8")
    return tmp_path


# --- Criterion 1: load_holon system_prompt == active.txt byte-for-byte (+ fallback) ---

def test_load_holon_golden(tmp_path):
    root = _make_agent(tmp_path, active="I am opus_composer, the composer.")
    h = load_holon("opus_composer", agents_root=root)
    assert h.system_prompt == "I am opus_composer, the composer."
    assert h.model == "claude-opus-4-8"
    assert h.provider_type == "claude_code"  # anthropic_max coerced to a VALID enum value


def test_load_holon_fallback_when_no_active(tmp_path, caplog):
    root = _make_agent(tmp_path, with_active=False)
    with caplog.at_level("INFO"):
        h = load_holon("opus_composer", agents_root=root)
    assert h.system_prompt == "FALLBACK PROMPT"
    assert any("no active.txt" in r.message for r in caplog.records)


def test_load_holon_missing_agent_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_holon("does_not_exist", agents_root=tmp_path)


def test_load_holon_malformed_identity_raises_clean(tmp_path):
    d = tmp_path / "broken"
    (d / "prompt_variants").mkdir(parents=True)
    (d / "identity.json").write_text("{not valid json")
    with pytest.raises(ValueError, match="malformed identity.json"):
        load_holon("broken", agents_root=tmp_path)


def test_load_holon_strips_bom(tmp_path):
    d = tmp_path / "bomtest"
    (d / "prompt_variants").mkdir(parents=True)
    (d / "identity.json").write_text(json.dumps({"model": "m", "provider": "anthropic_max"}))
    (d / "prompt_variants" / "active.txt").write_bytes(b"\xef\xbb\xbfI am the agent.")
    h = load_holon("bomtest", agents_root=tmp_path)
    assert h.system_prompt == "I am the agent."  # BOM stripped, no U+FEFF


# --- Regression: provider_type must be a VALID ProviderType (the enum bug) ---

def test_provider_type_is_valid_enum(tmp_path):
    from dharma_swarm.runtime_provider import ProviderType
    root = _make_agent(tmp_path)  # provider=anthropic_max
    h = load_holon("opus_composer", agents_root=root)
    assert h.provider_type == "claude_code"
    assert ProviderType(h.provider_type) == ProviderType.CLAUDE_CODE  # would have caught the crash


def test_unknown_provider_falls_back_to_valid_enum(tmp_path):
    from dharma_swarm.runtime_provider import ProviderType
    root = _make_agent(tmp_path, provider="totally_made_up")
    h = load_holon("opus_composer", agents_root=root)
    ProviderType(h.provider_type)  # must not raise — falls back to claude_code


# --- Integration: the real registered opus_composer (skips on machines without it) ---

def test_load_holon_real_opus_composer():
    from pathlib import Path
    if not (Path.home() / ".dharma" / "agents" / "opus_composer" / "identity.json").exists():
        pytest.skip("opus_composer not registered on this machine")
    h = load_holon("opus_composer")
    assert h.model == "claude-opus-4-8"
    assert h.provider_type == "claude_code"
    assert len(h.system_prompt) > 0


# --- U1: get_holon_provider wires name -> live provider (no network, just instantiation) ---

def test_get_holon_provider_returns_real_provider(tmp_path):
    from dharma_swarm.providers import ClaudeCodeProvider
    root = _make_agent(tmp_path)  # provider anthropic_max -> claude_code
    h = load_holon("opus_composer", agents_root=root)
    provider = holon_bridge.get_holon_provider(h)
    assert hasattr(provider, "stream") and hasattr(provider, "complete")
    assert isinstance(provider, ClaudeCodeProvider)  # claude_code -> ClaudeCodeProvider (Max plan)


def test_dialogue_provider_refuses_agentic_owner_without_safe_override(tmp_path):
    root = _make_agent(tmp_path, provider="anthropic_max")
    h = load_holon("opus_composer", agents_root=root)

    with pytest.raises(HolonDialogueProviderError, match="agentic and unsafe"):
        holon_bridge.get_holon_dialogue_provider(h, env={})


def test_dialogue_provider_checks_anthropic_transport_before_factory(tmp_path, monkeypatch):
    from dharma_swarm import runtime_provider

    root = _make_agent(tmp_path, provider="anthropic")
    h = load_holon("opus_composer", agents_root=root)
    monkeypatch.setattr(runtime_provider, "_resolve_cli_binary", lambda _name: "/fixture/claude")

    def fail_if_created(_config):
        pytest.fail("unsafe subprocess provider was instantiated before the dialogue gate")

    monkeypatch.setattr(runtime_provider, "create_runtime_provider", fail_if_created)
    with pytest.raises(HolonDialogueProviderError, match="claude_code.*unsafe"):
        holon_bridge.get_holon_dialogue_provider(h, env={})


def test_dialogue_provider_safe_override_resolves_runtime_provider(tmp_path, monkeypatch):
    from dharma_swarm import runtime_provider
    from dharma_swarm.models import ProviderType
    from dharma_swarm.runtime_provider import RuntimeProviderConfig

    root = _make_agent(tmp_path, provider="anthropic_max")
    h = load_holon("opus_composer", agents_root=root)
    resolved: dict[str, object] = {}

    def fake_resolve(ptype, *, model=None, env=None, **kwargs):
        resolved["provider"] = ptype
        resolved["model"] = model
        return RuntimeProviderConfig(provider=ptype, default_model=model, available=True)

    class StubDialogueProvider:
        runtime_provider_type = "ollama"
        runtime_default_model = "dialogue-model"

    monkeypatch.setattr(runtime_provider, "resolve_runtime_provider_config", fake_resolve)
    monkeypatch.setattr(runtime_provider, "create_runtime_provider", lambda config: StubDialogueProvider())

    provider = holon_bridge.get_holon_dialogue_provider(
        h,
        env={
            "DHARMA_HOLON_DIALOGUE_PROVIDER": "ollama",
            "DHARMA_HOLON_DIALOGUE_MODEL": "dialogue-model",
        },
    )

    assert isinstance(provider, StubDialogueProvider)
    assert getattr(provider, "holon_dialogue_provider_override") is True
    assert resolved == {"provider": ProviderType.OLLAMA, "model": "dialogue-model"}


def test_dialogue_provider_refuses_unsafe_override(tmp_path):
    root = _make_agent(tmp_path, provider="ollama")
    h = load_holon("opus_composer", agents_root=root)

    with pytest.raises(HolonDialogueProviderError, match="unsafe read-only dialogue provider override"):
        holon_bridge.get_holon_dialogue_provider(
            h,
            env={"DHARMA_HOLON_DIALOGUE_PROVIDER": "codex"},
        )


def test_livingdock_context_is_bounded_and_evidence_backed(tmp_path):
    root = _make_agent(tmp_path, provider="ollama")
    agent_dir = root / "opus_composer"
    (agent_dir / "living_agent.json").write_text(
        json.dumps({"agent_uid": "opus_composer", "wake_loop_active": False, "status": "idle"}),
        encoding="utf-8",
    )
    (agent_dir / "dialogue").mkdir()
    (agent_dir / "dialogue" / "operator_sessions.jsonl").write_text(
        "\n".join([json.dumps({"event": "session", "note": "bounded context " + ("x" * 500)}) for _ in range(5)]),
        encoding="utf-8",
    )
    h = load_holon("opus_composer", agents_root=root)

    ctx = build_livingdock_dialogue_context(h, agents_root=root, max_chars=420)

    assert "read_only_dialogue_no_privileged_action" in ctx.content
    assert "protected_actions_allowed: false" in ctx.content
    assert len(ctx.content) <= 420
    assert "truncated" in ctx.content
    assert str(agent_dir / "identity.json") in ctx.evidence_paths
    assert str(agent_dir / "living_agent.json") in ctx.evidence_paths


def test_holon_talk_declared_first_uses_identity_model(tmp_path, monkeypatch):
    """The explicit declared-first CLI mode must preserve the identity-declared model."""
    from dharma_swarm.terminal_commands import _holons as holon_talk

    root = _make_agent(tmp_path, model="identity-model", provider="ollama")
    h = load_holon("opus_composer", agents_root=root)
    sentinel_provider = object()
    recorded: dict[str, str] = {}

    def _fake_get_holon_provider(holon):
        recorded["name"] = holon.name
        recorded["model"] = holon.model
        recorded["provider_type"] = holon.provider_type
        return sentinel_provider

    monkeypatch.setattr(holon_talk, "get_holon_provider", _fake_get_holon_provider)

    provider, provider_name, model, mode = holon_talk._resolve_provider(h, "declared-first")

    assert provider is sentinel_provider
    assert provider_name == "ollama"
    assert model == "identity-model"
    assert mode == "declared-first"
    assert recorded == {
        "name": "opus_composer",
        "model": "identity-model",
        "provider_type": "ollama",
    }


def test_holon_talk_free_first_walks_canonical_chain(monkeypatch):
    """free-first must use preferred_runtime_provider_configs and skip the claude_code door."""
    from types import SimpleNamespace

    from dharma_swarm.runtime_provider import ProviderType
    from dharma_swarm.terminal_commands import _holons as holon_talk

    configs = [
        SimpleNamespace(provider=ProviderType.CLAUDE_CODE, default_model="claude-opus-4-8"),
        SimpleNamespace(provider=ProviderType.OLLAMA, default_model="glm-5:cloud"),
        SimpleNamespace(provider=ProviderType.NVIDIA_NIM, default_model="llama-3.3-70b"),
    ]
    monkeypatch.setattr(holon_talk, "preferred_runtime_provider_configs", lambda: configs)
    sentinel = object()
    created: list = []

    def _fake_create(cfg):
        created.append(cfg.provider)
        return sentinel

    monkeypatch.setattr(holon_talk, "create_runtime_provider", _fake_create)

    provider, pname, model = holon_talk._resolve_free_provider()

    assert provider is sentinel
    assert pname == "ollama"  # first non-claude entry of the canonical chain
    assert model == "glm-5:cloud"
    assert created == [ProviderType.OLLAMA]  # claude_code skipped, never instantiated


async def test_holon_talk_declared_failure_falls_back_with_receipt_provenance(
    tmp_path, monkeypatch, capsys
):
    """Declared-route failure text must fall back once and record fallback_from in the receipt."""
    from dharma_swarm.terminal_commands import _holons as holon_talk

    monkeypatch.setenv("HOME", str(tmp_path))
    root = _make_agent(tmp_path / "agents-root")
    holon = load_holon("opus_composer", agents_root=root)
    monkeypatch.setattr(holon_talk, "load_holon", lambda name: holon)

    class FailingProvider:
        async def stream(self, request):
            yield "Credit balance is too low"

    class GoodProvider:
        async def stream(self, request):
            yield "I am opus_composer; my telos is dharma."

    monkeypatch.setattr(
        holon_talk,
        "_resolve_declared_provider",
        lambda h: (FailingProvider(), "claude_code", "claude-opus-4-8"),
    )
    free_calls: list[int] = []

    def _fake_free():
        free_calls.append(1)
        return GoodProvider(), "ollama", "glm-5:cloud"

    monkeypatch.setattr(holon_talk, "_resolve_free_provider", _fake_free)

    rc = await holon_talk.talk("opus_composer", "who are you?", routing_mode="declared-first")

    assert rc == 0
    assert free_calls == [1]  # exactly one fallback, no double fallback
    rpath = tmp_path / ".dharma" / "agents" / "opus_composer" / "talk_receipts.jsonl"
    receipt = json.loads(rpath.read_text(encoding="utf-8").splitlines()[-1])
    assert receipt["routing_mode"] == "declared-first"
    assert receipt["model"] == "ollama/glm-5:cloud"
    assert receipt["fallback_from"] == "claude_code/claude-opus-4-8"
    assert "opus_composer" in receipt["reply"]


def test_holon_script_wrappers_export_package_runtime():
    """Source-tree script entry points remain compatible aliases."""
    from scripts import holon_run, holon_talk
    from dharma_swarm.terminal_commands import _holons

    assert holon_talk.talk is _holons.talk
    assert holon_talk._resolve_provider is _holons._resolve_provider
    assert holon_run.run is _holons.run
    assert holon_run._make_free_runner is _holons._make_free_runner


# --- Criterion 2: holon_reply routes through the holon's OWN model AND streams freely ---

async def test_stub_model_routing(tmp_path):
    root = _make_agent(tmp_path)
    h = load_holon("opus_composer", agents_root=root)
    recorded: dict = {}

    class StubProvider:
        async def stream(self, request: LLMRequest):
            recorded["model"] = request.model
            recorded["system"] = request.system
            recorded["is_llmrequest"] = isinstance(request, LLMRequest)
            yield "hello "
            yield "world"

    out = "".join([c async for c in holon_bridge.holon_reply(h, "hi", StubProvider())])
    assert recorded["is_llmrequest"] is True
    assert recorded["model"] == "claude-opus-4-8"  # the holon's OWN model, not a global default
    assert recorded["system"] == h.system_prompt
    assert out == "hello world"


async def test_holon_reply_can_include_livingdock_context_and_request_model(tmp_path):
    root = _make_agent(tmp_path)
    h = load_holon("opus_composer", agents_root=root)
    recorded: dict = {}

    class StubProvider:
        async def stream(self, request: LLMRequest):
            recorded["model"] = request.model
            recorded["system"] = request.system
            yield "ok"

    out = "".join([
        c
        async for c in holon_bridge.holon_reply(
            h,
            "hi",
            StubProvider(),
            livingdock_context="## Current LivingDock Context\nprotected_actions_allowed: false",
            request_model="dialogue-model",
        )
    ])

    assert out == "ok"
    assert recorded["model"] == "dialogue-model"
    assert "protected_actions_allowed: false" in recorded["system"]


async def test_holon_reply_streams_and_does_not_refuse_conversation(tmp_path):
    """Regression: read-only reply must STREAM token-by-token and must NOT refuse
    natural language containing words like 'created' (the detonation's category-error)."""
    root = _make_agent(tmp_path)
    h = load_holon("opus_composer", agents_root=root)

    class StubProvider:
        async def stream(self, request: LLMRequest):
            yield "I "
            yield "created a mental model — that's done."  # 'created'/'done' must flow freely

    chunks = [c async for c in holon_bridge.holon_reply(h, "analyze", StubProvider())]
    assert len(chunks) == 2  # streamed, not buffered into one
    assert "".join(chunks) == "I created a mental model — that's done."  # not refused


# --- guard_outcome_claim is a STEP-3 tool-boundary utility (still unit-tested) ---

def test_guard_blocks_unbacked_claim():
    claim = "I updated the file and it passed."
    refused = guard_outcome_claim(claim, has_artifact=False)
    assert refused.startswith("[refused")
    assert claim not in refused


def test_guard_allows_claim_with_artifact():
    txt = "I updated the file."
    assert guard_outcome_claim(txt, has_artifact=True) == txt
