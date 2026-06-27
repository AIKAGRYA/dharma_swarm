from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _load_closeout_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "runtime_truth_closeout.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_truth_closeout", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _clean_census(state_root: Path, *, db_path: Path | None = None) -> dict:
    runtime_db = db_path or state_root / "state" / "runtime.db"
    return {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-18T16:58:15+00:00",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "status": "live",
                "proof_gaps": [],
                "raw": {
                    "runtime_truth_clean_epoch": {
                        "enabled": True,
                        "receipt_verified": True,
                        "receipt_id": "rr-runtime-truth-clean-epoch",
                        "evidence": "active-head runtime truth is scoped",
                    },
                    "runtime_receipt_active_head": {
                        "active_head_side_effect_key_clean": True,
                        "evidence": "recent runtime receipt head is clean",
                    },
                    "runtime_receipt_since_boot": {
                        "since_boot_major_identity_clean": True,
                        "evidence": "current daemon boot major receipts have required keys",
                    },
                    "runtime_receipt_coverage": {
                        "db_path": str(runtime_db),
                        "coverage_report_available": True,
                        "scope_mode": "since_created_at",
                        "scope_since_created_at": "2026-06-18T16:57:22+00:00",
                        "latest_sample_size": 50,
                        "latest_terminal_sample_size": 20,
                        "provider_model_latest_complete": True,
                        "provider_model_readiness_basis": "latest_major_accounted",
                        "latest_major_task_receipts_provider_model_accounted_percent": 100.0,
                        "latest_terminal_major_task_receipts_provider_model_accounted_percent": 100.0,
                        "blockers": [],
                        "production_readiness_blockers": [],
                    },
                },
            }
        ],
    }


def _write_tasks_db(
    state_root: Path,
    *,
    rows: list[tuple[str, str, int]] | None = None,
) -> None:
    db_path = state_root / "db" / "tasks.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                priority TEXT NOT NULL
            )
            """
        )
        index = 0
        for status, priority, count in rows or []:
            for _ in range(count):
                index += 1
                db.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?)",
                    (f"task-{index}", status, priority),
                )


def _write_runtime_db(
    state_root: Path,
    *,
    clean_epoch_count: int = 1,
    epoch_created_ats: list[str] | None = None,
) -> None:
    db_path = state_root / "state" / "runtime.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                receipt_type TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                causation_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                side_effect_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        if epoch_created_ats is None:
            created_ats = [
                f"2026-06-18T16:5{index}:22+00:00"
                for index in range(clean_epoch_count)
            ]
        else:
            created_ats = list(epoch_created_ats)
        for index, created_at in enumerate(created_ats):
            db.execute(
                """
                INSERT INTO runtime_receipts (
                    receipt_id,
                    receipt_type,
                    status,
                    payload_json,
                    created_at
                )
                VALUES (?, 'runtime_truth_clean_epoch', 'active', '{}', ?)
                """,
                (
                    f"rr-runtime-truth-clean-epoch-{index + 1}",
                    created_at,
                ),
            )


def _failed_check_ids(result: dict) -> set[str]:
    return {
        check["id"]
        for check in result["checks"]
        if check["status"] == "fail"
    }


def test_runtime_truth_closeout_passes_clean_unpaused_state(tmp_path: Path) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(state_root)
    _write_runtime_db(state_root)

    result = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
    )

    assert result["passed"] is True
    assert _failed_check_ids(result) == set()


def test_runtime_truth_closeout_fails_pause_unless_allowed(tmp_path: Path) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(state_root)
    _write_runtime_db(state_root)
    (state_root / ".PAUSE").parent.mkdir(parents=True, exist_ok=True)
    (state_root / ".PAUSE").write_text("paused\n", encoding="utf-8")

    strict = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
    )
    allowed = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
        allow_paused=True,
    )

    assert strict["passed"] is False
    assert _failed_check_ids(strict) == {"daemon_unpaused"}
    assert allowed["passed"] is True


def test_runtime_truth_closeout_fails_noncanonical_runtime_db(tmp_path: Path) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(state_root)
    _write_runtime_db(state_root)

    result = module.evaluate_closeout(
        _clean_census(state_root, db_path=tmp_path / "runtime.db"),
        state_root=state_root,
    )

    assert result["passed"] is False
    assert "canonical_runtime_db" in _failed_check_ids(result)


def test_runtime_truth_closeout_fails_unpaused_burn_in_when_backlog_unsafe(
    tmp_path: Path,
) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(
        state_root,
        rows=[
            ("pending", "high", 26),
            ("pending", "normal", 75),
            ("running", "normal", 1),
        ],
    )
    _write_runtime_db(state_root)

    strict = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
    )
    paused = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
        allow_paused=True,
    )

    assert strict["passed"] is False
    assert "unpaused_burn_in_preflight" in _failed_check_ids(strict)
    assert strict["unpaused_burn_in_preflight"]["pending_high_or_urgent"] == 26
    assert paused["passed"] is True


def test_runtime_truth_closeout_fails_repeated_recent_clean_epoch_declarations(
    tmp_path: Path,
) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(state_root)
    recent = datetime.now(UTC)
    _write_runtime_db(
        state_root,
        epoch_created_ats=[
            (recent - timedelta(hours=1)).isoformat(),
            (recent - timedelta(hours=2)).isoformat(),
        ],
    )

    result = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
    )

    assert result["passed"] is False
    assert "clean_epoch_declarations_bounded" in _failed_check_ids(result)


def test_runtime_truth_closeout_old_clean_epochs_do_not_trip_bound(
    tmp_path: Path,
) -> None:
    # Regression: runtime_receipts is append-only, so an all-time epoch count
    # can never shrink. 16 historical epochs (the real 2026-06-20 state) must
    # NOT make the bound permanently red when there is no recent churn.
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_tasks_db(state_root)
    _write_runtime_db(
        state_root,
        epoch_created_ats=[
            f"2026-05-{day:02d}T12:00:00+00:00" for day in range(1, 17)
        ],
    )

    result = module.evaluate_closeout(
        _clean_census(state_root),
        state_root=state_root,
    )

    assert "clean_epoch_declarations_bounded" not in _failed_check_ids(result)
    assert result["passed"] is True


def test_clean_epoch_summary_windows_recent_declarations(tmp_path: Path) -> None:
    module = _load_closeout_module()
    state_root = tmp_path / ".dharma"
    _write_runtime_db(
        state_root,
        epoch_created_ats=[
            "2026-06-18T10:00:00+00:00",
            "2026-06-18T11:00:00+00:00",
            "2026-06-20T09:00:00+00:00",
            "2026-06-20T11:30:00+00:00",
        ],
    )

    summary = module._clean_epoch_declaration_summary(
        state_root,
        lookback_hours=24.0,
        now=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    assert summary["total_count"] == 4
    assert summary["recent_count"] == 2
    assert summary["count"] == 2
