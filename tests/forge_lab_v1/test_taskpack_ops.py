from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.forge_lab import taskpack_apply, taskpack_ops


def _bytes_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_manifest(path: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )
    path.write_bytes(payload)
    return _bytes_digest(payload)


def _fresh_row(task_id: str = "fresh-task-1") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "repo": "example/project",
        "created_at": "2026-07-01T00:00:00Z",
        "problem_statement": "fix the sealed regression",
        "FAIL_TO_PASS": ["tests/test_regression.py::test_fix"],
    }


def _search_row(instance_id: str = "django__django-123") -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "repo": "django/django",
        "base_commit": "a" * 40,
        "problem_statement": "fix the public benchmark regression",
        "FAIL_TO_PASS": ["tests/regressiontests/example.py::ExampleTests::test_fix"],
    }


@pytest.fixture
def admitted_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "release" / ("a" * 40) / "repo"
    importer = repo / "scripts/runtime/forge_fresh_task_oracle.py"
    importer.parent.mkdir(parents=True)
    importer.write_text("# repository-owned importer fixture\n", encoding="utf-8")

    def _require(candidate: Path | None = None) -> dict[str, Any]:
        if candidate is not None:
            assert Path(candidate).resolve() == repo.resolve()
        return {
            "ready": True,
            "repo": str(repo),
            "commit": "a" * 40,
            "canonical_repository": "https://github.com/AIKAGRYA/dharma_swarm.git",
        }

    monkeypatch.setattr(taskpack_ops, "require_execution_source", _require)
    monkeypatch.setattr(
        taskpack_ops,
        "_model_cutoff_authority",
        lambda: {
            "active_profile_digest": "sha256:" + "b" * 64,
            "role_bindings": [],
            "cutoff_authority": "test_fixture_authority",
            "all_role_cutoffs_authoritative": True,
            "minimum_safe_cutoff": "2026-06-01T00:00:00Z",
        },
    )
    return repo


def _plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
    *,
    mode: taskpack_ops.TaskpackMode = taskpack_ops.MODE_GOVERNED_FRESH,
    rows: list[dict[str, Any]] | None = None,
) -> taskpack_ops.TaskpackPlan:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    manifest = tmp_path / f"{mode}.jsonl"
    selected_rows = rows or (
        [_search_row()]
        if mode == taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH
        else [_fresh_row()]
    )
    digest = _write_manifest(manifest, selected_rows)
    return taskpack_ops.plan_taskpack(
        manifest,
        manifest_digest=digest,
        model_cutoff="2026-06-01",
        mode=mode,
        repo=admitted_source,
    )


def test_status_missing_is_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "missing-state"
    monkeypatch.setenv("DHARMA_HOME", str(home))

    status = taskpack_ops.taskpack_status()

    assert status["ready"] is False
    assert status["exists"] is False
    assert status["reasons"] == ["taskbed_missing"]
    assert status["sqlite_mode"] == "mode=ro"
    assert not home.exists()


def test_status_rejects_partial_executor_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    db = taskpack_ops.anchored_taskbed_db()
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE taskbed_tasks (task_id TEXT, active INTEGER, "
            "created_at TEXT, first_seen_at REAL)"
        )
        connection.execute(
            "CREATE TABLE taskbed_allocations (task_id TEXT, split TEXT)"
        )

    status = taskpack_ops.taskpack_status()

    assert status["ready"] is False
    assert status["reasons"] == ["taskbed_schema_incompatible"]


