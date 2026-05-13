from __future__ import annotations

import json

import pytest

from dharma_swarm.memory_kernel import (
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

context_parity = pytest.importorskip("dharma_swarm.memory_kernel.context_parity")

run_context_parity_eval = context_parity.run_context_parity_eval
render_context_parity_markdown = context_parity.render_context_parity_markdown


def _surface(
    *,
    surface_id: str = "fixture.runtime_state",
    category: SurfaceCategory = SurfaceCategory.RUNTIME_CONTROL,
    role: MemorySurfaceRole = MemorySurfaceRole.RUNTIME_STATE,
    authority_level: AuthorityLevel = AuthorityLevel.HIGH,
    write_mode: WriteMode = WriteMode.READ_WRITE,
    projection_of: tuple[str, ...] = (),
    canon_risk: RiskLevel = RiskLevel.LOW,
    pii_risk: RiskLevel = RiskLevel.LOW,
) -> MemorySurface:
    return MemorySurface(
        surface_id=surface_id,
        path="/fixture/.dharma/state/runtime.db",
        owner_module="fixture",
        role=role,
        category=category,
        authority_level=authority_level,
        write_mode=write_mode,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.SNAPSHOT,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="fixture",
        canon_risk=canon_risk,
        pii_secrets_risk=pii_risk,
        latency_risk=RiskLevel.LOW,
        projection_of=projection_of,
    )


def _atom(
    *,
    surface: MemorySurface | None = None,
    atom_type: MemoryAtomType = MemoryAtomType.RUNTIME_EVENT,
    content_ref: str = "runtime_event:1",
    content: str | None = "observed runtime event",
    truth_state: TruthState = TruthState.OBSERVED,
    memory_lane: MemoryLane | None = None,
    context_admissible: bool = True,
) -> MemoryAtom:
    resolved_surface = surface or _surface()
    return MemoryAtom.build(
        surface=resolved_surface,
        atom_type=atom_type,
        content_ref=content_ref,
        content=content,
        timestamp="2026-05-13T00:00:00Z",
        source_path=resolved_surface.path,
        adapter_name="fixture_parity",
        read_mode=ReadMode.READ_ONLY,
        memory_lane=memory_lane,
        scope=MemoryScope.PROJECT,
        truth_state=truth_state,
        context_admissible=context_admissible,
    )


def _projection_atom() -> MemoryAtom:
    return _atom(
        surface=_surface(
            surface_id="fixture.vector_projection",
            category=SurfaceCategory.PROJECTION,
            role=MemorySurfaceRole.PROJECTION_INDEX,
            authority_level=AuthorityLevel.LOW,
            write_mode=WriteMode.PROJECTION_WRITE,
            projection_of=("fixture.runtime_state",),
            canon_risk=RiskLevel.MEDIUM,
            pii_risk=RiskLevel.MEDIUM,
        ),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="source_chunk:projection-1",
        content="derived projection chunk",
        truth_state=TruthState.DERIVED,
        memory_lane=MemoryLane.PROJECTION,
        context_admissible=True,
    )


def _payload_and_markdown(report: object) -> tuple[str, str]:
    payload = json.dumps(report.to_json(), sort_keys=True, default=str)
    markdown = render_context_parity_markdown(report)
    return payload, markdown


def _metric_names(report: object) -> set[str]:
    return {_metric_name(metric) for metric in report.metrics}


def _metric_name(metric: object) -> str:
    if isinstance(metric, dict):
        return str(metric["name"])
    return str(metric.name)


def _metric_status(metric: object) -> str:
    status = metric["status"] if isinstance(metric, dict) else metric.status
    return str(getattr(status, "value", status))


def _metric_json(metric: object) -> str:
    if isinstance(metric, dict):
        payload = metric
    elif hasattr(metric, "to_json"):
        payload = metric.to_json()
    else:
        payload = {"name": _metric_name(metric), "status": _metric_status(metric)}
    return json.dumps(payload, sort_keys=True, default=str)


def _is_warning_status(metric: object) -> bool:
    return _metric_status(metric) in {"warn", "warning"}


def _is_hard_failure_status(metric: object) -> bool:
    return _metric_status(metric) in {"fail", "hard_failure"}


def test_legacy_current_context_redacts_and_warns_without_hard_failure() -> None:
    report = run_context_parity_eval(
        current_context_text=(
            "Use /Users/dhyana/.dharma/state/runtime.db secret_token=abc123"
        ),
        memory_atoms=(),
    )
    payload, markdown = _payload_and_markdown(report)

    assert report.metric_count == len(report.metrics)
    assert report.hard_failure_count == 0
    assert report.warning_count >= 1
    assert any(_is_warning_status(metric) for metric in report.metrics)
    assert "/Users/dhyana" not in payload
    assert "/Users/dhyana" not in markdown
    assert "/fixture" not in payload
    assert "/fixture" not in markdown
    assert "abc123" not in payload
    assert "abc123" not in markdown


def test_safe_observed_memory_atom_records_admitted_count_metric() -> None:
    report = run_context_parity_eval(
        current_context_text="safe current context",
        memory_atoms=(_atom(),),
    )

    assert report.hard_failure_count == 0
    assert any(
        "admitted" in name and "count" in name for name in _metric_names(report)
    )


def test_projection_atom_is_omitted_by_default_without_hard_failure() -> None:
    report = run_context_parity_eval(
        current_context_text="safe current context",
        memory_atoms=(_projection_atom(),),
    )

    assert report.hard_failure_count == 0
    pack = report.to_json()["memory_report"]["pack"]
    assert pack["admitted_count"] == 0
    assert pack["omitted_count"] == 1
    related_metrics = [
        metric
        for metric in report.metrics
        if any(
            token in _metric_json(metric)
            for token in ("omitted", "omission", "projection")
        )
    ]
    assert related_metrics
    assert all(
        not _is_hard_failure_status(metric)
        for metric in related_metrics
    )


def test_parity_report_outputs_do_not_leak_raw_paths_or_secret_literals() -> None:
    local_path = "/Users/dhyana/.dharma/db/memory_plane.db"
    report = run_context_parity_eval(
        current_context_text=f"Legacy context {local_path} secret_token=abc123",
        memory_atoms=(
            _atom(
                content_ref=local_path,
                content=f"Observed evidence at {local_path} secret_token=abc123",
            ),
        ),
    )
    payload, markdown = _payload_and_markdown(report)

    assert report.hard_failure_count == 0
    assert "/Users/dhyana" not in payload
    assert "/Users/dhyana" not in markdown
    assert "/fixture" not in payload
    assert "/fixture" not in markdown
    assert "abc123" not in payload
    assert "abc123" not in markdown
