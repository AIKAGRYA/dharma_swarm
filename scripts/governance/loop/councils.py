#!/usr/bin/env python3
"""Council prompt resolver.

Maps a ``(council_id, prompt_id)`` pair to the ported ``PROMPTS.md`` file path
under ``councils/``. The five councils are ported verbatim from the Desktop
suite (numbered dirs ``01_testing_verification`` through
``05_governance_evidence_fitness``).

Usage:
    python3 scripts/governance/loop/councils.py resolve <council_id> <prompt_id>
    python3 scripts/governance/loop/councils.py list

Exit codes:
    0   resolution succeeded (path printed) / list succeeded
    2   unknown council_id or prompt_id not found in the council's PROMPTS.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COUNCILS_REL = Path("councils")

# council_id -> ported directory name under councils/
COUNCIL_DIRS: dict[str, str] = {
    "testing_verification": "01_testing_verification",
    "architecture_complexity": "02_architecture_complexity",
    "runtime_distributed_reliability": "03_runtime_distributed_reliability",
    "ai_slop_prompt_security": "04_ai_slop_prompt_security",
    "governance_evidence_fitness": "05_governance_evidence_fitness",
}


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _councils_root(repo_root: Path | None = None) -> Path:
    return (repo_root or _default_repo_root()) / COUNCILS_REL


def list_councils() -> list[str]:
    return list(COUNCIL_DIRS)


def resolve_council_dir(council_id: str, repo_root: Path | None = None) -> Path | None:
    dir_name = COUNCIL_DIRS.get(council_id)
    if dir_name is None:
        return None
    d = _councils_root(repo_root) / dir_name
    return d if d.is_dir() else None


def _prompt_present(prompts_md: Path, prompt_id: str) -> bool:
    try:
        text = prompts_md.read_text()
    except OSError:
        return False
    # word-boundary match so "TV-01" does not match "TV-010"
    pattern = r"(?<![A-Za-z0-9])" + re.escape(prompt_id) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def resolve_prompt_path(
    council_id: str, prompt_id: str, repo_root: Path | None = None
) -> Path | None:
    """Resolve (council_id, prompt_id) to the ported PROMPTS.md path.

    Returns None if the council is unknown or the prompt_id does not appear in
    that council's PROMPTS.md.
    """
    d = resolve_council_dir(council_id, repo_root=repo_root)
    if d is None:
        return None
    prompts_md = d / "PROMPTS.md"
    if not prompts_md.is_file():
        return None
    if not _prompt_present(prompts_md, prompt_id):
        return None
    return prompts_md


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve council_id + prompt_id to a PROMPTS.md path.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve", help="resolve a council_id + prompt_id to a PROMPTS.md path")
    p_resolve.add_argument("council_id")
    p_resolve.add_argument("prompt_id")

    sub.add_parser("list", help="list known council_ids")

    args = parser.parse_args(argv)

    if args.command == "list":
        for cid in list_councils():
            sys.stdout.write(cid + "\n")
        return 0

    if args.command == "resolve":
        path = resolve_prompt_path(args.council_id, args.prompt_id)
        if path is None:
            sys.stderr.write(
                f"unresolved: council_id={args.council_id!r} prompt_id={args.prompt_id!r}\n"
            )
            return 2
        sys.stdout.write(str(path) + "\n")
        return 0

    # argparse(required=True) guards this, but keep a defensive return.
    return 2


if __name__ == "__main__":
    sys.exit(main())
