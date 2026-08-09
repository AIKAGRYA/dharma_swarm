#!/usr/bin/env python3
"""darshan_pack.py — assemble the Darshan Pack: the organism seeing itself.

One small markdown artifact (≤4000 tokens) every agent and the operator can
read at session start. It is a *projection*, never an authority — each
section names its owner:

  1. Identity        — docs/wiki/ORGANISM_IDENTITY.md (canonical wiki text).
  2. Active tracks   — docs/governance/ACTIVE_TRACK.yaml (declared intent).
  3. State fullness  — live sqlite row counts from ~/.dharma/ (0/absent
                       when a store is missing; absence is a finding, not
                       an error).
  4. Task board      — ~/.dharma/board event log snapshot, if present.

Stdlib-only, deterministic for a given filesystem state, no network,
read-only (sqlite opened via file:...?mode=ro so absent DBs are never
created). Writes to stdout by default; --out PATH writes a file instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PAGE = REPO_ROOT / "docs/wiki/ORGANISM_IDENTITY.md"
ACTIVE_TRACK_PATH = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"

# Rough ceiling: ~4 chars/token keeps the pack safely under 4000 tokens.
MAX_PACK_CHARS = 15000
MAX_BOARD_KINDS = 8


def dharma_home() -> Path:
    """Runtime state root, resolved by its canonical owner (daemon_config)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from dharma_swarm.daemon_config import dharma_state_dir

    return dharma_state_dir()


def read_identity() -> str:
    """Return the identity page body with its YAML frontmatter stripped."""
    if not IDENTITY_PAGE.exists():
        return (
            "IDENTITY PAGE ABSENT — docs/wiki/ORGANISM_IDENTITY.md is "
            "missing; the wiki seed has not been metabolized here."
        )
    text = IDENTITY_PAGE.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return text.strip()


def parse_active_tracks() -> list[dict[str, str]]:
    """Parse active_tracks entries (id/name/status/serves) from the YAML.

    Uses PyYAML when importable, else a minimal line parser bound to the
    file's stable `active_tracks:` block layout. Only ACTIVE tracks are
    returned, sorted by id for determinism.
    """
    if not ACTIVE_TRACK_PATH.exists():
        return []
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(ACTIVE_TRACK_PATH.read_text(encoding="utf-8"))
        raw = data.get("active_tracks", []) if isinstance(data, dict) else []
        tracks = [
            {
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", "")),
                "status": str(entry.get("status", "")),
                "serves": str(entry.get("serves", "")),
            }
            for entry in raw
            if isinstance(entry, dict)
        ]
    except Exception:
        tracks = _parse_active_tracks_minimal()
    active = [t for t in tracks if t["status"] == "ACTIVE" and t["id"]]
    return sorted(active, key=lambda t: t["id"])


def _parse_active_tracks_minimal() -> list[dict[str, str]]:
    """Line-level fallback parser for the active_tracks block (no pyyaml)."""
    tracks: list[dict[str, str]] = []
    in_block = False
    current: dict[str, str] | None = None
    for line in ACTIVE_TRACK_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if line.startswith("active_tracks:"):
            in_block = True
            continue
        if in_block and line and not line.startswith((" ", "\t")):
            break  # next top-level key ends the block
        if not in_block:
            continue
        if line.startswith("  - id:"):
            current = {"id": stripped.partition("id:")[2].strip()}
            tracks.append(current)
        elif current is not None and line.startswith("    "):
            key, sep, value = stripped.partition(":")
            if sep and key in ("name", "status", "serves") and key not in current:
                current[key] = value.strip().strip("\"'")
    for track in tracks:
        for key in ("name", "status", "serves"):
            track.setdefault(key, "")
    return tracks


