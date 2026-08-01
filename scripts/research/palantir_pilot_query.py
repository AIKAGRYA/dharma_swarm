#!/usr/bin/env python3
"""Query Palantir Pilot's local public-source workspace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    build_answer_packet_from_query_packet,
    build_query_packet,
    index_workspace_to_memory_plane,
    record_query_packet_to_memory_plane,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402


def _format_markdown(packet: dict[str, object]) -> str:
    source_hits = packet.get("source_hits")
    note_hits = packet.get("note_hits")
    sources = source_hits if isinstance(source_hits, list) else []
    notes = note_hits if isinstance(note_hits, list) else []

    lines = [
        "# Palantir Pilot Query",
        "",
        f"Query: `{packet.get('query', '')}`",
        f"Observed: {packet.get('observed_at', '')}",
        f"Latest source index: `{packet.get('latest_source_index', '')}`",
        f"Indexed URLs: {packet.get('indexed_url_count', 0)}",
        "",
        f"Boundary: {packet.get('source_boundary', '')}",
        "",
        "## Source Hits",
        "",
    ]
    if not sources:
        lines.append("- No source-index hits.")
    for item in sources:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- score={score} family={family} lastmod={lastmod} {url}".format(
                score=item.get("score", 0),
                family=item.get("family", ""),
                lastmod=item.get("lastmod", ""),
                url=item.get("url", ""),
            )
        )

    lines.extend(["", "## Note Hits", ""])
    if not notes:
        lines.append("- No wiki-note hits.")
    for item in notes:
        if not isinstance(item, dict):
            continue
        lines.append(f"- score={item.get('score', 0)} `{item.get('path', '')}`")
        snippet = str(item.get("snippet") or "")
        if snippet:
            lines.append(f"  {snippet}")

    lines.append("")
    return "\n".join(lines)


def _format_answer_markdown(packet: dict[str, object]) -> str:
    source_citations = packet.get("source_citations")
    note_citations = packet.get("note_citations")
    limitations = packet.get("limitations")
    sources = source_citations if isinstance(source_citations, list) else []
    notes = note_citations if isinstance(note_citations, list) else []
    limits = limitations if isinstance(limitations, list) else []

    lines = [
        "# Palantir Pilot Answer",
        "",
        f"Query: `{packet.get('query', '')}`",
        f"Observed: {packet.get('observed_at', '')}",
        f"Confidence: {packet.get('confidence', '')}",
        "",
        str(packet.get("answer") or ""),
        "",
        f"Boundary: {packet.get('source_boundary', '')}",
        "",
        "## Source Citations",
        "",
    ]
    if not sources:
        lines.append("- No public source URL citations.")
    for item in sources:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- family={family} lastmod={lastmod} {url}".format(
                family=item.get("family", ""),
                lastmod=item.get("lastmod", ""),
                url=item.get("url", ""),
            )
        )

    lines.extend(["", "## Note Citations", ""])
    if not notes:
        lines.append("- No local wiki-note citations.")
    for item in notes:
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('path', '')}`")
        snippet = str(item.get("snippet") or "")
        if snippet:
            lines.append(f"  {snippet}")

    lines.extend(["", "## Limitations", ""])
    for item in limits:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--db-path", default="")
    parser.add_argument("--family", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--index-workspace", action="store_true")
    parser.add_argument("--record-db", action="store_true")
    parser.add_argument("--answer", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    dharma_home = Path(args.dharma_home).expanduser()
    db_path = Path(args.db_path).expanduser() if args.db_path else None
    database_receipts: dict[str, object] = {}
    if args.index_workspace:
        database_receipts["workspace_index"] = index_workspace_to_memory_plane(
            dharma_home=dharma_home,
            db_path=db_path,
        )

    query_packet = build_query_packet(
        args.query,
        dharma_home=dharma_home,
        family=args.family or None,
        limit=max(1, args.limit),
    )
    if args.record_db:
        database_receipts["query_log"] = record_query_packet_to_memory_plane(
            query_packet,
            dharma_home=dharma_home,
            db_path=db_path,
            task_id=args.task_id or None,
        )

    packet = (
        build_answer_packet_from_query_packet(query_packet)
        if args.answer
        else query_packet
    )
    if database_receipts:
        packet["database_receipt"] = database_receipts

    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=True, default=str))
    elif args.answer:
        print(_format_answer_markdown(packet), end="")
    else:
        print(_format_markdown(packet), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
