"""End-to-end tests for the revenue-wedge audit kit against the committed fixture repo.

The kit is exercised exactly as a client would run it: as a subprocess with a
target repo path. No dharma_swarm imports are required by the kit itself.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KIT = REPO_ROOT / "scripts" / "revenue_wedge" / "audit_kit.py"
# The synthetic target repo's Python sources are committed as `*.py.txt` so the
# parent repository's own CI (import-provenance ratchet, pytest collection)
# never scans this fixture's planted slop. The kit must see real `.py` files, so
# each test materializes the template tree into a tmp dir first.
FIXTURE_TEMPLATE = Path(__file__).resolve().parent / "fixtures" / "revenue_wedge_target_repo"


def materialize_fixture(dest: Path) -> Path:
    """Copy the fixture template tree into ``dest``, renaming ``*.py.txt`` -> ``*.py``."""
    for src in FIXTURE_TEMPLATE.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(FIXTURE_TEMPLATE)
        if src.name.endswith(".py.txt"):
            rel = rel.with_name(src.name[: -len(".txt")])
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())
    return dest

EXPECTED_DETECTORS = {
    "hardcoded_secret_like",
    "missing_annotations_public_api",
    "duplicate_functions",
    "test_gap_modules",
    "dead_code_markers",
    "oversized_module",
}


def run_kit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(KIT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def scan_fixture(output_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    target = materialize_fixture(output_dir / "_target")
    return run_kit(
        "scan",
        "--target-repo",
        str(target),
        "--output-dir",
        str(output_dir),
        "--max-module-lines",
        "40",
        *extra,
    )


def test_scan_fixture_produces_receipt_and_ranked_report(tmp_path: Path) -> None:
    result = scan_fixture(tmp_path)
    assert result.returncode == 0, result.stderr

    receipt_path = tmp_path / "audit_receipt.json"
    report_path = tmp_path / "slop_report.md"
    assert receipt_path.is_file()
    assert report_path.is_file()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "revenue_wedge_audit_kit_receipt.v1"
    assert receipt["python_files_scanned"] == 3

    detectors = {finding["detector"] for finding in receipt["findings"]}
    assert EXPECTED_DETECTORS <= detectors

    secret_findings = [f for f in receipt["findings"] if f["detector"] == "hardcoded_secret_like"]
    assert any(f["path"] == "src/app.py" for f in secret_findings)

    gap_paths = {f["path"] for f in receipt["findings"] if f["detector"] == "test_gap_modules"}
    assert "src/app.py" in gap_paths
    assert "src/helpers.py" not in gap_paths  # covered by tests/checks_helpers.py

    # findings are ranked: first finding carries the highest severity weight
    assert receipt["findings"][0]["severity"] == "critical"
    assert receipt["summary"]["finding_count"] == len(receipt["findings"])
    assert receipt["summary"]["slop_score_per_kloc"] > 0

    # fixture is not a git repo: provenance must degrade gracefully
    assert receipt["provenance"]["available"] is False
    assert "not a git repository" in receipt["provenance"]["reason"]

    report = report_path.read_text(encoding="utf-8")
    assert "Ranked Slop & Provenance Report" in report
    assert "1. **CRITICAL** hardcoded_secret_like" in report
    # run inside the dharma repo, the hygiene registry cross-reference resolves
    assert "[hygiene:VC-E2]" in report


def test_render_is_pure_function_of_receipt(tmp_path: Path) -> None:
    result = scan_fixture(tmp_path)
    assert result.returncode == 0, result.stderr

    rerendered = tmp_path / "rerendered.md"
    render = run_kit(
        "render",
        "--receipt",
        str(tmp_path / "audit_receipt.json"),
        "--output",
        str(rerendered),
    )
    assert render.returncode == 0, render.stderr
    original = (tmp_path / "slop_report.md").read_text(encoding="utf-8")
    assert rerendered.read_text(encoding="utf-8") == original


def test_fail_threshold_gate_exits_nonzero(tmp_path: Path) -> None:
    result = scan_fixture(tmp_path, "--fail-threshold", "0.01")
    assert result.returncode == 2
    assert "exceeds threshold" in result.stdout


def test_git_provenance_counts_ai_attributed_commits(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        import pytest

        pytest.skip("git binary unavailable")

    repo = tmp_path / "client_repo"
    materialize_fixture(repo)

    def git(*args: str) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Fixture Human",
                "-c",
                "user.email=human@example.com",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    git("init", "--quiet")
    git("add", "-A")
    git("commit", "--quiet", "-m", "initial import")
    (repo / "src" / "app.py").write_text(
        (repo / "src" / "app.py").read_text(encoding="utf-8") + "\n# touched\n",
        encoding="utf-8",
    )
    git("add", "-A")
    git(
        "commit",
        "--quiet",
        "-m",
        "tweak app\n\nCo-Authored-By: Oz <oz-agent@warp.dev>",
    )

    out = tmp_path / "out"
    result = run_kit("scan", "--target-repo", str(repo), "--output-dir", str(out))
    assert result.returncode == 0, result.stderr
    receipt = json.loads((out / "audit_receipt.json").read_text(encoding="utf-8"))
    prov = receipt["provenance"]
    assert prov["available"] is True
    assert prov["total_commits"] == 2
    assert prov["ai_attributed_commits"] == 1
    assert prov["ai_commit_fraction"] == 0.5
    assert any(e["path"] == "src/app.py" for e in prov["top_ai_touched_files"])
