"""Self-organizing pass (Slice D) — propose-then-apply, dry-run first.

LlamaFS (iyaja/llama-fs) watches a messy directory and reorganizes it by content.
This slice takes the *safe* half of that idea: a BATCH, DRY-RUN-FIRST organizer
that PROPOSES a target layout and never mutates until the operator explicitly
confirms — mirroring the swarm's gate-everything ethos. Watch-mode is deferred.

Honesty note: classification here is deterministic (by file family), not
LLM-content-summarized. The LLM summary (LlamaFS's actual mechanism) is the later
upgrade; this slice ships the propose/apply *skeleton* with the human gate intact,
which is the part that must be right before any model is allowed to move a file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

# File family -> destination folder. The deterministic stand-in for LLM grouping.
_FAMILIES: dict[str, set[str]] = {
    "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
    "docs": {".md", ".txt", ".pdf", ".rst", ".doc", ".docx"},
    "code": {".py", ".js", ".ts", ".go", ".rs", ".sh", ".c", ".cpp", ".h"},
    "data": {".json", ".yaml", ".yml", ".csv", ".toml", ".parquet"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
}


class ReorgMove(BaseModel):
    """A single proposed move (src -> dst), with the reason it was proposed.

    Proposed ontology api_name (defer to owner): ``dharma.execution.ReorgMove``.
    """

    src: str
    dst: str
    reason: str = ""


class ReorgProposal(BaseModel):
    """A dry-run reorganization plan. NEVER applied until explicitly confirmed.

    Proposed ontology api_name (defer to owner): ``dharma.execution.ReorgProposal``.
    """

    root: str
    moves: list[ReorgMove] = Field(default_factory=list)
    generated_at: str = ""


class ApplyResult(BaseModel):
    """The record of applying a proposal (which moves ran, which were skipped)."""

    applied: list[ReorgMove] = Field(default_factory=list)
    skipped: list[ReorgMove] = Field(default_factory=list)


def _family_for(suffix: str) -> str:
    for family, exts in _FAMILIES.items():
        if suffix.lower() in exts:
            return family
    return "misc"


def propose_organization(
    root: str | Path, *, generated_at: str = ""
) -> ReorgProposal:
    """Scan a directory's top-level files and PROPOSE a by-family layout.

    Pure read — touches nothing. Only proposes moves for files that are not
    already under their family folder. ``generated_at`` is injected (the module
    never calls the clock — determinism for tests/replay).
    """
    root_path = Path(root).resolve()
    moves: list[ReorgMove] = []
    if not root_path.is_dir():
        return ReorgProposal(root=str(root_path), moves=[], generated_at=generated_at)
    for child in sorted(root_path.iterdir()):
        if not child.is_file():
            continue
        family = _family_for(child.suffix)
        dst = root_path / family / child.name
        if dst.resolve() == child.resolve():
            continue
        moves.append(
            ReorgMove(
                src=str(child.relative_to(root_path)),
                dst=str(dst.relative_to(root_path)),
                reason=f"by family: {child.suffix or 'no-ext'} -> {family}/",
            )
        )
    return ReorgProposal(root=str(root_path), moves=moves, generated_at=generated_at)


def render_proposal(proposal: ReorgProposal) -> str:
    """Render a proposal as operator-reviewable markdown."""
    lines = [f"# Reorg proposal for `{proposal.root}`", ""]
    if proposal.generated_at:
        lines.append(f"_generated: {proposal.generated_at}_\n")
    if not proposal.moves:
        lines.append("_No moves proposed — directory already organized._")
        return "\n".join(lines) + "\n"
    lines.append(f"{len(proposal.moves)} move(s) proposed (review before applying):\n")
    for m in proposal.moves:
        lines.append(f"- `{m.src}` → `{m.dst}`  _( {m.reason} )_")
    return "\n".join(lines) + "\n"


def apply_proposal(
    proposal: ReorgProposal,
    *,
    confirm: bool = False,
    write_ok=None,
) -> ApplyResult:
    """Apply a proposal — GATED. Refuses unless ``confirm=True`` is passed.

    The gate is the whole point of Slice D: no file moves without an explicit
    operator confirm. ``write_ok`` is an optional ``(src, dst) -> bool`` predicate
    (the seam for MemoryWritePolicy); a move it rejects is skipped, not forced.
    Moves never overwrite an existing destination, and never escape the root.
    """
    if not confirm:
        raise PermissionError(
            "apply_proposal requires confirm=True — dry-run-first; nothing moved."
        )
    root = Path(proposal.root).resolve()
    result = ApplyResult()
    for move in proposal.moves:
        src = (root / move.src).resolve()
        dst = (root / move.dst).resolve()
        # Guards: stay in root, source exists, never overwrite, honor write_ok.
        if not _within(root, src) or not _within(root, dst):
            result.skipped.append(move)
            continue
        if not src.is_file() or dst.exists():
            result.skipped.append(move)
            continue
        if write_ok is not None and not write_ok(str(src), str(dst)):
            result.skipped.append(move)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        result.applied.append(move)
    return result


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
        return True
    except ValueError:
        return False
