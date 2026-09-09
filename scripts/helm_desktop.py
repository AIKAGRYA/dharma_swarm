#!/usr/bin/env python3
"""Dependency-light CLI entrypoint, runnable from any working directory."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.helm_desktop.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
