"""External-target ingestion — clone, pin to a SHA, and digest the tree.

A Foundry run must be reproducible from published artifacts alone, so every
target is pinned: a specific repo at a specific commit, with a content digest of
the files in scope. The pin manifest lives under ``~/.dharma/foundry/targets/``
(runtime state, never git). Tests pass ``local_source`` to skip the network.

Isolation note: targets are cloned into ``~/.dharma/foundry/targets/`` and NEVER
into the dharma_swarm checkout — the Foundry evolves foreign trees, never its own
live root (mirrors ``dharma_swarm.evolution_safety`` protected-root doctrine).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

_STATE_ROOT = Path.home() / ".dharma" / "foundry" / "targets"
_IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache"}


@dataclass(frozen=True)
class TargetSpec:
    """A pinned external target and how to score changes to it."""

    id: str
    name: str
    url: str
    sha: str
    evolve_paths: list[str] = field(default_factory=list)
    oracle_cmd: list[str] = field(default_factory=list)
    subdir: str = ""
    license: str = ""
    ai_policy: str = "unknown"  # native | conditional | banned | unknown
    notes: str = ""
    # Docker image with the target's deps pre-installed (campaigns run with
    # --network none, so nothing can pip-install at benchmark time; build the
    # image once at ingest). Empty = the isolation policy's default image.
    docker_image: str = ""
    # Exact immutable content digest required for unattended evaluator replay.
    # A mutable tag alone is never enough to seed a champion.
    docker_image_digest: str = ""
    # For unattended campaign cycles: the one-line optimization objective fed
    # to the mutation prompt, and the ring-2 held-out oracle shell command
    # (FOUNDRY_METRICS sentinel output). Empty objective = target cannot run
    # unattended; empty heldout = ring 2 skipped, no receipts minted.
    objective: str = ""
    heldout_cmd: str = ""


@dataclass(frozen=True)
class PinnedTarget:
    """The result of ingesting a :class:`TargetSpec`."""

    spec: TargetSpec
    root: str
    resolved_sha: str
    tree_digest: str
    ingested_at: str

    def manifest(self) -> dict[str, Any]:
        return {
            "spec": asdict(self.spec),
            "root": self.root,
            "resolved_sha": self.resolved_sha,
            "tree_digest": self.tree_digest,
            "ingested_at": self.ingested_at,
        }


def compute_tree_digest(root: Path, paths: Sequence[str] | None = None) -> str:
    """Deterministic sha256 over the (relpath, filehash) pairs under ``root``.

    When ``paths`` is given, only files matching those path prefixes are hashed
    (the evolve scope), so the digest tracks exactly what the Foundry may change.
    """
    root = Path(root)
    entries: list[tuple[str, str]] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in file.relative_to(root).parts):
            continue
        rel = file.relative_to(root).as_posix()
        if paths and not any(rel == p or rel.startswith(p.rstrip("*").rstrip("/") + "/") or rel.startswith(p) for p in paths):
            continue
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        entries.append((rel, digest))
    blob = "\n".join(f"{rel}:{h}" for rel, h in entries)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*_IGNORE_DIRS))


def _assert_safe_evolve_paths(root: Path, paths: Sequence[str]) -> None:
    resolved_root = Path(root).resolve()
    for raw in paths:
        prefix = str(raw).split("*", 1)[0].rstrip("/")
        pure = PurePosixPath(prefix)
        if (
            not prefix
            or pure.is_absolute()
            or "\\" in prefix
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ValueError(f"unsafe evolve path: {raw!r}")
        cursor = resolved_root
        for part in pure.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError(f"evolve path contains symlink component: {raw!r}")
        try:
            cursor.resolve(strict=False).relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            raise ValueError(f"evolve path escapes target tree: {raw!r}") from exc


def ingest(
    spec: TargetSpec,
    *,
    dest_root: Path | None = None,
    local_source: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> PinnedTarget:
    """Materialize a pinned checkout of ``spec`` and write its manifest.

    ``local_source`` copies an existing tree instead of cloning (tests / offline
    fixtures). Otherwise ``git clone`` + ``git checkout <sha>`` via ``runner``.
    """
    state_root = Path(dest_root) if dest_root is not None else _STATE_ROOT
    checkout = state_root / spec.id
    checkout.parent.mkdir(parents=True, exist_ok=True)

    if local_source is not None:
        _copy_tree(Path(local_source), checkout)
        resolved_sha = spec.sha or "local"
    else:
        if checkout.exists():
            shutil.rmtree(checkout)
        runner(["git", "clone", "--depth", "50", spec.url, str(checkout)], check=True)
        if spec.sha:
            runner(["git", "-C", str(checkout), "checkout", spec.sha], check=True)
        resolved = runner(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        resolved_sha = (getattr(resolved, "stdout", "") or "").strip() or spec.sha

    if spec.subdir:
        _assert_safe_evolve_paths(checkout, [spec.subdir])
    scope_root = checkout / spec.subdir if spec.subdir else checkout
    _assert_safe_evolve_paths(scope_root, spec.evolve_paths)
    digest = compute_tree_digest(scope_root, spec.evolve_paths or None)

    pinned = PinnedTarget(
        spec=spec,
        root=str(checkout),
        resolved_sha=resolved_sha,
        tree_digest=digest,
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_path = state_root / f"{spec.id}.pin.json"
    manifest_path.write_text(
        json.dumps(pinned.manifest(), indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return pinned
