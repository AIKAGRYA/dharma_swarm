#!/usr/bin/env python3
"""Repo-grounding gate for the NĀGA-IR spec triple.

The baseline is encoded from the mission library's repo_grounding.md:
claims about local repo objects must either match origin/main facts or be
phrased as future/planned targets. Exit 0 means no blocking repo claims, 1
means contradictions were found, and 2 means the checker could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"

EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2
REPORT_SCHEMA_VERSION = "naga_repo_grounding_report.v1"

ABSENT_OBJECTS = (
    "packages/telos-kernel/",
    "titanium-verify",
    "dharma_swarm/reconciler.py",
    "dharma_swarm/sab/",
)
VERIFIED_TRUE_OBJECTS = (
    "scripts/governance/assurance_boundary.py",
    "dharma_swarm/coalgebra.py",
    "docs/telos-engine/01_SATTVA_VISION.md",
)

FUTURE_MARKERS = (
    "planned",
    "future",
    "later pr",
    "later ",
    "target",
    "may add",
    "may model",
    "deferred",
    "not implemented",
    "does not claim",
    "does not currently contain",
    "does not contain",
    "absent",
    "missing",
    "no ",
    "not ",
)

EXISTENCE_MARKERS = (
    "exists",
    "contains",
    "emits",
    "exports",
    "implements",
    "provides",
    "currently has",
    "already",
    "on main",
    "in this checkout",
)

ABSENCE_MARKERS = (
    "does not contain",
    "does not currently contain",
    "absent",
    "missing",
    "not present",
    "no ",
)


class BrokenCheck(RuntimeError):
    """The checker could not read the requested files."""


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    line: int
    detail: str

    def render(self, root: Path) -> str:
        location = self.path.relative_to(root).as_posix() if self.path.is_relative_to(root) else str(self.path)
        return f"{self.code} {location}:{self.line}: {self.detail}"


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("*.md")))
        else:
            paths.append(item)
    if not paths:
        paths = sorted(DEFAULT_SPEC_DIR.glob("*.md"))
    if not paths:
        raise BrokenCheck(f"no markdown files found under {DEFAULT_SPEC_DIR}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise BrokenCheck(f"missing spec file(s): {', '.join(missing)}")
    return paths


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def strip_code_spans(text: str) -> str:
    return re.sub(r"`([^`]*)`", r"\1", text)


def is_forward_or_absent_claim(lower: str) -> bool:
    return any(marker in lower for marker in FUTURE_MARKERS)


def asserts_existence(lower: str) -> bool:
    if is_forward_or_absent_claim(lower):
        return False
    return any(marker in lower for marker in EXISTENCE_MARKERS)


def asserts_absence(lower: str) -> bool:
    return any(marker in lower for marker in ABSENCE_MARKERS)


def has_same_line_negation(lower: str, term: str) -> bool:
    idx = lower.find(term.lower())
    if idx < 0:
        return False
    window = lower[max(0, idx - 40):idx]
    return any(marker in window for marker in ABSENCE_MARKERS)


def check_assurance_boundary(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    term = "scripts/governance/assurance_boundary.py"
    if term not in text:
        return
    if has_same_line_negation(lower, term):
        yield Finding(
            "NAGA-GROUND-ASSURANCE-ABSENT",
            path,
            line_no,
            "`scripts/governance/assurance_boundary.py` is VERIFIED-TRUE on origin/main, not absent",
        )


def check_bisimilar(path: Path, line_no: int, text: str) -> Iterator[Finding]:
    if "Bisimilar(" in text or "Bisimilar()" in text:
        yield Finding(
            "NAGA-GROUND-BISIMILAR",
            path,
            line_no,
            "`dharma_swarm/coalgebra.py` exposes lowercase function `bisimilar(...)`, not `Bisimilar()`",
        )


def check_absent_objects(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    for obj in ABSENT_OBJECTS:
        if obj.lower() not in lower:
            continue
        if asserts_existence(lower) and not has_same_line_negation(lower, obj):
            yield Finding(
                "NAGA-GROUND-ABSENT-OBJECT",
                path,
                line_no,
                f"`{obj}` is absent on origin/main; claim must be planned/future or non-existent",
            )


def check_verified_true_absence(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    for obj in VERIFIED_TRUE_OBJECTS:
        if obj == "scripts/governance/assurance_boundary.py":
            continue
        if obj.lower() in lower and has_same_line_negation(lower, obj):
            yield Finding(
                "NAGA-GROUND-TRUE-ABSENCE",
                path,
                line_no,
                f"`{obj}` is VERIFIED-TRUE on origin/main and cannot be claimed absent",
            )


def check_sab_receipts(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    mentions_sab_client = "sab_client.py" in lower or "sab client" in lower
    mentions_sab_shadow = "sab" in lower and "shadow" in lower and "export" in lower
    mentions_receipts = "receipt" in lower or "receipts" in lower
    mentions_packets_not_receipts = "not receipts" in lower or "packets" in lower
    if (mentions_sab_client or mentions_sab_shadow) and mentions_receipts:
        if not is_forward_or_absent_claim(lower) and not mentions_packets_not_receipts:
            yield Finding(
                "NAGA-GROUND-SAB-RECEIPTS",
                path,
                line_no,
                "`sab_client.py` shadow-exports SABContribution packets on main, not receipts",
            )


def check_coalgebra_line_count(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    if "dharma_swarm/coalgebra.py" not in lower:
        return
    match = re.search(r"(\d+)\s+lines", lower)
    if match and match.group(1) != "536":
        yield Finding(
            "NAGA-GROUND-COALGEBRA-LINES",
            path,
            line_no,
            "`dharma_swarm/coalgebra.py` is 536 lines on origin/main",
        )


def check_assurance_report_claim(path: Path, line_no: int, text: str, lower: str) -> Iterator[Finding]:
    if "assurance_boundary_report" in lower and "assurance_boundary_report.v1" not in lower:
        yield Finding(
            "NAGA-GROUND-ASSURANCE-SCHEMA",
            path,
            line_no,
            "assurance boundary report schema is `assurance_boundary_report.v1`",
        )
    if "ab-01" in lower and "ab-05" in lower and "ab-04" not in lower:
        yield Finding("NAGA-GROUND-AB-CONTRACTS", path, line_no, "AB contract span must include AB-01..AB-05")


def check_line(path: Path, line_no: int, line: str) -> list[Finding]:
    text = strip_code_spans(line)
    lower = text.lower()
    findings: list[Finding] = []
    for checker in (
        check_assurance_boundary,
        check_verified_true_absence,
        check_absent_objects,
        check_sab_receipts,
        check_coalgebra_line_count,
        check_assurance_report_claim,
    ):
        findings.extend(checker(path, line_no, text, lower))
    findings.extend(check_bisimilar(path, line_no, text))
    return findings


def check_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    in_fence = False
    for line_no, line in enumerate(read_lines(path), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        findings.extend(check_line(path, line_no, line))
    return findings


def run(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in spec_paths(paths):
        findings.extend(check_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NĀGA-IR repo claims against the origin/main grounding baseline.")
    parser.add_argument("paths", nargs="*", type=Path, help="spec files or directories; defaults to specs/naga_ir/*.md")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        findings = run(args.paths)
    except BrokenCheck as exc:
        print(f"naga-repo-grounding: BROKEN: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    if args.json:
        print(json.dumps({"schema_version": REPORT_SCHEMA_VERSION, "findings": [f.render(REPO_ROOT) for f in findings]}, indent=2))
    else:
        if not findings:
            print("naga-repo-grounding: clean")
        for finding in findings:
            print(finding.render(REPO_ROOT))
    return EXIT_VIOLATED if findings else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
