from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = (
    ROOT
    / "docs"
    / "langgraph_parity"
    / "DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json"
)


def _comparison_requirements() -> list[str]:
    target = json.loads(RUBRIC.read_text(encoding="utf-8"))["comparison_target"]
    return [
        f"{target['distribution']}=={target['version']}",
        target["checkpoint_distribution"],
        target["persistent_checkpoint_adapter"],
    ]


def test_oracle_extra_exactly_pins_the_frozen_comparison_tuple() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["optional-dependencies"]["test-oracle"] == (
        _comparison_requirements()
    )


def test_uv_lock_carries_the_frozen_comparison_tuple() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked = {
        package["name"]: package["version"]
        for package in lock["package"]
        if package["name"]
        in {"langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite"}
    }
    expected = {
        requirement.rsplit("==", 1)[0]: requirement.rsplit("==", 1)[1]
        for requirement in _comparison_requirements()
    }

    assert locked == expected
