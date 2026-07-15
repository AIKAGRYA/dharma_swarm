"""Build a human-first, read-only projection of Forge Lab run history.

Canonical run receipts remain under ``state/rsi_runs`` and the native evolution
archive. This compatibility module preserves the public API and ``python -m``
entrypoint while the implementation is decomposed by responsibility.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.operator_history_projection import (
    build_operator_history as _build_operator_history,
    build_parser as _build_parser,
    main as _main,
)
from dharma_swarm.forge_lab.operator_history_sources import (
    HISTORY_ROW_SCHEMA as HISTORY_ROW_SCHEMA,
    MARKER_NAME as MARKER_NAME,
    METRIC_KEYS as METRIC_KEYS,
    SCORECARD_SCHEMA as SCORECARD_SCHEMA,
    VIEW_SCHEMA as VIEW_SCHEMA,
)


def build_operator_history(
    state_root: Path,
    output_root: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build and atomically install the operator-facing history projection."""

    return _build_operator_history(state_root, output_root, generated_at)


def build_parser() -> argparse.ArgumentParser:
    return _build_parser()


def main(argv: list[str] | None = None) -> int:
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