def test_status_reads_wal_aware_anchored_ledger_with_executor_eligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    db = taskpack_ops.anchored_taskbed_db()
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE taskbed_tasks (
                task_id TEXT PRIMARY KEY,
                task_json TEXT NOT NULL,
                source TEXT NOT NULL,
                taskbed TEXT NOT NULL,
                contamination_state TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                first_seen_at REAL NOT NULL,
                active INTEGER NOT NULL,
                max_uses_per_epoch INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """CREATE TABLE taskbed_allocations (
                allocation_id TEXT NOT NULL, task_id TEXT NOT NULL,
                split TEXT NOT NULL, epoch_id TEXT NOT NULL,
                lane_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                allocated_at REAL NOT NULL, status TEXT NOT NULL
            )"""
        )
        connection.executemany(
            "INSERT INTO taskbed_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "fresh-1",
                    "{}",
                    "post_cutoff_pr_suite",
                    "fresh_pr_suite",
                    "fresh_post_cutoff",
                    "{}",
                    "2026-07-01T00:00:00Z",
                    1.0,
                    1,
                    1,
                ),
                (
                    "django__django-123",
                    "{}",
                    "official_swebench_search_only",
                    "search_only_public_swebench",
                    "possible_pretrain",
                    "{}",
                    "",
                    2.0,
                    1,
                    1,
                ),
                (
                    "old-disabled",
                    "{}",
                    "legacy",
                    "legacy",
                    "possible_pretrain",
                    "{}",
                    "",
                    3.0,
                    0,
                    1,
                ),
            ],
        )

    before = sorted(path.name for path in db.parent.iterdir())
    real_connect = taskpack_ops.sqlite3.connect
    observed: list[tuple[str, dict[str, Any]]] = []

    def _connect(database: str, **kwargs: Any) -> sqlite3.Connection:
        observed.append((str(database), dict(kwargs)))
        return real_connect(database, **kwargs)

    monkeypatch.setattr(taskpack_ops.sqlite3, "connect", _connect)
    status = taskpack_ops.taskpack_status()
    after = sorted(path.name for path in db.parent.iterdir())

    assert status["ready"] is True
    assert status["task_count"] == 3
    assert status["active_task_count"] == 2
    assert status["eligible_explore_task_count"] == 2
    assert status["next_explore_task_id"] == "django__django-123"
    assert status["contamination_state_counts"] == {
        "fresh_post_cutoff": 1,
        "possible_pretrain": 2,
    }
    assert "mode=ro" in observed[0][0]
    assert "immutable=1" not in observed[0][0]
    assert observed[0][1]["uri"] is True
    assert before == after
    assert not db.with_name("taskbed.db-wal").exists()
    assert not db.with_name("taskbed.db-shm").exists()


def test_status_observes_uncheckpointed_wal_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    db = taskpack_ops.anchored_taskbed_db()
    db.parent.mkdir(parents=True)
    writer = sqlite3.connect(db)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute(
            """
            CREATE TABLE taskbed_tasks (
                task_id TEXT PRIMARY KEY, task_json TEXT NOT NULL,
                source TEXT NOT NULL, taskbed TEXT NOT NULL,
                contamination_state TEXT NOT NULL, provenance_json TEXT NOT NULL,
                created_at TEXT NOT NULL, first_seen_at REAL NOT NULL,
                active INTEGER NOT NULL, max_uses_per_epoch INTEGER NOT NULL
            )
            """
        )
        writer.execute(
            """CREATE TABLE taskbed_allocations (
                allocation_id TEXT NOT NULL, task_id TEXT NOT NULL,
                split TEXT NOT NULL, epoch_id TEXT NOT NULL,
                lane_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                allocated_at REAL NOT NULL, status TEXT NOT NULL
            )"""
        )
        writer.execute(
            "INSERT INTO taskbed_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "django__django-456",
                "{}",
                "official_swebench_search_only",
                "search_only_public_swebench",
                "possible_pretrain",
                "{}",
                "",
                1.0,
                1,
                1,
            ),
        )
        writer.commit()

        status = taskpack_ops.taskpack_status()

        assert status["ready"] is True
        assert status["task_count"] == 1
        assert status["next_explore_task_id"] == "django__django-456"
    finally:
        writer.close()


def test_status_rejects_a_symlinked_taskbed_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    db = taskpack_ops.anchored_taskbed_db()
    db.parent.mkdir(parents=True)
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"not a ledger")
    db.symlink_to(outside)

    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.taskpack_status()

    assert error.value.code == "TASKBED_PATH_UNSAFE"
    assert outside.read_bytes() == b"not a ledger"


def test_plan_is_deterministic_and_seals_exact_strict_importer_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    first = _plan(tmp_path, monkeypatch, admitted_source)
    second = taskpack_ops.plan_taskpack(
        first["manifest"]["path"],
        manifest_digest=first["manifest"]["digest"],
        model_cutoff="2026-06-01T00:00:00Z",
        repo=admitted_source,
    )

    assert first == second
    assert first["plan_digest"].startswith("sha256:")
    assert first["model_cutoff"] == "2026-06-01T00:00:00Z"
    assert first["taskbed_db"] == str(tmp_path / "state/forge_v1/taskbed.db")
    assert first["oracle_preflight"]["derived_state_counts"] == {"fresh_post_cutoff": 1}
    assert first["custody"] == {
        "epistemic_modality": "ORACLE_FRESH_TASK_INTAKE",
        "promotion_eligible": True,
        "confirm_eligible": True,
        "public_pretraining_contamination_possible": False,
        "model_cutoff_authoritative": True,
        "custody_reason": "active_role_model_cutoffs_authoritatively_bounded",
    }
    assert first["model_cutoff_authority"]["all_role_cutoffs_authoritative"] is True
    argv = first["importer_argv"]
    assert argv[0] == str(Path(taskpack_ops.sys.executable).resolve())
    assert argv[1] == str(
        admitted_source / "scripts/runtime/forge_fresh_task_oracle.py"
    )
    assert argv[-1] == "--json"
    assert "--include-ineligible" not in argv
    assert argv[argv.index("--max-uses-per-epoch") + 1] == "1"
    assert not (tmp_path / "state").exists()


