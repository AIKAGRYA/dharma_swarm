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


@dataclass(frozen=True)
class PacketMatch:
    packet_id: str
    file: str
    score: int
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "file": self.file,
            "score": self.score,
            "reasons": list(self.reasons),
        }


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_./-]+", text)}


def load_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help="Task/topic text to route")
    parser.add_argument("--path", action="append", default=[], help="Repo path touched by the task")
    parser.add_argument("--top", type=int, default=3, help="Number of packets to return")
    parser.add_argument("--id", help="Return an exact packet id")
    parser.add_argument("--print-packet", action="store_true", help="Print packet markdown for --id or top match")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
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
        print(json.dumps([match.to_json() for match in matches], indent=2))
    else:
        print(_render_text(matches), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
