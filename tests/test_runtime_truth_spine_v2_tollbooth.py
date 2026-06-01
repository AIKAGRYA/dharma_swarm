"""Runtime Truth Spine v2 tollbooth regression checks."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_free_text_result_path_requires_structured_opt_in() -> None:
    source = (REPO_ROOT / "dharma_swarm" / "orchestrator.py").read_text(encoding="utf-8")
    gate = 'task_metadata.get("allow_free_text_result_path") is True'
    write = "target.write_text(result, encoding=\"utf-8\")"

    assert gate in source
    assert write in source
    assert source.index(gate) < source.index(write)
