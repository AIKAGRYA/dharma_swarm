"""Render Forge Lab operator-history scorecards and source links."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from dharma_swarm.forge_lab.operator_history_sources import (
    HISTORY_ROW_SCHEMA,
    _display_state,
    _first,
    _format_count,
    _format_duration,
    _format_rate,
    _get,
    _mapping,
    _parse_time,
    _sequence,
    _slug,
)


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_text(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if executable:
            path.chmod(0o755)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def _safe_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target)


def _scorecard_table(scorecard: Mapping[str, Any]) -> str:
    metrics = _mapping(scorecard.get("metrics"))
    quality = _mapping(metrics.get("quality"))
    lineage = _mapping(metrics.get("lineage"))
    evaluation = _mapping(metrics.get("evaluation"))
    usage = _mapping(metrics.get("usage"))
    provider = _mapping(metrics.get("provider"))
    runtime = _mapping(metrics.get("runtime"))
    holdout = _mapping(metrics.get("holdout"))
    provenance = _mapping(metrics.get("provenance"))
    integrity = _mapping(metrics.get("integrity"))
    verdict = _mapping(metrics.get("verdict"))
    models = (
        ", ".join(str(item) for item in _sequence(provider.get("models"))) or "unknown"
    )
    quality_text = f"{_format_rate(quality.get('seed_pass_rate'))} → {_format_rate(quality.get('best_pass_rate'))}"
    budget_state = quality.get("budget_evidence_state")
    if budget_state == "no_budget_valid_rows":
        quality_text += " — **INVALID FOR LIFT: 0 budget-valid rows**"
    elif budget_state in {"partially_budget_invalid", "incomplete_budget_validity"}:
        quality_text += " — **BUDGET-QUALIFIED / PARTIAL**"
    evaluation_text = (
        f"{_format_count(evaluation.get('solved_observations'))}/"
        f"{_format_count(evaluation.get('task_observations'))} passed observations"
    )
    calls = provider.get("logical_requests")
    calls_text = (
        "unknown"
        if calls is None
        else f"{_format_count(calls)} ({_format_count(provider.get('successful_requests'))} ok / {_format_count(provider.get('failed_requests'))} failed)"
    )
    usage_text = _format_count(usage.get("reported_tokens"))
    if usage.get("is_lower_bound") is True and usage_text != "unknown":
        usage_text = f"≥{usage_text}"
    return "\n".join(
        [
            "| # | Metric | Value |",
            "|---:|---|---|",
            f"| 1 | Verdict | **{_display_state(verdict.get('state'))}**; promotion: {_display_state(verdict.get('promotion'))} |",
            f"| 2 | Quality | {quality_text}; lift {_format_rate(quality.get('absolute_lift'))} |",
            f"| 3 | Lineage | {_format_count(lineage.get('unique_candidate_ids'))} unique candidates, {_format_count(lineage.get('unique_child_ids'))} descendants, depth {_format_count(lineage.get('maximum_generation'))} |",
            f"| 4 | Evaluation | {_format_count(evaluation.get('accepted_graded_rows'))} accepted graded rows; {evaluation_text} |",
            f"| 5 | Usage | {usage_text} reported tokens; actual USD **unknown** |",
            f"| 6 | Provider | {models}; calls {calls_text} |",
            f"| 7 | Runtime | {_format_duration(runtime.get('operator_elapsed_seconds'))} operator elapsed; {_format_duration(runtime.get('active_wall_seconds'))} active |",
            f"| 8 | Holdout | used: {_display_state(holdout.get('used'))}; results: {_format_count(holdout.get('result_occurrences'))} |",
            f"| 9 | Provenance | mode {_display_state(provenance.get('mode'))}; source `{provenance.get('source_git_sha8') or 'unknown'}` |",
            f"| 10 | Integrity | Merkle {_display_state(integrity.get('merkle_verified'))}; scratch removed {_display_state(integrity.get('scratch_removed'))}; warnings {_format_count(integrity.get('warning_count'))} |",
        ]
    )


def _run_readme(scorecard: Mapping[str, Any]) -> str:
    metrics = _mapping(scorecard.get("metrics"))
    verdict = _mapping(metrics.get("verdict"))
    warnings = _sequence(scorecard.get("warnings"))
    warning_section = (
        "\n".join(f"- {warning}" for warning in warnings) or "- None recorded."
    )
    return f"""# {scorecard.get("run_id") or scorecard.get("experiment_id")}

