"""Adapter protocol and shared subprocess wrapper."""

from __future__ import annotations

import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from dharma_swarm.slop.models import DetectorFamily, DetectorResult, Finding


class BaseAdapter(ABC):
    tool: str
    family: DetectorFamily

    @abstractmethod
    def run(self, paths: Iterable[Path]) -> DetectorResult: ...


def run_subprocess(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 60.0,
) -> tuple[int, str, str, float]:
    """Run a command, return (exit_code, stdout, stderr, duration_sec).

    Returns exit_code=127 on missing executable, exit_code=124 on timeout.
    """
    if not argv:
        return 1, "", "empty argv", 0.0
    if shutil.which(argv[0]) is None:
        return 127, "", f"{argv[0]}: command not found", 0.0
    start = time.perf_counter()
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"{argv[0]}: timeout after {timeout}s", time.perf_counter() - start
    except OSError as exc:
        return 1, "", f"{argv[0]}: {exc}", time.perf_counter() - start
    return (
        result.returncode,
        result.stdout or "",
        result.stderr or "",
        time.perf_counter() - start,
    )


def empty_result(
    tool: str,
    family: DetectorFamily,
    error: str,
    duration_sec: float = 0.0,
) -> DetectorResult:
    return DetectorResult(
        tool=tool,
        family=family,
        findings=[],
        duration_sec=duration_sec,
        exit_code=127 if "command not found" in error else 1,
        error=error,
    )


def normalize_path(path: str, repo_root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(repo_root))
        except ValueError:
            return str(p)
    return str(p)


__all__ = [
    "BaseAdapter",
    "Finding",
    "empty_result",
    "normalize_path",
    "run_subprocess",
]