def test_plan_rejects_unsealed_implicit_pr_and_policy_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    cases = [
        ({"repo": "example/project", "pr_number": 1}, "MANIFEST_TASK_ID_REQUIRED"),
        (_fresh_row("pr::example/project#1"), "MANIFEST_PR_TASK_ID_FORBIDDEN"),
        ({**_fresh_row(), "max_uses_per_epoch": 2}, "MANIFEST_MAX_USES_POLICY"),
    ]
    for index, (row, code) in enumerate(cases):
        manifest = tmp_path / f"invalid-{index}.jsonl"
        digest = _write_manifest(manifest, [row])
        with pytest.raises(taskpack_ops.TaskpackError) as error:
            taskpack_ops.plan_taskpack(
                manifest,
                manifest_digest=digest,
                model_cutoff="2026-06-01",
                repo=admitted_source,
            )
        assert error.value.code == code

    valid = tmp_path / "valid.jsonl"
    digest = _write_manifest(valid, [_fresh_row()])
    with pytest.raises(taskpack_ops.TaskpackError, match="digest"):
        taskpack_ops.plan_taskpack(
            valid,
            manifest_digest="sha256:" + "0" * 64,
            model_cutoff="2026-06-01",
            repo=admitted_source,
        )
    with pytest.raises(taskpack_ops.TaskpackError) as outside:
        taskpack_ops.plan_taskpack(
            valid,
            manifest_digest=digest,
            model_cutoff="2026-06-01",
            taskbed_db=tmp_path / "outside.db",
            repo=admitted_source,
        )
    assert outside.value.code == "TASKBED_PATH_NOT_ANCHORED"


def test_search_only_mode_is_typed_public_possible_pretrain_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(
        tmp_path,
        monkeypatch,
        admitted_source,
        mode=taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH,
    )

    assert plan["policy"] == {
        "source": "official_swebench_search_only",
        "taskbed": "search_only_public_swebench",
        "max_uses_per_epoch": 1,
        "include_ineligible": True,
    }
    assert plan["oracle_preflight"]["derived_state_counts"] == {"possible_pretrain": 1}
    assert "--include-ineligible" in plan["importer_argv"]
    assert plan["custody"] == {
        "epistemic_modality": "EXPLORE_ONLY",
        "promotion_eligible": False,
        "confirm_eligible": False,
        "public_pretraining_contamination_possible": True,
        "model_cutoff_authoritative": True,
        "custody_reason": "public_swebench_possible_pretrain",
    }
    assert plan["epistemic_modality"] == "EXPLORE_ONLY"
    assert plan["promotion_eligible"] is False
    assert plan["confirm_eligible"] is False


def test_governed_fresh_requires_authoritative_active_role_cutoffs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    monkeypatch.setattr(
        taskpack_ops,
        "_model_cutoff_authority",
        lambda: {
            "active_profile_digest": None,
            "role_bindings": [],
            "cutoff_authority": "operator_supplied_unverified",
            "all_role_cutoffs_authoritative": False,
            "minimum_safe_cutoff": None,
        },
    )
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    manifest = tmp_path / "fresh.jsonl"
    digest = _write_manifest(manifest, [_fresh_row()])

    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.plan_taskpack(
            manifest,
            manifest_digest=digest,
            model_cutoff="2026-06-01",
            repo=admitted_source,
        )

    assert error.value.code == "MODEL_CUTOFF_AUTHORITY_REQUIRED"


