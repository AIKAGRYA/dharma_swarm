"""Tests for scripts/governance/loop/prompt_audit_triage.py — Stage 2 (deterministic).

Covers VAL-TRIAGE-001..007:
  001  E2+ findings routed to IMPLEMENT
  002  below-E2 findings routed to DEFER
  003  dedup by failure_class (one accepted, recurrence noted)
  004  failure_class seen in >=2 prior runs auto-escalates to must_gate=true
  005  accepted_findings.jsonl produced (one JSON per finding, routing + recurrence_score)
  006  NEEDS_HUMAN routing for ambiguous findings (distinct from IMPLEMENT/DEFER)
  007  all-findings-deferred run completes cleanly, no fix_proposal artifacts
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = sys.executable
TRIAGE_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_triage.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_warrant_dict(run_id: str = "warrant-triage-test") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "origin/main",
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/prompt_audit_triage.py"],
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _make_finding(
    fid: str = "F-001",
    title: str = "test finding",
    severity: str = "medium",
    evidence_level: str = "E2_tested",
    failure_class: str = "SLOP_MARKER_DRIFT",
    confidence: str = "medium",
    files: list[str] | None = None,
) -> dict:
    return {
        "id": fid,
        "title": title,
        "severity": severity,
        "evidence_level": evidence_level,
        "confidence": confidence,
        "files": files or ["src/foo.py"],
        "line_refs": ["src/foo.py:42"],
        "observed": "marker missing",
        "inferred": "slop reintroduced",
        "risk": "gate bypass",
        "failure_class": failure_class,
        "recommendation": "add gate",
        "verification": "run gate",
    }


def _make_audit_doc(
    prompt_id: str = "TV-01",
    council_id: str = "testing_verification",
    findings: list[dict] | None = None,
    run_id: str | None = None,
) -> dict:
    doc = {
        "prompt_id": prompt_id,
        "council_id": council_id,
        "repo_path": "/tmp/ds_loop",
        "git_ref": "ratchet/loop-phases-1-3",
        "scope": {
            "files_examined": ["src/foo.py"],
            "commands_run": [{"command": "echo hi", "cwd": "/tmp", "exit_code": 0}],
            "commands_not_run": [{"command": "echo bye", "reason": "n/a"}],
        },
        "summary": {"verdict": "fail", "confidence": "high"},
        "findings": findings if findings is not None else [_make_finding()],
        "not_proven": [],
    }
    if run_id is not None:
        doc["run_id"] = run_id
    return doc


def _setup_run(
    tmp_path: Path,
    run_id: str = "triage-test-001",
    audits: dict[str, dict] | None = None,
    warrant: dict | None = None,
) -> tuple[Path, str, Path]:
    """Create a run dir with audit JSON files. Returns (warrant_path, run_id, run_dir)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    warrant_path = _write_warrant(tmp_path, warrant)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id,
         "--warrant", str(warrant_path)],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"
    run_dir = Path(proc.stdout.strip())

    # Write audit JSON files.
    if audits:
        audit_dir = run_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        for pid, doc in audits.items():
            (audit_dir / f"{pid}.json").write_text(
                json.dumps(doc, indent=2, sort_keys=True) + "\n"
            )
    return warrant_path, run_id, run_dir


def _run_triage_cli(
    warrant: Path, run_id: str, runs_root: Path
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    return subprocess.run(
        [VENV_PYTHON, str(TRIAGE_CLI), "--warrant", str(warrant), "--run-id", run_id],
        capture_output=True, text=True, env=env,
    )


def _write_prior_ledger(run_dir: Path, finding_class: str, finding_id: str = "F-prior") -> None:
    """Write a ledger entry for a prior run (simulates recurrence source)."""
    ledger_dir = run_dir / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "ledger_entry": {
            "timestamp_utc": "2026-06-20T00:00:00Z",
            "commit": "abc123",
            "finding_class": finding_class,
            "status": "gated",
            "gate_ref": "ci/gate",
            "receipt_ref": ["receipts/r.txt"],
            "proof_mode": "natural",
            "prevents_recurrence": True,
            "human_approver": None,
        }
    }
    (ledger_dir / f"ledger_entry_{finding_id}.yaml").write_text(
        yaml.safe_dump(entry, sort_keys=False)
    )