def sqlite_count(db_path: Path, table: str) -> str:
    """Row count for table in db_path as a string; 'absent' when unreadable.

    Read-only URI open: an absent database is never created by looking.
    """
    if not db_path.exists():
        return "absent"
    try:
        import sqlite3

        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not row or row[0] == 0:
                return "absent"
            return str(con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
        finally:
            con.close()
    except Exception:
        return "absent"


def state_fullness_lines() -> list[str]:
    """Live fullness counts for the knowledge/state stores (SEEING.md table)."""
    home = dharma_home()
    wiki_pages = sorted((REPO_ROOT / "docs/wiki").glob("*.md"))
    stores = [
        ("Wiki pages (docs/wiki/*.md)", str(len(wiki_pages))),
        (
            "Ontology objects (~/.dharma/ontology.db)",
            sqlite_count(home / "ontology.db", "objects"),
        ),
        (
            "Memory atoms (~/.dharma/agent_memory/memories.db)",
            sqlite_count(home / "agent_memory/memories.db", "memories"),
        ),
        (
            "Knowledge propositions (~/.dharma/state/knowledge.db)",
            sqlite_count(home / "state/knowledge.db", "propositions"),
        ),
        (
            "Vector documents (~/.dharma/vectors.db)",
            sqlite_count(home / "vectors.db", "vec_documents"),
        ),
    ]
    return [f"- {label}: {count}" for label, count in stores]


def board_snapshot_lines() -> list[str]:
    """Task-board event snapshot from ~/.dharma/board, guarded and read-only."""
    board_dir = dharma_home() / "board"
    if not board_dir.is_dir():
        return ["- Task board: absent"]
    db_files = sorted(
        p for p in board_dir.iterdir() if p.suffix in (".sqlite3", ".db", ".sqlite")
    )
    if not db_files:
        return ["- Task board: absent"]
    lines: list[str] = []
    for db_path in db_files:
        total = sqlite_count(db_path, "board_events")
        if total == "absent":
            lines.append(f"- {db_path.name}: no board_events table")
            continue
        lines.append(f"- {db_path.name}: {total} event(s)")
        try:
            import sqlite3

            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = con.execute(
                    "SELECT kind, count(*) FROM board_events "
                    "GROUP BY kind ORDER BY kind"
                ).fetchall()
            finally:
                con.close()
            for kind, count in rows[:MAX_BOARD_KINDS]:
                lines.append(f"  - {kind}: {count}")
        except Exception:
            lines.append("  - (event kinds unreadable)")
    return lines


def build_pack() -> str:
    """Assemble the full pack as markdown text."""
    tracks = parse_active_tracks()
    track_lines = [
        f"- `{t['id']}` — {t['name']} (serves `{t['serves']}`)" for t in tracks
    ] or ["- none declared ACTIVE (check docs/governance/ACTIVE_TRACK.yaml)"]

    sections = [
        "# DARSHAN PACK — the organism seeing itself",
        "",
        "Projection only. Owners: docs/wiki/ (identity), "
        "docs/governance/ACTIVE_TRACK.yaml (intent), ~/.dharma/ (runtime).",
        "",
        "## 1. Identity (docs/wiki/ORGANISM_IDENTITY.md)",
        "",
        read_identity(),
        "",
        f"## 2. Active tracks — declared intent ({len(tracks)} ACTIVE)",
        "",
        *track_lines,
        "",
        "## 3. State fullness — live counts (0/absent = empty store)",
        "",
        *state_fullness_lines(),
        "",
        "## 4. Task board snapshot",
        "",
        *board_snapshot_lines(),
        "",
        "Fullness check: `python3 scripts/governance/darshan_pack.py` · "
        "doctrine: docs/wiki/SEEING.md",
    ]
    pack = "\n".join(sections)
    if len(pack) > MAX_PACK_CHARS:
        pack = pack[:MAX_PACK_CHARS] + "\n[pack truncated at token ceiling]"
    return pack + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="darshan_pack",
        description="Assemble the Darshan Pack (organism self-view) as markdown.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the pack to PATH instead of stdout",
    )
    args = parser.parse_args(argv)
    pack = build_pack()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(pack, encoding="utf-8")
    else:
        sys.stdout.write(pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
