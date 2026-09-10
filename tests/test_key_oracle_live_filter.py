"""Tests for the live-key oracle and the providers.py dead-key chain filter.

Covers the Step-1 spec contract:
  - dead-key providers pruned from the chain
  - all-dead falls back to the UNFILTERED chain (never a self-inflicted outage)
  - stale status file => oracle returns None => env-presence behaviour (no filter)
  - oauth rows count as live
  - 429 (~) rows are pruned-but-recoverable (not live)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from dharma_swarm import key_oracle
from dharma_swarm.key_oracle import live_providers
from dharma_swarm.models import ProviderType
from dharma_swarm.provider_policy import ProviderRouteDecision, RoutePath
from dharma_swarm.providers import ModelRouter


def _write_status(home: Path, rows: dict, *, age_s: float = 0.0) -> None:
    target = home / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_test_ts": time.time() - age_s,
        "rows": rows,
    }
    (target / "keys_status.json").write_text(json.dumps(payload), encoding="utf-8")


def _row(glyph: str, *, status: str = "", env_var: str = "X", present: bool = True) -> dict:
    return {
        "glyph": glyph,
        "status": status,
        "env_var": env_var,
        "key_present": present,
    }


def _row_with_name(name: str, glyph: str, *, status: str = "", env_var: str = "X", present: bool = True) -> dict:
    row = _row(glyph, status=status, env_var=env_var, present=present)
    row["name"] = name
    return row


# ---------------------------------------------------------------------------
# key_oracle.live_providers
# ---------------------------------------------------------------------------


def test_live_providers_oauth_counts_live(tmp_path: Path, monkeypatch) -> None:
    # Host-detected keyless providers (local/ollama/claude_code smoke) are
    # intentionally environment-dependent; this test isolates oauth/key rows.
    # Without this, _detect_keyless_live's claude_code branch shells out to a
    # REAL `claude -p ...` subprocess whenever the claude binary is on PATH
    # (true in this container, since Claude Code itself is `claude`) — a
    # live network call costing ~9s (WP-0D suite-context timeout) instead of
    # the fast, hermetic check this test's own docstring already promised.
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {
            "claude_code": _row("✓", status="Max plan (keychain oauth)"),
            "codex (openai-pro)": _row("✓", status="oauth present (chatgpt)"),
        },
    )
    live = live_providers(home=tmp_path)
    assert live is not None
    # ANTHROPIC liveness derives from the claude_code oauth row.
    assert "anthropic" in live
    assert "claude_code" in live
    assert "codex" in live


def test_live_providers_accepts_current_dkeys_array_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    target = tmp_path / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_test_ts": time.time(),
        "rows": [
            _row_with_name("groq", "✓", status="live"),
            _row_with_name("openrouter", "✗", status="HTTP 404"),
        ],
    }
    (target / "keys_status.json").write_text(json.dumps(payload), encoding="utf-8")

    live = live_providers(home=tmp_path)

    assert live is not None
    assert "groq" in live
    assert "openrouter" not in live
    assert "openrouter_free" not in live


def test_live_providers_429_is_pruned(tmp_path: Path, monkeypatch) -> None:
    """A 429 (~) row is NOT live (rate-limited; pruned-but-recoverable)."""
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {
            "gemini": _row("~", status="HTTP 429 rate-limited"),
            "openai": _row("✓", status="live"),
        },
    )
    live = live_providers(home=tmp_path)
    assert live is not None
    assert "google_ai" not in live  # gemini -> google_ai mapping, pruned
    assert "openai" in live


def test_live_providers_dead_glyphs_not_live(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {
            "openrouter": _row("✗", status="HTTP 404"),
            "groq": _row("✗", status="HTTP 403 auth"),
            "minimax": _row("·", status="no key", present=False),
            "xai": _row("$", status="valid · funds=0"),
            "deepseek": _row("✓", status="live"),
        },
    )
    live = live_providers(home=tmp_path)
    assert live is not None
    assert "openrouter" not in live
    assert "openrouter_free" not in live
    assert "groq" not in live
    assert "minimax" not in live
    assert "xai" not in live
    assert "deepseek" in live


def test_live_providers_all_dead_returns_real_empty_not_none(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """All keys dead is a VALID answer (empty-but-for-keyless), not None."""
    # Keep the assertion about keyed-provider semantics independent of host
    # tools. A developer machine with Ollama installed legitimately contributes
    # {"local", "ollama"} to keyless liveness.
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: {"local"})
    _write_status(
        tmp_path,
        {
            "openrouter": _row("✗", status="HTTP 404"),
            "anthropic": _row("✗", status="HTTP 400"),
        },
    )
    live = live_providers(home=tmp_path)
    assert live is not None  # fresh + parseable => a real set, never None
    # claude_code row absent => anthropic NOT derivable as live.
    assert "anthropic" not in live
    assert "openrouter" not in live
    # keyless still live; this is a real set, distinguishable from None.
    assert live == {"local"}


# ---- fail-open paths (the load-bearing contract) ----


def test_live_providers_missing_file_returns_none(tmp_path: Path) -> None:
    # No keys_status.json written at all.
    assert live_providers(home=tmp_path) is None


def test_live_providers_stale_returns_none(tmp_path: Path, monkeypatch) -> None:
    """Stale (age > ttl) => None => callers keep env-presence behaviour."""
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {"openai": _row("✓", status="live")},
        age_s=10_000,  # well beyond default 900s ttl
    )
    assert live_providers(ttl_s=900, home=tmp_path) is None
    # but a generous ttl makes the same file fresh again
    fresh = live_providers(ttl_s=100_000, home=tmp_path)
    assert fresh is not None
    assert "openai" in fresh


def test_stale_oracle_warning_is_emitted_once_per_observation(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_status(
        tmp_path,
        {"openai": _row("✓", status="live")},
        age_s=10_000,
    )
    caplog.set_level("WARNING", logger="dharma_swarm.key_oracle")

    assert live_providers(ttl_s=900, home=tmp_path, now=time.time()) is None
    assert live_providers(ttl_s=900, home=tmp_path, now=time.time() + 30) is None

    warnings = [
        record
        for record in caplog.records
        if "keys_status.json is stale" in record.getMessage()
    ]
    assert len(warnings) == 1


def test_live_providers_malformed_returns_none(tmp_path: Path) -> None:
    target = tmp_path / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    (target / "keys_status.json").write_text("{ not json", encoding="utf-8")
    assert live_providers(home=tmp_path) is None


def test_live_providers_missing_rows_returns_none(tmp_path: Path) -> None:
    target = tmp_path / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    (target / "keys_status.json").write_text(
        json.dumps({"last_test_ts": time.time()}), encoding="utf-8"
    )
    assert live_providers(home=tmp_path) is None


def test_live_providers_future_timestamp_treated_fresh(tmp_path: Path, monkeypatch) -> None:
    """Clock skew (future ts) must not be read as 'stale'."""
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {"openai": _row("✓", status="live")},
        age_s=-5000,  # timestamp in the future
    )
    live = live_providers(home=tmp_path)
    assert live is not None
    assert "openai" in live


# ---------------------------------------------------------------------------
# ModelRouter._prune_dead_key_providers (the chain filter)
# ---------------------------------------------------------------------------


def _patch_oracle(monkeypatch, value):
    monkeypatch.setattr(
        "dharma_swarm.providers.live_providers", lambda *a, **k: value
    )


def test_prune_dead_key_dropped(monkeypatch) -> None:
    chain = [ProviderType.OPENROUTER, ProviderType.OPENAI, ProviderType.OLLAMA]
    # openrouter dead; openai + ollama live.
    _patch_oracle(monkeypatch, {"openai", "ollama", "local"})
    out = ModelRouter._prune_dead_key_providers(chain)
    assert ProviderType.OPENROUTER not in out
    assert out == [ProviderType.OPENAI, ProviderType.OLLAMA]


def test_prune_all_dead_keeps_unfiltered(monkeypatch) -> None:
    """If every routed provider is dead-keyed, keep the UNFILTERED chain."""
    chain = [ProviderType.OPENROUTER, ProviderType.ANTHROPIC]
    # live set excludes both => filtering would empty the chain.
    _patch_oracle(monkeypatch, {"openai", "local"})
    out = ModelRouter._prune_dead_key_providers(chain)
    assert out == chain  # never a self-inflicted outage


def test_prune_oracle_none_keeps_unfiltered(monkeypatch) -> None:
    """Stale/missing oracle (None) => env-presence behaviour, no filtering."""
    chain = [ProviderType.OPENROUTER, ProviderType.OPENAI]
    _patch_oracle(monkeypatch, None)
    out = ModelRouter._prune_dead_key_providers(chain)
    assert out == chain


def test_prune_injected_oracle_none_keeps_unfiltered() -> None:
    chain = [ProviderType.OPENROUTER, ProviderType.OPENAI]
    out = ModelRouter._prune_dead_key_providers(
        chain,
        live_provider=lambda: None,
    )
    assert out == chain


def test_provider_chain_uses_injected_oracle() -> None:
    router = ModelRouter(
        {
            ProviderType.OPENROUTER: object(),
            ProviderType.OPENAI: object(),
        },
        key_liveness_provider=lambda: {"openai", "local"},
    )
    decision = ProviderRouteDecision(
        path=RoutePath.REFLEX,
        selected_provider=ProviderType.OPENROUTER,
        selected_model_hint=None,
        fallback_providers=[ProviderType.OPENAI],
        fallback_model_hints=[],
        confidence=1.0,
        requires_human=False,
        reasons=["test"],
    )

    out = router._provider_chain(decision)

    assert out == [ProviderType.OPENAI]


def test_prune_oracle_raises_keeps_unfiltered(monkeypatch) -> None:
    """The oracle must never take down routing."""
    def _boom(*a, **k):
        raise RuntimeError("oracle exploded")

    monkeypatch.setattr("dharma_swarm.providers.live_providers", _boom)
    chain = [ProviderType.OPENAI, ProviderType.OPENROUTER]
    out = ModelRouter._prune_dead_key_providers(chain)
    assert out == chain


def test_prune_empty_chain_is_noop(monkeypatch) -> None:
    _patch_oracle(monkeypatch, {"openai"})
    assert ModelRouter._prune_dead_key_providers([]) == []


def test_prune_429_provider_dropped(monkeypatch, tmp_path: Path) -> None:
    """End-to-end via the real oracle: a 429 (~) provider is pruned."""
    monkeypatch.setattr("dharma_swarm.key_oracle._detect_keyless_live", lambda: set())
    _write_status(
        tmp_path,
        {
            "gemini": _row("~", status="HTTP 429 rate-limited"),
            "openai": _row("✓", status="live"),
        },
    )
    # Drive the real oracle against tmp HOME by monkeypatching Path.home.
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    chain = [ProviderType.GOOGLE_AI, ProviderType.OPENAI]
    out = ModelRouter._prune_dead_key_providers(chain)
    assert ProviderType.GOOGLE_AI not in out
    assert out == [ProviderType.OPENAI]
