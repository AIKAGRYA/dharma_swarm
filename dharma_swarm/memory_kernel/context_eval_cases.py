"""Synthetic MemoryKernel context-eval cases.

These cases exercise the context admission harness without reading live memory
or wiring MemoryKernel into prompt construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    AuthorityLevel,
    MemoryAtom,
    MemoryAtomType,
    MemoryLane,
    MemoryScope,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
)
from dharma_swarm.memory_kernel.context_admission import MemoryContextBudget
from dharma_swarm.memory_kernel.context_eval import ContextEvalConfig, ContextEvalReport, run_context_eval


@dataclass(frozen=True)
class ContextEvalCase:
    case_id: str
    title: str
    description: str
    config: ContextEvalConfig
    current_context_text: str | None = None
    atoms: tuple[MemoryAtom, ...] = ()
    expected_hard_failures: int = 0
    expected_admitted_atoms: int | None = None
    expected_min_warnings: int = 0

    def to_json(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "description": self.description,
            "config": self.config.to_json(),
            "current_context_text": "<present>" if self.current_context_text else None,
            "atoms": tuple(atom.atom_id for atom in self.atoms),
            "expected_hard_failures": self.expected_hard_failures,
            "expected_admitted_atoms": self.expected_admitted_atoms,
            "expected_min_warnings": self.expected_min_warnings,
        }


@dataclass(frozen=True)
class ContextEvalCaseResult:
    case: ContextEvalCase
    report: ContextEvalReport
    passed: bool
    failures: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "case": self.case.to_json(),
            "passed": self.passed,
            "failures": self.failures,
            "report": self.report.to_json(),
        }


def default_context_eval_cases() -> tuple[ContextEvalCase, ...]:
    """Return the built-in shadow cases for M3B/M3C context work."""

    curated = _atom(
        surface=_runtime_surface(),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:curated-1",
        truth_state=TruthState.OBSERVED,
        context_admissible=True,
    )
    projection = _atom(
        surface=_projection_surface(),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="source_chunk:projection-1",
        truth_state=TruthState.DERIVED,
        context_admissible=True,
    )
    rejected = _atom(
        surface=_runtime_surface(),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:rejected-1",
        truth_state=TruthState.REJECTED,
        context_admissible=True,
    )
    superseded = _atom(
        surface=_runtime_surface(),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:superseded-1",
        truth_state=TruthState.SUPERSEDED,
        context_admissible=True,
    )
    high_risk = _atom(
        surface=_runtime_surface(canon_risk=RiskLevel.HIGH, pii_risk=RiskLevel.HIGH),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:high-risk-1",
        truth_state=TruthState.OBSERVED,
        context_admissible=True,
    )
    content_atom = _atom(
        surface=_runtime_surface(),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:bounded-content-1",
        content=(
            f"Evidence from {Path.home()}/.dharma/state/runtime.db "
            "secret_token=abc123"
        ),
        truth_state=TruthState.OBSERVED,
        context_admissible=True,
    )
    truncated_content = _atom(
        surface=_runtime_surface(),
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime_event:truncated-content-1",
        content=(
            f"Evidence from {Path.home()}/.dharma/state/runtime.db "
            "secret_token=abc123 " + "verified " * 24
        ),
        truth_state=TruthState.OBSERVED,
        context_admissible=True,
    )
    capped_atoms = tuple(
        _atom(
            surface=_runtime_surface(),
            atom_type=MemoryAtomType.RUNTIME_EVENT,
            content_ref=f"runtime_event:cap-candidate-{index}",
            truth_state=TruthState.OBSERVED,
            context_admissible=True,
        )
        for index in range(4)
    )
    return (
        ContextEvalCase(
            case_id="current_context_redaction",
            title="Current Context Redaction",
            description="Legacy context text with local path and secret-like marker is warned and redacted.",
            config=ContextEvalConfig(include_memory_kernel=False),
            current_context_text=(
                f"Use {Path.home()}/.dharma/db/memory_plane.db secret_token=abc123"
            ),
            expected_hard_failures=0,
            expected_min_warnings=6,
        ),
        ContextEvalCase(
            case_id="observed_runtime_admitted",
            title="Observed Runtime Reference Admitted",
            description="A context-admissible observed runtime atom can enter as a reference-only pack item.",
            config=ContextEvalConfig(include_current_context=False),
            atoms=(curated,),
            expected_hard_failures=0,
            expected_admitted_atoms=1,
        ),
        ContextEvalCase(
            case_id="projection_omitted_by_default",
            title="Projection Omitted By Default",
            description="Projection atoms are not admitted unless the budget explicitly allows projections.",
            config=ContextEvalConfig(include_current_context=False),
            atoms=(projection,),
            expected_hard_failures=0,
            expected_admitted_atoms=0,
        ),
        ContextEvalCase(
            case_id="rejected_omitted_by_default",
            title="Rejected Memory Omitted By Default",
            description="Rejected atoms are omitted even when they are marked context-admissible.",
            config=ContextEvalConfig(include_current_context=False),
            atoms=(rejected,),
            expected_hard_failures=0,
            expected_admitted_atoms=0,
        ),
        ContextEvalCase(
            case_id="superseded_omitted_by_default",
            title="Superseded Memory Omitted By Default",
            description="Superseded atoms are omitted even when they are marked context-admissible.",
            config=ContextEvalConfig(include_current_context=False),
            atoms=(superseded,),
            expected_hard_failures=0,
            expected_admitted_atoms=0,
        ),
        ContextEvalCase(
            case_id="high_risk_omitted_by_default",
            title="High-Risk Memory Omitted By Default",
            description="High-risk atoms are omitted unless the budget explicitly allows high-risk memory.",
            config=ContextEvalConfig(include_current_context=False),
            atoms=(high_risk,),
            expected_hard_failures=0,
            expected_admitted_atoms=0,
        ),
        ContextEvalCase(
            case_id="projection_override_marked",
            title="Projection Override Remains Marked",
            description="A projection override admits derived projection memory while preserving projection labels.",
            config=ContextEvalConfig(
                include_current_context=False,
                budget=MemoryContextBudget(
                    allow_projections=True,
                    allowed_truth_states=(TruthState.DERIVED,),
                ),
            ),
            atoms=(projection,),
            expected_hard_failures=0,
            expected_admitted_atoms=1,
        ),
        ContextEvalCase(
            case_id="high_risk_override_explicit",
            title="High-Risk Override Explicit",
            description="High-risk memory is admitted only when the budget explicitly allows it.",
            config=ContextEvalConfig(
                include_current_context=False,
                budget=MemoryContextBudget(allow_high_risk=True),
            ),
            atoms=(high_risk,),
            expected_hard_failures=0,
            expected_admitted_atoms=1,
        ),
        ContextEvalCase(
            case_id="bounded_content_redacted",
            title="Bounded Content Redacted",
            description="Explicit content inclusion is still bounded and redacts local path and secret-like text.",
            config=ContextEvalConfig(
                include_current_context=False,
                budget=MemoryContextBudget(include_content=True),
            ),
            atoms=(content_atom,),
            expected_hard_failures=0,
            expected_admitted_atoms=1,
        ),
        ContextEvalCase(
            case_id="content_budget_truncation_redacted",
            title="Content Budget Truncation Redacted",
            description="Included content is truncated by budget after local paths and secret-like text are redacted.",
            config=ContextEvalConfig(
                include_current_context=False,
                budget=MemoryContextBudget(include_content=True, max_atom_chars=80),
            ),
            atoms=(truncated_content,),
            expected_hard_failures=0,
            expected_admitted_atoms=1,
        ),
        ContextEvalCase(
            case_id="atom_cap_candidate_limit_warning",
            title="Atom Cap Candidate Limit Warning",
            description="Candidate truncation emits a warning and the admitted-atom cap omits excess candidates.",
            config=ContextEvalConfig(
                include_current_context=False,
                budget=MemoryContextBudget(max_candidate_atoms=3, max_admitted_atoms=1),
            ),
            atoms=capped_atoms,
            expected_hard_failures=0,
            expected_admitted_atoms=1,
            expected_min_warnings=5,
        ),
    )


def run_context_eval_case(case: ContextEvalCase) -> ContextEvalCaseResult:
    report = run_context_eval(
        config=case.config,
        current_context_text=case.current_context_text,
        memory_atoms=case.atoms,
    )
    failures: list[str] = []
    if report.hard_failure_count != case.expected_hard_failures:
        failures.append(
            "hard_failure_count "
            f"expected={case.expected_hard_failures} actual={report.hard_failure_count}"
        )
    if report.warning_count < case.expected_min_warnings:
        failures.append(
            "warning_count "
            f"expected_min={case.expected_min_warnings} actual={report.warning_count}"
        )
    if case.expected_admitted_atoms is not None:
        admitted = report.memory_kernel.pack.admitted_count if report.memory_kernel else 0
        if admitted != case.expected_admitted_atoms:
            failures.append(
                "admitted_count "
                f"expected={case.expected_admitted_atoms} actual={admitted}"
            )
    return ContextEvalCaseResult(
        case=case,
        report=report,
        passed=not failures,
        failures=tuple(failures),
    )


def run_default_context_eval_cases() -> tuple[ContextEvalCaseResult, ...]:
    return tuple(run_context_eval_case(case) for case in default_context_eval_cases())


def _runtime_surface(
    *,
    canon_risk: RiskLevel = RiskLevel.LOW,
    pii_risk: RiskLevel = RiskLevel.LOW,
) -> MemorySurface:
    return MemorySurface(
        surface_id="fixture.runtime_state",
        path="/fixture/.dharma/state/runtime.db",
        owner_module="fixture",
        role=MemorySurfaceRole.RUNTIME_STATE,
        category=SurfaceCategory.RUNTIME_CONTROL,
        authority_level=AuthorityLevel.HIGH,
        write_mode=WriteMode.READ_WRITE,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.SNAPSHOT,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="fixture",
        canon_risk=canon_risk,
        pii_secrets_risk=pii_risk,
        latency_risk=RiskLevel.LOW,
    )


def _projection_surface() -> MemorySurface:
    return MemorySurface(
        surface_id="fixture.vector_projection",
        path="/fixture/.dharma/vectors.db",
        owner_module="fixture",
        role=MemorySurfaceRole.PROJECTION_INDEX,
        category=SurfaceCategory.PROJECTION,
        authority_level=AuthorityLevel.LOW,
        write_mode=WriteMode.PROJECTION_WRITE,
        adapter_mode=AdapterMode.METADATA_ONLY,
        active_status=SurfaceStatus.SNAPSHOT,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="fixture",
        canon_risk=RiskLevel.MEDIUM,
        pii_secrets_risk=RiskLevel.MEDIUM,
        latency_risk=RiskLevel.LOW,
        projection_of=("fixture.runtime_state",),
    )


def _atom(
    *,
    surface: MemorySurface,
    atom_type: MemoryAtomType,
    content_ref: str,
    truth_state: TruthState,
    context_admissible: bool,
    content: str | None = None,
) -> MemoryAtom:
    return MemoryAtom.build(
        surface=surface,
        atom_type=atom_type,
        content_ref=content_ref,
        content=content,
        timestamp="2026-05-13T00:00:00Z",
        source_path=surface.path,
        adapter_name="fixture_case",
        read_mode=ReadMode.READ_ONLY,
        memory_lane=MemoryLane.WORKING
        if surface.category == SurfaceCategory.RUNTIME_CONTROL
        else MemoryLane.PROJECTION,
        scope=MemoryScope.PROJECT,
        truth_state=truth_state,
        context_admissible=context_admissible,
    )
