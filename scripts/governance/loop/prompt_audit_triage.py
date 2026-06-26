#!/usr/bin/env python3
"""Stage 2 — prompt-audit-triage (deterministic) for the Cybernetic Ratchet Loop.

Reads all audit JSON from the run, applies the evidence/severity policy, dedupes
by ``failure_class`` (recurrence noted), scores recurrence against prior ledger
entries, routes ambiguous findings to NEEDS_HUMAN, and emits
``runs/<run_id>/accepted_findings.jsonl`` (one JSON per finding with routing +
recurrence_score).

Policy (spec §5):
  - E2+ (E2_tested, E3_cross_checked, E4_regression_proven) → IMPLEMENT
  - Below E2 (E0_none, E1_static) → DEFER (tracked issue)
  - Ambiguous (missing/empty failure_class, or low-confidence high-severity)
    → NEEDS_HUMAN (distinct from IMPLEMENT/DEFER)
  - Dedup by failure_class: one accepted per class, recurrence within the run
    noted on the surviving finding.
  - Recurrence: a failure_class seen in ≥2 prior runs (per the ledger)
    auto-escalates to ``must_gate=true``.

This stage is fully deterministic — no LLM is invoked. The warrant is
re-validated on stage entry (``Warrant.load_and_check``).

When all findings route to DEFER, the run completes cleanly (exit 0) and no
``fix_proposal_*`` artifacts are produced (Stage 3 is not invoked).

Usage:
    python3 scripts/governance/loop/prompt_audit_triage.py --warrant <yaml> --run-id <id>

Exit codes:
    0   triage complete (accepted_findings.jsonl written)
    2   warrant invalid/expired, no audit JSON found, or hard error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.governance.loop.runs import Run, RunManager
from scripts.governance.loop.warrant import Warrant, WarrantError

EVIDENCE_ORDER: dict[str, int] = {
    "E0_none": 0,
    "E1_static": 1,
    "E2_tested": 2,
    "E3_cross_checked": 3,
    "E4_regression_proven": 4,
}

E2_FLOOR: int = EVIDENCE_ORDER["E2_tested"]

SEVERITY_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

MUST_GATE_THRESHOLD: int = 2


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


# ---------------------------------------------------------------------------
# Routing policy (pure, deterministic, testable)
# ---------------------------------------------------------------------------


def route_finding(finding: dict) -> str:
    """Determine the routing for a single finding.

    Returns one of ``IMPLEMENT``, ``DEFER``, ``NEEDS_HUMAN``.

    - Missing/empty ``failure_class`` → NEEDS_HUMAN (cannot classify or dedupe).
    - ``severity`` high/critical with ``confidence`` low → NEEDS_HUMAN
      (high-stakes low-confidence ambiguity requiring human judgment).
    - ``evidence_level`` >= E2_tested → IMPLEMENT.
    - Below E2 → DEFER (tracked issue).
    """
    failure_class = (finding.get("failure_class") or "").strip()
    if not failure_class:
        return "NEEDS_HUMAN"

    severity = finding.get("severity", "low")
    confidence = finding.get("confidence", "medium")
    if severity in ("high", "critical") and confidence == "low":
        return "NEEDS_HUMAN"

    evidence = finding.get("evidence_level", "E0_none")
    ev_level = EVIDENCE_ORDER.get(evidence, 0)
    if ev_level >= E2_FLOOR:
        return "IMPLEMENT"
    return "DEFER"


# ---------------------------------------------------------------------------
# Recurrence scoring (reads prior ledger entries across all runs)
# ---------------------------------------------------------------------------


def _extract_finding_class(ledger_doc: dict) -> str | None:
    """Extract the finding_class from a ledger entry YAML dict (tolerant of layout)."""
    if not isinstance(ledger_doc, dict):
        return None
    entry = ledger_doc.get("ledger_entry")
    if isinstance(entry, dict) and entry.get("finding_class"):
        return str(entry["finding_class"])
    if ledger_doc.get("finding_class"):
        return str(ledger_doc["finding_class"])
    return None


def count_prior_recurrence(failure_class: str, current_run_id: str) -> int:
    """Count how many prior runs (excluding the current run) have a ledger entry
    with the given ``failure_class``.

    Scans all run week-buckets under the configured runs root. A run "counts"
    if at least one of its ledger entries references the same failure_class.
    """
    runs: list[Run] = []
    try:
        runs = RunManager.list_runs()
    except Exception:
        return 0

    count = 0
    for run in runs:
        if run.run_id == current_run_id:
            continue
        found = False
        for ledger_path in run.list_ledger_entries():
            if found:
                break
            try:
                doc = run.read_yaml(ledger_path)
            except Exception:
                continue
            fc = _extract_finding_class(doc)
            if fc is not None and fc == failure_class:
                found = True
        if found:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Dedup + triage core
# ---------------------------------------------------------------------------


def _finding_sort_key(finding: dict) -> tuple[int, int]:
    """Sort key: higher evidence_level first, then higher severity."""
    ev = EVIDENCE_ORDER.get(finding.get("evidence_level", "E0_none"), 0)
    sev = SEVERITY_ORDER.get(finding.get("severity", "low"), 0)
    return (ev, sev)


def triage_findings(
    all_findings: list[dict],
    current_run_id: str,
) -> list[dict]:
    """Apply the full triage policy to a flat list of findings from all audits.

    Returns a list of accepted-finding records (dicts) ready to be written as
    JSONL lines. Each record contains:
      finding_id, prompt_id, council_id, title, severity, evidence_level,
      failure_class, routing, must_gate, recurrence_score, recurrence_within_run,
      files, observed, recommendation, audit_path.
    """
    # Group by failure_class. Findings with an empty failure_class are NOT
    # deduped (each is ambiguous and routed to NEEDS_HUMAN individually).
    by_class: dict[str, list[dict]] = {}
    ambiguous: list[dict] = []
    for entry in all_findings:
        fc = (entry["finding"].get("failure_class") or "").strip()
        if not fc:
            ambiguous.append(entry)
        else:
            by_class.setdefault(fc, []).append(entry)

    accepted: list[dict] = []

    for fc, group in by_class.items():
        # Sort: highest evidence + severity first (the survivor).
        group.sort(key=lambda e: _finding_sort_key(e["finding"]), reverse=True)
        survivor = group[0]
        recurrence_within_run = len(group) > 1

        recurrence_score = count_prior_recurrence(fc, current_run_id)
        must_gate = recurrence_score >= MUST_GATE_THRESHOLD
        routing = route_finding(survivor["finding"])

        accepted.append(_build_record(survivor, routing, must_gate, recurrence_score, recurrence_within_run))

    for entry in ambiguous:
        recurrence_score = 0
        accepted.append(
            _build_record(entry, "NEEDS_HUMAN", False, recurrence_score, False)
        )

    return accepted


def _build_record(
    entry: dict,
    routing: str,
    must_gate: bool,
    recurrence_score: int,
    recurrence_within_run: bool,
) -> dict:
    finding = entry["finding"]
    return {
        "finding_id": finding.get("id", ""),
        "prompt_id": entry.get("prompt_id", ""),
        "council_id": entry.get("council_id", ""),
        "title": finding.get("title", ""),
        "severity": finding.get("severity", "low"),
        "evidence_level": finding.get("evidence_level", "E0_none"),
        "failure_class": (finding.get("failure_class") or "").strip(),
        "routing": routing,
        "must_gate": must_gate,
        "recurrence_score": recurrence_score,
        "recurrence_within_run": recurrence_within_run,
        "files": finding.get("files", []),
        "observed": finding.get("observed", ""),
        "recommendation": finding.get("recommendation", ""),
        "audit_path": entry.get("audit_path", ""),
    }


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------


def _load_all_findings(run: Run) -> list[dict]:
    """Read all audit JSON from the run dir and flatten into a list of
    (finding, prompt_id, council_id, audit_path) entries."""
    entries: list[dict] = []
    for audit_path in run.list_audits():
        try:
            doc = run.read_json(audit_path)
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"cannot read audit JSON {audit_path}: {exc}") from exc
        prompt_id = doc.get("prompt_id", audit_path.stem)
        council_id = doc.get("council_id", "")
        for finding in doc.get("findings", []):
            entries.append(
                {
                    "finding": finding,
                    "prompt_id": prompt_id,
                    "council_id": council_id,
                    "audit_path": str(audit_path.relative_to(run.run_dir)) if audit_path.is_relative_to(run.run_dir) else str(audit_path),
                }
            )
    return entries


def run_triage(warrant_path: Path, run: Run) -> int:
    """Execute Stage 2 triage for the given run.

    Returns 0 on success, 2 on hard error.
    """
    # Re-validate the warrant on stage entry.
    try:
        Warrant.load_and_check(warrant_path)
    except WarrantError as exc:
        return _emit_error(f"warrant stage-entry refused: {exc}")

    # Load all audit JSON from the run dir.
    try:
        all_entries = _load_all_findings(run)
    except ValueError as exc:
        return _emit_error(str(exc))

    audit_files = run.list_audits()
    if not audit_files:
        return _emit_error(
            f"no audit JSON found in {run.audit_dir} — run prompt-audit-run (Stage 1) first"
        )

    accepted = triage_findings(all_entries, run.run_id)

    # Write accepted_findings.jsonl.
    out_path = run.accepted_findings_path()
    run.write_jsonl(out_path, accepted)

    # Update the manifest with finding ids.
    for rec in accepted:
        run.add_finding(rec["finding_id"])

    # Report.
    impl = [r for r in accepted if r["routing"] == "IMPLEMENT"]
    deferred = [r for r in accepted if r["routing"] == "DEFER"]
    human = [r for r in accepted if r["routing"] == "NEEDS_HUMAN"]
    must_gate = [r for r in accepted if r["must_gate"]]

    sys.stdout.write(
        f"prompt-audit-triage complete: {len(accepted)} accepted findings "
        f"({len(impl)} IMPLEMENT, {len(deferred)} DEFER, {len(human)} NEEDS_HUMAN"
        + (f", {len(must_gate)} must_gate" if must_gate else "")
        + ")\n"
    )

    if not impl:
        sys.stdout.write(
            "no IMPLEMENT findings — all deferred; run complete (no remediate)\n"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 2 (deterministic triage): route audit findings to "
            "IMPLEMENT/DEFER/NEEDS_HUMAN and emit accepted_findings.jsonl."
        ),
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--run-id", required=True, help="the run id (locates the run dir)")
    args = parser.parse_args(argv)

    warrant_path = Path(args.warrant)

    try:
        run = RunManager.open_run(args.run_id)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))

    return run_triage(warrant_path, run)


if __name__ == "__main__":
    sys.exit(main())
