"""Hermetic tests for the canonical model-status projection."""

from __future__ import annotations

import json
import time
from pathlib import Path

from dharma_swarm import key_oracle
from dharma_swarm.model_status import (
    floor_model_status,
    save_profile,
    top_floor_models_for_dashboard,
)


def _row(glyph: str, *, status: str = "live", http: str = "200") -> dict[str, str]:
    return {
        "glyph": glyph,
        "status": status,
        "http": http,
        "env_var": "SAFE_TEST_ENV",
    }


def _write_status(home: Path, rows: dict[str, dict[str, str]]) -> None:
    target = home / ".dharma"
    target.mkdir(parents=True, exist_ok=True)
    (target / "keys_status.json").write_text(
        json.dumps({"last_test_ts": time.time(), "rows": rows}),
        encoding="utf-8",
    )


def test_floor_status_projection_uses_dkeys_rows_without_live_calls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "claude_code": _row("✓"),
            "codex (openai-pro)": _row("✓", status="oauth present"),
            "openai": _row("✓"),
            "ollama_cloud": _row("✓"),
            "openrouter": _row("✗", status="HTTP 404", http="404"),
        },
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")

    assert projection.oracle_state == "fresh"
    assert len(projection.models) == 12
    assert all(model.lane == "floor" for model in projection.models)
    by_id = {model.id: model for model in projection.models}
    assert by_id["claude-opus-4.8"].available is True
    assert by_id["kimi-k2.6"].available is True
    assert by_id["gpt-5-codex"].available is False
    assert by_id["gpt-5-codex"].unavailable_reason == "provider_dead"
    assert by_id["gpt-5-codex"].verification.status == "unverified"


def test_missing_key_status_is_unverified_not_advertised_callable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")

    assert projection.oracle_state == "unknown"
    assert projection.live_providers is None
    assert all(model.available is False for model in projection.models)
    assert {model.status for model in projection.models} == {"unverified"}
    assert {model.unavailable_reason for model in projection.models} == {"key_status_unknown"}


def test_dashboard_projection_applies_profile_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path, {"ollama_cloud": _row("✓")})
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    profile_path = tmp_path / "profiles.json"

    saved = save_profile(
        "kimi-k2.6",
        custom_label="Kimi Floor",
        short_name="Kimi",
        path=profile_path,
    )
    rows = top_floor_models_for_dashboard(profiles_path=profile_path)
    kimi = next(row for row in rows if row["id"] == "kimi-k2.6")

    assert saved == {"custom_label": "Kimi Floor", "short_name": "Kimi"}
    assert kimi["ui_label"] == "Kimi Floor"
    assert kimi["short_name"] == "Kimi"
