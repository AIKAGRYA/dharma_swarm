from __future__ import annotations

import json
from pathlib import Path

from scripts.check_claim_redlines import (
    CandidateClaim,
    main,
    run_redline_preflight,
)


def _safe_candidate(tmp_path: Path) -> CandidateClaim:
    artifact = tmp_path / "dossier.md"
    artifact.write_text(
        "This bounded proof artifact records uncertainty and makes no claim of "
        "production readiness, customer traction, consciousness, or autonomous "
        "live self-modification.",
        encoding="utf-8",
    )
    return CandidateClaim(
        title="Agentic Immune X-Ray: internally gated proof artifact",
        summary=(
            "Dharma Swarm produced a bounded internal proof artifact and routed it "
            "through existing credibility, Semantic Anekanta, Bhed Gnan, "
            "TelosGatekeeper, Outcome, ValueEvent, and Contribution surfaces. "
            "The packet is a semi-public venture-proposal witness, with no claim "
            "of production readiness, customer traction, consciousness, or "
            "autonomous live self-modification."
        ),
        stage="venture_proposal",
        boundary="semi_public_agora",
        artifact_refs=("dharma_swarm/reports/agentic_immune_system_packet_20260511/dossier.md",),
        scan_paths=(artifact,),
    )


def test_redline_preflight_passes_safe_semi_public_claim(tmp_path: Path) -> None:
    report = run_redline_preflight(_safe_candidate(tmp_path), pass_count=3)

    assert report["passed"] is True
    assert report["pass_count"] == 3
    assert [p["name"] for p in report["passes"]] == [
        "literal_sensitive_pattern_scan",
        "boundary_and_reference_policy_scan",
        "telos_gate_redline_scan",
    ]


def test_redline_preflight_blocks_secret_in_scanned_artifact(tmp_path: Path) -> None:
    candidate = _safe_candidate(tmp_path)
    secret = tmp_path / "secret.md"
    secret.write_text("api_key = 'sk-proj-1234567890abcdefghijklmnop'", encoding="utf-8")
    candidate = CandidateClaim(
        title=candidate.title,
        summary=candidate.summary,
        stage=candidate.stage,
        boundary=candidate.boundary,
        artifact_refs=candidate.artifact_refs,
        scan_paths=(secret,),
    )

    report = run_redline_preflight(candidate, pass_count=3)

    assert report["passed"] is False
    assert any(v["redline"] == "secret_or_api_key" for v in report["violations"])


def test_redline_preflight_blocks_local_home_artifact_ref(tmp_path: Path) -> None:
    candidate = _safe_candidate(tmp_path)
    candidate = CandidateClaim(
        title=candidate.title,
        summary=candidate.summary,
        stage=candidate.stage,
        boundary=candidate.boundary,
        artifact_refs=("/Users/dhyana/private/transcript.md",),
        scan_paths=candidate.scan_paths,
    )

    report = run_redline_preflight(candidate, pass_count=3)

    assert report["passed"] is False
    assert any(v["redline"] == "local_private_path_in_artifact_ref" for v in report["violations"])


def test_redline_preflight_blocks_unsupported_overclaims(tmp_path: Path) -> None:
    candidate = _safe_candidate(tmp_path)
    candidate = CandidateClaim(
        title=candidate.title,
        summary="Dharma Swarm is conscious and production-ready for paying customers.",
        stage=candidate.stage,
        boundary=candidate.boundary,
        artifact_refs=candidate.artifact_refs,
        scan_paths=candidate.scan_paths,
    )

    report = run_redline_preflight(candidate, pass_count=3)

    assert report["passed"] is False
    redlines = {v["redline"] for v in report["violations"]}
    assert "unsupported_consciousness_claim" in redlines
    assert "production_ready_claim" in redlines
    assert "customer_or_revenue_traction_claim" in redlines


def test_redline_cli_writes_report_and_fails_on_violation(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "redlines.json"

    code = main([
        "--title",
        "Unsafe",
        "--summary",
        "This solves all agent governance.",
        "--artifact-ref",
        "dharma_swarm/reports/safe.md",
        "--output",
        str(output),
        "--fail-on-violation",
    ])

    assert code == 1
    assert output.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert any(v["redline"] == "solved_agent_governance_claim" for v in payload["violations"])
