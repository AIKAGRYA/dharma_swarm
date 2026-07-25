"""Semantic FS facade (Slice C) — LSFS-style syscalls over the MemoryKernel.

LSFS (arXiv 2410.11843) gives a filesystem semantic syscalls — keywords_retrieve,
semantic_retrieve, group_semantic, integrated_retrieve — backed by a semantic
index. The swarm already HAS the index: the MemoryKernel front door over the
registered vector/graph/log surfaces. This module is a thin facade that exposes
the LSFS vocabulary and delegates to that front door. It builds NO new vector DB
and owns NO store — it wraps what exists (converge, don't duplicate).

Honesty note: true embedding-ranked retrieval lives in the surface adapters. At
this layer ``semantic_retrieve`` is a *lexical* proxy (keyword overlap over the
bounded candidate set the kernel returns). The seam is here for the embedding
ranker to slot into later without changing callers.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from dharma_swarm.memory_kernel.atoms import MemoryAtomType, MemoryQuery

# Words too common to carry retrieval signal (the LSFS Parser's stop set).
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "what", "which", "how", "find", "show", "get", "me", "my", "this", "that",
    "with", "about", "from", "into", "all", "any",
}
_WORD_RE = re.compile(r"[a-z0-9_]+")


class ScoredAtom(BaseModel):
    """A retrieval hit — a thin projection of a MemoryAtom (not the atom itself).

    Proposed ontology api_name (defer to owner): ``dharma.knowledge.RetrievalHit``.
    """

    surface_id: str = ""
    atom_type: str = ""
    surface_role: str = ""
    score: float = 0.0
    snippet: str = ""


def parse_query(prompt: str, *, max_terms: int = 8) -> list[str]:
    """LSFS-Parser analog: extract retrieval keywords from a natural-language ask."""
    seen: list[str] = []
    for tok in _WORD_RE.findall((prompt or "").lower()):
        if tok in _STOP or len(tok) < 2 or tok in seen:
            continue
        seen.append(tok)
        if len(seen) >= max_terms:
            break
    return seen


def _atom_text(atom: object) -> str:
    """Best-effort text of an atom for lexical scoring (duck-typed)."""
    for attr in ("content", "summary", "title", "content_ref"):
        val = getattr(atom, attr, None)
        if isinstance(val, str) and val:
            return val
    return ""


def _enum_value(val: object) -> str:
    return getattr(val, "value", str(val)) if val is not None else ""


class SemanticFS:
    """LSFS-style syscalls over a MemoryKernel-like front door.

    The kernel only needs ``iter_memory_atoms(*, surface_ids, atom_types, query,
    limit_total)`` — so a real MemoryKernel or a test fake both work.
    """

    def __init__(self, kernel: object) -> None:
        self._kernel = kernel

    def _candidates(
        self,
        *,
        surface_ids: list[str] | None,
        atom_types: set[MemoryAtomType] | None,
        cap: int,
    ) -> list[object]:
        query = MemoryQuery(limit_total=cap, include_content=True)
        return list(
            self._kernel.iter_memory_atoms(
                surface_ids=surface_ids,
                atom_types=atom_types,
                query=query,
                limit_total=cap,
            )
        )

    def keywords_retrieve(
        self,
        keywords: list[str],
        *,
        k: int = 8,
        surface_ids: list[str] | None = None,
        atom_types: set[MemoryAtomType] | None = None,
    ) -> list[ScoredAtom]:
        """Rank bounded candidate atoms by keyword overlap; return top-k hits."""
        terms = [w.lower() for w in keywords if w]
        cap = max(50, k * 6)
        hits: list[ScoredAtom] = []
        for atom in self._candidates(surface_ids=surface_ids, atom_types=atom_types, cap=cap):
            text = _atom_text(atom).lower()
            if not text or not terms:
                continue
            matched = sum(1 for t in terms if t in text)
            if matched == 0:
                continue
            hits.append(
                ScoredAtom(
                    surface_id=getattr(atom, "surface_id", ""),
                    atom_type=_enum_value(getattr(atom, "atom_type", "")),
                    surface_role=_enum_value(getattr(atom, "surface_role", "")),
                    score=matched / len(terms),
                    snippet=_atom_text(atom)[:200],
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def semantic_retrieve(
        self, query: str, *, k: int = 8, surface_ids: list[str] | None = None
    ) -> list[ScoredAtom]:
        """Natural-language retrieve (lexical proxy today; embedding seam later)."""
        return self.keywords_retrieve(parse_query(query), k=k, surface_ids=surface_ids)

    def group_semantic(self, hits: list[ScoredAtom]) -> dict[str, list[ScoredAtom]]:
        """Group hits by surface_role (LSFS group_semantic analog)."""
        groups: dict[str, list[ScoredAtom]] = {}
        for h in hits:
            groups.setdefault(h.surface_role or h.surface_id or "unknown", []).append(h)
        return groups

    def integrated_retrieve(
        self, query: str, *, k: int = 8
    ) -> dict[str, list[ScoredAtom]]:
        """Retrieve across all surfaces, then group (LSFS integrated_retrieve)."""
        return self.group_semantic(self.semantic_retrieve(query, k=k))
