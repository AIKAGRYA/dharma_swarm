from __future__ import annotations

import sqlite3
from pathlib import Path

from dharma_swarm.runtime_context import (
    build_runtime_context_packet,
    provider_route_snapshot,
)


def _write_provider_attempts(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE provider_attempts (
                decision_id TEXT NOT NULL,
                attempt_idx INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                tier TEXT NOT NULL DEFAULT 'unknown',
                success INTEGER NOT NULL DEFAULT 0,
                outcome TEXT NOT NULL DEFAULT 'unknown',
                error_class TEXT NOT NULL DEFAULT '',
                error_detail TEXT NOT NULL DEFAULT '',
                duration_ms REAL NOT NULL DEFAULT 0.0,
                stop_reason TEXT NOT NULL DEFAULT '',
                usage_json TEXT NOT NULL DEFAULT '{}',
                cost_estimate_usd REAL NOT NULL DEFAULT 0.0,
                circuit_state TEXT NOT NULL DEFAULT 'closed',
                schema_version TEXT NOT NULL DEFAULT 'v1',
                created_at TEXT NOT NULL,
                PRIMARY KEY (decision_id, attempt_idx)
            )
            """
        )
        db.executemany(
            """
            INSERT INTO provider_attempts (
                decision_id, attempt_idx, provider, model, tier, success,
                outcome, error_class, error_detail, duration_ms, circuit_state,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "d1",
                    0,
                    "openrouter",
                    "z-ai/glm-5",
                    "frontier",
                    0,
                    "Error code: 402",
                    "billing_exhausted",
                    "Insufficient credits",
                    10.0,
                    "closed",
                    "2026-06-20T03:14:45+00:00",
                ),
                (
                    "d2",
                    0,
                    "ollama",
                    "qwen3-coder:480b-cloud",
                    "frontier",
                    1,
                    "success",
                    "",
                    "",
                    200.0,
                    "closed",
                    "2026-06-20T03:15:45+00:00",
                ),
            ],
        )


def test_provider_route_snapshot_reads_live_success_and_blocked_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "state" / "runtime.db"
    _write_provider_attempts(db_path)
    monkeypatch.setenv("DGC_ROUTER_TELEMETRY_DB", str(db_path))

    snapshot = provider_route_snapshot(state_dir=tmp_path)

    assert snapshot["available"] is True
    assert "ollama:qwen3-coder:480b-cloud" in snapshot["recent_success_lanes"]
    assert "openrouter:z-ai/glm-5" in snapshot["blocked_lanes"]
    statuses = {lane["route_key"]: lane["status"] for lane in snapshot["lanes"]}
    assert statuses["ollama:qwen3-coder:480b-cloud"] == "live_success"
    assert statuses["openrouter:z-ai/glm-5"] == "blocked"
    assert snapshot["latest_attempts"][0]["error_detail"] == ""


def test_build_runtime_context_packet_is_secret_free_and_machine_readable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "state" / "runtime.db"
    _write_provider_attempts(db_path)
    monkeypatch.setenv("DGC_ROUTER_TELEMETRY_DB", str(db_path))

    packet = build_runtime_context_packet(
        repo_root=tmp_path,
        state_dir=tmp_path,
        health={"status": "ok"},
        runtime_truth={
            "schema_version": "runtime_truth_closeout.v1",
            "status": "fail",
            "passed": False,
            "checks": [
                {
                    "id": "provider_model_accounted",
                    "passed": False,
                    "evidence": "sample below threshold",
                }
            ],
        },
        provider_status={"shadow_mode": True},
    )

    assert packet["schema"] == "dharma_swarm.runtime_context.v1"
    assert packet["secrets_included"] is False
    assert packet["daemon"]["status"] == "ok"
    assert packet["runtime_truth"]["failed_checks"] == ["provider_model_accounted"]
    assert packet["provider_routes"]["recent_success_lanes"] == [
        "ollama:qwen3-coder:480b-cloud"
    ]
    assert "OPENROUTER_API_KEY" not in str(packet)
