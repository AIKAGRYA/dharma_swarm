"""Isolated entrypoint for an immutable Dharma runtime release.

Python isolated mode intentionally removes the checkout root from sys.path.
The installed dharma_swarm package remains importable, but runtime modules
also consume the versioned scripts namespace. Admit exactly the already-pinned
release root before dispatch so those imports resolve from the same clean Git
checkout rather than from an ambient working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


_RELEASE_ROOT_ENV = "DHARMA_RELEASE_ROOT"
_ONLY_COMMAND = ("orchestrate-live",)


def admit_release_root() -> Path:
    """Bind imports to the checkout containing this installed entrypoint."""

    raw_root = os.environ.get(_RELEASE_ROOT_ENV, "").strip()
    if not raw_root:
        raise SystemExit(f"release entrypoint denied: {_RELEASE_ROOT_ENV} is required")

    release_root = Path(raw_root).expanduser().resolve()
    package_root = Path(__file__).resolve().parents[1]
    if release_root != package_root:
        raise SystemExit(
            "release entrypoint denied: installed package does not match "
            f"{_RELEASE_ROOT_ENV}"
        )

    root_text = str(release_root)
    if not sys.path or sys.path[0] != root_text:
        sys.path.insert(0, root_text)
    return release_root


def main() -> None:
    if tuple(sys.argv[1:]) != _ONLY_COMMAND:
        raise SystemExit(
            "release entrypoint denied: only orchestrate-live is supported"
        )
    admit_release_root()

    from dharma_swarm.dgc_cli import main as dgc_main

    dgc_main()


if __name__ == "__main__":
    main()
