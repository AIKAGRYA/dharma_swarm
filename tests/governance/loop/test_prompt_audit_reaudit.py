"""Tests for scripts/governance/loop/prompt_audit_reaudit.py — Stage 4 (Verifier).

Covers VAL-REAUDIT-002..011:
  002  Verifier sees only claim + deterministic evidence (NOT Implementer rationale)
  003  Falsification mandate (falsification_attempts[] with concrete attempts)
  004  Anti-gaming checklist in verdict (all §8 items)
  005  model_independence recorded honestly (not_proven in stub mode)
  006  verifier_verdict.yaml produced (§6.3 schema: verdict + checklist + attempts + evidence)
  007  Refuted verdict prevents ratcheting (no ratchet/ledger)
  008  Inconclusive verdict routes to DEFER (no ratchet advancement)
  009  verifier_model recorded in verdict (stub in M1)
  010  Verifier checklist includes no_widened_budgets
  011  Verifier prompt frames falsification as the success condition
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
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
REAUDIT_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_reaudit.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

USER_REPO = "/Users/dhyana/dharma_swarm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_warrant_dict(run_id: str = "warrant-reaudit-test") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "HEAD",
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/**"],
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _make_finding(
    fid: str = "F-001",
    routing: str = "IMPLEMENT",
    evidence_level: str = "E2_tested",
    failure_class: str = "SLOP_MARKER_DRIFT",
    files: list[str] | None = None,
) -> dict:
    return {
        "finding_id": fid,
        "prompt_id": "TV-01",
        "council_id": "testing_verification",
        "title": "test finding",
        "severity": "medium",
        "evidence_level": evidence_level,
        "failure_class": failure_class,
        "routing": routing,
        "must_gate": False,
        "recurrence_score": 0,
        "recurrence_within_run": False,
        "files": files or [],
        "observed": "stub observation",
        "recommendation": "stub recommendation",
        "audit_path": "audit/TV-01.json",
    }


def _make_fix_proposal(
    run_id: str,
    finding_id: str = "F-001",
    proof_mode: str = "synthetic",
    red_exit: int = 1,
    green_exit: int = 0,
    write_set: list[str] | None = None,
    implementer_rationale: str | None = None,
) -> dict:
    """Build a §6.2 fix_proposal dict. ``implementer_rationale`` simulates a
    rationale field that must NEVER be passed to the Verifier."""
    fp = {
        "fix_proposal": {
            "run_id": run_id,
            "finding_id": finding_id,
            "write_set_used": write_set or ["scripts/governance/loop/**"],
            "patch_ref": f"fix/{finding_id}",
            "red_before": {
                "command": f'"{VENV_PYTHON}" gate.py',
                "exit_code": red_exit,
                "key_output": "FAIL: marker not found" if red_exit != 0 else "OK",
            },
            "green_after": {
                "command": f'"{VENV_PYTHON}" gate.py',
                "exit_code": green_exit,
                "key_output": "OK: marker found" if green_exit == 0 else "FAIL",
            },
            "proof_mode": proof_mode,
            "anti_gaming_checklist": {
                "no_new_skips": "pass",
                "no_new_xfails": "pass",
                "no_weakened_assertions": "pass",
                "no_deleted_tests": "pass",
                "no_widened_budgets": "pass",
                "fix_addresses_root_cause": "pass",
            },
        }
    }
    if implementer_rationale is not None:
        fp["fix_proposal"]["implementer_rationale"] = implementer_rationale
    return fp


def _clean_diff(filepath: str = "scripts/governance/loop/marker.txt") -> str:
    """A valid unified diff that passes all anti-gaming checks."""
    return (
        f"diff --git a/{filepath} b/{filepath}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{filepath}\n"
        "@@ -0,0 +1 @@\n"
        "+fix applied\n"
    )


def _setup_run(
    tmp_path: Path,
    finding: dict,
    fix_proposal: dict,
    fix_diff: str = "",
    warrant: dict | None = None,
) -> tuple[Path, str, Path]:
    """Create a run dir with accepted_findings + fix_proposal + fix_diff.

    Returns (warrant_path, run_id, runs_root).
    """
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "reaudit-test-001"
    w = warrant or _make_warrant_dict()
    warrant_path = tmp_path / "warrant.yaml"
    warrant_path.write_text(yaml.safe_dump(w, sort_keys=False))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id, "--warrant", str(warrant_path)],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"
    run_dir = Path(proc.stdout.strip())

    from scripts.governance.loop.runs import Run
    run = Run(run_dir)
    # Write accepted_findings.jsonl
    run.write_jsonl(run.accepted_findings_path(), [finding])
    # Write fix_proposal
    fid = finding["finding_id"]
    run.write_yaml(run.fix_proposal_path(fid), fix_proposal)
    # Write fix diff
    if fix_diff:
        diff_path = run.fixes_dir / f"fix_diff_{fid}.patch"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(fix_diff)

    return warrant_path, run_id, runs_root


def _run_reaudit_cli(
    warrant: Path,
    run_id: str,
    runs_root: Path,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "stub"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            VENV_PYTHON, str(REAUDIT_CLI),
            "--warrant", str(warrant),
            "--run-id", run_id,
        ],
        capture_output=True, text=True, env=env,
    )


def _open_run(run_id: str, runs_root: Path):
    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    return RunManager.open_run(run_id)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-006: verifier_verdict.yaml produced (§6.3 schema)
# ---------------------------------------------------------------------------


def test_verifier_verdict_produced(tmp_path):
    """VAL-REAUDIT-006: verifier_verdict_<id>.yaml is produced with verdict +
    anti_gaming_checklist + falsification_attempts + evidence."""
    finding = _make_finding(fid="F-VP-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-VP-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        vpath = run.verifier_verdict_path("F-VP-001")
        assert vpath.exists(), f"verifier_verdict not written: {vpath}"
        doc = yaml.safe_load(vpath.read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["finding_id"] == "F-VP-001"
        assert vv["verdict"] in ("confirmed", "refuted", "inconclusive")
        assert "anti_gaming_checklist" in vv
        assert "falsification_attempts" in vv
        assert isinstance(vv["falsification_attempts"], list)
        assert len(vv["falsification_attempts"]) > 0
        assert "evidence" in vv
        receipt = vv.get("verifier_invocation")
        assert receipt and receipt["role"] == "verifier"
        assert receipt["invocation_id"].startswith("stub-verifier-")
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-002: Verifier sees only claim + deterministic evidence
# ---------------------------------------------------------------------------


def test_verifier_input_excludes_implementer_rationale(tmp_path):
    """VAL-REAUDIT-002: the Verifier input contains evidence but NOT Implementer
    rationale. Even when the fix_proposal carries an implementer_rationale field,
    it must not appear in the constructed verifier input."""
    from scripts.governance.loop.prompt_audit_reaudit import build_verifier_input

    finding = _make_finding(fid="F-ISO-001")
    fix_proposal = _make_fix_proposal(
        "reaudit-test-001", "F-ISO-001",
        implementer_rationale="I fixed it by adding the marker because the gate checks for it.",
    )
    fp_inner = fix_proposal["fix_proposal"]

    verifier_input = build_verifier_input(finding, fp_inner)

    # Must contain the claim (finding fields) + deterministic evidence
    assert verifier_input["finding_id"] == "F-ISO-001"
    assert "evidence" in verifier_input
    assert "red_before" in verifier_input["evidence"]
    assert "green_after" in verifier_input["evidence"]

    # Must NOT contain the Implementer's rationale
    assert "implementer_rationale" not in verifier_input
    assert "implementer_rationale" not in verifier_input.get("evidence", {})
    # No rationale-like keys leak through
    for key in ("rationale", "implementer_notes", "summary", "recommendation", "inferred"):
        assert key not in verifier_input, f"Verifier input leaks {key!r}"


def test_verifier_input_recursively_strips_session_context():
    from scripts.governance.loop.prompt_audit_reaudit import build_verifier_input

    finding = _make_finding(fid="F-NESTED-ISO")
    finding["session_context"] = {"implementer_rationale": "SECRET_RATIONALE"}
    finding["nested"] = [{"rationale": "SECRET_NESTED"}]
    fix_proposal = _make_fix_proposal("reaudit-test-001", "F-NESTED-ISO")
    fp = fix_proposal["fix_proposal"]
    fp["implementer_invocation"] = {
        "invocation_id": "impl-secret",
        "stdout_excerpt": "SECRET_STDOUT",
        "session_context": {"notes": "SECRET_NOTES"},
    }
    fp["red_before"]["session_context"] = {"rationale": "SECRET_RECEIPT_CONTEXT"}

    verifier_input = build_verifier_input(finding, fp)
    serialized = json.dumps(verifier_input, sort_keys=True)
    assert "SECRET_" not in serialized
    assert "implementer_invocation" not in serialized
    assert "session_context" not in serialized


# ---------------------------------------------------------------------------
# VAL-REAUDIT-003: Falsification mandate (concrete attempts listed)
# ---------------------------------------------------------------------------


def test_falsification_attempts_listed(tmp_path):
    """VAL-REAUDIT-003: falsification_attempts[] are concrete attempts, not just
    a confirmation."""
    finding = _make_finding(fid="F-FALSIFY-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-FALSIFY-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-FALSIFY-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        attempts = vv["falsification_attempts"]
        assert len(attempts) >= 2, f"need concrete falsification attempts, got {attempts}"
        for a in attempts:
            assert isinstance(a, dict)
            assert "attempt" in a, f"attempt missing 'attempt' field: {a}"
            assert "result" in a, f"attempt missing 'result' field: {a}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_falsification_attempts_listed_empty_diff(tmp_path):
    """falsification_attempts[] are listed even when the diff is minimal."""
    finding = _make_finding(fid="F-FALSIFY-002")
    fp = _make_fix_proposal("reaudit-test-001", "F-FALSIFY-002")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff="")

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    # Empty diff → fix_addresses_root_cause fails → refuted (exit 1)
    assert proc.returncode != 0

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-FALSIFY-002").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert len(vv["falsification_attempts"]) > 0
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-004: Anti-gaming checklist in verdict (all §8 items)
# ---------------------------------------------------------------------------


def test_anti_gaming_checklist_all_items(tmp_path):
    """VAL-REAUDIT-004: the verifier_verdict includes the §8 anti_gaming_checklist
    with no_new_skips, no_new_xfails, no_weakened_assertions, no_deleted_tests,
    fix_addresses_root_cause (all with pass/fail)."""
    finding = _make_finding(fid="F-AG-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-AG-001")
    diff = (
        "diff --git a/scripts/governance/loop/marker.txt b/scripts/governance/loop/marker.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/scripts/governance/loop/marker.txt\n"
        "@@ -0,0 +1 @@\n"
        "+fix applied\n"
    )
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-AG-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        checklist = vv["anti_gaming_checklist"]
        for item in ["no_new_skips", "no_new_xfails", "no_weakened_assertions",
                      "no_deleted_tests", "fix_addresses_root_cause"]:
            assert item in checklist, f"checklist missing {item}"
            assert checklist[item] in ("pass", "fail"), f"checklist {item}={checklist[item]!r}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-010: Verifier checklist includes no_widened_budgets
# ---------------------------------------------------------------------------


def test_checklist_includes_no_widened_budgets(tmp_path):
    """VAL-REAUDIT-010: the verifier_verdict's anti_gaming_checklist includes a
    no_widened_budgets entry with pass/fail."""
    finding = _make_finding(fid="F-WB-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-WB-001")
    diff = (
        "diff --git a/scripts/governance/loop/marker.txt b/scripts/governance/loop/marker.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/scripts/governance/loop/marker.txt\n"
        "@@ -0,0 +1 @@\n"
        "+fix applied\n"
    )
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-WB-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert "no_widened_budgets" in vv["anti_gaming_checklist"]
        assert vv["anti_gaming_checklist"]["no_widened_budgets"] in ("pass", "fail")
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-005: model_independence recorded honestly
# ---------------------------------------------------------------------------


def test_model_independence_not_proven_in_stub(tmp_path):
    """VAL-REAUDIT-005: model_independence is 'not_proven' in stub mode (never
    recorded as pass/proven when a different family was not used)."""
    finding = _make_finding(fid="F-MI-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-MI-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-MI-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert "model_independence" in vv, "missing model_independence field"
        assert vv["model_independence"] == "not_proven", (
            f"stub mode must record not_proven, got {vv['model_independence']!r}"
        )
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_model_independence_never_pass_when_not_proven(tmp_path):
    """VAL-REAUDIT-005: model_independence is never 'proven' or 'pass' when the
    verifier is the same family (stub). Even a custom same-family verifier must
    record not_proven."""
    from scripts.governance.loop.prompt_audit_reaudit import (
        VerifierBackend, VerifierResult, run_reaudit,
    )
    from scripts.governance.loop.runs import RunManager

    finding = _make_finding(fid="F-MI-002", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-MI-002")
    diff = _clean_diff()
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    class SameFamilyVerifier(VerifierBackend):
        def verify(self, finding, evidence, prompt):
            return VerifierResult(
                verdict="confirmed",
                falsification_attempts=[{"attempt": "stub", "result": "pass"}],
                verifier_model="stub-same-family",
                model_independence="proven",  # wrongly claims proven
            )

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        warrant = _make_warrant_dict()
        wp = tmp_path / "w2.yaml"
        wp.write_text(yaml.safe_dump(warrant, sort_keys=False))
        rc = run_reaudit(wp, run, SameFamilyVerifier())
        # The stage must override the dishonest "proven" to "not_proven"
        doc = yaml.safe_load(run.verifier_verdict_path("F-MI-002").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["model_independence"] == "not_proven", (
            "stage must not allow a same-family/stub verifier to claim proven"
        )
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-009: verifier_model recorded in verdict
# ---------------------------------------------------------------------------


def test_verifier_model_recorded(tmp_path):
    """VAL-REAUDIT-009: verifier_verdict includes verifier_model (stub in M1)."""
    finding = _make_finding(fid="F-VM-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-VM-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-VM-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert "verifier_model" in vv, "missing verifier_model field"
        assert vv["verifier_model"] == "stub", (
            f"stub mode must record verifier_model='stub', got {vv['verifier_model']!r}"
        )
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-011: Verifier prompt frames falsification as success
# ---------------------------------------------------------------------------


def test_falsification_prompt_frames_falsification_as_success():
    """VAL-REAUDIT-011: the Verifier prompt explicitly frames finding the fix
    incomplete or gamed as the goal (falsification = success)."""
    from scripts.governance.loop.prompt_audit_reaudit import build_falsification_prompt
    prompt = build_falsification_prompt()
    text = prompt.lower()
    # Must frame falsification as the success condition
    assert "falsif" in text, "prompt must mention falsification"
    assert "disprove" in text or "incomplete" in text or "gamed" in text, (
        "prompt must frame finding the fix incomplete/gamed as the goal"
    )
    # Must NOT frame confirmation as the success condition
    assert "confirm the fix is correct" not in text
    assert "your goal is to confirm" not in text


def test_falsification_prompt_in_verdict_artifact(tmp_path):
    """VAL-REAUDIT-011: the verdict artifact (or a receipt) records the
    falsification-first prompt so it is inspectable."""
    finding = _make_finding(fid="F-PROMPT-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-PROMPT-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        # The prompt should be recorded in a receipt under receipts/
        prompt_receipt = run.receipts_dir / "verifier_prompt_F-PROMPT-001.txt"
        assert prompt_receipt.exists(), f"falsification prompt receipt not written: {prompt_receipt}"
        text = prompt_receipt.read_text().lower()
        assert "falsif" in text
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-007: Refuted verdict prevents ratcheting
# ---------------------------------------------------------------------------


def test_refuted_verdict_prevents_ratcheting(tmp_path):
    """VAL-REAUDIT-007: a refuted verdict causes no ratchet_<id>.yaml or
    ledger_entry to be produced. The finding is rejected."""
    finding = _make_finding(fid="F-REFUTE-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-REFUTE-001")
    # Diff with a skip → anti-gaming fails → refuted
    diff = (
        "diff --git a/tests/x.py b/tests/x.py\n"
        "--- /dev/null\n"
        "+++ b/tests/x.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+import pytest\n"
        "+pytest.skip('gamed')\n"
    )
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode != 0, "refuted verdict should exit non-zero (exit 1)"

    try:
        run = _open_run(run_id, runs_root)
        vpath = run.verifier_verdict_path("F-REFUTE-001")
        assert vpath.exists(), "verifier_verdict must be written even on refutation"
        doc = yaml.safe_load(vpath.read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["verdict"] == "refuted", f"expected refuted, got {vv['verdict']!r}"
        # No ratchet or ledger produced
        assert not run.ratchet_path("F-REFUTE-001").exists(), "refuted must not produce ratchet"
        assert not run.ledger_entry_path("F-REFUTE-001").exists(), "refuted must not produce ledger"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_refuted_via_invalid_evidence(tmp_path):
    """A fix_proposal with invalid evidence (red_before exit 0) is refuted."""
    finding = _make_finding(fid="F-BADRED-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-BADRED-001", red_exit=0)
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode != 0, "invalid red_before should refute (non-zero exit)"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-BADRED-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["verdict"] == "refuted"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REAUDIT-008: Inconclusive verdict routes to DEFER
# ---------------------------------------------------------------------------


def test_inconclusive_routes_to_defer(tmp_path):
    """VAL-REAUDIT-008: an inconclusive verdict routes the finding to DEFER (no
    ratchet advancement)."""
    from scripts.governance.loop.prompt_audit_reaudit import (
        VerifierBackend, VerifierResult, run_reaudit,
    )
    from scripts.governance.loop.runs import RunManager

    finding = _make_finding(fid="F-INCONCL-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-INCONCL-001")
    diff = _clean_diff()
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    class InconclusiveVerifier(VerifierBackend):
        def verify(self, finding, evidence, prompt):
            return VerifierResult(
                verdict="inconclusive",
                falsification_attempts=[{"attempt": "could not reproduce red-before", "result": "inconclusive"}],
                verifier_model="stub",
                model_independence="not_proven",
            )

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        warrant = _make_warrant_dict()
        wp = tmp_path / "w2.yaml"
        wp.write_text(yaml.safe_dump(warrant, sort_keys=False))
        rc = run_reaudit(wp, run, InconclusiveVerifier())
        # Inconclusive → DEFER → exit 0 (clean, not a rejection)
        assert rc == 0, f"inconclusive should route to DEFER cleanly, got exit {rc}"

        doc = yaml.safe_load(run.verifier_verdict_path("F-INCONCL-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["verdict"] == "inconclusive"
        # No ratchet or ledger produced
        assert not run.ratchet_path("F-INCONCL-001").exists(), "inconclusive must not ratchet"
        assert not run.ledger_entry_path("F-INCONCL-001").exists(), "inconclusive must not ledger"
        # DEFER should be recorded somewhere (routing in verdict or stdout)
        output = vv.get("routing", "")
        assert output == "DEFER" or "DEFER" in str(vv)
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# Confirmed verdict (happy path)
# ---------------------------------------------------------------------------


def test_confirmed_verdict_clean_fix(tmp_path):
    """A clean fix (valid red/green, anti-gaming all pass) produces a confirmed
    verdict and does NOT produce ratchet/ledger (that is Stage 5's job)."""
    finding = _make_finding(fid="F-CONFIRM-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-CONFIRM-001")
    diff = (
        "diff --git a/scripts/governance/loop/marker.txt b/scripts/governance/loop/marker.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/scripts/governance/loop/marker.txt\n"
        "@@ -0,0 +1 @@\n"
        "+fix applied\n"
    )
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-CONFIRM-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["verdict"] == "confirmed"
        # Stage 4 does not produce ratchet/ledger (Stage 5 does)
        assert not run.ratchet_path("F-CONFIRM-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# Anti-gaming checklist run independently (not copied from remediate)
# ---------------------------------------------------------------------------


def test_anti_gaming_run_independently(tmp_path):
    """The reaudit anti-gaming checklist is run on the fix diff independently,
    not just copied from the fix_proposal. A diff with a skip must fail even if
    the fix_proposal's checklist says all-pass."""
    finding = _make_finding(fid="F-INDEP-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-INDEP-001")
    # fix_proposal says all-pass, but the diff has a skip → independent check must catch it
    diff = (
        "diff --git a/tests/y.py b/tests/y.py\n"
        "--- /dev/null\n"
        "+++ b/tests/y.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+import pytest\n"
        "+@pytest.mark.skip('gamed')\n"
    )
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=diff)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode != 0, "independent anti-gaming should catch the skip → refuted"

    try:
        run = _open_run(run_id, runs_root)
        doc = yaml.safe_load(run.verifier_verdict_path("F-INDEP-001").read_text())
        vv = doc.get("verifier_verdict", doc)
        assert vv["verdict"] == "refuted"
        assert vv["anti_gaming_checklist"]["no_new_skips"] == "fail"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# No fix_proposals → clean exit (nothing to verify)
# ---------------------------------------------------------------------------


def test_no_fix_proposals_clean_exit(tmp_path):
    """When there are no fix_proposals, the stage exits 0 (nothing to verify)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "reaudit-empty-001"
    warrant = _make_warrant_dict()
    warrant_path = tmp_path / "warrant.yaml"
    warrant_path.write_text(yaml.safe_dump(warrant, sort_keys=False))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id, "--warrant", str(warrant_path)],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0

    # Write accepted_findings with a DEFER finding (no fix_proposal)
    from scripts.governance.loop.runs import Run
    run = Run(Path(proc.stdout.strip()))
    run.write_jsonl(run.accepted_findings_path(), [_make_finding(fid="F-DEFER", routing="DEFER")])

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"no fix_proposals should exit 0, got {proc.returncode}"


# ---------------------------------------------------------------------------
# Warrant re-validation on stage entry
# ---------------------------------------------------------------------------


def test_expired_warrant_aborts_stage_entry(tmp_path):
    """An expired warrant is refused at reaudit stage entry (exit 2)."""
    finding = _make_finding(fid="F-EXP-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-EXP-001")
    warrant = _make_warrant_dict()
    warrant["expires_at"] = "2020-01-01T00:00:00Z"
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff="+x\n", warrant=warrant)

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode != 0
    output = proc.stdout + proc.stderr
    assert "expired" in output.lower()


# ---------------------------------------------------------------------------
# User working tree never touched
# ---------------------------------------------------------------------------


def test_user_working_tree_untouched(tmp_path):
    """The user's working tree at /Users/dhyana/dharma_swarm is not modified."""
    finding = _make_finding(fid="F-USERTREE-001", files=["scripts/governance/loop/marker.txt"])
    fp = _make_fix_proposal("reaudit-test-001", "F-USERTREE-001")
    warrant_path, run_id, runs_root = _setup_run(tmp_path, finding, fp, fix_diff=_clean_diff())

    before = subprocess.run(
        ["git", "-C", USER_REPO, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    before_branch = subprocess.run(
        ["git", "-C", USER_REPO, "branch", "--show-current"],
        capture_output=True, text=True,
    )

    proc = _run_reaudit_cli(warrant_path, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    after = subprocess.run(
        ["git", "-C", USER_REPO, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    after_branch = subprocess.run(
        ["git", "-C", USER_REPO, "branch", "--show-current"],
        capture_output=True, text=True,
    )

    assert before.stdout == after.stdout, "user working tree status changed!"
    assert before_branch.stdout == after_branch.stdout, "user working tree branch changed!"


# ---------------------------------------------------------------------------
# VAL-AUDIT-004: Verifier evidence filtered to deterministic keys
# ---------------------------------------------------------------------------


def test_deterministic_receipt_subset_keeps_only_whitelisted_keys():
    """VAL-AUDIT-004: _deterministic_receipt_subset keeps only the deterministic
    receipt keys (command, exit_code, key_output, receipt_ref, valid, kind, value)
    and strips non-deterministic keys (rationale, session_context, recommendations)."""
    from scripts.governance.loop.prompt_audit_reaudit import (
        _DETERMINISTIC_RECEIPT_KEYS,
        _deterministic_receipt_subset,
    )

    expected_keys = {"command", "exit_code", "key_output", "receipt_ref", "valid", "kind", "value"}
    assert _DETERMINISTIC_RECEIPT_KEYS == expected_keys, (
        f"deterministic key set must be exactly {expected_keys}, got {_DETERMINISTIC_RECEIPT_KEYS}"
    )

    receipt = {
        "command": "pytest tests/x.py",
        "exit_code": 1,
        "key_output": "FAIL: ...",
        "receipt_ref": "receipts/red_before.json",
        "valid": True,
        "kind": "red_before",
        "value": 42,
        # non-deterministic keys that must be stripped
        "rationale": "the fix is good because I said so",
        "session_context": {"notes": "SECRET"},
        "recommendations": ["trust me"],
        "implementer_notes": "I fixed it",
        "inferred": "probably works",
    }
    subset = _deterministic_receipt_subset(receipt)
    # Only deterministic keys retained
    assert set(subset.keys()) == expected_keys, (
        f"subset must contain only deterministic keys, got {set(subset.keys())}"
    )
    # Non-deterministic keys stripped
    for bad_key in ("rationale", "session_context", "recommendations", "implementer_notes", "inferred"):
        assert bad_key not in subset, f"non-deterministic key {bad_key!r} leaked into subset"
    # Deterministic values preserved
    assert subset["command"] == "pytest tests/x.py"
    assert subset["exit_code"] == 1
    assert subset["kind"] == "red_before"


def test_deterministic_receipt_subset_non_dict_returns_empty():
    """VAL-AUDIT-004: a non-dict receipt yields an empty dict (no crash)."""
    from scripts.governance.loop.prompt_audit_reaudit import _deterministic_receipt_subset

    assert _deterministic_receipt_subset(None) == {}
    assert _deterministic_receipt_subset("not a dict") == {}
    assert _deterministic_receipt_subset([]) == {}


def test_verifier_input_evidence_contains_only_deterministic_keys(tmp_path):
    """VAL-AUDIT-004: the constructed verifier input's evidence receipts contain
    ONLY deterministic keys (end-to-end via build_verifier_input)."""
    from scripts.governance.loop.prompt_audit_reaudit import build_verifier_input

    finding = _make_finding(fid="F-DETKEYS-001")
    fp = _make_fix_proposal("reaudit-test-001", "F-DETKEYS-001")
    fp_inner = fp["fix_proposal"]
    # Inject non-deterministic keys into the receipts
    fp_inner["red_before"]["rationale"] = "SECRET_RATIONALE"
    fp_inner["red_before"]["session_context"] = {"notes": "SECRET"}
    fp_inner["green_after"]["recommendations"] = ["trust me"]

    verifier_input = build_verifier_input(finding, fp_inner)
    red = verifier_input["evidence"]["red_before"]
    green = verifier_input["evidence"]["green_after"]
    allowed = {"command", "exit_code", "key_output", "receipt_ref", "valid", "kind", "value"}
    assert set(red.keys()) <= allowed, f"red_before leaked non-deterministic keys: {set(red.keys()) - allowed}"
    assert set(green.keys()) <= allowed, f"green_after leaked non-deterministic keys: {set(green.keys()) - allowed}"
    assert "rationale" not in red
    assert "session_context" not in red
    assert "recommendations" not in green


# ---------------------------------------------------------------------------
# VAL-AUDIT-005: Verifier generates unique invocation receipts (uuid4-based)
# ---------------------------------------------------------------------------


def test_consecutive_verifier_invocations_have_distinct_invocation_ids():
    """VAL-AUDIT-005: two consecutive Verifier invocations generate different
    uuid4-based invocation_ids, proving fresh context is distinguishable across runs."""
    from scripts.governance.loop.prompt_audit_reaudit import StubVerifier

    verifier = StubVerifier()
    finding = _make_finding(fid="F-UUID-001")
    evidence = {
        "finding_id": "F-UUID-001",
        "claim": {"finding_id": "F-UUID-001"},
        "evidence": {
            "red_before": {"exit_code": 1},
            "green_after": {"exit_code": 0},
            "proof_mode": "synthetic",
        },
    }
    prompt = "falsification-first"

    verifier.verify(finding, evidence, prompt)
    first_receipt = verifier.invocation_receipt()
    verifier.verify(finding, evidence, prompt)
    second_receipt = verifier.invocation_receipt()

    assert first_receipt is not None and second_receipt is not None
    assert first_receipt["invocation_id"] != second_receipt["invocation_id"], (
        "two consecutive verifier invocations must have distinct invocation_ids"
    )
    assert first_receipt["invocation_id"].startswith("stub-verifier-")
    assert second_receipt["invocation_id"].startswith("stub-verifier-")


def test_invocation_id_is_uuid4_hex_format():
    """VAL-AUDIT-005: the invocation_id suffix is a uuid4 hex (32 hex chars)."""
    from scripts.governance.loop.prompt_audit_reaudit import StubVerifier

    verifier = StubVerifier()
    finding = _make_finding(fid="F-UUIDFMT-001")
    evidence = {
        "finding_id": "F-UUIDFMT-001",
        "claim": {"finding_id": "F-UUIDFMT-001"},
        "evidence": {
            "red_before": {"exit_code": 1},
            "green_after": {"exit_code": 0},
            "proof_mode": "synthetic",
        },
    }
    verifier.verify(finding, evidence, "prompt")
    receipt = verifier.invocation_receipt()
    suffix = receipt["invocation_id"].replace("stub-verifier-", "")
    # uuid4 hex is 32 hex characters
    assert len(suffix) == 32, f"uuid4 hex suffix must be 32 chars, got {len(suffix)}: {suffix!r}"
    assert all(c in "0123456789abcdef" for c in suffix), f"suffix must be hex: {suffix!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
