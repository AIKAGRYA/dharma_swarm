"""Hermetic tests for the canonical model-status projection."""

from __future__ import annotations

import json
import time
from pathlib import Path

from dharma_swarm import key_oracle
from dharma_swarm.model_status import (
    LIVE_CALL_MATRIX_PATH_ENV,
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
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")

    assert projection.oracle_state == "fresh"
    # 21 floor entries after the NVIDIA bleeding-edge NIM expansion (2026-06-18).
    assert len(projection.models) == 21
    assert all(model.lane == "floor" for model in projection.models)
    by_id = {model.id: model for model in projection.models}
    assert by_id["claude-opus-4.8"].available is True
    assert by_id["kimi-k2.6"].available is True
    assert by_id["gpt-5-codex"].available is False
    assert by_id["gpt-5-codex"].unavailable_reason == "provider_dead"
    assert by_id["gpt-5-codex"].verification.status == "unverified"


def test_live_call_matrix_failure_overrides_dkeys_live_route(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path, {"claude_code": _row("✓", status="oauth present")})
    live_matrix = tmp_path / "live_call_matrix.json"
    live_matrix.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "claude-opus-4.8",
                        "actual_live_call": {
                            "route": "claude_code:claude-opus-4.8",
                            "status": "failed",
                            "failure_class": "quota",
                            "reason": "Credit balance is too low",
                            "started_at": "2026-06-18T03:30:56Z",
                        },
                        "actual_live_calls": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(live_matrix))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    by_id = {model.id: model for model in projection.models}
    opus = by_id["claude-opus-4.8"]

    assert opus.available is False
    assert opus.status == "unavailable"
    assert opus.unavailable_reason == "quota"
    assert opus.route_statuses[0].status == "unavailable"
    assert opus.route_statuses[0].reason == "quota"
    assert opus.verification.status == "failed"
    assert opus.verification.error == "Credit balance is too low"


def test_live_call_matrix_rate_limit_does_not_poison_successful_route(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "ollama_cloud": _row("✓"),
            "nvidia_nim": _row("✓"),
        },
    )
    live_matrix = tmp_path / "live_call_matrix.json"
    live_matrix.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "minimax-m3",
                        "actual_live_calls": [
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "ok",
                                "probe": "pong_exact",
                                "started_at": "2026-06-18T03:41:11Z",
                            },
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "failed",
                                "failure_class": "rate_limited",
                                "probe": "json_schema",
                                "started_at": "2026-06-18T03:41:12Z",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(live_matrix))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    minimax = {model.id: model for model in projection.models}["minimax-m3"]
    by_route = {route.route: route for route in minimax.route_statuses}

    assert minimax.available is True
    assert "nvidia_nim:minimaxai/minimax-m3" in minimax.available_routes
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].status == "live_routable"
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].reason is None
    assert minimax.verification.status == "verified"


def test_live_call_matrix_rate_limited_route_stays_routable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "ollama_cloud": _row("✓"),
            "nvidia_nim": _row("✓"),
        },
    )
    live_matrix = tmp_path / "live_call_matrix.json"
    live_matrix.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "minimax-m3",
                        "actual_live_call": {
                            "route": "nvidia_nim:minimaxai/minimax-m3",
                            "status": "failed",
                            "failure_class": "rate_limited",
                            "reason": "NVIDIA NIM error 429: Too Many Requests",
                            "started_at": "2026-06-18T03:41:12Z",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(live_matrix))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    minimax = {model.id: model for model in projection.models}["minimax-m3"]
    by_route = {route.route: route for route in minimax.route_statuses}

    assert minimax.available is True
    assert "nvidia_nim:minimaxai/minimax-m3" in minimax.available_routes
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].status == "live_routable"
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].reason is None
    assert minimax.verification.status == "failed"
    assert minimax.verification.error == "NVIDIA NIM error 429: Too Many Requests"


def test_live_call_matrix_keeps_route_failed_when_later_case_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "ollama_cloud": _row("✓"),
            "nvidia_nim": _row("✓"),
        },
    )
    live_matrix = tmp_path / "live_call_matrix.json"
    live_matrix.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "minimax-m3",
                        "actual_live_calls": [
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "ok",
                                "probe": "pong_exact",
                                "started_at": "2026-06-18T03:41:11Z",
                            },
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "failed",
                                "failure_class": "timeout",
                                "probe": "json_schema",
                                "started_at": "2026-06-18T03:48:29Z",
                            },
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "ok",
                                "probe": "multilingual",
                                "started_at": "2026-06-18T03:50:00Z",
                            },
                            {
                                "route": "nvidia_nim:minimaxai/minimax-m3",
                                "status": "failed",
                                "failure_class": "quota",
                                "probe": "long_context",
                                "started_at": "2026-06-18T04:00:00Z",
                            },
                            {
                                "route": "ollama:minimax-m3:cloud",
                                "status": "ok",
                                "probe": "full_profile",
                                "started_at": "2026-06-18T03:50:01Z",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(live_matrix))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    minimax = {model.id: model for model in projection.models}["minimax-m3"]
    by_route = {route.route: route for route in minimax.route_statuses}

    assert minimax.available is True
    assert minimax.status == "live_routable"
    assert minimax.available_routes == ["ollama:minimax-m3:cloud"]
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].status == "unavailable"
    assert by_route["nvidia_nim:minimaxai/minimax-m3"].reason == "quota"
    assert minimax.verification.status == "verified"


def test_missing_key_status_is_unverified_not_advertised_callable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)

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
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)
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
