#!/usr/bin/env python3
"""Render or write the Palantir Pilot public-source manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.palantir_pilot import (  # noqa: E402
    WIKI_HOME,
    build_source_manifest,
    format_markdown,
    write_wiki_home,
)
from dharma_swarm.palantir_pilot_manifest import default_dharma_home  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dharma-home", default=str(default_dharma_home()))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-wiki", action="store_true")
    args = parser.parse_args(argv)

    dharma_home = Path(args.dharma_home).expanduser()
    manifest = build_source_manifest(
        repo_root=Path(args.repo_root),
        dharma_home=dharma_home,
    )

    if args.write_wiki:
        write_wiki_home(dharma_home / WIKI_HOME, manifest)

    if args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=True, default=str))
    else:
        print(format_markdown(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
