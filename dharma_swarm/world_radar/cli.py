"""CLI helpers for operator-supplied world radar signals."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_radar.bronze import (
    ingest_hn_algolia_to_bronze,
    ingest_operator_drops_to_bronze,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dharma_swarm.world_radar.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    drop = sub.add_parser("drop", help="append an operator world-signal drop")
    drop.add_argument("--title", required=True)
    drop.add_argument("--url", required=True)
    drop.add_argument("--note", default="")
    drop.add_argument("--tag", action="append", default=[])
    drop.add_argument("--state-dir", default="")
    bronze_drops = sub.add_parser(
        "bronze-operator-drops",
        help="admit existing operator drops into Bronze raw receipts",
    )
    bronze_drops.add_argument("--state-dir", default="")
    bronze_drops.add_argument("--max-items", type=int, default=10)
    bronze_drops.add_argument("--timeout-s", type=int, default=10)
    bronze_hn = sub.add_parser(
        "bronze-hn",
        help="fetch a bounded HN Algolia page into Bronze raw receipts",
    )
    bronze_hn.add_argument("--query", required=True)
    bronze_hn.add_argument("--limit", type=int, default=1)
    bronze_hn.add_argument("--timeout-s", type=int, default=10)
    bronze_hn.add_argument("--state-dir", default="")
    args = parser.parse_args(argv)
    if args.cmd == "drop":
        path = append_operator_drop(
            title=args.title,
            url=args.url,
            note=args.note,
            tags=tuple(args.tag or ()),
            state_dir=Path(args.state_dir).expanduser() if args.state_dir else None,
        )
        print(path)
        return 0
    if args.cmd == "bronze-operator-drops":
        result = ingest_operator_drops_to_bronze(
            state_dir=Path(args.state_dir).expanduser() if args.state_dir else None,
            max_items=args.max_items,
            timeout_s=args.timeout_s,
        )
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0 if result.ok else 1
    if args.cmd == "bronze-hn":
        result = ingest_hn_algolia_to_bronze(
            query=args.query,
            state_dir=Path(args.state_dir).expanduser() if args.state_dir else None,
            limit=args.limit,
            timeout_s=args.timeout_s,
        )
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0 if result.ok else 1
    return 2


def append_operator_drop(
    *,
    title: str,
    url: str,
    note: str = "",
    tags: tuple[str, ...] = (),
    state_dir: Path | None = None,
) -> Path:
    state = state_dir or dharma_state_dir()
    path = state / "meta" / "world_operator_drops.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": f"operator-{uuid4().hex[:12]}",
        "source": "operator_drop",
        "source_type": "operator_drop",
        "category": "company",
        "title": title.strip(),
        "description": note.strip(),
        "url": url.strip(),
        "keywords": [tag.strip() for tag in tags if tag.strip()],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
