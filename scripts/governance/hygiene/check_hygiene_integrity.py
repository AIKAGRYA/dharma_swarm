#!/usr/bin/env python3
"""Integrity checks for the governance hygiene catalogue.

Pattern files intentionally use JSON-compatible YAML so this gate stays
stdlib-only, matching the DocOps integrity checker.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
HYGIENE_ROOT = Path("docs/governance/hygiene")
PATTERN_DIR = HYGIENE_ROOT / "patterns"
ARCHIVE_DIR = HYGIENE_ROOT / "archive"
CATALOGUE = HYGIENE_ROOT / "CATALOGUE.md"
AUDIT_PROMPT = HYGIENE_ROOT / "AUDIT_PROMPT.md"

ID_RE = re.compile(r"^([A-Z]{2})-([A-Z])([0-9]+)$")
STAGES = {"observed", "measured", "advisory", "enforced", "resolved", "archived"}
DETECTOR_TYPES = {"command", "manual", "external"}
SEVERITIES = {
    "informational",
    "structural",
    "security",
    "correctness",
    "performance",
    "distributed",
    "operational",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "cluster",
    "cluster_title",
    "severity",
    "stage",
    "created",
    "last_verified",
    "next_review",
    "definition",
    "why_it_hurts",
    "detector",
    "enforcement",
    "sources",
    "audit_questions",
}
BLOCKED_COMMAND_RE = re.compile(
    r"\b(rm|mv|scp|ssh)\b|git\s+(add|reset|checkout|clean|commit|push|pull|merge|rebase|stash)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str

    def render(self) -> str:
        return f"{self.severity}: {self.message}"


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: expected JSON-compatible YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: top-level pattern payload must be an object")
    return payload


def pattern_paths(repo_root: Path = REPO_ROOT, include_archive: bool = True) -> list[Path]:
    roots = [repo_root / PATTERN_DIR]
    if include_archive:
        roots.append(repo_root / ARCHIVE_DIR)
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(sorted(root.glob("*.yaml")))
    return paths


def load_patterns(repo_root: Path = REPO_ROOT, include_archive: bool = True) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for path in pattern_paths(repo_root, include_archive=include_archive):
        pattern = load_json_yaml(path)
        pattern["_path"] = path.relative_to(repo_root).as_posix()
        patterns.append(pattern)
    return sorted(patterns, key=pattern_sort_key)


def pattern_sort_key(pattern: dict[str, Any]) -> tuple[str, str, int, str]:
    match = ID_RE.match(str(pattern.get("id", "")))
    if not match:
        return ("ZZ", "ZZ", 9999, str(pattern.get("id", "")))
    return (match.group(1), match.group(2), int(match.group(3)), str(pattern.get("id")))


def _date_or_none(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_pattern(pattern: dict[str, Any], seen: set[str], today: date) -> list[Finding]:
    findings: list[Finding] = []
    pattern_id = str(pattern.get("id", "<missing>"))
    rel_path = str(pattern.get("_path", "<unknown>"))

    missing = sorted(REQUIRED_FIELDS - set(pattern))
    if missing:
        findings.append(Finding("FAIL", f"{rel_path}: missing required fields: {', '.join(missing)}"))
        return findings

    match = ID_RE.match(pattern_id)
    if not match:
        findings.append(Finding("FAIL", f"{rel_path}: invalid id {pattern_id!r}; expected VC-A1 or AI-A1 style"))
    else:
        if pattern.get("cluster") != match.group(2):
            findings.append(Finding("FAIL", f"{rel_path}: cluster must match id prefix {match.group(2)}"))
        if Path(rel_path).stem != pattern_id:
            findings.append(Finding("FAIL", f"{rel_path}: file stem must match id {pattern_id}"))

    if pattern_id in seen:
        findings.append(Finding("FAIL", f"{rel_path}: duplicate pattern id {pattern_id}"))
    seen.add(pattern_id)

    stage = pattern.get("stage")
    if stage not in STAGES:
        findings.append(Finding("FAIL", f"{rel_path}: stage {stage!r} not in {sorted(STAGES)}"))
    if pattern.get("severity") not in SEVERITIES:
        findings.append(Finding("FAIL", f"{rel_path}: unsupported severity {pattern.get('severity')!r}"))

    for field in ("created", "last_verified", "next_review"):
        if _date_or_none(pattern.get(field)) is None:
            findings.append(Finding("FAIL", f"{rel_path}: {field} must be an ISO date"))
    next_review = _date_or_none(pattern.get("next_review"))
    if stage not in {"resolved", "archived"} and next_review and next_review < today:
        findings.append(Finding("WARN", f"{rel_path}: next_review {next_review.isoformat()} is stale"))

    detector = pattern.get("detector")
    if not isinstance(detector, dict):
        findings.append(Finding("FAIL", f"{rel_path}: detector must be an object"))
    else:
        detector_type = detector.get("type")
        if detector_type not in DETECTOR_TYPES:
            findings.append(Finding("FAIL", f"{rel_path}: detector.type must be one of {sorted(DETECTOR_TYPES)}"))
        if detector_type == "command":
            command = detector.get("command")
            if not isinstance(command, str) or not command.strip():
                findings.append(Finding("FAIL", f"{rel_path}: command detector needs detector.command"))
            elif BLOCKED_COMMAND_RE.search(command):
                findings.append(Finding("FAIL", f"{rel_path}: detector.command contains a blocked mutating command"))
        if detector_type == "manual" and not detector.get("rationale"):
            findings.append(Finding("FAIL", f"{rel_path}: manual detector needs detector.rationale"))
        if detector_type == "external" and not detector.get("command"):
            findings.append(Finding("FAIL", f"{rel_path}: external detector needs a command or tool reference"))

    enforcement = pattern.get("enforcement")
    if not isinstance(enforcement, dict):
        findings.append(Finding("FAIL", f"{rel_path}: enforcement must be an object"))
    elif stage == "enforced" and not enforcement.get("rule"):
        findings.append(Finding("FAIL", f"{rel_path}: enforced pattern needs enforcement.rule"))

    if stage == "archived" and not pattern.get("archived_reason"):
        findings.append(Finding("FAIL", f"{rel_path}: archived pattern needs archived_reason"))

    if not isinstance(pattern.get("sources"), list):
        findings.append(Finding("FAIL", f"{rel_path}: sources must be a list"))
    questions = pattern.get("audit_questions")
    if not isinstance(questions, list) or not questions:
        findings.append(Finding("FAIL", f"{rel_path}: audit_questions must be a non-empty list"))

    return findings


def active_patterns(patterns: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [pattern for pattern in patterns if pattern.get("stage") != "archived"]


def render_catalogue(patterns: list[dict[str, Any]]) -> str:
    lines = [
        "# Hygiene Catalogue",
        "",
        "Generated from `docs/governance/hygiene/patterns/*.yaml`.",
        "Do not edit this file by hand; run `make hygiene-check` to verify and",
        "`python3 scripts/governance/hygiene/audit_agent_prompt.py --write` to regenerate.",
        "",
        "| ID | Stage | Severity | Pattern | Detector | Enforcement |",
        "|---|---|---|---|---|---|",
    ]
    current_cluster = None
    for pattern in active_patterns(patterns):
        cluster = f"{pattern['cluster']} - {pattern['cluster_title']}"
        if cluster != current_cluster:
            lines.extend(["", f"## Cluster {cluster}", ""])
            current_cluster = cluster
        detector = pattern["detector"]
        detector_label = detector.get("type", "unknown")
        if detector.get("command"):
            detector_label = f"{detector_label} detector"
        if detector.get("target"):
            detector_label = f"{detector_label} ({detector['target']})"
        enforcement = pattern.get("enforcement", {}).get("rule") or "-"
        title = pattern["title"].replace("|", "/")
        lines.append(
            f"| `{pattern['id']}` | `{pattern['stage']}` | `{pattern['severity']}` | "
            f"{title} | {detector_label} | {enforcement} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_audit_prompt(patterns: list[dict[str, Any]]) -> str:
    lines = [
        "# Vibe-Code Audit Prompt",
        "",
        "Generated from `docs/governance/hygiene/patterns/*.yaml`.",
        "Use this as the anti-slop field checklist for a PR, module, or branch.",
        "",
        "Instructions:",
        "1. Start with `make onboard`, then run `make hygiene-audit`.",
        "2. For each relevant pattern below, cite file paths and concrete evidence.",
        "3. Do not promote a signal to a gate unless the lifecycle criteria in `LIFECYCLE.md` are met.",
        "",
    ]
    current_cluster = None
    for pattern in active_patterns(patterns):
        cluster = f"{pattern['cluster']} - {pattern['cluster_title']}"
        if cluster != current_cluster:
            lines.extend([f"## Cluster {cluster}", ""])
            current_cluster = cluster
        lines.append(f"### {pattern['id']} - {pattern['title']}")
        lines.append(pattern["definition"])
        lines.append("")
        lines.append("Audit questions:")
        for question in pattern["audit_questions"]:
            lines.append(f"- {question}")
        lines.append("")
    return "\n".join(lines)


def run_checks(repo_root: Path, today: date) -> list[Finding]:
    patterns = load_patterns(repo_root)
    findings: list[Finding] = []
    seen: set[str] = set()
    for pattern in patterns:
        findings.extend(validate_pattern(pattern, seen, today))

    expected_catalogue = render_catalogue(patterns)
    expected_prompt = render_audit_prompt(patterns)
    generated = [
        (repo_root / CATALOGUE, expected_catalogue),
        (repo_root / AUDIT_PROMPT, expected_prompt),
    ]
    for path, expected in generated:
        if not path.exists():
            findings.append(Finding("FAIL", f"{path.relative_to(repo_root)} is missing"))
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            findings.append(
                Finding(
                    "FAIL",
                    f"{path.relative_to(repo_root)} is out of sync; run "
                    "python3 scripts/governance/hygiene/audit_agent_prompt.py --write",
                )
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args(argv)

    today = date.fromisoformat(args.today)
    findings = run_checks(args.repo_root.resolve(), today)
    for finding in findings:
        print(finding.render())
    failures = [finding for finding in findings if finding.severity == "FAIL"]
    if failures:
        return 1
    print("Hygiene integrity OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
