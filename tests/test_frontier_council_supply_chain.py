from __future__ import annotations

import json
from pathlib import Path
import sys

from dharma_swarm.frontier_council import (
    ARCHIVE_RECEIPT_SCHEMA,
    VERIFIER_RECEIPT_SCHEMA,
    run_full_supply_chain,
)
from dharma_swarm.world_radar.bronze import ingest_rows_to_bronze
from dharma_swarm.world_radar.cli import main
from dharma_swarm.world_radar.io_utils import write_json_atomic


def test_full_supply_chain_closes_single_source_signal_as_halt(tmp_path: Path) -> None:
    state, boundary_path, _raw_path = _bronze_boundary(tmp_path)

    result = run_full_supply_chain(
        boundary_path,
        state_dir=state,
        sandbox_command=(sys.executable, "-c", "print('sandbox ok')"),
        sandbox_cwd=Path.cwd(),
        timeout_s=5,
    )

    assert result.ok is True
    assert result.decision_kind == "halt"
    verifier = _read_json(Path(result.verifier_receipt_path))
    sandbox = _read_json(Path(result.sandbox_result_path))
    archive = _read_json(Path(result.archive_receipt_path))
    assert verifier["schema_version"] == VERIFIER_RECEIPT_SCHEMA
    assert verifier["decision"]["reason"] == "insufficient_independent_corroboration"
    assert verifier["guardrails"]["may_apply_code"] is False
    assert sandbox["passed"] is True
    assert archive["schema_version"] == ARCHIVE_RECEIPT_SCHEMA
    assert archive["status"] == "closed_halt"
    assert archive["not_applied"] is True
    assert archive["lineage"]["verifier_receipt"] == verifier["verifier_receipt_id"]
    assert archive["lineage"]["implementation"] == "no_change"
    assert len(Path(result.archive_ledger_path).read_text(encoding="utf-8").splitlines()) == 1


def test_full_supply_chain_can_emit_one_scorable_task_when_corroborated(tmp_path: Path) -> None:
    state, boundary_path, raw_path = _bronze_boundary(tmp_path)
    raw = _read_json(raw_path)
    raw["corroboration"] = {
        "required_k": 2,
        "observed_k": 2,
        "status": "corroborated",
        "independent_source_urls": [
            raw["source_url"],
            "https://example.org/independent-verifier-note",
        ],
    }
    write_json_atomic(raw_path, raw)

    result = run_full_supply_chain(
        boundary_path,
        state_dir=state,
        sandbox_command=(sys.executable, "-c", "print('task sandbox ok')"),
        sandbox_cwd=Path.cwd(),
        timeout_s=5,
    )

    verifier = _read_json(Path(result.verifier_receipt_path))
    archive = _read_json(Path(result.archive_receipt_path))
    assert result.decision_kind == "scorable_task"
    task = verifier["decision"]["task"]
    assert task["quality_metric"] == "sandbox_command_exit_code_zero"
    assert task["sandbox_command_required"] is True
    assert archive["status"] == "closed_scorable_task"
    assert archive["lineage"]["kept_claim"] == "scorable_task"
    assert archive["not_applied"] is True


def test_world_radar_cli_runs_full_chain(tmp_path: Path, capsys) -> None:
    state, boundary_path, _raw_path = _bronze_boundary(tmp_path)

    rc = main(
        [
            "run-full-chain",
            "--boundary-path",
            str(boundary_path),
            "--state-dir",
            str(state),
            "--timeout-s",
            "5",
            "--sandbox-command",
            sys.executable,
            "-c",
            "print('cli sandbox ok')",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision_kind"] == "halt"
    assert payload["sandbox_passed"] is True
    assert Path(payload["archive_receipt_path"]).exists()


def _bronze_boundary(tmp_path: Path) -> tuple[Path, Path, Path]:
    state = tmp_path / ".dharma"
    result = ingest_rows_to_bronze(
        [
            {
                "id": "operator-zeroshot-001",
                "source": "operator_drop",
                "source_type": "operator_drop",
                "title": "Zeroshot, an open-source CLI for coding-agent verification loops",
                "description": "Operator-attested public signal for verifier review.",
                "url": "https://github.com/the-open-engine/zeroshot",
                "keywords": ["agentic", "verification"],
                "observed_at": "2026-06-20T00:00:00+00:00",
            }
        ],
        state_dir=state,
        fetched_at="2026-06-20T00:00:00+00:00",
    )
    assert result.boundary_written == 1
    return state, Path(result.boundary_paths[0]), Path(result.receipt_paths[0])


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
