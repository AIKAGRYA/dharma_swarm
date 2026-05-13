from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    CensusConfig,
    ContextEvalConfig,
    ContextEvalSeverity,
    MemoryAtom,
    MemoryAtomType,
    MemoryContextBudget,
    MemoryKernel,
    MemoryKernelConfig,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
    evaluate_current_context_text,
    evaluate_memory_kernel_context,
    preview_memory_pack,
    render_context_eval_markdown,
    run_default_context_eval_cases,
    run_context_eval,
)
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sqlite_db(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def _surface(
    *,
    surface_id: str = "home.runtime_state",
    category: SurfaceCategory = SurfaceCategory.RUNTIME_CONTROL,
    role: MemorySurfaceRole = MemorySurfaceRole.RUNTIME_STATE,
    authority_level: AuthorityLevel = AuthorityLevel.HIGH,
    canon_risk: RiskLevel = RiskLevel.LOW,
    pii_risk: RiskLevel = RiskLevel.LOW,
    projection_of: tuple[str, ...] = (),
) -> MemorySurface:
    return MemorySurface(
        surface_id=surface_id,
        path="/Users/dhyana/.dharma/state/runtime.db",
        owner_module="dharma_swarm.runtime_state",
        role=role,
        category=category,
        authority_level=authority_level,
        write_mode=WriteMode.READ_WRITE,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.ACTIVE,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="good",
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
    context_admissible: bool = True,
) -> MemoryAtom:
    resolved_surface = surface or _surface()
    return MemoryAtom.build(
        surface=resolved_surface,
        atom_type=atom_type,
        content_ref=content_ref,
        content=content,
        timestamp="2026-05-12T00:00:00Z",
        source_path="/Users/dhyana/.dharma/state/runtime.db",
        adapter_name="test_adapter",
        read_mode=ReadMode.READ_ONLY,
        truth_state=truth_state,
        context_admissible=context_admissible,
    )


def _fixture_memory_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(
        home / ".dharma/db/memory_plane.db",
        [
            "CREATE TABLE event_log(id INTEGER PRIMARY KEY, payload TEXT, timestamp TEXT)",
            "CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY, content TEXT, timestamp TEXT)",
            "CREATE TABLE idea_shards(id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)",
            "CREATE TABLE source_chunks(id INTEGER PRIMARY KEY, chunk_text TEXT, source_path TEXT)",
            "CREATE TABLE retrieval_log(id INTEGER PRIMARY KEY, query TEXT, score REAL)",
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn one', '2026-05-11T01:01:00Z')",
        ],
    )
    _write(home / ".dharma/conversation_log/2026-05-11.jsonl", '{"content": "hidden"}\n')
    return home, repo


def test_current_context_lane_scans_text_without_serializing_raw_paths() -> None:
    report = evaluate_current_context_text(
        "Use /Users/dhyana/.dharma/state/runtime.db with secret_token=abc123",
        source="fixture",
        query="/Users/dhyana/task",
    )
    payload = json.dumps(report.to_json(), sort_keys=True)

    assert report.finding_count == 2
    assert report.hard_failure_count == 0
    assert "sensitive_path_detected" in payload
    assert "<local_path_redacted>" in payload
    assert "/Users/dhyana" not in payload
    assert "abc123" not in payload


def test_memory_kernel_lane_flags_unsafe_projection_admission() -> None:
    projection = _atom(
        surface=_surface(
            surface_id="home.vectors",
            category=SurfaceCategory.PROJECTION,
            role=MemorySurfaceRole.PROJECTION_INDEX,
            authority_level=AuthorityLevel.LOW,
            projection_of=("home.memory_plane",),
        ),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="chunk:1",
        truth_state=TruthState.OBSERVED,
        context_admissible=True,
    )
    permissive_pack = preview_memory_pack(
        (projection,),
        budget=MemoryContextBudget(allow_projections=True),
    )

    report = evaluate_memory_kernel_context(
        (projection,),
        budget=MemoryContextBudget(),
        pack=permissive_pack,
    )

    assert report.hard_failure_count == 1
    assert report.findings[0].severity is ContextEvalSeverity.HARD_FAILURE
    assert report.findings[0].kind == "projection_admitted_without_override"


def test_context_eval_requires_explicit_memory_surfaces(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    empty = run_context_eval(
        config=ContextEvalConfig(
            include_current_context=False,
            memory_surface_ids=(),
        ),
        memory_kernel=kernel,
    )
    explicit = run_context_eval(
        config=ContextEvalConfig(
            include_current_context=False,
            memory_surface_ids=("home.conversation_log",),
        ),
        memory_kernel=kernel,
    )

    assert empty.memory_kernel is not None
    assert empty.memory_kernel.atom_count == 0
    assert "no_memory_surfaces_configured" in empty.warnings
    assert explicit.memory_kernel is not None
    assert explicit.memory_kernel.atom_count == 1
    assert explicit.memory_kernel.pack.admitted_count == 0


def test_context_eval_current_reader_disables_semantic_feedback(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_read_memory_context(**kwargs):
        calls.append(kwargs)
        return "safe context"

    monkeypatch.setattr("dharma_swarm.context.read_memory_context", fake_read_memory_context)

    report = run_context_eval(
        config=ContextEvalConfig(query="memory kernel"),
        state_dir=tmp_path,
    )

    assert calls
    assert calls[0]["allow_semantic_search"] is False
    assert calls[0]["consumer"] == "memory_kernel.context_eval.shadow"
    assert report.current_context is not None
    assert report.hard_failure_count == 0


def test_context_eval_warning_count_includes_lane_warnings() -> None:
    report = run_context_eval(
        config=ContextEvalConfig(include_memory_kernel=False),
        current_context_text="Use /Users/dhyana/.dharma/state/runtime.db secret_token=abc123",
    )

    assert report.hard_failure_count == 0
    assert report.warning_count == 6


def test_context_eval_report_markdown_and_json_do_not_leak_paths() -> None:
    report = run_context_eval(
        config=ContextEvalConfig(include_memory_kernel=False),
        current_context_text="Unsafe path /Users/dhyana/.dharma/db/memory_plane.db",
    )
    payload = json.dumps(report.to_json(), sort_keys=True)
    markdown = render_context_eval_markdown(report)

    assert report.current_context is not None
    assert report.current_context.finding_count == 1
    assert "/Users/dhyana" not in payload
    assert "/Users/dhyana" not in markdown
    assert "Memory Context Safety Eval" in markdown


def test_default_context_eval_cases_pass_without_leaking_sensitive_literals() -> None:
    results = run_default_context_eval_cases()
    payload = json.dumps([result.to_json() for result in results], sort_keys=True)

    assert results
    assert all(result.passed for result in results)
    assert "current_context_redaction" in payload
    assert "projection_omitted_by_default" in payload
    assert "/Users/dhyana" not in payload
    assert "abc123" not in payload
