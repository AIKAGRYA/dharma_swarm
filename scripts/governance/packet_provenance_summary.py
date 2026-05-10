#!/usr/bin/env python3
"""Summarize packet-provenance evidence for governance calibration."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.governance.check_packet_provenance import DEFAULT_WITNESS_PATH

JsonDict = dict[str, Any]


def _load_json(path: Path) -> JsonDict | None:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return row if isinstance(row, dict) else None


def load_witness_events(path: Path) -> list[JsonDict]:
    if not path.exists():
        return []
    events: list[JsonDict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "valid" in row:
            row.setdefault("source", "local-witness")
            events.append(row)
    return events


def load_ci_events(path: Path) -> list[JsonDict]:
    if not path.exists():
        return []
    events: list[JsonDict] = []
    for report_path in sorted(path.glob("*.json")):
        row = _load_json(report_path)
        if row is None or "valid" not in row:
            continue
        row.setdefault("source", "ci-artifact")
        row.setdefault("artifact_path", str(report_path))
        events.append(row)
    return events


def load_events(*, witness_jsonl: Path, ci_report_dir: Path) -> list[JsonDict]:
    return load_witness_events(witness_jsonl.expanduser()) + load_ci_events(ci_report_dir)


def _requirements(event: JsonDict) -> list[JsonDict]:
    rows = event.get("requirements")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _uncovered(event: JsonDict) -> list[JsonDict]:
    rows = event.get("uncovered_required_files")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _required_count(event: JsonDict) -> int:
    value = event.get("required_count")
    if isinstance(value, int):
        return value
    return sum(1 for row in _requirements(event) if bool(row.get("required")))


def summarize_events(events: list[JsonDict]) -> JsonDict:
    sources: Counter[str] = Counter()
    uncovered_by_reason: Counter[str] = Counter()
    packet_required_events = 0
    valid_events = 0
    invalid_events = 0
    bypass_events = 0
    bypass_override_events = 0
    level2_rejections = 0
    level1_rejections = 0
    missing_packet_id_events = 0
    uncovered_file_count = 0

    for event in events:
        sources[str(event.get("source") or "unknown")] += 1
        valid = bool(event.get("valid"))
        required_count = _required_count(event)
        uncovered = _uncovered(event)
        missing_packet_ids = event.get("missing_packet_ids")
        missing_count = len(missing_packet_ids) if isinstance(missing_packet_ids, list) else 0

        if valid:
            valid_events += 1
        else:
            invalid_events += 1
        if required_count:
            packet_required_events += 1
        if bool(event.get("bypass_reason")):
            bypass_events += 1
            if required_count and valid:
                bypass_override_events += 1
        if missing_count:
            missing_packet_id_events += 1

        for row in uncovered:
            reason = str(row.get("reason") or "unknown")
            uncovered_by_reason[reason] += 1
            uncovered_file_count += 1
        if any(row.get("reason") == "hot_or_governance_path" for row in uncovered):
            level2_rejections += 1
        if any(row.get("reason") == "risky_source_cleanup_or_refactor" for row in uncovered):
            level1_rejections += 1

    total = len(events)
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_events": total,
        "valid_events": valid_events,
        "invalid_events": invalid_events,
        "packet_required_events": packet_required_events,
        "bypass_events": bypass_events,
        "bypass_override_events": bypass_override_events,
        "level2_rejections": level2_rejections,
        "level1_rejections": level1_rejections,
        "missing_packet_id_events": missing_packet_id_events,
        "uncovered_file_count": uncovered_file_count,
        "invalid_rate": invalid_events / total if total else 0.0,
        "bypass_rate": bypass_events / packet_required_events if packet_required_events else 0.0,
        "sources": dict(sorted(sources.items())),
        "uncovered_by_reason": dict(sorted(uncovered_by_reason.items())),
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_markdown(summary: JsonDict) -> str:
    lines = [
        "# Packet Provenance Calibration",
        "",
        f"Generated UTC: {summary['generated_utc']}",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| total events | {summary['total_events']} |",
        f"| valid events | {summary['valid_events']} |",
        f"| invalid events | {summary['invalid_events']} |",
        f"| invalid rate | {_pct(float(summary['invalid_rate']))} |",
        f"| packet-required events | {summary['packet_required_events']} |",
        f"| bypass reasons | {summary['bypass_events']} |",
        f"| valid bypass overrides | {summary['bypass_override_events']} |",
        f"| bypass rate among required | {_pct(float(summary['bypass_rate']))} |",
        f"| level-2 hot/governance rejections | {summary['level2_rejections']} |",
        f"| level-1 risky-source rejections | {summary['level1_rejections']} |",
        f"| missing Packet-Id artifacts | {summary['missing_packet_id_events']} |",
        f"| uncovered required files | {summary['uncovered_file_count']} |",
        "",
    ]

    sources = summary.get("sources") or {}
    if sources:
        lines.extend(["## Sources", ""])
        lines.extend(f"- {source}: {count}" for source, count in sources.items())
        lines.append("")

    reasons = summary.get("uncovered_by_reason") or {}
    if reasons:
        lines.extend(["## Uncovered Files By Reason", ""])
        lines.extend(f"- {reason}: {count}" for reason, count in reasons.items())
        lines.append("")

    if not summary["total_events"]:
        lines.append("No packet-provenance evidence has been recorded yet.")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--witness-jsonl", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument(
        "--ci-report-dir",
        type=Path,
        default=Path("quality-reports/packet-provenance"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    events = load_events(
        witness_jsonl=args.witness_jsonl,
        ci_report_dir=args.ci_report_dir,
    )
    summary = summarize_events(events)
    text = json.dumps(summary, indent=2, sort_keys=True) if args.json else render_markdown(summary)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