@pytest.mark.parametrize(
    "row",
    [
        {**_search_row(), "instance_id": "not-an-official-id"},
        {**_search_row(), "created_at": "2026-07-01T00:00:00Z"},
        {key: value for key, value in _search_row().items() if key != "base_commit"},
        {key: value for key, value in _search_row().items() if key != "FAIL_TO_PASS"},
    ],
)
def test_search_only_mode_fails_closed_for_nonofficial_or_oracle_fresh_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
    row: dict[str, Any],
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))
    manifest = tmp_path / "search.jsonl"
    digest = _write_manifest(manifest, [row])

    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.plan_taskpack(
            manifest,
            manifest_digest=digest,
            model_cutoff="2026-06-01",
            mode=taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH,
            repo=admitted_source,
        )
    assert error.value.code in {
        "SEARCH_TASK_NOT_OFFICIAL_SWEBENCH",
        "SEARCH_TASK_CUSTODY_INVALID",
    }


def _importer_summary(plan: taskpack_ops.TaskpackPlan, *, secret: str = "") -> str:
    state = (
        "possible_pretrain"
        if plan["mode"] == taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH
        else "fresh_post_cutoff"
    )
    payload = {
        "schema": "forge_v2.fresh_task_oracle.v1",
        "source": plan["policy"]["source"],
        "taskbed": plan["policy"]["taskbed"],
        "model_cutoff": plan["model_cutoff"],
        "input_count": 1,
        "imported_count": 1,
        "skipped_count": 0,
        "imported_task_ids": [
            "django__django-123"
            if plan["mode"] == taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH
            else "fresh-task-1"
        ],
        "skipped": [],
        "derived_state_counts": {state: 1},
        "ledger_state_counts": {state: 1},
        "diagnostic": f"safe output {secret}",
        "api_key": secret,
    }
    return json.dumps(payload)


def test_apply_revalidates_runs_owned_importer_redacts_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    secret = "provider-secret-that-must-not-persist"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    plan = _plan(tmp_path, monkeypatch, admitted_source)
    calls: list[dict[str, Any]] = []

    def _run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=_importer_summary(plan, secret=secret),
            stderr=f"diagnostic accidentally contained {secret}",
        )

    monkeypatch.setattr(taskpack_ops.subprocess, "run", _run)
    first = taskpack_ops.apply_taskpack(
        plan,
        plan_digest=plan["plan_digest"],
        request_id="daily-fresh-20260827",
        timeout_seconds=12,
    )
    second = taskpack_ops.apply_taskpack(
        plan,
        plan_digest=plan["plan_digest"],
        request_id="daily-fresh-20260827",
        timeout_seconds=12,
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(calls) == 1
    assert calls[0]["argv"] == plan["importer_argv"]
    assert calls[0]["cwd"] == admitted_source.as_posix()
    assert calls[0]["timeout"] == 12
    assert secret not in json.dumps(calls[0]["env"])
    rendered = Path(first["receipt_path"]).read_text(encoding="utf-8")
    assert secret not in rendered
    receipt = first["receipt"]
    assert receipt["status"] == "succeeded"
    assert receipt["importer_result"]["diagnostic"].endswith("[REDACTED_SECRET]")
    assert receipt["importer_result"]["api_key"] == "[REDACTED_SECRET]"
    assert receipt["action_digest"].startswith("sha256:")


def test_apply_search_receipt_keeps_never_confirm_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(
        tmp_path,
        monkeypatch,
        admitted_source,
        mode=taskpack_ops.MODE_SEARCH_ONLY_PUBLIC_SWEBENCH,
    )

    def _run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            argv, 0, stdout=_importer_summary(plan), stderr=""
        )

    monkeypatch.setattr(taskpack_ops.subprocess, "run", _run)
    applied = taskpack_ops.apply_taskpack(
        plan,
        plan_digest=plan["plan_digest"],
        request_id="public-search-20260827",
    )

    assert applied["receipt"]["policy"]["include_ineligible"] is True
    assert applied["receipt"]["importer_argv_digest"].startswith("sha256:")
    assert applied["receipt"]["custody"]["epistemic_modality"] == "EXPLORE_ONLY"
    assert applied["receipt"]["custody"]["promotion_eligible"] is False
    assert applied["receipt"]["custody"]["confirm_eligible"] is False
    assert applied["receipt"]["epistemic_modality"] == "EXPLORE_ONLY"
    assert applied["receipt"]["promotion_eligible"] is False
    assert applied["receipt"]["confirm_eligible"] is False
    assert applied["epistemic_modality"] == "EXPLORE_ONLY"
    assert applied["promotion_eligible"] is False
    assert applied["confirm_eligible"] is False


