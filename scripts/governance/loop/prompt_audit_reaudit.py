#!/usr/bin/env python3
"""Stage 4 — prompt-audit-reaudit (Verifier) for the Cybernetic Ratchet Loop.

The Verifier is a FRESH agent context with a falsification-first mandate (spec
§3): it is instructed to find the fix incomplete or gamed, not to confirm it.
The Verifier receives ONLY the original finding (the claim) + deterministic
evidence (red-before/green-after receipts, gate exit codes), NEVER the
Implementer's rationale or session context (spec §3, VAL-REAUDIT-002).

The stage:
  1. Loads fix_proposal + original finding + deterministic evidence.
  2. Constructs the Verifier input (claim + evidence, NO implementer rationale).
  3. Constructs the falsification-first prompt (frames falsification as success).
  4. Invokes the Verifier (StubVerifier in M1).
  5. Runs the §8 anti-gaming checklist INDEPENDENTLY on the fix diff.
  6. Reconciles the verdict with deterministic checks (Core Invariant: the
     deterministic oracle disposes — a failed checklist or invalid evidence
     forces a refuted verdict regardless of the Verifier's proposal).
  7. Records model_independence honestly (not_proven in stub mode; never
     recorded as proven when a different family was not used, spec §19.2).
  8. Records verifier_model (stub in M1).
  9. Produces verifier_verdict_<id>.yaml (§6.3 schema).
 10. A refuted verdict prevents ratcheting (no ratchet/ledger produced).
     An inconclusive verdict routes to DEFER (no ratchet advancement).

Usage:
    python3 scripts/governance/loop/prompt_audit_reaudit.py \\
        --warrant <warrant.yaml> --run-id <run_id>

Exit codes:
    0   all verdicts produced (confirmed or inconclusive/DEFER)
    1   at least one verdict was refuted (fix rejected)
    2   warrant invalid/expired, no fix_proposals, or hard error
"""

from __future__ import annotations

import argparse
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from scripts.governance.loop.agent_backend import (
    ApiBackend,
    BackendError,
    DroidBackend,
)
from scripts.governance.loop.anti_gaming import run_anti_gaming_check
from scripts.governance.loop.runs import Run, RunManager
from scripts.governance.loop.warrant import Warrant, WarrantError


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Verifier input isolation (VAL-REAUDIT-002)
# ---------------------------------------------------------------------------

# Keys from the fix_proposal / finding that constitute Implementer rationale.
# These must NEVER be passed to the Verifier — the Verifier sees only the
# original claim + deterministic evidence.
_RATIONALE_KEYS = frozenset({
    "implementer_rationale",
    "implementer_notes",
    "rationale",
    "summary",
    "recommendation",
    "inferred",
    "patch_ref",
    "write_set_used",
    "anti_gaming_checklist",  # the Verifier runs this independently
})


