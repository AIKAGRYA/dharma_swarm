"""Tests for scripts/check_provider_credits.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import check_provider_credits as cpc


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
