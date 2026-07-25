"""Shared primitives for the Pramāṇa Probe runner.

This module deliberately has *no* dependency on the host repo. It contains the
confidence rubric, the grade model, the table renderer, and the AST/git/subprocess
helpers every signal routes through. The whole point of the runner is that a
"Demonstration run" is no longer trust-me prose: you run the instrument and it
emits its own row, with the confidence it actually earned.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --------------------------------------------------------------------------- #
# Confidence rubric — the "vibe knob" killed and defined.
# --------------------------------------------------------------------------- #
class Confidence(str, Enum):
    """How much the number can be trusted, by *how it was produced* — not by feel.

    HIGH        a dedicated tool/algorithm ran on complete input with no heuristic
                gap (radon cc; AST line count; npm-audit advisory IDs; git log).
    MEDIUM      the right tool ran, but a blind spot it structurally cannot see
                remains (static reachability in a repo with dynamic/string loading;
                coupling from static imports only).
    LOW         a proxy stood in for the named instrument, or input was partial.
                A LOW finding MUST NOT be reported as actionable without
                confirmation by the named tool.
    UNASSESSED  the named instrument is absent and no faithful proxy exists.
                The axis is explicitly not scored. Never inferred, never guessed.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNASSESSED = "UNASSESSED"


class Grade(str, Enum):
    GREEN = "GREEN"        # clean on this axis — return-clean, not a gap to fill
    AMBER = "AMBER"        # present, bounded, worth knowing
    RED = "RED"            # actionable pressure
    UNASSESSED = "—"       # not scored (mirror of Confidence.UNASSESSED)


@dataclass
class SignalResult:
    """One row of the index. Scope and denominator are mandatory: a composite that
    sums signals measured over different denominators without disclosing them is
    itself slop (this is the scope-normalization invariant)."""

    signal: str
    measured: str                  # human-readable measured value
    grade: Grade
    confidence: Confidence
    confirm_with: str              # the named instrument that upgrades/refutes this
    scope: str                     # exactly what was measured over (the denominator)
    pressure: float = 0.0          # 0..1 normalized; only meaningful within a scope
    detail: list[str] = field(default_factory=list)
    instrument: str = ""           # what actually produced the number this run
    count: int | None = None       # raw finding count (machine-comparable; None when UNASSESSED)

    def as_dict(self) -> dict:
        return {
            "signal": self.signal,
            "measured": self.measured,
            "grade": self.grade.value,
            "confidence": self.confidence.value,
            "confirm_with": self.confirm_with,
            "scope": self.scope,
            "pressure": round(self.pressure, 3),
            "instrument": self.instrument,
            "count": self.count,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- #
# Source enumeration
# --------------------------------------------------------------------------- #
_DEFAULT_EXCLUDES = (
    ".venv", "venv", "node_modules", ".git", "__pycache__", ".mypy_cache",
    ".pytest_cache", "build", "dist", ".tox", "site-packages",
)


def iter_py_files(root: Path, excludes: tuple[str, ...] = _DEFAULT_EXCLUDES) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if parts & set(excludes):
            continue
        out.append(p)
    return out


# Language-agnostic source extensions. Used by the signals whose instrument does
# not depend on a Python AST (a 3000-line file is a god object in any language;
# co-change coupling is a property of git history, not syntax). Python-AST
# signals deliberately do NOT use this set — they return UNASSESSED rather than
# pretend to read a language they cannot parse.
SOURCE_EXTS = (
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".go", ".rs", ".java", ".kt", ".kts", ".rb", ".php", ".cs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm",
    ".swift", ".scala", ".clj", ".ex", ".exs",
)


def iter_source_files(
    root: Path,
    exts: tuple[str, ...] = SOURCE_EXTS,
    excludes: tuple[str, ...] = _DEFAULT_EXCLUDES,
) -> list[Path]:
    extset = {e.lower() for e in exts}
    excl = set(excludes)
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in extset or not p.is_file():
            continue
        if set(p.parts) & excl:
            continue
        out.append(p)
    return out


def parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except (SyntaxError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# External-tool routing — present? then route; absent? then say so (never fake).
# --------------------------------------------------------------------------- #
def tool_path(name: str, venv_first: bool = True) -> str | None:
    """Locate an instrument. Checks the active venv's bin first, then PATH."""
    if venv_first:
        candidates = []
        # the running interpreter's own bin dir is the most reliable: an
        # instrument pip-installed into this venv sits right next to python.
        candidates.append(Path(sys.executable).parent / name)
        venv = os.environ.get("VIRTUAL_ENV")
        if venv:
            candidates.append(Path(venv) / "bin" / name)
        # also probe a local .venv relative to cwd
        candidates.append(Path.cwd() / ".venv" / "bin" / name)
        for c in candidates:
            if c.exists():
                return str(c)
    return shutil.which(name)


def run_json(cmd: list[str], cwd: Path | None = None, timeout: int = 120):
    """Run a tool that emits JSON on stdout. Returns parsed JSON or None."""
    try:
        out = subprocess.check_output(cmd, cwd=str(cwd) if cwd else None,
                                      stderr=subprocess.DEVNULL, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        # npm audit exits non-zero when advisories exist; recover its stdout.
        out = getattr(e, "output", None)
        if not out:
            return None
    try:
        return json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return None


def git(args: list[str], cwd: Path, timeout: int = 120) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(cwd),
                                       stderr=subprocess.DEVNULL, timeout=timeout).decode(
            "utf-8", "replace")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_table(results: list[SignalResult]) -> str:
    headers = ["Signal", "Measured", "Grade", "Confidence", "Confirm with"]
    rows = [[r.signal, r.measured, r.grade.value, r.confidence.value, r.confirm_with]
            for r in results]
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cells)) + " |"
    sep = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines = [fmt(headers), sep, *(fmt(r) for r in rows)]
    return "\n".join(lines)
