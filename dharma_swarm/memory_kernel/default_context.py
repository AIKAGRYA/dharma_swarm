"""Default Memory Kernel context section helpers."""

from __future__ import annotations

import logging
from typing import Any

from dharma_swarm.context_compiler_utils import (
    ContextSection,
    dedupe_strings as _dedupe,
)
from dharma_swarm.memory_kernel import (
    MemoryContextBudget,
    MemoryContextPack,
    MemoryQuery,
    TruthState,
)

logger = logging.getLogger(__name__)


def build_memory_kernel_default_context(
    memory_kernel: Any,
    *,
    recall_query: str,
    token_budget: int,
) -> tuple[ContextSection | None, dict[str, Any]]:
    if memory_kernel is None:
        return None, {"status": "not_configured"}

    try:
        atom_budget = max(4, min(24, int(token_budget) // 100))
        pack = memory_kernel.preview_memory_pack(
            query=MemoryQuery(
                limit_total=atom_budget,
                limit_per_surface=atom_budget,
                include_content=True,
                max_canon_risk=None,
                max_pii_risk=None,
                include_high_risk=False,
                include_projections=False,
                include_unsafe=False,
                require_source_digest=True,
                require_source_row_key=True,
            ),
            budget=MemoryContextBudget(
                max_candidate_atoms=atom_budget,
                max_admitted_atoms=max(1, min(8, atom_budget)),
                max_total_chars=max(600, min(2400, int(token_budget) * 2)),
                max_atom_chars=420,
                include_content=True,
                require_context_admissible=False,
                allow_projections=False,
                allow_high_risk=False,
                allowed_truth_states=(
                    TruthState.OBSERVED,
                    TruthState.CLAIMED,
                    TruthState.CURATED,
                    TruthState.CANONICAL,
                ),
            ),
        )
    except Exception as exc:
        logger.debug("Memory Kernel default context failed", exc_info=True)
        return None, {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }

    metadata = memory_kernel_pack_metadata(pack)
    metadata["status"] = "used"
    metadata["query_present"] = bool(recall_query)
    return (
        ContextSection(
            name="Memory Kernel",
            priority=4,
            content=format_memory_kernel_pack(pack),
            source_refs=memory_kernel_pack_source_refs(pack),
            metadata=metadata,
        ),
        metadata,
    )


def memory_kernel_pack_metadata(pack: MemoryContextPack) -> dict[str, Any]:
    return {
        "pack_id": pack.pack_id,
        "candidate_count": pack.candidate_count,
        "admitted_count": pack.admitted_count,
        "omitted_count": pack.omitted_count,
        "candidate_truncated": pack.candidate_truncated,
        "warnings": list(pack.warnings),
    }


def memory_kernel_pack_source_refs(pack: MemoryContextPack) -> list[str]:
    refs: list[str] = []
    for item in pack.items:
        if not item.admitted:
            continue
        refs.append(f"memory_kernel:{item.surface_id}")
        refs.extend(item.source_refs)
    return _dedupe(refs)


def format_memory_kernel_pack(pack: MemoryContextPack) -> str:
    lines = [
        f"- pack_id={pack.pack_id}",
        f"- candidates={pack.candidate_count}",
        f"- admitted={pack.admitted_count}",
        f"- omitted={pack.omitted_count}",
    ]
    if pack.warnings:
        lines.append(f"- warnings={', '.join(str(item) for item in pack.warnings)}")

    admitted = [item for item in pack.items if item.admitted]
    if admitted:
        lines.extend(["", "Admitted atoms:"])
        for item in admitted[:8]:
            lines.append(
                "- "
                f"rank={item.rank} surface={item.surface_id} "
                f"type={_enum_value(item.atom_type)} truth={_enum_value(item.truth_state)} "
                f"authority={_enum_value(item.authority_level)}"
            )
            if item.selection_reasons:
                lines.append(f"  reasons={', '.join(item.selection_reasons)}")
            if item.content_snippet:
                lines.append(f"  snippet={_inline_context(item.content_snippet, 420)}")
    else:
        lines.extend(["", "Admitted atoms:", "- none"])

    omitted = [item for item in pack.items if not item.admitted]
    if omitted:
        lines.extend(["", "Omitted atoms:"])
        for item in omitted[:8]:
            lines.append(
                "- "
                f"surface={item.surface_id} type={_enum_value(item.atom_type)} "
                f"truth={_enum_value(item.truth_state)} "
                f"reasons={', '.join(item.omission_reasons)}"
            )
    return "\n".join(lines)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _inline_context(value: str, max_chars: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 14)].rstrip() + "...<truncated>"
