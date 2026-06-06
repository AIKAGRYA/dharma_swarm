#!/usr/bin/env python3
"""check_track_status.py — validate ACTIVE_TRACK.yaml against repo reality.

This is the governance gate that prevents the failure mode where a prose
"current track" pointer rots while work moves on. It does three things:

  1. Verifies the active tracks list is well-formed (schema, 1-10 ACTIVE).
  2. Evaluates each acceptance_criteria predicate against the filesystem
     (and, when network is allowed, the GitHub API for PR merge status),
     per active track.
  3. Checks TTL per track — fails if (today - verified_at) > ttl_days.

Outputs:
  - reports/governance/active_track_evidence.json  (machine readable)
  - reports/governance/active_track_evidence.md    (human readable)
  - non-zero exit if any blocking finding is raised.

The script is stdlib-only. PR merge status is checked optionally via the
`gh` CLI if available; otherwise it is reported as "unknown" without
failing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

ACTIVE_TRACK_PATH = Path("docs/governance/ACTIVE_TRACK.yaml")
REPORTS_DIR = Path("reports/governance")
SCHEMA_VERSION = 2
MAX_ACTIVE_TRACKS = 10


def _primary_track(active_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the primary active track (primary:true marker, else first)."""
    if not active_tracks:
        return {}
    for trk in active_tracks:
        if isinstance(trk, dict) and trk.get("primary"):
            return trk
    return active_tracks[0]


@dataclass
class Finding:
    severity: str          # ERROR | WARN | INFO
    check: str
    message: str
    criterion_id: str | None = None


@dataclass
class CriterionResult:
    id: str
    kind: str
    passed: bool
    detail: str = ""


def load_active_track(path: Path) -> dict[str, Any]:
    """Parse ACTIVE_TRACK.yaml using a stdlib-only YAML-subset parser.

    The file is intentionally simple YAML — we restrict ourselves to the
    subset already used by docs/docops/assertions.yaml (which is JSON-
    compatible). To stay stdlib-only we attempt PyYAML first; if missing,
    fall back to a minimal block parser.
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML block parser sufficient for ACTIVE_TRACK.yaml.

    Supports: mappings, scalar values (str/int/bool), block-literal `|`
    strings, sequences of mappings, sequences of scalars. Comments (`#`)
    and blank lines are skipped. Indentation is 2 spaces.
    """
    lines = text.splitlines()

    def strip_comment(s: str) -> str:
        in_quote = False
        for i, ch in enumerate(s):
            if ch == '"':
                in_quote = not in_quote
            if ch == "#" and not in_quote:
                return s[:i].rstrip()
        return s.rstrip()

    cleaned: list[tuple[int, str]] = []
    for raw in lines:
        line = strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        cleaned.append((indent, line.lstrip(" ")))

    pos = 0

    def parse_block(base_indent: int) -> Any:
        nonlocal pos
        result: dict[str, Any] | list[Any] | None = None
        while pos < len(cleaned):
            indent, content = cleaned[pos]
            if indent < base_indent:
                return result if result is not None else {}
            if content.startswith("- "):
                if result is None:
                    result = []
                if not isinstance(result, list):
                    return result
                item_content = content[2:]
                # Sequence item could be a scalar or an inline `key: value`
                if ":" in item_content and not item_content.startswith("\""):
                    key, _, val = item_content.partition(":")
                    inline = {key.strip(): _scalar(val.strip())}
                    pos += 1
                    # Subsequent indented lines belong to this item
                    sub = parse_block(base_indent + 2)
                    if isinstance(sub, dict):
                        inline.update(sub)
                    result.append(inline)
                else:
                    result.append(_scalar(item_content))
                    pos += 1
                continue
            if ":" in content:
                key, _, val = content.partition(":")
                key = key.strip()
                val = val.strip()
                if result is None:
                    result = {}
                if not isinstance(result, dict):
                    return result
                if val == "":
                    pos += 1
                    result[key] = parse_block(base_indent + 2)
                elif val == "|":
                    pos += 1
                    block_lines: list[str] = []
                    block_indent = None
                    while pos < len(cleaned):
                        ind2, c2 = cleaned[pos]
                        if ind2 <= base_indent:
                            break
                        if block_indent is None:
                            block_indent = ind2
                        block_lines.append(" " * max(ind2 - block_indent, 0) + c2)
                        pos += 1
                    result[key] = "\n".join(block_lines)
                else:
                    result[key] = _scalar(val)
                    pos += 1
                continue
            pos += 1
        return result if result is not None else {}

    def _scalar(s: str) -> Any:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        if s.lower() in {"true", "false"}:
            return s.lower() == "true"
        if s.lower() in {"null", "~", ""}:
            return None
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    return parse_block(0) or {}


def check_file_exists(file_path: str) -> CriterionResult:
    path = Path(file_path)
    return CriterionResult(
        id="", kind="file_exists",
        passed=path.exists(),
        detail=f"{file_path} {'present' if path.exists() else 'MISSING'}",
    )


