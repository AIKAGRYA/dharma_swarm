"""Hermetic tests for the canonical model-status projection."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from dharma_swarm import key_oracle, model_pool
from dharma_swarm.model_status import (
    HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
    LIVE_CALL_MATRIX_DIR_ENV,
    LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV,
    LIVE_CALL_MATRIX_PATH_ENV,
    floor_model_status,
    helm_on_call_projection_from_dict,
    projection_to_dict,
    save_profile,
    top_floor_models_for_dashboard,
)


@pytest.fixture(autouse=True)
def _disable_auto_live_matrix(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(tmp_path / "no-auto-live-matrix"))


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
    expected_floor_ids = {entry.id for entry in model_pool.floor_entries()}
    projected_ids = {model.id for model in projection.models}
    assert len(projection.models) == len(expected_floor_ids)
    assert projected_ids == expected_floor_ids
    assert {"kimi-k3", "glm-5.2"} <= projected_ids
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


def test_direct_live_probe_receipt_overrides_dkeys_live_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "claude_code": _row("✓", status="oauth present"),
            "ollama_cloud": _row("✓"),
            "nvidia_nim": _row("✓"),
        },
    )
    live_probe = tmp_path / "model_routing_live_probe.json"
    live_probe.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "claude-opus-4.8",
                        "route": "claude_code:claude-opus-4.8",
                        "status": "failed",
                        "failure_class": "timeout",
                        "started_at": "2026-07-01T01:09:06Z",
                    },
                    {
                        "logical_model_id": "kimi-k2.6",
                        "route": "ollama:kimi-k2.6:cloud",
                        "status": "ok",
                        "response_preview": "PONG",
                        "started_at": "2026-07-01T01:15:00Z",
                    },
                    {
                        "logical_model_id": "kimi-k2.6",
                        "route": "nvidia_nim:moonshotai/kimi-k2.6",
                        "status": "failed",
                        "failure_class": "schema_failure",
                        "error": "expected 'PONG'",
                        "started_at": "2026-07-01T01:15:01Z",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(live_probe))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    by_id = {model.id: model for model in projection.models}
    opus = by_id["claude-opus-4.8"]
    kimi = by_id["kimi-k2.6"]
    kimi_routes = {route.route: route for route in kimi.route_statuses}

    assert opus.available is False
    assert opus.unavailable_reason == "timeout"
    assert opus.verification.status == "failed"
    assert kimi.available is True
    assert kimi.available_routes == ["ollama:kimi-k2.6:cloud"]
    assert kimi_routes["nvidia_nim:moonshotai/kimi-k2.6"].status == "unavailable"
    assert kimi_routes["nvidia_nim:moonshotai/kimi-k2.6"].reason == "schema_failure"
    assert kimi.verification.status == "verified"


def test_live_probe_closeout_receipt_merges_referenced_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(
        tmp_path,
        {
            "codex (openai-pro)": _row("✓", status="oauth present"),
            "openai": _row("~", status="HTTP 429 rate-limited", http="429"),
        },
    )
    full_live = tmp_path / "full_live.json"
    codex_retest = tmp_path / "codex_retest.json"
    closeout = tmp_path / "provider_live_matrix.json"
    full_live.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "gpt-5.5",
                        "route": "codex:gpt-5.5",
                        "status": "failed",
                        "failure_class": "routing_bug",
                        "error": "Operation not permitted",
                        "started_at": "2026-07-01T01:10:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    codex_retest.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "gpt-5.5",
                        "route": "codex:gpt-5.5",
                        "status": "ok",
                        "response_preview": "PONG",
                        "started_at": "2026-07-01T02:53:01Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    closeout.write_text(
        json.dumps(
            {
                "schema_version": "dharma.provider_live_matrix_closeout.v1",
                "artifacts": {
                    "full_live_matrix": str(full_live),
                    "codex_outside_sandbox_retest": str(codex_retest),
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(LIVE_CALL_MATRIX_PATH_ENV, str(closeout))

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    gpt = {model.id: model for model in projection.models}["gpt-5.5"]
    by_route = {route.route: route for route in gpt.route_statuses}

    assert gpt.available is True
    assert "codex:gpt-5.5" in gpt.available_routes
    assert by_route["codex:gpt-5.5"].status == "live_routable"
    assert gpt.verification.status == "verified"
    assert gpt.verification.verified_at == "2026-07-01T02:53:01Z"


def test_fresh_live_probe_closeout_is_discovered_without_operator_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path, {"claude_code": _row("✓", status="oauth present")})
    allnight = tmp_path / "reports" / "langgraph_parity" / "allnight"
    allnight.mkdir(parents=True)
    live_probe = allnight / "model_routing_live_probe_live.json"
    closeout = allnight / "provider_live_matrix_20260701T010345Z.json"
    live_probe.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "claude-opus-4.8",
                        "route": "claude_code:claude-opus-4.8",
                        "status": "failed",
                        "failure_class": "timeout",
                        "started_at": "2026-07-01T01:09:06Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    closeout.write_text(
        json.dumps(
            {
                "schema_version": "dharma.provider_live_matrix_closeout.v1",
                "generated_at": "2026-07-01T02:58:57Z",
                "artifacts": {"full_live_matrix": str(live_probe)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(allnight))
    monkeypatch.setenv(LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV, "100000")

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    opus = {model.id: model for model in projection.models}["claude-opus-4.8"]

    assert opus.available is False
    assert opus.status == "unavailable"
    assert opus.unavailable_reason == "timeout"
    assert opus.verification.status == "failed"


def test_stale_auto_discovered_live_probe_closeout_expires(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_status(tmp_path, {"claude_code": _row("✓", status="oauth present")})
    allnight = tmp_path / "reports" / "langgraph_parity" / "allnight"
    allnight.mkdir(parents=True)
    live_probe = allnight / "model_routing_live_probe_live.json"
    closeout = allnight / "provider_live_matrix_20200101T000000Z.json"
    live_probe.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "claude-opus-4.8",
                        "route": "claude_code:claude-opus-4.8",
                        "status": "failed",
                        "failure_class": "timeout",
                        "started_at": "2020-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    closeout.write_text(
        json.dumps(
            {
                "schema_version": "dharma.provider_live_matrix_closeout.v1",
                "generated_at": "2020-01-01T00:00:00Z",
                "artifacts": {"full_live_matrix": str(live_probe)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(allnight))
    monkeypatch.setenv(LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV, "1")

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    opus = {model.id: model for model in projection.models}["claude-opus-4.8"]

    assert opus.available is True
    assert opus.status == "live_routable"
    assert opus.verification.status == "unverified"


def test_fresh_live_probe_sets_model_status_when_key_oracle_unknown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    allnight = tmp_path / "reports" / "langgraph_parity" / "allnight"
    allnight.mkdir(parents=True)
    live_probe = allnight / "model_routing_live_probe_live.json"
    closeout = allnight / "provider_live_matrix_20260701T010345Z.json"
    live_probe.write_text(
        json.dumps(
            {
                "schema_version": "dharma.model_routing_live_probe.v1",
                "results": [
                    {
                        "logical_model_id": "kimi-k2.6",
                        "route": "ollama:kimi-k2.6:cloud",
                        "status": "ok",
                        "response_preview": "PONG",
                        "started_at": "2026-07-01T01:15:09Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    closeout.write_text(
        json.dumps(
            {
                "schema_version": "dharma.provider_live_matrix_closeout.v1",
                "generated_at": "2026-07-01T02:58:57Z",
                "artifacts": {"full_live_matrix": str(live_probe)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(LIVE_CALL_MATRIX_PATH_ENV, raising=False)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(allnight))
    monkeypatch.setenv(LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV, "100000")

    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    kimi = {model.id: model for model in projection.models}["kimi-k2.6"]

    assert projection.oracle_state == "unknown"
    assert kimi.available is True
    assert kimi.status == "live_routable"
    assert kimi.available_routes == ["ollama:kimi-k2.6:cloud"]
    assert kimi.verification.status == "verified"


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


def test_legacy_model_status_projection_cannot_be_deserialized_as_helm_truth(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(key_oracle.Path, "home", classmethod(lambda cls: tmp_path))
    projection = floor_model_status(profiles_path=tmp_path / "profiles.json")
    payload = projection_to_dict(projection)

    assert payload["schema_version"] != HELM_ON_CALL_PROJECTION_SCHEMA_VERSION
    with pytest.raises(ValueError, match="exactly"):
        helm_on_call_projection_from_dict(payload)
