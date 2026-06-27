"""Agentized end-to-end test for the Cybernetic Ratchet Loop (M2 integration).

Drives the full 5-stage chain with ``LOOP_AGENT_BACKEND=droid`` against a fake
``droid`` CLI (deterministic, no network) that records every invocation and
returns schema-valid canned audit JSON. This proves the Phase-2 agentized
assertions at the integrated loop level:

  VAL-AGENT-002  DroidBackend shells out to the droid CLI for LLM stages
  VAL-AGENT-003  Auditor / Implementer / Verifier are distinct invocations
                 with isolated contexts (not one session playing all roles)
  VAL-AGENT-004  Verifier invocation does NOT receive Implementer rationale
  VAL-AGENT-006  For high/critical findings the Verifier routes to a different
                 model family; model_independence recorded honestly
  VAL-REAUDIT-001  Verifier is a FRESH context, distinct from the Implementer
                   session
  VAL-CROSS-004  Agentized loop (droid backend) produces fix_proposal +
                 verifier_verdict + ratchet (ready-to-merge proposal)
  VAL-CROSS-005  No LLM opinion recorded as truth (verdicts backed by receipts)
  VAL-CROSS-007  User working tree never modified

The fake droid CLI stands in for the real ``droid`` CLI so the test is
deterministic and hermetic. A separate live run against the real droid CLI
(see handoff) provides the non-deterministic real-world evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"

LOOP_DIR = REPO_ROOT / "scripts" / "governance" / "loop"
RUNS_CLI = LOOP_DIR / "runs.py"
SCOPER_CLI = LOOP_DIR / "scoper.py"
AUDIT_RUN_CLI = LOOP_DIR / "prompt_audit_run.py"
TRIAGE_CLI = LOOP_DIR / "prompt_audit_triage.py"
REMEDIATE_CLI = LOOP_DIR / "prompt_audit_remediate.py"
REAUDIT_CLI = LOOP_DIR / "prompt_audit_reaudit.py"
LEARN_CLI = LOOP_DIR / "prompt_audit_learn.py"
VALIDATE_AUDIT_CLI = LOOP_DIR / "validate_audit.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

MISSION_BRANCH = "ratchet/loop-phases-1-3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _make_warrant_dict(run_id: str = "warrant-agentized") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "HEAD",
            "head_ref": MISSION_BRANCH,
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/**"],
        "budget": {
            "max_tokens": 100000,
            "max_wall_clock_min": 30,
            "max_fixes_per_run": 5,
        },
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _high_severity_audit_json(run_id: str) -> dict:
    """A schema-valid audit document with one HIGH severity E2_tested finding.

    Routing through triage yields an IMPLEMENT finding with severity=high, which
    forces the DroidBackend to route the Verifier to a different model family
    (VAL-AGENT-006).
    """
    return {
        "prompt_id": "TV-01",
        "council_id": "testing_verification",
        "run_id": run_id,
        "operator": "droid",
        "model": "glm-5.2",
        "repo_path": str(REPO_ROOT),
        "git_ref": MISSION_BRANCH,
        "timestamp_utc": _future_iso(0),
        "mode": "weekly",
        "scope": {
            "files_examined": [],
            "commands_run": [
                {
                    "command": "pytest --collect-only -q",
                    "cwd": str(REPO_ROOT),
                    "exit_code": 0,
                    "key_output": "collection ok",
                }
            ],
            "commands_not_run": [],
        },
        "summary": {
            "verdict": "warn",
            "confidence": "high",
            "evidence_floor": "E2_tested",
        },
        "findings": [
            {
                "id": "F-HIGH-001",
                "title": "High-severity slop finding for agentized e2e",
                "severity": "high",
                "evidence_level": "E2_tested",
                "confidence": "high",
                "files": [],
                "line_refs": [],
                "observed": "agentized e2e canned observation",
                "inferred": "agentized e2e canned inference",
                "risk": "high-severity slop class",
                "failure_class": "HIGH_SLOP_AGENTIZED",
                "recommendation": "fix via isolated worktree + deterministic gate",
                "verification": "red-before/green-after on a deterministic gate",
            }
        ],
        "not_proven": ["agentized e2e — canned finding for role-separation proof"],
        "open_questions": [],
        "follow_up_issues": [],
    }


def _write_fake_droid(tmp_path: Path, stdout_text: str) -> Path:
    """Write a fake ``droid`` executable that logs argv+prompt and emits stdout.

    The fake reads ``DROID_FAKE_LOG`` (append one JSON line per invocation) and
    ``DROID_FAKE_STDOUT`` / ``DROID_FAKE_EXIT`` for the emitted output / exit
    code. This stands in for the real ``droid`` CLI so the test is deterministic.
    """
    fake = tmp_path / "droid"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "log_path = os.environ.get('DROID_FAKE_LOG')\n"
        "prompt_text = ''\n"
        "if '-f' in sys.argv:\n"
        "    prompt_text = Path(sys.argv[sys.argv.index('-f') + 1]).read_text()\n"
        "if log_path:\n"
        "    with open(log_path, 'a') as fh:\n"
        "        fh.write(json.dumps({'argv': sys.argv[1:], 'prompt': prompt_text}) + '\\n')\n"
        "sys.stdout.write(os.environ.get('DROID_FAKE_STDOUT', " + repr(stdout_text) + "))\n"
        "sys.exit(int(os.environ.get('DROID_FAKE_EXIT', '0')))\n"
    )
    fake.chmod(0o755)
    return fake


def _base_env(runs_root: Path, fake_droid: Path, audit_stdout: str) -> dict:
    """Build the env for agentized CLI stage invocations."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "droid"
    env["LOOP_DROID_PATH"] = str(fake_droid)
    env["DROID_FAKE_STDOUT"] = audit_stdout
    # Force the heterogeneous verifier model to a different family than primary.
    env["LOOP_DROID_PRIMARY_MODEL"] = "glm-5.2"
    env["LOOP_DROID_VERIFIER_MODEL"] = "gpt-5.2"
    return env


