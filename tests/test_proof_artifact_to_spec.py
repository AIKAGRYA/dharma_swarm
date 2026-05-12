from __future__ import annotations

import json
from pathlib import Path

from tools.build_protocol.cli import main as build_cli_main
from tools.build_protocol.pilot00_dryrun_generator import parse_spec
from tools.build_protocol.proof_artifact_to_spec import (
    load_contract,
    render_spec,
    run_closure_preflight,
)


def test_closure_preflight_keeps_all_major_organs(tmp_path: Path) -> None:
    contract_path = _write_packet(tmp_path)
    selection = load_contract(contract_path, repo_root=tmp_path)

    report = run_closure_preflight(
        selection,
        report_path=contract_path.parent / "closure_run_report.json",
    )

    assert report["decision"]["status"] == "preflight_ready_with_open_wires"
    assert "ThinkodynamicDirector" in report["core_organs"]
    assert "Evolution" in report["core_organs"]
    assert "Kalyan" in report["core_organs"]
    assert any(
        check["name"] == "spine_bindings.opportunity_id"
        and check["status"] == "pending"
        for check in report["checks"]
    )


def test_render_spec_is_pilot_00_compatible(tmp_path: Path) -> None:
    contract_path = _write_packet(tmp_path)
    selection = load_contract(contract_path, repo_root=tmp_path)
    report = run_closure_preflight(
        selection,
        report_path=contract_path.parent / "closure_run_report.json",
    )
    spec_text = render_spec(selection, report)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(spec_text, encoding="utf-8")

    spec = parse_spec(spec_path)

    assert "whole-organism tracer" in spec.telos
    assert "ThinkodynamicDirector" in spec_text
    assert "guarded Evolution" in spec_text
    assert "TODO" not in spec_text
    assert str(contract_path.relative_to(tmp_path)) in spec.allowed_paths


def test_cli_writes_closure_report_and_spec(
    tmp_path: Path,
    capsys,
) -> None:
    contract_path = _write_packet(tmp_path)
    output_dir = tmp_path / "specs"
    report_path = contract_path.parent / "closure_run_report.json"

    rc = build_cli_main([
        "proof-artifact-to-spec",
        str(contract_path),
        "--repo-root",
        str(tmp_path),
        "--output-dir",
        str(output_dir),
        "--report-path",
        str(report_path),
    ])

    assert rc == 0
    spec_path = Path(capsys.readouterr().out.strip())
    assert spec_path.exists()
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["artifact_id"] == "proof_artifact_test"
    assert report["decision"]["status"] == "preflight_ready_with_open_wires"


def test_cli_blocks_missing_minimum_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    contract_path = _write_packet(tmp_path, write_dossier=False)

    rc = build_cli_main([
        "proof-artifact-to-spec",
        str(contract_path),
        "--repo-root",
        str(tmp_path),
        "--print-report",
    ])

    assert rc == 2
    report = json.loads(capsys.readouterr().out)
    assert report["decision"]["status"] == "blocked"
    assert any(
        check["name"] == "minimum_viable_artifact.path"
        and check["status"] == "fail"
        for check in report["checks"]
    )


