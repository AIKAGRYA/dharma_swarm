"""Read-only parity scoring for legacy context and MemoryKernel lanes.

This module only compares shadow eval reports. It does not inject prompts,
write retrieval feedback, promote facts, or mutate any memory surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.atoms import MemoryAtom
from dharma_swarm.memory_kernel.context_admission import MemoryContextBudget
from dharma_swarm.memory_kernel.context_eval import (
    ContextEvalConfig,
    ContextEvalSeverity,
    CurrentContextLaneReport,
    MemoryKernelContextLaneReport,
    run_context_eval,
)
from dharma_swarm.memory_kernel.context_safety import safe_eval_ref


_STATUS_PASS = "pass"
_STATUS_WARN = "warn"
_STATUS_FAIL = "fail"
_SENSITIVE_FINDINGS = {
    "sensitive_path_detected",
    "secret_like_text_detected",
    "memory_pack_output_path_leak",
}


@dataclass(frozen=True)
class ContextParityMetric:
    name: str
    legacy_value: object
    memory_kernel_value: object
    status: str
    reason: str

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "legacy_value": _json_value(self.legacy_value),
            "memory_kernel_value": _json_value(self.memory_kernel_value),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ContextParityReport:
    query_ref: str
    legacy_report: CurrentContextLaneReport | None
    memory_report: MemoryKernelContextLaneReport | None
    metric_count: int
    pass_count: int
    warning_count: int
    hard_failure_count: int
    metrics: tuple[ContextParityMetric, ...]
    warnings: tuple[str, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "query_ref": self.query_ref,
            "legacy_report": (
                self.legacy_report.to_json() if self.legacy_report else None
            ),
            "memory_report": (
                self.memory_report.to_json() if self.memory_report else None
            ),
            "metric_count": self.metric_count,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "hard_failure_count": self.hard_failure_count,
            "metrics": tuple(metric.to_json() for metric in self.metrics),
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


def run_context_parity_eval(
    *,
    query: str | None = None,
    current_context_text: str | None = None,
    state_dir: Path | None = None,
    memory_kernel: object | None = None,
    memory_atoms: Iterable[MemoryAtom] | None = None,
    memory_surface_ids: tuple[str, ...] = (),
    budget: MemoryContextBudget | None = None,
    allow_current_semantic_search: bool = False,
    metadata: dict[str, object] | None = None,
) -> ContextParityReport:
    """Compare legacy current-context output to a MemoryKernel context lane."""

    resolved_budget = budget or MemoryContextBudget()
    warnings: list[str] = [
        "shadow_mode_no_prompt_injection",
        "no_retrieval_feedback_writes",
        "no_canon_or_chetana_mutation",
    ]
    legacy_text = current_context_text
    if legacy_text is None and state_dir is None:
        legacy_text = ""
        warnings.append("legacy_current_context_not_read_without_state_dir_or_text")
    if memory_kernel is None and memory_atoms is None:
        warnings.append("memory_kernel_lane_has_no_kernel_or_atoms")

    eval_report = run_context_eval(
        config=ContextEvalConfig(
            query=query,
            include_current_context=True,
            include_memory_kernel=True,
            memory_surface_ids=memory_surface_ids,
            memory_limit_total=resolved_budget.max_candidate_atoms,
            memory_limit_per_surface=resolved_budget.max_candidate_atoms,
            allow_current_semantic_search=allow_current_semantic_search,
            budget=resolved_budget,
        ),
        current_context_text=legacy_text,
        state_dir=state_dir,
        memory_kernel=memory_kernel,
        memory_atoms=memory_atoms,
    )
    warnings.extend(eval_report.warnings)
    metrics = _build_metrics(eval_report.current_context, eval_report.memory_kernel)
    return ContextParityReport(
        query_ref=safe_eval_ref(query or ""),
        legacy_report=eval_report.current_context,
        memory_report=eval_report.memory_kernel,
        metric_count=len(metrics),
        pass_count=sum(1 for metric in metrics if metric.status == _STATUS_PASS),
        warning_count=sum(1 for metric in metrics if metric.status == _STATUS_WARN),
        hard_failure_count=sum(1 for metric in metrics if metric.status == _STATUS_FAIL),
        metrics=metrics,
        warnings=tuple(dict.fromkeys(warnings)),
        metadata=dict(metadata or {}),
    )


def render_context_parity_markdown(report: ContextParityReport) -> str:
    lines = [
        "# Memory Context Parity Eval",
        "",
        "Shadow-mode comparison only. It does not inject prompts or write retrieval feedback.",
        "",
        "## Summary",
        "",
        f"- Query: `{report.query_ref}`",
        f"- Metrics: `{report.metric_count}`",
        f"- Passed: `{report.pass_count}`",
        f"- Warnings: `{report.warning_count}`",
        f"- Hard failures: `{report.hard_failure_count}`",
        "",
    ]
    if report.legacy_report:
        legacy = report.legacy_report
        lines.extend(
            [
                "## Legacy Current Context",
                "",
                f"- Source: `{legacy.source}`",
                f"- Characters: `{legacy.char_count}`",
                f"- Findings: `{legacy.finding_count}`",
                "",
            ]
        )
    if report.memory_report:
        memory = report.memory_report
        lines.extend(
            [
                "## MemoryKernel Context",
                "",
                f"- Atoms: `{memory.atom_count}`",
                f"- Candidates: `{memory.pack.candidate_count}`",
                f"- Admitted: `{memory.pack.admitted_count}`",
                f"- Omitted: `{memory.pack.omitted_count}`",
                f"- Candidate truncated: `{str(memory.pack.candidate_truncated).lower()}`",
                f"- Hard failures: `{memory.hard_failure_count}`",
                "",
            ]
        )
    lines.extend(["## Metrics", ""])
    for metric in report.metrics:
        lines.append(
            f"- `{metric.status}` `{metric.name}` legacy=`{metric.legacy_value}` "
            f"memory_kernel=`{metric.memory_kernel_value}` reason={metric.reason}"
        )
    lines.append("")
    if report.warnings:
        lines.extend(["## Harness Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- `{warning}`")
        lines.append("")
    return "\n".join(lines)


def _build_metrics(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> tuple[ContextParityMetric, ...]:
    return (
        _hard_failure_metric(legacy, memory),
        _warning_count_metric(legacy, memory),
        _legacy_sensitive_findings_metric(legacy, memory),
        _memory_admitted_metric(legacy, memory),
        _memory_unsafe_admissions_metric(legacy, memory),
        _pack_omission_truncation_metric(legacy, memory),
    )


def _hard_failure_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_count = legacy.hard_failure_count if legacy else 0
    memory_count = memory.hard_failure_count if memory else 0
    status = _STATUS_FAIL if legacy_count or memory_count else _STATUS_PASS
    reason = "one or more lane reports contain hard failures" if status == _STATUS_FAIL else "no lane hard failures"
    return ContextParityMetric(
        name="hard_failure_count",
        legacy_value=legacy_count,
        memory_kernel_value=memory_count,
        status=status,
        reason=reason,
    )


def _warning_count_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_count = _legacy_warning_count(legacy)
    memory_count = _memory_warning_count(memory)
    status = _STATUS_WARN if legacy_count or memory_count else _STATUS_PASS
    reason = "lane warnings or warning findings are present" if status == _STATUS_WARN else "no lane warnings"
    return ContextParityMetric(
        name="warning_count",
        legacy_value=legacy_count,
        memory_kernel_value=memory_count,
        status=status,
        reason=reason,
    )


def _legacy_sensitive_findings_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_count = _sensitive_occurrence_count(legacy.findings if legacy else ())
    memory_count = _sensitive_occurrence_count(memory.findings if memory else ())
    if memory_count:
        status = _STATUS_FAIL
        reason = "MemoryKernel serialized context contains sensitive findings"
    elif legacy_count:
        status = _STATUS_WARN
        reason = "legacy current context contains sensitive findings"
    else:
        status = _STATUS_PASS
        reason = "no sensitive findings in either lane"
    return ContextParityMetric(
        name="legacy_sensitive_findings",
        legacy_value=legacy_count,
        memory_kernel_value=memory_count,
        status=status,
        reason=reason,
    )


def _memory_admitted_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_chars = legacy.char_count if legacy else 0
    atom_count = memory.atom_count if memory else 0
    admitted_count = memory.pack.admitted_count if memory else 0
    if memory is None or atom_count == 0:
        status = _STATUS_WARN
        reason = "MemoryKernel lane has no atoms to compare"
    elif admitted_count == 0:
        status = _STATUS_WARN
        reason = "MemoryKernel atoms were present but none were admitted"
    else:
        status = _STATUS_PASS
        reason = "MemoryKernel admitted at least one atom"
    return ContextParityMetric(
        name="memory_kernel_admitted_count",
        legacy_value={"char_count": legacy_chars},
        memory_kernel_value={"atom_count": atom_count, "admitted_count": admitted_count},
        status=status,
        reason=reason,
    )


def _memory_unsafe_admissions_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_value = legacy.hard_failure_count if legacy else 0
    unsafe_count = _hard_memory_finding_count(memory)
    status = _STATUS_FAIL if unsafe_count else _STATUS_PASS
    reason = "MemoryKernel admitted unsafe context items" if status == _STATUS_FAIL else "no unsafe MemoryKernel admissions"
    return ContextParityMetric(
        name="memory_kernel_unsafe_admissions",
        legacy_value=legacy_value,
        memory_kernel_value=unsafe_count,
        status=status,
        reason=reason,
    )


def _pack_omission_truncation_metric(
    legacy: CurrentContextLaneReport | None,
    memory: MemoryKernelContextLaneReport | None,
) -> ContextParityMetric:
    legacy_lines = legacy.line_count if legacy else 0
    if memory is None:
        return ContextParityMetric(
            name="pack_omission_truncation",
            legacy_value={"line_count": legacy_lines},
            memory_kernel_value={"omitted_count": 0, "candidate_truncated": False},
            status=_STATUS_WARN,
            reason="MemoryKernel pack was not produced",
        )
    value = {
        "omitted_count": memory.pack.omitted_count,
        "candidate_truncated": memory.pack.candidate_truncated,
    }
    has_pack_gap = memory.pack.omitted_count > 0 or memory.pack.candidate_truncated
    status = _STATUS_WARN if has_pack_gap else _STATUS_PASS
    reason = "MemoryKernel pack omitted or truncated candidates" if has_pack_gap else "MemoryKernel pack included all candidates considered"
    return ContextParityMetric(
        name="pack_omission_truncation",
        legacy_value={"line_count": legacy_lines},
        memory_kernel_value=value,
        status=status,
        reason=reason,
    )


def _legacy_warning_count(report: CurrentContextLaneReport | None) -> int:
    if report is None:
        return 0
    return max(0, report.finding_count - report.hard_failure_count) + len(report.warnings)


def _memory_warning_count(report: MemoryKernelContextLaneReport | None) -> int:
    if report is None:
        return 0
    item_warning_count = sum(len(item.warnings) for item in report.pack.items)
    finding_warning_count = max(0, report.finding_count - report.hard_failure_count)
    return finding_warning_count + len(report.warnings) + item_warning_count


def _sensitive_occurrence_count(findings: Iterable[object]) -> int:
    total = 0
    for finding in findings:
        if getattr(finding, "kind", "") in _SENSITIVE_FINDINGS:
            total += int(getattr(finding, "occurrence_count", 1))
    return total


def _hard_memory_finding_count(report: MemoryKernelContextLaneReport | None) -> int:
    if report is None:
        return 0
    return sum(
        1
        for finding in report.findings
        if finding.severity == ContextEvalSeverity.HARD_FAILURE
    )


def _json_value(value: object) -> object:
    if hasattr(value, "to_json"):
        return value.to_json()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_json_value(item) for item in value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value
