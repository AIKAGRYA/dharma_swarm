from __future__ import annotations

import ast
import json
import os
import plistlib
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.holon_persistence import save_cycle_record
from dharma_swarm.holon_service_liveness import record_service_heartbeat
from dharma_swarm.operator_core.control_surface import (
    _rows_from_live_ops_census,
    build_control_surface_summary,
)
from dharma_swarm.operator_core.control_surface_models import (
    _build_human_decision_context,
)
import dharma_swarm.operator_core.control_surface_live_ops as live_ops_adapter
import dharma_swarm.operator_core.live_ops_census_contract as live_ops_census_contract
import scripts.runtime.live_ops_census as live_ops_census
from scripts.runtime.live_ops_census import AUTHORITY_SOURCES, build_live_ops_census


REPO_ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_spine_launch_plist(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "com.dharma.swarm.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && exec env PYTHONPATH=/Users/dhyana/dharma_swarm TINY_ROUTER_BACKEND=heuristic ./.venv/bin/python -m dharma_swarm.dgc_cli orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )


def _write_runtime_receipts_db(
    db_path: Path,
    rows: list[tuple[str, str, str]],
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                side_effect_key TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        db.executemany(
            """
            INSERT INTO runtime_receipts (receipt_id, side_effect_key, created_at)
            VALUES (?, ?, ?)
            """,
            rows,
        )


def _write_runtime_coverage_db(db_path: Path, payload: dict[str, object]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript(
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
            );
            CREATE TABLE idempotency_records (
                idempotency_key TEXT NOT NULL,
                side_effect_key TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                result_receipt_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, side_effect_key)
            );
            CREATE TABLE delegation_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                claim_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                failure_code TEXT NOT NULL DEFAULT '',
                receipt_json TEXT NOT NULL DEFAULT '',
                current_artifact_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE execution_identities (
                identity_id TEXT PRIMARY KEY
            );
            CREATE TABLE task_claims (
                claim_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                claimed_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE artifact_records (
                artifact_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT ''
            );
            """
        )
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "receipt-coverage-1",
                "a2a_task",
                "run-coverage-1",
                "task-coverage-1",
                "trace-coverage-1",
                "corr-coverage-1",
                "agent-coverage-1",
                "idem-coverage-1",
                "side-coverage-1",
                "completed",
                json.dumps(payload),
                "2026-06-14T00:10:00+00:00",
            ),
        )
        db.execute(
            """
            INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "idem-coverage-1",
                "side-coverage-1",
                "run-coverage-1",
                "task-coverage-1",
                "trace-coverage-1",
                "corr-coverage-1",
                "completed",
                "receipt-coverage-1",
                "{}",
                "2026-06-14T00:09:00+00:00",
                "2026-06-14T00:10:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-coverage-1",
                "session-coverage-1",
                "claim-coverage-1",
                "completed",
                "",
                "{}",
                "artifact-coverage-1",
                json.dumps({"mission_id": "mission-coverage-1"}),
            ),
        )
        db.execute(
            "INSERT INTO execution_identities VALUES (?)",
            ("identity-coverage-1",),
        )
        db.execute(
            "INSERT INTO task_claims VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "claim-coverage-1",
                "session-coverage-1",
                "task-coverage-1",
                "agent-coverage-1",
                "completed",
                json.dumps({"mission_id": "mission-coverage-1"}),
                "2026-06-14T00:09:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO artifact_records VALUES (?, ?, ?)",
            ("artifact-coverage-1", "run-coverage-1", "task-coverage-1"),
        )
        db.commit()


def _write_runtime_truth_clean_epoch(
    *,
    state_root: Path,
    db_path: Path,
    since_created_at: str,
) -> None:
    receipt_id = "rr-runtime-truth-clean-epoch"
    epoch = {
        "schema_version": "runtime_truth_clean_epoch.v1",
        "created_at": since_created_at,
        "since_created_at": since_created_at,
        "reason": "test clean epoch",
        "historical_dirt_policy": "historical dirty receipts are not rewritten",
        "db_path": str(db_path),
        "receipt_id": receipt_id,
        "receipt_type": "runtime_truth_clean_epoch",
    }
    epoch_path = state_root / "state" / "runtime_truth_clean_epoch.json"
    epoch_path.parent.mkdir(parents=True, exist_ok=True)
    epoch_path.write_text(json.dumps(epoch), encoding="utf-8")
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                "runtime_truth_clean_epoch",
                "run-runtime-truth-clean-epoch",
                "runtime-truth-clean-epoch",
                "trace-runtime-truth-clean-epoch",
                "corr-runtime-truth-clean-epoch",
                "operator.runtime_truth",
                "idem-runtime-truth-clean-epoch",
                "side-runtime-truth-clean-epoch",
                "active",
                json.dumps({
                    "schema_version": "runtime_truth_clean_epoch.v1",
                    "since_created_at": since_created_at,
                    "reason": "test clean epoch",
                }),
                since_created_at,
            ),
        )
        db.commit()


def test_daemon_process_pattern_matches_module_and_console_script() -> None:
    pattern = live_ops_census.PROCESS_PATTERNS["dharma_daemon"]
    assert re.search(pattern, "python -m dharma_swarm.dgc_cli orchestrate-live")
    assert re.search(
        pattern,
        "cd /Users/dhyana/dharma_swarm && exec env PYTHONPATH=/Users/dhyana/dharma_swarm ./.venv/bin/python -m dharma_swarm.dgc_cli orchestrate-live",
    )
    assert re.search(pattern, "/opt/homebrew/bin/dgc orchestrate-live")
    assert re.search(
        pattern,
        "/bin/bash -c cd /Users/dhyana/dharma_swarm && source .env && dgc orchestrate-live",
    )


def test_cron_process_pattern_matches_module_and_console_script() -> None:
    pattern = live_ops_census.PROCESS_PATTERNS["dharma_cron"]
    assert re.search(pattern, "python -m dharma_swarm.dgc_cli cron daemon")
    assert re.search(
        pattern,
        "cd /Users/dhyana/dharma_swarm && exec env PYTHONPATH=/Users/dhyana/dharma_swarm ./.venv/bin/python -m dharma_swarm.dgc_cli cron daemon",
    )
    assert re.search(pattern, "/opt/homebrew/bin/dgc cron daemon")
    assert re.search(
        pattern,
        "/bin/bash -lc cd /Users/dhyana/dharma_swarm_live && exec /opt/homebrew/bin/dgc cron daemon",
    )


def test_process_snapshot_falls_back_to_launchctl_for_dharma_daemon(monkeypatch) -> None:
    def fake_run(args: list[str], *, cwd=None, timeout: int = 5) -> tuple[int, str]:
        if args[:2] == ["pgrep", "-fl"]:
            return 3, "pgrep: Cannot get process list"
        if args == ["launchctl", "print", "gui/501/com.dharma.swarm"]:
            return (
                0,
                """
gui/501/com.dharma.swarm = {
    state = running
    pid = 12345
}
                """,
            )
        if args == ["launchctl", "print", "gui/501/com.dharma.cron-daemon"]:
            return 1, "not loaded"
        raise AssertionError(args)

    monkeypatch.setattr(live_ops_census.os, "getuid", lambda: 501)
    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    snapshot = live_ops_census._process_snapshot(run_probes=True)

    assert snapshot["dharma_daemon"] == [
        {
            "pid": "12345",
            "command": "launchctl:com.dharma.swarm state=running",
        }
    ]


def test_process_snapshot_falls_back_to_launchctl_for_dharma_cron(monkeypatch) -> None:
    def fake_run(args: list[str], *, cwd=None, timeout: int = 5) -> tuple[int, str]:
        if args[:2] == ["pgrep", "-fl"]:
            return 3, "sysmon request failed with error: sysmond service not found"
        if args == ["launchctl", "print", "gui/501/com.dharma.cron-daemon"]:
            return (
                0,
                """
gui/501/com.dharma.cron-daemon = {
    state = running
    pid = 793
}
                """,
            )
        if args == ["launchctl", "print", "gui/501/com.dharma.swarm"]:
            return 1, "not loaded"
        raise AssertionError(args)

    monkeypatch.setattr(live_ops_census.os, "getuid", lambda: 501)
    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    snapshot = live_ops_census._process_snapshot(run_probes=True)

    assert snapshot["dharma_cron"] == [
        {
            "pid": "793",
            "command": "launchctl:com.dharma.cron-daemon state=running",
        }
    ]


def test_terminal_tui_process_pattern_avoids_generic_terminal_history() -> None:
    pattern = live_ops_census.PROCESS_PATTERNS["terminal_tui"]
    assert re.search(pattern, "tmux new-session -d -s dharma_terminal_tui")
    assert re.search(pattern, "cd /Users/dhyana/dharma_swarm/terminal && bun run src/index.tsx")
    assert re.search(pattern, "bun /Users/dhyana/dharma_swarm/terminal/src/index.tsx")
    assert not re.search(
        pattern,
        "Codex Computer Use turn-ended last-assistant-message='restart terminal later'",
    )


def test_lsof_listener_parser_extracts_owner_processes() -> None:
    output = "\n".join(
        [
            "COMMAND   PID   USER   FD   TYPE DEVICE SIZE/OFF NODE NAME",
            "Python  777 dhyana   12u  IPv4 0xabc      0t0  TCP 127.0.0.1:7433 (LISTEN)",
            "Python  777 dhyana   13u  IPv6 0xdef      0t0  TCP [::1]:7433 (LISTEN)",
        ]
    )

    assert live_ops_census._parse_lsof_listeners(output) == [
        {
            "pid": "777",
            "command": "Python",
            "listen_name": "127.0.0.1:7433 (LISTEN)",
            "source": "lsof_listen",
        }
    ]


def test_process_start_snapshot_records_probe_errors(monkeypatch) -> None:
    def fake_run(args, **_kwargs):  # noqa: ANN001
        assert args[:3] == ["ps", "-o", "lstart="]
        return 127, "[Errno 1] Operation not permitted: 'ps'"

    monkeypatch.setattr(live_ops_census, "_darwin_process_start_time", lambda _pid: ("", ""))
    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    starts = live_ops_census._process_start_snapshot(
        {"dharma_daemon": [{"pid": "777", "command": "Python"}]},
        run_probes=True,
    )

    assert live_ops_census._process_start_probe_errors(starts["dharma_daemon"]) == [
        {"pid": "777", "error": "[Errno 1] Operation not permitted: 'ps'"}
    ]


def test_process_start_snapshot_prefers_libproc_start_time(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("ps fallback should not run after libproc start proof")

    monkeypatch.setattr(
        live_ops_census,
        "_darwin_process_start_time",
        lambda _pid: ("2026-06-13T13:55:10Z", ""),
    )
    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    starts = live_ops_census._process_start_snapshot(
        {"dharma_daemon": [{"pid": "777", "command": "Python"}]},
        run_probes=True,
    )

    assert starts["dharma_daemon"] == {"777": "2026-06-13T13:55:10Z"}


def test_live_ops_census_folds_in_canonical_sources(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    for source in AUTHORITY_SOURCES:
        _write(repo / source["path"])
    _write(
        state / "state" / "revenue_wedge_last_state.json",
        json.dumps(
            {
                "gauntlet_decision": "HOLD",
                "human_approved_outreach": False,
                "revenue_usd": 0,
                "fire_ts": "2026-06-02T00:00:00Z",
            }
        ),
    )
    _write(
        state / "forge_reality_arena_master" / "codex_overnight_heartbeat.json",
        json.dumps({"ts": "2026-06-02T00:00:00Z", "status": "handoff"}),
    )
    _write(state / "a2a_bus" / "receipts" / "hermes" / "receipt_1.json", "{}")
    _write(state / "a2a_bus" / "messages" / "message_1.json", "{}")
    _write(state / "a2a_bus" / "tasks" / "queue.jsonl", "{}\n")
    _write(state / "a2a_bus" / "nats_live_receipt.json", "{}")
    _write(state / "a2a_bus" / "nats_contact_receipts.jsonl", "{}\n")
    _write(state / "a2a_bus" / "nats_oz_receipts.jsonl", "{}\n")
    _write(state / "nats" / "receipts" / "receipt_1.json", "{}")
    _write(state / "nats" / "nats-server.log", "ready\n")

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
            "nats": [{"pid": "102", "command": "nats-server local-nats.conf"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
            "nats": {"port": 4222, "listening": True, "evidence": "nats"},
            "dashboard_api": {"port": 8420, "listening": True, "evidence": "api"},
            "dashboard_web": {"port": 3420, "listening": True, "evidence": "web"},
        },
    )

    assert payload["schema_version"] == "live_ops_census.v1"
    assert {source["path"] for source in payload["authority_sources"]} >= {
        "ACTIVE_SURFACE_MANIFEST.yaml",
        "docs/governance/ACTIVE_TRACK.yaml",
        "docs/governance/SOVEREIGN_MANIFEST.md",
        "docs/governance/ANTI_SLOP_RULES.md",
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        "docs/ops/TMUX_AGENT_SUBSTRATE.md",
    }
    assert all(source["exists"] for source in payload["authority_sources"])

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    assert surfaces["substrate.dharma_daemon"]["status"] == "live"
    assert surfaces["transport.nats"]["status"] == "live"
    assert surfaces["evidence.a2a_mirrors"]["status"] == "live"
    assert surfaces["evidence.a2a_mirrors"]["desired_state"] == "evidence-mirror-not-authority"
    assert surfaces["evidence.nats_receipts"]["status"] == "live"
    assert surfaces["evidence.nats_receipts"]["desired_state"] == "ack-receipt-evidence"
    assert surfaces["evidence.nats_receipts"]["raw"]["nats_live_receipt_exists"] is True
    assert surfaces["dashboard.local"]["status"] == "live"
    assert surfaces["revenue.cashclaw_gate"]["status"] == "blocked"
    assert surfaces["revenue.cashclaw_gate"]["human_authority_required"] is True


def test_live_ops_census_validator_rejects_false_green_shapes() -> None:
    assert live_ops_census.validate_census_payload({}) == [
        "live ops census receipt schema_version is missing",
        "live ops census receipt is missing generated_at",
        "live ops census receipt surfaces is missing or not a list",
    ]
    assert live_ops_census.validate_census_payload(
        {
            "schema_version": "live_ops_census.v1",
            "generated_at": "2026-06-14T02:00:00Z",
            "surfaces": [],
        }
    ) == ["live ops census receipt surfaces is empty"]
    assert live_ops_census.validate_census_payload(
        {
            "schema_version": "live_ops_census.v1",
            "generated_at": "2026-06-14T02:00:00Z",
            "surfaces": [{"id": "substrate.dharma_daemon", "status": "live"}],
        }
    ) == []


def test_live_ops_census_freshness_reports_stale_generated_at() -> None:
    now = datetime(2026, 6, 14, 2, 0, tzinfo=timezone.utc)

    fresh = live_ops_census.census_payload_freshness(
        {"generated_at": "2026-06-14T01:45:00Z"},
        max_age_hours=1.0,
        now=now,
    )
    stale = live_ops_census.census_payload_freshness(
        {"generated_at": "2026-06-13T00:00:00Z"},
        max_age_hours=1.0,
        now=now,
    )
    malformed = live_ops_census.census_payload_freshness(
        {"generated_at": "not-a-date"},
        max_age_hours=1.0,
        now=now,
    )

    assert fresh["state"] == "fresh"
    assert fresh["age_minutes"] == 15.0
    assert stale["state"] == "stale"
    assert "older than 1h" in stale["evidence"]
    assert malformed["state"] == "stale"
    assert "missing or unparsable" in malformed["evidence"]


def test_live_ops_census_script_reexports_package_contract() -> None:
    assert live_ops_census.LIVE_OPS_CENSUS_SCHEMA_VERSION == (
        live_ops_census_contract.LIVE_OPS_CENSUS_SCHEMA_VERSION
    )
    assert live_ops_census.default_output_path is live_ops_census_contract.default_output_path
    assert live_ops_census.validate_census_payload is (
        live_ops_census_contract.validate_census_payload
    )
    assert live_ops_census.census_payload_freshness is (
        live_ops_census_contract.census_payload_freshness
    )


def test_live_ops_census_contract_default_output_honors_dharma_state_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))
    assert live_ops_census_contract.default_output_path() == (
        state_root / "ops/live_process_census.json"
    )


