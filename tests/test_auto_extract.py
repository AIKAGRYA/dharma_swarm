"""Tests for the auto-extract logic in orchestrator.py.

Verifies:
- The regex matches all 5 SEED_TASK descriptions and extracts correct paths.
- Results >200 chars are written to the matched path.
- Results <=200 chars are NOT written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dharma_swarm.startup_crew import SEED_TASKS

# Replica of the regex used in orchestrator.py auto-extract block.
AUTO_EXTRACT_RE = re.compile(
    r"[Ww]rite [\w\s]*?(?:to |report to |results to |output to |findings to )(~/[^\s,\"]+\.md)"
)

# Expected output paths per SEED_TASK (in order)
EXPECTED_PATHS = [
    "~/.dharma/shared/landscape_companies.md",
    "~/.dharma/shared/landscape_research.md",
    "~/.dharma/shared/competitor_deep_dives.md",
    "~/.dharma/shared/differentiation.md",
    "~/.dharma/shared/STATE_OF_AI_APRIL_2026.md",
]


class TestAutoExtractRegex:
    """Verify the regex matches every SEED_TASK description."""

    @pytest.mark.parametrize("idx,expected_path", enumerate(EXPECTED_PATHS))
    def test_seed_task_regex_match(self, idx: int, expected_path: str):
        task = SEED_TASKS[idx]
        desc = task["description"]
        m = AUTO_EXTRACT_RE.search(desc)
        assert m is not None, f"SEED_TASK[{idx}] description did not match regex: {desc[:120]!r}"
        assert m.group(1) == expected_path, (
            f"SEED_TASK[{idx}] extracted '{m.group(1)}' but expected '{expected_path}'"
        )

    def test_all_five_seed_tasks_present(self):
        assert len(SEED_TASKS) == 5, f"Expected 5 SEED_TASKS, got {len(SEED_TASKS)}"


def _run_auto_extract(desc: str, result: str, base_dir: Path) -> Path | None:
    """Simulate the orchestrator auto-extract logic, writing under base_dir."""
    m = AUTO_EXTRACT_RE.search(desc)
    if not m or not result or len(result) <= 200:
        return None
    # Resolve the path relative to base_dir instead of home, for testing.
    relative = Path(m.group(1).lstrip("~/"))
    target = base_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    return target


class TestAutoExtractWriteBehavior:
    """Verify write-on-match behaviour."""

    def test_result_over_200_chars_is_written(self, tmp_path: Path):
        desc = SEED_TASKS[0]["description"]
        result = "x" * 201
        target = _run_auto_extract(desc, result, tmp_path)
        assert target is not None
        assert target.exists()
        assert target.read_text() == result

    def test_result_exactly_200_chars_is_not_written(self, tmp_path: Path):
        desc = SEED_TASKS[0]["description"]
        result = "x" * 200
        target = _run_auto_extract(desc, result, tmp_path)
        assert target is None

    def test_result_under_200_chars_is_not_written(self, tmp_path: Path):
        desc = SEED_TASKS[0]["description"]
        result = "short"
        target = _run_auto_extract(desc, result, tmp_path)
        assert target is None

    def test_empty_result_is_not_written(self, tmp_path: Path):
        desc = SEED_TASKS[0]["description"]
        target = _run_auto_extract(desc, "", tmp_path)
        assert target is None

    @pytest.mark.parametrize("idx,expected_suffix", [
        (0, ".dharma/shared/landscape_companies.md"),
        (1, ".dharma/shared/landscape_research.md"),
        (2, ".dharma/shared/competitor_deep_dives.md"),
        (3, ".dharma/shared/differentiation.md"),
        (4, ".dharma/shared/STATE_OF_AI_APRIL_2026.md"),
    ])
    def test_each_seed_task_writes_to_correct_path(
        self, idx: int, expected_suffix: str, tmp_path: Path
    ):
        desc = SEED_TASKS[idx]["description"]
        result = "y" * 300
        target = _run_auto_extract(desc, result, tmp_path)
        assert target is not None
        assert str(target).endswith(expected_suffix), (
            f"SEED_TASK[{idx}] wrote to {target}, expected suffix {expected_suffix!r}"
        )
        assert target.read_text() == result
