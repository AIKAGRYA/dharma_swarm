"""Lane 2: $2,500 client audit engine — adversarial invariant suite."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "generate_client_report.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("generate_client_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def sample_spec(**overrides: Any) -> dict[str, Any]:
    r1 = {"receipt_id": "r-ok-1", "transition_id": "t-run", "status": "ok"}
    r_tamper_payload = {
        "receipt_id": "r-tamper",
        "transition_id": "t-tamper",
        "status": "ok",
    }
    spec: dict[str, Any] = {
        "schema": "dharma.client_audit_spec.v1",
        "engagement_id": "ENG-ACME-001",
        "client_name": "Acme Logistics",
        "target": {
            "name": "order-agent",
            "kind": "agent_spec",
            "identity": {
                "git_remote": "https://github.com/acme-logistics/order-agent.git",
                "vendor": "acme-logistics",
            },
        },
        "declared_graph": ["queued", "running", "completed"],
        "transitions": [
            {
                "id": "t-run",
                "from_state": "queued",
                "to_state": "running",
                "claimed_at": "2026-08-01T00:00:00Z",
                "claimed_status": "running",
                "receipt_id": "r-ok-1",
            },
            {
                "id": "t-ghost",
                "from_state": "running",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:01:00Z",
                "claimed_status": "completed",
                "receipt_id": None,
            },
            {
                "id": "t-skip",
                "from_state": "queued",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:02:00Z",
                "claimed_status": "success",
                "receipt_id": "missing-receipt",
            },
            {
                "id": "t-tamper",
                "from_state": "running",
                "to_state": "completed",
                "claimed_at": "2026-08-01T00:03:00Z",
                "claimed_status": "done",
                "receipt_id": "r-tamper",
            },
        ],
        "receipts": [
            {"receipt_id": "r-ok-1", "payload": r1, "sha256": _sha(r1)},
            {
                "receipt_id": "r-tamper",
                "payload": r_tamper_payload,
                "sha256": "0" * 64,
            },
        ],
    }
    spec.update(overrides)
    return spec


def test_module_is_stdlib_only() -> None:
    tree_source = SCRIPT.read_text(encoding="utf-8")
    forbidden = ("dharma_swarm", "reportlab", "weasyprint", "fpdf", "pytest")
    for needle in forbidden:
        assert needle not in tree_source.split("import")[0]
    assert "import dharma_swarm" not in tree_source
    assert "from dharma_swarm" not in tree_source


def test_evaluate_counts_unverified_and_hallucinated_completions() -> None:
    mod = load_mod()
    report = mod.evaluate_spec(sample_spec())
    assert report["summary"]["unverified_state_transition_count"] >= 2
    hallucinations = report["hallucinated_completions"]
    ids = {item["transition_id"] for item in hallucinations}
    assert "t-ghost" in ids
    ghost = next(item for item in hallucinations if item["transition_id"] == "t-ghost")
    assert ghost["claimed_status"] == "completed"
    assert "receipt" in ghost["failure_mode"].lower()


def test_each_invariant_carries_a_proof_digest() -> None:
    mod = load_mod()
    report = mod.evaluate_spec(sample_spec())
    assert report["invariants"]
    for item in report["invariants"]:
        digest = item["proof_digest"]
        assert digest.startswith("sha256:")
        hexpart = digest.split(":", 1)[1]
        assert len(hexpart) == 64
        assert all(ch in "0123456789abcdef" for ch in hexpart)
        recomputed = mod.proof_digest(item["invariant_id"], item["evidence"])
        assert recomputed == digest


def test_flat_price_is_decoupled_from_findings() -> None:
    mod = load_mod()
    dirty = mod.evaluate_spec(sample_spec())
    clean_spec = sample_spec()
    r1 = clean_spec["receipts"][0]
    clean_spec["transitions"] = [clean_spec["transitions"][0]]
    clean_spec["receipts"] = [r1]
    clean = mod.evaluate_spec(clean_spec)
    assert dirty["pricing"]["usd"] == 2500
    assert clean["pricing"]["usd"] == 2500
    assert dirty["pricing"]["flat"] is True
    assert "outcome" in dirty["pricing"]["decoupling"].lower()


def test_refuses_to_audit_systems_we_build() -> None:
    mod = load_mod()
    spec = sample_spec()
    spec["target"]["identity"]["git_remote"] = (
        "https://github.com/AIKAGRYA/dharma_swarm.git"
    )
    with pytest.raises(mod.IndependenceError):
        mod.evaluate_spec(spec)


def test_cli_writes_markdown_pdf_and_receipt(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(sample_spec()), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--spec",
            str(spec_path),
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    md = (out / "AUDIT_REPORT.md").read_text(encoding="utf-8")
    pdf = (out / "AUDIT_REPORT.pdf").read_bytes()
    receipt = json.loads((out / "audit_receipt.json").read_text(encoding="utf-8"))
    assert "unverified state transition" in md.lower()
    assert "hallucin" in md.lower()
    assert "sha256:" in md
    assert pdf.startswith(b"%PDF-")
    assert b"2500" in pdf
    assert receipt["schema"] == "dharma.client_audit_receipt.v1"
    assert receipt["summary"]["unverified_state_transition_count"] >= 2
    assert receipt["pricing"]["usd"] == 2500


def test_cli_self_audit_exits_independence(tmp_path: Path) -> None:
    spec = sample_spec()
    spec["target"]["identity"]["git_remote"] = "git@github.com:AIKAGRYA/dharma_swarm.git"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--spec",
            str(spec_path),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "independence" in (result.stderr + result.stdout).lower()
    assert not (tmp_path / "out" / "AUDIT_REPORT.md").exists()


def test_sample_flag_runs_foreign_fixture(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sample",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    md = (tmp_path / "AUDIT_REPORT.md").read_text(encoding="utf-8")
    assert "Acme" in md
    assert "dharma_swarm" not in md.lower() or "never audit" in md.lower()
