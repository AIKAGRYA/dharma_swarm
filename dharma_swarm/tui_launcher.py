"""TUI launcher with fallback chain: new TUI → legacy TUI → exit."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def launch_tui() -> None:
    """Launch the TUI, falling back to legacy if the new TUI fails."""
    # Try new TUI first
    try:
        from dharma_swarm.tui import run  # noqa: F811

        run()
        return
    except Exception as exc:
        logger.debug("New TUI failed: %s", exc)

    # Fall back to legacy TUI
    try:
        from dharma_swarm.tui_legacy import DGCApp

        DGCApp().run()
        return
    except Exception as exc:
        logger.error("All TUI backends failed: %s", exc)

    sys.exit(1)
