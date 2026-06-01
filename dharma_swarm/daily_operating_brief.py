"""Daily Operating Brief v0 for local operator review.

This module intentionally stays path-injected and read-only by default. It
summarizes existing evidence files into a markdown brief without becoming a
dashboard, runtime authority, ontology migration, or memory writer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.llm_burn import load_llm_burn_rollup


REVENUE_KEYWORDS = (
    "revenue",
    "wedge",
    "grant",
    "customer",
    "stripe",
    "gumroad",
    "mrr",
    "burn",
    "runway",
    "sell",
)

HUMAN_SOURCE_MARKERS = ("human", "operator", "dhyana")


@dataclass(frozen=True)
class DailyOperatingBriefInputs:
    """Explicit source paths for a Daily Operating Brief build."""

    agentops_reports_dir: Path | None = None
    kaizen_reports_dir: Path | None = None
    yds_ratings_path: Path | None = None
    cost_report_path: Path | None = None
    llm_burn_state_dir: Path | None = None
    docops_check_report_path: Path | None = None
    docops_inventory_path: Path | None = None
    hot_items_path: Path | None = None
    revenue_notes_path: Path | None = None
    now: datetime | None = None
    llm_burn_since_hours: float = 24.0


@dataclass(frozen=True)
class DailyOperatingBrief:
    """A practical operator brief assembled from local evidence."""

    date: str
    what_happened: list[str] = field(default_factory=list)
    gate_health: list[str] = field(default_factory=list)
    value_produced: list[str] = field(default_factory=list)
    burn_cost_signals: list[str] = field(default_factory=list)
    human_yds_ratings: list[str] = field(default_factory=list)
    revenue_moves: list[str] = field(default_factory=list)
    stop_doing: list[str] = field(default_factory=list)
    next_highest_leverage_move: list[str] = field(default_factory=list)
    doc_integrity_signals: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)


def build_daily_operating_brief(
    inputs: DailyOperatingBriefInputs,
) -> DailyOperatingBrief:
    """Build a Daily Operating Brief from explicit local evidence paths."""

    now = inputs.now or datetime.now(timezone.utc)
    missing: list[str] = []
    what_happened, gate_health, value_produced, stop_doing = _agentops_sections(
        inputs.agentops_reports_dir,
        missing,
    )
    kaizen_lines = _kaizen_lines(inputs.kaizen_reports_dir, missing)
    if kaizen_lines:
        value_produced.extend(kaizen_lines)

    yds_lines = _yds_lines(inputs.yds_ratings_path, missing)
    burn_lines = _burn_lines(
        cost_report_path=inputs.cost_report_path,
        llm_burn_state_dir=inputs.llm_burn_state_dir,
        now=now,
        since_hours=inputs.llm_burn_since_hours,
        missing=missing,
    )
    doc_integrity_lines = _docops_lines(
        check_report_path=inputs.docops_check_report_path,
        inventory_path=inputs.docops_inventory_path,
        missing=missing,
    )
    revenue_lines = _revenue_lines(inputs.revenue_notes_path, missing)
    hot_stop, hot_next = _hot_item_lines(inputs.hot_items_path, missing)

    stop_doing.extend(hot_stop)
    next_move = _next_move(
        gate_health,
        what_happened,
        hot_next,
        burn_lines,
        doc_integrity_lines,
    )

    return DailyOperatingBrief(
        date=now.date().isoformat(),
        what_happened=_with_default(what_happened, "No operating events found."),
        gate_health=_with_default(gate_health, "No gate health evidence found."),
        value_produced=_with_default(value_produced, "No value-produced evidence found."),
        burn_cost_signals=burn_lines,
        human_yds_ratings=yds_lines,
        revenue_moves=revenue_lines,
        stop_doing=_with_default(stop_doing, "No stop-doing signal found."),
        next_highest_leverage_move=[next_move],
        doc_integrity_signals=doc_integrity_lines,
        missing_sources=missing or ["No missing sources detected."],
    )


def render_markdown(brief: DailyOperatingBrief) -> str:
    """Render a Daily Operating Brief as markdown."""

    sections = [
        ("1. What happened", brief.what_happened),
        ("2. Gate health", brief.gate_health),
        ("3. Value produced", brief.value_produced),
        ("4. Burn / cost signals", brief.burn_cost_signals),
        ("5. Human YDS ratings", brief.human_yds_ratings),
        ("6. Revenue / self-funding moves", brief.revenue_moves),
        ("7. Stop doing", brief.stop_doing),
        ("8. Next highest-leverage move", brief.next_highest_leverage_move),
        ("9. Doc drift / claim integrity", brief.doc_integrity_signals),
        ("10. Missing sources", brief.missing_sources),
    ]
    lines = [f"# Daily Operating Brief {brief.date}", ""]
    for title, items in sections:
        lines.extend([f"## {title}", ""])
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_daily_operating_brief(
    inputs: DailyOperatingBriefInputs,
    output_path: Path,
) -> Path:
    """Build and write a Daily Operating Brief to an explicit output path."""

    brief = build_daily_operating_brief(inputs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(brief), encoding="utf-8")
    return output_path


def _agentops_sections(
    reports_dir: Path | None,
    missing: list[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    what_happened: list[str] = []
    gate_health: list[str] = []
    value_produced: list[str] = []
    stop_doing: list[str] = []

    reports = _json_reports(reports_dir, "report.json")
    if not reports:
        missing.append("AgentOps reports")
        what_happened.append("No AgentOps reports found.")
        gate_health.append("No AgentOps gate reports found.")
        return what_happened, gate_health, value_produced, stop_doing

    for path, report in reports:
        job_id = _string(report.get("job_id") or path.parent.parent.name or "unknown-job")
        branch = _string(report.get("branch") or "unknown-branch")
        worktree = _string(report.get("worktree") or "unknown-worktree")
        status = _string(report.get("status") or "unknown")
        commit_hash = _string(report.get("commit_hash") or "")
        scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
        scope_passed = bool(scope.get("passed")) if scope else False
        gates = report.get("gates") if isinstance(report.get("gates"), list) else []
        failed_gates = [
            gate for gate in gates
            if isinstance(gate, dict) and not bool(gate.get("passed"))
        ]

        commit_note = f", commit `{commit_hash}`" if commit_hash else ", no commit candidate"
        what_happened.append(
            f"AgentOps `{job_id}` ended `{status}` on `{branch}` in `{worktree}`{commit_note}."
        )

        if failed_gates or not scope_passed or status != "passed":
            failed = ", ".join(
                f"{_string(g.get('name') or 'unnamed')} exit {_string(g.get('exit_code'))}"
                for g in failed_gates
            )
            detail = failed or "scope/status failed"
            gate_health.append(f"AgentOps `{job_id}` not all green: {detail}.")
            stop_doing.append(f"Stop integrating `{job_id}` until its gate/scope failure is resolved.")
        else:
            gate_health.append(f"AgentOps `{job_id}` all green: {len(gates)} gate(s), scope passed.")

        changed_files = scope.get("changed_files") if isinstance(scope, dict) else None
        changed_count = len(changed_files) if isinstance(changed_files, list) else 0
        if commit_hash:
            value_produced.append(f"AgentOps `{job_id}` produced commit candidate `{commit_hash}`.")
        elif changed_count:
            value_produced.append(f"AgentOps `{job_id}` produced {changed_count} changed file(s) pending review.")
        else:
            value_produced.append(f"AgentOps `{job_id}` recorded no changed files.")

    return what_happened, gate_health, value_produced, stop_doing


def _kaizen_lines(reports_dir: Path | None, missing: list[str]) -> list[str]:
    reports = _json_reports(reports_dir, "kaizen_review.json")
    if not reports:
        missing.append("KaizenReview reports")
        return ["No KaizenReview reports found."]

    lines: list[str] = []
    for path, report in reports:
        label = _string(
            report.get("artifact")
            or report.get("title")
            or report.get("id")
            or path.parent.name
        )
        status = _string(report.get("status") or report.get("verdict") or "recorded")
        score = report.get("score") or report.get("quality_score") or report.get("forge_score")
        suffix = f", advisory score `{score}`" if score is not None else ""
        suffix += _kaizen_runtime_suffix(report)
        lines.append(f"KaizenReview `{label}` {status}{suffix}.")
    return lines


def _kaizen_runtime_suffix(report: dict[str, Any]) -> str:
    summary = report.get("runtime_truth_summary")
    if not isinstance(summary, dict):
        return ""
    jobs_with_refs = _intish(summary.get("jobs_with_refs"))
    jobs_without_refs = _intish(summary.get("jobs_without_refs"))
    total = jobs_with_refs + jobs_without_refs
    if not total:
        return ""
    return f", runtime refs `{jobs_with_refs}/{total}`"


def _yds_lines(path: Path | None, missing: list[str]) -> list[str]:
    records = _load_records(path)
    if records is None:
        missing.append("YDS ratings ledger")
        return ["No human YDS ratings found."]
    if not records:
        return ["No human YDS ratings found."]

    human: list[str] = []
    advisory: list[str] = []
    for record in records:
        source = _string(record.get("source") or "")
        rating = _string(record.get("rating") or record.get("yds") or "")
        if not rating:
            continue
        artifact = _string(record.get("artifact") or "unknown artifact")
        comment = _string(record.get("human_comment") or record.get("comment") or "")
        timestamp = _string(record.get("timestamp") or "")
        line = f"`{artifact}` rated `{rating}`"
        if timestamp:
            line += f" at {timestamp}"
        if comment:
            line += f": {comment}"
        if _is_human_source(source):
            human.append(line)
        else:
            advisory.append(f"Advisory only, non-human source `{source or 'unknown'}`: {line}.")

    if human:
        return human + advisory[:3]
    if advisory:
        return ["No human YDS ratings found.", *advisory[:3]]
    return ["No human YDS ratings found."]


def _burn_lines(
    *,
    cost_report_path: Path | None,
    llm_burn_state_dir: Path | None,
    now: datetime,
    since_hours: float,
    missing: list[str],
) -> list[str]:
    if cost_report_path is None and llm_burn_state_dir is None:
        missing.append("Burn/cost source")
        return ["No burn source found."]

    lines: list[str] = []
    if cost_report_path is not None:
        lines.extend(_cost_lines(cost_report_path, missing))
    if llm_burn_state_dir is not None:
        lines.extend(_llm_burn_lines(llm_burn_state_dir, now=now, since_hours=since_hours, missing=missing))

    return lines or ["No burn source found."]


def _cost_lines(path: Path, missing: list[str]) -> list[str]:
    records = _load_records(path)
    if records is None:
        missing.append("Burn/cost source")
        return ["No burn source found."]
    if not records:
        return ["No burn source found."]

    total_cost = 0.0
    saw_cost = False
    total_tokens = 0
    saw_tokens = False
    labels: list[str] = []
    for record in records:
        cost = _first_number(
            record,
            ("estimated_cost_usd", "cost_usd", "amount_usd", "total_cost_usd"),
        )
        if cost is not None:
            total_cost += cost
            saw_cost = True
        tokens = _token_total(record)
        if tokens is not None:
            total_tokens += tokens
            saw_tokens = True
        label = _record_label(record)
        if label:
            labels.append(label)

    lines: list[str] = []
    if saw_cost:
        lines.append(f"Cost source: {len(records)} record(s), ${total_cost:.4f} observed.")
    if saw_tokens:
        lines.append(f"Token signal: {total_tokens:,} token(s) observed.")
    if labels:
        lines.append(f"Notable burn records: {'; '.join(labels[:3])}.")
    if not lines:
        lines.append("Cost source present, but no explicit cost or token fields were found.")
    return lines


def _llm_burn_lines(
    state_dir: Path,
    *,
    now: datetime,
    since_hours: float,
    missing: list[str],
) -> list[str]:
    if not state_dir.exists():
        missing.append("LLM burn state directory")
        return []

    rollup = load_llm_burn_rollup(state_dir, now=now, since_hours=since_hours)
    if rollup.spans == 0:
        return [f"OpenInference-style LLM burn spans: none found in the last {since_hours:.0f}h."]

    lines = [
        (
            "OpenInference-style LLM burn spans: "
            f"{rollup.spans} span(s), recorded=${rollup.logged_cost_usd:.4f}, "
            f"estimated=${rollup.estimated_cost_usd:.4f}, "
            f"tokens={rollup.total_tokens:,}, "
            f"errors={rollup.error_spans}, "
            f"zero-token={rollup.zero_token_spans}, "
            f"unpriced={rollup.unpriced_spans}."
        )
    ]
    if rollup.by_source:
        lines.append(
            "LLM burn sources: "
            + ", ".join(f"{source}={count}" for source, count in rollup.by_source.items())
            + "."
        )
    if rollup.by_cost_source:
        lines.append(
            "LLM burn cost sources: "
            + ", ".join(f"{source}={count}" for source, count in rollup.by_cost_source.items())
            + "."
        )
    if rollup.top_failure_provider or rollup.top_failure_model:
        lines.append(
            "LLM failure hot spot: "
            f"provider={rollup.top_failure_provider or 'n/a'}, "
            f"model={rollup.top_failure_model or 'n/a'}."
        )
    return lines


def _revenue_lines(path: Path | None, missing: list[str]) -> list[str]:
    if path is None or not path.exists():
        missing.append("Revenue notes")
        return ["No revenue source found."]
    text = path.read_text(encoding="utf-8")
    matches = [
        _clean_bullet(line)
        for line in text.splitlines()
        if _contains_keyword(line, REVENUE_KEYWORDS)
    ]
    matches = [line for line in matches if line]
    if not matches:
        return ["Revenue source present, but no revenue/self-funding lines matched v0 keywords."]
    return matches[:8]


def _docops_lines(
    *,
    check_report_path: Path | None,
    inventory_path: Path | None,
    missing: list[str],
) -> list[str]:
    lines: list[str] = []

    if check_report_path is None or not check_report_path.exists():
        missing.append("DocOps integrity report")
        lines.append("No DocOps integrity report found.")
    else:
        report = _read_json(check_report_path)
        if isinstance(report, dict):
            lines.extend(_docops_check_lines(report))
        else:
            lines.append("DocOps integrity report present, but unreadable.")

    if inventory_path is None or not inventory_path.exists():
        missing.append("DocOps corpus inventory")
        lines.append("No DocOps corpus inventory found.")
    else:
        inventory = _read_json(inventory_path)
        if isinstance(inventory, dict):
            lines.extend(_docops_inventory_lines(inventory))
        else:
            lines.append("DocOps corpus inventory present, but unreadable.")

    return lines


def _docops_check_lines(report: dict[str, Any]) -> list[str]:
    passed = bool(report.get("passed"))
    status = "passed" if passed else "failed"
    failures = _intish(report.get("failure_count"))
    warnings = _intish(report.get("warning_count"))
    date = _string(report.get("date"))
    date_note = f" on {date}" if date else ""
    lines = [
        (
            f"DocOps integrity {status}{date_note}: "
            f"{failures} failure(s), {warnings} warning(s)."
        )
    ]

    metrics = report.get("metrics")
    if isinstance(metrics, dict):
        markdown_files = _intish(metrics.get("markdown_files"))
        authority_docs = _intish(metrics.get("authority_candidate_docs"))
        assertions = _intish(metrics.get("doc_assertions"))
        if markdown_files or authority_docs or assertions:
            details = []
            if markdown_files:
                details.append(f"{markdown_files} markdown file(s)")
            if authority_docs:
                details.append(f"{authority_docs} authority-candidate doc(s)")
            if assertions:
                details.append(f"{assertions} executable assertion(s)")
            lines.append("DocOps metric snapshot: " + ", ".join(details) + ".")

    findings = report.get("findings")
    if isinstance(findings, list) and findings:
        for finding in findings[:3]:
            if isinstance(finding, dict):
                lines.append("DocOps finding: " + _docops_finding_label(finding) + ".")
    return lines


def _docops_inventory_lines(inventory: dict[str, Any]) -> list[str]:
    details = []
    for key, label in (
        ("markdown_files", "markdown file(s) indexed"),
        ("markdown_file_count", "markdown file(s) indexed"),
        ("absolute_path_ref_count", "absolute path reference(s)"),
        ("path_ref_count", "path reference(s)"),
        ("broken_path_ref_count", "broken path reference(s)"),
        ("canonical_claim_count", "canonical/source-of-truth claim(s)"),
    ):
        value = _intish(inventory.get(key))
        if value:
            details.append(f"{value} {label}")
    if details:
        return ["DocOps corpus inventory: " + ", ".join(details[:4]) + "."]
    return ["DocOps corpus inventory present."]


def _docops_finding_label(finding: dict[str, Any]) -> str:
    rule = _string(
        finding.get("rule")
        or finding.get("rule_id")
        or finding.get("kind")
        or finding.get("type")
        or "unlabeled"
    )
    path = _string(finding.get("path") or finding.get("file") or "")
    message = _string(finding.get("message") or finding.get("detail") or "")
    parts = [rule]
    if path:
        parts.append(path)
    if message:
        parts.append(message)
    return " - ".join(parts)


def _hot_item_lines(path: Path | None, missing: list[str]) -> tuple[list[str], list[str]]:
    if path is None or not path.exists():
        missing.append("Hot items")
        return [], []
    stop_lines: list[str] = []
    next_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = _clean_bullet(line)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if "[ ]" in line and len(next_lines) < 3:
            next_lines.append(cleaned.replace("[ ] ", ""))
        if any(marker in lowered for marker in ("do not", "stop ", "must fix")):
            stop_lines.append(cleaned)
        if len(stop_lines) >= 5 and len(next_lines) >= 3:
            break
    return stop_lines[:5], next_lines[:3]


def _next_move(
    gate_health: list[str],
    what_happened: list[str],
    hot_next: list[str],
    burn_lines: list[str],
    doc_integrity_lines: list[str],
) -> str:
    if any("not all green" in line for line in gate_health):
        return "Fix the first failed AgentOps gate or scope violation before expanding work."
    if any("DocOps integrity failed" in line for line in doc_integrity_lines):
        return "Fix DocOps integrity failures before adding or promoting more documentation."
    if any("No AgentOps reports found." in line for line in what_happened):
        return "Run one bounded AgentOps work packet and feed its report into tomorrow's brief."
    if any(re.search(r"unpriced=[1-9]", line) for line in burn_lines):
        return "Close the unpriced LLM span gap before scaling another long autonomous run."
    if hot_next:
        return hot_next[0]
    return "Pick one bounded, tested operating improvement and capture its evidence through AgentOps."


def _json_reports(root: Path | None, filename: str) -> list[tuple[Path, dict[str, Any]]]:
    if root is None or not root.exists():
        return []
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob(f"**/{filename}")):
        data = _read_json(path)
        if isinstance(data, dict):
            reports.append((path, data))
    return reports


def _load_records(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None or not path.exists():
        return None
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(data)
        return records

    data = _read_json(path)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("entries", "records", "costs", "ratings"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    return []


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _with_default(lines: list[str], fallback: str) -> list[str]:
    return lines if lines else [fallback]


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_human_source(source: str) -> bool:
    lowered = source.lower()
    return any(marker in lowered for marker in HUMAN_SOURCE_MARKERS)


def _first_number(record: dict[str, Any], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _intish(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _token_total(record: dict[str, Any]) -> int | None:
    total = _first_number(record, ("tokens", "total_tokens", "token_count"))
    if total is not None:
        return int(total)
    input_tokens = _first_number(record, ("input_tokens", "prompt_tokens"))
    output_tokens = _first_number(record, ("output_tokens", "completion_tokens"))
    if input_tokens is None and output_tokens is None:
        return None
    return int(input_tokens or 0) + int(output_tokens or 0)


def _record_label(record: dict[str, Any]) -> str:
    parts = [
        _string(record.get("provider")),
        _string(record.get("model")),
        _string(record.get("task_id") or record.get("agent_name") or record.get("description")),
    ]
    return " / ".join(part for part in parts if part)


def _contains_keyword(line: str, keywords: Iterable[str]) -> bool:
    lowered = line.lower()
    return any(keyword in lowered for keyword in keywords)


def _clean_bullet(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned)
    return cleaned.strip()


__all__ = [
    "DailyOperatingBrief",
    "DailyOperatingBriefInputs",
    "build_daily_operating_brief",
    "render_markdown",
    "write_daily_operating_brief",
]
