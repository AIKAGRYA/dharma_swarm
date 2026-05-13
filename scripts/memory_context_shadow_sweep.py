#!/usr/bin/env python3
"""Run representative MemoryKernel context shadow parity scenarios."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.memory_kernel import (
    CensusConfig,
    MemoryContextBudget,
    MemoryKernel,
    MemoryKernelConfig,
    run_context_parity_eval,
)
from dharma_swarm.memory_kernel.context_admission import redact_context_text


@dataclass(frozen=True)
class ShadowSweepScenario:
    scenario_id: str
    title: str
    query: str
    current_context_text: str

    def to_json(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "query_ref": redact_context_text(self.query),
        }


def default_shadow_scenarios() -> tuple[ShadowSweepScenario, ...]:
    synthetic_key = "API" + "_KEY=sample_placeholder"
    synthetic_bearer = "Authorization: Bearer " + ("a" * 16)
    return (
        ShadowSweepScenario(
            "normal_task_context",
            "Normal Task Context",
            "continue MemoryKernel implementation",
            "\n".join(
                [
                    "## Operator Intent",
                    "Continue the MemoryKernel implementation without changing live prompts.",
                    "## Task State",
                    "- task_id=memory-m4a",
                    "- status=in_progress",
                ]
            ),
        ),
        ShadowSweepScenario(
            "code_review_context",
            "Code Review Context",
            "review MemoryKernel writer sentinel for hidden write paths",
            "\n".join(
                [
                    "## Review Scope",
                    "Check writer sentinel safety, output redaction, and bounded discovery.",
                    "## Findings",
                    "- projection stores must not be treated as authority.",
                ]
            ),
        ),
        ShadowSweepScenario(
            "knowledge_ops_context",
            "KnowledgeOps Context",
            "convert memory atoms into evidence packets",
            "\n".join(
                [
                    "## KnowledgeOps",
                    "MemoryAtoms are evidence, not canon.",
                    "Generated cards must cite source atoms and preserve truth_state.",
                ]
            ),
        ),
        ShadowSweepScenario(
            "routing_witness_context",
            "Routing And Witness Context",
            "audit route witness and provider-learning memory",
            "\n".join(
                [
                    "## Runtime Evidence",
                    "Route decisions are telemetry and witness evidence.",
                    "Provider learning must remain separate from semantic truth.",
                ]
            ),
        ),
        ShadowSweepScenario(
            "stale_conflict_context",
            "Stale Or Conflicting Context",
            "detect stale or conflicting memory claims",
            "\n".join(
                [
                    "## Memory Conflict",
                    "Claim A says Chetana staging is canon.",
                    "Claim B says Chetana staging is non-canon and needs review.",
                    "Treat this as conflict evidence, not overwrite authority.",
                ]
            ),
        ),
        ShadowSweepScenario(
            "sensitive_contamination_context",
            "Sensitive Contamination Context",
            "scan context for secrets and local paths",
            (
                "Use /Users/dhyana/.dharma/db/memory_plane.db "
                f"{synthetic_key} "
                f"{synthetic_bearer}"
            ),
        ),
        ShadowSweepScenario(
            "large_noisy_context",
            "Large Noisy Context",
            "summarize noisy memory without prompt pollution",
            "\n".join(
                ["## Noisy Memory"]
                + [
                    f"- repeated observation {idx}: raw logs are evidence, projections are not truth"
                    for idx in range(60)
                ]
            ),
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--memory-home", type=Path)
    parser.add_argument("--memory-surface", action="append", default=[])
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--list-scenarios", action="store_true")
    parser.add_argument("--max-candidate-atoms", type=int, default=50)
    parser.add_argument("--max-admitted-atoms", type=int, default=8)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--fail-on-hard-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenarios = _selected_scenarios(args.scenario)
    if args.list_scenarios:
        print(
            _safe_json_text(
                {
                    "scenario_count": len(scenarios),
                    "scenarios": [scenario.to_json() for scenario in scenarios],
                }
            )
        )
        return 0

    validation_error = _validate_args(args)
    if validation_error:
        print(_safe_json_text({"error": validation_error}))
        return 2

    memory_kernel = _memory_kernel(args)
    reports = [
        _run_scenario(args, scenario, memory_kernel=memory_kernel)
        for scenario in scenarios
    ]
    payload = _payload(reports)
    payload_text = _safe_json_text(payload)
    print(payload_text)

    if not args.dry_run:
        if args.output_json:
            output_json = _resolve_output(args.output_json, args.repo_root)
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(payload_text + "\n", encoding="utf-8")
        if args.output_md:
            output_md = _resolve_output(args.output_md, args.repo_root)
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(_safe_text(_render_markdown(reports)), encoding="utf-8")

    if args.fail_on_hard_failure and int(payload["hard_failure_count"]) > 0:
        return 6
    return 0


def _selected_scenarios(scenario_ids: list[str]) -> tuple[ShadowSweepScenario, ...]:
    scenarios = default_shadow_scenarios()
    if not scenario_ids:
        return scenarios
    wanted = set(scenario_ids)
    return tuple(scenario for scenario in scenarios if scenario.scenario_id in wanted)


def _validate_args(args: argparse.Namespace) -> str:
    available = {scenario.scenario_id for scenario in default_shadow_scenarios()}
    unknown = sorted(set(args.scenario) - available)
    if unknown:
        return "unknown scenario(s): " + ", ".join(unknown)
    if args.memory_surface and args.memory_home is None:
        return "--memory-surface requires explicit --memory-home"
    if args.memory_home is not None and not args.memory_surface:
        return "--memory-home requires at least one --memory-surface"
    for output_path in (args.output_json, args.output_md):
        if output_path and _is_memory_surface_output(output_path, args):
            return "output paths under memory surfaces are not allowed"
    return ""


def _memory_kernel(args: argparse.Namespace) -> MemoryKernel | None:
    if args.memory_home is None:
        return None
    return MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=args.repo_root,
                home=args.memory_home,
                include_discovered=False,
            )
        )
    )


def _run_scenario(
    args: argparse.Namespace,
    scenario: ShadowSweepScenario,
    *,
    memory_kernel: MemoryKernel | None,
) -> dict[str, object]:
    report = run_context_parity_eval(
        query=scenario.query,
        current_context_text=scenario.current_context_text,
        state_dir=None,
        memory_kernel=memory_kernel,
        memory_surface_ids=tuple(args.memory_surface),
        budget=MemoryContextBudget(
            max_candidate_atoms=args.max_candidate_atoms,
            max_admitted_atoms=args.max_admitted_atoms,
            include_content=False,
        ),
        allow_current_semantic_search=False,
    )
    return {
        "scenario": scenario.to_json(),
        "report": report.to_json(),
    }


def _payload(reports: list[dict[str, object]]) -> dict[str, object]:
    hard_failure_count = sum(
        int(report["report"]["hard_failure_count"]) for report in reports
    )
    warning_count = sum(int(report["report"]["warning_count"]) for report in reports)
    return {
        "scenario_count": len(reports),
        "hard_failure_count": hard_failure_count,
        "warning_count": warning_count,
        "reports": reports,
    }


def _render_markdown(reports: list[dict[str, object]]) -> str:
    payload = _payload(reports)
    lines = [
        "# Memory Context Shadow Sweep",
        "",
        "Representative shadow-mode context parity reports. This command does not inject prompts, write retrieval feedback, or mutate memory.",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{payload['scenario_count']}`",
        f"- Hard failures: `{payload['hard_failure_count']}`",
        f"- Warnings: `{payload['warning_count']}`",
        "",
        "## Scenarios",
        "",
    ]
    for item in reports:
        scenario = item["scenario"]
        report_json = item["report"]
        lines.extend(
            [
                f"### {scenario['title']}",
                "",
                f"- Scenario: `{scenario['scenario_id']}`",
                f"- Query: `{scenario['query_ref']}`",
                f"- Hard failures: `{report_json['hard_failure_count']}`",
                f"- Warnings: `{report_json['warning_count']}`",
                "",
            ]
        )
        lines.extend(_render_report_metrics(report_json))
        lines.append("")
    return "\n".join(lines)


def _render_report_metrics(report_json: dict[str, object]) -> list[str]:
    lines = ["#### Metrics", ""]
    for metric in report_json.get("metrics", ()):
        if not isinstance(metric, dict):
            continue
        lines.append(
            f"- `{metric.get('status', '')}` `{metric.get('name', '')}` "
            f"reason={metric.get('reason', '')}"
        )
    warnings = report_json.get("warnings", ())
    if warnings:
        lines.extend(["", "#### Harness Warnings", ""])
        for warning in warnings:
            lines.append(f"- `{warning}`")
    return lines


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _is_memory_surface_output(path: Path, args: argparse.Namespace) -> bool:
    resolved = _resolve_output(path, args.repo_root).expanduser().resolve()
    for root in _memory_surface_roots(args):
        if _is_relative_to(resolved, root.expanduser().resolve()):
            return True
    return False


def _memory_surface_roots(args: argparse.Namespace) -> tuple[Path, ...]:
    home_roots = [Path.home()]
    if args.memory_home is not None:
        home_roots.append(args.memory_home)
    roots: list[Path] = []
    for home in home_roots:
        roots.extend(
            [
                home / ".dharma",
                home / ".smriti",
                home / ".codex" / "memories",
            ]
        )
    roots.extend([args.repo_root / ".dharma", args.repo_root / ".swarm"])
    return tuple(roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_json_text(payload: object) -> str:
    return _safe_text(json.dumps(payload, indent=2, sort_keys=True))


def _safe_text(text: str) -> str:
    return redact_context_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