# ---------------------------------------------------------------------------
# VAL-TRIAGE-001: E2+ findings routed to IMPLEMENT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ev", ["E2_tested", "E3_cross_checked", "E4_regression_proven"])
def test_e2plus_findings_routed_to_implement(tmp_path, ev):
    """VAL-TRIAGE-001: findings with evidence_level E2 or higher route to IMPLEMENT."""
    finding = _make_finding(evidence_level=ev, failure_class=f"CLASS_{ev}")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    findings_path = run_dir / "accepted_findings.jsonl"
    assert findings_path.exists(), "accepted_findings.jsonl must be produced"
    records = [json.loads(line) for line in findings_path.read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["routing"] == "IMPLEMENT", f"E2+ finding must route to IMPLEMENT, got {records[0]['routing']}"


def test_triage_rejects_audit_artifact_from_different_run_id(tmp_path):
    finding = _make_finding(evidence_level="E2_tested", failure_class="RUN_ID_MISMATCH")
    audit = _make_audit_doc(findings=[finding], run_id="other-run")
    warrant, run_id, run_dir = _setup_run(tmp_path, run_id="triage-current", audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert "run_id" in out and "other-run" in out
    assert not (run_dir / "accepted_findings.jsonl").exists()


# ---------------------------------------------------------------------------
# VAL-TRIAGE-002: below-E2 findings routed to DEFER
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ev", ["E0_none", "E1_static"])
def test_below_e2_findings_routed_to_defer(tmp_path, ev):
    """VAL-TRIAGE-002: findings with evidence_level below E2 route to DEFER, not IMPLEMENT."""
    finding = _make_finding(evidence_level=ev, failure_class=f"CLASS_{ev}")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["routing"] == "DEFER", f"below-E2 finding must route to DEFER, got {records[0]['routing']}"


# ---------------------------------------------------------------------------
# VAL-TRIAGE-003: dedup by failure_class
# ---------------------------------------------------------------------------


def test_dedup_by_failure_class(tmp_path):
    """VAL-TRIAGE-003: two findings with the same failure_class are deduped (one accepted, recurrence noted)."""
    f1 = _make_finding(fid="F-001", evidence_level="E2_tested", failure_class="DUP_CLASS", severity="high")
    f2 = _make_finding(fid="F-002", evidence_level="E3_cross_checked", failure_class="DUP_CLASS", severity="medium")
    audit = _make_audit_doc(findings=[f1, f2])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    # Only one accepted finding for DUP_CLASS.
    dup_records = [r for r in records if r["failure_class"] == "DUP_CLASS"]
    assert len(dup_records) == 1, f"expected 1 deduped finding, got {len(dup_records)}"
    # Recurrence within the run is noted.
    assert dup_records[0].get("recurrence_within_run") is True, "recurrence_within_run must be True for deduped findings"


def test_dedup_keeps_higher_evidence(tmp_path):
    """Dedup keeps the finding with the highest evidence_level."""
    f_low = _make_finding(fid="F-low", evidence_level="E1_static", failure_class="DUP2", severity="critical")
    f_high = _make_finding(fid="F-high", evidence_level="E3_cross_checked", failure_class="DUP2", severity="low")
    audit = _make_audit_doc(findings=[f_low, f_high])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    dup = [r for r in records if r["failure_class"] == "DUP2"]
    assert len(dup) == 1
    # The higher-evidence finding (E3) is kept, and routes to IMPLEMENT.
    assert dup[0]["evidence_level"] == "E3_cross_checked"
    assert dup[0]["routing"] == "IMPLEMENT"


def test_different_failure_classes_not_deduped(tmp_path):
    """Findings with different failure_classes are NOT deduped."""
    f1 = _make_finding(fid="F-001", failure_class="CLASS_A", evidence_level="E2_tested")
    f2 = _make_finding(fid="F-002", failure_class="CLASS_B", evidence_level="E2_tested")
    audit = _make_audit_doc(findings=[f1, f2])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    classes = {r["failure_class"] for r in records}
    assert classes == {"CLASS_A", "CLASS_B"}, f"both classes must appear, got {classes}"


# ---------------------------------------------------------------------------
# VAL-TRIAGE-004: recurrence >=2 prior runs auto-escalates to must_gate=true
# ---------------------------------------------------------------------------


def test_recurrence_auto_escalates_must_gate(tmp_path):
    """VAL-TRIAGE-004: a failure_class seen in >=2 prior runs gets must_gate=true."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        # Create two prior runs with ledger entries for RECUR_CLASS.
        for i, rid in enumerate(["prior-run-a", "prior-run-b"]):
            prior_warrant = _write_warrant(tmp_path, _make_warrant_dict(f"warrant-{rid}"))
            proc = subprocess.run(
                [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", rid,
                 "--warrant", str(prior_warrant)],
                capture_output=True, text=True,
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            )
            assert proc.returncode == 0
            prior_dir = Path(proc.stdout.strip())
            _write_prior_ledger(prior_dir, "RECUR_CLASS", finding_id=f"F-prior-{i}")

        # Current run with a finding of the same failure_class.
        finding = _make_finding(failure_class="RECUR_CLASS", evidence_level="E2_tested")
        audit = _make_audit_doc(findings=[finding])
        warrant, run_id, run_dir = _setup_run(
            tmp_path, run_id="current-run", audits={"TV-01": audit}
        )

        proc = _run_triage_cli(warrant, run_id, runs_root)
        assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

        records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
        recur = [r for r in records if r["failure_class"] == "RECUR_CLASS"]
        assert len(recur) == 1
        assert recur[0]["must_gate"] is True, "must_gate must be True for a failure_class seen in >=2 prior runs"
        assert recur[0]["recurrence_score"] >= 2, f"recurrence_score must be >=2, got {recur[0]['recurrence_score']}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_no_recurrence_no_must_gate(tmp_path):
    """A failure_class NOT seen in prior runs does not get must_gate=true."""
    finding = _make_finding(failure_class="NOVEL_CLASS", evidence_level="E2_tested")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["must_gate"] is False
    assert records[0]["recurrence_score"] == 0


def test_single_recurrence_no_must_gate(tmp_path):
    """A failure_class seen in only 1 prior run does NOT get must_gate=true (threshold is >=2)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        # One prior run.
        prior_warrant = _write_warrant(tmp_path, _make_warrant_dict("warrant-prior1"))
        proc = subprocess.run(
            [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", "prior-single",
             "--warrant", str(prior_warrant)],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        assert proc.returncode == 0
        _write_prior_ledger(Path(proc.stdout.strip()), "SINGLE_RECUR", finding_id="F-s1")

        finding = _make_finding(failure_class="SINGLE_RECUR", evidence_level="E2_tested")
        audit = _make_audit_doc(findings=[finding])
        warrant, run_id, run_dir = _setup_run(
            tmp_path, run_id="current-single", audits={"TV-01": audit}
        )

        proc = _run_triage_cli(warrant, run_id, runs_root)
        assert proc.returncode == 0

        records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
        assert len(records) == 1
        assert records[0]["must_gate"] is False, "1 prior run is below the >=2 threshold"
        assert records[0]["recurrence_score"] == 1
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-TRIAGE-005: accepted_findings.jsonl produced with routing + recurrence_score
# ---------------------------------------------------------------------------


def test_accepted_findings_jsonl_format(tmp_path):
    """VAL-TRIAGE-005: accepted_findings.jsonl has one JSON line per finding with routing + recurrence_score."""
    f1 = _make_finding(fid="F-001", failure_class="CLASS_X", evidence_level="E2_tested")
    f2 = _make_finding(fid="F-002", failure_class="CLASS_Y", evidence_level="E1_static")
    audit = _make_audit_doc(findings=[f1, f2])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    path = run_dir / "accepted_findings.jsonl"
    assert path.exists(), "accepted_findings.jsonl must exist"
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    assert len(lines) == 2, f"expected 2 JSON lines, got {len(lines)}"
    for line in lines:
        rec = json.loads(line)
        assert "routing" in rec, "each record must have a routing field"
        assert "recurrence_score" in rec, "each record must have a recurrence_score field"
        assert rec["routing"] in ("IMPLEMENT", "DEFER", "NEEDS_HUMAN")


def test_multiple_audits_aggregated(tmp_path):
    """Triage reads all audit JSON from the run dir and aggregates findings."""
    audit_a = _make_audit_doc(prompt_id="TV-01", findings=[_make_finding(fid="F-a", failure_class="CLASS_A", evidence_level="E2_tested")])
    audit_b = _make_audit_doc(prompt_id="TV-08", findings=[_make_finding(fid="F-b", failure_class="CLASS_B", evidence_level="E3_cross_checked")])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit_a, "TV-08": audit_b})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    classes = {r["failure_class"] for r in records}
    assert classes == {"CLASS_A", "CLASS_B"}


# ---------------------------------------------------------------------------
# VAL-TRIAGE-006: NEEDS_HUMAN routing for ambiguous findings
# ---------------------------------------------------------------------------


def test_needs_human_for_missing_failure_class(tmp_path):
    """VAL-TRIAGE-006: a finding with an empty/missing failure_class routes to NEEDS_HUMAN."""
    finding = _make_finding(evidence_level="E2_tested", failure_class="")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["routing"] == "NEEDS_HUMAN", f"ambiguous finding must route to NEEDS_HUMAN, got {records[0]['routing']}"


def test_needs_human_distinct_from_implement_and_defer(tmp_path):
    """A NEEDS_HUMAN finding does not proceed to IMPLEMENT."""
    finding = _make_finding(evidence_level="E4_regression_proven", failure_class="", severity="critical")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    assert records[0]["routing"] == "NEEDS_HUMAN"
    assert records[0]["routing"] != "IMPLEMENT"
    assert records[0]["routing"] != "DEFER"


def test_needs_human_low_confidence_high_severity(tmp_path):
    """A high/critical severity finding with low confidence is ambiguous -> NEEDS_HUMAN."""
    finding = _make_finding(
        evidence_level="E2_tested", failure_class="CONTRADICTORY",
        severity="critical", confidence="low",
    )
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    records = [json.loads(line) for line in (run_dir / "accepted_findings.jsonl").read_text().splitlines() if line.strip()]
    assert records[0]["routing"] == "NEEDS_HUMAN", "critical+low-confidence must be NEEDS_HUMAN"


# ---------------------------------------------------------------------------
# VAL-TRIAGE-007: all-findings-deferred run completes cleanly, no fix_proposal
# ---------------------------------------------------------------------------


def test_all_deferred_completes_cleanly(tmp_path):
    """VAL-TRIAGE-007: when all findings defer, the run completes cleanly (exit 0)."""
    finding = _make_finding(evidence_level="E1_static", failure_class="DEFER_ONLY")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0, f"all-deferred run must exit 0: {proc.stdout!r} {proc.stderr!r}"


def test_all_deferred_no_fix_proposal_artifacts(tmp_path):
    """VAL-TRIAGE-007: when all findings defer, no fix_proposal_* artifacts are produced."""
    finding = _make_finding(evidence_level="E0_none", failure_class="DEFER_ONLY_2")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    fixes_dir = run_dir / "fixes"
    fix_artifacts = list(fixes_dir.glob("fix_proposal_*")) if fixes_dir.is_dir() else []
    assert fix_artifacts == [], f"no fix_proposal artifacts expected for all-deferred run, found: {fix_artifacts}"


def test_all_deferred_message(tmp_path):
    """The triage output indicates no IMPLEMENT findings when all defer."""
    finding = _make_finding(evidence_level="E1_static", failure_class="DEFER_MSG")
    audit = _make_audit_doc(findings=[finding])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "no implement" in combined or "all deferred" in combined or "defer" in combined, (
        f"output should indicate no IMPLEMENT findings: {proc.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Edge cases: zero findings, warrant re-validation, no audits
# ---------------------------------------------------------------------------


def test_zero_findings_produces_empty_jsonl(tmp_path):
    """An audit with zero findings produces an empty (or absent) accepted_findings.jsonl and exit 0."""
    audit = _make_audit_doc(findings=[])
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit})

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0

    path = run_dir / "accepted_findings.jsonl"
    if path.exists():
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        assert lines == [], "zero findings should produce an empty jsonl"