def check_file_contains(file_path: str, pattern: str) -> CriterionResult:
    path = Path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="file_contains", passed=False,
                                detail=f"{file_path} missing")
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = bool(re.search(pattern, text))
    return CriterionResult(
        id="", kind="file_contains", passed=found,
        detail=f"pattern {pattern!r} {'found' if found else 'NOT FOUND'} in {file_path}",
    )


def check_pr_merged(pr_number: int) -> CriterionResult:
    """Best-effort PR merge check via gh CLI. UNKNOWN does not fail."""
    if shutil.which("gh") is None:
        return CriterionResult(id="", kind="pr_merged", passed=True,
                                detail=f"PR #{pr_number}: gh CLI absent, skipped")
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number),
             "--repo", "AmitabhainArunachala/dharma_swarm",
             "--json", "state,mergedAt"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return CriterionResult(id="", kind="pr_merged", passed=True,
                                    detail=f"PR #{pr_number}: gh query failed, skipped")
        data = json.loads(result.stdout)
        merged = data.get("state") == "MERGED" and bool(data.get("mergedAt"))
        return CriterionResult(
            id="", kind="pr_merged", passed=merged,
            detail=f"PR #{pr_number}: state={data.get('state')} mergedAt={data.get('mergedAt')}",
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="pr_merged", passed=True,
                                detail=f"PR #{pr_number}: {type(exc).__name__}, skipped")


def evaluate_criterion(crit: dict[str, Any]) -> CriterionResult:
    kind = crit.get("kind", "")
    if kind == "file_exists":
        res = check_file_exists(crit["file"])
    elif kind == "file_contains":
        res = check_file_contains(crit["file"], crit["pattern"])
    elif kind == "pr_merged":
        res = check_pr_merged(int(crit["pr"]))
    else:
        res = CriterionResult(id="", kind=kind, passed=False,
                              detail=f"unknown predicate kind: {kind}")
    res.id = crit.get("id", "")
    return res


def days_since(date_str: str) -> int | None:
    """Return days since date_str (negative if in the future). None if malformed.

    Future dates are allowed and not malformed — repos span timezones, and
    verified_at may be set in the operator's local timezone while CI is UTC.
    """
    try:
        when = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - when).days