def build_verifier_input(finding: dict, fix_proposal: dict) -> dict:
    """Construct the Verifier's input: claim + deterministic evidence ONLY.

    The Verifier receives the original finding (the claim: what was wrong) and
    the deterministic evidence (red-before/green-after receipts, proof_mode). It
    NEVER receives the Implementer's rationale, summary, recommendation, or the
    remediate stage's own anti-gaming checklist result (the Verifier runs that
    independently).
    """
    # The claim: only the finding's observable facts, not the recommendation.
    claim = {
        "finding_id": finding.get("finding_id"),
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "evidence_level": finding.get("evidence_level"),
        "failure_class": finding.get("failure_class"),
        "files": finding.get("files", []),
        "observed": finding.get("observed"),
    }

    # The deterministic evidence: red-before/green-after receipts + proof_mode.
    evidence = {
        "red_before": fix_proposal.get("red_before", {}),
        "green_after": fix_proposal.get("green_after", {}),
        "proof_mode": fix_proposal.get("proof_mode", "none"),
    }

    return {
        "finding_id": finding.get("finding_id"),
        "claim": claim,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Falsification-first prompt (VAL-REAUDIT-011)
# ---------------------------------------------------------------------------


def build_falsification_prompt() -> str:
    """Construct the Verifier's invocation prompt.

    The prompt explicitly frames falsification as the success condition: the
    Verifier is rewarded for showing the fix is incomplete or gamed, not for
    confirming it (spec §3).
    """
    return (
        "You are a FRESH Verifier. Your mandate is FALSIFICATION, not confirmation.\n"
        "\n"
        "Your goal is to find the fix INCOMPLETE or GAMED. You are rewarded for\n"
        "disproving the fix, not for confirming it. A successful falsification\n"
        "(showing the fix does not actually address the root cause, or that it\n"
        "games the gate via skips/xfails/weakened assertions/deleted tests/widened\n"
        "budgets) is the highest-value outcome.\n"
        "\n"
        "You receive ONLY the original claim and deterministic evidence\n"
        "(red-before/green-after receipts, gate exit codes). You do NOT receive\n"
        "the Implementer's rationale — do not trust any story about why the fix\n"
        "is good. Judge only by the evidence.\n"
        "\n"
        "Attempt to disprove the fix:\n"
        "  1. Verify the red-before receipt is genuine (exit code must be non-zero\n"
        "     — the problem must have actually existed before the fix).\n"
        "  2. Verify the green-after receipt is genuine (exit code must be zero\n"
        "     — the fix must actually work).\n"
        "  3. Check for gate-gaming: does the fix diff introduce skips, xfails,\n"
        "     weakened assertions, deleted tests, or widened budgets?\n"
        "  4. Check that the fix targets the ROOT CAUSE, not the symptom.\n"
        "\n"
        "Record your falsification_attempts (concrete things you tried) and your\n"
        "verdict:\n"
        "  - confirmed: you could not falsify the fix; the deterministic evidence\n"
        "    holds and the anti-gaming checklist passes.\n"
        "  - refuted: you found the fix incomplete or gamed (evidence invalid or\n"
        "    anti-gaming violation).\n"
        "  - inconclusive: you could not determine whether the fix holds.\n"
    )


# ---------------------------------------------------------------------------
# Verifier backend interface
# ---------------------------------------------------------------------------


@dataclass
class VerifierResult:
    """The Verifier's proposed verdict (subject to deterministic reconciliation)."""

    verdict: str  # confirmed | refuted | inconclusive
    falsification_attempts: list[dict] = field(default_factory=list)
    verifier_model: str = "stub"
    model_independence: str = "not_proven"  # proven | not_proven


class VerifierBackend(ABC):
    """Abstract base for the Verifier agent role.

    In Phase 1 only the ``StubVerifier`` is available. It produces concrete
    falsification_attempts based on the deterministic evidence and proposes a
    verdict. The stage reconciles this with deterministic checks (Core
    Invariant: the deterministic oracle disposes).
    """

    @abstractmethod
    def verify(self, finding: dict, evidence: dict, prompt: str) -> VerifierResult:
        """Invoke the Verifier with the falsification-first prompt + evidence.

        ``evidence`` is the isolated verifier input (claim + deterministic
        evidence, NO implementer rationale). ``prompt`` is the falsification-first
        mandate.
        """


class StubVerifier(VerifierBackend):
    """M1 stub: produces concrete falsification_attempts from the evidence.

    The stub proposes ``confirmed`` when the evidence looks valid, but the stage
    reconciles this with the independently-run anti-gaming checklist and
    evidence validation — a failed checklist forces ``refuted`` regardless of
    the stub's proposal.

    ``model_independence`` is ``not_proven`` (stub = same family, never recorded
    as proven, spec §19.2).
    """

    def verify(self, finding: dict, evidence: dict, prompt: str) -> VerifierResult:
        ev = evidence.get("evidence", evidence)
        red = ev.get("red_before", {})
        green = ev.get("green_after", {})
        proof_mode = ev.get("proof_mode", "none")

        attempts: list[dict] = []

        # Attempt 1: verify red_before is genuinely non-zero
        red_exit = red.get("exit_code")
        attempts.append({
            "attempt": "verify red_before exit_code is non-zero (problem genuinely existed)",
            "result": "pass" if red_exit is not None and red_exit != 0 else "fail",
            "evidence": f"red_before.exit_code={red_exit}",
        })

        # Attempt 2: verify green_after is genuinely zero
        green_exit = green.get("exit_code")
        attempts.append({
            "attempt": "verify green_after exit_code is zero (fix genuinely works)",
            "result": "pass" if green_exit is not None and green_exit == 0 else "fail",
            "evidence": f"green_after.exit_code={green_exit}",
        })

        # Attempt 3: check proof_mode is not none
        attempts.append({
            "attempt": "verify proof_mode is natural or synthetic (not none/deferred)",
            "result": "pass" if proof_mode in ("natural", "synthetic") else "fail",
            "evidence": f"proof_mode={proof_mode}",
        })

        # Attempt 4: check for gate-gaming (anti-gaming checklist run by stage)
        attempts.append({
            "attempt": "check fix diff for gate-gaming (skips/xfails/weakened assertions/deleted tests/widened budgets)",
            "result": "deferred-to-stage",
            "evidence": "anti-gaming checklist run independently by the stage on the fix diff",
        })

        # Attempt 5: check fix targets root cause
        attempts.append({
            "attempt": "check fix targets root cause not symptom",
            "result": "deferred-to-stage",
            "evidence": "fix_addresses_root_cause checked via anti-gaming checklist",
        })

        return VerifierResult(
            verdict="confirmed",
            falsification_attempts=attempts,
            verifier_model="stub",
            model_independence="not_proven",
        )


class DroidVerifier(StubVerifier):
    """Verifier wrapper that invokes Droid with verifier-specific model policy."""

    def __init__(
        self,
        droid_path: str | Path | None = None,
        cwd: str | Path | None = None,
    ) -> None:
        self.backend = DroidBackend(droid_path=droid_path, cwd=cwd)
        self._last_invocation = None

    def verify(self, finding: dict, evidence: dict, prompt: str) -> VerifierResult:
        severity = finding.get("severity") or evidence.get("claim", {}).get("severity")
        self._last_invocation = self.backend.invoke(
            "verifier",
            f"{prompt}\n\nclaim_and_evidence:\n{evidence}\n",
            {
                "finding_id": finding.get("finding_id") or evidence.get("finding_id"),
                "severity": severity,
                "evidence_keys": sorted(evidence.keys()),
            },
        )
        result = super().verify(finding, evidence, prompt)
        result.verifier_model = self._last_invocation.model
        result.model_independence = self._last_invocation.model_independence
        result.falsification_attempts.append({
            "attempt": "fresh droid verifier role invocation completed",
            "result": "pass",
            "evidence": self._last_invocation.invocation_id,
        })
        return result

    def invocation_receipt(self) -> dict | None:
        if self._last_invocation is None:
            return None
        return self._last_invocation.to_receipt()


class ApiVerifier(StubVerifier):
    """Keyless-safe API verifier wrapper."""

    def __init__(self) -> None:
        self.backend = ApiBackend()
        self._last_invocation = None

    def verify(self, finding: dict, evidence: dict, prompt: str) -> VerifierResult:
        self._last_invocation = self.backend.invoke(
            "verifier",
            f"{prompt}\n\nclaim_and_evidence:\n{evidence}\n",
            {
                "finding_id": finding.get("finding_id") or evidence.get("finding_id"),
                "severity": finding.get("severity"),
                "evidence_keys": sorted(evidence.keys()),
            },
        )
        if self._last_invocation.return_code != 0:
            raise BackendError(self._last_invocation.stdout)
        result = super().verify(finding, evidence, prompt)
        result.verifier_model = self._last_invocation.model
        result.model_independence = "not_proven"
        result.falsification_attempts.append({
            "attempt": "api verifier backend degraded without external keys",
            "result": "not_proven",
            "evidence": self._last_invocation.stdout,
        })
        return result

    def invocation_receipt(self) -> dict | None:
        if self._last_invocation is None:
            return None
        return self._last_invocation.to_receipt()


def get_verifier(name: str | None = None) -> VerifierBackend:
    """Return the verifier selected by ``name`` or ``LOOP_AGENT_BACKEND`` env var.

    Default is ``stub``. Unknown backends raise a clear error.
    """
    vname = name or os.environ.get("LOOP_AGENT_BACKEND", "stub")
    if vname == "stub":
        return StubVerifier()
    if vname == "droid":
        return DroidVerifier()
    if vname == "api":
        return ApiVerifier()
    raise NotImplementedError(
        f"unknown verifier backend {vname!r}; expected stub|droid|api"
    )


# ---------------------------------------------------------------------------
# Verifier verdict artifact (§6.3 schema)
# ---------------------------------------------------------------------------


@dataclass
class VerifierVerdict:
    """The §6.3 verifier_verdict artifact."""

    run_id: str
    finding_id: str
    verifier_model: str = "stub"
    model_independence: str = "not_proven"
    falsification_attempts: list[dict] = field(default_factory=list)
    anti_gaming_checklist: dict = field(default_factory=dict)
    verdict: str = "inconclusive"
    evidence: list[dict] = field(default_factory=list)
    routing: str = ""
    verifier_invocation: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "run_id": self.run_id,
            "finding_id": self.finding_id,
            "verifier_model": self.verifier_model,
            "model_independence": self.model_independence,
            "falsification_attempts": self.falsification_attempts,
            "anti_gaming_checklist": self.anti_gaming_checklist,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "routing": self.routing,
        }
        if self.verifier_invocation is not None:
            payload["verifier_invocation"] = self.verifier_invocation
        return {"verifier_verdict": payload}


