from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import grader_runtime, operator_views, provider_selftest
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_lab.version import PACKAGE_VERSION, source_commit


@pytest.fixture
def anchored_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "rsi-lab"
    state = root / "state"
    monkeypatch.setenv("RSI_LAB_ROOT", str(root))
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.setenv("DHARMA_HOME", str(state / ".dharma"))
    monkeypatch.setenv("RSI_LAB_LEGACY_BIN", str(root / "bin"))
    return root, state


def test_legacy_refresh_duplication_and_state_split_are_detected_without_values(
    anchored_state: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _state = anchored_state
    legacy_bin = root / "bin"
    legacy_bin.mkdir(parents=True)
    (legacy_bin / "rsi-keys-refresh").write_text("legacy", encoding="utf-8")
    receipt = root / "current-main" / "state" / ".dharma" / "keys_status.json"
    receipt.parent.mkdir(parents=True)
    secret = "must-not-appear-in-doctor"
    receipt.write_text(
        json.dumps(
            {
                "rows": [
                    {"name": "kimi", "glyph": "ok", "status": "probe_http_200"},
                    {"name": "moonshot", "glyph": "ok", "status": "probe_http_200"},
                ],
                "unrelated_secret": secret,
            }
        ),
        encoding="utf-8",
    )
    log_dir = root / "current-main" / "state" / "rsi_runs"
    log_dir.mkdir(parents=True)
    monkeypatch.setenv(
        "RSI_LAB_CRONTAB_TEXT",
        "*/10 * * * * /root/rsi-lab/bin/rsi-keys-refresh "
        ">> /root/rsi-lab/current-main/state/rsi_runs/keys.log 2>&1\n",
    )

    status = operator_views.legacy_control_status()

    assert status["ready"] is False
    assert status["retirement_required"] is True
    assert "legacy_rsi_keys_refresh_cron_active" in status["hazards"]
    assert "legacy_provider_state_split_present" in status["hazards"]
    assert "kimi_moonshot_same_probe_projection_detected" in status["hazards"]
    assert "versioned_provider_refresh_entries:0/1" in status["hazards"]
    assert status["replacement"] == "rsi-provider-refresh"
    assert status["replacement_installer"] == "rsi-provider-refresh-install"
    assert secret not in json.dumps(status)


def test_exactly_one_versioned_refresh_entry_is_ready(
    anchored_state: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "RSI_LAB_CRONTAB_TEXT",
        "17 * * * * /root/rsi-lab/bin/rsi-provider-refresh "
        ">> /root/rsi-lab/state/provider_refresh.log 2>&1\n",
    )

    status = operator_views.legacy_control_status()

    assert status["ready"] is True
    assert status["hazards"] == []
    assert status["retirement_required"] is False
    assert status["cron"]["versioned_refresh_entries"] == 1


def test_provider_readiness_requires_fresh_live_callable_independent_routes(
    anchored_state: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, state = anchored_state
    receipts = state / ".dharma" / "forge_lab" / "provider_selftests"
    receipts.mkdir(parents=True)
    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(receipts))
    path = receipts / "latest__staged__provider_selftest.json"
    policy = {
        "source": {
            "package_version": PACKAGE_VERSION,
            "commit": source_commit(),
            "tree_state": "clean",
        },
        "configuration": {
            "profile": "staged",
            "current_model": None,
            "requested_models": ["route-a", "route-b"],
        },
        "probe_policy": {
            "require_independent_routes": 2,
            "timeout_s": 20,
            "max_provider_calls": 4,
            "alias_policy": provider_selftest.ALIAS_POLICY_VERSION,
        },
    }
    payload = {
        "schema": provider_selftest.PROVIDER_SELFTEST_SCHEMA,
        "ok": True,
        "live": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "callable_count": 0,
        "independent_route_count": 2,
        "policy": policy,
        "policy_digest": content_digest(policy),
        "receipt_id": "doctor-test",
        "receipt": str(path),
        "cached": False,
    }
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert operator_views.provider_readiness()["ready"] is False
    assert "zero_callable_routes" in operator_views.provider_readiness()["reasons"]

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["callable_count"] = 2
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    ready = operator_views.provider_readiness()
    assert ready["ready"] is True
    assert ready["independent_route_count"] == 2

    payload["checked_at"] = "2999-01-01T00:00:00Z"
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    future = operator_views.provider_readiness()
    assert future["ready"] is False
    assert future["age_seconds"] < 0
    assert "provider_receipt_stale_or_unparseable" in future["reasons"]


def test_read_only_worker_alert_archive_and_reconcile_surfaces(
    anchored_state: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _root, state = anchored_state
    forge = state / ".dharma" / "forge_lab"
    workers = forge / "workers"
    alerts = forge / "alerts"
    workers.mkdir(parents=True)
    alerts.mkdir(parents=True)
    (workers / "worker-1.json").write_text(
        json.dumps({"worker_id": "worker-1", "state": "offline"}), encoding="utf-8"
    )
    (alerts / "alerts.jsonl").write_text(
        json.dumps({"alert_id": "alert-1", "at": "2026-08-25T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    archive = state / ".dharma" / "evolution_archive" / "agent_evolution" / "exp-1"
    archive.mkdir(parents=True)
    (archive / "run_manifest.json").write_text(
        json.dumps({"experiment_id": "exp-1"}), encoding="utf-8"
    )
    monkeypatch.setenv("RSI_LAB_CRONTAB_TEXT", "")

    assert operator_views.list_workers() == {
        "workers": [{"worker_id": "worker-1", "state": "offline"}],
        "count": 1,
        "read_only": True,
    }
    alert_view = operator_views.list_alerts()
    assert alert_view["count"] == 1
    assert alert_view["read_only"] is True
    archive_view = operator_views.inspect_archive()
    assert archive_view["count"] == 1
    assert archive_view["experiments"][0]["experiment_id"] == "exp-1"
    report = operator_views.reconcile()
    assert report["read_only"] is True
    assert any(
        row["code"] == "LEGACY_CONTROL_DRIFT"
        and row["detail"] == "versioned_provider_refresh_entries:0/1"
        for row in report["findings"]
    )


def test_state_anchor_refuses_divergent_dharma_home(
    anchored_state: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "other"))
    status = operator_views.state_anchor_status()
    assert status["ready"] is False
    assert status["reasons"] == ["DHARMA_HOME_not_anchored_under_RSI_LAB_STATE"]


def test_swebench_runtime_is_api_and_import_root_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "venv" / "lib" / "python3.12" / "site-packages"
    root.mkdir(parents=True)

    def module(name: str) -> SimpleNamespace:
        path = root / name.replace(".", "_") / "__init__.py"
        path.parent.mkdir()
        path.write_text("", encoding="utf-8")
        return SimpleNamespace(__file__=str(path))

    runtime_names = (
        "swebench",
        "docker",
        "datasets",
        "huggingface_hub",
        "pyarrow",
    )
    modules = {name: module(name) for name in runtime_names}
    run_evaluation_path = root / "swebench" / "harness" / "run_evaluation.py"
    run_evaluation_path.parent.mkdir()
    run_evaluation_path.write_text("", encoding="utf-8")
    run_evaluation = SimpleNamespace(__file__=str(run_evaluation_path))
    for name in (
        "build_container",
        "cleanup_container",
        "copy_to_container",
        "exec_run_with_timeout",
        "load_swebench_dataset",
        "make_test_spec",
        "main",
    ):
        setattr(run_evaluation, name, lambda: None)
    modules["swebench.harness.run_evaluation"] = run_evaluation
    distributions: dict[str, SimpleNamespace] = {}
    expected_digests: dict[str, str] = {}
    expected_tree_digests: dict[str, str] = {}
    for name in runtime_names:
        dist = root / f"{name}.dist-info"
        dist.mkdir()
        record = dist / "RECORD"
        record_paths = [f"{name}/__init__.py", f"{name}.dist-info/RECORD"]
        if name == "swebench":
            record_paths.append("swebench/harness/run_evaluation.py")
        record.write_text(
            "".join(f"{path},,\n" for path in record_paths),
            encoding="utf-8",
        )
        distributions[name] = SimpleNamespace(_path=dist)
        expected_digests[name] = (
            "sha256:" + hashlib.sha256(record.read_bytes()).hexdigest()
        )
        mapping = {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in record_paths
        }
        canonical = json.dumps(
            mapping,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_tree_digests[name] = (
            "sha256:" + hashlib.sha256(canonical).hexdigest()
        )
    monkeypatch.setenv("RSI_LAB_SWEBENCH_PYDEPS", str(root))
    import_calls: list[str] = []

    def import_module(name: str) -> SimpleNamespace:
        import_calls.append(name)
        return modules[name]

    monkeypatch.setattr(grader_runtime.importlib, "import_module", import_module)
    monkeypatch.setattr(
        grader_runtime.importlib.metadata,
        "version",
        lambda _name: grader_runtime.SUPPORTED_SWEBENCH_VERSION,
    )
    monkeypatch.setattr(
        grader_runtime.importlib.metadata,
        "distribution",
        lambda name: distributions[name],
    )
    monkeypatch.setattr(
        grader_runtime,
        "SUPPORTED_LINUX_RUNTIME_RECORD_DIGESTS",
        expected_digests,
    )
    monkeypatch.setattr(
        grader_runtime,
        "SUPPORTED_LINUX_RUNTIME_TREE_DIGESTS",
        expected_tree_digests,
    )

    ready = operator_views.swebench_runtime_readiness()
    assert ready["ready"] is True
    assert ready["api_compatible"] is True
    assert ready["distribution_custody_verified_before_import"] is True
    assert ready["module_origins_attested"] is True
    imported_after_ready = list(import_calls)
    assert set(ready["record_origins"]) == set(runtime_names)
    expected_counts = dict.fromkeys(runtime_names, 2)
    expected_counts["swebench"] = 3
    assert ready["tree_file_counts"] == expected_counts

    docker_module = root / "docker" / "__init__.py"
    docker_module.write_text("tampered\n", encoding="utf-8")
    tampered = operator_views.swebench_runtime_readiness()
    assert tampered["ready"] is False
    assert "swebench_runtime_docker_tree_mismatch" in tampered["reasons"]
    assert import_calls == imported_after_ready
    docker_module.write_text("", encoding="utf-8")

    pyarrow_origin = modules["pyarrow"].__file__
    modules["pyarrow"].__file__ = str(tmp_path / "escaped" / "pyarrow.py")
    escaped = operator_views.swebench_runtime_readiness()
    assert escaped["ready"] is False
    assert "swebench_runtime_import_escaped_anchor" in escaped["reasons"]
    modules["pyarrow"].__file__ = pyarrow_origin

    run_evaluation.exec_run_with_timeout = None
    incompatible = operator_views.swebench_runtime_readiness()
    assert incompatible["ready"] is False
    assert "swebench_runtime_api_incompatible" in incompatible["reasons"]

    (root / "docker.dist-info" / "RECORD").chmod(0o666)
    root.chmod(0o777)
    writable = operator_views.swebench_runtime_readiness()
    assert writable["ready"] is False
    assert "swebench_runtime_anchor_writable" in writable["reasons"]


def test_swebench_runtime_refuses_missing_required_dedicated_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RSI_LAB_SWEBENCH_PYDEPS", raising=False)
    monkeypatch.setenv("RSI_LAB_REQUIRE_SWEBENCH_PYDEPS", "1")

    readiness = operator_views.swebench_runtime_readiness()

    assert readiness["ready"] is False
    assert "swebench_runtime_dedicated_required" in readiness["reasons"]


def test_grader_requires_python_sdk_ping_not_only_docker_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RSI_LAB_GRADER_MODE", "official-swebench-docker")
    monkeypatch.setattr(operator_views.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(
        operator_views.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "27.0\n", ""),
    )
    monkeypatch.setattr(
        operator_views,
        "swebench_runtime_readiness",
        lambda: {"ready": True, "reasons": []},
    )
    monkeypatch.setattr(
        operator_views,
        "_docker_sdk_status",
        lambda: (False, "docker_sdk_TLSParameterError"),
    )

    readiness = operator_views.grader_readiness()

    assert readiness["ready"] is False
    assert readiness["docker_daemon_reachable"] is True
    assert readiness["docker_sdk_daemon_reachable"] is False
    assert "docker_sdk_TLSParameterError" in readiness["reasons"]


def test_taskbed_readiness_is_read_only_and_state_anchored(
    anchored_state: tuple[Path, Path],
) -> None:
    _root, state = anchored_state
    missing = operator_views.taskbed_readiness()
    assert missing["ready"] is False
    assert missing["reasons"] == ["anchored_taskbed_missing_or_unsafe"]

    path = state / ".dharma" / "forge_v1" / "taskbed.db"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE taskbed_tasks (
              task_id TEXT PRIMARY KEY,
              task_json TEXT NOT NULL,
              source TEXT NOT NULL,
              taskbed TEXT NOT NULL,
              contamination_state TEXT NOT NULL,
              provenance_json TEXT NOT NULL,
              active INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              first_seen_at REAL NOT NULL,
              max_uses_per_epoch INTEGER NOT NULL
            );
            CREATE TABLE taskbed_allocations (
              allocation_id TEXT NOT NULL,
              task_id TEXT NOT NULL,
              split TEXT NOT NULL,
              epoch_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              candidate_id TEXT NOT NULL,
              allocated_at REAL NOT NULL,
              status TEXT NOT NULL
            );
            INSERT INTO taskbed_tasks VALUES
              ('fixture-task', '{}', 'official_swebench_search_only',
               'search_only_public_swebench', 'possible_pretrain', '{}', 1,
               '2026-08-25T00:00:00Z', 1.0, 1);
            INSERT INTO taskbed_tasks VALUES
              ('pr::host-unsafe', '{}', 'post_cutoff_pr_suite', 'fresh_pr_suite',
               'fresh_post_cutoff', '{}', 1, '2026-08-24T00:00:00Z', 0.5, 1);
            """
        )

    ready = operator_views.taskbed_readiness()
    assert ready["ready"] is True
    assert ready["eligible_explore_tasks"] == 1
    assert ready["next_explore_task_id"] == "fixture-task"
    assert ready["read_only"] is True
