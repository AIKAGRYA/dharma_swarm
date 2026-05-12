from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from dharma_swarm.immune_mission_xray import (
    ImmuneMissionXRayInputs,
    run_immune_mission_xray,
)
from tools.build_protocol.cli import main as build_protocol_main


def _write_sample_repo(root: Path) -> None:
    package = root / "sample_app"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "core.py").write_text(
        "\n".join(
            [
                "def choose_action(items):",
                "    total = 0",
                "    for item in items:",
                "        if item > 0:",
                "            total += item",
                "        else:",
                "            total -= item",
                "    return total",
                "",
            ]
        ),
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        "from sample_app.core import choose_action\n\n"
        "def test_choose_action():\n"
        "    assert choose_action([1, -2]) == 3\n",
        encoding="utf-8",
    )


def test_immune_mission_xray_generates_redline_checked_proof_packet(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    output_dir = tmp_path / "reports" / "immune_mission_xray_2026-05-12_sample"

    result = run_immune_mission_xray(
        ImmuneMissionXRayInputs(
            target_root=tmp_path,
            title="Sample Agent Governance",
            summary="Diagnose whether this small agentic workflow has enough evidence, correction, and rollback discipline.",
            output_dir=output_dir,
            today=date(2026, 5, 12),
        )
    )

    assert result.redline_passed is True
    assert result.closure_decision in {"preflight_ready_with_open_wires", "closure_ready"}
    assert result.report_path.exists()
    assert result.contract_path.exists()
    assert result.generated_spec_path and result.generated_spec_path.exists()
    assert result.repo_xray_report_path and result.repo_xray_report_path.exists()
    assert result.sab_claim_candidate_path.exists()
    assert result.memory_authority_map_path.exists()
    assert result.witness_gap_map_path.exists()
    assert result.tool_permission_risk_map_path.exists()

    report = result.report_path.read_text(encoding="utf-8")
    assert "Unsupported Claim Register" in report
    assert "Evidence Tier Map" in report
    assert "Memory Authority Map" in report
    assert "Witness And Correction Gap Map" in report
    assert "Tool And Permission Risk Map" in report
    assert "Rollback And Intervention Map" in report

    redline = json.loads(result.redline_path.read_text(encoding="utf-8"))
    assert redline["passed"] is True
    assert redline["pass_count"] == 3

    contract = json.loads(result.contract_path.read_text(encoding="utf-8"))
    assert contract["internal_wedge"] == "Immune Mission X-Ray"
    assert contract["spine_bindings"]["build_spec"].endswith("next_build_spec.md")
    assert contract["spine_bindings"]["sabp_claim_path"].endswith("sab_claim_candidate.json")
    assert contract["witness_mandala"]["required"] is True
    assert set(contract["packet_rules"]["claim_tiers"]) == {
        "proven_in_code",
        "partial_runtime",
        "credible_design",
        "hypothesis",
        "vision",
        "blocked",
    }
    assert "dharma_swarm/insight_brief.py" in contract["evidence_surfaces"]["existing_dharma_surfaces"]
    assert contract["gates"]["darwin_shadow_apply"] == "not_run_by_xray_generator"

    candidate = json.loads(result.sab_claim_candidate_path.read_text(encoding="utf-8"))
    assert candidate["status"] == "candidate"
    assert candidate["externalization_ready"] is False
    assert len(candidate["witness_mandala"]["records"]) == 6
    assert not candidate["local_private_evidence_refs"]
    assert all("/Users/" not in ref for ref in candidate["artifact_refs"])


def test_immune_mission_xray_blocks_overclaim_before_closure(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    output_dir = tmp_path / "reports" / "immune_mission_xray_2026-05-12_blocked"

    result = run_immune_mission_xray(
        ImmuneMissionXRayInputs(
            target_root=tmp_path,
            title="Overclaimed Packet",
            summary="This system is production-ready and has customer traction.",
            output_dir=output_dir,
            today=date(2026, 5, 12),
            include_repo_xray=False,
        )
    )

    assert result.redline_passed is False
    assert result.closure_report_path is None
    assert result.generated_spec_path is None
    redline = json.loads(result.redline_path.read_text(encoding="utf-8"))
    assert any(v["redline"] == "production_ready_claim" for v in redline["violations"])


def test_build_protocol_cli_immune_mission_xray(tmp_path: Path, capsys) -> None:
    _write_sample_repo(tmp_path)
    output_dir = tmp_path / "reports" / "immune_mission_xray_cli"

    rc = build_protocol_main(
        [
            "immune-mission-xray",
            str(tmp_path),
            "--title",
            "CLI Sample Governance",
            "--summary",
            "Diagnose a bounded workflow for evidence, correction, and rollback discipline.",
            "--output-dir",
            str(output_dir),
            "--skip-repo-xray",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["redline_passed"] is True
    assert Path(payload["contract_path"]).exists()
    assert Path(payload["redline_path"]).exists()
    assert Path(payload["sab_claim_candidate_path"]).exists()


def test_build_protocol_cli_immune_xray_alias(tmp_path: Path, capsys) -> None:
    _write_sample_repo(tmp_path)
    output_dir = tmp_path / "reports" / "immune_xray_alias"

    rc = build_protocol_main(
        [
            "immune-xray",
            "--target-root",
            str(tmp_path),
            "--title",
            "Alias Governance",
            "--output-dir",
            str(output_dir),
            "--claim-id",
            "claim-alias-governance-v1",
            "--print-summary",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["redline_passed"] is True
    assert Path(payload["contract_path"]).exists()
    candidate = json.loads(Path(payload["sab_claim_candidate_path"]).read_text(encoding="utf-8"))
    assert candidate["claim_id"] == "claim-alias-governance-v1"
    assert candidate["boundary"] == "semi_public_sabp"