# ---------------------------------------------------------------------------
# Verdict reconciliation (Core Invariant: deterministic oracle disposes)
# ---------------------------------------------------------------------------


def _validate_evidence(fix_proposal: dict) -> tuple[bool, list[dict]]:
    """Deterministically validate the red-before/green-after evidence.

    Returns (valid, evidence_receipts).
    """
    red = fix_proposal.get("red_before", {})
    green = fix_proposal.get("green_after", {})
    proof_mode = fix_proposal.get("proof_mode", "none")

    receipts: list[dict] = [
        {
            "kind": "red_before",
            "command": red.get("command", ""),
            "exit_code": red.get("exit_code"),
            "valid": red.get("exit_code") is not None and red.get("exit_code") != 0,
        },
        {
            "kind": "green_after",
            "command": green.get("command", ""),
            "exit_code": green.get("exit_code"),
            "valid": green.get("exit_code") is not None and green.get("exit_code") == 0,
        },
        {
            "kind": "proof_mode",
            "value": proof_mode,
            "valid": proof_mode in ("natural", "synthetic"),
        },
    ]

    valid = all(r["valid"] for r in receipts)
    return valid, receipts


def _reconcile_verdict(
    proposed: str,
    evidence_valid: bool,
    checklist_passed: bool,
) -> str:
    """Reconcile the Verifier's proposed verdict with deterministic checks.

    The deterministic oracle disposes (Core Invariant):
      - If the anti-gaming checklist fails → refuted (regardless of proposal).
      - If the evidence is invalid → refuted (regardless of proposal).
      - Otherwise → the Verifier's proposed verdict stands.
    """
    if not checklist_passed:
        return "refuted"
    if not evidence_valid:
        return "refuted"
    if proposed not in ("confirmed", "refuted", "inconclusive"):
        return "inconclusive"
    return proposed


