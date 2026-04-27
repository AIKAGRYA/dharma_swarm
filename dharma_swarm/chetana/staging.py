"""chetana.staging — the L0-staging area where untrusted atoms land.

Layout:
    ~/.dharma/knowledge/staging/<date>/<atom_id>.md  — pending atoms
    ~/.dharma/knowledge/quarantine/<date>/<atom_id>.md — atoms past stale_after
    ~/.dharma/knowledge/wiki/<atom_slug>.md  — promoted (existing wiki path)

The staging area is a flat append-only zone. Atoms in staging are NEVER
referenced by trusted layers. Only chetana.promote can move an atom out.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from .provenance import FrontmatterSchema, assemble_atom, render_frontmatter_yaml


STAGING_ROOT = Path.home() / ".dharma" / "knowledge" / "staging"
QUARANTINE_ROOT = Path.home() / ".dharma" / "knowledge" / "quarantine"
WIKI_ROOT = Path.home() / ".dharma" / "knowledge" / "wiki"
TRUSTED_DEFAULT = WIKI_ROOT / "concepts"


def staging_path_for(atom_id: str, when: date | None = None) -> Path:
    when = when or date.today()
    return STAGING_ROOT / when.isoformat() / f"{atom_id}.md"


def quarantine_path_for(atom_id: str, when: date | None = None) -> Path:
    when = when or date.today()
    return QUARANTINE_ROOT / when.isoformat() / f"{atom_id}.md"


def trusted_path_for(slug: str, root: Path | None = None) -> Path:
    root = root or TRUSTED_DEFAULT
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in slug.lower())
    safe = safe.strip("-")[:120] or "atom"
    return root / f"{safe}.md"


def write_staged(schema: FrontmatterSchema, body: str, *, when: date | None = None) -> Path:
    """Write a new staged atom. Returns the path."""
    if schema.provenance is not None:
        raise ValueError("staged atoms must NOT have provenance set; use chetana.promote first")
    path = staging_path_for(schema.atom_id, when=when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(assemble_atom(schema, body), encoding="utf-8")
    return path


def write_trusted(
    schema: FrontmatterSchema,
    body: str,
    *,
    slug: str | None = None,
    root: Path | None = None,
) -> Path:
    """Write a promoted atom into the wiki. Provenance MUST be set."""
    if schema.provenance is None:
        raise ValueError("trusted atoms MUST carry provenance; promote them first")
    target = trusted_path_for(slug or _derive_slug(schema.title), root=root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(assemble_atom(schema, body), encoding="utf-8")
    return target


def quarantine_atom(staged_path: Path, *, when: date | None = None) -> Path:
    """Move a staged or trusted atom to quarantine (e.g., on stale_after expiry)."""
    if not staged_path.exists():
        raise FileNotFoundError(staged_path)
    when = when or date.today()
    target = QUARANTINE_ROOT / when.isoformat() / staged_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged_path), str(target))
    return target


def list_staged() -> list[Path]:
    if not STAGING_ROOT.exists():
        return []
    return sorted(p for p in STAGING_ROOT.rglob("*.md") if p.is_file())


def list_trusted(root: Path | None = None) -> list[Path]:
    root = root or TRUSTED_DEFAULT
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def list_quarantine() -> list[Path]:
    if not QUARANTINE_ROOT.exists():
        return []
    return sorted(p for p in QUARANTINE_ROOT.rglob("*.md") if p.is_file())


def _derive_slug(title: str) -> str:
    s = title.lower().strip()
    s = "".join(c if c.isalnum() or c.isspace() else "-" for c in s)
    s = "-".join(s.split())
    return s.strip("-") or "atom"
