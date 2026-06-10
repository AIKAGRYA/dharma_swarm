#!/usr/bin/env python3
"""Regenerate hygiene catalogue and audit prompt from pattern files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_hygiene_integrity import (  # noqa: E402
    AUDIT_PROMPT,
    CATALOGUE,
    REPO_ROOT,
    load_patterns,
    render_audit_prompt,
    render_catalogue,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--write", action="store_true", help="write generated files")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    patterns = load_patterns(repo_root)
    outputs = {
        repo_root / CATALOGUE: render_catalogue(patterns),
        repo_root / AUDIT_PROMPT: render_audit_prompt(patterns),
    }

    if args.write:
        for path, text in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(repo_root)}")
        return 0

    for path, text in outputs.items():
        print(f"--- {path.relative_to(repo_root)} ---")
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