def test_live_ops_census_contract_import_direction_static() -> None:
    forbidden = {
        "default_output_path",
        "validate_census_payload",
        "census_payload_freshness",
    }
    checked_files = [
        REPO_ROOT / "dharma_swarm/operator_core/control_surface_live_ops.py",
        REPO_ROOT / "scripts/governance/agent_onboard.py",
        REPO_ROOT / "scripts/governance/orientation_graph.py",
        REPO_ROOT / "scripts/governance/spine_dispatch_mode_report.py",
    ]
    violations: list[str] = []
    for path in checked_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "scripts.runtime.live_ops_census":
                continue
            imported = {alias.name for alias in node.names}
            leaked = sorted(imported & forbidden)
            if leaked:
                violations.append(f"{path.relative_to(REPO_ROOT)} imports {leaked}")
    assert violations == []


def test_live_ops_census_marks_stale_a2a_mirrors_partial(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state_root"
    mirror = state / "a2a_bus" / "messages" / "old_message.json"
    _write(mirror, "{}")
    old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(mirror, (old_ts, old_ts))

    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=state,
        run_probes=False,
    )

    mirrors = {
        surface["id"]: surface for surface in payload["surfaces"]
    }["evidence.a2a_mirrors"]
    assert mirrors["status"] == "live"
    assert mirrors["desired_state"] == "evidence-mirror-not-authority"
    assert mirrors["proof_state"] == "partial"
    assert mirrors["proof_gaps"] == ["a2a_mirror_evidence_stale"]
    assert mirrors["next_action"] == (
        "treat filesystem mirrors as historical; use NATS ack/domain receipts for live-contact proof"
    )
    assert mirrors["raw"]["latest_mirror_path"] == str(mirror)
    assert mirrors["raw"]["mirror_fresh"] is False
    assert mirrors["raw"]["mirror_stale"] is True
    assert mirrors["raw"]["nats_live_contact_bound"] is False
    assert mirrors["raw"]["mirror_max_age_hours"] == 24.0


