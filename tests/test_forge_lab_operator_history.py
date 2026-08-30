"""Tests for the read-only Forge Lab operator-history projection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from dharma_swarm.forge_lab.operator_history import (
    METRIC_KEYS,
    SCORECARD_SCHEMA,
    VIEW_SCHEMA,
    build_operator_history,
)


FIXED_NOW = datetime(2026, 7, 12, 1, 2, 3, tzinfo=timezone.utc)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_result(path: Path, *, experiment_id: str, candidate: str, parent: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": "forge_lab.result_observation.v0",
        "experiment_id": experiment_id,
        "candidate_id": candidate,
        "parent_id": parent,
        "state": "graded",
        "role": "seed_baseline" if parent is None else "candidate",
        "generation": 0 if parent is None else 1,
        "pass_rate": 1 / 3,
        "per_task": [
            {"task_id": "task-1", "resolved": True, "tokens_spent": 10},
            {"task_id": "task-2", "resolved": False, "error": "empty_patch", "tokens_spent": 20},
            {"task_id": "task-3", "resolved": False, "error": "empty_patch", "tokens_spent": 30},
        ],
        "budget": {"spent_tokens": 60, "invalid": False},
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def _native(
    state: Path,
    experiment_id: str,
    *,
    started_at: str,
    closeout: bool = True,
    with_result: bool = True,
) -> Path:
    root = state / ".dharma" / "evolution_archive" / "agent_evolution" / experiment_id
    _write_json(
        root / "run_manifest.json",
        {
            "schema": "forge_lab.run_manifest.v0",
            "experiment_id": experiment_id,
            "started_at": started_at,
            "benchmark": "fixture-pr-suite",
            "git_base_sha": "a" * 40,
            "mode": "shadow",
            "config": {
                "generations": 2,
                "children": 1,
                "tasks_per_generation": 3,
                "solver_model": "moonshot:kimi-k2.7-code",
                "verifier_model": "moonshot:kimi-k2.7-code",
            },
        },
    )
    if with_result:
        _write_result(root / "results.jsonl", experiment_id=experiment_id, candidate="seed")
    if closeout:
        _write_json(
            root / "closeout.json",
            {
                "schema": "forge_lab.closeout.v0",
                "experiment_id": experiment_id,
                "closeout_state": "inconclusive_low_power",
                "started_at": started_at,
                "finished_at": "2026-07-11T01:10:00+00:00",
                "wall_seconds": 600,
                "stats": {
                    "counters": {"graded": 1},
                    "seed_pass_rate": 1 / 3,
                    "best_pass_rate": 1 / 3,
                    "tokens_spent_total": 60,
                },
                "merkle": {"verified": True},
                "scratch_worktree": {"removed": True},
            },
        )
    return root


def _operator_run(state: Path, run_id: str, log: str | None) -> Path:
    run = state / "rsi_runs" / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    if log is not None:
        (state / "rsi_runs" / f"{run_id}.log").write_text(log, encoding="utf-8")
    return run


def _manager_fixture(state: Path) -> tuple[Path, list[str]]:
    run_id = "rsi-manager-4h-20260711T140037Z"
    run = _operator_run(state, run_id, None)
    ids: list[str] = []
    names = (
        "canary_attempt1_blocked",
        "canary_attempt2_timeout",
        "canary",
        "screen_775",
        "screen_3232_fallback",
    )
    for index, name in enumerate(names, start=1):
        experiment_id = f"exp_agent_evolution_manager_20260711T14{index:02d}000_{'b' * 8}"
        ids.append(experiment_id)
        _native(
            state,
            experiment_id,
            started_at=f"2026-07-11T14:{index:02d}:00+00:00",
        )
        _write_json(run / "experiments" / f"{name}.json", {"experiment_id": experiment_id})
    _write_json(
        run / "protocol_result.json",
        {
            "schema": "forge_lab.bounded_comparison_closeout.v0",
            "closeout_state": "measured_negative_screen",
            "holdout_used": False,
            "usage": {
                "reported_tokens": 300,
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "logical_requests": 5,
            },
        },
    )
    _write_json(
        run / "preregistration.json",
        {
            "source": {"head": "c" * 40},
            "provider": {"route": "moonshot:kimi-k2.7-code", "independent_routes": 1},
            "fuses": {"reported_token_cap": 1000},
        },
    )
    _write_json(
        run / "manager_closeout.json",
        {"finished_at": "2026-07-11T16:00:00+00:00", "usage": {"reported_tokens": 300}},
    )
    _write_json(
        run / "postrun_audit.json",
        {
            "provider_trace": {
                "route": "MoonshotProvider/kimi-k2.7-code",
                "independent_routes": 1,
                "trace_rows": 5,
                "successful_responses": 4,
                "failed_responses": 1,
                "hidden_retries": 0,
            },
            "native_receipts": [
                {
                    "experiment_id": experiment_id,
                    "merkle_verified": True,
                    "scratch_removed": True,
                }
                for experiment_id in ids[2:]
            ],
            "panel_preservation": {
                "preregistered_holdout_tasks": 8,
                "holdout_result_occurrences": 0,
                "untouched_reserve_tasks": 10,
                "reserve_result_occurrences": 0,
                "frozen_candidate_file_exists": False,
            },
            "source": {"worktree_clean": True},
        },
    )
    return run, ids


def _regular_generated_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    )


def test_builds_stable_operator_view_and_groups_manager_phases(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    manager_run, experiment_ids = _manager_fixture(state)
    source_hash = hashlib.sha256((manager_run / "protocol_result.json").read_bytes()).hexdigest()
    archive = state / ".dharma" / "evolution_archive" / "agent_evolution"
    for experiment_id, seed, best in (
        (experiment_ids[2], 0.1, 0.2),
        (experiment_ids[3], 0.8, 0.85),
        (experiment_ids[4], 0.5, 0.55),
    ):
        closeout_path = archive / experiment_id / "closeout.json"
        closeout = json.loads(closeout_path.read_text())
        closeout["stats"]["seed_pass_rate"] = seed
        closeout["stats"]["best_pass_rate"] = best
        closeout_path.write_text(json.dumps(closeout), encoding="utf-8")

    orphan_id = "exp_manual_fixture_20260710T0100000_deadbeef"
    _native(state, orphan_id, started_at="2026-07-10T01:00:00+00:00")
    output = tmp_path / "operator-history"

    manifest = build_operator_history(state, output, generated_at=FIXED_NOW)

    assert manifest["schema"] == VIEW_SCHEMA
    assert manifest["operator_run_count"] == 1
    assert manifest["linked_native_experiment_count"] == 5
    assert manifest["native_only_experiment_count"] == 1
    assert (output / "README_FIRST.md").is_file()
    assert (output / "LATEST").is_symlink()
    assert (output / "LATEST" / "README.md").is_file()
    assert "2026-07-11T140037Z__manager-4h__shadow__kimi-k2-7-code" in (output / "LATEST").resolve().name

    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())
    assert scorecard["schema"] == SCORECARD_SCHEMA
    assert set(scorecard["metrics"]) == set(METRIC_KEYS)
    assert len(scorecard["metrics"]) == 10
    assert scorecard["metrics"]["usage"]["actual_cost_usd"] is None
    assert scorecard["metrics"]["evaluation"]["native_experiment_ids"] == experiment_ids
    assert scorecard["metrics"]["evaluation"]["native_experiment_count"] == 5
    assert scorecard["metrics"]["quality"]["seed_pass_rate"] == pytest.approx(0.1)
    assert scorecard["metrics"]["quality"]["best_pass_rate"] == pytest.approx(0.2)
    assert scorecard["metrics"]["quality"]["absolute_lift"] == pytest.approx(0.1)
    assert scorecard["metrics"]["quality"]["maximum_observed_pass_rate"] == pytest.approx(0.85)
    assert scorecard["metrics"]["integrity"]["merkle_verified"] is True
    assert scorecard["metrics"]["integrity"]["scratch_removed"] is True
    assert len(list((output / "LATEST" / "SOURCE_LINKS").glob("E*"))) == 5
    assert hashlib.sha256((manager_run / "protocol_result.json").read_bytes()).hexdigest() == source_hash


def test_history_is_newest_first_and_regeneration_is_idempotent(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    older_id = "exp_fixture_old_20260708T0100010_aaaaaaaa"
    newer_id = "exp_fixture_new_20260709T0100010_bbbbbbbb"
    _native(state, older_id, started_at="2026-07-08T01:00:01+00:00")
    _native(state, newer_id, started_at="2026-07-09T01:00:01+00:00")
    _operator_run(
        state,
        "rsi-smoke-20260708T010000Z",
        f"START_UTC=2026-07-08T01:00:00Z\nMODE=shadow\n{older_id}\n",
    )
    _operator_run(
        state,
        "rsi-smoke-20260709T010000Z",
        f"START_UTC=2026-07-09T01:00:00Z\nMODE=shadow\n{newer_id}\n",
    )
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    first = _regular_generated_text(output)
    rows = [json.loads(line) for line in (output / "history.v1.jsonl").read_text().splitlines()]
    assert [row["run_id"] for row in rows] == [
        "rsi-smoke-20260709T010000Z",
        "rsi-smoke-20260708T010000Z",
    ]
    assert (output / "LATEST").resolve().name.startswith("2026-07-09T010000Z")

    build_operator_history(state, output, generated_at=FIXED_NOW)
    assert _regular_generated_text(output) == first
    assert not list(tmp_path.glob(".operator-history.previous-*"))


def test_infers_only_matching_smoke_and_keeps_unknown_native_separate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    inferred_id = "exp_agent_evolution_fixture_20260708T0108440_aaaaaaaa"
    _native(state, inferred_id, started_at="2026-07-08T01:08:44+00:00", closeout=False)
    tombstone_id = "exp_unknown_20260708T0200000_unknown"
    (state / ".dharma" / "evolution_archive" / "agent_evolution" / tombstone_id).mkdir(parents=True)
    _operator_run(
        state,
        "rsi-smoke-20260708T010843Z",
        "\n".join(
            [
                "START_UTC=2026-07-08T01:08:43Z",
                f"REPO_HEAD={'a' * 40}",
                "PRESET=smoke generations=2 children=1 tasks=3",
                "MODE=shadow NO_LIFT_CLAIM=true",
                "SECRET_SENTINEL=do-not-copy",
            ]
        ),
    )
    output = tmp_path / "operator-history"

    manifest = build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())

    assert manifest["linked_native_experiment_count"] == 1
    assert manifest["native_only_experiment_count"] == 1
    assert scorecard["metrics"]["evaluation"]["native_experiment_ids"] == [inferred_id]
    assert scorecard["metrics"]["provenance"]["association_methods"] == [
        "inferred_timestamp_and_config"
    ]
    assert scorecard["metrics"]["usage"]["reported_tokens"] == 60
    assert scorecard["metrics"]["usage"]["is_lower_bound"] is True
    assert any("inferred" in warning.lower() for warning in scorecard["warnings"])
    assert "SECRET_SENTINEL" not in _regular_generated_text(output)


def test_budget_invalid_quality_is_prominent_in_run_and_global_indexes(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    experiment_id = "exp_invalid_budget_20260709T0100010_aaaaaaaa"
    native = _native(state, experiment_id, started_at="2026-07-09T01:00:01+00:00")
    row = json.loads((native / "results.jsonl").read_text())
    row["budget"]["invalid"] = True
    (native / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    closeout = json.loads((native / "closeout.json").read_text())
    closeout["stats"]["seed_pass_rate"] = 0.2
    closeout["stats"]["best_pass_rate"] = 0.4
    (native / "closeout.json").write_text(json.dumps(closeout), encoding="utf-8")
    _operator_run(
        state,
        "rsi-loop-n20-20260709T010000Z",
        f"START_UTC=2026-07-09T01:00:00Z\nMODE=shadow\n{experiment_id}\n",
    )
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())

    assert scorecard["metrics"]["quality"]["absolute_lift"] == pytest.approx(0.2)
    assert scorecard["metrics"]["quality"]["headline_lift_valid"] is False
    assert scorecard["metrics"]["quality"]["budget_evidence_state"] == "no_budget_valid_rows"
    assert any("quality invalid for lift" in warning.lower() for warning in scorecard["warnings"])
    assert "INVALID FOR LIFT" in (output / "LATEST" / "README.md").read_text()
    assert "INVALID (0 budget-valid)" in (output / "ALL_RUNS.md").read_text()


def test_legacy_best_fitness_is_not_mislabeled_as_pass_rate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    experiment_id = "exp_legacy_20260706T1200000_deadbeef"
    native = state / ".dharma" / "evolution_archive" / "agent_evolution" / experiment_id
    _write_json(
        native / "closeout.json",
        {
            "schema": "forge_lab.closeout.v0",
            "experiment_id": experiment_id,
            "closeout_state": "completed",
            "created_at": "2026-07-06T12:00:00Z",
            "graded_count": 7,
            "best_fitness": 0.51,
        },
    )
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard_path = next((output / "native-only").glob("*/*/SCORECARD.json"))
    scorecard = json.loads(scorecard_path.read_text())

    assert scorecard["run_id"] == experiment_id
    assert scorecard["metrics"]["quality"]["best_pass_rate"] is None
    assert scorecard["metrics"]["evaluation"]["accepted_graded_rows"] == 7


def test_manager_without_audit_excludes_blocked_and_discarded_attempts(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    manager_run, _ = _manager_fixture(state)
    (manager_run / "postrun_audit.json").unlink()
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())

    assert scorecard["metrics"]["evaluation"]["raw_graded_rows"] == 5
    assert scorecard["metrics"]["evaluation"]["accepted_graded_rows"] == 3
    assert scorecard["metrics"]["evaluation"]["task_observations"] == 9


def test_native_only_slugs_cannot_collide_at_the_same_second(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    for suffix in ("aaaaaaaa", "bbbbbbbb"):
        _native(
            state,
            f"exp_collision_20260706T1200000_{suffix}",
            started_at="2026-07-06T12:00:00+00:00",
        )
    output = tmp_path / "operator-history"

    manifest = build_operator_history(state, output, generated_at=FIXED_NOW)
    native_dirs = list((output / "native-only" / "2026-07-06").iterdir())

    assert manifest["native_only_experiment_count"] == 2
    assert len(native_dirs) == 2
    assert len({path.name for path in native_dirs}) == 2


def test_missing_explicit_phase_cannot_report_complete_receipts(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    manager_run, experiment_ids = _manager_fixture(state)
    missing = (
        state
        / ".dharma"
        / "evolution_archive"
        / "agent_evolution"
        / experiment_ids[-1]
    )
    for path in missing.iterdir():
        path.unlink()
    missing.rmdir()
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())

    assert scorecard["metrics"]["integrity"]["complete_receipts"] is False
    assert any("references missing" in warning.lower() for warning in scorecard["warnings"])


def test_corrupt_and_incomplete_receipts_degrade_to_unknown_with_warning(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    experiment_id = "exp_corrupt_20260708T0300010_aaaaaaaa"
    native = state / ".dharma" / "evolution_archive" / "agent_evolution" / experiment_id
    native.mkdir(parents=True)
    (native / "run_manifest.json").write_text("{not-json", encoding="utf-8")
    _operator_run(
        state,
        "rsi-smoke-20260708T030000Z",
        f"START_UTC=2026-07-08T03:00:00Z\n{experiment_id}\n",
    )
    output = tmp_path / "operator-history"

    build_operator_history(state, output, generated_at=FIXED_NOW)
    scorecard = json.loads((output / "LATEST" / "SCORECARD.json").read_text())

    assert scorecard["metrics"]["verdict"]["state"] == "incomplete_no_results"
    assert scorecard["metrics"]["quality"]["best_pass_rate"] is None
    assert scorecard["metrics"]["usage"]["reported_tokens"] is None
    assert any("could not read run manifest" in warning.lower() for warning in scorecard["warnings"])
    assert any("no closeout" in warning.lower() for warning in scorecard["warnings"])


def test_refuses_to_replace_an_unmarked_directory(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (state / "rsi_runs").mkdir(parents=True)
    output = tmp_path / "operator-history"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("user-owned", encoding="utf-8")

    with pytest.raises(ValueError, match="non-generated"):
        build_operator_history(state, output, generated_at=FIXED_NOW)

    assert sentinel.read_text(encoding="utf-8") == "user-owned"


def test_refuses_to_trust_a_counterfeit_generated_marker(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (state / "rsi_runs").mkdir(parents=True)
    output = tmp_path / "operator-history"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("user-owned", encoding="utf-8")
    (output / ".rsi-operator-history").write_text(
        json.dumps({"schema": "some_other_tool.v1"}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unrecognized generated marker"):
        build_operator_history(state, output, generated_at=FIXED_NOW)

    assert sentinel.read_text(encoding="utf-8") == "user-owned"


def test_requires_a_second_location_outside_canonical_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (state / "rsi_runs").mkdir(parents=True)

    with pytest.raises(ValueError, match="second location"):
        build_operator_history(state, state / "operator-history", generated_at=FIXED_NOW)

    with pytest.raises(ValueError, match="second location"):
        build_operator_history(state, tmp_path, generated_at=FIXED_NOW)


def test_second_location_guard_follows_symlinked_ancestors(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (state / "rsi_runs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "state-link").symlink_to(state, target_is_directory=True)

    with pytest.raises(ValueError, match="second location"):
        build_operator_history(
            state,
            outside / "state-link" / "operator-history",
            generated_at=FIXED_NOW,
        )

    assert not (state / "operator-history").exists()
