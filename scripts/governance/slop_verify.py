#!/usr/bin/env python3
"""slop-verify — Dharma Code Quality Governance CLI.

Usage:
    python3 scripts/governance/slop_verify.py <path> [<path> ...]
        [--mode pre-commit|ci|nightly]
        [--threshold 0.5]
        [--detector vulture --detector ai-slop-detector]
        [--changed-since main]
        [--ledger-dir ~/.dharma/slop_ledger]
        [--no-ledger]
        [--output-format json|table]

Exit codes:
    0 — clean (no module exceeded the requested threshold)
    1 — slop detected at or above threshold
    2 — internal error / detector failure
    127 — no detectors available (all missing)

Three lanes:
    pre-commit  fast detectors only (vulture), changed files, hard 5s budget
    ci          fast + structured (vulture + ai-slop-detector + others), 90s budget
    nightly     full pool including LLM/behavioral, 10min budget

The CLI never modifies source files. Findings → ledger → review.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.slop.adapters import REGISTRY as ADAPTER_REGISTRY  # noqa: E402
from dharma_swarm.slop.aggregate import aggregate_results  # noqa: E402
from dharma_swarm.slop.ledger import LEDGER_DIR, write_entries  # noqa: E402
from dharma_swarm.slop.models import (  # noqa: E402
    DetectorResult,
    SlopLedgerEntry,
)
from dharma_swarm.slop.router import Action, route_score, severity_summary  # noqa: E402

MODE_PROFILES: dict[str, dict[str, object]] = {
    "pre-commit": {
        "detectors": ("vulture", "oxlint"),
        "budget_sec": 5.0,
        "default_threshold": 0.50,
    },
    "ci": {
        "detectors": (
            "vulture", "ai-slop-detector", "sentry-spotlight",
            "fallow", "knip", "jscpd", "tsc", "eslint",
        ),
        "budget_sec": 90.0,
        "default_threshold": 0.50,
    },
    "nightly": {
        "detectors": (
            "vulture", "ai-slop-detector", "sentry-spotlight",
            "fallow", "knip", "jscpd", "tsc", "eslint",
            "dependency-cruiser",
        ),
        "budget_sec": 600.0,
        "default_threshold": 0.30,
    },
}

SOURCE_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
)
EXCLUDE_DIR_NAMES: frozenset[str] = frozenset(
    {"__pycache__", ".venv", "node_modules", ".next", "dist", "build", ".turbo", ".git"}
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="slop-verify", description=__doc__.split("\n\n", 1)[0])
    p.add_argument("paths", nargs="*", help="Files or directories to scan")
    p.add_argument(
        "--mode",
        choices=tuple(MODE_PROFILES.keys()),
        default="ci",
        help="Lane profile (default: ci)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Block on score >= threshold (default depends on mode)",
    )
    p.add_argument(
        "--detector",
        action="append",
        dest="detectors",
        help="Override detector list (repeatable). Default depends on mode.",
    )
    p.add_argument(
        "--changed-since",
        default=None,
        help="Restrict scan to files changed vs given git ref (e.g. 'main', 'HEAD~1')",
    )
    p.add_argument(
        "--ledger-dir",
        default=str(LEDGER_DIR),
        help=f"Ledger directory (default: {LEDGER_DIR})",
    )
    p.add_argument(
        "--no-ledger",
        action="store_true",
        help="Do not write a ledger entry",
    )
    p.add_argument(
        "--output-format",
        choices=("json", "table"),
        default="table",
        help="Stdout format (default: table)",
    )
    return p.parse_args(argv)


def changed_files(ref: str, *, repo_root: Path = REPO_ROOT) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", ref, "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    out: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = (repo_root / line).resolve()
        if p.exists() and p.suffix in SOURCE_SUFFIXES:
            out.append(p)
    return out


def expand_paths(paths: Iterable[str], *, repo_root: Path = REPO_ROOT) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = repo_root / p
        if p.is_file():
            if p.suffix in SOURCE_SUFFIXES:
                out.append(p)
        elif p.is_dir():
            for child in p.rglob("*"):
                if not child.is_file() or child.suffix not in SOURCE_SUFFIXES:
                    continue
                if any(part in EXCLUDE_DIR_NAMES for part in child.parts):
                    continue
                out.append(child)
    return sorted(set(out))


def select_detectors(
    mode: str, override: list[str] | None
) -> list[str]:
    chosen = override if override else list(MODE_PROFILES[mode]["detectors"])  # type: ignore[arg-type]
    return [name for name in chosen if name in ADAPTER_REGISTRY]


def run_detectors(
    detectors: list[str], paths: list[Path]
) -> list[DetectorResult]:
    results: list[DetectorResult] = []
    for name in detectors:
        adapter = ADAPTER_REGISTRY[name]
        results.append(adapter(paths))
    return results


def render_table(scores: dict, threshold: float, summary: dict[str, int]) -> str:
    if not scores:
        return "no findings (clean)"
    lines = ["", f"{'PATH':<60} {'P':>6} {'AGREE':>6} {'#FINDINGS':>10} {'ACTION':<22}"]
    lines.append("-" * 110)
    sorted_scores = sorted(scores.values(), key=lambda s: s.p, reverse=True)
    for s in sorted_scores[:50]:
        action = route_score(s).value
        flag = "!" if s.p >= threshold else " "
        lines.append(
            f"{flag} {s.path:<58} {s.p:>6.3f} {s.agreement:>6} {s.finding_count:>10} {action:<22}"
        )
    lines.append("")
    lines.append("ACTION SUMMARY:  " + "  ".join(f"{k}={v}" for k, v in summary.items() if v))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = MODE_PROFILES[args.mode]
    threshold = args.threshold if args.threshold is not None else float(profile["default_threshold"])  # type: ignore[arg-type]

    if args.changed_since:
        paths = changed_files(args.changed_since)
        if args.paths:
            extra = expand_paths(args.paths)
            paths = sorted(set(paths) | set(extra))
    else:
        if not args.paths:
            print("error: no paths supplied (use a path or --changed-since)", file=sys.stderr)
            return 2
        paths = expand_paths(args.paths)

    if not paths:
        print("no Python files to scan", file=sys.stderr)
        return 0

    detectors = select_detectors(args.mode, args.detectors)
    if not detectors:
        print(
            f"error: no detectors available for mode={args.mode}; "
            f"requested={args.detectors or list(profile['detectors'])} "
            f"available={sorted(ADAPTER_REGISTRY)}",
            file=sys.stderr,
        )
        return 127

    results = run_detectors(detectors, paths)
    scores = aggregate_results(results)
    summary = severity_summary(scores.values())

    if not args.no_ledger:
        entries = [
            SlopLedgerEntry.now(
                mode=args.mode,
                score=score,
                action=route_score(score).value,
                findings=[
                    f for r in results for f in r.findings if f.path == score.path
                ],
            )
            for score in scores.values()
        ]
        write_entries(entries, base=Path(args.ledger_dir).expanduser())

    if args.output_format == "json":
        out = {
            "mode": args.mode,
            "threshold": threshold,
            "detectors": detectors,
            "summary": summary,
            "detector_results": [r.to_dict() for r in results],
            "module_scores": {p: s.to_dict() for p, s in scores.items()},
        }
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(render_table(scores, threshold, summary))

    blocking = [s for s in scores.values() if s.p >= threshold]
    if blocking:
        return 1
    if any(r.exit_code not in (0, 1) and r.exit_code != 127 for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
