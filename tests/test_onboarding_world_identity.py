"""Fetch-free world-identity projection for compact onboarding (One World S4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.operator_core.onboarding import cli, render, world_identity

REPO_ROOT = Path(__file__).resolve().parents[1]


def _observation(**overrides: Any) -> dict[str, Any]:
    base = {
        "schema": world_identity.SCHEMA,
        "authority": world_identity.AUTHORITY,
        "fetch_free": True,
        "host": "test-host",
        "head": "c" * 40,
        "branch": "test/world-identity",
        "base_ref": "origin/main",
        "ahead": 2,
        "behind": 0,
        "base_tip_committer_ts": 1_788_000_000,
        "base_tip_committer_iso": "2026-08-29T01:45:43Z",
        "last_fetch_observed_age_seconds": 3600.0,
        "oldest_dirty_age_seconds": None,
        "oldest_dirty_path": "",
        "drift_warn_behind": world_identity.DRIFT_WARN_BEHIND,
        "dirty_warn_age_seconds": world_identity.DIRTY_WARN_AGE_SECONDS,
        "session_gate": False,
    }
    base.update(overrides)
    return base


def _receipt(world: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_verdict": "READY",
        "exit_code": 0,
        "stable_core": {
            "repository": {"branch": "test/world-identity", "head": "c" * 40},
            "portfolio": {"tracks": []},
            "orientation": {"broken_register": {}, "static_surfaces": {}},
            "required_reading": [],
        },
        "live_delta": {
            "repo_state": {
                "base": "origin/main",
                "dirty": False,
                "conflicted": False,
                "ahead": 2,
                "behind": 0,
            },
            "conditions": [],
            "toolchain": {},
            "projection_freshness": {},
        },
        "extensions": {"world_identity": world},
    }


def test_collection_schema_authority_and_live_repo_identity() -> None:
    observation = world_identity.collect_world_identity()

    assert observation["schema"] == "dharma_swarm.onboard_world_identity.v1"
    assert observation["authority"] == "advisory_only"
    assert observation["fetch_free"] is True
    assert observation["session_gate"] is False
    assert observation["host"]
    assert observation["head"]
    assert observation["branch"]
    assert observation["drift_warn_behind"] == 50
    assert observation["dirty_warn_age_seconds"] == 24 * 60 * 60


def test_collection_reuses_observed_live_state_distance() -> None:
    live_state = {"ahead": 7, "behind": 3}

    observation = world_identity.collect_world_identity(live_state=live_state)

    assert observation["ahead"] == 7
    assert observation["behind"] == 3


def test_human_renderer_names_identity_and_fetch_free_stance() -> None:
    output = render.render_compact(_receipt(_observation()))

    assert "WORLD IDENTITY — FETCH-FREE, ADVISORY ONLY" in output
    assert "test/world-identity @ " + "c" * 12 in output
    assert "host test-host" in output
    assert "vs local origin/main: ahead 2 · behind 0" in output
    assert "last fetch observed 1h ago" in output
    assert "WARNING" not in output.split("WORLD IDENTITY")[1].split("Primary blocker")[0]


def test_human_renderer_warns_loudly_on_drift_and_stale_dirty() -> None:
    drifting = _observation(
        behind=68,
        oldest_dirty_age_seconds=3 * 86400.0,
        oldest_dirty_path="docs/stale.md",
    )

    output = render.render_compact(_receipt(drifting))

    assert "WARNING: 68 commits behind local origin/main (> 50)" in output
    assert "WARNING: oldest dirty entry (docs/stale.md) is 3d old (> 24h)" in output


def test_human_renderer_handles_unobserved_fetch_and_missing_base() -> None:
    observation = _observation(
        ahead=None,
        behind=None,
        base_tip_committer_ts=None,
        base_tip_committer_iso="",
        last_fetch_observed_age_seconds=None,
    )

    output = render.render_compact(_receipt(observation))

    assert "ahead ? · behind ?" in output
    assert "last fetch unobserved; local ref may be stale" in output


def test_world_conditions_are_advisory_warns() -> None:
    drifting = _observation(behind=68, oldest_dirty_age_seconds=2 * 86400.0)

    conditions = cli._world_identity_conditions(drifting)

    assert {condition.id for condition in conditions} == {
        "world_drift_behind",
        "world_dirty_stale",
    }
    for condition in conditions:
        assert condition.state == "warn"
        assert condition.condition_class == "info"
        assert condition.mandatory is False
    assert cli._world_identity_conditions(_observation()) == []


def test_world_observation_does_not_change_typed_exit_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def run_with(observation: dict[str, Any], ops_name: str) -> tuple[int, str]:
        monkeypatch.setattr(
            cli.world_identity,
            "collect_world_identity",
            lambda live_state=None: observation,
        )
        monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / ops_name))
        exit_code = cli.assemble_and_run(["--json"])
        payload = json.loads(capsys.readouterr().out)
        return exit_code, payload["verdict"]

    calm = run_with(_observation(), "ops-calm")
    drifting = run_with(
        _observation(behind=500, oldest_dirty_age_seconds=30 * 86400.0),
        "ops-drifting",
    )

    assert calm == drifting


def test_json_projection_excludes_volatile_world_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli.world_identity,
        "collect_world_identity",
        lambda live_state=None: _observation(),
    )
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))

    exit_code = cli.assemble_and_run(["--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == payload["exit_code"]
    assert "world_identity" not in payload
    assert set(payload) == set(render._JSON_PROJECTION_KEYS)
