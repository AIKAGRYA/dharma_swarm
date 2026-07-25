"""OKF projector (Slice B) — export/import a portable knowledge graph.

Google's Open Knowledge Format (OKF v0.1): a bundle is a directory of markdown
files; each file is one concept and its path is its identifier; each opens with
YAML frontmatter whose ONLY required field is ``type``; two filenames are
reserved (``index.md`` listing, ``log.md`` history); concepts cross-reference
with ordinary markdown links, making the directory a graph.

This module is the swarm's outward face: it projects existing owners (the
Semantic Commons manifest, a MemoryKernel surface) to a portable bundle any
external human or agent can read, and ingests foreign bundles as a tolerant
consumer. It mints no truth — it serializes what an owner already holds.

Tolerant-consumer rule (OKF spec): a reader MUST NOT reject a bundle for a
missing optional field, an unknown ``type``, or a broken cross-link.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

OKF_VERSION = "0.1"
_RESERVED = {"index.md", "log.md"}


class OKFConcept(BaseModel):
    """One OKF concept = one markdown file. Its ``rel_path`` is its identifier.

    Proposed ontology api_name (defer to owner): ``dharma.knowledge.OKFConcept``.
    """

    rel_path: str               # e.g. "objects/A2ACard.md" — the identifier
    type: str                   # the ONE required OKF frontmatter field
    title: str = ""
    description: str = ""
    fields: dict[str, object] = Field(default_factory=dict)  # extra frontmatter
    body: str = ""              # markdown body (may contain links)
    links: list[str] = Field(default_factory=list)  # bundle-relative link targets


def _frontmatter(concept: OKFConcept) -> str:
    """Serialize frontmatter with ``type`` guaranteed first (OKF requirement)."""
    data: dict[str, object] = {"type": concept.type}
    if concept.title:
        data["title"] = concept.title
    if concept.description:
        data["description"] = concept.description
    for k, v in concept.fields.items():
        if k not in data:
            data[k] = v
    dumped = yaml.safe_dump(data, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{dumped}\n---\n"


def _render_body(concept: OKFConcept) -> str:
    """Body = description + explicit link list (so the directory forms a graph)."""
    parts: list[str] = []
    if concept.title:
        parts.append(f"# {concept.title}\n")
    if concept.body:
        parts.append(concept.body.rstrip() + "\n")
    elif concept.description:
        parts.append(concept.description.rstrip() + "\n")
    if concept.links:
        parts.append("\n## Related\n")
        for target in concept.links:
            name = Path(target).stem
            parts.append(f"- [{name}]({target})")
    return "\n".join(parts).rstrip() + "\n"


def _within(root: Path, candidate: Path) -> bool:
    """True if *candidate* resolves inside *root* (bundle containment guard)."""
    try:
        candidate.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def write_bundle(
    concepts: list[OKFConcept],
    root: str | Path,
    *,
    title: str = "Dharma Knowledge Bundle",
    okf_version: str = OKF_VERSION,
    today: str | None = None,
) -> Path:
    """Write concepts as an OKF bundle (one file per concept + index.md + log.md).

    Returns the bundle root. ``today`` is injectable so callers can stamp a date
    (this module never calls the clock itself — determinism for tests/replay).
    """
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    resolved_root = root_path.resolve()

    # Validate every concept path BEFORE writing: relative, non-reserved, and
    # contained within the bundle — a caller-supplied rel_path of "../x" or an
    # absolute path must never write outside the bundle root.
    targets: set[Path] = set()
    for concept in concepts:
        if Path(concept.rel_path).is_absolute():
            raise ValueError(f"OKF concept rel_path must be relative: {concept.rel_path}")
        target = (root_path / concept.rel_path).resolve()
        if Path(concept.rel_path).name in _RESERVED:
            raise ValueError(f"concept rel_path collides with reserved name: {concept.rel_path}")
        if not _within(resolved_root, target):
            raise ValueError(f"OKF concept rel_path escapes the bundle: {concept.rel_path}")
        targets.add(target)

    # Remove stale concept files (non-reserved *.md no longer in the set) so a
    # re-export after a rename/delete does not resurrect removed concepts via
    # read_bundle(). Only touches files inside the bundle root.
    for existing in root_path.rglob("*.md"):
        if existing.name in _RESERVED:
            continue
        if existing.resolve() not in targets:
            existing.unlink()

    for concept in concepts:
        target = root_path / concept.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_frontmatter(concept) + "\n" + _render_body(concept), encoding="utf-8")

    _write_index(root_path, concepts, title=title, okf_version=okf_version)
    _write_log(root_path, concepts, today=today)
    return root_path


def _write_index(root: Path, concepts: list[OKFConcept], *, title: str, okf_version: str) -> None:
    """index.md — progressive-disclosure listing (no frontmatter); declares version."""
    lines = [f"# {title}", "", f"okf_version: \"{okf_version}\"", "", "## Concepts", ""]
    for c in sorted(concepts, key=lambda c: c.rel_path):
        desc = c.description or c.title or c.type
        lines.append(f"- [{c.title or Path(c.rel_path).stem}]({c.rel_path}) — {desc}")
    (root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_log(root: Path, concepts: list[OKFConcept], *, today: str | None) -> None:
    """log.md — change history, ISO-8601 date heading, newest first."""
    stamp = today or "0000-00-00"
    lines = [
        "# Change Log",
        "",
        f"## {stamp}",
        "",
        f"**Creation** — bundle generated with {len(concepts)} concept(s).",
        "",
    ]
    (root / "log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_bundle(root: str | Path) -> list[OKFConcept]:
    """Ingest an OKF bundle as a TOLERANT consumer.

    Never raises on unknown ``type``, missing optional fields, or broken links
    (OKF spec). Files that fail to parse at all are skipped, not fatal. Reserved
    filenames (index.md/log.md) are not concepts.
    """
    root_path = Path(root)
    concepts: list[OKFConcept] = []
    for md in sorted(root_path.rglob("*.md")):
        if md.name in _RESERVED:
            continue
        try:
            text = md.read_text(encoding="utf-8")
            meta, body = _split_frontmatter(text)
            concepts.append(
                OKFConcept(
                    rel_path=str(md.relative_to(root_path)),
                    type=str(meta.get("type", "unknown")),  # tolerate missing type
                    title=str(meta.get("title", "")),
                    description=str(meta.get("description", "")),
                    fields={k: v for k, v in meta.items()
                            if k not in ("type", "title", "description")},
                    body=body,
                    links=_extract_links(body),
                )
            )
        except Exception:
            # Tolerant consumer: a malformed file does not sink the bundle.
            continue
    return concepts


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading ``---`` YAML frontmatter block from the body (yaml-parsed)."""
    if not text.lstrip().startswith("---"):
        return {}, text
    stripped = text.lstrip()
    end = stripped.find("\n---", 3)
    if end == -1:
        return {}, text
    block = stripped[3:end].strip()
    body = stripped[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(block) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def _extract_links(body: str) -> list[str]:
    """Pull markdown link targets ``[x](target)`` from a body."""
    import re

    return re.findall(r"\]\(([^)]+)\)", body)


# ── Projector: the Semantic Commons manifest -> an OKF bundle ───────────────


def project_semantic_objects(manifest_path: str | Path) -> list[OKFConcept]:
    """Project docs/ontology/semantic_objects.yaml into OKF concepts.

    Each runtime object becomes one concept; its OKF ``type`` is the object's
    ``kind`` (runtime_object, identifier, route_binding, ...). This makes the
    Semantic Commons a portable, browsable index of terms — the outward face of
    the ontology. Read-only projection: the manifest stays the owner.
    """
    data = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8")) or {}
    objects = data.get("objects", {}) if isinstance(data, dict) else {}
    concepts: list[OKFConcept] = []
    for name, spec in objects.items():
        spec = spec if isinstance(spec, dict) else {}
        kind = str(spec.get("kind", "runtime_object"))
        desc = str(spec.get("description", ""))
        # Links: any field whose value names another object in the manifest.
        links: list[str] = []
        for v in _flat_values(spec):
            if isinstance(v, str) and v in objects and v != name:
                tgt = f"objects/{v}.md"
                if tgt not in links:
                    links.append(tgt)
        body_lines = [desc, ""] if desc else []
        owner = spec.get("owner")
        if owner:
            body_lines.append(f"**Owner:** `{owner}`")
        concepts.append(
            OKFConcept(
                rel_path=f"objects/{name}.md",
                type=kind,
                title=name,
                description=desc,
                fields={k: v for k, v in spec.items()
                        if k in ("owner", "alias") and isinstance(v, (str, int, float, bool))},
                body="\n".join(body_lines),
                links=links,
            )
        )
    return concepts


def _flat_values(obj: object):
    """Yield scalar values nested anywhere in a dict/list (for link discovery)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flat_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flat_values(v)
    else:
        yield obj
