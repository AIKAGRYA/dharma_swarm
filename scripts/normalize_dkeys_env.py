#!/usr/bin/env python3
"""Normalize dkeys env var names to dharma_swarm canonical names.

Usage:
    # Dry-run — show what would be normalized, no mutation:
    python scripts/normalize_dkeys_env.py

    # Apply — copy alias values to canonical names in current process:
    python scripts/normalize_dkeys_env.py --apply

    # Emit shell export statements for sourcing:
    eval "$(python scripts/normalize_dkeys_env.py --emit-exports)"

The alias table lives in ``dharma_swarm.api_keys.ENV_ALIASES`` — that is the
single source of truth.  This script is a convenience wrapper.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the repo root is importable even when invoked directly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dharma_swarm.api_keys import ENV_ALIASES, normalize_env_aliases


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "***"
    return value[:4] + "..." + value[-2:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--apply",
        action="store_true",
        help="Mutate os.environ (useful when sourced via exec/subprocess).",
    )
    group.add_argument(
        "--emit-exports",
        action="store_true",
        help="Print shell export statements to stdout for eval.",
    )
    args = parser.parse_args()

    if args.emit_exports:
        # Emit shell logic that copies values during eval without printing them.
        for alias, canonical in ENV_ALIASES.items():
            if alias == canonical:
                continue
            sys.stdout.write(
                f"if [ -n \"${{{alias}:-}}\" ] && [ -z \"${{{canonical}:-}}\" ]; "
                f"then export {canonical}=\"${{{alias}}}\"; fi\n"
            )
        return

    applied = normalize_env_aliases(dry_run=not args.apply)

    if not applied:
        alias_count = sum(1 for alias, canonical in ENV_ALIASES.items() if alias != canonical)
        aliases_present = sum(
            1
            for alias, canonical in ENV_ALIASES.items()
            if alias != canonical and os.environ.get(alias, "").strip()
        )
        canonical_present = sum(
            1
            for alias, canonical in ENV_ALIASES.items()
            if alias != canonical and os.environ.get(canonical, "").strip()
        )
        print("All dkeys aliases already match dharma_swarm canonical names (or no aliases present).")
        print(
            "Alias table summary: "
            f"entries={alias_count} aliases_present={aliases_present} "
            f"canonical_present={canonical_present}"
        )
        return

    action = "Applied" if args.apply else "Would apply (dry-run)"
    print(f"{action} {len(applied)} alias normalization(s):\n")
    for index, _item in enumerate(applied, start=1):
        print(f"  normalization #{index}: alias value copied to canonical credential slot")

    if not args.apply:
        print("\nRe-run with --apply to mutate os.environ, or use --emit-exports for shell sourcing.")


if __name__ == "__main__":
    main()