def test_no_audit_json_exits_nonzero(tmp_path):
    """No audit JSON in the run dir is a hard error (exit 2)."""
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={})
    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 2, f"no audits should be exit 2: {proc.stdout!r}"


def test_expired_warrant_aborts_triage(tmp_path):
    """An expired warrant is refused at triage stage entry (exit 2)."""
    finding = _make_finding(evidence_level="E2_tested", failure_class="CLASS_Z")
    audit = _make_audit_doc(findings=[finding])
    expired = _make_warrant_dict()
    expired["expires_at"] = "2020-01-01T00:00:00Z"
    warrant, run_id, run_dir = _setup_run(tmp_path, audits={"TV-01": audit}, warrant=expired)

    proc = _run_triage_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 2
    assert "expired" in (proc.stdout + proc.stderr).lower()


# ---------------------------------------------------------------------------
# Unit tests for the triage policy functions (deterministic, no CLI)
# ---------------------------------------------------------------------------


def test_evidence_order():
    """Evidence level ordering is correct: E0 < E1 < E2 < E3 < E4."""
    from scripts.governance.loop.prompt_audit_triage import EVIDENCE_ORDER, E2_FLOOR

    assert EVIDENCE_ORDER["E0_none"] < EVIDENCE_ORDER["E1_static"]
    assert EVIDENCE_ORDER["E1_static"] < EVIDENCE_ORDER["E2_tested"]
    assert EVIDENCE_ORDER["E2_tested"] < EVIDENCE_ORDER["E3_cross_checked"]
    assert EVIDENCE_ORDER["E3_cross_checked"] < EVIDENCE_ORDER["E4_regression_proven"]
    assert E2_FLOOR == EVIDENCE_ORDER["E2_tested"]


def test_route_finding_e2plus_implement():
    from scripts.governance.loop.prompt_audit_triage import route_finding

    f = _make_finding(evidence_level="E2_tested", failure_class="C1", severity="medium", confidence="high")
    assert route_finding(f) == "IMPLEMENT"


def test_route_finding_below_e2_defer():
    from scripts.governance.loop.prompt_audit_triage import route_finding

    f = _make_finding(evidence_level="E1_static", failure_class="C1", severity="medium", confidence="high")
    assert route_finding(f) == "DEFER"


def test_route_finding_missing_failure_class_needs_human():
    from scripts.governance.loop.prompt_audit_triage import route_finding

    f = _make_finding(evidence_level="E2_tested", failure_class="", severity="medium", confidence="high")
    assert route_finding(f) == "NEEDS_HUMAN"


def test_route_finding_low_confidence_high_severity_needs_human():
    from scripts.governance.loop.prompt_audit_triage import route_finding

    f = _make_finding(evidence_level="E2_tested", failure_class="C1", severity="critical", confidence="low")
    assert route_finding(f) == "NEEDS_HUMAN"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
