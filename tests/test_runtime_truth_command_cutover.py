from __future__ import annotations

from pathlib import Path


FORBIDDEN_COMMAND_SUBSTRATE_TERMS = (
    "WorkCommand",
    "WorkRun",
    "WorkReceipt",
    "command_runs",
    "work_runs",
)

SOURCE_ROOTS = ("dharma_swarm", "scripts", "api", "dashboard/src")
SOURCE_SUFFIXES = {".py", ".sql", ".ts", ".tsx"}


def test_no_parallel_command_spine_substrate_symbols() -> None:
    repo = Path(__file__).resolve().parents[1]
    hits: list[str] = []
    for root_name in SOURCE_ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in FORBIDDEN_COMMAND_SUBSTRATE_TERMS:
                if term in text:
                    hits.append(f"{path.relative_to(repo)}: {term}")

    assert hits == []
