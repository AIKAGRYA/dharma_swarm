#!/usr/bin/env python3
"""Route a task or path to the right context engineering packet.

Read-only helper. It projects from docs/context_engineering/CONTEXT_PACKET_INDEX.json
and does not own any packet fact.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "docs/context_engineering/CONTEXT_PACKET_INDEX.json"
INDEX_SCHEMA_VERSION = "context-packet-index-v1.1"
ANCHOR_FIELDS = (
    "vision_anchors",
    "current_reality_anchors",
    "dense_docs",
    "future_agent_review_hooks",
)


@dataclass(frozen=True)
class PacketMatch:
    packet_id: str
    file: str
    score: int
    reasons: tuple[str, ...]

    def to_json(self, *, hydrate: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "packet_id": self.packet_id,
            "file": self.file,
            "score": self.score,
            "reasons": list(self.reasons),
        }
        if hydrate:
            packet = packet_by_id(self.packet_id)
            if packet is not None:
                for field in ANCHOR_FIELDS:
                    payload[field] = packet.get(field, [])
        return payload


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_./-]+", text)}


def _validate_anchor_items(packet_id: str, field: str, value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{packet_id} missing non-empty {field}")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{packet_id}.{field}[{index}] must be an object")
        if field == "future_agent_review_hooks":
            for key in ("when", "ask", "expect"):
                if not item.get(key):
                    raise ValueError(f"{packet_id}.{field}[{index}] missing {key}")
        else:
            for key in ("type", "ref", "why"):
                if not item.get(key):
                    raise ValueError(f"{packet_id}.{field}[{index}] missing {key}")


def _validate_index(data: dict[str, Any]) -> None:
    if data.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {INDEX_SCHEMA_VERSION}")
    for packet in data.get("packets", []):
        packet_id = str(packet.get("id", "<unknown>"))
        for field in ANCHOR_FIELDS:
            if field not in packet:
                raise ValueError(f"{packet_id} missing {field}")
            _validate_anchor_items(packet_id, field, packet[field])


def load_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_index(data)
    return data


def _path_matches(pattern: str, path: str) -> bool:
    normalized_pattern = pattern.replace("**", "*")
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, normalized_pattern)


def score_packet(packet: dict[str, Any], query: str, paths: tuple[str, ...]) -> PacketMatch:
    query_lower = query.lower()
    query_tokens = _tokens(query)
    score = 0
    reasons: list[str] = []

    packet_id = str(packet["id"])
    if packet_id.lower() in query_lower:
        score += 20
        reasons.append("id")

    for alias in packet.get("aliases", []):
        alias_text = str(alias).lower()
        alias_tokens = _tokens(alias_text)
        if alias_text and alias_text in query_lower:
            score += 8
            reasons.append(f"alias:{alias}")
        elif alias_tokens and alias_tokens <= query_tokens:
            score += 5
            reasons.append(f"alias_tokens:{alias}")

    for command in packet.get("commands", []):
        command_text = str(command).lower()
        if command_text and command_text in query_lower:
            score += 4
            reasons.append(f"command:{command}")

    for surface in packet.get("primary_surfaces", []):
        surface_text = str(surface)
        surface_lower = surface_text.lower().replace("**", "")
        if surface_lower and surface_lower in query_lower:
            score += 4
            reasons.append(f"surface_text:{surface}")
        for path in paths:
            if _path_matches(surface_text, path):
                score += 12
                reasons.append(f"path:{path}->{surface}")

    return PacketMatch(
        packet_id=packet_id,
        file=str(packet["file"]),
        score=score,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def route_packets(query: str, paths: tuple[str, ...] = (), top: int = 3) -> list[PacketMatch]:
    data = load_index()
    matches = [
        score_packet(packet, query, paths)
        for packet in data.get("packets", [])
    ]
    matches.sort(key=lambda match: (-match.score, match.packet_id))
    return [match for match in matches[:top] if match.score > 0]


def packet_by_id(packet_id: str) -> dict[str, Any] | None:
    data = load_index()
    for packet in data.get("packets", []):
        if packet.get("id") == packet_id:
            return packet
    return None


def _render_text(matches: list[PacketMatch]) -> str:
    if not matches:
        return "No packet match. Run make onboard, then inspect CONTEXT_PACKET_INDEX.json.\n"
    lines = ["Recommended context packets:"]
    for match in matches:
        reason_text = ", ".join(match.reasons) if match.reasons else "score"
        lines.append(f"- {match.packet_id} ({match.file}) score={match.score} reasons={reason_text}")
    return "\n".join(lines) + "\n"


def _label(field: str) -> str:
    labels = {
        "vision_anchors": "Vision anchors",
        "current_reality_anchors": "Current reality anchors",
        "dense_docs": "Dense docs",
        "future_agent_review_hooks": "Future-agent review hooks",
    }
    return labels[field]


def _render_anchors(packet: dict[str, Any]) -> str:
    lines = [f"{packet['id']} anchors:"]
    for field in ANCHOR_FIELDS:
        lines.append(f"{_label(field)}:")
        for item in packet.get(field, []):
            if field == "future_agent_review_hooks":
                lines.append(
                    f"- {item['when']}: {item['ask']} "
                    f"(expect: {item['expect']})"
                )
            else:
                lines.append(f"- {item['ref']} [{item['type']}]: {item['why']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help="Task/topic text to route")
    parser.add_argument("--path", action="append", default=[], help="Repo path touched by the task")
    parser.add_argument("--top", type=int, default=3, help="Number of packets to return")
    parser.add_argument("--id", help="Return an exact packet id")
    parser.add_argument("--print-packet", action="store_true", help="Print packet markdown for --id or top match")
    parser.add_argument("--show-anchors", action="store_true", help="Print compact packet anchors")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--hydrate", action="store_true", help="Include anchor metadata in route JSON")
    args = parser.parse_args(argv)

    if args.id:
        packet = packet_by_id(args.id)
        if packet is None:
            print(f"Unknown packet id: {args.id}", file=sys.stderr)
            return 2
        packet_path = REPO_ROOT / "docs/context_engineering" / str(packet["file"])
        if args.print_packet:
            print(packet_path.read_text(encoding="utf-8"))
        elif args.json:
            print(json.dumps(packet, indent=2))
        elif args.show_anchors:
            print(_render_anchors(packet), end="")
        else:
            print(f"{packet['id']} -> docs/context_engineering/{packet['file']}")
        return 0

    query = " ".join(args.query).strip()
    matches = route_packets(query, tuple(args.path), max(1, args.top))
    if args.print_packet and matches:
        packet = packet_by_id(matches[0].packet_id)
        if packet is None:
            print(f"Packet disappeared from index: {matches[0].packet_id}", file=sys.stderr)
            return 2
        packet_path = REPO_ROOT / "docs/context_engineering" / str(packet["file"])
        print(packet_path.read_text(encoding="utf-8"))
    elif args.json:
        print(json.dumps([match.to_json(hydrate=args.hydrate) for match in matches], indent=2))
    elif args.show_anchors and matches:
        print(_render_text(matches), end="\n")
        packet = packet_by_id(matches[0].packet_id)
        if packet is None:
            print(f"Packet disappeared from index: {matches[0].packet_id}", file=sys.stderr)
            return 2
        print(_render_anchors(packet), end="")
    else:
        print(_render_text(matches), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
