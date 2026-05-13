from __future__ import annotations

import json

from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    MemoryAtom,
    MemoryAtomType,
    MemoryContextBudget,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
    preview_memory_pack,
    render_memory_context_pack_markdown,
)


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


def test_context_pack_admits_only_context_admissible_observed_atoms() -> None:
    admitted_atom = _atom()
    raw_atom = _atom(content_ref="runtime_event:2", context_admissible=False)
    projection_atom = _atom(
        surface=_surface(
            surface_id="home.vectors",
            category=SurfaceCategory.PROJECTION,
            role=MemorySurfaceRole.PROJECTION_INDEX,
            authority_level=AuthorityLevel.LOW,
            projection_of=("home.memory_plane",),
        ),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="chunk:1",
        truth_state=TruthState.DERIVED,
    )

    pack = preview_memory_pack((admitted_atom, raw_atom, projection_atom))

    assert pack.admitted_count == 1
    assert pack.omitted_count == 2
    assert pack.items[0].admitted is True
    assert pack.items[0].content_snippet is None
    assert "reference_only" in pack.items[0].selection_reasons
    assert "atom_not_context_admissible" in pack.items[1].omission_reasons
    assert "projection_blocked" in pack.items[2].omission_reasons
    assert "truth_state_not_allowed" in pack.items[2].omission_reasons


def test_context_pack_redacts_local_refs_and_keeps_content_out_by_default() -> None:
    atom = _atom(
        content="private path /Users/dhyana/.dharma/state/runtime.db should not leak",
    )

    pack = preview_memory_pack((atom,))
    payload = json.dumps(pack.to_json(), sort_keys=True)

    assert pack.admitted_count == 1
    assert pack.items[0].content_snippet is None
    assert "content_available_but_not_included" in pack.items[0].warnings
    assert "local_path_refs_redacted" in pack.items[0].warnings
    assert "/Users/dhyana" not in payload


def test_context_pack_can_include_bounded_redacted_content_when_opted_in() -> None:
    atom = _atom(
        content="safe prefix /Users/dhyana/secret/file.md with trailing content",
    )

    pack = preview_memory_pack(
        (atom,),
        budget=MemoryContextBudget(include_content=True, max_atom_chars=36),
    )
    payload = json.dumps(pack.to_json(), sort_keys=True)

    assert pack.admitted_count == 1
    assert pack.items[0].content_snippet is not None
    assert "<local_path_redacted>" in pack.items[0].content_snippet
    assert pack.items[0].content_snippet.endswith("...<truncated>")
    assert "/Users/dhyana" not in payload


def test_context_pack_markdown_is_preview_not_promotion() -> None:
    pack = preview_memory_pack((_atom(),))

    rendered = render_memory_context_pack_markdown(pack)

    assert "# Memory Context Pack Preview" in rendered
    assert "does not inject prompts, promote memories, or write feedback" in rendered
