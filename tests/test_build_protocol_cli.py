from __future__ import annotations

import json
from pathlib import Path

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
