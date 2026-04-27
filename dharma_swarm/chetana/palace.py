"""chetana.palace — Memory Palace (L3) renderer.

The palace is the spatial frame of the PKM. Pillars are rooms, axioms are loci.
Atoms live in rooms based on their tags / `related:` pointers. The output is a
JSON Canvas file (kepano open spec) that opens natively in Obsidian and other
canvas-aware tools.

The 10 pillars are the canonical rooms:
    Levin · Kauffman · Jantsch · Deacon · Friston · Hofstadter ·
    Aurobindo · Dada Bhagwan · Varela · Beer

Plus 5 system rooms:
    Telos · R_V Research · Phoenix · Foundations · Operations

Atoms are mapped to rooms by:
    1. explicit `pillar:` frontmatter tag (highest priority)
    2. `related:` wikilinks pointing into a pillar's seed article
    3. tag overlap with pillar canon
    4. fallback: "Operations" room
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .provenance import parse_frontmatter
from .staging import TRUSTED_DEFAULT


logger = logging.getLogger(__name__)

DEFAULT_PALACE_PATH = Path.home() / ".dharma" / "knowledge" / "memory_palace.canvas"


PILLAR_ROOMS: dict[str, dict[str, Any]] = {
    "levin": {"label": "Levin (basal cognition)", "x": -1200, "y": -800, "color": "1"},
    "kauffman": {"label": "Kauffman (autocatalysis)", "x": -800, "y": -800, "color": "2"},
    "jantsch": {"label": "Jantsch (self-organizing universe)", "x": -400, "y": -800, "color": "3"},
    "deacon": {"label": "Deacon (absential causation)", "x": 0, "y": -800, "color": "4"},
    "friston": {"label": "Friston (active inference)", "x": 400, "y": -800, "color": "5"},
    "hofstadter": {"label": "Hofstadter (strange loops)", "x": 800, "y": -800, "color": "6"},
    "aurobindo": {"label": "Aurobindo (involution/evolution)", "x": -1200, "y": -400, "color": "1"},
    "dada_bhagwan": {"label": "Dada Bhagwan (Akram Vignan)", "x": -800, "y": -400, "color": "2"},
    "varela": {"label": "Varela (autopoiesis)", "x": -400, "y": -400, "color": "3"},
    "beer": {"label": "Beer (VSM)", "x": 0, "y": -400, "color": "4"},
    "telos": {"label": "Telos (Jagat Kalyan)", "x": 0, "y": 0, "color": "6"},
    "rv_research": {"label": "R_V Research (mechanistic)", "x": 400, "y": 0, "color": "5"},
    "phoenix": {"label": "Phoenix (behavioral)", "x": 800, "y": 0, "color": "5"},
    "foundations": {"label": "Foundations (10 pillars index)", "x": -800, "y": 0, "color": "1"},
    "operations": {"label": "Operations (everything else)", "x": -1200, "y": 400, "color": "4"},
}


@dataclass
class PalaceSnapshot:
    rooms: list[dict[str, Any]] = field(default_factory=list)
    atoms: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, int] = field(default_factory=dict)


def render_palace(
    *,
    roots: list[Path] | None = None,
    out_path: Path | None = None,
    canvas_width: int = 320,
    canvas_height: int = 80,
) -> tuple[Path, PalaceSnapshot]:
    """Walk trusted atoms, place each into a room, write a JSON Canvas."""
    roots = roots or [TRUSTED_DEFAULT]
    out_path = out_path or DEFAULT_PALACE_PATH

    snap = PalaceSnapshot()

    # Build room nodes.
    room_node_ids: dict[str, str] = {}
    for room_id, meta in PILLAR_ROOMS.items():
        node_id = f"room-{room_id}"
        room_node_ids[room_id] = node_id
        snap.rooms.append(
            {
                "id": node_id,
                "type": "group",
                "x": meta["x"],
                "y": meta["y"],
                "width": canvas_width + 40,
                "height": canvas_height * 5,
                "label": meta["label"],
                "color": meta["color"],
            }
        )
        snap.coverage[room_id] = 0

    # Walk atoms, assign each to a room, append a card node.
    atom_idx = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                schema, _body = parse_frontmatter(text)
            except Exception:
                continue
            if schema is None:
                continue
            room = _classify_atom_to_room(schema)
            snap.coverage[room] = snap.coverage.get(room, 0) + 1

            base = PILLAR_ROOMS[room]
            stack_y = base["y"] + (snap.coverage[room] - 1) * (canvas_height + 8)
            atom_idx += 1
            node_id = f"atom-{atom_idx:04d}"
            snap.atoms.append(
                {
                    "id": node_id,
                    "type": "file",
                    "file": str(path),
                    "x": base["x"] + 20,
                    "y": stack_y + 20,
                    "width": canvas_width,
                    "height": canvas_height,
                    "label": schema.title[:80],
                }
            )
            snap.edges.append(
                {
                    "id": f"edge-{atom_idx:04d}",
                    "fromNode": room_node_ids[room],
                    "toNode": node_id,
                    "fromSide": "right",
                    "toSide": "left",
                    "label": "contains",
                }
            )

    canvas = {
        "nodes": snap.rooms + snap.atoms,
        "edges": snap.edges,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(canvas, indent=2), encoding="utf-8")
    return out_path, snap


def _classify_atom_to_room(schema: Any) -> str:
    tags = [t.lower() for t in (getattr(schema, "tags", None) or [])]
    related = [r.lower() for r in (getattr(schema, "related", None) or [])]
    title_lower = (schema.title or "").lower()

    # explicit pillar: tag wins
    for t in tags:
        if t.startswith("pillar:"):
            room_key = t.split(":", 1)[1].strip()
            if room_key in PILLAR_ROOMS:
                return room_key

    # title / tag / related hints
    haystack = " ".join(tags + related + [title_lower])
    matchers = {
        "levin": ["levin", "bioelectric", "basal cognition", "cognitive light cone"],
        "kauffman": ["kauffman", "autocatalytic", "adjacent possible"],
        "jantsch": ["jantsch", "self-organizing universe", "dissipative"],
        "deacon": ["deacon", "absential", "autogenesis"],
        "friston": ["friston", "active inference", "free energy", "markov blanket"],
        "hofstadter": ["hofstadter", "strange loop", "tangled hierarchy", "eigenform"],
        "aurobindo": ["aurobindo", "involution", "supramental", "overmind"],
        "dada_bhagwan": ["akram", "dada", "shuddhatma", "pratishthit", "vignan", "swabhaav"],
        "varela": ["varela", "autopoiesis", "enactivism", "neurophenomenology"],
        "beer": ["beer ", "vsm", "viable system", "cybernetic"],
        "telos": ["telos", "jagat kalyan", "moksha", "purpose"],
        "rv_research": ["r_v", "rv ", "geometric lens", "mechanistic interpretability", "mistral", "transformer"],
        "phoenix": ["phoenix", "l3-l4", "level transition", "behavioral"],
        "foundations": ["pillar", "foundations", "ten-pillars"],
    }
    for room, needles in matchers.items():
        for n in needles:
            if n in haystack:
                return room
    return "operations"


def palace_summary(snap: PalaceSnapshot) -> str:
    lines = ["# Memory palace", "", "## Room coverage"]
    for room, count in sorted(snap.coverage.items(), key=lambda x: -x[1]):
        meta = PILLAR_ROOMS.get(room, {"label": room})
        lines.append(f"- {meta['label']}: {count} atoms")
    return "\n".join(lines)
