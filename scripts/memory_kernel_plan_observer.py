#!/usr/bin/env python3
"""Observe in-flight MemoryKernel work without steering it."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


DEFAULT_WATCH_PATHS = (
    "dharma_swarm/memory_kernel",
    "dharma_swarm/knowledge_ops",
    "scripts/memory_surface_census.py",
    "scripts/memory_writer_sentinel.py",
    "scripts/memory_kernel_plan_observer.py",
    "tests/test_memory_kernel_adapters.py",
    "tests/test_memory_surface_census.py",
    "tests/test_memory_writer_sentinel.py",
    "tests/test_knowledge_ops.py",
    "tests/test_memory_kernel_plan_observer.py",
    "docs/architecture/memory_kernel_current_intent.md",
    "docs/architecture/memory_kernel_m1_read_facade.md",
    "docs/architecture/memory_kernel_m2_writer_sentinel.md",
    "docs/architecture/memory_kernel_m2b_knowledgeops_intake.md",
    "docs/architecture/memory_kernel_m2c_conflict_projection_review.md",
    "docs/architecture/memory_kernel_m2d_promotion_proposal_queue.md",
    "docs/architecture/memory_surfaces_census_v3.md",
)


@dataclass(frozen=True)
class WatchedFile:
    path: str
    size_bytes: int
    mtime: str
    sha256: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CodexProcess:
    pid: int
    ppid: int | None
    elapsed: str
    command: str
    command_sha256: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelPlanSnapshot:
    timestamp: str
    repo_root: str
    branch: str | None
    head: str | None
    status_short: tuple[str, ...]
    watched_file_count: int
    watched_files: tuple[WatchedFile, ...]
    recent_commits: tuple[dict[str, object], ...]
    codex_process_count: int
    codex_processes: tuple[CodexProcess, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["watched_files"] = [item.to_json() for item in self.watched_files]
        payload["codex_processes"] = [item.to_json() for item in self.codex_processes]
        return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/knowledge_ops/memory_kernel_plan_observer.jsonl"),
    )
    parser.add_argument("--duration-seconds", type=int, default=6 * 60 * 60)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--watch-path",
        action="append",
        default=[],
        help="Additional path to include in the file inventory. May be repeated.",
    )
    parser.add_argument(
        "--include-file-hashes",
        action="store_true",
        help="Include sha256 hashes for watched files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    watch_paths = DEFAULT_WATCH_PATHS + tuple(args.watch_path)
    duration_seconds = 0 if args.once else max(0, args.duration_seconds)
    interval_seconds = max(0.1, args.interval_seconds)
    deadline = time.monotonic() + duration_seconds

    while True:
        snapshot = collect_snapshot(
            repo_root,
            watch_paths=watch_paths,
            include_file_hashes=args.include_file_hashes,
        )
        append_snapshot(output, snapshot)
        print(json.dumps(snapshot.to_json(), indent=2, sort_keys=True))
        if args.once or time.monotonic() >= deadline:
            break
        time.sleep(min(interval_seconds, max(0.0, deadline - time.monotonic())))
    return 0


def collect_snapshot(
    repo_root: Path,
    *,
    watch_paths: Iterable[str] = DEFAULT_WATCH_PATHS,
    include_file_hashes: bool = False,
) -> MemoryKernelPlanSnapshot:
    files = collect_watched_files(
        repo_root,
        watch_paths=watch_paths,
        include_file_hashes=include_file_hashes,
    )
    processes = collect_codex_processes()
    return MemoryKernelPlanSnapshot(
        timestamp=datetime.now(UTC).isoformat(),
        repo_root=str(repo_root),
        branch=git_output(repo_root, ("branch", "--show-current")),
        head=git_output(repo_root, ("rev-parse", "--short", "HEAD")),
        status_short=tuple(
            line
            for line in (git_output(repo_root, ("status", "--short")) or "").splitlines()
            if _is_memory_kernel_related_status(line)
        ),
        watched_file_count=len(files),
        watched_files=files,
        recent_commits=recent_memory_kernel_commits(repo_root),
        codex_process_count=len(processes),
        codex_processes=processes,
    )


def collect_watched_files(
    repo_root: Path,
    *,
    watch_paths: Iterable[str] = DEFAULT_WATCH_PATHS,
    include_file_hashes: bool = False,
) -> tuple[WatchedFile, ...]:
    files: list[WatchedFile] = []
    for watch_path in watch_paths:
        root = repo_root / watch_path
        if root.is_dir():
            candidates = sorted(
                path
                for path in root.rglob("*")
                if path.is_file() and not _is_generated_file(path)
            )
        elif root.is_file():
            candidates = [] if _is_generated_file(root) else [root]
        else:
            candidates = []
        for path in candidates:
            stat = path.stat()
            files.append(
                WatchedFile(
                    path=path.relative_to(repo_root).as_posix(),
                    size_bytes=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    sha256=sha256_file(path) if include_file_hashes else "",
                )
            )
    deduped = {item.path: item for item in files}
    return tuple(deduped[key] for key in sorted(deduped))


def collect_codex_processes() -> tuple[CodexProcess, ...]:
    output = run_command(("ps", "-axo", "pid=,ppid=,etime=,command="), cwd=None)
    if output is None:
        return ()
    return parse_codex_processes(output)


def parse_codex_processes(ps_output: str) -> tuple[CodexProcess, ...]:
    processes: list[CodexProcess] = []
    for line in ps_output.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid_text, ppid_text, elapsed, command = parts
        if not _is_codex_process_command(command):
            continue
        processes.append(
            CodexProcess(
                pid=_safe_int(pid_text, default=0),
                ppid=_safe_int_or_none(ppid_text),
                elapsed=elapsed,
                command=_safe_command_label(command),
                command_sha256=hashlib.sha256(command.encode("utf-8")).hexdigest(),
            )
        )
    return tuple(sorted(processes, key=lambda item: item.pid))


def recent_memory_kernel_commits(repo_root: Path, limit: int = 10) -> tuple[dict[str, object], ...]:
    output = run_command(
        (
            "git",
            "-C",
            str(repo_root),
            "log",
            f"-n{limit}",
            "--format=%H%x09%ct%x09%s",
            "--",
            *DEFAULT_WATCH_PATHS,
        ),
        cwd=repo_root,
    )
    if not output:
        return ()
    commits: list[dict[str, object]] = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        commit_hash, timestamp, subject = parts
        commits.append(
            {
                "hash": commit_hash,
                "timestamp": int(timestamp),
                "subject": subject,
            }
        )
    return tuple(commits)


def append_snapshot(output: Path, snapshot: MemoryKernelPlanSnapshot) -> None:
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot.to_json(), sort_keys=True) + "\n")


def git_output(repo_root: Path, args: tuple[str, ...]) -> str | None:
    return run_command(("git", "-C", str(repo_root), *args), cwd=repo_root)


def run_command(command: tuple[str, ...], *, cwd: Path | None) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_generated_file(path: Path) -> bool:
    return (
        "__pycache__" in path.parts
        or path.suffix in {".pyc", ".pyo"}
        or path.name == ".DS_Store"
    )


def _safe_command_label(command: str) -> str:
    binary = command.split(None, 1)[0] if command.strip() else "unknown"
    return Path(binary).name


def _is_codex_process_command(command: str) -> bool:
    parts = command.split()
    if not parts:
        return False
    executable = Path(parts[0]).name.lower()
    if "codex" in executable:
        return True
    if executable != "node" or len(parts) < 2:
        return False
    wrapper = Path(parts[1]).name.lower()
    return "codex" in wrapper


def _is_memory_kernel_related_status(status_line: str) -> bool:
    return any(path in status_line for path in DEFAULT_WATCH_PATHS)


def _safe_int(text: str, *, default: int) -> int:
    try:
        return int(text)
    except ValueError:
        return default


def _safe_int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
