#!/usr/bin/env python3
"""Run non-blocking hygiene detectors and write a dated baseline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_hygiene_integrity import REPO_ROOT, active_patterns, load_patterns  # noqa: E402


DEFAULT_OUTPUT_DIR = Path("docs/governance/hygiene/baselines")


def run_detector(command: str, repo_root: Path, timeout: int) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=repo_root,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def render_scan(repo_root: Path, pattern_id: str | None, timeout: int, today: str) -> str:
    patterns = active_patterns(load_patterns(repo_root))
    if pattern_id:
        patterns = [pattern for pattern in patterns if pattern["id"] == pattern_id]
        if not patterns:
            raise SystemExit(f"unknown pattern id: {pattern_id}")

    lines = [
        f"# Hygiene Baseline - {today}",
        "",
        "This is a non-blocking scan. Counts are heuristic signals, not verdicts.",
        "",
    ]
    for pattern in patterns:
        detector = pattern["detector"]
        lines.append(f"## {pattern['id']} - {pattern['title']}")
        lines.append(f"stage: {pattern['stage']}  severity: {pattern['severity']}")
        lines.append(f"definition: {pattern['definition']}")
        detector_type = detector.get("type")
        if detector_type == "command":
            command = detector["command"]
            lines.append(f"detector: `{command}`")
            try:
                returncode, output = run_detector(command, repo_root, timeout)
            except subprocess.TimeoutExpired:
                returncode, output = 124, f"timeout after {timeout}s"
            lines.append(f"exit_code: {returncode}")
            lines.append("output:")
            if output:
                lines.extend(f"  {line.rstrip()}" for line in output.splitlines())
            else:
                lines.append("  <empty>")
        else:
            lines.append(f"detector: {detector_type} - {detector.get('rationale', detector.get('command', 'manual review'))}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--pattern", help="run one pattern id, e.g. VC-A1")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    text = render_scan(repo_root, args.pattern, args.timeout, args.date)

    output = args.output
    if output is None:
        output = repo_root / DEFAULT_OUTPUT_DIR / f"{args.date}.txt"
    elif not output.is_absolute():
        output = repo_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    try:
        display_path = output.relative_to(repo_root)
    except ValueError:
        display_path = output
    print(f"wrote {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