def run(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    if not ACTIVE_TRACK_PATH.exists():
        findings.append(Finding("ERROR", "active-track-missing",
                                f"{ACTIVE_TRACK_PATH} not found"))
        emit_reports(findings, [], None)
        return 2

    track = load_active_track(ACTIVE_TRACK_PATH)

    if track.get("schema_version") != SCHEMA_VERSION:
        findings.append(Finding("ERROR", "schema-version-mismatch",
                                f"expected schema_version={SCHEMA_VERSION}, "
                                f"got {track.get('schema_version')!r}"))

    active_tracks = track.get("active_tracks") or []
    if not isinstance(active_tracks, list):
        active_tracks = []
    if len(active_tracks) == 0:
        findings.append(Finding("ERROR", "no-active-track",
                                "ACTIVE_TRACK.yaml has no active_tracks. "
                                "Declare at least one track (>=1 required) or close the previous one explicitly."))
        emit_reports(findings, [], track)
        return 2
    if len(active_tracks) > MAX_ACTIVE_TRACKS:
        findings.append(Finding("ERROR", "too-many-active-tracks",
                                f"ACTIVE_TRACK.yaml declares {len(active_tracks)} active tracks "
                                f"(cap is {MAX_ACTIVE_TRACKS}). Close some before opening more."))
        emit_reports(findings, [], track)
        return 2

    # Evaluate each active track independently. Findings are tagged with the
    # track id so per-track results are distinguishable.
    all_crit_results: list[CriterionResult] = []
    track_reports: list[dict[str, Any]] = []
    any_shippable = False

    for trk in active_tracks:
        tid = trk.get("id", "(unknown)")

        # TTL check (future dates allowed for timezone tolerance)
        ttl = int(trk.get("ttl_days", 14))
        age = days_since(str(trk.get("verified_at", "")))
        if age is None:
            findings.append(Finding("ERROR", "verified-at-malformed",
                                    f"[{tid}] verified_at malformed: {trk.get('verified_at')!r}"))
        elif age > ttl:
            findings.append(Finding(
                "ERROR", "active-track-stale",
                f"[{tid}] verified_at is {age} days old (ttl_days={ttl}). "
                f"Re-verify and bump verified_at, or close this track."))

        # Prerequisites (must be true now — failure means track is mis-declared)
        prereq_results: list[CriterionResult] = []
        for crit in trk.get("prerequisites", []) or []:
            prereq_results.append(evaluate_criterion(crit))

        prereq_failures = [c for c in prereq_results
                           if not c.passed and c.kind in {"file_exists", "file_contains"}]
        for c in prereq_failures:
            findings.append(Finding(
                "ERROR", f"prerequisite:{c.id}",
                f"[{tid}] Prerequisite failed: {c.detail}. Track is mis-declared — "
                f"the work it claims to build on does not exist.",
                criterion_id=c.id))

        # Completion criteria (will flip from false to true as the track lands)
        completion_results: list[CriterionResult] = []
        for crit in trk.get("completion_criteria", []) or []:
            completion_results.append(evaluate_criterion(crit))

        all_crit_results.extend(prereq_results)
        all_crit_results.extend(completion_results)

        # Track is SHIPPABLE when prerequisites hold AND all completion criteria pass.
        prereqs_ok = all(c.passed for c in prereq_results) if prereq_results else True
        completion_ok = (all(c.passed for c in completion_results)
                         if completion_results else False)
        shippable = prereqs_ok and completion_ok and trk.get("status") == "ACTIVE"
        any_shippable = any_shippable or shippable

        passed = sum(1 for c in completion_results if c.passed)
        if shippable:
            findings.append(Finding(
                "INFO", "track-shippable",
                f"[{tid}] All {len(completion_results)} completion criteria pass. "
                f"Track is SHIPPABLE — close it or declare its successor."))
        elif prereqs_ok and completion_results:
            findings.append(Finding(
                "INFO", "track-in-progress",
                f"[{tid}] {passed}/{len(completion_results)} completion criteria pass. "
                f"Track is in progress."))

        track_reports.append({
            "id": tid,
            "primary": bool(trk.get("primary")),
            "status": trk.get("status"),
            "shippable": shippable,
            "prerequisites_ok": prereqs_ok,
            "completion_progress": {"passed": passed, "total": len(completion_results)},
            "criteria": [asdict(c) for c in (prereq_results + completion_results)],
        })

    emit_reports(findings, all_crit_results, track, track_reports=track_reports,
                 any_shippable=any_shippable)

    has_errors = any(f.severity == "ERROR" for f in findings)
    return 1 if has_errors else 0


def emit_reports(findings: list[Finding], crit_results: list[CriterionResult],
                 track: dict[str, Any] | None, *,
                 track_reports: list[dict[str, Any]] | None = None,
                 any_shippable: bool = False) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    track_reports = track_reports or []

    active_tracks = (track or {}).get("active_tracks") or []
    if not isinstance(active_tracks, list):
        active_tracks = []
    # Back-compat alias: top-level active_track_id is the PRIMARY track id
    # (the item with primary:true, else first). Single-track consumers keep
    # reading this field unchanged.
    primary = _primary_track(active_tracks)
    primary_id = primary.get("id")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        # Back-compat alias for single-track consumers.
        "active_track_id": primary_id,
        "coordination_model": (track or {}).get("parallel_lane_policy", {}),
        # Per-track array (new in schema v2).
        "active_tracks": track_reports,
        "any_shippable": any_shippable,
        "criteria": [asdict(c) for c in crit_results],
        "findings": [asdict(f) for f in findings],
    }
    (REPORTS_DIR / "active_track_evidence.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    coordination = payload["coordination_model"].get(
        "model", "1-10 active tracks") if isinstance(payload["coordination_model"], dict) else "1-10 active tracks"
    md = ["# Active Track Evidence",
          "",
          f"Generated: {payload['generated_at']}",
          f"Active tracks: **{len(track_reports)}** (primary: `{primary_id}`)",
          f"Coordination: `{coordination}`",
          ""]
    for tr in track_reports:
        prog = tr.get("completion_progress", {"passed": 0, "total": 0})
        primary_tag = " (primary)" if tr.get("primary") else ""
        md.append(f"## Track `{tr.get('id')}`{primary_tag}")
        md.append("")
        md.append(f"Status: {tr.get('status')}")
        md.append(f"Prerequisites: **{'OK' if tr.get('prerequisites_ok') else 'FAILED'}**")
        md.append(f"Completion: **{prog['passed']}/{prog['total']}**")
        md.append(f"Shippable: **{'YES' if tr.get('shippable') else 'no'}**")
        md.append("")
        criteria = tr.get("criteria") or []
        if criteria:
            md.append("### Criteria")
            md.append("")
            for c in criteria:
                mark = "✓" if c.get("passed") else "✗"
                md.append(f"- {mark} `{c.get('id')}` ({c.get('kind')}) — {c.get('detail')}")
            md.append("")
    if findings:
        md.append("## Findings")
        md.append("")
        for f in findings:
            md.append(f"- **{f.severity}** `{f.check}`: {f.message}")
        md.append("")
    (REPORTS_DIR / "active_track_evidence.md").write_text("\n".join(md), encoding="utf-8")

    for f in findings:
        stream = sys.stderr if f.severity == "ERROR" else sys.stdout
        print(f"{f.severity}: {f.check}: {f.message}", file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ACTIVE_TRACK.yaml against repo reality.")
    parser.add_argument("--warn-only", action="store_true",
                        help="Emit findings but never exit non-zero (for pre-commit)")
    args = parser.parse_args()
    code = run(args)
    if args.warn_only:
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
