"""Daily Operating Brief built from encapsulated operating facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.operator_core.operating_facts import (
    OperatingFactBundle,
    OperatingFactInputs,
    build_operating_fact_bundle,
    organ_state_facts,
)


@dataclass(frozen=True)
class DailyOperatingBriefInputs(OperatingFactInputs):
    """Explicit local inputs for a read-only Daily Operating Brief build."""

    now: datetime | None = None


@dataclass(frozen=True)
class DailyOperatingBrief:
    date: str
    what_happened: list[str] = field(default_factory=list)
    gate_health: list[str] = field(default_factory=list)
    value_produced: list[str] = field(default_factory=list)
    burn_cost_signals: list[str] = field(default_factory=list)
    human_yds_ratings: list[str] = field(default_factory=list)
    revenue_moves: list[str] = field(default_factory=list)
    stop_doing: list[str] = field(default_factory=list)
    coherence_state: list[str] = field(default_factory=list)
    next_highest_leverage_move: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)


def build_daily_operating_brief(inputs: DailyOperatingBriefInputs) -> DailyOperatingBrief:
    """Build a practical operator brief from canonical operating facts."""

    now = inputs.now or datetime.now(timezone.utc)
    bundle = build_operating_fact_bundle(
        OperatingFactInputs(
            agentops_reports_dir=inputs.agentops_reports_dir,
            kaizen_reports_dir=inputs.kaizen_reports_dir,
            yds_ratings_path=inputs.yds_ratings_path,
            burn_report_path=inputs.burn_report_path,
            revenue_notes_path=inputs.revenue_notes_path,
        )
    )
    what_happened = _what_happened(bundle)
    gate_health = _gate_health(bundle)
    value_produced = _value_produced(bundle)
    burn = _burn_lines(bundle)
    yds = _yds_lines(bundle)
    revenue = _revenue_lines(bundle)
    stop_doing = _stop_doing(bundle)
    coherence_state = _coherence_lines(bundle)
    next_move = _next_move(bundle)
    return DailyOperatingBrief(
        date=now.date().isoformat(),
        what_happened=_with_default(what_happened, "No operating events found."),
        gate_health=_with_default(gate_health, "No gate health evidence found."),
        value_produced=_with_default(value_produced, "No value-produced evidence found."),
        burn_cost_signals=_with_default(burn, "No burn source found."),
        human_yds_ratings=_with_default(yds, "No human YDS ratings found."),
        revenue_moves=_with_default(revenue, "No revenue source found."),
        stop_doing=_with_default(stop_doing, "No stop-doing signal found."),
        coherence_state=_with_default(coherence_state, "No coherence drift found."),
        next_highest_leverage_move=[next_move],
        missing_sources=list(bundle.missing_sources) or ["No missing sources detected."],
    )


def render_markdown(brief: DailyOperatingBrief) -> str:
    sections = [
        ("1. What happened", brief.what_happened),
        ("2. Gate health", brief.gate_health),
        ("3. Value produced", brief.value_produced),
        ("4. Burn / cost signals", brief.burn_cost_signals),
        ("5. Human YDS ratings", brief.human_yds_ratings),
        ("6. Revenue / self-funding moves", brief.revenue_moves),
        ("7. Stop doing", brief.stop_doing),
        ("8. Coherence state", brief.coherence_state),
        ("9. Next highest-leverage move", brief.next_highest_leverage_move),
        ("10. Missing sources", brief.missing_sources),
    ]
    lines = [f"# Daily Operating Brief {brief.date}", ""]
    for title, items in sections:
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_daily_operating_brief(inputs: DailyOperatingBriefInputs, output_path: Path) -> Path:
    brief = build_daily_operating_brief(inputs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(brief), encoding="utf-8")
    return output_path


def _what_happened(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for run in bundle.agentops:
        commit = f", commit `{run.commit_hash}`" if run.commit_hash else ", no commit"
        lines.append(
            f"AgentOps `{run.job_id}` ended `{run.status}` on `{run.branch}`{commit}."
        )
    for review in bundle.kaizen:
        lines.append(
            f"KaizenReview consumed {review.jobs_reviewed} job(s); next `{review.next_recommendation or 'unknown'}`."
        )
    return lines


def _gate_health(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for run in bundle.agentops:
        if run.gate_state == "all_green" and run.scope_state == "scope_clean":
            lines.append(f"AgentOps `{run.job_id}` all green with clean scope.")
        elif run.gate_state == "some_red":
            failed = ", ".join(run.failed_gates) or "unknown gate"
            lines.append(f"AgentOps `{run.job_id}` has red gate(s): {failed}.")
        elif run.scope_state == "scope_violation":
            violations = ", ".join(run.scope_violations) or "unknown file"
            lines.append(f"AgentOps `{run.job_id}` has scope violation(s): {violations}.")
        else:
            lines.append(f"AgentOps `{run.job_id}` gate/scope state is unknown.")
    return lines


def _value_produced(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for run in bundle.agentops:
        if run.commit_hash:
            lines.append(f"AgentOps `{run.job_id}` produced commit candidate `{run.commit_hash}`.")
        elif run.changed_files:
            lines.append(f"AgentOps `{run.job_id}` produced {len(run.changed_files)} changed file(s).")
        else:
            lines.append(f"AgentOps `{run.job_id}` recorded no changed files.")
    for review in bundle.kaizen:
        if review.playbook_update_candidates:
            lines.append(
                "KaizenReview surfaced playbook candidate: "
                + review.playbook_update_candidates[0]
            )
    return lines


def _burn_lines(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for burn in bundle.burn:
        bits = [f"Burn source `{burn.label}`"]
        if burn.total_cost_usd is not None:
            bits.append(f"${burn.total_cost_usd:.4f}")
        if burn.total_tokens is not None:
            bits.append(f"{burn.total_tokens} token(s)")
        if burn.unpriced_span_count:
            bits.append(f"{burn.unpriced_span_count} unpriced span(s)")
        lines.append(": ".join([bits[0], ", ".join(bits[1:])]) if len(bits) > 1 else bits[0])
    return lines


def _yds_lines(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for rating in bundle.human_yds:
        prefix = "Human" if rating.authoritative else "Advisory"
        note = f": {rating.human_note}" if rating.human_note else ""
        lines.append(f"{prefix} YDS `{rating.rating}` for `{rating.artifact_uri}`{note}")
    return lines


def _revenue_lines(bundle: OperatingFactBundle) -> list[str]:
    return [
        f"`{signal.line}` ({', '.join(signal.keywords)})"
        for signal in bundle.revenue[:5]
    ]


def _stop_doing(bundle: OperatingFactBundle) -> list[str]:
    items: list[str] = []
    for run in bundle.agentops:
        if run.gate_state == "some_red":
            items.append(f"Do not expand `{run.job_id}` until failed gates are fixed.")
        if run.scope_state == "scope_violation":
            items.append(f"Do not integrate `{run.job_id}` until scope is narrowed or split.")
    for review in bundle.kaizen:
        items.extend(review.stop_doing_items)
    for burn in bundle.burn:
        if burn.unpriced_span_count:
            items.append("Do not scale long agent runs while LLM spans remain unpriced.")
    return items


def _coherence_lines(bundle: OperatingFactBundle) -> list[str]:
    lines: list[str] = []
    for fact in organ_state_facts(bundle):
        if fact.coherence_state in {"drifted", "unknown", "declared_only"}:
            gap = f": {fact.open_gap}" if fact.open_gap else ""
            lines.append(f"`{fact.name}` is `{fact.coherence_state}`{gap}")
    return lines


def _next_move(bundle: OperatingFactBundle) -> str:
    if not bundle.agentops:
        return "run one bounded AgentOps packet and feed its report into KaizenReview"
    for run in bundle.agentops:
        if run.gate_state == "some_red":
            return f"fix failed gate(s) for AgentOps `{run.job_id}`"
    for run in bundle.agentops:
        if run.scope_state == "scope_violation":
            return f"repeat AgentOps `{run.job_id}` with narrower allowed_files"
    for burn in bundle.burn:
        if burn.unpriced_span_count:
            return "close the LLM pricing gap before scaling another autonomous run"
    for review in bundle.kaizen:
        if review.next_recommendation:
            return review.next_recommendation
    if not any(rating.authoritative for rating in bundle.human_yds):
        return "request one human YDS rating for the most useful artifact"
    return "promote the green packet pattern into the next bounded work packet"


def _with_default(items: list[str], fallback: str) -> list[str]:
    return items if items else [fallback]
