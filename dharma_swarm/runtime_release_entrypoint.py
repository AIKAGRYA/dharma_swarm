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
_ORCHESTRATE_COMMAND = "orchestrate-live"
_A2A_INBOX_BRIDGE_COMMAND = "a2a-inbox-bridge"
_SUPPORTED_COMMANDS = frozenset(
    {_ORCHESTRATE_COMMAND, _A2A_INBOX_BRIDGE_COMMAND}
)


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


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] not in _SUPPORTED_COMMANDS:
        raise SystemExit(
            "release entrypoint denied: supported commands are orchestrate-live "
            "and a2a-inbox-bridge"
        )
    command, command_args = args[0], args[1:]
    if command == _ORCHESTRATE_COMMAND and command_args:
        raise SystemExit(
            "release entrypoint denied: orchestrate-live accepts no arguments"
        )
    admit_release_root()

    if command == _ORCHESTRATE_COMMAND:
        from dharma_swarm.dgc_cli import main as dgc_main

        dgc_main()
        return 0

    from scripts.runtime.a2a_inbox_bridge import main as bridge_main

    return bridge_main(command_args)


if __name__ == "__main__":
    raise SystemExit(main())
