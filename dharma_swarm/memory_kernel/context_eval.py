"""M3B safety-first context admission evaluation harness.

The harness compares two separate representations:

* current context text, scanned as text
* MemoryKernel atoms, evaluated through the structured context admission pack

It is shadow-mode only.  It does not write feedback, inject prompts, promote
knowledge, or mutate any memory surface.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.atoms import (
    MemoryAtom,
    MemoryLane,
    MemoryQuery,
    RiskLevel,
    SurfaceCategory,
    TruthState,
)
from dharma_swarm.memory_kernel.context_admission import (
    MemoryContextBudget,
    MemoryContextPack,
    preview_memory_pack,
)
from dharma_swarm.memory_kernel.context_safety import (
    detect_text_safety_issues,
    redacted_preview,
    safe_eval_ref,
    short_hash,
    stable_context_finding_id,
)


_HIGH_RISKS = {RiskLevel.HIGH, RiskLevel.CRITICAL}


class ContextEvalLane(StrEnum):
    CURRENT_CONTEXT = "current_context"
    MEMORY_KERNEL = "memory_kernel"
    OUTPUT_ARTIFACT = "output_artifact"


class ContextEvalSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HARD_FAILURE = "hard_failure"


@dataclass(frozen=True)
class ContextSafetyFinding:
    finding_id: str
    lane: ContextEvalLane
    kind: str
    severity: ContextEvalSeverity
    reason: str
    occurrence_count: int = 1
    sample_redacted: str = ""
    sample_hash: str = ""
    atom_id: str | None = None
    surface_id: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["severity"] = self.severity.value
        return payload


@dataclass(frozen=True)
class CurrentContextLaneReport:
    source: str
    query_ref: str
    char_count: int
    line_count: int
    redacted_preview: str
    finding_count: int
    hard_failure_count: int
    findings: tuple[ContextSafetyFinding, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [finding.to_json() for finding in self.findings]
        return payload


@dataclass(frozen=True)
class MemoryKernelContextLaneReport:
    atom_count: int
    pack: MemoryContextPack
    finding_count: int
    hard_failure_count: int
    findings: tuple[ContextSafetyFinding, ...]
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "atom_count": self.atom_count,
            "pack": self.pack.to_json(),
            "finding_count": self.finding_count,
            "hard_failure_count": self.hard_failure_count,
            "findings": [finding.to_json() for finding in self.findings],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ContextEvalConfig:
    query: str | None = None
    limit: int = 5
    memory_surface_ids: tuple[str, ...] = ()
    memory_limit_total: int = 50
    memory_limit_per_surface: int = 25
    include_current_context: bool = True
    include_memory_kernel: bool = True
    allow_current_semantic_search: bool = False
    budget: MemoryContextBudget = field(default_factory=MemoryContextBudget)

    def to_json(self) -> dict[str, object]:
        return {
            "query_ref": safe_eval_ref(self.query or ""),
            "limit": self.limit,
            "memory_surface_ids": self.memory_surface_ids,
            "memory_limit_total": self.memory_limit_total,
            "memory_limit_per_surface": self.memory_limit_per_surface,
            "include_current_context": self.include_current_context,
            "include_memory_kernel": self.include_memory_kernel,
            "allow_current_semantic_search": self.allow_current_semantic_search,
            "budget": self.budget.to_json(),
        }


@dataclass(frozen=True)
class ContextEvalReport:
    config: ContextEvalConfig
    current_context: CurrentContextLaneReport | None
    memory_kernel: MemoryKernelContextLaneReport | None
    hard_failure_count: int
    warning_count: int
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "config": self.config.to_json(),
            "current_context": (
                self.current_context.to_json() if self.current_context else None
            ),
            "memory_kernel": (
                self.memory_kernel.to_json() if self.memory_kernel else None
            ),
            "hard_failure_count": self.hard_failure_count,
            "warning_count": self.warning_count,
            "warnings": self.warnings,
        }


def run_context_eval(
    *,
    config: ContextEvalConfig | None = None,
    current_context_text: str | None = None,
    state_dir: Path | None = None,
    memory_kernel: object | None = None,
    memory_atoms: Iterable[MemoryAtom] | None = None,
) -> ContextEvalReport:
    """Run a safety-first shadow evaluation with no MemoryKernel writes."""

    resolved = config or ContextEvalConfig()
    warnings: list[str] = ["shadow_mode_no_prompt_injection", "no_new_feedback_writes"]
    current_report: CurrentContextLaneReport | None = None
    memory_report: MemoryKernelContextLaneReport | None = None

    if resolved.include_current_context:
        text = current_context_text
        source = "provided_text"
        if text is None:
            text = _read_current_context_text(resolved, state_dir=state_dir)
            source = "context.read_memory_context"
        current_report = evaluate_current_context_text(
            text or "",
            source=source,
            query=resolved.query,
        )

    if resolved.include_memory_kernel:
        atoms = tuple(
            memory_atoms
            if memory_atoms is not None
            else _collect_memory_atoms(memory_kernel, resolved)
        )
        memory_report = evaluate_memory_kernel_context(atoms, budget=resolved.budget)
        if memory_kernel is not None and not resolved.memory_surface_ids and memory_atoms is None:
            warnings.append("no_memory_surfaces_configured")

    output_findings = _output_artifact_findings(current_report, memory_report, resolved)
    hard_failure_count = sum(
        item.hard_failure_count
        for item in (current_report, memory_report)
        if item is not None
    ) + sum(1 for finding in output_findings if finding.severity == ContextEvalSeverity.HARD_FAILURE)
    all_warning_count = len(warnings)
    for item in (current_report, memory_report):
        if item is None:
            continue
        all_warning_count += item.finding_count - item.hard_failure_count
        all_warning_count += len(item.warnings)
    if output_findings:
        warnings.extend(finding.kind for finding in output_findings)
    return ContextEvalReport(
        config=resolved,
        current_context=current_report,
        memory_kernel=memory_report,
        hard_failure_count=hard_failure_count,
        warning_count=all_warning_count,
        warnings=tuple(warnings),
    )


def evaluate_current_context_text(
    text: str,
    *,
    source: str,
    query: str | None = None,
) -> CurrentContextLaneReport:
    findings = tuple(_text_findings(text, lane=ContextEvalLane.CURRENT_CONTEXT))
    return CurrentContextLaneReport(
        source=source,
        query_ref=safe_eval_ref(query or ""),
        char_count=len(text),
        line_count=len(text.splitlines()),
        redacted_preview=redacted_preview(text),
        finding_count=len(findings),
        hard_failure_count=0,
        findings=findings,
        warnings=(
            "current_context_findings_are_warnings_not_hard_failures",
            "current_context_raw_text_not_serialized",
        ),
    )


def evaluate_memory_kernel_context(
    atoms: Iterable[MemoryAtom],
    *,
    budget: MemoryContextBudget | None = None,
    pack: MemoryContextPack | None = None,
) -> MemoryKernelContextLaneReport:
    rows = tuple(atoms)
    resolved_budget = budget or MemoryContextBudget()
    resolved_pack = pack or preview_memory_pack(rows, budget=resolved_budget)
    findings = tuple(_memory_kernel_findings(rows, resolved_pack, resolved_budget))
    hard_failures = sum(
        1 for finding in findings if finding.severity == ContextEvalSeverity.HARD_FAILURE
    )
    return MemoryKernelContextLaneReport(
        atom_count=len(rows),
        pack=resolved_pack,
        finding_count=len(findings),
        hard_failure_count=hard_failures,
        findings=findings,
        warnings=tuple(resolved_pack.warnings),
    )


def _read_current_context_text(config: ContextEvalConfig, *, state_dir: Path | None) -> str:
    from dharma_swarm.context import read_memory_context

    return read_memory_context(
        state_dir=state_dir,
        query=config.query,
        limit=config.limit,
        consumer="memory_kernel.context_eval.shadow",
        allow_semantic_search=config.allow_current_semantic_search,
    )


def _collect_memory_atoms(memory_kernel: object | None, config: ContextEvalConfig) -> tuple[MemoryAtom, ...]:
    if memory_kernel is None or not config.memory_surface_ids:
        return ()
    query = MemoryQuery(
        limit_total=config.memory_limit_total,
        limit_per_surface=config.memory_limit_per_surface,
        include_content=config.budget.include_content,
    )
    iter_memory_atoms = getattr(memory_kernel, "iter_memory_atoms")
    return tuple(
        iter_memory_atoms(
            surface_ids=config.memory_surface_ids,
            query=query,
        )
    )


def _text_findings(text: str, *, lane: ContextEvalLane) -> Iterable[ContextSafetyFinding]:
    for issue in detect_text_safety_issues(text):
        yield ContextSafetyFinding(
            finding_id=stable_context_finding_id(
                lane.value,
                issue.kind,
                issue.sample_hash,
            ),
            lane=lane,
            kind=issue.kind,
            severity=ContextEvalSeverity.WARNING,
            reason=issue.reason,
            occurrence_count=issue.occurrence_count,
            sample_redacted=issue.sample_redacted,
            sample_hash=issue.sample_hash,
        )


def _memory_kernel_findings(
    atoms: tuple[MemoryAtom, ...],
    pack: MemoryContextPack,
    budget: MemoryContextBudget,
) -> Iterable[ContextSafetyFinding]:
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    for item in pack.items:
        atom = atom_by_id.get(item.atom_id)
        if not item.admitted:
            continue
        if item.content_snippet is not None and not budget.include_content:
            yield _finding(
                lane=ContextEvalLane.MEMORY_KERNEL,
                kind="content_included_without_budget",
                severity=ContextEvalSeverity.HARD_FAILURE,
                reason="MemoryKernel admitted raw content while include_content is false",
                atom_id=item.atom_id,
                surface_id=item.surface_id,
            )
        if item.truth_state in {TruthState.REJECTED, TruthState.SUPERSEDED}:
            yield _finding(
                lane=ContextEvalLane.MEMORY_KERNEL,
                kind="rejected_or_superseded_admitted",
                severity=ContextEvalSeverity.HARD_FAILURE,
                reason="MemoryKernel admitted rejected or superseded memory",
                atom_id=item.atom_id,
                surface_id=item.surface_id,
            )
        if (
            not budget.allow_projections
            and (
                item.surface_category == SurfaceCategory.PROJECTION
                or item.memory_lane == MemoryLane.PROJECTION
                or bool(item.projection_of)
            )
        ):
            yield _finding(
                lane=ContextEvalLane.MEMORY_KERNEL,
                kind="projection_admitted_without_override",
                severity=ContextEvalSeverity.HARD_FAILURE,
                reason="MemoryKernel admitted a projection without projection override",
                atom_id=item.atom_id,
                surface_id=item.surface_id,
            )
        if atom and not budget.allow_high_risk and (
            atom.canon_risk in _HIGH_RISKS or atom.pii_risk in _HIGH_RISKS
        ):
            yield _finding(
                lane=ContextEvalLane.MEMORY_KERNEL,
                kind="high_risk_admitted_without_override",
                severity=ContextEvalSeverity.HARD_FAILURE,
                reason="MemoryKernel admitted high-risk memory without override",
                atom_id=item.atom_id,
                surface_id=item.surface_id,
            )
        serialized = json.dumps(item.to_json(), sort_keys=True, default=str)
        for text_finding in _text_findings(
            serialized,
            lane=ContextEvalLane.MEMORY_KERNEL,
        ):
            yield ContextSafetyFinding(
                finding_id=text_finding.finding_id,
                lane=text_finding.lane,
                kind="memory_pack_output_path_leak",
                severity=ContextEvalSeverity.HARD_FAILURE,
                reason="MemoryKernel pack item serialized with local path references",
                occurrence_count=text_finding.occurrence_count,
                sample_redacted=text_finding.sample_redacted,
                sample_hash=text_finding.sample_hash,
                atom_id=item.atom_id,
                surface_id=item.surface_id,
            )


def _output_artifact_findings(
    current_report: CurrentContextLaneReport | None,
    memory_report: MemoryKernelContextLaneReport | None,
    config: ContextEvalConfig,
) -> tuple[ContextSafetyFinding, ...]:
    payload = {
        "config": config.to_json(),
        "current_context": current_report.to_json() if current_report else None,
        "memory_kernel": memory_report.to_json() if memory_report else None,
    }
    return tuple(
        ContextSafetyFinding(
            finding_id=finding.finding_id,
            lane=ContextEvalLane.OUTPUT_ARTIFACT,
            kind="serialized_eval_output_path_leak",
            severity=ContextEvalSeverity.HARD_FAILURE,
            reason="context eval output artifact contains local path references",
            occurrence_count=finding.occurrence_count,
            sample_redacted=finding.sample_redacted,
            sample_hash=finding.sample_hash,
        )
        for finding in _text_findings(
            json.dumps(payload, sort_keys=True, default=str),
            lane=ContextEvalLane.OUTPUT_ARTIFACT,
        )
        if finding.kind == "sensitive_path_detected"
    )


def _finding(
    *,
    lane: ContextEvalLane,
    kind: str,
    severity: ContextEvalSeverity,
    reason: str,
    occurrence_count: int = 1,
    sample: str = "",
    atom_id: str | None = None,
    surface_id: str | None = None,
) -> ContextSafetyFinding:
    sample_hash = short_hash(sample) if sample else ""
    return ContextSafetyFinding(
        finding_id=stable_context_finding_id(lane.value, kind, sample_hash, atom_id or ""),
        lane=lane,
        kind=kind,
        severity=severity,
        reason=reason,
        occurrence_count=occurrence_count,
        sample_redacted=safe_eval_ref(sample) if sample else "",
        sample_hash=sample_hash,
        atom_id=atom_id,
        surface_id=surface_id,
    )