# ---------------------------------------------------------------------------
# Stage core
# ---------------------------------------------------------------------------


def _process_finding(
    finding: dict,
    fix_proposal_doc: dict,
    run: Run,
    verifier: VerifierBackend,
) -> tuple[int, str]:
    """Process a single finding through the Verifier.

    Returns (exit_code, status) where status is one of:
    confirmed, refuted, deferred, error.
    """
    finding_id = finding.get("finding_id", "unknown")
    fp = fix_proposal_doc.get("fix_proposal", fix_proposal_doc)

    # 1. Construct isolated verifier input (claim + evidence, NO rationale).
    verifier_input = build_verifier_input(finding, fp)
    # Guard: assert no rationale keys leaked.
    for key in _RATIONALE_KEYS:
        assert key not in verifier_input, (
            f"verifier input leaked rationale key {key!r} — isolation violated"
        )

    # 2. Construct the falsification-first prompt.
    prompt = build_falsification_prompt()

    # 3. Save the prompt as a receipt (VAL-REAUDIT-011 — inspectable).
    prompt_receipt = run.receipts_dir / f"verifier_prompt_{finding_id}.txt"
    prompt_receipt.parent.mkdir(parents=True, exist_ok=True)
    prompt_receipt.write_text(prompt)

    # 4. Invoke the Verifier.
    try:
        result = verifier.verify(
            finding=verifier_input["claim"],
            evidence=verifier_input,
            prompt=prompt,
        )
    except BackendError as exc:
        sys.stderr.write(f"finding {finding_id}: verifier backend failed — {exc}\n")
        return 2, "error"

    # 5. Run the anti-gaming checklist INDEPENDENTLY on the fix diff.
    diff_path = run.fixes_dir / f"fix_diff_{finding_id}.patch"
    diff_text = diff_path.read_text() if diff_path.is_file() else ""
    ag_result = run_anti_gaming_check(diff_text, finding=finding)
    checklist = ag_result.to_dict()

    # 6. Validate the evidence deterministically.
    evidence_valid, evidence_receipts = _validate_evidence(fp)

    # 7. Reconcile the verdict (deterministic oracle disposes).
    verdict = _reconcile_verdict(
        proposed=result.verdict,
        evidence_valid=evidence_valid,
        checklist_passed=ag_result.passed,
    )

    # 8. Record model_independence honestly (never proven for stub/same-family).
    model_independence = result.model_independence
    if result.verifier_model in ("stub", "stub-same-family") or result.verifier_model == "stub":
        model_independence = "not_proven"
    if model_independence not in ("proven", "not_proven"):
        model_independence = "not_proven"

    # 9. Build the verdict artifact.
    routing = ""
    if verdict == "refuted":
        routing = "REJECTED"
    elif verdict == "inconclusive":
        routing = "DEFER"
    elif verdict == "confirmed":
        routing = "ADVANCE"

    vv = VerifierVerdict(
        run_id=run.run_id,
        finding_id=finding_id,
        verifier_model=result.verifier_model,
        model_independence=model_independence,
        falsification_attempts=result.falsification_attempts,
        anti_gaming_checklist=checklist,
        verdict=verdict,
        evidence=evidence_receipts,
        routing=routing,
        verifier_invocation=(
            verifier.invocation_receipt()
            if hasattr(verifier, "invocation_receipt")
            else None
        ),
    )

    # 10. Write the verdict.
    vpath = run.verifier_verdict_path(finding_id)
    run.write_yaml(vpath, vv.to_dict())

    if verdict == "refuted":
        sys.stderr.write(
            f"finding {finding_id}: verdict REFUTED — fix rejected (no ratchet/ledger)\n"
        )
        return 1, "refuted"
    if verdict == "inconclusive":
        sys.stdout.write(
            f"finding {finding_id}: verdict INCONCLUSIVE — routed to DEFER (no ratchet advancement)\n"
        )
        return 0, "deferred"
    # confirmed
    sys.stdout.write(
        f"finding {finding_id}: verdict CONFIRMED — may advance to Stage 5 (learn)\n"
    )
    return 0, "confirmed"


