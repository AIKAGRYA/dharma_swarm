#!/usr/bin/env python3
"""Build the local Morning Cockpit evidence bundle.

This runner is deliberately thin. It executes existing local evidence
collectors, writes the Daily Operating Brief, and records a small manifest. It
does not schedule agents, allocate worktrees, merge branches, or mutate runtime
state beyond the explicit report output paths.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.daily_operating_brief import (
    DailyOperatingBriefInputs,
    build_daily_operating_brief,
    render_markdown,
)


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    exit_code: int
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


@dataclass(frozen=True)
class MorningCockpitConfig:
    repo_root: Path
    operator_ground_truth_output: Path
    docops_report_output: Path
    docops_inventory_output: Path
    docops_inventory_markdown: Path
    brief_output: Path
    manifest_output: Path
    agentops_reports_dir: Path
    kaizen_reports_dir: Path
    yds_ratings_path: Path | None = None
    cost_report_path: Path | None = None
    llm_burn_state_dir: Path | None = None
    hot_items_path: Path | None = None
    revenue_notes_path: Path | None = None
    fail_on_missing_major: bool = False
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def run_morning_cockpit(config: MorningCockpitConfig) -> dict[str, Any]:
    """Run evidence collectors, write the brief, and return a manifest."""

    config.operator_ground_truth_output.parent.mkdir(parents=True, exist_ok=True)
    config.docops_report_output.parent.mkdir(parents=True, exist_ok=True)
    config.brief_output.parent.mkdir(parents=True, exist_ok=True)
    config.manifest_output.parent.mkdir(parents=True, exist_ok=True)

    commands = [
        _run_command(
            "operator-ground-truth",
            [
                sys.executable,
                "scripts/operator_ground_truth.py",
                "--repo-root",
                str(config.repo_root),
                "--json",
                "--output",
                str(config.operator_ground_truth_output),
            ],
            cwd=config.repo_root,
        ),
        _run_command(
            "docops-report",
            [
                sys.executable,
                "scripts/docops/check_docops_integrity.py",
                "--report-json",
                str(config.docops_report_output),
                "--inventory-json",
                str(config.docops_inventory_output),
                "--inventory-markdown",
                str(config.docops_inventory_markdown),
            ],
            cwd=config.repo_root,
        ),
    ]

    inputs = DailyOperatingBriefInputs(
        agentops_reports_dir=config.agentops_reports_dir,
        kaizen_reports_dir=config.kaizen_reports_dir,
        yds_ratings_path=config.yds_ratings_path,
        cost_report_path=config.cost_report_path,
        llm_burn_state_dir=config.llm_burn_state_dir,
        docops_check_report_path=config.docops_report_output,
        docops_inventory_path=config.docops_inventory_output,
        operator_ground_truth_path=config.operator_ground_truth_output,
        hot_items_path=config.hot_items_path,
        revenue_notes_path=config.revenue_notes_path,
        now=config.now,
    )
    brief = build_daily_operating_brief(inputs)
    config.brief_output.write_text(render_markdown(brief), encoding="utf-8")

    command_failures = [
        command.name for command in commands
        if not command.passed
    ]
    missing_major_sources = _missing_major_sources(
        config,
        command_failures=command_failures,
    )
    passed = not command_failures and (
        not missing_major_sources or not config.fail_on_missing_major
    )
    manifest = {
        "generated_at": config.now.isoformat(),
        "passed": passed,
        "strict_missing_major": config.fail_on_missing_major,
        "brief_output": str(config.brief_output),
        "operator_ground_truth_output": str(config.operator_ground_truth_output),
        "docops_report_output": str(config.docops_report_output),
        "docops_inventory_output": str(config.docops_inventory_output),
        "commands": [command.to_dict() for command in commands],
        "missing_sources": brief.missing_sources,
        "missing_major_sources": missing_major_sources,
    }
    config.manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _run_command(name: str, command: list[str], *, cwd: Path) -> CommandResult:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return CommandResult(
            name=name,
            command=command,
            exit_code=127,
            stderr_tail=str(exc),
        )
    return CommandResult(
        name=name,
        command=command,
        exit_code=proc.returncode,
        stdout_tail=_tail(proc.stdout),
        stderr_tail=_tail(proc.stderr),
    )


def _missing_major_sources(
    config: MorningCockpitConfig,
    *,
    command_failures: list[str],
) -> list[str]:
    missing: list[str] = []
    if command_failures:
        missing.extend(f"command:{name}" for name in command_failures)
    if not config.operator_ground_truth_output.exists():
        missing.append("operator_ground_truth")
    if not config.docops_report_output.exists():
        missing.append("docops_check")
    if not config.docops_inventory_output.exists():
        missing.append("docops_inventory")
    if not _has_report(config.agentops_reports_dir, "report.json"):
        missing.append("agentops_reports")
    if not _has_report(config.kaizen_reports_dir, "kaizen_review.json"):
        missing.append("kaizen_reports")
    return missing


def _has_report(root: Path, filename: str) -> bool:
    return root.exists() and any(root.glob(f"**/{filename}"))


def _tail(text: str, *, max_chars: int = 2000) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[-max_chars:]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="morning_cockpit",
        description="Build Operator Ground Truth, DocOps, and Daily Brief evidence.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--operator-ground-truth-output",
        type=Path,
        default=Path("reports/operator_ground_truth/latest.json"),
    )
    parser.add_argument(
        "--docops-report-output",
        type=Path,
        default=Path("reports/docops/check.json"),
    )
    parser.add_argument(
        "--docops-inventory-output",
        type=Path,
        default=Path("reports/docops/corpus_inventory.json"),
    )
    parser.add_argument(
        "--docops-inventory-markdown",
        type=Path,
        default=Path("reports/docops/corpus_inventory.md"),
    )
    parser.add_argument("--brief-output", type=Path, default=None)
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("reports/morning_cockpit/latest.json"),
    )
    parser.add_argument(
        "--agentops-reports-dir",
        type=Path,
        default=Path("reports/agentops"),
    )
    parser.add_argument(
        "--kaizen-reports-dir",
        type=Path,
        default=Path("reports/kaizen"),
    )
    parser.add_argument("--yds-ratings-path", type=Path)
    parser.add_argument("--cost-report-path", type=Path)
    parser.add_argument("--llm-burn-state-dir", type=Path)
    parser.add_argument("--hot-items-path", type=Path)
    parser.add_argument("--revenue-notes-path", type=Path)
    parser.add_argument(
        "--fail-on-missing-major",
        action="store_true",
        help="Return non-zero when AgentOps/Kaizen or generated evidence is missing.",
    )
    return parser.parse_args(argv)


def _resolve_config(args: argparse.Namespace) -> MorningCockpitConfig:
    repo_root = args.repo_root.resolve()
    now = datetime.now(timezone.utc)
    brief_output = args.brief_output or Path(
        f"reports/daily_operating_brief/{now.date().isoformat()}.md"
    )
    return MorningCockpitConfig(
        repo_root=repo_root,
        operator_ground_truth_output=_under_repo(repo_root, args.operator_ground_truth_output),
        docops_report_output=_under_repo(repo_root, args.docops_report_output),
        docops_inventory_output=_under_repo(repo_root, args.docops_inventory_output),
        docops_inventory_markdown=_under_repo(repo_root, args.docops_inventory_markdown),
        brief_output=_under_repo(repo_root, brief_output),
        manifest_output=_under_repo(repo_root, args.manifest_output),
        agentops_reports_dir=_under_repo(repo_root, args.agentops_reports_dir),
        kaizen_reports_dir=_under_repo(repo_root, args.kaizen_reports_dir),
        yds_ratings_path=_optional_path(repo_root, args.yds_ratings_path),
        cost_report_path=_optional_path(repo_root, args.cost_report_path),
        llm_burn_state_dir=_optional_path(repo_root, args.llm_burn_state_dir),
        hot_items_path=_optional_path(repo_root, args.hot_items_path),
        revenue_notes_path=_optional_path(repo_root, args.revenue_notes_path),
        fail_on_missing_major=bool(args.fail_on_missing_major),
        now=now,
    )


def _under_repo(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _optional_path(repo_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return _under_repo(repo_root, path)


def main(argv: list[str] | None = None) -> int:
    config = _resolve_config(parse_args(argv))
    manifest = run_morning_cockpit(config)
    print(f"Morning Cockpit brief: {manifest['brief_output']}")
    if manifest["missing_major_sources"]:
        print(
            "Morning Cockpit missing major evidence: "
            + ", ".join(manifest["missing_major_sources"])
        )
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
