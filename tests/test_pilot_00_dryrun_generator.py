from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_protocol" / "pilot_00_dryrun_generator.py"

spec = importlib.util.spec_from_file_location("pilot_00_dryrun_generator", MODULE_PATH)
assert spec is not None
pilot = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = pilot
spec.loader.exec_module(pilot)


def test_generates_shape_only_dryrun_bundle(tmp_path: Path) -> None:
    input_spec = tmp_path / "docs_atom_oneline.md"
    input_spec.write_text(
        """# docs_atom_oneline

Telos: Add a one-line docstring to `dharma_swarm/math_bridges.py:TaskResult.is_ok`.

Allowed paths:
- dharma_swarm/math_bridges.py

Forbidden paths:
- dharma_swarm/orchestrate_live.py
- dharma_swarm/swarm.py
- dharma_swarm/frontier_council.py
- dharma_swarm/agent_runner.py
- dharma_swarm/guardian_crew.py
- dharma_swarm/insight_brief.py
- api/**
- dashboard/**

Proof command:
pytest tests/test_math_bridges.py -q

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )

    output_dir = pilot.generate(input_spec, tmp_path / "dryruns", "pilot-00-test")

    assert (output_dir / "build_packet.json").is_file()
    assert (output_dir / "work_packets" / "wp_001.json").is_file()
    assert (output_dir / "dispatch_plan.md").is_file()
    assert (output_dir / "proof_command.txt").read_text(encoding="utf-8").splitlines() == [
        "pytest tests/test_math_bridges.py -q"
    ]
    assert (output_dir / "gates_required.txt").read_text(encoding="utf-8").splitlines() == [
        "telos",
        "scoped_tests",
        "scope_check",
    ]

    build_packet = json.loads((output_dir / "build_packet.json").read_text(encoding="utf-8"))
    work_packet = json.loads((output_dir / "work_packets" / "wp_001.json").read_text(encoding="utf-8"))

    assert build_packet["metadata"]["kind"] == "build_packet"
    assert build_packet["metadata"]["protocol_version"] == "v0"
    assert build_packet["metadata"]["child_task_ids"] == ["wp_001"]
    assert work_packet["payload"]["kind"] == "work_packet"
    assert work_packet["scope"] == ["dharma_swarm/math_bridges.py"]
    assert work_packet["payload"]["allowed_paths"] == ["dharma_swarm/math_bridges.py"]
    assert work_packet["constraints"] == ["no_merge", "no_push", "no_shell_exec", "scope_locked"]
    assert work_packet["metadata"]["dry_run"] is True

    dispatch_plan = (output_dir / "dispatch_plan.md").read_text(encoding="utf-8")
    assert "spawns no agent" in dispatch_plan
    assert "writes no SQLite state" in dispatch_plan


def test_rejects_unknown_or_unbounded_input(tmp_path: Path) -> None:
    input_spec = tmp_path / "bad.md"
    input_spec.write_text(
        """# bad

Telos: TBD

Allowed paths:
- dharma_swarm/math_bridges.py

Forbidden paths:
- dharma_swarm/agent_runner.py

Proof command:
pytest tests/test_math_bridges.py -q

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )

    try:
        pilot.generate(input_spec, tmp_path / "dryruns", "bad")
    except ValueError as exc:
        assert "telos must be concrete" in str(exc)
    else:
        raise AssertionError("expected invalid pilot spec to fail")
