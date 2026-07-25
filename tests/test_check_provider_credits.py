"""Tests for scripts/check_provider_credits.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import check_provider_credits as cpc
from dharma_swarm.api_keys import PROVIDER_API_KEY_ENV_KEYS


def test_redact_log_excerpt_masks_common_secret_shapes() -> None:
    text = (
        "openai quota exceeded bearer sk-proj-abc123456789 "
        "api_key=sk-or-v1-secretvalue token=abc123 "
        "https://user:password@example.test/path"
    )

    redacted = cpc.redact_log_excerpt(text, limit=500)

    assert "sk-proj-abc123456789" not in redacted
    assert "sk-or-v1-secretvalue" not in redacted
    assert "token=abc123" not in redacted
    assert "user:password@" not in redacted
    assert "[REDACTED" in redacted


def test_provider_registry_uses_canonical_api_key_registry() -> None:
    assert {
        provider: config["key_env"]
        for provider, config in cpc.PROVIDERS.items()
    } == PROVIDER_API_KEY_ENV_KEYS


def test_scan_logs_redacts_credit_error_excerpts(monkeypatch, tmp_path: Path) -> None:
    log_file = tmp_path / "provider.log"
    log_file.write_text(
        "openai quota exceeded bearer sk-proj-sensitive123 api_key=sk-or-v1-secret\n",
        encoding="utf-8",
    )
    results = {provider: {"credit_errors": []} for provider in cpc.PROVIDERS}
    monkeypatch.setattr(cpc, "LOG_DIRS", [tmp_path])

    cpc.scan_logs_for_credit_errors(results)

    [excerpt] = results["openai"]["credit_errors"]
    assert "sk-proj-sensitive123" not in excerpt
    assert "sk-or-v1-secret" not in excerpt
    assert "[REDACTED" in excerpt


def test_scan_logs_ignores_files_outside_window(monkeypatch, tmp_path: Path) -> None:
    import os as _os
    import time as _time

    stale = tmp_path / "stale.log"
    stale.write_text("openai insufficient credits\n", encoding="utf-8")
    week_ago = _time.time() - 7 * 24 * 3600
    _os.utime(stale, (week_ago, week_ago))

    fresh = tmp_path / "fresh.log"
    fresh.write_text("groq: you have reached your weekly usage limit\n", encoding="utf-8")

    results = {provider: {"credit_errors": []} for provider in cpc.PROVIDERS}
    monkeypatch.setattr(cpc, "LOG_DIRS", [tmp_path])

    cpc.scan_logs_for_credit_errors(results, window_hours=72.0)

    # the week-old 402-style line no longer poisons the narrative...
    assert results["openai"]["credit_errors"] == []
    # ...while the live wording that previously matched nothing now counts
    [excerpt] = results["groq"]["credit_errors"]
    assert "weekly usage limit" in excerpt


def test_new_exhaustion_wordings_match() -> None:
    for line in (
        "you have reached your weekly usage limit",
        "HTTP 429 too many requests",
        "RESOURCE_EXHAUSTED: quota",
    ):
        assert any(p.search(line) for p in cpc.CREDIT_ERROR_PATTERNS), line
