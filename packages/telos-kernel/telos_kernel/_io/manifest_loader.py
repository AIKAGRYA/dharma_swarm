"""Manifest loader \u2014 filesystem + YAML side.

The core `manifest.py` accepts a parsed dict and validates it via Pydantic.
This module reads YAML off disk and hands the parsed dict to core. The
YAML parser, file handle, and path-resolution logic all live here so the
core module can remain effect-free.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from telos_kernel.effects import Effect, effect
from telos_kernel.manifest import Manifest


DEFAULT_MANIFEST_PATH: Path = (
    Path(__file__).resolve().parents[4] / "kernel" / "manifest.yaml"
)


@effect(Effect.FS_READ)
def read_manifest_yaml(path: str | Path | None = None) -> dict[str, Any]:
    """Read raw YAML from disk. Returns the parsed dict for downstream
    Pydantic validation. Does not construct a Manifest.

    Raises FileNotFoundError, yaml.YAMLError. Not fail-closed on purpose:
    a missing manifest is a system-configuration failure, not a runtime
    verdict; the boot path handles the exception explicitly.
    """
    p = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@effect(Effect.FS_READ)
def load_manifest_from_disk(path: str | Path | None = None) -> Manifest:
    """Read + validate. Convenience wrapper around read_manifest_yaml +
    Manifest.model_validate. This is the function the boot path calls.
    """
    raw = read_manifest_yaml(path)
    return Manifest.model_validate(raw)