def test_live_ops_census_does_not_gap_stale_a2a_mirror_when_nats_contact_is_bound(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    mirror = state / "a2a_bus" / "messages" / "old_message.json"
    _write(mirror, "{}")
    old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(mirror, (old_ts, old_ts))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write(
        state / "a2a_bus" / "nats_live_receipt.json",
        json.dumps({
            "ack_verified": True,
            "ack_tier": "DELIVERED_TO_CONSUMER",
            "ts": now,
        }),
    )
    _write(
        repo / "reports" / "a2a" / "send_receipts" / "send.json",
        json.dumps({
            "schema_version": "dharma.a2a.send_receipt.v1",
            "timestamp": now,
            "packet_id": "packet-1",
            "status": "HERMES_M5_CONSUMED",
            "contact_evidence_tier": "HANDLER_ACKED",
            "target_uid": "hermes-m5",
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    mirrors = {
        surface["id"]: surface for surface in payload["surfaces"]
    }["evidence.a2a_mirrors"]
    assert mirrors["status"] == "live"
    assert mirrors["proof_state"] == "bound"
    assert mirrors["proof_gaps"] == []
    assert mirrors["next_action"] == (
        "NATS live-contact proof is bound; filesystem mirrors are historical compatibility evidence"
    )
    assert mirrors["raw"]["mirror_stale"] is True
    assert mirrors["raw"]["nats_live_contact_bound"] is True


def test_live_ops_census_marks_nats_hot_contact_ack_stale(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state_root"
    _write(
        state / "a2a_bus" / "nats_live_receipt.json",
        json.dumps({
            "ack_verified": True,
            "ack_tier": "DELIVERED_TO_CONSUMER",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }),
    )
    _write(
        state / "a2a_bus" / "nats_contact_receipts.jsonl",
        json.dumps({
            "ack_tier": "HANDLER_ACKED",
            "agent_uid": "hermes-m5",
            "ts": "2026-01-01T00:00:00+00:00",
            "verdict": "OK",
        })
        + "\n",
    )

    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=state,
        run_probes=False,
    )

    nats_receipts = {
        surface["id"]: surface for surface in payload["surfaces"]
    }["evidence.nats_receipts"]
    assert nats_receipts["status"] == "live"
    assert nats_receipts["proof_state"] == "partial"
    assert nats_receipts["proof_gaps"] == ["nats_hot_contact_ack_stale"]
    assert nats_receipts["raw"]["ack_tier_state"]["live_probe"]["ack_verified"] is True
    assert (
        nats_receipts["raw"]["ack_tier_state"]["hot_contact"]["ack_tier"]
        == "HANDLER_ACKED"
    )
    assert (
        nats_receipts["raw"]["ack_tier_state"]["operator_hot_contact_ready"]
        is False
    )


def test_live_ops_census_marks_nats_hot_contact_ack_bound_when_fresh(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state_root"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write(
        state / "a2a_bus" / "nats_live_receipt.json",
        json.dumps({
            "ack_verified": True,
            "ack_tier": "DELIVERED_TO_CONSUMER",
            "ts": now,
        }),
    )
    _write(
        state / "a2a_bus" / "nats_contact_receipts.jsonl",
        json.dumps({
            "ack_tier": "HANDLER_ACKED",
            "agent_uid": "hermes-m5",
            "ts": now,
            "verdict": "OK",
        })
        + "\n",
    )

    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=state,
        run_probes=False,
    )

    nats_receipts = {
        surface["id"]: surface for surface in payload["surfaces"]
    }["evidence.nats_receipts"]
    assert nats_receipts["status"] == "live"
    assert nats_receipts["proof_state"] == "bound"
    assert nats_receipts["proof_gaps"] == []
    assert (
        nats_receipts["raw"]["ack_tier_state"]["operator_hot_contact_ready"]
        is True
    )
    assert nats_receipts["next_action"] == (
        "NATS ack tier is freshly proven for operator hot contact"
    )


def test_live_ops_census_accepts_fresh_a2a_send_receipt_for_hot_contact(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write(
        state / "a2a_bus" / "nats_live_receipt.json",
        json.dumps({
            "ack_verified": True,
            "ack_tier": "DELIVERED_TO_CONSUMER",
            "ts": now,
        }),
    )
    _write(
        state / "a2a_bus" / "nats_contact_receipts.jsonl",
        json.dumps({
            "ack_tier": "HANDLER_ACKED",
            "agent_uid": "hermes-m5",
            "ts": "2026-01-01T00:00:00+00:00",
            "verdict": "OK",
        })
        + "\n",
    )
    _write(
        repo / "reports" / "a2a" / "send_receipts" / "send.json",
        json.dumps({
            "schema_version": "dharma.a2a.send_receipt.v1",
            "timestamp": now,
            "packet_id": "packet-1",
            "status": "CODEX_COMPOSER_CONSUMED",
            "contact_evidence_tier": "HANDLER_ACKED",
            "target_uid": "codex_composer",
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    nats_receipts = {
        surface["id"]: surface for surface in payload["surfaces"]
    }["evidence.nats_receipts"]
    assert nats_receipts["status"] == "live"
    assert nats_receipts["proof_state"] == "bound"
    assert nats_receipts["proof_gaps"] == []
    ack_state = nats_receipts["raw"]["ack_tier_state"]
    assert ack_state["operator_hot_contact_ready"] is True
    assert ack_state["hot_contact"]["source"] == "reports/a2a/send_receipts"
    assert ack_state["hot_contact"]["agent_uid"] == "codex_composer"


def test_live_ops_census_records_daemon_dispatch_launch_spec(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    repo.mkdir(parents=True)
    (repo / "com.dharma.swarm.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && exec env PYTHONPATH=/Users/dhyana/dharma_swarm TINY_ROUTER_BACKEND=heuristic ./.venv/bin/python -m dharma_swarm.dgc_cli orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    daemon = surfaces["substrate.dharma_daemon"]
    dispatch = daemon["raw"]["dispatch_launch"]
    assert dispatch["state"] == "spine_enabled_launch_spec"
    assert dispatch["env_declares_spine"] is True
    assert dispatch["repo_module_invocation"] is True
    assert dispatch["ambient_dgc_invocation"] is False
    assert daemon["raw"]["running_dispatch_proof"] == "not_inspected_no_secret_env_dump"
    assert daemon["proof_state"] == "partial"
    assert daemon["proof_gaps"] == ["daemon_dispatch_runtime_unproven"]
    assert daemon["next_action"] == "controlled restart plus daemon/default receipt probe required"


def test_live_ops_census_flags_ambient_dgc_spine_launch_spec(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    repo.mkdir(parents=True)
    (repo / "com.dharma.swarm.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && dgc orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "/opt/homebrew/bin/dgc orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    daemon = surfaces["substrate.dharma_daemon"]
    dispatch = daemon["raw"]["dispatch_launch"]
    assert dispatch["state"] == "ambient_dgc_spine_launch_spec"
    assert dispatch["repo_module_invocation"] is False
    assert dispatch["ambient_dgc_invocation"] is True
    assert "daemon_launch_not_repo_pinned" in daemon["proof_gaps"]
    assert daemon["next_action"] == "pin LaunchAgent to repo module before restart"


def test_live_ops_census_records_cron_dispatch_launch_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "com.dharma.cron-daemon.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-lc",
                "cd /Users/dhyana/dharma_swarm && exec env PYTHONPATH=/Users/dhyana/dharma_swarm ./.venv/bin/python -m dharma_swarm.dgc_cli cron daemon",
            ],
            "EnvironmentVariables": {
                "PYTHONPATH": "/Users/dhyana/dharma_swarm",
                "PATH": "/usr/bin:/bin",
            },
        })
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_cron": [{"pid": "793", "command": "dharma_swarm.dgc_cli cron daemon"}],
        },
        ports={},
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    cron = surfaces["substrate.dharma_cron"]
    dispatch = cron["raw"]["dispatch_launch"]
    assert dispatch["state"] == "repo_pinned_cron_launch_spec"
    assert dispatch["repo_module_invocation"] is True
    assert dispatch["ambient_dgc_invocation"] is False
    assert "cron_launch_not_repo_pinned" not in cron["proof_gaps"]


def test_live_ops_census_flags_ambient_dgc_cron_launch_spec(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "com.dharma.cron-daemon.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-lc",
                "cd /Users/dhyana/dharma_swarm_live && exec /opt/homebrew/bin/dgc cron daemon",
            ],
            "EnvironmentVariables": {
                "PYTHONPATH": "/Users/dhyana/dharma_swarm_live",
                "PATH": "/usr/bin:/bin",
            },
        })
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_cron": [{"pid": "793", "command": "/opt/homebrew/bin/dgc cron daemon"}],
        },
        ports={},
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    cron = surfaces["substrate.dharma_cron"]
    dispatch = cron["raw"]["dispatch_launch"]
    assert dispatch["state"] == "ambient_dgc_cron_launch_spec"
    assert dispatch["repo_module_invocation"] is False
    assert dispatch["ambient_dgc_invocation"] is True
    assert "cron_launch_not_repo_pinned" in cron["proof_gaps"]
    assert cron["next_action"] == "pin cron LaunchAgent to repo module before burn-in"


def test_live_ops_census_accepts_non_secret_daemon_health_spine_self_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
        daemon_health_self_report={
            "url": "http://127.0.0.1:7433/health",
            "http_status": 200,
            "state": "spine_enabled_self_report",
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
            "evidence": "daemon /health returned non-secret runtime_dispatch block",
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert daemon["proof_state"] == "bound"
    assert daemon["proof_gaps"] == []
    assert daemon["next_action"] == ""
    assert daemon["raw"]["running_dispatch_proof"] == "spine_enabled_self_report"
    assert daemon["raw"]["daemon_health_self_report"]["runtime_dispatch"] == {
        "spine_dispatch_enabled": True,
        "dispatch_mode": "spine",
        "env_key_present": True,
        "source": "process_env_non_secret_boolean",
    }


def test_daemon_health_self_report_accepts_matching_health_parent_pid(
    monkeypatch,
) -> None:
    def fake_fetch(url: str, *, timeout_seconds: float) -> tuple[int, dict]:
        assert url == live_ops_census.DAEMON_HEALTH_URL
        assert timeout_seconds == live_ops_census.DAEMON_HEALTH_TIMEOUT_SECONDS
        return 200, {
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
            "daemon_pid": 101,
            "daemon_process_alive": True,
            "health_process_pid": 202,
        }

    monkeypatch.setattr(live_ops_census, "_fetch_json_document", fake_fetch)

    report = live_ops_census._daemon_health_self_report(
        run_probes=True,
        observed_pids={"101"},
    )

    assert report["state"] == "spine_enabled_self_report"
    assert report["daemon_pid"] == "101"
    assert report["daemon_process_alive"] is True
    assert report["health_process_pid"] == 202


def test_daemon_health_self_report_rejects_stale_health_parent_pid(
    monkeypatch,
) -> None:
    def fake_fetch(url: str, *, timeout_seconds: float) -> tuple[int, dict]:
        assert url == live_ops_census.DAEMON_HEALTH_URL
        assert timeout_seconds == live_ops_census.DAEMON_HEALTH_TIMEOUT_SECONDS
        return 200, {
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
            "daemon_pid": 202,
            "daemon_process_alive": True,
            "health_process_pid": 303,
        }

    monkeypatch.setattr(live_ops_census, "_fetch_json_document", fake_fetch)

    report = live_ops_census._daemon_health_self_report(
        run_probes=True,
        observed_pids={"101"},
    )

    assert report["state"] == "daemon_pid_mismatch"
    assert report["daemon_pid"] == "202"
    assert report["observed_pids"] == ["101"]


def test_daemon_health_self_report_rejects_dead_health_parent(
    monkeypatch,
) -> None:
    def fake_fetch(url: str, *, timeout_seconds: float) -> tuple[int, dict]:
        assert url == live_ops_census.DAEMON_HEALTH_URL
        assert timeout_seconds == live_ops_census.DAEMON_HEALTH_TIMEOUT_SECONDS
        return 200, {
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
            "daemon_pid": 101,
            "daemon_process_alive": False,
            "health_process_pid": 303,
        }

    monkeypatch.setattr(live_ops_census, "_fetch_json_document", fake_fetch)

    report = live_ops_census._daemon_health_self_report(
        run_probes=True,
        observed_pids={"101"},
    )

    assert report["state"] == "daemon_parent_not_alive"
    assert report["daemon_pid"] == "101"


def test_live_ops_census_accepts_fresh_pid_bound_daemon_dispatch_file_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)
    report = state / "ops" / "daemon_runtime_dispatch_self_report.json"
    _write(
        report,
        json.dumps({
            "schema_version": "dharma.daemon.runtime_dispatch_self_report.v1",
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "pid": 101,
            "source": "dharma_swarm.orchestrate_live",
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "launchctl:com.dharma.swarm state=running"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": False, "evidence": ""},
        },
        daemon_health_self_report={
            "url": "http://127.0.0.1:7433/health",
            "state": "unreachable",
            "evidence": "connection refused",
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert daemon["proof_state"] == "bound"
    assert daemon["proof_gaps"] == []
    assert daemon["raw"]["running_dispatch_proof"] == "spine_enabled_self_report"
    assert (
        daemon["raw"]["running_dispatch_proof_source"]
        == "daemon_runtime_dispatch_self_report_file"
    )
    assert daemon["raw"]["daemon_runtime_dispatch_self_report"]["pid"] == "101"


def test_live_ops_census_accepts_daemon_pid_file_for_launchd_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)
    _write(state / "daemon.pid", "202\n")
    _write(
        state / "ops" / "daemon_runtime_dispatch_self_report.json",
        json.dumps({
            "schema_version": "dharma.daemon.runtime_dispatch_self_report.v1",
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "pid": 202,
            "source": "dharma_swarm.orchestrate_live",
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [
                {"pid": "101", "command": "launchctl:com.dharma.swarm state=running"}
            ],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": False, "evidence": ""},
        },
        daemon_health_self_report={
            "url": "http://127.0.0.1:7433/health",
            "state": "unreachable",
            "evidence": "connection refused",
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert daemon["proof_state"] == "bound"
    assert daemon["proof_gaps"] == []
    assert daemon["raw"]["daemon_pid_file"]["state"] == "present"
    assert daemon["raw"]["daemon_runtime_dispatch_self_report"]["pid"] == "202"
    assert daemon["raw"]["daemon_runtime_dispatch_self_report"]["pid_source"] == (
        "daemon_pid_file"
    )
    assert daemon["pids"] == ["101", "202"]


def test_live_ops_census_rejects_daemon_pid_file_without_live_daemon(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)
    _write(state / "daemon.pid", "202\n")
    _write(
        state / "ops" / "daemon_runtime_dispatch_self_report.json",
        json.dumps({
            "schema_version": "dharma.daemon.runtime_dispatch_self_report.v1",
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "pid": 202,
            "source": "dharma_swarm.orchestrate_live",
            "runtime_dispatch": {
                "spine_dispatch_enabled": True,
                "dispatch_mode": "spine",
                "env_key_present": True,
                "source": "process_env_non_secret_boolean",
            },
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={"dharma_daemon": []},
        ports={
            "dharma_daemon": {"port": 7433, "listening": False, "evidence": ""},
        },
        daemon_health_self_report={
            "url": "http://127.0.0.1:7433/health",
            "state": "unreachable",
            "evidence": "connection refused",
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert daemon["status"] == "stopped"
    assert daemon["raw"]["daemon_pid_file"]["state"] == "present"
    assert daemon["raw"]["daemon_runtime_dispatch_self_report"]["state"] == (
        "pid_not_observed"
    )


def test_live_ops_census_keeps_dispatch_gap_on_legacy_daemon_health_self_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
        daemon_health_self_report={
            "url": "http://127.0.0.1:7433/health",
            "http_status": 200,
            "state": "legacy_self_report",
            "runtime_dispatch": {
                "spine_dispatch_enabled": False,
                "dispatch_mode": "legacy",
                "env_key_present": False,
                "source": "process_env_non_secret_boolean",
            },
            "evidence": "daemon /health returned non-secret runtime_dispatch block",
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert daemon["proof_state"] == "partial"
    assert daemon["raw"]["running_dispatch_proof"] == "legacy_self_report"
    assert daemon["proof_gaps"] == ["daemon_dispatch_runtime_unproven"]
    assert daemon["next_action"] == "controlled restart plus daemon/default receipt probe required"


def test_live_ops_census_marks_live_daemon_dirty_when_runtime_receipt_head_has_blank_side_effect_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    latest = now.isoformat()
    _write_runtime_receipts_db(
        runtime_db,
        [
            ("old-clean", "side-old", (now - timedelta(minutes=10)).isoformat()),
            ("dirty", "", (now - timedelta(minutes=1)).isoformat()),
            ("new-clean", "side-new", latest),
        ],
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert "daemon_dispatch_runtime_unproven" in daemon["proof_gaps"]
    assert "daemon_runtime_receipts_active_head_dirty" in daemon["proof_gaps"]
    assert daemon["next_action"] == "fix active runtime receipt producers before claiming daemon readiness"
    head = daemon["raw"]["runtime_receipt_active_head"]
    assert head["active_head_side_effect_key_clean"] is False
    assert head["latest_created_at"] == latest
    assert head["latest_fresh"] is True
    assert [
        (row["window_minutes"], row["total"], row["missing_side_effect_key"])
        for row in head["windows"]
    ] == [(5, 2, 1), (15, 3, 1), (60, 3, 1)]


def test_live_ops_census_marks_current_boot_dirty_when_major_receipt_keys_are_blank(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    started_at = now - timedelta(minutes=5)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
            "actual_served_provider": "openrouter",
            "actual_served_model": "qwen3-coder-live",
            "provider_model_truth_source": "runtime_provider.actual_served",
        },
    )
    with sqlite3.connect(runtime_db) as db:
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "receipt-boot-dirty",
                "task_claim",
                "run-boot-dirty",
                "task-boot-dirty",
                "trace-boot-dirty",
                "corr-boot-dirty",
                "agent-boot-dirty",
                "",
                "",
                "claimed",
                "{}",
                now.isoformat(),
            ),
        )
        db.commit()

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        process_starts={
            "dharma_daemon": {"101": started_at.isoformat().replace("+00:00", "Z")},
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert "daemon_runtime_receipts_since_boot_dirty" in daemon["proof_gaps"]
    assert daemon["next_action"] == (
        "fix current-boot runtime receipt producers before claiming daemon readiness"
    )
    since_boot = daemon["raw"]["runtime_receipt_since_boot"]
    assert since_boot["process_started_at"] == started_at.isoformat().replace("+00:00", "Z")
    assert since_boot["since_boot_major_identity_clean"] is False
    assert since_boot["major_since_boot_total"] == 1
    assert since_boot["missing_side_effect_key"] == 1
    assert since_boot["missing_idempotency_key"] == 1
    assert since_boot["gap_sample"][0]["receipt_id"] == "receipt-boot-dirty"


def test_live_ops_census_does_not_mark_live_daemon_dirty_when_runtime_receipt_head_is_clean(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _write_runtime_receipts_db(
        runtime_db,
        [
            ("old-clean", "side-old", (now - timedelta(minutes=10)).isoformat()),
            ("mid-clean", "side-mid", (now - timedelta(minutes=1)).isoformat()),
            ("new-clean", "side-new", now.isoformat()),
        ],
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert daemon["proof_gaps"] == ["daemon_dispatch_runtime_unproven"]
    head = daemon["raw"]["runtime_receipt_active_head"]
    assert head["active_head_side_effect_key_clean"] is True
    assert head["latest_fresh"] is True
    assert [
        (row["window_minutes"], row["missing_side_effect_key"])
        for row in head["windows"]
    ] == [(5, 0), (15, 0), (60, 0)]


def test_live_ops_census_marks_live_daemon_stale_when_runtime_receipts_are_old(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    latest = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=7)
    _write_runtime_receipts_db(
        runtime_db,
        [
            ("old-clean", "side-old", (latest - timedelta(minutes=10)).isoformat()),
            ("new-clean", "side-new", latest.isoformat()),
        ],
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert "daemon_dispatch_runtime_unproven" in daemon["proof_gaps"]
    assert "daemon_runtime_receipts_stale" in daemon["proof_gaps"]
    assert "daemon_runtime_receipts_active_head_dirty" not in daemon["proof_gaps"]
    assert daemon["next_action"] == (
        "exercise a fresh daemon/default runtime receipt path before claiming daemon readiness"
    )
    head = daemon["raw"]["runtime_receipt_active_head"]
    assert head["active_head_side_effect_key_clean"] is True
    assert head["latest_fresh"] is False
    assert head["latest_max_age_hours"] == 6.0
    assert head["latest_age_hours"] >= 6.99
    assert head["evidence"] == "latest runtime receipt head is stale"


def test_live_ops_census_marks_provider_model_receipt_gap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
        },
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert "daemon_dispatch_runtime_unproven" in daemon["proof_gaps"]
    assert "daemon_runtime_provider_model_unproven" in daemon["proof_gaps"]
    assert daemon["next_action"] == (
        "exercise a fresh daemon/default runtime receipt path before claiming daemon readiness"
    )
    coverage = daemon["raw"]["runtime_receipt_coverage"]
    assert coverage["coverage_report_available"] is True
    assert coverage["latest_sample_size"] == 1
    assert coverage["latest_with_provider_model_payload"] == 0
    assert coverage["latest_major_task_receipts_provider_model_percent"] == 0.0
    assert coverage["latest_major_task_receipts_provider_model_provenance_percent"] == 0.0
    assert coverage["provider_model_latest_complete"] is False
    assert coverage["production_readiness_blockers"] == [
        "latest major task receipts do not all carry provider/model payloads",
        "latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata",
    ]
    assert coverage["latest_provider_model_unproven_producer_groups"] == [
        {
            "receipt_type": "a2a_task",
            "provider_model_payload_class": "missing",
            "provider_model_truth_source": "<blank>",
            "producer_source": "<unknown>",
            "producer_failure_code": "<none>",
            "topology": "<blank>",
            "missing_provider_model_provenance": 1,
            "sample_agent_id": "agent-coverage-1",
            "sample_task_id": "task-coverage-1",
        }
    ]


def test_live_ops_census_accounts_explicit_no_provider_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
            "provider_execution": False,
            "provider_model_truth_source": "runtime_control.no_provider_execution",
            "provider_model_applicability": "not_applicable",
            "no_provider_model_reason": (
                "living_agent_kernel_v1_no_provider_execution"
            ),
        },
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [
                {"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}
            ],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert "daemon_dispatch_runtime_unproven" in daemon["proof_gaps"]
    assert "daemon_runtime_provider_model_unproven" not in daemon["proof_gaps"]
    assert daemon["next_action"] == (
        "exercise a fresh daemon/default runtime receipt path before claiming daemon readiness"
    )
    coverage = daemon["raw"]["runtime_receipt_coverage"]
    assert coverage["latest_sample_size"] == 1
    assert coverage["latest_with_provider_model_payload"] == 0
    assert coverage["latest_with_provider_model_accounted"] == 1
    assert coverage["latest_major_task_receipts_provider_model_percent"] == 0.0
    assert coverage["latest_major_task_receipts_provider_model_accounted_percent"] == 100.0
    assert coverage["provider_model_payload_complete"] is False
    assert coverage["provider_model_accounted_complete"] is True
    assert coverage["provider_model_latest_complete"] is True
    assert coverage["latest_provider_model_payload_class_breakdown"] == {
        "no_provider_execution": 1
    }
    assert coverage["production_readiness_blockers"] == []
    assert coverage["evidence"] == (
        "latest major runtime receipts account for provider/model truth"
    )


def test_live_ops_census_scopes_active_head_to_verified_clean_epoch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    since_created_at = "2026-06-14T00:10:00+00:00"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
            "provider_execution": False,
            "provider_model_truth_source": "runtime_control.no_provider_execution",
            "provider_model_applicability": "not_applicable",
            "no_provider_model_reason": "test_deterministic_no_provider_execution",
        },
    )
    with sqlite3.connect(runtime_db) as db:
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "receipt-historical-dirty",
                "task_claim",
                "run-historical-dirty",
                "task-historical-dirty",
                "trace-historical-dirty",
                "corr-historical-dirty",
                "agent-historical-dirty",
                "",
                "",
                "completed",
                "{}",
                "2026-06-14T00:09:00+00:00",
            ),
        )
        db.commit()
    _write_runtime_truth_clean_epoch(
        state_root=state,
        db_path=runtime_db,
        since_created_at=since_created_at,
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [
                {"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}
            ],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert "daemon_runtime_receipts_active_head_dirty" not in daemon["proof_gaps"]
    assert "daemon_runtime_provider_model_unproven" not in daemon["proof_gaps"]
    raw = daemon["raw"]
    assert raw["runtime_truth_clean_epoch"]["enabled"] is True
    assert raw["runtime_truth_clean_epoch"]["receipt_verified"] is True
    assert raw["runtime_truth_clean_epoch"]["since_created_at"] == since_created_at
    active_head = raw["runtime_receipt_active_head"]
    assert active_head["scope_mode"] == "since_created_at"
    assert active_head["scope_since_created_at"] == since_created_at
    assert active_head["unscoped_runtime_receipts_total"] == 3
    assert active_head["runtime_receipts_total"] == 2
    assert active_head["active_head_side_effect_key_clean"] is True
    coverage = raw["runtime_receipt_coverage"]
    assert coverage["active_epoch_enabled"] is True
    assert coverage["scope_mode"] == "since_created_at"
    assert coverage["scope_since_created_at"] == since_created_at
    assert coverage["major_task_receipts_total"] == 1
    assert coverage["latest_sample_size"] == 1
    assert coverage["provider_model_latest_complete"] is True
    assert "historical dirty receipts before the clean epoch" in (
        coverage["historical_scope_note"]
    )


def test_live_ops_census_accepts_terminal_provider_model_truth_with_pending_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
            "provider_execution": False,
            "provider_model_truth_source": "runtime_control.no_provider_execution",
            "provider_model_applicability": "not_applicable",
            "no_provider_model_reason": "dispatch_dropoff_before_worker_execution",
        },
    )
    with sqlite3.connect(runtime_db) as db:
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "receipt-coverage-claimed",
                "delegation_run",
                "run-coverage-1",
                "task-coverage-1",
                "trace-coverage-1",
                "corr-coverage-1",
                "agent-coverage-1",
                "idem-coverage-claimed",
                "side-coverage-claimed",
                "claimed",
                json.dumps({
                    "mission_id": "mission-coverage-1",
                    "artifact_refs": ["artifact-coverage-1"],
                }),
                "2026-06-14T00:11:00+00:00",
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-coverage-claimed",
                "side-coverage-claimed",
                "run-coverage-1",
                "task-coverage-1",
                "trace-coverage-1",
                "corr-coverage-1",
                "completed",
                "receipt-coverage-claimed",
                "{}",
                "2026-06-14T00:10:30+00:00",
                "2026-06-14T00:11:00+00:00",
            ),
        )
        db.commit()

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [
                {"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}
            ],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "substrate.dharma_daemon"
    ]
    assert "daemon_runtime_provider_model_unproven" not in daemon["proof_gaps"]
    coverage = daemon["raw"]["runtime_receipt_coverage"]
    assert coverage["provider_model_accounted_complete"] is False
    assert coverage["terminal_provider_model_accounted_complete"] is True
    assert coverage["provider_model_latest_complete"] is True
    assert coverage["provider_model_readiness_basis"] == "latest_terminal_accounted"
    assert coverage["latest_provider_model_pending_execution"] == 1
    assert coverage["evidence"] == (
        "latest terminal major runtime receipts account for provider/model truth; "
        "pending receipts remain incomplete"
    )


def test_live_ops_census_projects_active_head_gap_producers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    runtime_db = tmp_path / "runtime.db"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(runtime_db))
    _write_spine_launch_plist(repo)
    _write_runtime_coverage_db(
        runtime_db,
        {
            "mission_id": "mission-coverage-1",
            "artifact_refs": ["artifact-coverage-1"],
        },
    )
    with sqlite3.connect(runtime_db) as db:
        db.execute(
            "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run_ds_goal_deadbeef",
                "ds_goal:palantir-pilot-source-card-expansion-2026-06-14",
                "",
                "completed",
                "",
                "",
                "",
                "{}",
            ),
        )
        db.execute(
            """
            INSERT INTO runtime_receipts (
                receipt_id, receipt_type, run_id, task_id, trace_id,
                correlation_id, agent_id, idempotency_key, side_effect_key,
                status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rr-ds-goal-gap",
                "delegation_run",
                "run_ds_goal_deadbeef",
                "palantir-pilot-source-card-expansion-2026-06-14-t01",
                "trace-ds-goal",
                "corr-ds-goal",
                "palantir_pilot",
                "idem-ds-goal",
                "",
                "completed",
                "{}",
                "2026-06-14T00:11:00+00:00",
            ),
        )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    coverage = daemon["raw"]["runtime_receipt_coverage"]

    assert coverage["active_head_gap_producer_groups"] == [
        {
            "window_minutes": 5,
            "receipt_type": "delegation_run",
            "producer_source": "ds_goal_cli",
            "producer_failure_code": "sync_receipt_side_effect_key_missing",
            "topology": "cli_goal_run",
            "identifier_shape": "ordinary",
            "missing_side_effect_key": 1,
            "sample_agent_id": "palantir_pilot",
            "sample_task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
        }
    ]
    assert coverage["field_gap_producer_groups"] == [
        {
            "gap_type": "artifact_evidence",
            "receipt_type": "delegation_run",
            "producer_source": "ds_goal_cli",
            "producer_failure_code": "sync_receipt_side_effect_key_missing",
            "topology": "cli_goal_run",
            "identifier_shape": "ordinary",
            "missing": 1,
            "latest_created_at": "2026-06-14T00:11:00+00:00",
            "freshness_class": "active_head_60m",
            "age_minutes_from_head": 0,
            "recommended_action": "repair_installed_ds_goal_wrapper_or_pin_invocations",
            "sample_agent_id": "palantir_pilot",
            "sample_task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
            "sample_run_id": "run_ds_goal_deadbeef",
        },
        {
            "gap_type": "idempotency_record",
            "receipt_type": "delegation_run",
            "producer_source": "ds_goal_cli",
            "producer_failure_code": "sync_receipt_side_effect_key_missing",
            "topology": "cli_goal_run",
            "identifier_shape": "ordinary",
            "missing": 1,
            "latest_created_at": "2026-06-14T00:11:00+00:00",
            "freshness_class": "active_head_60m",
            "age_minutes_from_head": 0,
            "recommended_action": "repair_installed_ds_goal_wrapper_or_pin_invocations",
            "sample_agent_id": "palantir_pilot",
            "sample_task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
            "sample_run_id": "run_ds_goal_deadbeef",
        },
        {
            "gap_type": "mission_payload",
            "receipt_type": "delegation_run",
            "producer_source": "ds_goal_cli",
            "producer_failure_code": "sync_receipt_side_effect_key_missing",
            "topology": "cli_goal_run",
            "identifier_shape": "ordinary",
            "missing": 1,
            "latest_created_at": "2026-06-14T00:11:00+00:00",
            "freshness_class": "active_head_60m",
            "age_minutes_from_head": 0,
            "recommended_action": "repair_installed_ds_goal_wrapper_or_pin_invocations",
            "sample_agent_id": "palantir_pilot",
            "sample_task_id": "palantir-pilot-source-card-expansion-2026-06-14-t01",
            "sample_run_id": "run_ds_goal_deadbeef",
        },
    ]
    assert coverage["field_gap_summary"] == {
        "group_count": 3,
        "total_missing": 3,
        "active_head_missing": 3,
        "recent_historical_missing": 0,
        "older_historical_missing": 0,
        "unknown_freshness_missing": 0,
        "future_clock_skew_missing": 0,
        "quarantine_candidate_missing": 0,
        "by_freshness_class": {"active_head_60m": 3},
        "by_recommended_action": {
            "repair_installed_ds_goal_wrapper_or_pin_invocations": 3
        },
        "by_gap_type": {
            "artifact_evidence": 1,
            "idempotency_record": 1,
            "mission_payload": 1,
        },
        "by_receipt_type": {"delegation_run": 3},
        "by_producer_source": {"ds_goal_cli": 3},
    }
    assert coverage["field_gap_action_queue"][0]["short_label"] == "ds_goal_wrapper"
    assert coverage["field_gap_action_queue"][0]["missing"] == 3
    assert coverage["field_gap_action_queue"][0]["owner_surface"] == "cli.ds_goal"
    assert coverage["field_gap_action_queue"][0]["required_evidence"]
    assert [
        (item["short_label"], item["status"])
        for item in coverage["gate_70_to_75_components"]
    ] == [
        ("core", "fail"),
        ("idempotency", "fail"),
        ("mission", "fail"),
        ("artifact", "fail"),
        ("active_head", "fail"),
    ]


def test_live_ops_census_marks_ds_goal_cli_target_repo_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    repo = home / "dharma_swarm"
    stale_repo = home / "dharma_swarm_main"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("DHARMA_SWARM_REPO", raising=False)
    _write(
        home / ".dharma" / "bin" / "ds-goal",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then
  repo="$DHARMA_SWARM_REPO"
elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then
  repo="$HOME/dharma_swarm_main"
else
  repo="$HOME/dharma_swarm"
fi
cd "$repo"
exec python3 scripts/runtime/autonomy_spine.py "$@"
""",
    )
    _write(stale_repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        stale_repo / "dharma_swarm" / "runtime_state.py",
        "def create_task_claim_sync():\n"
        "    record_receipt_for_identity_sync(payload={'claim_id': claim_id})\n"
        "def create_delegation_run_sync():\n"
        "    record_receipt_for_identity_sync(payload={'failure_code': failure_code})\n",
    )
    _write(repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        repo / "dharma_swarm" / "runtime_state.py",
        'side_effect_key = f"task_claim:{claim.claim_id}:{claim.status}"\n'
        'side_effect_key = f"delegation_run:{identity.run_id}:{run.status}"\n',
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    ds_goal = {surface["id"]: surface for surface in payload["surfaces"]}["cli.ds_goal"]
    assert ds_goal["status"] == "live"
    assert ds_goal["proof_state"] == "partial"
    assert ds_goal["human_authority_required"] is True
    assert ds_goal["proof_gaps"] == [
        "ds_goal_cli_target_repo_mismatch",
        "ds_goal_cli_target_lacks_sync_side_effect_hardening",
    ]
    assert ds_goal["raw"]["target_repo"] == str(stale_repo)
    assert ds_goal["raw"]["target_resolution_source"] == (
        "installed_wrapper_dharma_swarm_main_preference"
    )
    assert ds_goal["raw"]["target_matches_current_repo"] is False
    assert ds_goal["raw"]["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'}"
    )
    assert ds_goal["restart_command"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'} --help"
    )
    assert "pinned current-checkout invocation" in ds_goal["next_action"]
    contract = ds_goal["raw"]["installed_wrapper_contract"]
    assert contract["wrapper_exists"] is True
    assert contract["wrapper_sha256"]
    assert contract["dharma_swarm_repo_pin_supported"] is True
    assert contract["dharma_swarm_main_preference_declared"] is True
    assert contract["dharma_swarm_fallback_declared"] is True
    assert contract["execs_autonomy_spine"] is True
    assert ds_goal["raw"]["default_wrapper_target"]["target_repo"] == str(stale_repo)
    assert ds_goal["raw"]["default_wrapper_target"]["target_matches_audited_repo"] is False
    assert ds_goal["raw"]["target_sync_receipt_hardening"]["state"] == (
        "sync_receipt_side_effect_keys_missing"
    )
    decision = ds_goal["raw"]["convergence_decision_packet"]
    assert decision["approval_state"] == "operator_approval_required"
    assert decision["operator_approval_required"] is True
    assert decision["default_target_repo"] == str(stale_repo)
    assert decision["default_target_matches_audited_checkout"] is False
    assert decision["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'}"
    )
    preflight = ds_goal["raw"]["longrun_preflight_gate"]
    assert preflight["schema_version"] == "dharma.ds_goal_longrun_preflight.v1"
    assert preflight["status"] == "blocked_unpinned_default_target"
    assert preflight["longrun_start_allowed"] is False
    assert preflight["operator_convergence_required"] is True
    assert preflight["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'}"
    )
    assert [
        item["id"] for item in decision["operator_decision_options"]
    ] == [
        "converge_installed_wrapper_default_to_audited_checkout",
        "harden_current_default_target_checkout",
        "retain_default_with_mandatory_pin_or_quarantine",
    ]
    assert "start_repo_native_longrun_from_unpinned_ds_goal" in decision[
        "forbidden_without_operator_approval"
    ]


def test_live_ops_census_accepts_converged_ds_goal_default_wrapper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    repo = home / "dharma_swarm"
    stale_repo = home / "dharma_swarm_main"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("DHARMA_SWARM_REPO", raising=False)
    _write(
        home / ".dharma" / "bin" / "ds-goal",
        """#!/usr/bin/env bash
set -euo pipefail
# dharma_swarm_main remains a fallback only; comments must not define order.
if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then
  repo="$DHARMA_SWARM_REPO"
elif [[ -f "$HOME/dharma_swarm/scripts/runtime/autonomy_spine.py" ]]; then
  repo="$HOME/dharma_swarm"
elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then
  repo="$HOME/dharma_swarm_main"
else
  repo="$HOME/dharma_swarm"
fi
cd "$repo"
exec python3 scripts/runtime/autonomy_spine.py "$@"
""",
    )
    _write(stale_repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        stale_repo / "dharma_swarm" / "runtime_state.py",
        "def create_task_claim_sync():\n"
        "    record_receipt_for_identity_sync(payload={'claim_id': claim_id})\n",
    )
    _write(repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        repo / "dharma_swarm" / "runtime_state.py",
        'side_effect_key = f"task_claim:{claim.claim_id}:{claim.status}"\n'
        'side_effect_key = f"delegation_run:{identity.run_id}:{run.status}"\n',
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    ds_goal = {surface["id"]: surface for surface in payload["surfaces"]}["cli.ds_goal"]
    assert ds_goal["status"] == "live"
    assert ds_goal["proof_state"] == "bound"
    assert ds_goal["human_authority_required"] is False
    assert ds_goal["proof_gaps"] == []
    assert ds_goal["next_action"] == ""
    assert ds_goal["raw"]["target_repo"] == str(repo)
    assert ds_goal["raw"]["target_resolution_source"] == (
        "installed_wrapper_dharma_swarm_preference"
    )
    assert ds_goal["raw"]["target_matches_current_repo"] is True
    contract = ds_goal["raw"]["installed_wrapper_contract"]
    assert contract["dharma_swarm_preference_declared"] is True
    assert contract["dharma_swarm_main_preference_declared"] is False
    assert contract["default_target_order"] == ["dharma_swarm", "dharma_swarm_main"]
    assert ds_goal["raw"]["default_wrapper_target"]["target_repo"] == str(repo)
    assert ds_goal["raw"]["default_wrapper_target"][
        "target_matches_audited_repo"
    ] is True
    assert ds_goal["raw"]["target_sync_receipt_hardening"]["state"] == (
        "sync_receipt_side_effect_keys_hardened"
    )
    decision = ds_goal["raw"]["convergence_decision_packet"]
    assert decision["approval_state"] == "not_required_default_matches_audited_checkout"
    assert decision["operator_approval_required"] is False
    preflight = ds_goal["raw"]["longrun_preflight_gate"]
    assert preflight["status"] == "pass_default_matches_audited_checkout"
    assert preflight["longrun_start_allowed"] is True
    assert preflight["operator_convergence_required"] is False


def test_live_ops_census_accepts_ds_goal_cli_repo_env_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    repo = home / "dharma_swarm"
    stale_repo = home / "dharma_swarm_main"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_SWARM_REPO", str(repo))
    _write(
        home / ".dharma" / "bin" / "ds-goal",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then
  repo="$DHARMA_SWARM_REPO"
elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then
  repo="$HOME/dharma_swarm_main"
else
  repo="$HOME/dharma_swarm"
fi
cd "$repo"
exec python3 scripts/runtime/autonomy_spine.py "$@"
""",
    )
    _write(stale_repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        stale_repo / "dharma_swarm" / "runtime_state.py",
        "def create_task_claim_sync():\n"
        "    record_receipt_for_identity_sync(payload={'claim_id': claim_id})\n",
    )
    _write(repo / "scripts" / "runtime" / "autonomy_spine.py")
    _write(
        repo / "dharma_swarm" / "runtime_state.py",
        'side_effect_key = f"task_claim:{claim.claim_id}:{claim.status}"\n'
        'side_effect_key = f"delegation_run:{identity.run_id}:{run.status}"\n',
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    ds_goal = {surface["id"]: surface for surface in payload["surfaces"]}["cli.ds_goal"]
    assert ds_goal["status"] == "live"
    assert ds_goal["proof_state"] == "bound"
    assert ds_goal["human_authority_required"] is True
    assert ds_goal["proof_gaps"] == []
    assert "operator decision" in ds_goal["next_action"]
    assert ds_goal["raw"]["target_repo"] == str(repo)
    assert ds_goal["raw"]["target_resolution_source"] == "DHARMA_SWARM_REPO"
    assert ds_goal["raw"]["target_matches_current_repo"] is True
    assert ds_goal["raw"]["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'}"
    )
    assert ds_goal["raw"]["installed_wrapper_contract"][
        "dharma_swarm_main_preference_declared"
    ] is True
    assert ds_goal["raw"]["default_wrapper_target"]["target_repo"] == str(stale_repo)
    assert ds_goal["raw"]["default_wrapper_target"]["target_matches_audited_repo"] is False
    assert ds_goal["raw"]["target_sync_receipt_hardening"]["state"] == (
        "sync_receipt_side_effect_keys_hardened"
    )
    decision = ds_goal["raw"]["convergence_decision_packet"]
    assert decision["approval_state"] == "operator_approval_required"
    assert decision["default_target_repo"] == str(stale_repo)
    assert decision["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={repo} {home / '.dharma' / 'bin' / 'ds-goal'}"
    )
    preflight = ds_goal["raw"]["longrun_preflight_gate"]
    assert preflight["status"] == "pass_explicit_audited_checkout_pin"
    assert preflight["longrun_start_allowed"] is True
    assert preflight["repo_pin_source"] == "DHARMA_SWARM_REPO"
    assert preflight["repo_pin_matches_audited_checkout"] is True
    assert preflight["operator_convergence_required"] is True


def test_live_ops_census_uses_port_owner_when_daemon_pgrep_misses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)
    _write(repo / "dharma_swarm" / "orchestrator.py")

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [],
        },
        ports={
            "dharma_daemon": {
                "port": 7433,
                "listening": True,
                "evidence": "Python 777 dhyana TCP 127.0.0.1:7433 (LISTEN)",
                "owner_processes": [
                    {
                        "pid": "777",
                        "command": "Python",
                        "listen_name": "TCP 127.0.0.1:7433 (LISTEN)",
                        "source": "lsof_listen",
                    }
                ],
            },
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert daemon["status"] == "live"
    assert daemon["pid_count"] == 1
    assert daemon["pids"] == ["777"]
    assert daemon["raw"]["process_source_state"]["state"] == "process_start_uninspected"
    assert daemon["raw"]["process_source_state"]["pids"] == ["777"]


def test_live_ops_census_marks_daemon_process_start_probe_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    _write_spine_launch_plist(repo)
    _write(repo / "dharma_swarm" / "orchestrator.py")

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "777", "command": "Python"}],
        },
        process_starts={
            "dharma_daemon": {
                "__probe_errors__": json.dumps(
                    [{"pid": "777", "error": "[Errno 1] Operation not permitted: 'ps'"}]
                )
            },
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert "daemon_process_start_uninspected" in daemon["proof_gaps"]
    source_state = daemon["raw"]["process_source_state"]
    assert source_state["state"] == "process_start_probe_failed"
    assert source_state["process_start_probe_errors"] == [
        {"pid": "777", "error": "[Errno 1] Operation not permitted: 'ps'"}
    ]


def test_live_ops_census_marks_daemon_stale_when_source_changed_after_start(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    home = tmp_path / "home"
    monkeypatch.setattr(live_ops_census.Path, "home", staticmethod(lambda: home))
    repo.mkdir(parents=True)
    (repo / "com.dharma.swarm.plist").write_bytes(
        plistlib.dumps({
            "ProgramArguments": [
                "/bin/bash",
                "-c",
                "cd /Users/dhyana/dharma_swarm && source .env && exec env PYTHONPATH=/Users/dhyana/dharma_swarm TINY_ROUTER_BACKEND=heuristic ./.venv/bin/python -m dharma_swarm.dgc_cli orchestrate-live",
            ],
            "EnvironmentVariables": {
                "DHARMA_SPINE_DISPATCH": "1",
                "PATH": "/usr/bin:/bin",
            },
        })
    )
    source_path = repo / "dharma_swarm" / "orchestrator.py"
    _write(source_path)
    source_ts = datetime(2026, 6, 13, 20, 10, tzinfo=timezone.utc).timestamp()
    os.utime(source_path, (source_ts, source_ts))

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
        },
        process_starts={
            "dharma_daemon": {"101": "2026-06-13T20:00:00Z"},
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
        },
    )

    daemon = {surface["id"]: surface for surface in payload["surfaces"]}["substrate.dharma_daemon"]
    assert daemon["proof_state"] == "partial"
    assert "daemon_dispatch_runtime_unproven" in daemon["proof_gaps"]
    assert "daemon_process_source_stale" in daemon["proof_gaps"]
    source_state = daemon["raw"]["process_source_state"]
    assert source_state["state"] == "source_changed_after_process_start"
    assert source_state["stale_pids"] == [
        {"pid": "101", "started_at": "2026-06-13T20:00:00Z"}
    ]
    assert source_state["source_newer_files"] == [
        {"path": "dharma_swarm/orchestrator.py", "mtime": "2026-06-13T20:10:00Z"}
    ]


def test_live_ops_census_records_dashboard_control_surface_probe(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state_root",
        run_probes=False,
        ports={
            "dashboard_api": {"port": 8420, "listening": True, "evidence": "api"},
            "dashboard_web": {"port": 3420, "listening": True, "evidence": "web"},
        },
        http_probes={
            "dashboard_control_surface_rows": {
                "url": "http://127.0.0.1:8420/api/control-surface/rows",
                "state": "timeout",
                "evidence": "timed out after 1.5s",
            }
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    dashboard = surfaces["dashboard.local"]
    assert dashboard["status"] == "live"
    assert dashboard["proof_state"] == "partial"
    assert dashboard["proof_gaps"] == ["dashboard_control_surface_rows_unproven"]
    assert dashboard["raw"]["control_surface_rows_probe"]["state"] == "timeout"
    assert "control_surface_rows=timeout" in dashboard["evidence"]
    assert dashboard["next_action"] == (
        "inspect or restart dashboard API; control-surface rows probe did not answer"
    )


def test_dashboard_source_freshness_includes_operator_ui_runtime_evidence() -> None:
    assert "dashboard/src/components/cockpit/SystemTruthMatrix.tsx" in (
        live_ops_census.DASHBOARD_CONTROL_SURFACE_SOURCE_PATHS
    )
    assert "dashboard/src/lib/controlSurfaceRuntimeEvidence.ts" in (
        live_ops_census.DASHBOARD_CONTROL_SURFACE_SOURCE_PATHS
    )


def test_live_ops_census_marks_dashboard_source_stale_when_projector_changed(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "dharma_swarm" / "operator_core" / "control_surface_live_ops.py"
    _write(source_path)
    source_ts = datetime(2026, 6, 13, 20, 30, tzinfo=timezone.utc).timestamp()
    os.utime(source_path, (source_ts, source_ts))

    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state_root",
        run_probes=False,
        processes={
            "dashboard_api": [{"pid": "201", "command": "uvicorn api.main:app"}],
        },
        process_starts={
            "dashboard_api": {"201": "2026-06-13T20:00:00Z"},
        },
        ports={
            "dashboard_api": {"port": 8420, "listening": True, "evidence": "api"},
            "dashboard_web": {"port": 3420, "listening": True, "evidence": "web"},
        },
        http_probes={
            "dashboard_control_surface_rows": {
                "state": "ok",
                "source_error_count": 0,
                "elapsed_seconds": 0.2,
                "slow": False,
            }
        },
    )

    dashboard = {surface["id"]: surface for surface in payload["surfaces"]}["dashboard.local"]
    assert dashboard["proof_state"] == "partial"
    assert dashboard["proof_gaps"] == ["dashboard_control_surface_source_stale"]
    assert dashboard["next_action"] == "restart dashboard API to load current control-surface projector"
    source_state = dashboard["raw"]["process_source_state"]
    assert source_state["state"] == "source_changed_after_process_start"
    assert source_state["stale_pids"] == [
        {"pid": "201", "started_at": "2026-06-13T20:00:00Z"}
    ]
    assert source_state["source_newer_files"] == [
        {
            "path": "dharma_swarm/operator_core/control_surface_live_ops.py",
            "mtime": "2026-06-13T20:30:00Z",
        }
    ]


def test_live_ops_census_marks_terminal_tui_source_stale(tmp_path: Path) -> None:
    source_path = tmp_path / "terminal" / "src" / "app.tsx"
    _write(source_path)
    source_ts = datetime(2026, 6, 13, 20, 45, tzinfo=timezone.utc).timestamp()
    os.utime(source_path, (source_ts, source_ts))

    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state_root",
        run_probes=False,
        processes={
            "terminal_tui": [{"pid": "301", "command": "bun terminal/src/index.tsx"}],
        },
        process_starts={
            "terminal_tui": {"301": "2026-06-13T20:00:00Z"},
        },
    )

    terminal = {surface["id"]: surface for surface in payload["surfaces"]}["terminal.tui"]
    assert terminal["status"] == "live"
    assert terminal["proof_state"] == "partial"
    assert terminal["proof_gaps"] == ["terminal_tui_source_stale"]
    assert terminal["next_action"] == (
        "restart terminal TUI to load current terminal source after operator approval"
    )
    source_state = terminal["raw"]["process_source_state"]
    assert source_state["state"] == "source_changed_after_process_start"
    assert source_state["stale_pids"] == [
        {"pid": "301", "started_at": "2026-06-13T20:00:00Z"}
    ]
    assert source_state["source_newer_files"] == [
        {"path": "terminal/src/app.tsx", "mtime": "2026-06-13T20:45:00Z"}
    ]


def test_live_ops_census_marks_terminal_tui_live_from_tmux_session(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state_root",
        run_probes=False,
        tmux_sessions=["dharma_terminal_tui"],
    )

    terminal = {surface["id"]: surface for surface in payload["surfaces"]}["terminal.tui"]
    assert terminal["status"] == "live"
    assert terminal["pid_count"] == 0
    assert terminal["proof_state"] == "bound"
    assert terminal["proof_gaps"] == []
    assert terminal["raw"]["session"] == "dharma_terminal_tui"
    assert terminal["raw"]["tmux_session_live"] is True
    assert terminal["raw"]["process_live"] is False
    assert terminal["raw"]["process_source_state"]["state"] == "no_process"


def test_live_ops_census_treats_slow_dashboard_probe_as_bound_performance_signal(
    tmp_path: Path,
) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state_root",
        run_probes=False,
        ports={
            "dashboard_api": {"port": 8420, "listening": True, "evidence": "api"},
            "dashboard_web": {"port": 3420, "listening": True, "evidence": "web"},
        },
        http_probes={
            "dashboard_control_surface_rows": {
                "url": "http://127.0.0.1:8420/api/control-surface/rows",
                "state": "ok",
                "row_count": 20,
                "elapsed_seconds": 2.8,
                "slow": True,
                "performance_state": "slow",
                "evidence": "control-surface rows envelope returned data list in 2.8s",
            }
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    dashboard = surfaces["dashboard.local"]
    assert dashboard["status"] == "live"
    assert dashboard["proof_state"] == "bound"
    assert dashboard["proof_gaps"] == []
    assert dashboard["raw"]["control_surface_rows_probe"]["state"] == "ok"
    assert dashboard["raw"]["control_surface_rows_probe"]["performance_state"] == "slow"
    assert "control_surface_rows=ok" in dashboard["evidence"]
    assert "control_surface_rows_elapsed=2.8s" in dashboard["evidence"]
    assert dashboard["next_action"] == "profile dashboard API rows endpoint; live proof is slow"


def test_live_ops_census_tracks_governed_a2a_inbox_bridge(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    latest_receipt = repo / "reports" / "a2a" / "inbox_bridge_receipts" / "receipt.json"
    _write(latest_receipt, "{}")
    _write(state / "a2a_bus" / "bridge_heartbeats" / "hermes-m5.json", "{}")

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "a2a_inbox_bridge": [
                {"pid": "201", "command": "python scripts/runtime/a2a_inbox_bridge.py --loop"}
            ],
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["label"] == "A2A inbox delivery bridge"
    assert bridge["status"] == "live"
    assert bridge["desired_state"] == "delivery-handler-not-semantic-peer"
    assert bridge["proof_state"] == "bound"
    assert bridge["proof_gaps"] == []
    assert bridge["raw"]["bridge_kind"] == "filesystem_delivery_handler"
    assert bridge["raw"]["semantic_reply_claim"] is False
    assert bridge["raw"]["peer_model_processed_claim"] is False
    assert bridge["raw"]["heartbeat_exists"] is True
    assert bridge["raw"]["latest_receipt"] == str(latest_receipt)
    assert "scripts/runtime/a2a_inbox_bridge.py" in bridge["evidence"]


def test_live_ops_census_marks_live_a2a_bridge_partial_without_heartbeat(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=tmp_path / "state_root",
        run_probes=False,
        processes={
            "a2a_inbox_bridge": [
                {"pid": "201", "command": "python scripts/runtime/a2a_inbox_bridge.py --loop"}
            ],
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["status"] == "live"
    assert bridge["proof_state"] == "partial"
    assert bridge["proof_gaps"] == ["a2a_inbox_bridge_heartbeat_missing"]


def test_live_ops_census_marks_a2a_bridge_stale_heartbeat(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    latest_receipt = repo / "reports" / "a2a" / "inbox_bridge_receipts" / "receipt.json"
    _write(
        latest_receipt,
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
            "timestamp": "2000-01-02T00:00:00Z",
        }),
    )
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / "hermes-m5.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": "2000-01-01T00:00:00Z",
            "status": "IDLE",
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "a2a_inbox_bridge": [
                {"pid": "201", "command": "python scripts/runtime/a2a_inbox_bridge.py --loop"}
            ],
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["status"] == "live"
    assert bridge["proof_state"] == "partial"
    assert bridge["proof_gaps"] == ["a2a_inbox_bridge_heartbeat_stale"]
    assert bridge["raw"]["heartbeat_fresh"] is False
    assert bridge["raw"]["heartbeat_status"] == "IDLE"
    assert bridge["raw"]["latest_receipt"] == str(latest_receipt)
    assert bridge["raw"]["latest_receipt_timestamp"] == "2000-01-02T00:00:00Z"
    assert bridge["raw"]["consumer_probe"]["state"] == "not_checked"


def test_live_ops_census_projects_a2a_packet_lifecycle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    latest_receipt = (
        repo
        / "reports"
        / "a2a"
        / "inbox_bridge_receipts"
        / "receipt.json"
    )
    packet_id = "packet-1"
    _write(
        latest_receipt,
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
            "timestamp": "2026-06-11T16:05:43Z",
            "packet_id": packet_id,
            "status": "DELIVERED_AND_ACKED",
            "contact_evidence_tier": "HANDLER_ACKED",
            "semantic_reply_claim": False,
            "peer_model_processed_claim": False,
        }),
    )
    _write(
        repo / "reports" / "a2a" / "send_receipts" / "send.json",
        json.dumps({
            "schema_version": "dharma.a2a.send_receipt.v1",
            "timestamp": "2026-06-11T16:05:40Z",
            "packet_id": packet_id,
            "status": "HERMES_M5_CONSUMED",
            "contact_evidence_tier": "HANDLER_ACKED",
        }),
    )
    _write(
        repo / "reports" / "a2a" / "domain_reply_receipts" / "domain.json",
        json.dumps({
            "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
            "timestamp": "2026-06-11T16:06:40Z",
            "packet_id": packet_id,
            "status": "DOMAIN_REPLY_PUBLISHED",
            "contact_evidence_tier": "DOMAIN_RECEIPTED",
            "reply_evidence_tier": "DOMAIN_RECEIPTED",
            "domain_receipt_claim": True,
            "semantic_reply_claim": False,
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "a2a_inbox_bridge": [
                {"pid": "201", "command": "python scripts/runtime/a2a_inbox_bridge.py --loop"}
            ],
        },
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    lifecycle = surfaces["transport.a2a_bridge"]["raw"]["a2a_lifecycle"]
    assert lifecycle["packet_id"] == packet_id
    assert lifecycle["sent"] == "send_receipt_found"
    assert lifecycle["handler_ack"] == "handler_acked"
    assert lifecycle["domain_receipt"] == "domain_receipted"
    assert lifecycle["semantic_reply"] == "missing"
    assert lifecycle["peer_model"] == "missing"
    assert lifecycle["completed"] == "incomplete"
    assert lifecycle["domain_reply_receipt"]["state"] == "found"


def test_live_ops_census_marks_stopped_a2a_bridge_with_stale_heartbeat(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / "hermes-m5.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": "2000-01-01T00:00:00Z",
            "status": "IDLE",
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["status"] == "stopped"
    assert bridge["proof_state"] == "partial"
    assert bridge["proof_gaps"] == [
        "a2a_inbox_bridge_stopped",
        "a2a_inbox_bridge_heartbeat_stale",
    ]
    assert bridge["raw"]["heartbeat_fresh"] is False
    assert bridge["raw"]["heartbeat_status"] == "IDLE"


def test_a2a_bridge_consumer_probe_parses_read_only_nats_info(monkeypatch) -> None:
    def fake_run(args, *, cwd=None, timeout=5):
        assert args[:5] == [
            "nats",
            "--no-context",
            "--server",
            "nats://127.0.0.1:4222",
            "consumer",
        ]
        return (
            0,
            json.dumps({
                "config": {
                    "ack_policy": "explicit",
                    "deliver_policy": "new",
                    "filter_subject": "dharma.agent.hermes-m5.inbox",
                },
                "delivered": {"last_active": "2026-06-11T16:05:43Z"},
                "ack_floor": {"last_active": "2026-06-11T16:05:44Z"},
                "num_ack_pending": 0,
                "num_pending": 0,
                "num_waiting": 0,
                "ts": "2026-06-14T12:44:28Z",
            }),
        )

    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    probe = live_ops_census._a2a_inbox_bridge_consumer_probe(
        run_probes=True,
        nats_port={"listening": True},
        stream="DHARMA_FLEET",
        consumer="hermes_inbox",
    )

    assert probe["state"] == "consumer_inspectable"
    assert probe["filter_subject"] == "dharma.agent.hermes-m5.inbox"
    assert probe["deliver_policy"] == "new"
    assert probe["ack_policy"] == "explicit"
    assert probe["num_pending"] == 0


def test_live_ops_census_marks_stopped_a2a_bridge_as_proof_gap(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=tmp_path / "state_root",
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["status"] == "stopped"
    assert bridge["proof_state"] == "partial"
    assert bridge["proof_gaps"] == ["a2a_inbox_bridge_stopped"]
    assert bridge["next_action"] == (
        "start governed launchd inbox bridge fleet if live A2A delivery is required"
    )


def test_live_ops_census_treats_fresh_a2a_bridge_heartbeat_as_live(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    latest_receipt = repo / "reports" / "a2a" / "inbox_bridge_receipts" / "receipt.json"
    _write(
        latest_receipt,
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
            "timestamp": now,
            "status": "DELIVERED_AND_ACKED",
            "packet_id": "packet-1",
            "contact_evidence_tier": "HANDLER_ACKED",
        }),
    )
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / "hermes-m5.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": now,
            "status": "IDLE",
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    bridge = surfaces["transport.a2a_bridge"]
    assert bridge["status"] == "live"
    assert bridge["proof_gaps"] == []
    assert bridge["restart_command"] == "bash scripts/start_a2a_inbox_bridge_fleet_launchd.sh"
    assert "scripts/status_a2a_inbox_bridge_fleet_launchd.sh" in bridge["evidence"]


def test_live_ops_census_tracks_bound_holon_l4_surface(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    agents_root = state / "agents"
    holon_name = "codex_composer"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_iso = now.isoformat().replace("+00:00", "Z")
    artifact = agents_root / holon_name / "artifacts" / "l4-proof.json"
    _write(
        artifact,
        json.dumps({
            "schema_version": "dharma.holon_l4_artifact.v1",
            "holon": holon_name,
        }),
    )
    record_service_heartbeat(
        holon_name,
        agents_root=agents_root,
        session_id="l4-bound",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now,
        proof_ref={
            "kind": "l4_supervised_smoke_artifact",
            "artifact_id": "holon_l4_artifact:test",
            "artifact_digest": "sha256:test",
        },
        claim_scope={
            "transport_reachable": True,
            "model_responsive": True,
            "orchestration_proven": True,
        },
    )
    save_cycle_record(
        holon_name,
        {
            "schema_version": "dharma.holon_l4_smoke.v1",
            "overall_pass": True,
            "proof_digest": "sha256:l4",
            "proof_levels": {
                "service_heartbeat": True,
                "transport_reachable": True,
                "model_responsive": True,
                "orchestration": True,
            },
            "model_probe": {
                "attempted": True,
                "responsive": True,
                "status": "ok",
                "provider_source": "declared_identity",
                "provider_type": "codex",
                "model": "gpt-5.5",
                "reply_digest": "sha256:model",
                "route_policy": {
                    "decision": "allow",
                    "explicit_lease": True,
                    "model_probe_lease_id": "lease:test:l4-model",
                    "lease_evidence": {
                        "valid": True,
                        "path": str(agents_root / holon_name / "leases" / "model.json"),
                    },
                },
            },
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:test",
                "path": str(artifact),
            },
            "claim_scope": {
                "transport_reachable": True,
                "model_responsive": True,
                "orchestration_proven": True,
            },
        },
        agents_root=agents_root,
    )
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / f"{holon_name}.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": now_iso,
            "agent_uid": holon_name,
            "subject": f"dharma.agent.{holon_name}.inbox",
            "stream": "DHARMA_FLEET",
            "consumer": f"{holon_name}_inbox",
            "status": "IDLE",
            "cycle": 1,
        }),
    )
    _write(
        repo
        / "reports"
        / "sovereign_holons"
        / "verify_holon_harness_prod_20260618T000000Z.json",
        json.dumps({
            "overall_pass": True,
            "timestamp": now_iso,
            "checks": {
                "l4_orchestration_probe_stub": {
                    "pass": True,
                }
            },
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    holon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "holon.codex_composer_l4"
    ]
    assert holon["status"] == "live"
    assert holon["proof_state"] == "bound"
    assert holon["proof_gaps"] == []
    assert holon["raw"]["service_liveness"]["service_alive"] is True
    assert holon["raw"]["transport_liveness"]["transport_reachable"] is True
    assert holon["raw"]["persisted_l4_proof"]["overall_pass"] is True
    assert holon["raw"]["persisted_l4_proof"]["artifact_exists"] is True
    assert (
        holon["raw"]["model_responsiveness"]["model_responsive_proven"]
        is True
    )
    assert holon["raw"]["prod_verifier"]["l4_orchestration_probe_stub_pass"] is True

    record_service_heartbeat(
        holon_name,
        agents_root=agents_root,
        session_id="l4-bound-paused",
        service_id="holon-l4-service",
        status="paused",
        observed_at=now + timedelta(seconds=1),
        proof_ref={"kind": "l4_service_cycle_paused"},
        claim_scope={"runtime_paused": True},
    )
    paused_payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )
    paused_holon = {surface["id"]: surface for surface in paused_payload["surfaces"]}[
        "holon.codex_composer_l4"
    ]
    assert paused_holon["status"] == "paused"
    assert paused_holon["proof_state"] == "bound"
    assert paused_holon["proof_gaps"] == []
    assert paused_holon["raw"]["service_liveness"]["service_paused"] is True
    assert "holon_service_not_alive" not in paused_holon["proof_gaps"]


def test_live_ops_census_requires_l4_model_responsive_proof(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    agents_root = state / "agents"
    holon_name = "codex_composer"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_iso = now.isoformat().replace("+00:00", "Z")
    artifact = agents_root / holon_name / "artifacts" / "l4-proof.json"
    _write(
        artifact,
        json.dumps({
            "schema_version": "dharma.holon_l4_artifact.v1",
            "holon": holon_name,
        }),
    )
    record_service_heartbeat(
        holon_name,
        agents_root=agents_root,
        session_id="l4-without-model",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now,
        proof_ref={"kind": "l4_service_cycle", "artifact": {"path": str(artifact)}},
        claim_scope={
            "transport_reachable": True,
            "orchestration_proven": True,
            "service_alive": True,
        },
    )
    save_cycle_record(
        holon_name,
        {
            "schema_version": "dharma.holon_l4_smoke.v1",
            "overall_pass": True,
            "proof_digest": "sha256:l4",
            "proof_levels": {
                "service_heartbeat": True,
                "transport_reachable": True,
                "orchestration": True,
            },
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:test",
                "path": str(artifact),
            },
        },
        agents_root=agents_root,
    )
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / f"{holon_name}.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": now_iso,
            "agent_uid": holon_name,
            "subject": f"dharma.agent.{holon_name}.inbox",
            "stream": "DHARMA_FLEET",
            "consumer": f"{holon_name}_inbox",
            "status": "IDLE",
            "cycle": 1,
        }),
    )
    _write(
        repo
        / "reports"
        / "sovereign_holons"
        / "verify_holon_harness_prod_20260618T000000Z.json",
        json.dumps({
            "overall_pass": True,
            "timestamp": now_iso,
            "checks": {"l4_orchestration_probe_stub": {"pass": True}},
        }),
    )

    payload = build_live_ops_census(repo_root=repo, state_root=state, run_probes=False)

    holon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "holon.codex_composer_l4"
    ]
    assert holon["status"] == "partial"
    assert holon["proof_state"] == "partial"
    assert holon["proof_gaps"] == ["holon_l4_model_responsive_proof_missing"]
    assert (
        holon["raw"]["model_responsiveness"]["model_responsive_proven"]
        is False
    )


def test_live_ops_census_tracks_active_holon_l4_tmux_supervisor(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    agents_root = state / "agents"
    holon_name = "codex_composer"
    tmux_session = "dharma_holon_l4_codex_composer"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_iso = now.isoformat().replace("+00:00", "Z")
    artifact = agents_root / holon_name / "artifacts" / "l4-proof.json"
    _write(
        artifact,
        json.dumps({
            "schema_version": "dharma.holon_l4_artifact.v1",
            "holon": holon_name,
        }),
    )
    record_service_heartbeat(
        holon_name,
        agents_root=agents_root,
        session_id="l4-real-tmux-supervisor",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now,
        proof_ref={
            "kind": "l4_service_cycle",
            "artifact": {"path": str(artifact)},
        },
        claim_scope={
            "transport_reachable": True,
            "model_responsive": True,
            "orchestration_proven": True,
            "service_alive": True,
        },
    )
    save_cycle_record(
        holon_name,
        {
            "schema_version": "dharma.holon_l4_smoke.v1",
            "overall_pass": True,
            "proof_digest": "sha256:l4",
            "proof_levels": {
                "service_heartbeat": True,
                "transport_reachable": True,
                "model_responsive": True,
                "orchestration": True,
            },
            "model_probe": {
                "attempted": True,
                "responsive": True,
                "status": "ok",
                "provider_source": "declared_identity",
                "provider_type": "codex",
                "model": "gpt-5.5",
                "reply_digest": "sha256:model",
                "route_policy": {
                    "decision": "allow",
                    "explicit_lease": True,
                    "model_probe_lease_id": "lease:test:l4-model",
                    "lease_evidence": {
                        "valid": True,
                        "path": str(agents_root / holon_name / "leases" / "model.json"),
                    },
                },
            },
            "artifact": {
                "artifact_id": "holon_l4_artifact:test",
                "digest": "sha256:test",
                "path": str(artifact),
            },
        },
        agents_root=agents_root,
    )
    _write(
        state / "a2a_bus" / "bridge_heartbeats" / f"{holon_name}.json",
        json.dumps({
            "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
            "timestamp": now_iso,
            "agent_uid": holon_name,
            "subject": f"dharma.agent.{holon_name}.inbox",
            "stream": "DHARMA_FLEET",
            "consumer": f"{holon_name}_inbox",
            "status": "IDLE",
            "cycle": 1,
        }),
    )
    _write(
        repo
        / "reports"
        / "sovereign_holons"
        / "verify_holon_harness_prod_20260618T000000Z.json",
        json.dumps({
            "overall_pass": True,
            "timestamp": now_iso,
            "checks": {
                "l4_orchestration_probe_stub": {
                    "pass": True,
                }
            },
        }),
    )
    supervisor_dir = agents_root / holon_name / "supervisor" / "tmux_live"
    _write(
        supervisor_dir / "tmux_supervisor_plan.json",
        json.dumps({
            "schema_version": "dharma.holon_l4_supervisor_plan.v1",
            "tmux_session": tmux_session,
        }),
    )
    _write(
        supervisor_dir / "activation_receipts.jsonl",
        "\n".join([
            json.dumps({
                "target_kind": "launch_artifact",
                "status": "installed",
                "record_hash": "sha256:install",
            }),
            json.dumps({
                "target_kind": "launch_start",
                "status": "activated",
                "record_hash": "sha256:start",
                "created_at": now_iso,
                "service_state_ref": {
                    "service_alive": True,
                    "required_new_record_observed": True,
                    "required_service_id_matched": True,
                    "required_session_id_matched": True,
                },
            }),
        ])
        + "\n",
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        tmux_sessions=[tmux_session],
    )

    holon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "holon.codex_composer_l4"
    ]
    supervisor = holon["raw"]["supervisor_activation"]
    assert holon["status"] == "live"
    assert holon["proof_gaps"] == []
    assert supervisor["status"] == "active"
    assert supervisor["tmux_session"] == tmux_session
    assert supervisor["tmux_session_live"] is True
    assert supervisor["latest_activated_start_receipt_hash"] == "sha256:start"
    assert supervisor["strict_service_bound"] is True
    assert (
        holon["raw"]["model_responsiveness"]["model_responsive_proven"]
        is True
    )


def test_live_ops_census_marks_holon_l4_surface_partial_without_receipts(
    tmp_path: Path,
) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=tmp_path / "state_root",
        run_probes=False,
    )

    holon = {surface["id"]: surface for surface in payload["surfaces"]}[
        "holon.codex_composer_l4"
    ]
    assert holon["status"] == "unknown"
    assert holon["proof_state"] == "partial"
    assert "holon_codex_composer_l4_unknown" in holon["proof_gaps"]
    assert "holon_service_heartbeat_missing" in holon["proof_gaps"]
    assert "holon_transport_a2a_inbox_bridge_heartbeat_missing" in holon["proof_gaps"]
    assert "holon_l4_persisted_proof_missing" in holon["proof_gaps"]
    assert "holon_l4_model_responsive_proof_missing" in holon["proof_gaps"]
    assert "holon_l4_prod_verifier_missing" in holon["proof_gaps"]


def test_live_ops_census_marks_stopped_required_live_p0_surfaces_as_proof_gaps(
    tmp_path: Path,
) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=tmp_path / "state_root",
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    expected = {
        "substrate.dharma_daemon": "substrate_dharma_daemon_stopped",
        "substrate.dharma_cron": "substrate_dharma_cron_stopped",
        "transport.nats": "transport_nats_stopped",
        "dashboard.local": "dashboard_local_stopped",
        "tmux.cockpit": "tmux_cockpit_stopped",
    }
    for surface_id, proof_gap in expected.items():
        surface = surfaces[surface_id]
        assert surface["priority"] == "p0"
        assert surface["desired_state"] == "live"
        assert surface["status"] == "stopped"
        assert proof_gap in surface["proof_gaps"]
        assert surface["proof_state"] == "partial"

    assert surfaces["external.hermes_a2a"]["priority"] == "p1"
    assert surfaces["external.hermes_a2a"]["desired_state"] == "live"
    assert surfaces["external.hermes_a2a"]["proof_gaps"] == []
    assert payload["summary"]["proof_gap_surfaces"] == 10


def test_live_ops_census_marks_stale_p0_surfaces_as_proof_gaps(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state_root"
    _write(
        state_root / "remote_nodes" / "agni" / "kaizen_agni_latest.json",
        json.dumps({"updated_at": "2026-01-01T00:00:00Z"}),
    )

    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=state_root,
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    agni = surfaces["remote.agni"]
    assert agni["status"] == "stale"
    assert agni["priority"] == "p0"
    assert agni["proof_state"] == "partial"
    assert agni["proof_gaps"] == ["remote_agni_stale"]
    assert payload["summary"]["proof_gap_surfaces"] == 10


def test_live_ops_census_marks_unknown_p0_and_supervised_surfaces_as_proof_gaps(
    tmp_path: Path,
) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path / "repo",
        state_root=tmp_path / "state_root",
        run_probes=False,
    )

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    expected = {
        "evidence.nats_receipts": "evidence_nats_receipts_unknown",
        "holon.codex_composer_l4": "holon_codex_composer_l4_unknown",
        "remote.agni": "remote_agni_unknown",
        "mission.forge_reality_arena": "mission_forge_reality_arena_unknown",
    }
    for surface_id, proof_gap in expected.items():
        surface = surfaces[surface_id]
        assert surface["status"] == "unknown"
        assert proof_gap in surface["proof_gaps"]
        assert surface["proof_state"] == "partial"

    assert surfaces["agent.merge_master_mike"]["priority"] == "p1"
    assert surfaces["agent.merge_master_mike"]["status"] == "stopped"
    assert surfaces["agent.merge_master_mike"]["proof_gaps"] == []


def test_live_ops_census_treats_exhausted_forge_arena_as_external_gated(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    _write(
        state / "forge_reality_arena_master" / "codex_overnight_heartbeat.json",
        json.dumps({
            "ts": "2026-06-02T15:52:49Z",
            "cycle": 13,
            "result": "internal packets exhausted",
        }),
    )
    _write(
        repo / "reports" / "agentops" / "work_packets" / "forge-reality-arena-status.json",
        json.dumps({
            "control_watch_tower_visibility": {
                "completion_state": "internal_exhausted_external_gated",
                "remaining_internal_packets": [],
                "autonomy_cycle_policy": {
                    "decision": "stop_internal_autonomy_cycles",
                    "decision_inputs": {
                        "completion_state": "internal_exhausted_external_gated",
                        "external_action_lease_needed": True,
                        "remaining_internal_packet_count": 0,
                    },
                    "next_packet": "operator-approved External Beast lease packet",
                    "reason": "v1 internal proof chain is complete",
                },
            },
        }),
    )

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
    )

    forge = {surface["id"]: surface for surface in payload["surfaces"]}[
        "mission.forge_reality_arena"
    ]
    assert forge["status"] == "blocked"
    assert forge["desired_state"] == "blocked-until-operator-external-lease"
    assert forge["proof_gaps"] == []
    assert forge["proof_state"] == "bound"
    assert forge["human_authority_required"] is True
    assert forge["restart_command"] == ""
    assert forge["stop_policy"] == "external-action-lease-required"
    assert forge["raw"]["external_gate"]["state"] == "external_gated"
    assert payload["summary"]["proof_gap_surfaces"] == 9


def test_dashboard_control_surface_probe_accepts_large_valid_json(monkeypatch) -> None:
    body = json.dumps({
        "data": [{"id": "row-1", "payload": "x" * 70000}],
        "source_errors": [],
    }).encode("utf-8")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return False

        def read(self, limit: int = -1) -> bytes:
            return body if limit < 0 else body[:limit]

    def fake_urlopen(request, timeout):  # noqa: ANN001
        assert request.full_url == "http://127.0.0.1:8420/api/control-surface/rows"
        assert timeout == 5.0
        return Response()

    monkeypatch.setattr(live_ops_census.urllib.request, "urlopen", fake_urlopen)

    result = live_ops_census._http_json_probe(
        "http://127.0.0.1:8420/api/control-surface/rows"
    )

    assert result["state"] == "ok"
    assert result["row_count"] == 1
    assert result["source_error_count"] == 0
    assert result["slow"] is False
    assert result["performance_state"] == "fast"


def test_dashboard_control_surface_probe_reports_slow_json(monkeypatch) -> None:
    body = json.dumps({"data": [], "source_errors": []}).encode("utf-8")
    ticks = iter([10.0, 12.75])

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return False

        def read(self, limit: int = -1) -> bytes:
            return body

    def fake_urlopen(request, timeout):  # noqa: ANN001
        assert timeout == 5.0
        return Response()

    monkeypatch.setattr(live_ops_census.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(live_ops_census.urllib.request, "urlopen", fake_urlopen)

    result = live_ops_census._http_json_probe(
        "http://127.0.0.1:8420/api/control-surface/rows"
    )

    assert result["state"] == "ok"
    assert result["elapsed_seconds"] == 2.75
    assert result["slow"] is True
    assert result["performance_state"] == "slow"
    assert result["timeout_seconds"] == 5.0
    assert result["slow_threshold_seconds"] == 2.0


def test_http_probe_snapshot_uses_dashboard_rows_timeout(monkeypatch) -> None:
    captured: dict[str, float] = {}

    def fake_http_json_probe(url: str, *, timeout_seconds: float, **_kwargs):  # noqa: ANN003
        captured[url] = timeout_seconds
        return {"url": url, "state": "ok"}

    monkeypatch.setattr(live_ops_census, "_http_json_probe", fake_http_json_probe)

    result = live_ops_census._http_probe_snapshot(run_probes=True)

    dashboard_url = live_ops_census.HTTP_PROBES["dashboard_control_surface_rows"]
    assert result["dashboard_control_surface_rows"]["state"] == "ok"
    assert captured[dashboard_url] == live_ops_census.DASHBOARD_ROWS_PROBE_TIMEOUT_SECONDS


def test_live_ops_census_surface_contract_is_complete(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=False,
    )
    surfaces = payload["surfaces"]
    required = {
        "id",
        "label",
        "class",
        "status",
        "desired_state",
        "priority",
        "evidence",
        "authority_refs",
        "restart_command",
        "stop_policy",
        "next_action",
        "human_authority_required",
        "vps_candidate",
        "proof_gaps",
        "proof_state",
        "raw",
    }

    assert payload["summary"]["total"] == len(surfaces) == 17
    for surface in surfaces:
        assert required <= set(surface)
        assert isinstance(surface["evidence"], list)
        assert isinstance(surface["authority_refs"], list)
        assert surface["authority_refs"], surface["id"]
        assert isinstance(surface["restart_command"], str)
        assert isinstance(surface["stop_policy"], str)
        assert isinstance(surface["human_authority_required"], bool)
        assert isinstance(surface["vps_candidate"], bool)
        assert isinstance(surface["proof_gaps"], list)
        assert isinstance(surface["proof_state"], str)

    human_authority_ids = {
        surface["id"]
        for surface in surfaces
        if surface["human_authority_required"]
    }
    assert {
        "revenue.cashclaw_gate",
        "remote.agni",
        "agent.merge_master_mike",
        "load.colima_openclaw",
    } <= human_authority_ids
    assert payload["summary"]["human_authority_required"] == len(human_authority_ids)
    assert payload["summary"]["proof_gap_surfaces"] == sum(
        1 for surface in surfaces if surface["proof_gaps"]
    )


def test_live_ops_census_projects_into_control_surface_rows(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-02T00:00:00Z",
        "surfaces": [
            {
                "id": "revenue.cashclaw_gate",
                "label": "Revenue / CashClaw gate",
                "class": "revenue",
                "status": "blocked",
                "desired_state": "blocked-until-operator-approval",
                "priority": "p0",
                "evidence": ["state/revenue_wedge_last_state.json"],
                "authority_refs": ["docs/governance/ACTIVE_TRACK.yaml"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "keep HOLD until explicit operator approval",
                "raw": {},
            }
        ],
    }
    _write(tmp_path / "docs" / "governance" / "ACTIVE_TRACK.yaml")

    rows = _rows_from_live_ops_census(payload, tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == "live_ops.revenue.cashclaw_gate"
    assert row.kind == "fleet"
    assert row.coherence_state == "drifted"
    assert "human_authority_required" in row.gap_codes
    assert any(ref.path == "docs/governance/ACTIVE_TRACK.yaml" for ref in row.source_refs)

    ctx = _build_human_decision_context(row)
    assert ctx.required is True
    assert "operator authority" in ctx.why_now


def test_live_ops_adapter_skips_dashboard_rows_self_probe_on_cache_miss(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    captured: dict[str, object] = {}

    def fake_build_live_ops_census(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {
            "schema_version": "live_ops_census.v1",
            "generated_at": "2026-06-13T20:40:00Z",
            "surfaces": [],
        }

    monkeypatch.setattr(live_ops_census, "build_live_ops_census", fake_build_live_ops_census)

    payload = live_ops_adapter._live_ops_census_payload(repo)

    assert payload["schema_version"] == "live_ops_census.v1"
    assert captured["repo_root"] == repo
    assert captured["run_probes"] is True
    http_probes = captured["http_probes"]
    assert isinstance(http_probes, dict)
    dashboard_probe = http_probes["dashboard_control_surface_rows"]
    assert dashboard_probe["state"] == "not_checked"
    assert "recursive dashboard rows self-probe" in dashboard_probe["evidence"]


def test_live_ops_adapter_ignores_schema_invalid_fresh_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    output = state / "ops" / "live_process_census.json"
    repo.mkdir()
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    captured: dict[str, object] = {}

    def fake_build_live_ops_census(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {
            "schema_version": "live_ops_census.v1",
            "generated_at": "2026-06-13T20:40:00Z",
            "surfaces": [
                {
                    "id": "adapter.cache_rebuilt",
                    "label": "Cache rebuilt",
                    "class": "substrate",
                    "status": "unknown",
                    "desired_state": "live",
                    "priority": "p0",
                    "evidence": [],
                    "authority_refs": ["scripts/runtime/live_ops_census.py"],
                    "human_authority_required": False,
                    "vps_candidate": False,
                    "proof_gaps": ["cache_invalid_rebuilt"],
                    "proof_state": "partial",
                    "raw": {},
                }
            ],
        }

    monkeypatch.setattr(live_ops_census, "build_live_ops_census", fake_build_live_ops_census)

    payload = live_ops_adapter._live_ops_census_payload(repo)

    assert captured["repo_root"] == repo
    assert payload["surfaces"][0]["id"] == "adapter.cache_rebuilt"


def test_live_ops_adapter_ignores_generated_at_stale_fresh_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    output = state / "ops" / "live_process_census.json"
    repo.mkdir()
    output.parent.mkdir(parents=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": "2000-01-01T00:00:00Z",
                "surfaces": [{"id": "adapter.cache_stale", "status": "live"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    captured: dict[str, object] = {}

    def fake_build_live_ops_census(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {
            "schema_version": "live_ops_census.v1",
            "generated_at": "2026-06-13T20:40:00Z",
            "surfaces": [
                {
                    "id": "adapter.cache_rebuilt_from_stale",
                    "label": "Cache rebuilt from stale generated_at",
                    "class": "substrate",
                    "status": "unknown",
                    "desired_state": "live",
                    "priority": "p0",
                    "evidence": [],
                    "authority_refs": ["scripts/runtime/live_ops_census.py"],
                    "human_authority_required": False,
                    "vps_candidate": False,
                    "proof_gaps": ["cache_generated_at_stale_rebuilt"],
                    "proof_state": "partial",
                    "raw": {},
                }
            ],
        }

    monkeypatch.setattr(live_ops_census, "build_live_ops_census", fake_build_live_ops_census)

    payload = live_ops_adapter._live_ops_census_payload(repo)

    assert captured["repo_root"] == repo
    assert payload["surfaces"][0]["id"] == "adapter.cache_rebuilt_from_stale"


def test_daemon_live_ops_row_is_partial_until_runtime_dispatch_is_proven(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T18:57:03Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "controlled restart plus daemon/default receipt probe required",
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "not_inspected_no_secret_env_dump",
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.substrate.dharma_daemon"
    assert row.observed_state == "live"
    assert row.coherence_state == "partial"
    assert "daemon_dispatch_runtime_unproven" in row.gap_codes
    assert any(
        evidence.source
        == (
            "daemon_dispatch launch=spine_enabled_launch_spec; "
            "running=not_inspected_no_secret_env_dump"
        )
        and evidence.status == "unproven"
        for evidence in row.evidence
    )


def test_daemon_live_ops_row_is_bound_after_runtime_dispatch_proof(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T18:57:03Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "",
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "spine_enabled_self_report",
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.coherence_state == "bound"
    assert "daemon_dispatch_runtime_unproven" not in row.gap_codes
    assert any(
        evidence.source
        == (
            "daemon_dispatch launch=spine_enabled_launch_spec; "
            "running=spine_enabled_self_report"
        )
        and evidence.status == "present"
        for evidence in row.evidence
    )


def test_daemon_live_ops_row_deduplicates_runtime_dispatch_gap(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T20:30:00Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "controlled restart plus daemon/default receipt probe required",
                "proof_gaps": ["daemon_dispatch_runtime_unproven"],
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "not_inspected_no_secret_env_dump",
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.gap_codes.count("daemon_dispatch_runtime_unproven") == 1


def test_daemon_live_ops_row_projects_runtime_receipt_head_evidence(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T22:26:02Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "fix active runtime receipt producers before claiming daemon readiness",
                "proof_gaps": [
                    "daemon_dispatch_runtime_unproven",
                    "daemon_runtime_receipts_active_head_dirty",
                ],
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "not_inspected_no_secret_env_dump",
                    "runtime_receipt_active_head": {
                        "active_head_side_effect_key_clean": False,
                        "runtime_receipts_total": 7601,
                        "latest_created_at": "2026-06-13T22:14:53.872338+00:00",
                        "latest_age_hours": 7.2,
                        "latest_max_age_hours": 6.0,
                        "latest_fresh": False,
                        "windows": [
                            {
                                "window_minutes": 5,
                                "total": 56,
                                "missing_side_effect_key": 56,
                            },
                            {
                                "window_minutes": 15,
                                "total": 168,
                                "missing_side_effect_key": 168,
                            },
                            {
                                "window_minutes": 60,
                                "total": 280,
                                "missing_side_effect_key": 280,
                            },
                        ],
                    },
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert "daemon_runtime_receipts_active_head_dirty" in row.gap_codes
    assert any(
        evidence.kind == "db_probe"
        and evidence.status == "unproven"
        and evidence.source
        == (
            "runtime_receipt_active_head clean=false; "
            "fresh=false; age_hours=7.2; max_age_hours=6.0; "
            "total=7601; latest=2026-06-13T22:14:53.872338+00:00; "
            "windows=5m:56/56,15m:168/168,60m:280/280"
        )
        for evidence in row.evidence
    )


def test_daemon_live_ops_row_projects_provider_model_coverage_evidence(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-14T00:26:02Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "route actual provider/model into runtime receipts before claiming daemon readiness",
                "proof_gaps": [
                    "daemon_dispatch_runtime_unproven",
                    "daemon_runtime_provider_model_unproven",
                ],
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "not_inspected_no_secret_env_dump",
                    "runtime_receipt_coverage": {
                        "coverage_report_available": True,
                        "scope_mode": "since_created_at",
                        "scope_since_created_at": "2026-06-18T16:57:22+00:00",
                        "active_epoch_enabled": True,
                        "active_epoch_receipt_id": "rr-runtime-truth-clean-epoch",
                        "major_task_receipts_total": 3523,
                        "latest_sample_size": 500,
                        "latest_with_provider_payload": 0,
                        "latest_with_model_payload": 0,
                        "latest_with_provider_model_payload": 0,
                        "latest_with_provider_model_provenance": 0,
                        "latest_major_task_receipts_provider_model_percent": 0.0,
                        "latest_major_task_receipts_provider_model_provenance_percent": 0.0,
                        "provider_model_latest_complete": False,
                        "latest_provider_model_unproven_producer_groups": [
                            {
                                "receipt_type": "delegation_run",
                                "provider_model_payload_class": "missing",
                                "producer_source": "ds_goal_cli",
                                "producer_failure_code": "sync_receipt_side_effect_key_missing",
                                "missing_provider_model_provenance": 1,
                            }
                        ],
                        "active_head_gap_producer_groups": [
                            {
                                "window_minutes": 15,
                                "receipt_type": "delegation_run",
                                "producer_source": "ds_goal_cli",
                                "producer_failure_code": "sync_receipt_side_effect_key_missing",
                                "missing_side_effect_key": 1,
                            }
                        ],
                    },
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert "daemon_runtime_provider_model_unproven" in row.gap_codes
    assert any(
        evidence.kind == "db_probe"
        and evidence.status == "unproven"
        and evidence.source
        == (
            "runtime_receipt_provider_model available=true; "
            "scope=since_created_at; scope_since=2026-06-18T16:57:22+00:00; "
            "active_epoch=true; epoch_receipt=rr-runtime-truth-clean-epoch; "
            "latest=0/500; "
            "proof=0/500; accounted=0/500; provider=0/500; model=0/500; "
            "percent=0.0; proof_percent=0.0; accounted_percent=unknown; "
            "terminal=0/0; "
            "terminal_percent=unknown; terminal_proof=0/0; "
            "terminal_proof_percent=unknown; terminal_accounted=0/0; "
            "terminal_accounted_percent=unknown; pending=0; major_total=3523; "
            "active_head_gap_producers="
            "15m:delegation_run/ds_goal_cli/sync_receipt_side_effect_key_missing=1; "
            "provider_model_gap_producers="
            "delegation_run/missing/ds_goal_cli/sync_receipt_side_effect_key_missing=1"
        )
        for evidence in row.evidence
    )


def test_ds_goal_live_ops_row_projects_wrapper_state_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "dharma_swarm"
    stale_repo = tmp_path / "dharma_swarm_main"
    wrapper = tmp_path / ".dharma" / "bin" / "ds-goal"
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-14T13:11:11Z",
        "surfaces": [
            {
                "id": "cli.ds_goal",
                "label": "ds-goal runtime CLI",
                "class": "terminal",
                "status": "live",
                "desired_state": "wrapper-targets-current-runtime-checkout",
                "priority": "p1",
                "evidence": [
                    str(wrapper),
                    str(stale_repo),
                    "ds-goal wrapper resolves to a different checkout than this census",
                ],
                "authority_refs": ["scripts/runtime/autonomy_spine.py"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "use the pinned current-checkout invocation",
                "proof_gaps": [
                    "ds_goal_cli_target_repo_mismatch",
                    "ds_goal_cli_target_lacks_sync_side_effect_hardening",
                ],
                "raw": {
                    "target_repo": str(stale_repo),
                    "current_repo": str(repo),
                    "target_matches_current_repo": False,
                    "safe_current_checkout_invocation": (
                        f"DHARMA_SWARM_REPO={repo} {wrapper}"
                    ),
                    "default_wrapper_target": {
                        "target_repo": str(stale_repo),
                    },
                    "target_sync_receipt_hardening": {
                        "state": "sync_receipt_side_effect_keys_missing",
                    },
                    "longrun_preflight_gate": {
                        "status": "blocked_unpinned_default_target",
                        "passed": False,
                        "operator_convergence_required": True,
                    },
                    "convergence_decision_packet": {
                        "operator_approval_required": True,
                    },
                },
            }
        ],
    }

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.cli.ds_goal"
    assert row.coherence_state == "partial"
    assert "ds_goal_cli_target_repo_mismatch" in row.gap_codes
    assert "human_authority_required" in row.gap_codes
    assert any(
        evidence.kind == "process"
        and evidence.status == "degraded"
        and evidence.provenance_chain
        == ["live_ops_census", "cli.ds_goal", "ds_goal_cli_state"]
        and evidence.source
        == (
            f"ds_goal_cli_state target_repo={stale_repo}; current_repo={repo}; "
            f"matches_current=false; default_target={stale_repo}; "
            "hardening=sync_receipt_side_effect_keys_missing; "
            "preflight=blocked_unpinned_default_target; "
            "operator_approval_required=true; "
            f"safe_pin=DHARMA_SWARM_REPO={repo} {wrapper}"
        )
        for evidence in row.evidence
    )


def test_live_ops_row_projects_process_source_state_evidence(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T23:16:39Z",
        "surfaces": [
            {
                "id": "substrate.dharma_daemon",
                "label": "Dharma daemon",
                "class": "substrate",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["port:7433"],
                "authority_refs": ["docs/state/LIVE_OPS_DASHBOARD.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "controlled restart plus daemon/default receipt probe required",
                "proof_gaps": [
                    "daemon_dispatch_runtime_unproven",
                    "daemon_process_source_stale",
                ],
                "raw": {
                    "dispatch_launch": {
                        "state": "spine_enabled_launch_spec",
                    },
                    "running_dispatch_proof": "not_inspected_no_secret_env_dump",
                    "process_source_state": {
                        "state": "source_changed_after_process_start",
                        "pids": ["93875"],
                        "process_starts": [
                            {
                                "pid": "93875",
                                "started_at": "2026-06-13T13:55:10Z",
                            }
                        ],
                        "newest_source_mtime": "2026-06-13T21:10:58Z",
                        "source_newer_files": [
                            {
                                "path": "dharma_swarm/orchestrator.py",
                                "mtime": "2026-06-13T21:10:58Z",
                            }
                        ],
                    },
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "state" / "LIVE_OPS_DASHBOARD.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    evidence = next(
        item
        for item in row.evidence
        if item.source.startswith("process_source_state state=")
    )
    assert evidence.status == "degraded"
    assert evidence.source == (
        "process_source_state state=source_changed_after_process_start; "
        "starts=93875@2026-06-13T13:55:10Z; "
        "newest_source=2026-06-13T21:10:58Z; "
        "newer_files=dharma_swarm/orchestrator.py@2026-06-13T21:10:58Z"
    )
    assert evidence.provenance_chain == [
        "live_ops_census",
        "substrate.dharma_daemon",
        "process_source_state",
    ]
    assert evidence.raw_content is not None
    assert "source_changed_after_process_start" in evidence.raw_content


def test_dashboard_live_ops_row_is_partial_when_control_surface_probe_fails(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T18:57:03Z",
        "surfaces": [
            {
                "id": "dashboard.local",
                "label": "Dashboard API and web",
                "class": "dashboard",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["127.0.0.1:8420", "control_surface_rows=timeout"],
                "authority_refs": ["ACTIVE_SURFACE_MANIFEST.yaml"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "inspect or restart dashboard API",
                "raw": {
                    "control_surface_rows_probe": {
                        "state": "timeout",
                        "evidence": "timed out",
                    },
                },
            }
        ],
    }
    _write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.dashboard.local"
    assert row.observed_state == "live"
    assert row.coherence_state == "partial"
    assert "dashboard_control_surface_rows_unproven" in row.gap_codes
    assert any(
        evidence.source == "dashboard_control_surface_rows=timeout"
        and evidence.status == "unproven"
        for evidence in row.evidence
    )


def test_dashboard_live_ops_row_deduplicates_control_surface_gap(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T20:30:00Z",
        "surfaces": [
            {
                "id": "dashboard.local",
                "label": "Dashboard API and web",
                "class": "dashboard",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["127.0.0.1:8420", "control_surface_rows=timeout"],
                "authority_refs": ["ACTIVE_SURFACE_MANIFEST.yaml"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "inspect or restart dashboard API",
                "proof_gaps": ["dashboard_control_surface_rows_unproven"],
                "raw": {
                    "control_surface_rows_probe": {
                        "state": "timeout",
                        "evidence": "timed out",
                    },
                },
            }
        ],
    }
    _write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.gap_codes.count("dashboard_control_surface_rows_unproven") == 1


def test_dashboard_live_ops_row_is_bound_when_control_surface_probe_answers(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T18:57:03Z",
        "surfaces": [
            {
                "id": "dashboard.local",
                "label": "Dashboard API and web",
                "class": "dashboard",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": ["127.0.0.1:8420", "control_surface_rows=ok"],
                "authority_refs": ["ACTIVE_SURFACE_MANIFEST.yaml"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "",
                "raw": {
                    "control_surface_rows_probe": {
                        "state": "ok",
                        "row_count": 12,
                    },
                },
            }
        ],
    }
    _write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.coherence_state == "bound"
    assert "dashboard_control_surface_rows_unproven" not in row.gap_codes
    assert any(
        evidence.source == "dashboard_control_surface_rows=ok"
        and evidence.status == "present"
        for evidence in row.evidence
    )


def test_dashboard_live_ops_row_treats_self_probe_skip_as_non_failure(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-14T00:20:00Z",
        "surfaces": [
            {
                "id": "dashboard.local",
                "label": "Dashboard API and web",
                "class": "dashboard",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": [
                    "127.0.0.1:8420",
                    "control_surface_rows=not_checked",
                ],
                "authority_refs": ["ACTIVE_SURFACE_MANIFEST.yaml"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "",
                "raw": {
                    "control_surface_rows_probe": {
                        "state": "not_checked",
                        "evidence": (
                            "skipped inside control-surface row projection to "
                            "avoid recursive dashboard rows self-probe"
                        ),
                    },
                },
            }
        ],
    }
    _write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.coherence_state == "bound"
    assert "dashboard_control_surface_rows_unproven" not in row.gap_codes
    assert any(
        evidence.source == "dashboard_control_surface_rows=not_checked"
        and evidence.status == "skipped"
        for evidence in row.evidence
    )


def test_dashboard_live_ops_row_stays_bound_when_control_surface_probe_is_slow(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T20:20:00Z",
        "surfaces": [
            {
                "id": "dashboard.local",
                "label": "Dashboard API and web",
                "class": "dashboard",
                "status": "live",
                "desired_state": "live",
                "priority": "p0",
                "evidence": [
                    "127.0.0.1:8420",
                    "control_surface_rows=ok",
                    "control_surface_rows_elapsed=2.8s",
                ],
                "authority_refs": ["ACTIVE_SURFACE_MANIFEST.yaml"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "profile dashboard API rows endpoint; live proof is slow",
                "raw": {
                    "control_surface_rows_probe": {
                        "state": "ok",
                        "row_count": 20,
                        "elapsed_seconds": 2.8,
                        "slow": True,
                        "performance_state": "slow",
                    },
                },
            }
        ],
    }
    _write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.coherence_state == "bound"
    assert "dashboard_control_surface_rows_unproven" not in row.gap_codes
    assert "dashboard_control_surface_rows_slow" not in row.gap_codes
    assert any(
        evidence.source == "dashboard_control_surface_rows=ok"
        and evidence.status == "present"
        for evidence in row.evidence
    )


def test_live_ops_row_preserves_generic_census_proof_gaps(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T19:57:00Z",
        "surfaces": [
            {
                "id": "transport.a2a_bridge",
                "label": "A2A inbox delivery bridge",
                "class": "substrate",
                "status": "live",
                "desired_state": "delivery-handler-not-semantic-peer",
                "priority": "p0",
                "evidence": ["scripts/runtime/a2a_inbox_bridge.py"],
                "authority_refs": ["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "",
                "proof_gaps": ["a2a_inbox_bridge_heartbeat_missing"],
                "raw": {
                    "bridge_kind": "filesystem_delivery_handler",
                    "semantic_reply_claim": False,
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.transport.a2a_bridge"
    assert row.coherence_state == "partial"
    assert "a2a_inbox_bridge_heartbeat_missing" in row.gap_codes
    assert any(
        evidence.source == "proof_gap=a2a_inbox_bridge_heartbeat_missing"
        and evidence.status == "unproven"
        for evidence in row.evidence
    )


def test_stopped_a2a_bridge_row_projects_stopped_proof_gap(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-13T23:47:24Z",
        "surfaces": [
            {
                "id": "transport.a2a_bridge",
                "label": "A2A inbox delivery bridge",
                "class": "substrate",
                "status": "stopped",
                "desired_state": "delivery-handler-not-semantic-peer",
                "priority": "p0",
                "evidence": ["scripts/runtime/a2a_inbox_bridge.py"],
                "authority_refs": ["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "start governed inbox delivery bridge if live A2A delivery is required",
                "proof_gaps": ["a2a_inbox_bridge_stopped"],
                "raw": {
                    "bridge_kind": "filesystem_delivery_handler",
                    "process_live": False,
                    "tmux_session_live": False,
                    "heartbeat_exists": True,
                    "heartbeat_fresh": False,
                    "heartbeat_age_hours": 66.06,
                    "consumer_probe": {
                        "state": "consumer_inspectable",
                        "num_pending": 0,
                        "num_ack_pending": 0,
                    },
                    "semantic_reply_claim": False,
                    "peer_model_processed_claim": False,
                    "a2a_lifecycle": {
                        "sent": "send_receipt_found",
                        "handler_ack": "handler_acked",
                        "domain_receipt": "missing",
                        "completed": "incomplete",
                    },
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.transport.a2a_bridge"
    assert row.coherence_state == "drifted"
    assert "live_ops_not_live" in row.gap_codes
    assert "a2a_inbox_bridge_stopped" in row.gap_codes
    assert any(
        evidence.source == "proof_gap=a2a_inbox_bridge_stopped"
        and evidence.status == "unproven"
        for evidence in row.evidence
    )
    bridge_evidence = next(
        item for item in row.evidence if item.source.startswith("a2a_bridge_state ")
    )
    assert bridge_evidence.status == "degraded"
    assert bridge_evidence.source == (
        "a2a_bridge_state process_live=false; tmux_live=false; "
        "heartbeat=stale; heartbeat_age_hours=66.06; "
        "consumer=consumer_inspectable; pending=0; ack_pending=0; "
        "sent=send_receipt_found; handler_ack=handler_acked; "
        "domain_receipt=missing; semantic_reply=false; "
        "peer_model_processed=false; completed=false"
    )
    assert bridge_evidence.raw_content is not None
    assert "consumer_inspectable" in bridge_evidence.raw_content


def test_nats_receipts_row_projects_ack_tier_state(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-14T00:40:00Z",
        "surfaces": [
            {
                "id": "evidence.nats_receipts",
                "label": "NATS receipts and logs",
                "class": "evidence",
                "status": "live",
                "desired_state": "ack-receipt-evidence",
                "priority": "p0",
                "evidence": ["/Users/dhyana/.dharma/a2a_bus/nats_live_receipt.json"],
                "authority_refs": ["docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"],
                "human_authority_required": False,
                "vps_candidate": False,
                "next_action": "collect fresh HANDLER_ACKED receipt",
                "proof_gaps": ["nats_hot_contact_ack_stale"],
                "raw": {
                    "ack_tier_state": {
                        "operator_hot_contact_ready": False,
                        "operator_hot_contact_max_age_hours": 24.0,
                        "live_probe": {
                            "ack_verified": True,
                            "ack_tier": "DELIVERED_TO_CONSUMER",
                            "age_hours": 0.01,
                        },
                        "hot_contact": {
                            "ack_tier": "HANDLER_ACKED",
                            "age_hours": 210.5,
                        },
                    }
                },
            }
        ],
    }
    _write(tmp_path / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md")

    row = _rows_from_live_ops_census(payload, tmp_path)[0]

    assert row.id == "live_ops.evidence.nats_receipts"
    assert row.coherence_state == "partial"
    evidence = next(
        item for item in row.evidence if item.source.startswith("nats_ack_tier_state ")
    )
    assert evidence.kind == "go_receipt"
    assert evidence.status == "degraded"
    assert evidence.source == (
        "nats_ack_tier_state live_probe=DELIVERED_TO_CONSUMER; "
        "live_verified=true; live_age_hours=0.01; "
        "hot_contact=HANDLER_ACKED; hot_age_hours=210.5; "
        "hot_max_age_hours=24.0; ready=false"
    )
    assert evidence.raw_content is not None
    assert "operator_hot_contact_ready" in evidence.raw_content


def test_live_ops_rows_preserve_operator_contract_fields(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-02T00:00:00Z",
        "surfaces": [
            {
                "id": "remote.agni",
                "label": "AGNI remote watcher / trading",
                "class": "remote",
                "status": "stale",
                "desired_state": "remote-observed-or-blocked",
                "priority": "p0",
                "evidence": ["remote_nodes/agni/kaizen_agni_latest.json"],
                "authority_refs": ["docs/ops/TMUX_AGENT_SUBSTRATE.md"],
                "human_authority_required": True,
                "vps_candidate": True,
                "next_action": "refresh remote receipts and feeds",
                "restart_command": "ssh agni  # inspect remote receipts before launching anything",
                "stop_policy": "no-real-money-without-operator-approval",
                "raw": {"ack": "fixture"},
            },
            {
                "id": "load.colima_openclaw",
                "label": "Colima / OpenClaw VM",
                "class": "heavy",
                "status": "live",
                "desired_state": "operator-choice",
                "priority": "p2",
                "evidence": ["colima-openclaw-secure"],
                "authority_refs": ["docs/ops/LIVE_OPS_COCKPIT.md"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "stop for battery/flight if not needed",
                "restart_command": "colima start openclaw-secure",
                "stop_policy": "safe-to-stop-if-not-using-openclaw",
                "raw": {},
            },
        ],
    }
    _write(tmp_path / "docs" / "ops" / "TMUX_AGENT_SUBSTRATE.md")
    _write(tmp_path / "docs" / "ops" / "LIVE_OPS_COCKPIT.md")

    rows = {row.id: row for row in _rows_from_live_ops_census(payload, tmp_path)}
    agni = rows["live_ops.remote.agni"]
    assert agni.observed_state == "stale"
    assert "live_ops_status:stale" in agni.gap_codes
    assert "live_ops_not_live" in agni.gap_codes
    assert "human_authority_required" in agni.gap_codes
    assert "vps_candidate" in agni.gap_codes
    assert agni.raw["restart_command"].startswith("ssh agni")
    assert agni.raw["stop_policy"] == "no-real-money-without-operator-approval"
    assert any(ref.path == "docs/ops/TMUX_AGENT_SUBSTRATE.md" and ref.exists for ref in agni.source_refs)
    assert any(ev.source == "remote_nodes/agni/kaizen_agni_latest.json" for ev in agni.evidence)

    colima = rows["live_ops.load.colima_openclaw"]
    assert colima.observed_state == "live"
    assert "heavy_local_load" in colima.gap_codes
    assert "human_authority_required" in colima.gap_codes
    assert colima.raw["restart_command"] == "colima start openclaw-secure"
    assert colima.raw["stop_policy"] == "safe-to-stop-if-not-using-openclaw"


def test_control_surface_summary_names_live_ops_source() -> None:
    summary = build_control_surface_summary(rows=[])
    assert "live_ops_census" in summary["sources_consulted"]


def test_build_live_ops_census_without_write_does_not_create_receipt(tmp_path: Path) -> None:
    output = tmp_path / "state" / "ops" / "live_process_census.json"

    payload = live_ops_census.build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=False,
    )

    assert payload["schema_version"] == "live_ops_census.v1"
    assert not output.exists()


def test_live_ops_census_cli_requires_write_flag_for_receipt(monkeypatch, capsys, tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "live_ops_census.py",
            "--repo-root",
            str(tmp_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output",
            str(output),
            "--no-probes",
        ],
    )

    assert live_ops_census.main() == 0
    assert not output.exists()
    assert "live_ops_census.v1" in capsys.readouterr().out


def test_write_census_publishes_receipt_atomically(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "ops" / "live_process_census.json"
    output.parent.mkdir(parents=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "live_ops_census.v1",
                "generated_at": "old",
                "surfaces": [{"id": "old.surface", "status": "live"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original_replace = live_ops_census.os.replace
    replace_calls: list[tuple[Path, Path]] = []

    def replace_probe(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        assert json.loads(output.read_text(encoding="utf-8"))["generated_at"] == "old"
        assert json.loads(src_path.read_text(encoding="utf-8"))["generated_at"] == "new"
        replace_calls.append((src_path, dst_path))
        original_replace(src, dst)

    monkeypatch.setattr(live_ops_census.os, "replace", replace_probe)

    live_ops_census.write_census(
        {
            "schema_version": "live_ops_census.v1",
            "generated_at": "new",
            "surfaces": [{"id": "substrate.dharma_daemon"}],
        },
        output,
    )

    assert replace_calls
    assert replace_calls[0][1] == output
    assert json.loads(output.read_text(encoding="utf-8"))["generated_at"] == "new"
    assert not list(output.parent.glob(f".{output.name}.*.tmp"))


def test_control_surface_live_ops_adapter_does_not_write_receipts() -> None:
    tree = ast.parse((REPO_ROOT / "dharma_swarm/operator_core/control_surface_live_ops.py").read_text())
    write_calls: list[str] = []
    forbidden_path_attrs = {
        "chmod",
        "mkdir",
        "open",
        "rename",
        "replace",
        "rmdir",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_path_attrs:
            if node.func.attr == "replace" and any(
                keyword.arg == "tzinfo" for keyword in node.keywords
            ):
                continue
            write_calls.append(node.func.attr)
        if isinstance(node.func, ast.Name) and node.func.id in {"open", "write_census"}:
            write_calls.append(node.func.id)
    assert write_calls == []


def test_live_ops_census_subprocess_is_centralized_in_run_helper() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    call_owners: list[str] = []
    shell_true_locations: list[int] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
            ):
                call_owners.append(self.stack[-1] if self.stack else "<module>")
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                        if keyword.value.value is True:
                            shell_true_locations.append(node.lineno)
            self.generic_visit(node)

    Visitor().visit(tree)
    assert call_owners == ["_run"]
    assert shell_true_locations == []


def test_live_ops_census_writes_only_from_explicit_write_census_function() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    write_owners: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            path_write_attrs = {"mkdir", "write_text", "write_bytes", "unlink"}
            if isinstance(node.func, ast.Attribute) and node.func.attr in path_write_attrs:
                write_owners.append(self.stack[-1] if self.stack else "<module>")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "replace"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
            ):
                write_owners.append(self.stack[-1] if self.stack else "<module>")
            self.generic_visit(node)

    Visitor().visit(tree)
    assert write_owners
    assert set(write_owners) == {"write_census"}


def test_live_ops_census_has_no_process_control_api_calls() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    forbidden_names = {"system", "popen", "spawn", "kill", "killpg", "execv", "execve"}
    forbidden_subprocess_attrs = {"Popen", "call", "check_call", "check_output"}
    observed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"os", "subprocess"}
        ):
            if node.func.value.id == "subprocess" and node.func.attr in forbidden_subprocess_attrs:
                observed.append(f"subprocess.{node.func.attr}")
            if node.func.value.id == "os" and node.func.attr in forbidden_names:
                observed.append(f"os.{node.func.attr}")
    assert observed == []


def test_live_ops_census_only_uses_read_only_probe_commands_static_including_nats_consumer_info() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    allowed = {"git", "launchctl", "pgrep", "lsof", "ps", "tmux", "nats"}
    observed: set[str] = set()
    nats_invocations: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_run":
            continue
        if not node.args or not isinstance(node.args[0], ast.List) or not node.args[0].elts:
            continue
        first = node.args[0].elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            observed.add(first.value)
            if first.value == "nats":
                args: list[str] = []
                for element in node.args[0].elts:
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        args.append(element.value)
                    else:
                        args.append("<dynamic>")
                nats_invocations.append(args)
    assert observed
    assert observed <= allowed
    assert nats_invocations == [[
        "nats",
        "--no-context",
        "--server",
        "<dynamic>",
        "consumer",
        "info",
        "<dynamic>",
        "<dynamic>",
        "--json",
    ]]


def test_live_ops_census_does_not_execute_displayed_policy_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(live_ops_census.subprocess, "run", fake_run)

    payload = live_ops_census.build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=True,
    )

    allowed = {"git", "launchctl", "pgrep", "lsof", "ps", "tmux"}
    observed = {call[0] for call in calls}
    display_first_words = {
        str(surface.get("restart_command", "")).split()[0]
        for surface in payload["surfaces"]
        if str(surface.get("restart_command", "")).strip()
    }
    assert observed
    assert observed <= allowed
    assert not (display_first_words - allowed) & observed


def test_dharma_daemon_pattern_matches_container_and_cli_spellings():
    """Dockerfile.swarm boots `python -m dharma_swarm.orchestrate_live`; the
    CLI-only pattern could never match that cmdline, so the census reported
    the daemon dead on every containerized host."""
    import re

    pattern = live_ops_census.PROCESS_PATTERNS["dharma_daemon"]
    assert re.search(pattern, "python -m dharma_swarm.orchestrate_live")
    assert re.search(pattern, "python3 -m dharma_swarm.dgc_cli orchestrate-live")
    assert not re.search(pattern, "python3 -m dharma_swarm.dgc_cli cron daemon")
