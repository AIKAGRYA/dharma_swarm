"""Read-only Daily Operating Brief for Dharma Swarm.

This module is deliberately narrower than ``insight_brief``. It does not write
ontology rows, launch agents, call providers, or run swarm loops. It composes
local evidence that already exists into one operator-facing markdown artifact.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import shorten
from typing import Any, Callable
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")
DEFAULT_SINCE_HOURS = 24.0
DEFAULT_OUTPUT_DIR = Path.home() / "dharma_briefs"


@dataclass(frozen=True)
class GitSnapshot:
    branch: str
    head: str
    dirty_files: tuple[str, ...]
    error: str = ""


@dataclass(frozen=True)
class AgentOpsReport:
    packet_id: str
    status: str
    finished_at: str
    command_count: int
    failed_commands: tuple[str, ...]
    violation_count: int
    path: str


@dataclass(frozen=True)
class CostSnapshot:
    calls: int
    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    by_provider: dict[str, int]
    by_tier: dict[str, int]
    malformed_lines: int = 0


@dataclass(frozen=True)
class HumanYDSRating:
    target: str
    grade: str
    note: str
    timestamp: str
    source: str


@dataclass(frozen=True)
class OntologyCounts:
    counts: dict[str, int]
    error: str = ""


@dataclass(frozen=True)
class OperatingBrief:
    path: Path | None
    content: str


def build_daily_operating_brief(
    *,
    repo_root: str | Path = ".",
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    now_fn: Callable[[], datetime] | None = None,
    since_hours: float = DEFAULT_SINCE_HOURS,
    write: bool = True,
) -> OperatingBrief:
    """Build a local operating brief and optionally write it to markdown."""
    root = Path(repo_root).expanduser().resolve()
    now = now_fn() if now_fn is not None else datetime.now(WITA)
    state = Path(state_dir).expanduser() if state_dir is not None else Path.home() / ".dharma"
    out_dir = Path(output_dir).expanduser() if output_dir is not None else DEFAULT_OUTPUT_DIR

    content = render_daily_operating_brief(
        now=now,
        repo_root=root,
        state_dir=state,
        since_hours=since_hours,
    )
    if not write:
        return OperatingBrief(path=None, content=content)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now.date().isoformat()}-operating.md"
    path.write_text(content + "\n", encoding="utf-8")
    return OperatingBrief(path=path, content=content)


def render_daily_operating_brief(
    *,
    now: datetime,
    repo_root: Path,
    state_dir: Path,
    since_hours: float = DEFAULT_SINCE_HOURS,
) -> str:
    git = load_git_snapshot(repo_root)
    agentops = load_agentops_reports(repo_root / ".dharma" / "agentops" / "runs")
    cost = load_cost_snapshot(state_dir / "cost_log.jsonl", now=now, since_hours=since_hours)
    yds = load_yds_ratings(state_dir / "ysd" / "ledger.jsonl")
    ontology = load_ontology_counts(state_dir / "ontology.db")
    hot_verdict = extract_markdown_section(repo_root / "SWARM_HOT_ITEMS.md", "Current Verdict", limit=5)
    hot_items = extract_markdown_section(repo_root / "SWARM_HOT_ITEMS.md", "Hot Items", limit=8)
    manifest_counts = load_manifest_status_counts(repo_root / "ACTIVE_SURFACE_MANIFEST.yaml")
    revenue = load_revenue_signals(repo_root, state_dir)

    lines = [
        f"# Daily Operating Brief - {now.date().isoformat()}",
        "",
        f"Generated: `{now.isoformat()}`",
        f"Repo: `{repo_root}`",
        f"State dir: `{state_dir}`",
        "",
        "## 1. What Changed",
        "",
        *_render_git(git),
        "",
        "## 2. What Is Real Vs Decorative",
        "",
        *_render_manifest(manifest_counts),
        *_render_named_lines("Current verdict", hot_verdict),
        *_render_named_lines("Hot items", hot_items),
        "",
        "## 3. Tests / Brakes Status",
        "",
        *_render_agentops(agentops),
        "",
        "## 4. Burn / Cost Signal",
        "",
        *_render_cost(cost, since_hours=since_hours),
        "",
        "## 5. Value Produced",
        "",
        *_render_value(ontology, agentops),
        "",
        "## 6. Human YDS Ratings",
        "",
        *_render_yds(yds),
        "",
        "## 7. Revenue / Self-Funding Moves",
        "",
        *_render_revenue(revenue),
        "",
        "## 8. Stop Doing",
        "",
        *_render_stop_doing(hot_items),
        "",
        "## 9. One Next Move",
        "",
        f"- {choose_next_move(agentops=agentops, cost=cost, yds=yds, revenue=revenue)}",
    ]
    return "\n".join(lines).rstrip()


def load_git_snapshot(repo_root: Path) -> GitSnapshot:
    """Read branch/head/status without mutating the repository."""
    try:
        branch = _git(repo_root, ["branch", "--show-current"]) or "(detached)"
        head = _git(repo_root, ["log", "-1", "--oneline", "--decorate"])
        status = _git(repo_root, ["status", "--short"])
        dirty = tuple(line.strip() for line in status.splitlines() if line.strip())
        return GitSnapshot(branch=branch, head=head, dirty_files=dirty)
    except BriefSourceError as exc:
        return GitSnapshot(branch="", head="", dirty_files=(), error=str(exc))


def load_agentops_reports(runs_dir: Path, *, limit: int = 5) -> list[AgentOpsReport]:
    if not runs_dir.exists():
        return []
    reports: list[AgentOpsReport] = []
    for path in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        commands = payload.get("commands") if isinstance(payload.get("commands"), list) else []
        failed = [
            str(command.get("name") or "unnamed")
            for command in commands
            if isinstance(command, dict) and int(command.get("exit_code") or 0) != 0
        ]
        violations = payload.get("violations") if isinstance(payload.get("violations"), list) else []
        reports.append(
            AgentOpsReport(
                packet_id=str(payload.get("packet_id") or path.stem),
                status=str(payload.get("status") or "unknown"),
                finished_at=str(payload.get("finished_at") or ""),
                command_count=len(commands),
                failed_commands=tuple(failed),
                violation_count=len(violations),
                path=str(path),
            )
        )
        if len(reports) >= limit:
            break
    return reports


def load_cost_snapshot(
    path: Path,
    *,
    now: datetime,
    since_hours: float = DEFAULT_SINCE_HOURS,
) -> CostSnapshot:
    cutoff = now.timestamp() - (since_hours * 3600)
    if not path.exists():
        return CostSnapshot(
            calls=0,
            total_cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
            by_provider={},
            by_tier={},
        )

    calls = 0
    total_cost = 0.0
    input_tokens = 0
    output_tokens = 0
    by_provider: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()
    malformed = 0

    for row in _read_jsonl(path):
        if row is None:
            malformed += 1
            continue
        timestamp = _float(row.get("timestamp"))
        if timestamp is not None and timestamp < cutoff:
            continue
        calls += 1
        total_cost += _float(row.get("estimated_cost_usd")) or 0.0
        input_tokens += int(_float(row.get("input_tokens")) or 0)
        output_tokens += int(_float(row.get("output_tokens")) or 0)
        by_provider[str(row.get("provider") or "unknown")] += 1
        by_tier[str(row.get("tier") or "unknown")] += 1

    return CostSnapshot(
        calls=calls,
        total_cost_usd=round(total_cost, 6),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        by_provider=dict(sorted(by_provider.items())),
        by_tier=dict(sorted(by_tier.items())),
        malformed_lines=malformed,
    )


def load_yds_ratings(path: Path, *, limit: int = 5) -> list[HumanYDSRating]:
    if not path.exists():
        return []

    ratings: list[HumanYDSRating] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        rating = _parse_yds_json_line(stripped, source=str(path)) or _parse_yds_command_line(
            stripped,
            source=str(path),
        )
        if rating is not None:
            ratings.append(rating)
    return ratings[-limit:]


def load_ontology_counts(path: Path) -> OntologyCounts:
    if not path.exists():
        return OntologyCounts(counts={})

    wanted = ("Outcome", "ValueEvent", "Contribution", "WitnessLog", "KnowledgeArtifact")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT type_name, COUNT(*) FROM objects GROUP BY type_name"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return OntologyCounts(counts={}, error=str(exc))

    raw_counts = {str(type_name): int(count) for type_name, count in rows}
    return OntologyCounts(counts={name: raw_counts.get(name, 0) for name in wanted})


def extract_markdown_section(path: Path, heading: str, *, limit: int = 6) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    target = f"## {heading}".lower()
    capture = False
    extracted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == target:
            capture = True
            continue
        if capture and stripped.startswith("## "):
            break
        if not capture:
            continue
        cleaned = stripped.lstrip("- ").strip()
        if cleaned:
            extracted.append(shorten(cleaned, width=220, placeholder="..."))
        if len(extracted) >= limit:
            break
    return extracted


def load_manifest_status_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    counts: Counter[str] = Counter()
    for match in re.finditer(r"^\s*status:\s*([A-Za-z_]+)\s*$", text, flags=re.MULTILINE):
        counts[match.group(1)] += 1
    return dict(sorted(counts.items()))


def load_revenue_signals(repo_root: Path, state_dir: Path) -> list[str]:
    candidates = [
        (
            repo_root / "docs" / "missions" / "DGC_REVENUE_SWARM_2026-03-13.md",
            "Revenue swarm mission doc exists",
        ),
        (
            repo_root / "docs" / "reports" / "DGC_SELF_PROVING_VENTURE_STUDIO_2026-03-13.md",
            "Self-proving venture studio report exists",
        ),
        (
            repo_root
            / "docs"
            / "missions"
            / "anthropic-economic-futures-submission-2026-03-21"
            / "anthropic_grant_application_submission_ready_2026-03-21.md",
            "Anthropic Economic Futures grant packet exists",
        ),
        (
            state_dir / "artifacts" / "aligned_revenue_engines_garden.md",
            "Aligned revenue engines garden exists",
        ),
        (
            state_dir / "artifacts" / "welfare_ton_mrv_target_list_v2_2026-04-22.md",
            "Welfare-ton MRV target list exists",
        ),
    ]
    return [f"{label}: `{path}`" for path, label in candidates if path.exists()]


def choose_next_move(
    *,
    agentops: list[AgentOpsReport],
    cost: CostSnapshot,
    yds: list[HumanYDSRating],
    revenue: list[str],
) -> str:
    if not yds:
        return (
            "Register one human YDS rating for today's highest-value artifact; "
            "do not let AI self-grade it."
        )
    if not agentops:
        return "Run the next repo task through an AgentOps packet so the brief has gate evidence."
    if cost.calls == 0:
        return "Wire existing cost/traces into this brief before spending another long agent run."
    if revenue:
        return "Pick one revenue artifact and turn it into a dated outreach or submission action."
    return "Keep the next move small: one packet, one proof artifact, one verification report."


def _render_git(snapshot: GitSnapshot) -> list[str]:
    if snapshot.error:
        return [f"- Git snapshot unavailable: {snapshot.error}"]
    lines = [
        f"- Branch: `{snapshot.branch}`",
        f"- Head: `{snapshot.head}`",
    ]
    if snapshot.dirty_files:
        lines.append(f"- Dirty state: {len(snapshot.dirty_files)} item(s)")
        lines.extend(f"  - `{entry}`" for entry in snapshot.dirty_files[:8])
    else:
        lines.append("- Dirty state: clean")
    return lines


def _render_manifest(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["- Active surface manifest: missing or unreadable."]
    rendered = ", ".join(f"{name}={count}" for name, count in counts.items())
    return [f"- Active surface manifest status counts: {rendered}."]


def _render_named_lines(label: str, items: list[str]) -> list[str]:
    if not items:
        return [f"- {label}: no local source lines found."]
    return [f"- {label}: {item}" for item in items]


def _render_agentops(reports: list[AgentOpsReport]) -> list[str]:
    if not reports:
        return ["- No AgentOps run reports found under `.dharma/agentops/runs`."]
    status_counts = Counter(report.status for report in reports)
    lines = [
        "- Recent AgentOps reports: "
        + ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    ]
    for report in reports[:3]:
        failed = f", failed={','.join(report.failed_commands)}" if report.failed_commands else ""
        lines.append(
            "- "
            f"`{report.packet_id}` status={report.status} "
            f"commands={report.command_count} violations={report.violation_count}"
            f"{failed}"
        )
    return lines


def _render_cost(snapshot: CostSnapshot, *, since_hours: float) -> list[str]:
    if snapshot.calls == 0:
        lines = [f"- No cost entries found in the last {since_hours:.0f}h."]
    else:
        lines = [
            (
                "- "
                f"{snapshot.calls} call(s), ${snapshot.total_cost_usd:.4f}, "
                f"{snapshot.input_tokens:,} input tokens, "
                f"{snapshot.output_tokens:,} output tokens."
            ),
            "- Providers: " + ", ".join(f"{k}={v}" for k, v in snapshot.by_provider.items()),
            "- Tiers: " + ", ".join(f"{k}={v}" for k, v in snapshot.by_tier.items()),
        ]
    if snapshot.malformed_lines:
        lines.append(f"- Skipped malformed cost lines: {snapshot.malformed_lines}.")
    return lines


def _render_value(ontology: OntologyCounts, reports: list[AgentOpsReport]) -> list[str]:
    lines: list[str] = []
    if ontology.error:
        lines.append(f"- Ontology counts unavailable: {ontology.error}")
    elif ontology.counts:
        lines.append(
            "- Ontology counts: "
            + ", ".join(f"{name}={count}" for name, count in ontology.counts.items())
        )
    else:
        lines.append("- Ontology counts: no local ontology database found.")

    passed_packets = [report.packet_id for report in reports if report.status == "passed"]
    if passed_packets:
        lines.append("- Verified packet evidence: " + ", ".join(f"`{item}`" for item in passed_packets[:5]))
    else:
        lines.append("- Verified packet evidence: none found.")
    return lines


def _render_yds(ratings: list[HumanYDSRating]) -> list[str]:
    if not ratings:
        return ["- No human YDS ratings found. AI must not invent authoritative grades."]
    return [
        "- "
        f"`{rating.grade}` {rating.target}: "
        f"{rating.note or 'no note'}"
        f" ({rating.timestamp or rating.source})"
        for rating in ratings
    ]


def _render_revenue(signals: list[str]) -> list[str]:
    if not signals:
        return ["- No concrete revenue/self-funding artifacts found in configured sources."]
    return [f"- {signal}" for signal in signals]


def _render_stop_doing(hot_items: list[str]) -> list[str]:
    if hot_items:
        return [
            "- Do not expand dashboard/API/autonomy surfaces while these hot items remain unresolved.",
            "- Treat decorative or placeholder surfaces as stop-doing candidates unless tied to proof.",
        ]
    return [
        "- No hot-items source found; avoid broad new architecture until a source-of-truth map is present.",
    ]


class BriefSourceError(Exception):
    """A local brief source could not be read."""


def _git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise BriefSourceError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _read_jsonl(path: Path) -> list[dict[str, Any] | None]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any] | None] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            rows.append(None)
            continue
        rows.append(row if isinstance(row, dict) else None)
    return rows


def _parse_yds_json_line(line: str, *, source: str) -> HumanYDSRating | None:
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict):
        return None
    grade = str(row.get("grade") or "").strip()
    target = str(row.get("target") or row.get("target_path") or "").strip()
    if not grade or not target:
        return None
    return HumanYDSRating(
        target=target,
        grade=grade,
        note=str(row.get("note") or "").strip(),
        timestamp=str(row.get("timestamp") or row.get("date") or "").strip(),
        source=source,
    )


_YDS_COMMAND_RE = re.compile(
    r"^YDS:\s*rate\s+(?P<target>\S+)\s+(?P<grade>5\.\d{2}[a-d]?)\s*(?:[-:]\s*)?(?P<note>.*)$",
    flags=re.IGNORECASE,
)


def _parse_yds_command_line(line: str, *, source: str) -> HumanYDSRating | None:
    match = _YDS_COMMAND_RE.match(line)
    if match is None:
        return None
    return HumanYDSRating(
        target=match.group("target"),
        grade=match.group("grade"),
        note=match.group("note").strip(),
        timestamp="",
        source=source,
    )


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the read-only Daily Operating Brief v0.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect")
    parser.add_argument("--state-dir", help="State directory to inspect; defaults to ~/.dharma")
    parser.add_argument("--output-dir", help="Directory for the markdown brief")
    parser.add_argument("--since-hours", type=float, default=DEFAULT_SINCE_HOURS)
    parser.add_argument("--stdout", action="store_true", help="Print the brief instead of writing it")
    args = parser.parse_args(argv)

    brief = build_daily_operating_brief(
        repo_root=args.repo_root,
        state_dir=args.state_dir,
        output_dir=args.output_dir,
        since_hours=args.since_hours,
        write=not args.stdout,
    )
    if args.stdout:
        print(brief.content)
    elif brief.path is not None:
        print(brief.path)
    return 0


__all__ = [
    "AgentOpsReport",
    "CostSnapshot",
    "GitSnapshot",
    "HumanYDSRating",
    "OntologyCounts",
    "OperatingBrief",
    "build_daily_operating_brief",
    "choose_next_move",
    "extract_markdown_section",
    "load_agentops_reports",
    "load_cost_snapshot",
    "load_git_snapshot",
    "load_manifest_status_counts",
    "load_ontology_counts",
    "load_revenue_signals",
    "load_yds_ratings",
    "main",
    "render_daily_operating_brief",
]


if __name__ == "__main__":
    raise SystemExit(main())
