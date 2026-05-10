"""Check Tier-A pre-commit hook drift.

The canonical Tier-A hook IDs live in
`scripts/governance/pre_commit_config_fragment.yaml`. pre-commit has no native
fragment/include mechanism, so this checker verifies that the root
`.pre-commit-config.yaml` still contains the required hook IDs.

Usage:
    python3 scripts/governance/check_precommit_drift.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FRAGMENT = REPO_ROOT / "scripts/governance/pre_commit_config_fragment.yaml"
DEFAULT_PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

HOOK_ID_RE = re.compile(r"^\s*-\s+id:\s+([A-Za-z0-9_.-]+)\s*$")
REQUIRED_ID_RE = re.compile(r"^\s{4}-\s+([A-Za-z0-9_.-]+)\s*$")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}") from None


def required_hook_ids(fragment_text: str) -> list[str]:
    """Extract IDs from the fragment's `required_hook_ids` list."""
    ids: list[str] = []
    in_required_list = False

    for line in fragment_text.splitlines():
        stripped = line.strip()
        if stripped == "required_hook_ids:":
            in_required_list = True
            continue
        if in_required_list and line and not line.startswith(" "):
            break
        if in_required_list:
            match = REQUIRED_ID_RE.match(line)
            if match:
                ids.append(match.group(1))

    if not ids:
        raise SystemExit("No required hook IDs found in fragment.")
    return ids


def configured_hook_ids(pre_commit_text: str) -> set[str]:
    """Extract hook IDs from `.pre-commit-config.yaml`."""
    return {
        match.group(1)
        for line in pre_commit_text.splitlines()
        if (match := HOOK_ID_RE.match(line))
    }


def missing_required_hooks(required: list[str], configured: set[str]) -> list[str]:
    return [hook_id for hook_id in required if hook_id not in configured]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragment", type=Path, default=DEFAULT_FRAGMENT)
    parser.add_argument("--config", type=Path, default=DEFAULT_PRE_COMMIT_CONFIG)
    args = parser.parse_args()

    required = required_hook_ids(read_text(args.fragment))
    configured = configured_hook_ids(read_text(args.config))
    missing = missing_required_hooks(required, configured)

    print("Tier-A pre-commit drift check")
    print("-" * 60)
    print(f"Fragment: {args.fragment}")
    print(f"Config:   {args.config}")
    print(f"Required hook IDs: {', '.join(required)}")

    if missing:
        print()
        print("::warning::Missing required Tier-A pre-commit hook IDs:")
        for hook_id in missing:
            print(f"  - {hook_id}")
        return 1

    print()
    print("All required Tier-A hook IDs are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
