#!/usr/bin/env python3
"""CLI wrapper for Forge fresh task oracle intake."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.forge_v1.forge_v2.fresh_task_oracle import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
