#!/usr/bin/env python3
"""Build and validate the read-only Agent Card meishi index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.agent_card_index import (  # noqa: E402
    build_agent_card_index,
    render_agent_card_index_markdown,
    write_agent_card_index_reports,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dharma-home", default=str(Path.home() / ".dharma"))
    parser.add_argument("--cards-dir", default="")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "reports" / "agent_card"))
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown report.")
    parser.add_argument("--no-write", action="store_true", help="Do not write reports.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when error findings exist.")
    args = parser.parse_args(argv)

    index = build_agent_card_index(
        repo_root=Path(args.repo_root),
        dharma_home=Path(args.dharma_home),
        cards_dir=Path(args.cards_dir) if args.cards_dir else None,
    )
    paths: dict[str, str] = {}
    if not args.no_write:
        paths = write_agent_card_index_reports(index, Path(args.out_dir))

    payload = {
        "summary": index["summary"],
        "paths": paths,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.markdown:
        print(render_agent_card_index_markdown(index))
    else:
        summary = index["summary"]
        print("Agent Card Meishi Index")
        print(f"status: {summary['status']}")
        print(f"cards: {summary['card_file_count']} agents: {summary['agent_count']}")
        print(f"errors: {summary['error_count']} warnings: {summary['warning_count']}")
        for label, path in paths.items():
            print(f"{label}: {path}")

    return 1 if args.strict and index["summary"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