> Generated operator projection. Canonical receipts are linked, never replaced.

- **Started (UTC):** {scorecard.get("started_at") or "unknown"}
- **Finished (UTC):** {scorecard.get("finished_at") or "unknown"}
- **Verdict:** {_display_state(verdict.get("state"))}
- **Descriptive folder:** `{scorecard.get("slug")}`

## Ten-metric scorecard

{_scorecard_table(scorecard)}

## Warnings and evidence limits

{warning_section}

## Read next

- `SCORECARD.json` — machine-readable values and explicit nulls.
- `LINEAGE.md` — phases, retries, parents, and children.
- `SOURCE_ARTIFACTS.md` — canonical receipt locations and link confidence.
- `SOURCE_LINKS/` — symlinks only; raw artifacts are not copied here.
"""


def _lineage_markdown(scorecard: Mapping[str, Any]) -> str:
    experiments = _sequence(scorecard.get("experiments"))
    lines = [
        f"# Lineage and phases — {scorecard.get('run_id') or scorecard.get('experiment_id')}",
        "",
        "Native experiments are phases or attempts beneath the operator session, not separate top-level runs.",
        "",
        "| # | Label | Disposition | Native state | Graded | Score | Tokens | Experiment |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]
    if not experiments:
        lines.append("| — | — | — | — | — | — | — | No linked native experiment |")
    for index, item in enumerate(experiments, start=1):
        data = _mapping(item)
        lines.append(
            "| {index} | {label} | {disposition} | {state} | {graded} | {seed}→{best} | {tokens} | `{experiment_id}` |".format(
                index=index,
                label=data.get("label") or "native",
                disposition=data.get("disposition") or "unknown",
                state=_display_state(data.get("closeout_state")),
                graded=_format_count(data.get("graded_rows")),
                seed=_format_rate(data.get("seed_pass_rate")),
                best=_format_rate(data.get("best_pass_rate")),
                tokens=_format_count(data.get("reported_tokens")),
                experiment_id=data.get("experiment_id"),
            )
        )
    return "\n".join(lines) + "\n"


def _sources_markdown(scorecard: Mapping[str, Any]) -> str:
    provenance = _mapping(_get(scorecard, "metrics", "provenance"))
    lines = [
        f"# Canonical source artifacts — {scorecard.get('run_id') or scorecard.get('experiment_id')}",
        "",
        "> This directory is a projection. The paths below remain source truth.",
        "",
        f"- Operator session: `{provenance.get('operator_session_path') or 'none'}`",
        f"- Operator log: `{provenance.get('operator_log_path') or 'none'}`",
        f"- Native experiment: `{provenance.get('native_experiment_path') or 'see associations below'}`",
        f"- Source Git SHA: `{provenance.get('source_git_sha') or 'unknown'}`",
        "",
        "## Native associations",
        "",
        "| Experiment | Method | Confidence | Source path |",
        "|---|---|---|---|",
    ]
    experiments = _sequence(scorecard.get("experiments"))
    if not experiments:
        lines.append("| — | — | — | No linked native experiment |")
    for item in experiments:
        data = _mapping(item)
        lines.append(
            f"| `{data.get('experiment_id')}` | {data.get('link_method') or 'native-only'} | {data.get('confidence') or 'n/a'} | `{data.get('source_path') or 'missing'}` |"
        )
    return "\n".join(lines) + "\n"


def _history_row(scorecard: Mapping[str, Any], relative_path: str) -> dict[str, Any]:
    metrics = _mapping(scorecard.get("metrics"))
    return {
        "schema": HISTORY_ROW_SCHEMA,
        "run_id": scorecard.get("run_id"),
        "slug": scorecard.get("slug"),
        "started_at": scorecard.get("started_at"),
        "finished_at": scorecard.get("finished_at"),
        "kind": scorecard.get("kind"),
        "verdict": _get(metrics, "verdict", "state"),
        "seed_pass_rate": _get(metrics, "quality", "seed_pass_rate"),
        "best_pass_rate": _get(metrics, "quality", "best_pass_rate"),
        "graded_rows": _get(metrics, "evaluation", "accepted_graded_rows"),
        "task_observations": _get(metrics, "evaluation", "task_observations"),
        "reported_tokens": _get(metrics, "usage", "reported_tokens"),
        "actual_cost_usd": _get(metrics, "usage", "actual_cost_usd"),
        "models": _get(metrics, "provider", "models"),
        "mode": _get(metrics, "provenance", "mode"),
        "source_git_sha": _get(metrics, "provenance", "source_git_sha"),
        "warning_count": _get(metrics, "integrity", "warning_count"),
        "relative_path": relative_path,
    }


def _index_table(entries: Sequence[tuple[dict[str, Any], str]]) -> str:
    lines = [
        "| UTC start | Run | Verdict | Quality | Graded | Passed observations | Tokens | Elapsed | Model | Source |",
        "|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for scorecard, relative_path in entries:
        metrics = _mapping(scorecard["metrics"])
        model_values = _sequence(_get(metrics, "provider", "models"))
        model = (
            ", ".join(str(item).split(":")[-1] for item in model_values) or "unknown"
        )
        quality_display = _format_rate(_get(metrics, "quality", "best_pass_rate"))
        budget_state = _get(metrics, "quality", "budget_evidence_state")
        if quality_display != "unknown" and budget_state == "no_budget_valid_rows":
            quality_display += " — INVALID (0 budget-valid)"
        elif (
            quality_display != "unknown"
            and _get(metrics, "quality", "headline_lift_valid") is False
        ):
            quality_display += " ⚠ partial budget validity"
        token_display = _format_count(_get(metrics, "usage", "reported_tokens"))
        if (
            _get(metrics, "usage", "is_lower_bound") is True
            and token_display != "unknown"
        ):
            token_display = f"≥{token_display}"
        solved = _get(metrics, "evaluation", "solved_observations")
        observations = _get(metrics, "evaluation", "task_observations")
        lines.append(
            "| {started} | [{run}]({path}/README.md) | {verdict} | {quality} | {graded} | {solved}/{observations} | {tokens} | {elapsed} | {model} | `{sha}` |".format(
                started=scorecard.get("started_at") or "undated",
                run=scorecard.get("run_id") or scorecard.get("experiment_id"),
                path=relative_path,
                verdict=_display_state(_get(metrics, "verdict", "state")),
                quality=quality_display,
                graded=_format_count(
                    _get(metrics, "evaluation", "accepted_graded_rows")
                ),
                solved=_format_count(solved),
                observations=_format_count(observations),
                tokens=token_display,
                elapsed=_format_duration(
                    _get(metrics, "runtime", "operator_elapsed_seconds")
                ),
                model=model,
                sha=_get(metrics, "provenance", "source_git_sha8") or "unknown",
            )
        )
    return "\n".join(lines)


def _write_scorecard_directory(
    root: Path,
    scorecard: dict[str, Any],
    source_run: Mapping[str, Any] | None,
) -> str:
    started = _parse_time(scorecard.get("started_at"))
    date = started.strftime("%Y-%m-%d") if started else "undated"
    relative = (
        Path("runs" if source_run else "native-only") / date / str(scorecard["slug"])
    )
    destination = root / relative
    if destination.exists():
        raise ValueError(f"Operator-history destination collision: {relative}")
    destination.mkdir(parents=True, exist_ok=True)
    _write_text(destination / "README.md", _run_readme(scorecard))
    _write_text(destination / "SCORECARD.json", _json_text(scorecard))
    _write_text(destination / "LINEAGE.md", _lineage_markdown(scorecard))
    _write_text(destination / "SOURCE_ARTIFACTS.md", _sources_markdown(scorecard))
    links = destination / "SOURCE_LINKS"
    links.mkdir(exist_ok=True)
    if source_run:
        _safe_symlink(Path(source_run["path"]), links / "operator-session")
        if source_run.get("log_path"):
            _safe_symlink(Path(source_run["log_path"]), links / "operator-log.log")
    experiments = _sequence(scorecard.get("experiments"))
    for index, item in enumerate(experiments, start=1):
        data = _mapping(item)
        if not data.get("source_path"):
            continue
        name = f"E{index:02d}__{_slug(data.get('label'), fallback='native')}__{_slug(data.get('disposition'), fallback='recorded')}"
        _safe_symlink(Path(str(data["source_path"])), links / name)
    if not source_run:
        native_path = _first(
            _get(scorecard, "metrics", "provenance", "native_experiment_path"),
            _get(scorecard, "metrics", "provenance", "operator_session_path"),
        )
        if not native_path and scorecard.get("_source_path"):
            native_path = scorecard["_source_path"]
        if native_path:
            _safe_symlink(Path(str(native_path)), links / "native-experiment")
    return relative.as_posix()
