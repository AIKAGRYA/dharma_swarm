#!/usr/bin/env python3
"""orientation_graph.py — one-command, whole-system orientation view.

Renders the organism AT ONCE — identity (why), organs, active tracks,
canon custody, liveness, and broken register — as one typed, queryable
packet. A fresh agent should be able to answer "what is this system,
what lives inside it, what is live, what is broken, and what is canon"
from this single command.

This command does NOT own any fact. It projects from the existing owners:

    identity   -> foundations/THE_ORGANISM.md + docs/vision_maps/NORTH_STAR.md
    organs     -> docs/governance/VENTURE_CELL_PORTFOLIO.yaml
    tracks     -> docs/governance/ACTIVE_TRACK.yaml
    custody    -> docs/docops/assertions.yaml (canonical_guard.registered) + git
    liveness   -> live ops census receipt (scripts/runtime/live_ops_census.py)
    broken     -> docs/state/BROKEN_REGISTER.md

Doctrine line that must hold (same as the reconciliation track's):
    Read models project truth from owners; they do not become authority.

Usage:
    python3 scripts/governance/orientation_graph.py          # human view
    python3 scripts/governance/orientation_graph.py --json   # machine packet
    make orient

Write behavior: never writes. Exit code: always 0 (informational).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

ORGANISM_DOC = REPO_ROOT / "foundations/THE_ORGANISM.md"
NORTH_STAR_DOC = REPO_ROOT / "docs/vision_maps/NORTH_STAR.md"
GENOME_SYNTHESIS = REPO_ROOT / "reports/swarm_genome/2026-06-11/SYNTHESIS.md"
PORTFOLIO = REPO_ROOT / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
ASSERTIONS = REPO_ROOT / "docs/docops/assertions.yaml"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"

_STATE_ROOT = Path(os.environ.get("DHARMA_STATE_ROOT", str(Path.home() / ".dharma")))
CENSUS_RECEIPT = _STATE_ROOT / "ops" / "live_process_census.json"


@dataclass
class Identity:
    one_line: str
    read_first: list[str]
    missing_sources: list[str] = field(default_factory=list)


@dataclass
class Organ:
    id: str
    instrument: str
    status: str
    external_name: str = ""


@dataclass
class Track:
    id: str
    status: str
    serves: str
    owner: str
    owned_surfaces: list[str] = field(default_factory=list)


@dataclass
class CustodyReport:
    registered_total: int
    present: int
    missing: list[str] = field(default_factory=list)


@dataclass
class Liveness:
    receipt: str
    generated_at: str = ""
    surfaces: list[dict[str, str]] = field(default_factory=list)


@dataclass
class BrokenItem:
    id: str
    status: str
    title: str


@dataclass
class OrientationPacket:
    identity: Identity
    organs: list[Organ]
    tracks: list[Track]
    custody: CustodyReport
    liveness: Liveness
    broken: list[BrokenItem]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def build_identity() -> Identity:
    read_first = [
        "foundations/THE_ORGANISM.md",
        "docs/vision_maps/NORTH_STAR.md",
        "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
        "docs/MEGAFILE_INDEX.md",
    ]
    missing = [p for p in read_first if not (REPO_ROOT / p).exists()]
    one_line = ""
    if ORGANISM_DOC.exists():
        for line in ORGANISM_DOC.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("> **dharma_swarm is"):
                one_line = stripped.lstrip("> ").strip().strip("*")
                break
    if not one_line:
        one_line = ("(identity owner missing — read docs/vision_maps/"
                    "NORTH_STAR.md §1 for the telos)")
    return Identity(one_line=one_line, read_first=read_first,
                    missing_sources=missing)


def build_organs() -> list[Organ]:
    data = _load_yaml(PORTFOLIO)
    organs: list[Organ] = []
    for cell in data.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        organs.append(Organ(
            id=str(cell.get("id", "")),
            instrument=str(cell.get("instrument", "")),
            status=str(cell.get("status", "")),
            external_name=str(cell.get("external_name", "") or ""),
        ))
    return organs


def build_tracks() -> list[Track]:
    data = _load_yaml(ACTIVE_TRACK)
    tracks: list[Track] = []
    for entry in data.get("active_tracks") or []:
        if not isinstance(entry, dict):
            continue
        tracks.append(Track(
            id=str(entry.get("id", "")),
            status=str(entry.get("status", "")),
            serves=str(entry.get("serves", "")),
            owner=str(entry.get("owner", "")),
            owned_surfaces=[str(s) for s in entry.get("owned_surfaces") or []],
        ))
    return tracks


def build_custody() -> CustodyReport:
    registered: list[str] = []
    try:
        data = json.loads(ASSERTIONS.read_text(encoding="utf-8"))
        guard = data.get("canonical_guard", {})
        registered = [str(p) for p in guard.get("registered") or []]
    except Exception:
        data = _load_yaml(ASSERTIONS)
        guard = data.get("canonical_guard", {}) if isinstance(data, dict) else {}
        registered = [str(p) for p in guard.get("registered") or []]
    missing = [p for p in registered if not (REPO_ROOT / p).exists()]
    return CustodyReport(
        registered_total=len(registered),
        present=len(registered) - len(missing),
        missing=missing,
    )


def build_liveness() -> Liveness:
    if not CENSUS_RECEIPT.exists():
        return Liveness(receipt=(
            "no census receipt — run "
            "python3 scripts/runtime/live_ops_census.py --write"))
    try:
        payload = json.loads(CENSUS_RECEIPT.read_text(encoding="utf-8"))
    except Exception:
        return Liveness(receipt=f"unreadable receipt at {CENSUS_RECEIPT}")
    surfaces = []
    for surface in payload.get("surfaces") or []:
        if not isinstance(surface, dict):
            continue
        surfaces.append({
            "id": str(surface.get("surface_id", "")),
            "label": str(surface.get("label", "")),
            "status": str(surface.get("status", "")),
        })
    return Liveness(
        receipt=str(CENSUS_RECEIPT),
        generated_at=str(payload.get("generated_at", "")),
        surfaces=surfaces,
    )


_BR_HEAD = re.compile(r"^###\s+(?P<id>BR-\d+)\s*[—-]\s*(?P<title>.+)$")
_BR_STATUS = re.compile(r"^-\s*\*\*status:\*\*\s*(?P<status>[A-Z]+)")


def build_broken() -> list[BrokenItem]:
    items: list[BrokenItem] = []
    if not BROKEN_REGISTER.exists():
        return items
    current: BrokenItem | None = None
    for line in BROKEN_REGISTER.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## CLOSED"):
            break
        head = _BR_HEAD.match(stripped)
        if head:
            current = BrokenItem(id=head.group("id"), status="OPEN",
                                 title=head.group("title").strip())
            items.append(current)
            continue
        status = _BR_STATUS.match(stripped)
        if status and current is not None:
            current.status = status.group("status")
    return [i for i in items if i.status not in {"FIXED", "CLOSED"}]


def build_packet() -> OrientationPacket:
    return OrientationPacket(
        identity=build_identity(),
        organs=build_organs(),
        tracks=build_tracks(),
        custody=build_custody(),
        liveness=build_liveness(),
        broken=build_broken(),
    )


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def render(packet: OrientationPacket) -> None:
    _section("ORIENTATION — the whole organism at once (projection, not authority)")
    print(f"  {packet.identity.one_line}")
    print("  Read-first:")
    for path in packet.identity.read_first:
        marker = "MISSING " if path in packet.identity.missing_sources else ""
        print(f"    - {marker}{path}")

    _section(f"ORGANS ({len(packet.organs)}) — owner: docs/governance/VENTURE_CELL_PORTFOLIO.yaml")
    for organ in packet.organs:
        name = f" ({organ.external_name})" if organ.external_name else ""
        print(f"  [{organ.status:<18}] {organ.id}{name} — {organ.instrument}")

    _section(f"ACTIVE TRACKS ({len(packet.tracks)}) — owner: docs/governance/ACTIVE_TRACK.yaml")
    for track in packet.tracks:
        print(f"  [{track.status}] {track.id} serves={track.serves} owner={track.owner}")
        for surface in track.owned_surfaces:
            print(f"      owns {surface}")

    _section("CANON CUSTODY — owner: docs/docops/assertions.yaml canonical_guard.registered")
    print(f"  Registered canon docs: {packet.custody.registered_total} "
          f"(present in this checkout: {packet.custody.present})")
    for path in packet.custody.missing:
        print(f"  MISSING: {path}")

    _section("LIVENESS — owner: live ops census receipt (read-only)")
    print(f"  Receipt: {packet.liveness.receipt}")
    if packet.liveness.generated_at:
        print(f"  Generated: {packet.liveness.generated_at}")
    for surface in packet.liveness.surfaces:
        print(f"  [{surface['status']:<8}] {surface['id']} — {surface['label']}")

    _section(f"BROKEN REGISTER — open-like items ({len(packet.broken)})")
    for item in packet.broken:
        print(f"  [{item.status}] {item.id} — {item.title}")

    print()
    print("  Depth: make onboard (state) · docs/MEGAFILE_INDEX.md (maps)")
    print("  This view writes nothing and owns nothing.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the whole organism at once from its owners.")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the machine packet JSON to stdout")
    args = parser.parse_args(argv)
    packet = build_packet()
    if args.as_json:
        print(json.dumps(asdict(packet), sort_keys=True, indent=1))
    else:
        render(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
