from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.build_protocol.pilot00_dryrun_generator import parse_spec, run_dryrun


def _write_spec(path: Path) -> None:
    path.write_text(
        """# TaskResult is_ok docstring

Telos: Add a one-line docstring to dharma_swarm/math_bridges.py:TaskResult.is_ok without changing behavior.

Allowed paths:
- dharma_swarm/math_bridges.py

Forbidden paths:
- dharma_swarm/orchestrate_live.py
- api/**

Proof command:
pytest tests/test_math_bridges.py -q

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )


def test_parse_spec_extracts_required_fields(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.md"
    _write_spec(spec_path)

    spec = parse_spec(spec_path)

    assert spec.title == "taskresult_is_ok_docstring"
    assert spec.allowed_paths == ("dharma_swarm/math_bridges.py",)
    assert spec.proof_command == "pytest tests/test_math_bridges.py -q"
    assert spec.reviewer == "codex-reviewer"
    assert "dharma_swarm/orchestrate_live.py" in spec.forbidden_paths


def test_run_dryrun_emits_required_artifacts(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.md"
    output_base = tmp_path / "dryruns"
    _write_spec(spec_path)

    result = run_dryrun(
        spec_path,
        output_base=output_base,
        run_id="pilot-00-test",
        now=datetime(2026, 5, 6, tzinfo=timezone.utc),
    )

    expected = {
        "build_packet.json",
        "dispatch_plan.md",
        "gates_required.txt",
        "pre_flight_answers.md",
        "proof_command.txt",
        "rejected_paths.txt",
        "source_spec_copy.md",
        "validation_report.json",
        "work_packets",
    }
    assert {path.name for path in result.root.iterdir()} == expected
    assert (result.root / "work_packets" / "wp_001.json").exists()


def test_run_dryrun_build_and_work_packet_shapes(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.md"
    _write_spec(spec_path)

    result = run_dryrun(spec_path, output_base=tmp_path, run_id="run")
    build_packet = json.loads((result.root / "build_packet.json").read_text(encoding="utf-8"))
    work_packet = json.loads((result.root / "work_packets" / "wp_001.json").read_text(encoding="utf-8"))

    assert build_packet["title"] == "taskresult_is_ok_docstring"
    assert build_packet["metadata"]["kind"] == "build_packet"
    assert build_packet["metadata"]["protocol_version"] == "v0"
    assert build_packet["metadata"]["proof_command"] == "pytest tests/test_math_bridges.py -q"
    assert build_packet["metadata"]["approval_signature"].startswith("sha256:")
    assert work_packet["payload"]["kind"] == "work_packet"
    assert work_packet["payload"]["parent_build_packet_id"] == "taskresult_is_ok_docstring"
    assert work_packet["payload"]["allowed_paths"] == ["dharma_swarm/math_bridges.py"]
    assert work_packet["constraints"] == ["no_merge", "no_push", "no_shell_exec", "scope_locked"]


def test_dryrun_scope_validation_targets_allowed_paths_only(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.md"
    _write_spec(spec_path)

    result = run_dryrun(spec_path, output_base=tmp_path, run_id="run")
    work_packet = json.loads((result.root / "work_packets" / "wp_001.json").read_text(encoding="utf-8"))
    editable_paths = [*work_packet["scope"], *work_packet["payload"]["allowed_paths"]]

    forbidden_terms = ("orchestrate_live", "swarm.py", "agent_runner", "dashboard", "api")
    assert all(not any(term in path for term in forbidden_terms) for path in editable_paths)
    assert (result.root / "proof_command.txt").read_text(encoding="utf-8").count("\n") == 1
    assert "I don't know" not in (result.root / "pre_flight_answers.md").read_text(encoding="utf-8")


def test_parse_spec_rejects_missing_proof_command(tmp_path: Path) -> None:
    spec_path = tmp_path / "bad.md"
    spec_path.write_text(
        """# Bad Spec

Telos: Do something.

Allowed paths:
- dharma_swarm/math_bridges.py

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Proof command"):
        parse_spec(spec_path)
