#!/usr/bin/env python3
"""slop_trend.py — read the slop ledger, emit a markdown trend report.

Reads ~/.dharma/slop_ledger/*.jsonl (one entry per ModuleScore per
verification run), aggregates over time windows, and produces a
human-readable + machine-readable summary.

Use cases:
  - Daily morning check: what regressed overnight?
  - PR-time delta: are we shipping more slop or less?
  - Per-module hotspot ranking: which files are repeat offenders?
  - Per-detector signal-to-noise: which detectors actually fire?

Usage:
  python3 scripts/governance/slop_trend.py
  python3 scripts/governance/slop_trend.py --days 7
  python3 scripts/governance/slop_trend.py --days 30 --top 20 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

LEDGER_DIR = Path.home() / ".dharma" / "slop_ledger"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="slop_trend", description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--days", type=int, default=7, help="Window in days (default 7)")
    p.add_argument("--top", type=int, default=10, help="Top-N hotspots (default 10)")
    p.add_argument("--ledger-dir", default=str(LEDGER_DIR))
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p.add_argument("--mode-filter", default=None, help="Only entries from this mode (pre-commit|ci|nightly)")
    return p.parse_args(argv)


def iter_entries(ledger_dir: Path, since: datetime, mode_filter: str | None) -> list[dict]:
    if not ledger_dir.exists():
        return []
    entries: list[dict] = []
    for jsonl in sorted(ledger_dir.glob("*.jsonl")):
        try:
            day = datetime.strptime(jsonl.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if day < since - timedelta(days=1):
            continue
        with jsonl.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("timestamp")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt < since:
                            continue
                    except (ValueError, AttributeError):
                        pass
                if mode_filter and entry.get("mode") != mode_filter:
                    continue
                entries.append(entry)
    return entries


def summarize(entries: list[dict], top: int) -> dict:
    by_path_max_p: dict[str, float] = {}
    by_path_count: Counter[str] = Counter()
    by_action: Counter[str] = Counter()
    by_family_findings: Counter[str] = Counter()
    by_tool_findings: Counter[str] = Counter()
    runs_per_day: defaultdict[str, int] = defaultdict(int)

    for e in entries:
        score = e.get("module_score") or {}
        path = score.get("path") or ""
        p = float(score.get("p") or 0.0)
        if path:
            by_path_count[path] += 1
            if p > by_path_max_p.get(path, 0.0):
                by_path_max_p[path] = p
        action = e.get("action") or "unknown"
        by_action[action] += 1
        ts = e.get("timestamp", "")
        if ts:
            runs_per_day[ts[:10]] += 1
        for f in e.get("findings") or []:
            by_family_findings[f.get("family") or "unknown"] += 1
            by_tool_findings[f.get("tool") or "unknown"] += 1

    hotspots = [
        {"path": path, "max_p": by_path_max_p.get(path, 0.0), "appearances": cnt}
        for path, cnt in by_path_count.most_common(top)
    ]
    hotspots.sort(key=lambda r: (r["max_p"], r["appearances"]), reverse=True)
    return {
        "total_entries": len(entries),
        "runs_per_day": dict(sorted(runs_per_day.items())),
        "actions": dict(by_action),
        "family_findings": dict(by_family_findings.most_common()),
        "tool_findings": dict(by_tool_findings.most_common()),
        "hotspots": hotspots,
    }


def render_markdown(summary: dict, days: int) -> str:
    lines: list[str] = []
    lines.append(f"# Slop Verification Trend — last {days} days")
    lines.append("")
    lines.append(f"- Total ledger entries: **{summary['total_entries']}**")
    lines.append(f"- Distinct days with runs: **{len(summary['runs_per_day'])}**")
    lines.append("")
    lines.append("## Action distribution")
    if summary["actions"]:
        for action, n in sorted(summary["actions"].items(), key=lambda x: -x[1]):
            lines.append(f"- `{action}`: **{n}**")
    else:
        lines.append("(no actions)")
    lines.append("")
    lines.append("## Findings by detector family")
    if summary["family_findings"]:
        for fam, n in summary["family_findings"].items():
            lines.append(f"- `{fam}`: **{n}**")
    else:
        lines.append("(no findings)")
    lines.append("")
    lines.append("## Findings by tool")
    if summary["tool_findings"]:
        for tool, n in summary["tool_findings"].items():
            lines.append(f"- `{tool}`: **{n}**")
    else:
        lines.append("(no tool findings)")
    lines.append("")
    lines.append("## Top hotspots (by max probability across runs)")
    if summary["hotspots"]:
        lines.append("| path | max_p | appearances |")
        lines.append("|---|---:|---:|")
        for h in summary["hotspots"]:
            lines.append(f"| `{h['path']}` | {h['max_p']:.3f} | {h['appearances']} |")
    else:
        lines.append("(no hotspots)")
    lines.append("")
    lines.append("## Run cadence (entries per day)")
    if summary["runs_per_day"]:
        lines.append("| day | entries |")
        lines.append("|---|---:|")
        for day, n in summary["runs_per_day"].items():
            lines.append(f"| {day} | {n} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ledger_dir = Path(args.ledger_dir).expanduser()
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    entries = iter_entries(ledger_dir, since, args.mode_filter)
    summary = summarize(entries, args.top)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_markdown(summary, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
