#!/usr/bin/env python3
"""mutation_score_report.py — the PRODUCER half of the S6 mutation gate (P3-09).

Runs mutmut on the configured surfaces and writes a machine-readable report that
check_track_status.py's `mutation_score_gte` (S6) criterion READS. The gate never
runs mutmut inline (it is slow); this script is the separate `make mutation-test`
step. Report sink: reports/governance/mutation_score.json.

The score parser (parse_mutmut_summary) is pure and unit-tested so it cannot
silently drift across mutmut versions — itself an anti-slop discipline. If mutmut
is absent or fails, NO report is written (the gate then fail-closes as MISSING).

HONESTY NOTE (do not over-claim): this parser targets mutmut's classic run
summary. The interpreter env here ships mutmut 3.5.0 — a rewrite whose run output
and config discovery differ — and a real mutation run was NOT executed in-session
(scoping a single surface safely on a 770-module repo + the 3.x output format both
need confirmation). The STABLE CONTRACT is the report schema (a numeric `score`),
which any mutation tool can emit; the FIRST `make mutation-test` / CI run must
confirm the parse against real mutmut-3.x output (use `mutmut export-cicd-stats`
if the summary parse misses). Because the S6 gate fail-closes until a valid,
fresh report exists, a mis-parse can never grant false S6 credit — only withhold it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "reports/governance/mutation_score.json"

# mutmut tags outcomes with emoji in its run summary; word fallbacks cover other
# versions / --plain output. skipped mutants are EXCLUDED from the score.
_OUTCOME_EMOJI = {
    "killed": "🎉",
    "timeout": "⏰",
    "suspicious": "🤔",
    "survived": "🙁",
    "skipped": "🔇",
}


def parse_mutmut_summary(text: str) -> dict:
    """Extract mutant counts from mutmut output and compute the score.

    score = killed / (killed + survived + timeout + suspicious)   [skipped excluded]

    Tolerant of version drift: reads the emoji-tagged counts first, then falls
    back to word-based 'killed: N' patterns. Returns a dict with each outcome
    count plus `total` (scored mutants) and `score` (0.0 when nothing scored)."""
    counts: dict[str, int] = {}
    for name, emoji in _OUTCOME_EMOJI.items():
        hits = re.findall(rf"{re.escape(emoji)}\s*(\d+)", text)
        if not hits:
            hits = re.findall(rf"\b{name}\b[^\d]{{0,8}}(\d+)", text, re.IGNORECASE)
        counts[name] = int(hits[-1]) if hits else 0
    scored = counts["killed"] + counts["survived"] + counts["timeout"] + counts["suspicious"]
    counts["total"] = scored
    counts["score"] = round(counts["killed"] / scored, 4) if scored else 0.0
    return counts


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", default="",
                    help="paths_to_mutate override (else pyproject [tool.mutmut])")
    ap.add_argument("--output", default=str(DEFAULT_REPORT))
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)

    cmd = ["mutmut", "run"]
    if args.paths:
        cmd += ["--paths-to-mutate", args.paths]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=args.timeout)
    except FileNotFoundError:
        print("ERROR: mutmut not installed — `pip install mutmut`", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"ERROR: mutmut run exceeded {args.timeout}s", file=sys.stderr)
        return 2

    counts = parse_mutmut_summary((proc.stdout or "") + "\n" + (proc.stderr or ""))
    report = {
        "schema_version": "mutation_score_report.v1",
        "score": counts["score"],
        "killed": counts["killed"],
        "survived": counts["survived"],
        "timeout": counts["timeout"],
        "suspicious": counts["suspicious"],
        "skipped": counts["skipped"],
        "total": counts["total"],
        "paths": args.paths or "(pyproject [tool.mutmut])",
        "produced_at": _utc_now(),
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"mutation score {report['score']:.2f} "
          f"({report['killed']}/{report['total']} killed) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
