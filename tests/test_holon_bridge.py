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
from dharma_swarm.holon_bridge import load_holon, guard_outcome_claim
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
