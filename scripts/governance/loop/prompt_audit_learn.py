#!/usr/bin/env python3
"""Stage 5 — prompt-audit-learn (Ratcheter) for the Cybernetic Ratchet Loop.

Deterministic + LLM-assisted. Loads confirmed verdicts + CI results (FORGE exit
codes via oracle). Only a green CI exit code advances (non-green = rejection
recorded + archived, no ratchet). Drives the EXISTING on-main ratchet engine
(``scripts/governance/hygiene/ratchet.py`` + ``promote.py``) — does NOT build a
parallel ratchet (VAL-LEARN-002, mission invariant #7).

On green + confirmed:
  - Produces ``ratchet_<id>.yaml`` (spec §6.4: root_cause, fix_patch_ref,
    new_gate with kind/location/proves/red_before_ref/green_after_ref,
    prevents_recurrence).
  - Writes one ``ledger_entry_<id>.yaml`` per gate (spec §6.5: timestamp_utc,
    commit, finding_class, status, gate_ref, receipt_ref, human_approver) under
    ``runs/<run_id>/ledger/``. Ledger entries are structured YAML,
    evidence-linked (receipt_ref -> replayable receipt), and labeled
    ``prior_claim`` (not ``ground_truth``) for fresh agents (spec §10.5).
  - Writes the CI receipt to ``runs/<run_id>/receipts/``.

No gate producible = DEFER (ratchet-or-nothing, spec §1). The
``wire_ci_gate`` connection (VAL-LEARN-010) is fulfilled in M3.

Usage:
    python3 scripts/governance/loop/prompt_audit_learn.py \\
        --warrant <warrant.yaml> --run-id <run_id> \\
        [--ci-gate "<command>"] [--repo-root <path>]

Exit codes:
    0   all findings processed (ratcheted or deferred)
    1   at least one finding was rejected (non-green CI)
    2   warrant invalid/expired, no confirmed verdicts, or hard error
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from scripts.governance.loop.oracle import CIOracle, GateResult
from scripts.governance.loop.runs import Run, RunManager
from scripts.governance.loop.wire_ci_gate import WorkflowError, wire_gate
from scripts.governance.loop.warrant import Warrant, WarrantError

DEFAULT_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
RATCHET_SCRIPT = "scripts/governance/hygiene/ratchet.py"
PROMOTE_SCRIPT = "scripts/governance/hygiene/promote.py"
DEFAULT_CI_WORKFLOW = ".github/workflows/loop-ratchet-gates.yml"


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


# ---------------------------------------------------------------------------
# Ratchet record (spec §6.4)
# ---------------------------------------------------------------------------


@dataclass
class RatchetRecord:
    """The §6.4 ratchet record (the unit of learning)."""

    run_id: str
    finding_id: str
    root_cause: str = ""
    fix_patch_ref: str = ""
    new_gate: dict = field(default_factory=dict)
    prevents_recurrence: bool = False
    prevents_recurrence_note: str = ""
    ci_receipt_ref: str = ""
    promote_deferral: str = ""

    def to_dict(self) -> dict:
        return {
            "ratchet": {
                "run_id": self.run_id,
                "finding_id": self.finding_id,
                "root_cause": self.root_cause,
                "fix_patch_ref": self.fix_patch_ref,
                "new_gate": self.new_gate,
                "prevents_recurrence": self.prevents_recurrence,
                "prevents_recurrence_note": self.prevents_recurrence_note,
                "ci_receipt_ref": self.ci_receipt_ref,
                "promote_deferral": self.promote_deferral,
            }
        }


# ---------------------------------------------------------------------------
# Ledger entry (spec §6.5)
# ---------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    """The §6.5 learning ledger entry (System Intelligence).

    Structured YAML (not prose), evidence-linked (receipt_ref -> replayable
    receipt), and labeled ``prior_claim`` (not ``ground_truth``) when fed to
    fresh agents (spec §10.5, VAL-LEARN-007).
    """

    timestamp_utc: str
    commit: str
    finding_class: str
    status: str  # gated | tracked_issue | settled_false_positive
    gate_ref: str = ""
    receipt_ref: str = ""
    human_approver: str = ""
    claim_label: str = "prior_claim"

    def to_dict(self) -> dict:
        return {
            "ledger_entry": {
                "timestamp_utc": self.timestamp_utc,
                "commit": self.commit,
                "finding_class": self.finding_class,
                "status": self.status,
                "gate_ref": self.gate_ref,
                "receipt_ref": self.receipt_ref,
                "human_approver": self.human_approver,
                "claim_label": self.claim_label,
            }
        }


# ---------------------------------------------------------------------------
# Gate producibility (ratchet-or-nothing, spec §1)
# ---------------------------------------------------------------------------


def _can_produce_gate(fix_proposal: dict) -> tuple[bool, str]:
    """Determine whether a new gate can be produced from the fix evidence.

    Returns (can_produce, reason). A gate is producible when:
      - proof_mode is natural or synthetic (not none)
      - red_before has a non-zero exit code
      - green_after has a zero exit code

    If not, the finding routes to DEFER (ratchet-or-nothing).
    """
    fp = fix_proposal.get("fix_proposal", fix_proposal)
    proof_mode = fp.get("proof_mode", "none")
    if proof_mode == "none":
        return False, "proof_mode=none — no red-before/green-after achievable"
    red = fp.get("red_before", {})
    green = fp.get("green_after", {})
    red_exit = red.get("exit_code")
    green_exit = green.get("exit_code")
    if red_exit is None or red_exit == 0:
        return False, f"red_before exit_code={red_exit} — no genuine red (problem must have existed)"
    if green_exit is None or green_exit != 0:
        return False, f"green_after exit_code={green_exit} — no genuine green (fix must work)"
    return True, ""


def _gate_kind(proof_mode: str) -> str:
    """Map proof_mode to new_gate.kind."""
    if proof_mode == "natural":
        return "regression_test"
    return "ci_gate"


def _build_new_gate(
    finding: dict,
    fix_proposal: dict,
    red_before_ref: str,
    green_after_ref: str,
) -> dict:
    """Construct the new_gate block (spec §6.4)."""
    fp = fix_proposal.get("fix_proposal", fix_proposal)
    proof_mode = fp.get("proof_mode", "synthetic")
    gate_command = fp.get("green_after", {}).get("command", "")
    failure_class = finding.get("failure_class", "UNKNOWN")

    return {
        "kind": _gate_kind(proof_mode),
        "location": gate_command,
        "proves": f"prevents reintroduction of {failure_class}",
        "red_before_ref": red_before_ref,
        "green_after_ref": green_after_ref,
    }


# ---------------------------------------------------------------------------
# CI gate + ratchet engine driving
# ---------------------------------------------------------------------------


def _run_ci_gate(oracle: CIOracle, command: str) -> GateResult:
    """Run the FORGE/CI gate via the oracle and return the result.

    The exit code IS the verdict (Core Invariant). Green = exit 0; non-green =
    rejection (VAL-LEARN-001).
    """
    return oracle.run_gate(command)


def _drive_ratchet_engine(oracle: CIOracle, repo_root: Path) -> dict:
    """Drive the EXISTING on-main ratchet engine (VAL-LEARN-002).

    Runs ``hygiene/ratchet.py --json`` via the oracle to capture the ratchet
    engine's state as evidence. This does NOT build a parallel ratchet — it
    invokes the existing engine and records its output as a receipt.

    The ratchet engine may exit 2 (BROKEN — e.g. baselines file missing). This
    is recorded honestly as evidence; it does not block the finding from being
    ratcheted (the CI gate being green is the advance condition, VAL-LEARN-001).
    """
    command = f'"{oracle.python}" {RATCHET_SCRIPT} --json'
    result = oracle.run_gate(command, cwd=str(repo_root))
    return {
        "engine": "hygiene/ratchet.py",
        "exit_code": result.exit_code,
        "command": result.command,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:1000],
        "verdict": result.verdict,
        "driven_at_utc": _utc_now_iso(),
    }


def _assess_prevents_recurrence(
    run: Run,
    red_before_ref: str,
    green_after_ref: str,
) -> tuple[bool, str]:
    """Honestly assess whether the new_gate prevents recurrence (VAL-LEARN-008).

    Returns (prevents_recurrence, note). True only when the new_gate has a real
    red_before_ref receipt proving the slop class existed (non-zero exit) AND a
    green_after_ref receipt proving the gate passes after the fix (zero exit).
    False (with a note) otherwise — never hardcoded True.
    """
    red_path = run.run_dir / red_before_ref
    if not red_path.is_file():
        return False, f"red_before_ref receipt not found: {red_before_ref}"
    green_path = run.run_dir / green_after_ref
    if not green_path.is_file():
        return False, f"green_after_ref receipt not found: {green_after_ref}"

    import json

    red_receipt = json.loads(red_path.read_text())
    green_receipt = json.loads(green_path.read_text())

    red_exit = red_receipt.get("exit_code")
    if red_exit is None or red_exit == 0:
        return False, f"red_before_ref receipt exit_code={red_exit} — no genuine red (slop must have existed)"

    green_exit = green_receipt.get("exit_code")
    if green_exit is None or green_exit != 0:
        return False, f"green_after_ref receipt exit_code={green_exit} — no genuine green (gate must pass after fix)"

    return True, "red_before_ref shows non-zero (slop existed), green_after_ref shows zero (gate passes after fix)"


def _promote_deferral_note(finding: dict, fix_proposal: dict) -> str:
    """Document concretely why promote.py is deferred for this finding (VAL-LEARN-002).

    promote.py moves a hygiene pattern through the lifecycle (advisory -> enforced).
    In M1 stub mode the finding is synthetic — there is no real hygiene pattern
    in ``docs/governance/hygiene/patterns/`` to promote. An advisory->enforced
    promotion is therefore not warranted. The ratchet engine (ratchet.py) IS
    driven via subprocess (see ``_drive_ratchet_engine``); promote.py is deferred
    until a real hygiene pattern exists to promote.
    """
    failure_class = finding.get("failure_class", "UNKNOWN")
    return (
        f"promote.py deferred: no real hygiene pattern for {failure_class} in "
        f"docs/governance/hygiene/patterns/ (M1 stub mode — synthetic finding). "
        f"ratchet.py was driven via subprocess for a state receipt; "
        f"promote.py (advisory->enforced promotion) is not warranted until a "
        f"real pattern exists. PROMOTE_SCRIPT={PROMOTE_SCRIPT} available for "
        f"subprocess invocation when a promotion is warranted."
    )


# ---------------------------------------------------------------------------
# Receipt + record writers
# ---------------------------------------------------------------------------


def _relative_ref(run: Run, path: Path) -> str:
    """Return a path relative to the run dir for use as a receipt_ref."""
    try:
        return str(path.relative_to(run.run_dir))
    except ValueError:
        return str(path)


def _write_ci_receipt(run: Run, finding_id: str, result: GateResult) -> str:
    """Write the CI gate result as a receipt and return the relative ref."""
    receipt = result.to_dict()
    receipt["kind"] = "ci_gate"
    receipt["finding_id"] = finding_id
    receipt["timestamp_utc"] = _utc_now_iso()
    path = run.receipt_path(f"ci_receipt_{finding_id}.json")
    run.write_json(path, receipt)
    return _relative_ref(run, path)


def _write_ratchet_engine_receipt(run: Run, finding_id: str, receipt: dict) -> str:
    """Write the ratchet engine invocation result as a receipt."""
    path = run.receipt_path(f"ratchet_engine_receipt_{finding_id}.json")
    run.write_json(path, receipt)
    return _relative_ref(run, path)


def _write_red_before_receipt(run: Run, finding_id: str, fix_proposal: dict) -> str:
    """Write the red_before evidence as a replayable receipt."""
    fp = fix_proposal.get("fix_proposal", fix_proposal)
    red = fp.get("red_before", {})
    receipt = {
        "kind": "red_before",
        "finding_id": finding_id,
        "command": red.get("command", ""),
        "exit_code": red.get("exit_code"),
        "key_output": red.get("key_output", ""),
        "valid": red.get("exit_code") is not None and red.get("exit_code") != 0,
        "timestamp_utc": _utc_now_iso(),
    }
    path = run.receipt_path(f"red_before_receipt_{finding_id}.json")
    run.write_json(path, receipt)
    return _relative_ref(run, path)


def _write_rejection_record(
    run: Run,
    finding_id: str,
    ci_result: GateResult,
    ci_receipt_ref: str,
) -> str:
    """Write a rejection record for a non-green CI finding (VAL-LEARN-012).

    Records the exit code + failing gate before archiving. The finding does not
    silently disappear (spec §5: REJECT record why).
    """
    record = {
        "rejection": {
            "finding_id": finding_id,
            "ci_exit_code": ci_result.exit_code,
            "ci_gate": ci_result.command,
            "ci_receipt_ref": ci_receipt_ref,
            "reason": f"non-green CI exit code {ci_result.exit_code} — finding not ratcheted",
            "stderr_excerpt": ci_result.stderr[:500],
            "timestamp_utc": _utc_now_iso(),
        }
    }
    path = run.run_dir / f"rejection_{finding_id}.yaml"
    run.write_yaml(path, record)
    return _relative_ref(run, path)


def _write_defer_record(run: Run, finding_id: str, reason: str) -> str:
    """Write a DEFER record for a finding that cannot produce a gate."""
    record = {
        "defer": {
            "finding_id": finding_id,
            "reason": reason,
            "timestamp_utc": _utc_now_iso(),
        }
    }
    path = run.run_dir / f"defer_{finding_id}.yaml"
    run.write_yaml(path, record)
    return _relative_ref(run, path)


def _write_ci_wire_receipt(
    run: Run,
    finding_id: str,
    workflow_path: Path,
    gate_id: str,
    gate_name: str,
    gate_command: str,
    added: bool,
) -> str:
    receipt = {
        "kind": "ci_wire",
        "finding_id": finding_id,
        "workflow_path": str(workflow_path),
        "gate_id": gate_id,
        "gate_name": gate_name,
        "gate_command": gate_command,
        "added": added,
        "timestamp_utc": _utc_now_iso(),
    }
    path = run.receipt_path(f"ci_wire_receipt_{finding_id}.json")
    run.write_json(path, receipt)
    return _relative_ref(run, path)


# ---------------------------------------------------------------------------
# Stage core
# ---------------------------------------------------------------------------


def _process_finding(
    finding: dict,
    fix_proposal: dict,
    verdict_doc: dict,
    run: Run,
    oracle: CIOracle,
    repo_root: Path,
    ci_gate_command: str,
    wire_ci: bool = False,
    ci_workflow: Path | None = None,
) -> tuple[int, str]:
    """Process a single confirmed finding through the learn stage.

    Returns (exit_code, status) where status is one of:
    ratcheted, rejected, deferred, error.
    """
    finding_id = finding.get("finding_id", "unknown")
    fp = fix_proposal.get("fix_proposal", fix_proposal)
    failure_class = finding.get("failure_class", "UNKNOWN")

    # 1. Run the FORGE/CI gate via the oracle (exit code = verdict).
    ci_result = _run_ci_gate(oracle, ci_gate_command)

    # 2. Write the CI receipt (VAL-LEARN-011).
    ci_receipt_ref = _write_ci_receipt(run, finding_id, ci_result)

    # 3. Non-green CI = rejection (VAL-LEARN-001, VAL-LEARN-012).
    if not ci_result.passed:
        _write_rejection_record(run, finding_id, ci_result, ci_receipt_ref)
        sys.stderr.write(
            f"finding {finding_id}: CI REJECTED — exit code {ci_result.exit_code}. "
            f"Rejection recorded, no ratchet.\n"
        )
        return 1, "rejected"

    # 4. Green CI. Check gate producibility (ratchet-or-nothing).
    can_produce, reason = _can_produce_gate(fp)
    if not can_produce:
        _write_defer_record(run, finding_id, reason)
        sys.stdout.write(
            f"finding {finding_id}: DEFER — {reason} (ratchet-or-nothing)\n"
        )
        return 0, "deferred"

    # 5. Drive the existing ratchet engine (VAL-LEARN-002).
    ratchet_receipt = _drive_ratchet_engine(oracle, repo_root)
    ratchet_receipt_ref = _write_ratchet_engine_receipt(run, finding_id, ratchet_receipt)

    # 6. Write the red_before receipt (evidence-linked).
    red_before_ref = _write_red_before_receipt(run, finding_id, fp)

    # 7. Construct the new_gate (spec §6.4).
    new_gate = _build_new_gate(
        finding=finding,
        fix_proposal=fp,
        red_before_ref=red_before_ref,
        green_after_ref=ci_receipt_ref,
    )

    # 8. Honestly assess prevents_recurrence from receipt evidence (VAL-LEARN-008).
    prevents, prevents_note = _assess_prevents_recurrence(
        run, red_before_ref, ci_receipt_ref,
    )

    # 9. Document promote.py deferral concretely (VAL-LEARN-002).
    promote_note = _promote_deferral_note(finding, fp)

    # 10. Build the ratchet record (§6.4).
    root_cause = finding.get("observed", finding.get("title", ""))
    ratchet = RatchetRecord(
        run_id=run.run_id,
        finding_id=finding_id,
        root_cause=root_cause,
        fix_patch_ref=fp.get("patch_ref", ""),
        new_gate=new_gate,
        prevents_recurrence=prevents,
        prevents_recurrence_note=prevents_note,
        ci_receipt_ref=ci_receipt_ref,
        promote_deferral=promote_note,
    )
    ratchet_path = run.ratchet_path(finding_id)
    run.write_yaml(ratchet_path, ratchet.to_dict())

    # 11. Build the ledger entry (§6.5).
    commit = _git_commit(repo_root)
    ledger = LedgerEntry(
        timestamp_utc=_utc_now_iso(),
        commit=commit,
        finding_class=failure_class,
        status="gated",
        gate_ref=_relative_ref(run, ratchet_path),
        receipt_ref=ci_receipt_ref,
        human_approver="",
        claim_label="prior_claim",
    )
    ledger_path = run.ledger_entry_path(finding_id)
    run.write_yaml(ledger_path, ledger.to_dict())

    ci_wire_ref = ""
    if wire_ci:
        workflow_path = ci_workflow or (repo_root / DEFAULT_CI_WORKFLOW)
        gate_name = f"{finding_id}: {failure_class}"
        try:
            added = wire_gate(
                workflow_path,
                gate_id=finding_id,
                name=gate_name,
                command=new_gate["location"] or ci_gate_command,
            )
        except WorkflowError as exc:
            sys.stderr.write(f"finding {finding_id}: CI workflow wiring failed — {exc}\n")
            return 2, "error"
        ci_wire_ref = _write_ci_wire_receipt(
            run=run,
            finding_id=finding_id,
            workflow_path=workflow_path,
            gate_id=finding_id,
            gate_name=gate_name,
            gate_command=new_gate["location"] or ci_gate_command,
            added=added,
        )

    # 12. Update the run manifest.
    gate_manifest = {
        "finding_id": finding_id,
        "kind": new_gate["kind"],
        "location": new_gate["location"],
        "ratchet_ref": _relative_ref(run, ratchet_path),
        "ledger_ref": _relative_ref(run, ledger_path),
        "ci_receipt_ref": ci_receipt_ref,
        "ratchet_engine_receipt_ref": ratchet_receipt_ref,
    }
    if ci_wire_ref:
        gate_manifest["ci_wire_receipt_ref"] = ci_wire_ref
    run.add_gate(gate_manifest)

    sys.stdout.write(
        f"finding {finding_id}: RATCHETED — new gate ({new_gate['kind']}) at "
        f"{new_gate['location']}. Ratchet + ledger written.\n"
    )
    return 0, "ratcheted"


def run_learn(
    warrant_path: Path,
    run: Run,
    oracle: CIOracle,
    repo_root: Path,
    ci_gate_command: str | None = None,
    wire_ci: bool = False,
    ci_workflow: Path | None = None,
) -> int:
    """Execute Stage 5 (learn/ratchet) for all confirmed findings.

    Returns 0 if all findings were ratcheted or deferred, 1 if any was rejected
    (non-green CI), 2 on a hard error (warrant invalid, no confirmed verdicts).
    """
    # Re-validate the warrant on stage entry.
    try:
        Warrant.load_and_check(warrant_path)
    except WarrantError as exc:
        return _emit_error(f"warrant stage-entry refused: {exc}")

    # Load accepted_findings.jsonl (to find the original finding for each verdict).
    findings_path = run.accepted_findings_path()
    findings_map: dict[str, dict] = {}
    if findings_path.is_file():
        for f in run.read_jsonl(findings_path):
            fid = f.get("finding_id")
            if fid:
                findings_map[fid] = f

    # Discover verifier verdicts.
    verdicts = run.list_verifier_verdicts()
    if not verdicts:
        sys.stdout.write("no verifier verdicts — nothing to learn\n")
        return 0

    # Filter to confirmed verdicts (verdict=confirmed, routing=ADVANCE).
    confirmed: list[tuple[dict, dict, dict]] = []  # (verdict, finding, fix_proposal)
    for vpath in verdicts:
        vdoc = run.read_yaml(vpath)
        vv = vdoc.get("verifier_verdict", vdoc)
        if vv.get("verdict") != "confirmed":
            continue
        finding_id = vv.get("finding_id", "unknown")
        finding = findings_map.get(finding_id, {"finding_id": finding_id})
        fp_path = run.fix_proposal_path(finding_id)
        if not fp_path.is_file():
            sys.stderr.write(
                f"finding {finding_id}: confirmed but no fix_proposal — skipping\n"
            )
            continue
        fp_doc = run.read_yaml(fp_path)
        confirmed.append((vv, finding, fp_doc))

    if not confirmed:
        sys.stdout.write("no confirmed verdicts — nothing to learn\n")
        return 0

    rejected = 0
    ratcheted = 0
    deferred = 0

    for vv, finding, fp_doc in confirmed:
        finding_id = finding.get("finding_id", "unknown")
        fp = fp_doc.get("fix_proposal", fp_doc)

        # Determine the CI gate command: explicit arg > fix_proposal green_after.
        gate_cmd = ci_gate_command
        if gate_cmd is None:
            gate_cmd = fp.get("green_after", {}).get("command", "true")

        rc, status = _process_finding(
            finding, fp_doc, vv, run, oracle, repo_root, gate_cmd,
            wire_ci=wire_ci,
            ci_workflow=ci_workflow,
        )
        if status == "ratcheted":
            ratcheted += 1
        elif status == "deferred":
            deferred += 1
        elif status == "rejected":
            rejected += 1
        elif status == "error":
            return 2

    sys.stdout.write(
        f"prompt-audit-learn complete: {ratcheted} ratcheted, "
        f"{deferred} deferred (DEFER), {rejected} rejected (non-green CI)\n"
    )

    if rejected > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 5 (Ratcheter): ratchet confirmed findings into standing gates "
            "on green CI. Drives the existing hygiene/ratchet.py engine. "
            "No gate producible = DEFER (ratchet-or-nothing)."
        ),
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--run-id", required=True, help="the run id (locates the run dir)")
    parser.add_argument(
        "--ci-gate",
        default=None,
        help="CI gate command to run (exit code = verdict). Defaults to fix_proposal green_after.command.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="git repo root (default: mission worktree)",
    )
    parser.add_argument(
        "--wire-ci",
        action="store_true",
        help="wire ratcheted gates into loop-ratchet-gates.yml (Phase 3 path)",
    )
    parser.add_argument(
        "--ci-workflow",
        default=None,
        help=f"workflow path for --wire-ci (default: {DEFAULT_CI_WORKFLOW})",
    )
    args = parser.parse_args(argv)

    warrant_path = Path(args.warrant)
    repo_root = Path(args.repo_root)

    # Open the run dir.
    try:
        run = RunManager.open_run(args.run_id)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))

    # Create the oracle for gate runs.
    oracle = CIOracle(python=DEFAULT_PYTHON, repo_root=repo_root)

    ci_workflow = Path(args.ci_workflow) if args.ci_workflow else None
    return run_learn(
        warrant_path,
        run,
        oracle,
        repo_root,
        ci_gate_command=args.ci_gate,
        wire_ci=args.wire_ci,
        ci_workflow=ci_workflow,
    )


if __name__ == "__main__":
    sys.exit(main())
