"""Single source of truth for Forge Lab package and source identity."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


PACKAGE_NAME = "dharma_swarm.forge_lab"
PACKAGE_VERSION = "0.1.0-dev"
CLI_RESULT_SCHEMA = "forge_lab.cli_result.v1"
IMPLEMENTATION_STATUS = "minimum_safe_blocked_controller"


def _default_lab_base(
    home: Path,
    megha_base: Path = Path("/root/rsi-lab/current"),
) -> Path:
    """Select the host-local release root without failing on inaccessible paths."""

    try:
        if megha_base.is_dir():
            return megha_base
    except OSError:
        pass
    return home / ".dharma" / "rsi-lab" / "current"


_DEFAULT_LAB_BASE = Path(
    os.environ.get("RSI_LAB_BASE") or _default_lab_base(Path.home())
)
CANONICAL_CHECKOUT = Path(os.environ.get("RSI_LAB_REPO") or _DEFAULT_LAB_BASE / "repo")
SOURCE_CHECKOUT = Path(__file__).resolve().parents[2]


def _git_directory(checkout: Path) -> Path | None:
    marker = checkout / ".git"
    if marker.is_dir():
        return marker
    if not marker.is_file():
        return None

    try:
        declaration = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir: "
    if not declaration.startswith(prefix):
        return None
    git_directory = Path(declaration[len(prefix) :])
    if not git_directory.is_absolute():
        git_directory = checkout / git_directory
    return git_directory.resolve()


def _common_git_directory(git_directory: Path) -> Path:
    common_marker = git_directory / "commondir"
    try:
        common_declaration = common_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return git_directory
    common_directory = Path(common_declaration)
    if not common_directory.is_absolute():
        common_directory = git_directory / common_directory
    return common_directory.resolve()


def _read_ref(git_directory: Path, ref: str) -> str | None:
    common_directory = _common_git_directory(git_directory)
    for base in (git_directory, common_directory):
        try:
            value = (base / ref).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value

    for base in (git_directory, common_directory):
        try:
            packed_refs = (base / "packed-refs").read_text(encoding="utf-8")
        except OSError:
            continue
        suffix = f" {ref}"
        for line in packed_refs.splitlines():
            if line.startswith(("#", "^")):
                continue
            if line.endswith(suffix):
                return line.split(" ", 1)[0]
    return None


@lru_cache(maxsize=1)
def source_commit() -> str:
    """Return the checkout commit without shelling out to Git."""

    git_directory = _git_directory(SOURCE_CHECKOUT)
    if git_directory is None:
        return "unknown"
    try:
        head = (git_directory / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    ref_prefix = "ref: "
    if head.startswith(ref_prefix):
        return _read_ref(git_directory, head[len(ref_prefix) :]) or "unknown"
    return head or "unknown"


@lru_cache(maxsize=1)
def source_tree_state() -> str:
    """Report checkout dirtiness using a read-only Git query."""

    try:
        result = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(SOURCE_CHECKOUT),
                "status",
                "--porcelain",
                "--untracked-files=normal",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return "dirty" if result.stdout.strip() else "clean"


def forge_identity() -> dict[str, str]:
    """Return the canonical, serializable identity reported by every RSI entry point."""

    return {
        "package": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "source_commit": source_commit(),
        "canonical_checkout": str(CANONICAL_CHECKOUT),
        "source_checkout": str(SOURCE_CHECKOUT),
        "source_tree_state": source_tree_state(),
        "implementation_status": IMPLEMENTATION_STATUS,
    }