def test_apply_runs_the_real_repository_importer_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "state"))

    def _require(candidate: Path | None = None) -> dict[str, Any]:
        assert candidate is None or Path(candidate).resolve() == repo
        return {
            "ready": True,
            "repo": str(repo),
            "commit": "b" * 40,
            "canonical_repository": "https://github.com/AIKAGRYA/dharma_swarm.git",
        }

    monkeypatch.setattr(taskpack_ops, "require_execution_source", _require)
    monkeypatch.setattr(
        taskpack_ops,
        "_model_cutoff_authority",
        lambda: {
            "active_profile_digest": "sha256:" + "b" * 64,
            "role_bindings": [],
            "cutoff_authority": "test_fixture_authority",
            "all_role_cutoffs_authoritative": True,
            "minimum_safe_cutoff": "2026-06-01T00:00:00Z",
        },
    )
    manifest = tmp_path / "actual-import.jsonl"
    digest = _write_manifest(manifest, [_fresh_row("fresh-e2e-1")])
    plan = taskpack_ops.plan_taskpack(
        manifest,
        manifest_digest=digest,
        model_cutoff="2026-06-01",
        repo=repo,
    )

    applied = taskpack_ops.apply_taskpack(
        plan,
        plan_digest=plan["plan_digest"],
        request_id="real-importer-e2e",
        timeout_seconds=30,
    )

    assert applied["receipt"]["status"] == "succeeded"
    assert applied["receipt"]["importer_result"]["imported_task_ids"] == ["fresh-e2e-1"]
    status = taskpack_ops.taskpack_status()
    assert status["ready"] is True
    assert status["task_count"] == 1
    assert status["contamination_state_counts"] == {"fresh_post_cutoff": 1}


def test_apply_rejects_same_size_wrong_or_duplicate_importer_task_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(tmp_path, monkeypatch, admitted_source)
    summary = json.loads(_importer_summary(plan))
    summary["imported_task_ids"] = ["wrong-task-id"]

    monkeypatch.setattr(
        taskpack_ops.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(summary), stderr=""
        ),
    )

    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.apply_taskpack(
            plan,
            plan_digest=plan["plan_digest"],
            request_id="wrong-importer-identity",
        )

    assert error.value.code == "IMPORTER_RESULT_MISMATCH"
    assert error.value.receipt_path is not None


def test_apply_rejects_manifest_or_source_drift_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(tmp_path, monkeypatch, admitted_source)
    Path(plan["manifest"]["path"]).write_text("{}\n", encoding="utf-8")
    called = False

    def _run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        raise AssertionError("subprocess must not run after drift")

    monkeypatch.setattr(taskpack_ops.subprocess, "run", _run)
    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.apply_taskpack(
            plan,
            plan_digest=plan["plan_digest"],
            request_id="drifted-manifest",
        )
    assert error.value.code == "MANIFEST_DIGEST_MISMATCH"
    assert called is False


def test_failed_apply_is_receipted_and_not_unsafely_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(tmp_path, monkeypatch, admitted_source)
    calls = 0

    def _run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="bounded failure")

    monkeypatch.setattr(taskpack_ops.subprocess, "run", _run)
    for _ in range(2):
        with pytest.raises(taskpack_ops.TaskpackError) as error:
            taskpack_ops.apply_taskpack(
                plan,
                plan_digest=plan["plan_digest"],
                request_id="failed-once",
            )
        assert error.value.code == "IMPORTER_FAILED"
        assert error.value.receipt_path is not None
    assert calls == 1
    receipt = json.loads(error.value.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["importer_returncode"] == 2


def test_terminal_receipt_durability_failure_surfaces_unknown_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    admitted_source: Path,
) -> None:
    plan = _plan(tmp_path, monkeypatch, admitted_source)
    calls = 0

    def _run(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(
            argv, 0, stdout=_importer_summary(plan), stderr=""
        )

    original_write = taskpack_apply.write_json_exclusive

    def _write(path: Path, payload: dict[str, Any]) -> None:
        if path.name.endswith(".json") and not path.name.endswith(".intent.json"):
            raise OSError("simulated terminal receipt failure")
        original_write(path, payload)

    monkeypatch.setattr(taskpack_ops.subprocess, "run", _run)
    monkeypatch.setattr(taskpack_apply, "write_json_exclusive", _write)
    with pytest.raises(taskpack_ops.TaskpackError) as error:
        taskpack_ops.apply_taskpack(
            plan,
            plan_digest=plan["plan_digest"],
            request_id="unknown-after-import",
        )

    assert error.value.code == "APPLY_OUTCOME_UNKNOWN"
    assert error.value.receipt_path is not None
    assert error.value.receipt_path.name.endswith(".intent.json")
    assert calls == 1