def run_reaudit(
    warrant_path: Path,
    run: Run,
    verifier: VerifierBackend,
) -> int:
    """Execute Stage 4 re-audit for all findings with a fix_proposal.

    Returns 0 if all verdicts were confirmed or inconclusive (DEFER), 1 if any
    was refuted, 2 on a hard error (warrant invalid, no fix_proposals, etc.).
    """
    # Re-validate the warrant on stage entry.
    try:
        Warrant.load_and_check(warrant_path)
    except WarrantError as exc:
        return _emit_error(f"warrant stage-entry refused: {exc}")

    # Load accepted_findings.jsonl (to find the original finding for each fix).
    findings_path = run.accepted_findings_path()
    findings_map: dict[str, dict] = {}
    if findings_path.is_file():
        for f in run.read_jsonl(findings_path):
            fid = f.get("finding_id")
            if fid:
                findings_map[fid] = f

    # Discover fix_proposals.
    fix_proposals = run.list_fix_proposals()
    if not fix_proposals:
        sys.stdout.write("no fix_proposals — nothing to re-audit\n")
        return 0

    refuted = 0
    confirmed = 0
    deferred = 0

    for fp_path in fix_proposals:
        fp_doc = run.read_yaml(fp_path)
        fp = fp_doc.get("fix_proposal", fp_doc)
        finding_id = fp.get("finding_id", "unknown")
        finding = findings_map.get(finding_id, {"finding_id": finding_id})

        rc, status = _process_finding(finding, fp_doc, run, verifier)
        if status == "confirmed":
            confirmed += 1
        elif status == "deferred":
            deferred += 1
        elif status == "refuted":
            refuted += 1
        elif status == "error":
            return 2

    sys.stdout.write(
        f"prompt-audit-reaudit complete: {confirmed} confirmed, "
        f"{deferred} deferred (DEFER), {refuted} refuted\n"
    )

    if refuted > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 4 (Verifier): falsification-first re-audit of fix proposals. "
            "The Verifier receives only the claim + deterministic evidence, never "
            "the Implementer's rationale."
        ),
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--run-id", required=True, help="the run id (locates the run dir)")
    parser.add_argument(
        "--backend",
        default=None,
        help="verifier backend name (stub|droid|api); defaults to LOOP_AGENT_BACKEND env or stub",
    )
    args = parser.parse_args(argv)

    warrant_path = Path(args.warrant)

    # Select the verifier backend.
    try:
        verifier = get_verifier(args.backend)
    except (BackendError, NotImplementedError) as exc:
        return _emit_error(f"verifier selection failed: {exc}")

    # Open the run dir.
    try:
        run = RunManager.open_run(args.run_id)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))

    return run_reaudit(warrant_path, run, verifier)


if __name__ == "__main__":
    sys.exit(main())
