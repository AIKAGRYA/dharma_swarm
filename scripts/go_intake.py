#!/usr/bin/env python3
"""CLI wrapper for the GO economic primitive intake organ."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.go_intake import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
