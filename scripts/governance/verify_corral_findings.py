#!/usr/bin/env python3
"""Verify the staleness of findings in ``DE_BUG_CORRAL/``.

Bug-corral findings cite specific files and line numbers as evidence. The
corral is a snapshot; main moves. Before a corral PR (e.g. #592) merges, the
findings should be re-confirmed against the current working tree so we do not
import already-fixed claims as live debt.

This script parses each ``### SEVERITY · ID · TITLE`` block in
``DE_BUG_CORRAL/01.md`` and ``DE_BUG_CORRAL/02.md`` (and any other numbered
file in that directory), extracts every ``path/to/file.py:LINE`` style
reference inside the block, and reports:

  - PRESENT   the path exists and the cited line is within the file
  - GONE      the path no longer exists
  - SHORT     the path exists but the cited line is past EOF
  - OK        finding has at least one PRESENT reference
  - STALE-?   no PRESENT references at all (all GONE/SHORT)

This does NOT attempt to confirm semantic claims (e.g. "execute_action does
not call update_object" — that requires reading code). Semantic re-audit must
happen by hand on findings the script flags. The exit code is non-zero when
any finding shows zero PRESENT references, so the script can gate CI for the
corral-PR or be wired into ``governance-all``.

Usage:
    python scripts/governance/verify_corral_findings.py
    python scripts/governance/verify_corral_findings.py --json
    python scripts/governance/verify_corral_findings.py --dir DE_BUG_CORRAL
    python scripts/governance/verify_corral_findings.py --finding TV-01

Anti-slop note:
    Treat this script as a smoke detector, not a specification. A PRESENT
    line-reference is a necessary but not sufficient condition for a finding
    to still be live.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

HEADER_RE = re.compile(
    r"^###\s+(?P<severity>CRITICAL|MAJOR|MINOR|INFO)\s+·\s+(?P<fid>[A-Z]+-\d+)\s+·\s+(?P<title>.+?)\s*$"
)
# Match `<path>:<line>` references inside backticks.  The path must contain a
# slash or end in ``.py``/``.md``/``.yaml``/``.yml`` to avoid matching plain
# words like ``url:8080``.
REF_RE = re.compile(
    r"`(?P<path>[A-Za-z0-9_./\-]+\.(?:py|md|yaml|yml|toml|cfg|json|sh|mk|txt|ini))(?::(?P<line>\d+)(?:-(?P<endline>\d+))?)?`"
)
STATUS_RE = re.compile(r"^-\s*Status:\s*(?P<status>\S+)", re.IGNORECASE)


@dataclass
class Reference:
    path: str
    line: int | None
    end_line: int | None
    result: str  # PRESENT | GONE | SHORT | NOLINE

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "end_line": self.end_line,
            "result": self.result,
        }


@dataclass
class Finding:
    fid: str
    severity: str
    title: str
    declared_status: str | None
    source_file: str
    refs: list[Reference] = field(default_factory=list)

    def verdict(self) -> str:
        if not self.refs:
            return "NO-REFS"
        present = [r for r in self.refs if r.result == "PRESENT"]
        if present:
            return "OK"
        if all(r.result == "GONE" for r in self.refs):
            return "STALE-PATHS-GONE"
        return "STALE-LINES-PAST-EOF"

    def to_dict(self) -> dict:
        return {
            "fid": self.fid,
            "severity": self.severity,
            "title": self.title,
            "declared_status": self.declared_status,
            "source_file": self.source_file,
            "verdict": self.verdict(),
            "refs": [r.to_dict() for r in self.refs],
        }


_BASENAME_CACHE: dict[str, list[Path]] = {}


def _build_basename_cache(repo_root: Path) -> None:
    """Walk the tree once and bucket files by basename, for fuzzy resolution.

    The corral often cites a file by bare name (``agent_runner.py``) when the
    real path is ``dharma_swarm/agent_runner.py``. We tolerate that by falling
    back to a basename lookup when the literal path does not resolve.
    """
    if _BASENAME_CACHE:
        return
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"}
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & skip_dirs:
            continue
        _BASENAME_CACHE.setdefault(path.name, []).append(path)


def _resolve(repo_root: Path, path: str) -> Path | None:
    direct = repo_root / path
    if direct.exists():
        return direct
    # If the corral cited a bare filename, look it up.
    if "/" not in path:
        _build_basename_cache(repo_root)
        hits = _BASENAME_CACHE.get(path, [])
        if len(hits) == 1:
            return hits[0]
        # Ambiguous basename — treat as GONE rather than guess.
    return None


def _classify_ref(repo_root: Path, path: str, line: int | None) -> str:
    full = _resolve(repo_root, path)
    if full is None:
        return "GONE"
    if line is None:
        return "NOLINE"
    try:
        with full.open("rb") as f:
            count = sum(1 for _ in f)
    except OSError:
        return "GONE"
    if line > count:
        return "SHORT"
    return "PRESENT"


def parse_corral_file(repo_root: Path, md_path: Path) -> list[Finding]:
    """Parse a single ``DE_BUG_CORRAL/NN.md`` file into Findings."""
    findings: list[Finding] = []
    current: Finding | None = None
    try:
        rel_src = str(md_path.relative_to(repo_root))
    except ValueError:
        rel_src = str(md_path)
    with md_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = HEADER_RE.match(line)
            if m:
                if current:
                    findings.append(current)
                current = Finding(
                    fid=m.group("fid"),
                    severity=m.group("severity"),
                    title=m.group("title"),
                    declared_status=None,
                    source_file=rel_src,
                )
                continue
            if current is None:
                continue
            # Status line
            sm = STATUS_RE.match(line.strip())
            if sm:
                current.declared_status = sm.group("status").upper()
            # File:line references
            for rm in REF_RE.finditer(line):
                p = rm.group("path")
                l = rm.group("line")
                el = rm.group("endline")
                line_num = int(l) if l else None
                end_num = int(el) if el else None
                result = _classify_ref(repo_root, p, line_num)
                current.refs.append(
                    Reference(path=p, line=line_num, end_line=end_num, result=result)
                )
    if current:
        findings.append(current)
    return findings


def gather_findings(repo_root: Path, corral_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for md in sorted(corral_dir.glob("[0-9][0-9].md")):
        # Skip indices/provenance: 00 (index), 09 (provenance manifest)
        if md.stem in {"00", "09"}:
            continue
        findings.extend(parse_corral_file(repo_root, md))
    return findings


def render_text(findings: list[Finding]) -> str:
    out: list[str] = []
    out.append(f"Corral re-verifier — checked {len(findings)} findings against current tree")
    out.append("")

    by_verdict: dict[str, list[Finding]] = {}
    for f in findings:
        by_verdict.setdefault(f.verdict(), []).append(f)

    for verdict in ("STALE-PATHS-GONE", "STALE-LINES-PAST-EOF", "NO-REFS", "OK"):
        bucket = by_verdict.get(verdict, [])
        if not bucket:
            continue
        out.append(f"## {verdict}  ({len(bucket)})")
        for f in bucket:
            out.append(f"  - [{f.severity}] {f.fid} · {f.title}  ({f.source_file})")
            if verdict != "OK":
                for r in f.refs:
                    suffix = f":{r.line}" if r.line else ""
                    out.append(f"      {r.result:8s} {r.path}{suffix}")
        out.append("")

    # Summary line
    counts = {k: len(by_verdict.get(k, [])) for k in ("OK", "STALE-PATHS-GONE", "STALE-LINES-PAST-EOF", "NO-REFS")}
    out.append(
        "Summary: "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", default="DE_BUG_CORRAL", help="Corral directory to scan")
    p.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    p.add_argument(
        "--finding",
        default=None,
        help="Only verify a single finding ID (e.g. TV-01).",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any finding has zero PRESENT references.",
    )
    args = p.parse_args(argv)

    corral_dir = (REPO_ROOT / args.dir).resolve()
    if not corral_dir.exists():
        # Corral directory absent — treat as no-op, not failure. The branch
        # carrying the corral is separate from main.
        print(f"corral directory not present: {corral_dir}", file=sys.stderr)
        return 0

    findings = gather_findings(REPO_ROOT, corral_dir)
    if args.finding:
        findings = [f for f in findings if f.fid == args.finding]
        if not findings:
            print(f"finding {args.finding} not found", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        print(render_text(findings))

    if args.strict:
        stale = [f for f in findings if f.verdict() not in ("OK",)]
        return 1 if stale else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
