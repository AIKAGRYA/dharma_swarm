from __future__ import annotations

import copy
import inspect
from pathlib import Path
from typing import Any, Callable

import pytest

from dharma_swarm.forge_lab import unattended_call_shape as call_shape
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger


def _bridge(
    db: Path,
    *,
    task_id: str = "admitted-task",
    allocate: Callable[..., dict[str, Any]] = taskbed_ledger.allocate_task_ids,
) -> Callable[..., dict[str, Any]]:
    return call_shape._build_state_anchored_explore_allocator(
        admitted_task_id=task_id,
        taskbed_db=db,
        error_factory=call_shape.CallShapeError,
        allocate_task_ids_fn=allocate,
    )


def test_state_anchored_bridge_uses_real_allocator_for_exact_admitted_explore(
    tmp_path: Path,
) -> None:
    db = tmp_path / "state" / ".dharma" / "forge_v1" / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            {
                "task_id": "decoy-task",
                "created_at": "2026-08-01T00:00:00Z",
                "contamination_state": "fresh_post_cutoff",
            },
            {
                "task_id": "admitted-task",
                "created_at": "2026-08-02T00:00:00Z",
                "contamination_state": "fresh_post_cutoff",
            },
        ],
        db_path=db,
        source="offline-regression",
        taskbed="temporary",
    )
    allocate = _bridge(db)

    upstream = inspect.signature(taskbed_ledger.allocate_explore)
    bridge = inspect.signature(allocate)
    assert tuple(bridge.parameters) == tuple(upstream.parameters)
    assert [item.kind for item in bridge.parameters.values()] == [
        item.kind for item in upstream.parameters.values()
    ]

    receipt = allocate(count=1, epoch_id="run-1_gen0", lane_id="unattended")

    assert receipt["schema"] == "forge_v2.taskbed_allocation_receipt.v1"
    assert receipt["split"] == "explore"
    assert receipt["task_count"] == 1
    assert receipt["task_ids"] == ["admitted-task"]
    rows = taskbed_ledger.allocation_rows(receipt["allocation_id"], db_path=db)
    assert [(row["task_id"], row["split"]) for row in rows] == [
        ("admitted-task", "explore")
    ]


def test_state_anchored_bridge_allocates_both_experiment_epochs_as_explore(
    tmp_path: Path,
) -> None:
    db = tmp_path / "state" / ".dharma" / "forge_v1" / "taskbed.db"
    taskbed_ledger.register_tasks(
        [
            {
                "task_id": "admitted-task",
                "created_at": "2026-08-02T00:00:00Z",
                "contamination_state": "fresh_post_cutoff",
                "max_uses_per_epoch": 1,
            }
        ],
        db_path=db,
        source="offline-regression",
        taskbed="temporary",
    )
    allocate = _bridge(db)

    gen0 = allocate(
        count=1,
        epoch_id="unattended-run_gen0",
        lane_id="unattended",
    )
    gen1 = allocate(
        count=1,
        epoch_id="unattended-run_gen1",
        lane_id="unattended",
    )

    assert gen0["allocation_id"] != gen1["allocation_id"]
    assert gen0["task_ids"] == gen1["task_ids"] == ["admitted-task"]
    for receipt, epoch_id in (
        (gen0, "unattended-run_gen0"),
        (gen1, "unattended-run_gen1"),
    ):
        assert receipt["split"] == "explore"
        rows = taskbed_ledger.allocation_rows(receipt["allocation_id"], db_path=db)
        assert [(row["task_id"], row["split"], row["epoch_id"]) for row in rows] == [
            ("admitted-task", "explore", epoch_id)
        ]
    with taskbed_ledger.connect(db) as connection:
        confirm_count = connection.execute(
            "SELECT COUNT(*) FROM taskbed_allocations WHERE split='confirm'"
        ).fetchone()[0]
    assert confirm_count == 0


