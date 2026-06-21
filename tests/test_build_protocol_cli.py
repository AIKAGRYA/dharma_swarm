from __future__ import annotations

import json
from pathlib import Path
import sys

from dharma_swarm.runtime_contract import validate_envelope
from tools.build_protocol.cli import main


def test_plan_command_emits_dryrun_root(tmp_path: Path, capsys) -> None:
    spec = tmp_path / "work.md"
    output_base = tmp_path / "dryruns"
    spec.write_text(
        """# CLI Plan Smoke

Telos: Emit a dry-run bundle from a markdown work spec.

Allowed paths:
- tools/build_protocol/cli.py

Forbidden paths:
- api/**

Proof command:
pytest tests/test_build_protocol_cli.py -q

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )

    assert main(["plan", str(spec), "--output-base", str(output_base), "--run-id", "cli-smoke"]) == 0

    root = output_base / "cli-smoke"
    assert capsys.readouterr().out.strip() == str(root)
    assert (root / "build_packet.json").exists()
    assert (root / "work_packets" / "wp_001.json").exists()
    assert (root / "dispatch_plan.md").exists()


def test_seal_command_writes_review_and_proof_packets(tmp_path: Path, capsys) -> None:
    root = tmp_path / "dryrun"
    root.mkdir()

    assert main([
        "seal",
        str(root),
        "--build-packet-id",
        "build_1",
        "--work-packet-id",
        "wp_001",
        "--reviewer-agent",
        "reviewer",
        "--builder-agent",
        "builder",
        "--diff-ref",
        "diff.patch",
        "--test-output-ref",
        "test_output.txt",
        "--files",
        "1",
        "--added",
        "2",
        "--gate",
        "scoped_tests=pass",
    ]) == 0

    assert capsys.readouterr().out.strip() == str(root)
    review = json.loads((root / "review_packet.json").read_text(encoding="utf-8"))
    proof = json.loads((root / "proof_packet.json").read_text(encoding="utf-8"))
    assert review["status"] == "approved"
    assert proof["payload"]["merge_decision"] == "seal"
    assert validate_envelope(proof) == (True, [])


def test_shadow_apply_archives_sealed_packet_without_live_apply(
    tmp_path: Path,
    capsys,
) -> None:
    spec = tmp_path / "work.md"
    output_base = tmp_path / "dryruns"
    proof_command = f"{sys.executable} -c \"print('1 passed in 0.01s')\""
    spec.write_text(
        f"""# CLI Shadow Apply Smoke

Telos: Validate the sealed-packet apply mechanism and its parameter/architecture path while preserving the reviewer's first-person awareness as a witness/observer of the change and confirming system-level feedback, adaptation, and resilience across the Darwin archive network in shadow mode.

Allowed paths:
- tools/build_protocol/cli.py

Forbidden paths:
- api/**

Proof command:
{proof_command}

Reviewer:
codex-reviewer
""",
        encoding="utf-8",
    )

    assert main([
        "plan",
        str(spec),
        "--output-base",
        str(output_base),
        "--run-id",
        "shadow-smoke",
    ]) == 0
    root = output_base / "shadow-smoke"
    capsys.readouterr()

    assert main([
        "seal",
        str(root),
        "--build-packet-id",
        "cli-shadow-apply-smoke",
        "--work-packet-id",
        "wp_001",
        "--reviewer-agent",
        "reviewer",
        "--builder-agent",
        "builder",
        "--diff-ref",
        "missing.diff",
        "--test-output-ref",
        "test_output.txt",
        "--files",
        "1",
        "--added",
        "1",
        "--gate",
        "scoped_tests=pass",
    ]) == 0
    capsys.readouterr()

    assert main([
        "shadow-apply",
        str(root),
        "--workspace",
        str(tmp_path),
        "--proof-timeout",
        "5",
        "--archive-path",
        str(tmp_path / "archive.jsonl"),
        "--traces-path",
        str(tmp_path / "traces"),
        "--predictor-path",
        str(tmp_path / "predictor.jsonl"),
        "--halt-path",
        str(tmp_path / "missing-halt"),
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["applied"] is False
    assert payload["shadow"] is True
    assert payload["archive_entry_id"]


def test_opportunity_to_spec_command_writes_pilot_spec(tmp_path: Path, capsys) -> None:
    board = tmp_path / "opportunity_board.json"
    out_dir = tmp_path / "specs"
    board.write_text(
        json.dumps([
            {
                "opportunity_id": "opp_cli",
                "title": "Build CLI opportunity adapter",
                "domain": "internal_maintenance",
                "thesis": "feedback_closure",
                "evidence_signals": [
                    "scout:architecture - tools/build_protocol/cli.py:1",
                ],
            }
        ]),
        encoding="utf-8",
    )

    rc = main([
        "opportunity-to-spec",
        "--board",
        str(board),
        "--opportunity-id",
        "opp_cli",
        "--output-dir",
        str(out_dir),
    ])

    assert rc == 2
    path = Path(capsys.readouterr().out.strip())
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Telos: Build CLI opportunity adapter - feedback_closure" in text
    assert "- tools/build_protocol/cli.py" in text


def test_opportunity_to_spec_command_prints_source_input_context(tmp_path: Path, capsys) -> None:
    board = tmp_path / "opportunity_board.json"
    board.write_text(
        json.dumps([
            {
                "opportunity_id": "opp_cli_complete",
                "title": "Build complete adapter",
                "domain": "internal_maintenance",
                "thesis": "feedback_closure",
                "evidence_signals": [
                    "scout:architecture - tools/build_protocol/cli.py:1",
                ],
                "source_inputs": [
                    {
                        "source": "scout:architecture",
                        "evidence_ref": "tools/build_protocol/cli.py:1",
                        "title": "CLI adapter evidence",
                    }
                ],
            }
        ]),
        encoding="utf-8",
    )

    assert main([
        "opportunity-to-spec",
        "--board",
        str(board),
        "--opportunity-id",
        "opp_cli_complete",
        "--print",
    ]) == 0

    text = capsys.readouterr().out
    assert "## Source inputs" in text
    assert "scout:architecture: tools/build_protocol/cli.py:1" in text
