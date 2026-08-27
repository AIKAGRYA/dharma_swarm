"""Lockfile contract for the immutable A2A bridge runtime."""

from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_a2a_runtime_extra_is_exact_and_lock_bound() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["optional-dependencies"]["a2a-runtime"] == [
        "nats-py==2.15.0"
    ]

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {row["name"]: row for row in lock["package"]}
    assert packages["nats-py"]["version"] == "2.15.0"

    local = packages["dharma-swarm"]
    assert local["optional-dependencies"]["a2a-runtime"] == [{"name": "nats-py"}]
    metadata_rows = local["metadata"]["requires-dist"]
    assert {
        "name": "nats-py",
        "marker": "extra == 'a2a-runtime'",
        "specifier": "==2.15.0",
    } in metadata_rows