@pytest.mark.parametrize("count", [0, 2, True, "1"])
def test_state_anchored_bridge_refuses_count_drift(tmp_path: Path, count: Any) -> None:
    called = False

    def forbidden_allocator(**_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("allocator must not run")

    allocate = _bridge(tmp_path / "taskbed.db", allocate=forbidden_allocator)

    with pytest.raises(call_shape.CallShapeError) as error:
        allocate(count=count, epoch_id="run-1_gen0", lane_id="unattended")

    assert error.value.code == "TASK_SHAPE"
    assert called is False


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"db_path": "elsewhere.db"}, "TASK_ALLOCATION_OVERRIDE"),
        ({"allocation_id": "caller-selected"}, "TASK_ALLOCATION_OVERRIDE"),
        ({"candidate_id": "caller-selected"}, "TASK_ALLOCATION_OVERRIDE"),
        ({"epoch_id": ""}, "TASK_ALLOCATION_INTERFACE"),
        ({"lane_id": ""}, "TASK_ALLOCATION_INTERFACE"),
    ],
)
def test_state_anchored_bridge_refuses_interface_and_identity_drift(
    tmp_path: Path,
    override: dict[str, Any],
    code: str,
) -> None:
    called = False

    def forbidden_allocator(**_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("allocator must not run")

    allocate = _bridge(tmp_path / "taskbed.db", allocate=forbidden_allocator)
    kwargs: dict[str, Any] = {
        "count": 1,
        "epoch_id": "run-1_gen0",
        "lane_id": "unattended",
    }
    kwargs.update(override)

    with pytest.raises(call_shape.CallShapeError) as error:
        allocate(**kwargs)

    assert error.value.code == code
    assert called is False


def test_state_anchored_bridge_hardcodes_explore_and_types_allocator_errors(
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    def broken_allocator(**kwargs: Any) -> dict[str, Any]:
        observed.update(kwargs)
        raise TypeError("simulated allocator interface drift")

    allocate = _bridge(tmp_path / "taskbed.db", allocate=broken_allocator)

    with pytest.raises(call_shape.CallShapeError) as error:
        allocate(count=1, epoch_id="run-1_gen0", lane_id="unattended")

    assert error.value.code == "TASK_ALLOCATION_REFUSED"
    assert observed["split"] == "explore"
    assert observed["task_ids"] == ["admitted-task"]
    assert observed["allocation_id"] is None
    assert observed["candidate_id"] == ""


@pytest.mark.parametrize(
    "drift",
    [
        {"schema": "wrong"},
        {"split": "confirm"},
        {"task_count": 2},
        {"task_count": True},
        {"task_ids": ["other-task"]},
        {"blockers": ["unexpected"]},
        {"allocation_id": ""},
    ],
)
def test_state_anchored_bridge_refuses_receipt_drift(
    tmp_path: Path,
    drift: dict[str, Any],
) -> None:
    receipt: dict[str, Any] = {
        "schema": "forge_v2.taskbed_allocation_receipt.v1",
        "allocation_id": "explore-run-1",
        "split": "explore",
        "task_count": 1,
        "task_ids": ["admitted-task"],
        "blockers": [],
    }
    receipt.update(drift)
    allocate = _bridge(tmp_path / "taskbed.db", allocate=lambda **_kwargs: receipt)

    with pytest.raises(call_shape.CallShapeError) as error:
        allocate(count=1, epoch_id="run-1_gen0", lane_id="unattended")

    assert error.value.code == "TASK_ALLOCATION_RECEIPT"


def _runner_policy() -> call_shape.RunnerPolicy:
    return call_shape.RunnerPolicy(
        runner_schema="runner.v1",
        ledger_schema="ledger.v1",
        child_schema="child.v1",
        generations=1,
        children=1,
        tasks=1,
        logical_provider_call_slots=5,
        per_call_tokens=1,
        per_candidate_tokens=1,
        per_candidate_usd=0.1,
        max_experiment_tokens=1,
        max_timeout_seconds=60,
        run_usd_reservation=1.0,
    )


def _valid_child_result(scratch_root: Path) -> dict[str, Any]:
    experiment_id = "experiment-1"
    marker_digest = "sha256:" + "c" * 64
    result = {
        "schema": "child.v1",
        "run_id": "run-1",
        "experiment_id": experiment_id,
        "closeout_state": "inconclusive_low_power",
        "positive_rsi_claim": False,
        "logical_provider_calls_used": 5,
        "logical_provider_call_limit": 5,
        "logical_provider_calls_by_role": dict(call_shape.EXPECTED_PROVIDER_CALLS),
        "expected_provider_calls_by_role": dict(call_shape.EXPECTED_PROVIDER_CALLS),
        "execution_shape_ok": True,
        "scratch_cleanup_ok": True,
        "scratch_custody_attestation": {
            "schema": "rsi_lab.unattended_scratch_proof.v1",
            "operation": "attest",
            "ok": True,
            "scratch_root": str(scratch_root),
            "run_id": "run-1",
            "root_identity": {"device": 1, "inode": 2},
            "marker_digest": marker_digest,
            "inventory": None,
            "code": None,
            "message": None,
            "proof_digest": "pending",
        },
        "experiment_closeout": {
            "schema": "forge_lab.closeout.v0",
            "experiment_id": experiment_id,
            "closeout_state": "inconclusive_low_power",
            "scratch_worktree": {
                "path": str(scratch_root / experiment_id / "repo"),
                "state": "removed",
                "removed": True,
            },
            "stats": {
                "counters": {"graded": 2, "paired_controls": 1, "blocked": 0}
            },
        },
        "epistemic_modality": "EXPLORE_ONLY",
        "result_digest": "digest",
    }
    attestation = result["scratch_custody_attestation"]
    attestation["proof_digest"] = content_digest(
        {key: value for key, value in attestation.items() if key != "proof_digest"}
    )
    return result


def _validate_result(
    path: Path,
    result: dict[str, Any],
    scratch_root: Path,
) -> dict[str, Any] | None:
    def safe_json(_path: Path) -> dict[str, Any]:
        return copy.deepcopy(result)

    return call_shape.validated_child_result(
        path,
        run_id="run-1",
        scratch_root=scratch_root,
        scratch_marker_digest="sha256:" + "c" * 64,
        scratch_root_identity={"device": 1, "inode": 2},
        terminal_success_states=frozenset(
            {"inconclusive_low_power", "measured_negative"}
        ),
        policy=_runner_policy(),
        safe_json_fn=safe_json,
        chain_digest_fn=lambda _payload, _field: "digest",
    )


def test_validated_child_result_requires_exact_nested_cleanup_evidence(
    tmp_path: Path,
) -> None:
    scratch_root = tmp_path / "scratch"
    result = _valid_child_result(scratch_root)
    path = tmp_path / "child_result.json"

    assert _validate_result(path, result, scratch_root) == result

    result["scratch_cleanup_ok"] = False
    assert _validate_result(path, result, scratch_root) is None


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("logical_provider_calls_used",), 5.9),
        (("logical_provider_call_limit",), "5"),
        (("logical_provider_calls_by_role", "mutation"), 2),
        (("logical_provider_calls_by_role", "mutation"), 1.0),
        (("expected_provider_calls_by_role", "candidate_solver"), 2),
        (("expected_provider_calls_by_role", "candidate_solver"), 1.0),
        (("epistemic_modality",), "CONFIRM"),
        (("scratch_custody_attestation", "operation"), "create"),
        (
            ("scratch_custody_attestation", "marker_digest"),
            "sha256:" + "d" * 64,
        ),
        (("scratch_custody_attestation", "proof_digest"), "tampered"),
        (("closeout_state",), "measured_negative"),
        (("experiment_closeout", "closeout_state"), "blocked_with_evidence"),
        (("experiment_closeout", "scratch_worktree", "state"), "remove_unconfirmed"),
        (("experiment_closeout", "scratch_worktree", "removed"), False),
        (("experiment_closeout", "stats", "counters", "graded"), True),
        (("experiment_closeout", "stats", "counters", "paired_controls"), 2),
        (("experiment_closeout", "stats", "counters", "blocked"), 1),
    ],
)
def test_validated_child_result_rejects_self_asserted_shape_drift(
    tmp_path: Path,
    path: tuple[str, ...],
    value: Any,
) -> None:
    scratch_root = tmp_path / "scratch"
    result = _valid_child_result(scratch_root)
    target: dict[str, Any] = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    assert _validate_result(tmp_path / "result.json", result, scratch_root) is None