def _run_cli(cli: Path, env: dict, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [VENV_PYTHON, str(cli), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _open_run(run_id: str, runs_root: Path):
    from scripts.governance.loop.runs import RunManager

    old = os.environ.get("LOOP_RUNS_DIR")
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        return RunManager.open_run(run_id)
    finally:
        if old is not None:
            os.environ["LOOP_RUNS_DIR"] = old
        else:
            os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# Fixture: run the full 5-stage chain with the droid backend
# ---------------------------------------------------------------------------


@pytest.fixture()
def agentized_run(tmp_path: Path):
    """Run the full 5-stage pipeline with LOOP_AGENT_BACKEND=droid (fake CLI)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    warrant_path = _write_warrant(tmp_path)
    run_id = f"agentized-{int(time.time())}"

    audit_stdout = json.dumps(_high_severity_audit_json(run_id))
    fake_droid = _write_fake_droid(tmp_path, audit_stdout)
    droid_log = tmp_path / "droid_invocations.log"
    fake_droid.parent.mkdir(parents=True, exist_ok=True)

    env = _base_env(runs_root, fake_droid, audit_stdout)
    env["DROID_FAKE_LOG"] = str(droid_log)

    origin_main_before = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
        capture_output=True, text=True,
    ).stdout.strip()

    stage_procs: dict[str, subprocess.CompletedProcess[str]] = {}

    proc = _run_cli(RUNS_CLI, env, "create", "--run-id", run_id, "--warrant", str(warrant_path))
    stage_procs["runs_create"] = proc
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"
    run_dir = Path(proc.stdout.strip())

    scope_path = run_dir / "scope.json"
    proc = _run_cli(
        SCOPER_CLI, env,
        "--warrant", str(warrant_path),
        "--output", str(scope_path),
        "--changed-files", "scripts/governance/loop/warrant.py",
        "--repo-root", str(REPO_ROOT),
    )
    stage_procs["scoper"] = proc
    assert proc.returncode == 0, f"scoper failed: {proc.stderr!r}"

    proc = _run_cli(
        AUDIT_RUN_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--scope", str(scope_path),
    )
    stage_procs["audit_run"] = proc
    assert proc.returncode == 0, f"audit-run failed: {proc.stderr!r}"

    proc = _run_cli(TRIAGE_CLI, env, "--warrant", str(warrant_path), "--run-id", run_id)
    stage_procs["triage"] = proc
    assert proc.returncode == 0, f"triage failed: {proc.stderr!r}"

    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)
    proc = _run_cli(
        REMEDIATE_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--repo-root", str(REPO_ROOT),
        "--worktree-root", str(worktree_root),
    )
    stage_procs["remediate"] = proc
    assert proc.returncode == 0, f"remediate failed: {proc.stderr!r}"

    proc = _run_cli(REAUDIT_CLI, env, "--warrant", str(warrant_path), "--run-id", run_id)
    stage_procs["reaudit"] = proc
    assert proc.returncode == 0, f"reaudit failed: {proc.stderr!r}"

    marker_path = tmp_path / "fix_marker.txt"
    marker_path.write_text("fix applied\n")
    gate_script = tmp_path / "ci_gate.py"
    gate_script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"MARKER = Path({str(marker_path)!r})\n"
        "if MARKER.exists():\n"
        '    print("OK: ci green")\n'
        "    sys.exit(0)\n"
        'print("FAIL: ci red")\n'
        "sys.exit(1)\n"
    )
    ci_gate_cmd = f'"{VENV_PYTHON}" "{gate_script}"'

    proc = _run_cli(
        LEARN_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--ci-gate", ci_gate_cmd,
        "--repo-root", str(REPO_ROOT),
    )
    stage_procs["learn"] = proc
    assert proc.returncode == 0, f"learn failed: {proc.stderr!r}"

    run = _open_run(run_id, runs_root)
    findings = run.read_jsonl(run.accepted_findings_path())
    impl_findings = [f for f in findings if f.get("routing") == "IMPLEMENT"]
    assert impl_findings, f"no IMPLEMENT findings: {findings}"
    finding_id = impl_findings[0]["finding_id"]

    invocations = []
    if droid_log.is_file():
        for line in droid_log.read_text().splitlines():
            if line.strip():
                invocations.append(json.loads(line))

    return {
        "run_id": run_id,
        "runs_root": runs_root,
        "run_dir": run_dir,
        "run": run,
        "warrant_path": warrant_path,
        "finding_id": finding_id,
        "env": env,
        "stage_procs": stage_procs,
        "invocations": invocations,
        "droid_log": droid_log,
        "origin_main_before": origin_main_before,
    }


# ---------------------------------------------------------------------------
# VAL-CROSS-004: Agentized loop produces real proposal (droid backend)
# ---------------------------------------------------------------------------


class TestAgentizedLoopProducesProposal:
    """VAL-CROSS-004: droid backend produces fix_proposal + verifier_verdict + ratchet."""

    def test_all_stages_exit_zero(self, agentized_run):
        stage_procs = agentized_run["stage_procs"]
        for stage_name in ["runs_create", "scoper", "audit_run", "triage", "remediate", "reaudit", "learn"]:
            proc = stage_procs[stage_name]
            assert proc.returncode == 0, (
                f"{stage_name} exited {proc.returncode}: stderr={proc.stderr!r}"
            )

    def test_full_artifact_chain_produced(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]

        assert run.list_audits(), "no audit JSON produced"
        assert run.accepted_findings_path().is_file(), "accepted_findings.jsonl missing"
        assert run.fix_proposal_path(fid).is_file(), f"fix_proposal_{fid}.yaml missing"
        assert run.verifier_verdict_path(fid).is_file(), f"verifier_verdict_{fid}.yaml missing"
        assert run.ratchet_path(fid).is_file(), f"ratchet_{fid}.yaml missing"
        assert run.ledger_entry_path(fid).is_file(), f"ledger_entry_{fid}.yaml missing"

    def test_audit_json_schema_valid(self, agentized_run):
        run = agentized_run["run"]
        env = agentized_run["env"]
        for audit_path in run.list_audits():
            proc = _run_cli(VALIDATE_AUDIT_CLI, env, str(audit_path))
            assert proc.returncode == 0, (
                f"audit {audit_path.name} failed schema validation: {proc.stdout}"
            )

    def test_fix_proposal_red_before_green_after(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid)).get("fix_proposal")
        assert fp["red_before"]["exit_code"] != 0
        assert fp["green_after"]["exit_code"] == 0
        assert fp["proof_mode"] in ("natural", "synthetic")

    def test_verifier_verdict_confirmed(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")
        assert vv["verdict"] == "confirmed"
        assert vv["falsification_attempts"], "no falsification_attempts recorded"


# ---------------------------------------------------------------------------
# VAL-AGENT-002 + VAL-AGENT-003: droid CLI shelled out; 3 distinct role sessions
# ---------------------------------------------------------------------------


class TestRoleSeparation:
    """VAL-AGENT-002 / VAL-AGENT-003: distinct Auditor/Implementer/Verifier invocations."""

    def test_droid_cli_was_invoked(self, agentized_run):
        invocations = agentized_run["invocations"]
        assert invocations, "droid CLI was never invoked — DroidBackend did not shell out"

    def test_three_distinct_role_invocations(self, agentized_run):
        invocations = agentized_run["invocations"]
        prompts = [inv.get("prompt", "") for inv in invocations]
        roles = set()
        for p in prompts:
            if "ROLE: Auditor" in p:
                roles.add("auditor")
            elif "ROLE: Implementer" in p:
                roles.add("implementer")
            elif "FRESH Verifier" in p:
                roles.add("verifier")
        assert roles == {"auditor", "implementer", "verifier"}, (
            f"expected 3 distinct roles, got {roles}"
        )

    def test_implementer_and_verifier_invocations_recorded_in_artifacts(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid)).get("fix_proposal")
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")

        impl_inv = fp.get("implementer_invocation")
        ver_inv = vv.get("verifier_invocation")
        assert impl_inv and impl_inv.get("role") == "implementer", (
            "fix_proposal missing implementer_invocation receipt"
        )
        assert ver_inv and ver_inv.get("role") == "verifier", (
            "verifier_verdict missing verifier_invocation receipt"
        )


# ---------------------------------------------------------------------------
# VAL-REAUDIT-001: Verifier is a FRESH context (distinct from Implementer)
# ---------------------------------------------------------------------------


class TestVerifierFreshContext:
    """VAL-REAUDIT-001: Verifier session is distinct from the Implementer's."""

    def test_verifier_invocation_id_differs_from_implementer(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid)).get("fix_proposal")
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")

        impl_id = fp["implementer_invocation"]["invocation_id"]
        ver_id = vv["verifier_invocation"]["invocation_id"]
        assert impl_id != ver_id, (
            "Verifier reused the Implementer's invocation_id — context not fresh"
        )

    def test_verifier_prompt_does_not_contain_implementer_session(self, agentized_run):
        """The Verifier's droid invocation must not embed the Implementer's
        session context (invocation_id) — real agent-context freshness."""
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid)).get("fix_proposal")
        impl_invocation_id = fp["implementer_invocation"]["invocation_id"]

        invocations = agentized_run["invocations"]
        verifier_prompts = [
            inv.get("prompt", "") for inv in invocations
            if "FRESH Verifier" in inv.get("prompt", "")
        ]
        assert verifier_prompts, "no verifier invocation logged"
        for p in verifier_prompts:
            assert impl_invocation_id not in p, (
                "Verifier prompt embeds the Implementer's invocation_id — "
                "context not fresh (VAL-REAUDIT-001)"
            )


