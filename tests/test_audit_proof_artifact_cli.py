from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_proof_artifact import main


def test_audit_proof_artifact_cli_writes_existing_audit_shape(
    tmp_path: Path,
    capsys,
) -> None:
    proof = tmp_path / "proof.md"
    proof.write_text(
        "\n".join([
            "W = 588.5 wt-CO2e/yr",
            "Source: https://example.org/report doi:10.1234/test",
            "## Assumptions and Limitations",
            "Uncertainty bounds: +/-15% sensitivity analysis.",
        ]),
        encoding="utf-8",
    )

    code = main([str(proof), "--output-dir", str(tmp_path / "audits")])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    audit_path = Path(payload["audit_path"])
    assert audit_path.exists()
    assert payload["summary"]["submission_ready"] is True
    assert payload["results"][0]["gate"] == "no_private_evidence"


def test_audit_proof_artifact_cli_can_fail_when_not_ready(
    tmp_path: Path,
    capsys,
) -> None:
    proof = tmp_path / "proof.md"
    proof.write_text(
        "\n".join([
            "SUBMISSION READY",
            "Source: payroll audit",
            "This is UNVERIFIED.",
        ]),
        encoding="utf-8",
    )

    code = main([
        str(proof),
        "--output-dir",
        str(tmp_path / "audits"),
        "--fail-on-not-ready",
    ])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["submission_ready"] is False
    assert any(row["verdict"] == "fail" for row in payload["results"])