def test_validated_child_result_requires_nested_closeout_and_exact_scratch_path(
    tmp_path: Path,
) -> None:
    scratch_root = tmp_path / "scratch"
    result = _valid_child_result(scratch_root)
    del result["experiment_closeout"]
    assert _validate_result(tmp_path / "result.json", result, scratch_root) is None


def test_validated_child_result_is_total_for_unhashable_json_state(
    tmp_path: Path,
) -> None:
    scratch_root = tmp_path / "scratch"
    result = _valid_child_result(scratch_root)
    result["closeout_state"] = []
    result["experiment_closeout"]["closeout_state"] = []

    assert _validate_result(tmp_path / "result.json", result, scratch_root) is None

    result = _valid_child_result(scratch_root)
    result["experiment_closeout"]["scratch_worktree"]["path"] = str(
        tmp_path / "outside" / "experiment-1" / "repo"
    )
    assert _validate_result(tmp_path / "result.json", result, scratch_root) is None


def test_validated_child_result_treats_dangling_scratch_symlink_as_present(
    tmp_path: Path,
) -> None:
    scratch_root = tmp_path / "scratch"
    scratch_repo = scratch_root / "experiment-1" / "repo"
    scratch_repo.parent.mkdir(parents=True)
    scratch_repo.symlink_to(tmp_path / "missing", target_is_directory=True)
    result = _valid_child_result(scratch_root)

    assert scratch_repo.exists() is False
    assert _validate_result(tmp_path / "result.json", result, scratch_root) is None