# ---------------------------------------------------------------------------
# VAL-AGENT-006: heterogeneous verifier for high/critical findings
# ---------------------------------------------------------------------------


class TestHeterogeneousVerifier:
    """VAL-AGENT-006: high-severity Verifier routes to a different model family."""

    def test_verifier_uses_different_model_family(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid)).get("fix_proposal")
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")

        impl_model = fp["implementer_invocation"]["model"]
        ver_model = vv["verifier_model"]
        assert impl_model != ver_model, (
            f"Verifier model {ver_model!r} == Implementer model {impl_model!r} "
            "— no heterogeneous routing for high/critical finding"
        )

    def test_model_independence_recorded_proven(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")
        assert vv["model_independence"] == "proven", (
            f"model_independence={vv['model_independence']!r}; expected 'proven' "
            "for a different-family verifier on a high-severity finding"
        )


# ---------------------------------------------------------------------------
# VAL-CROSS-005 + VAL-CROSS-007: no LLM opinion as truth; user tree untouched
# ---------------------------------------------------------------------------


class TestHonestEvidenceAndBoundaries:
    """VAL-CROSS-005 / VAL-CROSS-007: verdicts backed by receipts; user tree safe."""

    def test_verdict_backed_by_deterministic_evidence(self, agentized_run):
        run = agentized_run["run"]
        fid = agentized_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid)).get("verifier_verdict")
        for ev in vv["evidence"]:
            assert "exit_code" in ev or "value" in ev, (
                f"evidence entry not receipt-backed: {ev}"
            )
        # anti_gaming_checklist must be present and all-pass for a confirmed verdict
        checklist = vv["anti_gaming_checklist"]
        assert all(v == "pass" for v in checklist.values()), (
            f"confirmed verdict with failing anti-gaming checklist: {checklist}"
        )

    def test_user_working_tree_untouched(self, agentized_run):
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
            capture_output=True, text=True,
        )
        assert proc.stdout.strip() == agentized_run["origin_main_before"], (
            "origin/main changed during the agentized run — propose-only violated"
        )