def test_closure_preflight_checks_required_witness_mandala(tmp_path: Path) -> None:
    contract_path = _write_packet(tmp_path)
    claim_path = tmp_path / "agora_claim.json"
    claim_path.write_text(
        json.dumps({
            "claim_id": "claim-test",
            "witness_mandala": {
                "version": "1.0",
                "records": _mandala_records(),
            },
        }),
        encoding="utf-8",
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["witness_mandala"] = {
        "required": True,
        "claim_path": str(claim_path),
    }
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    selection = load_contract(contract_path, repo_root=tmp_path)
    report = run_closure_preflight(
        selection,
        report_path=contract_path.parent / "closure_run_report.json",
    )

    assert any(
        check["name"] == "witness_mandala"
        and check["status"] == "pass"
        for check in report["checks"]
    )


def _mandala_records() -> list[dict]:
    roles = (
        "formal",
        "engineering",
        "adversarial",
        "economic",
        "ecological_social",
        "human_telos",
    )
    return [
        {
            "role": role,
            "stance": "challenge" if role == "adversarial" else "verify",
            "strongest_affirmation": f"{role} affirmation",
            "strongest_objection": f"{role} objection",
            "what_would_make_this_false": f"{role} falsifier",
            "evidence_required_to_upgrade": [f"{role} evidence"],
            "protected_value": f"{role} protected value",
            "next_test": f"{role} next test",
            "confidence": 0.72,
        }
        for role in roles
    ]


def _write_packet(tmp_path: Path, *, write_dossier: bool = True) -> Path:
    packet = tmp_path / "reports" / "agentic_immune_system_packet_20260511"
    docs = tmp_path / "docs" / "plans"
    packet.mkdir(parents=True)
    docs.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (tmp_path / "dharma_swarm").mkdir()

    source_synthesis = docs / "2026-05-11-global-proof-engine-scratchmap.md"
    source_synthesis.write_text(
        "ThinkodynamicDirector should preserve lodestones, telos, evolution, and value feedback.",
        encoding="utf-8",
    )
    if write_dossier:
        (packet / "agentic_era_immune_system_dossier.md").write_text(
            """# Agentic Era Immune System

This artifact treats agentic governance as a systems, mechanistic, and
phenomenological problem. Evidence, source limitations, assumptions, and
uncertainty are stated so the claim can be challenged.

## Limitations

This is a bounded internal proof packet and does not claim autonomous live
self-modification or public submission readiness.

## Uncertainty

The runtime wires are partial and should be tested through a shadow path.
""",
            encoding="utf-8",
        )
    (packet / "claims_register.md").write_text(
        "# Claims\n\n- Proven in code: Darwin shadow ingestion exists.\n",
        encoding="utf-8",
    )
    (packet / "human_operator_brief.md").write_text(
        "# Human Operator Brief\n\nBoundary decisions remain open.\n",
        encoding="utf-8",
    )
    (packet / "organ_wiring_matrix.md").write_text(
        "# Organ Wiring Matrix\n\nMissing wire: tools/build_protocol/proof_artifact_to_spec.py\n",
        encoding="utf-8",
    )
    (packet / "next_build_spec.md").write_text(
        "# Next Build Spec\n\nBuild tools/build_protocol/proof_artifact_to_spec.py\n",
        encoding="utf-8",
    )
    contract = {
        "artifact_id": "proof_artifact_test",
        "contract_version": "0.1.0",
        "status": "draft_scaffold",
        "title": "Agentic Era Immune System",
        "internal_wedge": "Immune Mission X-Ray",
        "parent_venture_cell": {
            "proposed_name": "Agentic Immune X-Ray",
            "status": "not_yet_registered_as_runtime_cell",
        },
        "telos": {
            "absolute_telos": "truthful witnessed self-correcting agentic systems",
            "commercial_telos": "make agentic work trustworthy",
            "anti_collapse_rule": "do not reduce this to a dashboard or manifesto",
        },
        "minimum_viable_artifact": {
            "type": "dossier",
            "path": "reports/agentic_immune_system_packet_20260511/agentic_era_immune_system_dossier.md",
        },
        "spine_bindings": {
            "source_synthesis": "docs/plans/2026-05-11-global-proof-engine-scratchmap.md",
            "claim_register": "reports/agentic_immune_system_packet_20260511/claims_register.md",
            "human_operator_brief": "reports/agentic_immune_system_packet_20260511/human_operator_brief.md",
            "organ_wiring_matrix": "reports/agentic_immune_system_packet_20260511/organ_wiring_matrix.md",
            "build_spec": "reports/agentic_immune_system_packet_20260511/next_build_spec.md",
            "sABP_submission": "pending",
            "witness_link_id": "pending",
            "outcome_id": "pending",
            "value_event_id": "pending",
            "contribution_ids": [],
            "opportunity_id": "pending",
        },
        "evidence_surfaces": {
            "dharma_swarm": [
                "reports/agentic_immune_system_packet_20260511/claims_register.md",
                "reports/agentic_immune_system_packet_20260511/organ_wiring_matrix.md",
            ],
            "external": ["NIST AI Agent Standards Initiative"],
        },
        "human_decisions_required": [
            {
                "id": "public_boundary",
                "decision": "Choose publication boundary.",
                "default": "semi-public Agora basin",
            }
        ],
        "next_state": "draft_dossier_to_reviewable_proof_packet",
    }
    contract_path = packet / "proof_artifact_contract.json"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return contract_path
