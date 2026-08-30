"""Filesystem and exact-argv adapters for heterogeneous labs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .config import CommandSpec, LabConfig, safe_subprocess_environment
from .models import ActionKind, ActionResult, CommandOutcome, EvidenceRef, LabSnapshot


RunFunction = Callable[..., subprocess.CompletedProcess[str]]
_PROVIDER_MARKERS = (
    "provider_error",
    "provider failure",
    "rate_limit",
    "rate limit",
    "quota",
    "insufficient credit",
    "authentication",
    "api key",
    "model_not_found",
    "model not found",
)
_HALT_VALUES = frozenset({"kill", "halt", "halted", "stop_requested"})
_HALT_KEYS = frozenset({"kill", "killed", "halt", "halted", "kill_requested", "stop_requested"})


def command_hash(argv: Iterable[str], *, cwd: Path | None = None) -> str:
    payload = json.dumps(
        {"argv": list(argv), "cwd": str(cwd) if cwd is not None else ""},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BoundedCommandRunner:
    """Exact-argv subprocess runner with a per-tick call fuse."""

    def __init__(
        self,
        max_calls: int,
        *,
        run_fn: RunFunction = subprocess.run,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_calls = max_calls
        self.calls = 0
        self._run = run_fn
        self._sleep = sleep_fn

    def available(self, spec: CommandSpec) -> tuple[bool, str]:
        if spec.cwd is not None and not spec.cwd.is_dir():
            return False, f"working_directory_unavailable:{spec.cwd}"
        executable = spec.argv[0]
        if "/" in executable:
            target = Path(executable).expanduser()
            if not target.is_file() or not os.access(target, os.X_OK):
                return False, f"executable_unavailable:{target}"
        elif shutil.which(executable, path=safe_subprocess_environment().get("PATH")) is None:
            return False, f"executable_unavailable:{Path(executable).name}"
        if Path(executable).name.lower().startswith("python") and len(spec.argv) > 1:
            script = spec.argv[1]
            if script.endswith(".py") and not Path(script).expanduser().is_file():
                return False, f"script_unavailable:{Path(script).name}"
        return True, ""

    def execute(
        self,
        spec: CommandSpec,
        *,
        attempts: int = 1,
        stdin: str | None = None,
    ) -> CommandOutcome:
        digest = command_hash(spec.argv, cwd=spec.cwd)
        available, error = self.available(spec)
        if not available:
            return CommandOutcome(False, None, command_sha256=digest, error=error)
        last: CommandOutcome | None = None
        for attempt in range(1, attempts + 1):
            if self.calls >= self.max_calls:
                return CommandOutcome(
                    False,
                    None,
                    attempts=attempt - 1,
                    command_sha256=digest,
                    error="subprocess_call_budget_exhausted",
                )
            self.calls += 1
            try:
                completed = self._run(
                    list(spec.argv),
                    check=False,
                    capture_output=True,
                    text=True,
                    input=stdin,
                    timeout=spec.timeout_seconds,
                    env=safe_subprocess_environment(),
                    cwd=str(spec.cwd) if spec.cwd is not None else None,
                    shell=False,
                )
                last = CommandOutcome(
                    True,
                    int(completed.returncode),
                    stdout=(completed.stdout or "")[: spec.max_output_bytes],
                    stderr=(completed.stderr or "")[: spec.max_output_bytes],
                    attempts=attempt,
                    command_sha256=digest,
                )
            except subprocess.TimeoutExpired as exc:
                last = CommandOutcome(
                    True,
                    None,
                    timed_out=True,
                    stdout=str(exc.stdout or "")[: spec.max_output_bytes],
                    stderr=str(exc.stderr or "")[: spec.max_output_bytes],
                    attempts=attempt,
                    command_sha256=digest,
                    error="timeout",
                )
            except OSError as exc:
                last = CommandOutcome(
                    False,
                    None,
                    attempts=attempt,
                    command_sha256=digest,
                    error=f"spawn_error:{type(exc).__name__}",
                )
            if last.succeeded or attempt == attempts:
                return last
            self._sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))
        assert last is not None
        return last

    def feature_detect(self, spec: CommandSpec) -> CommandOutcome:
        available, error = self.available(spec)
        if not available:
            return CommandOutcome(
                False,
                None,
                command_sha256=command_hash(spec.argv, cwd=spec.cwd),
                error=error,
            )
        if not spec.feature_argv:
            return CommandOutcome(
                True,
                None,
                command_sha256=command_hash(spec.argv, cwd=spec.cwd),
                error="feature_probe_not_declared",
            )
        feature = CommandSpec(
            argv=spec.feature_argv,
            timeout_seconds=min(spec.timeout_seconds, 30),
            max_output_bytes=spec.max_output_bytes,
            cwd=spec.cwd,
        )
        return self.execute(feature)


def _discover_bounded(path: Path, scan_limit: int) -> tuple[list[Path], bool]:
    if not path.exists() and not path.is_symlink():
        return [], False
    if path.is_file() or path.is_symlink():
        return [path], False
    found: list[Path] = []
    pending = [path]
    scanned = 0
    truncated = False
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            scanned += 1
            if scanned > scan_limit:
                truncated = True
                pending.clear()
                break
            candidate = Path(entry.path)
            if entry.is_symlink():
                found.append(candidate)
            elif entry.is_dir(follow_symlinks=False):
                pending.append(candidate)
            elif entry.is_file(follow_symlinks=False):
                found.append(candidate)
    return found, truncated


def _mtime(path: Path) -> float:
    try:
        return path.stat(follow_symlinks=False).st_mtime
    except OSError:
        return float("-inf")


def _safe_file_ref(path: Path, *, max_bytes: int = 1_048_576) -> EvidenceRef | None:
    try:
        stat = path.stat(follow_symlinks=False)
    except OSError:
        return None
    if not path.is_file() or path.is_symlink() or stat.st_size > max_bytes:
        return None
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    return EvidenceRef(
        path=str(path),
        sha256=hashlib.sha256(payload).hexdigest(),
        observed_mtime=stat.st_mtime,
        size_bytes=stat.st_size,
    )


def _json_payload(path: Path, *, max_bytes: int = 1_048_576) -> Any | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _flatten(value: Any, *, prefix: str = "", depth: int = 0) -> Iterable[tuple[str, Any]]:
    if depth > 8:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            yield name, child
            yield from _flatten(child, prefix=name, depth=depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value[:256]):
            name = f"{prefix}[{index}]"
            yield name, child
            yield from _flatten(child, prefix=name, depth=depth + 1)


def _payload_signals(payload: Any) -> tuple[list[str], list[str]]:
    halts: list[str] = []
    providers: list[str] = []
    for key, value in _flatten(payload):
        leaf = key.rsplit(".", 1)[-1].lower()
        rendered = str(value).lower()[:1024]
        if leaf in _HALT_KEYS and value not in (False, None, "", 0, "ok"):
            halts.append(f"json_halt:{key}")
        if leaf in {"status", "state", "verdict"} and rendered in _HALT_VALUES:
            halts.append(f"json_halt:{key}={rendered}")
        if any(marker in rendered for marker in _PROVIDER_MARKERS):
            providers.append(f"provider_failure:{key}")
    return halts, providers


class LabAdapter:
    """Inspect one lab and invoke only its declared exact adapters."""

    def __init__(self, config: LabConfig) -> None:
        self.config = config

    def observe(
        self,
        now: float,
        runner: BoundedCommandRunner,
        *,
        retry_attempts: int,
        skip_probe: bool = False,
    ) -> LabSnapshot:
        refs: list[EvidenceRef] = []
        halts: list[str] = []
        providers: list[str] = []
        warnings: list[str] = []
        blockers: list[str] = []
        discovered: dict[Path, set[Path]] = {}
        latest_provider_paths: set[Path] = set()
        for declared in (*self.config.evidence_paths, *self.config.halt_paths):
            files, truncated = _discover_bounded(declared, self.config.max_scan_entries)
            if truncated:
                blockers.append(f"evidence_discovery_limit_reached:{declared}")
            if (
                declared in self.config.halt_paths
                and declared.exists()
                and not declared.is_dir()
            ):
                halts.append(f"halt_marker_present:{declared}")
            for file_path in files:
                discovered.setdefault(file_path, set()).add(declared)
            if declared in self.config.evidence_paths and files:
                newest = max(_mtime(file_path) for file_path in files)
                latest_provider_paths.update(
                    file_path for file_path in files if _mtime(file_path) == newest
                )
        ordered = sorted(discovered, key=lambda path: (-_mtime(path), str(path)))
        for file_path in ordered[: self.config.max_evidence_files]:
            ref = _safe_file_ref(file_path)
            if ref is None:
                warnings.append(f"unreadable_or_oversize_evidence:{file_path}")
                continue
            refs.append(ref)
            payload = _json_payload(file_path)
            if payload is not None:
                payload_halts, payload_providers = _payload_signals(payload)
                halts.extend(payload_halts)
                if file_path in latest_provider_paths:
                    providers.extend(payload_providers)
            if file_path.name.upper() in {"STOP", "KILL", "HALT"}:
                halts.append(f"halt_marker_present:{file_path}")
        if self.config.require_evidence and not refs:
            blockers.append("required_evidence_missing")

        probe: CommandOutcome | None = None
        if self.config.status_probe is not None:
            if skip_probe:
                warnings.append("status_probe_skipped_circuit_open")
            else:
                probe = runner.execute(
                    self.config.status_probe,
                    attempts=retry_attempts,
                )
                if not probe.available:
                    blockers.append(probe.error or "status_probe_unavailable")
                elif not probe.succeeded:
                    detail = f"{probe.stdout}\n{probe.stderr}\n{probe.error}".lower()
                    if any(marker in detail for marker in _PROVIDER_MARKERS):
                        providers.append("provider_failure:status_probe")
                    else:
                        warnings.append("status_probe_failed")
                elif probe.stdout.strip().startswith(("{", "[")):
                    try:
                        probe_payload = json.loads(probe.stdout)
                    except json.JSONDecodeError:
                        warnings.append("status_probe_invalid_json")
                    else:
                        payload_halts, payload_providers = _payload_signals(probe_payload)
                        halts.extend(payload_halts)
                        providers.extend(payload_providers)
        latest = max((ref.observed_mtime for ref in refs), default=None)
        return LabSnapshot(
            lab=self.config.name,
            observed_at=now,
            evidence=tuple(refs),
            latest_evidence_at=latest,
            halt_evidence=tuple(sorted(set(halts))),
            provider_failures=tuple(sorted(set(providers))),
            warnings=tuple(sorted(set(warnings))),
            blockers=tuple(sorted(set(blockers))),
            probe=probe,
        )

    def command_for(self, action: ActionKind) -> CommandSpec | None:
        return {
            ActionKind.KEEP_HALTED: self.config.keep_halted,
            ActionKind.QUARANTINE_PROVIDER: self.config.quarantine_provider,
            ActionKind.ROTATE_PROVIDER: self.config.rotate_provider,
            ActionKind.RUN_BOUNDED_TRIAL: self.config.bounded_trial,
        }.get(action)

    def run_declared_action(
        self,
        action: ActionKind,
        runner: BoundedCommandRunner,
        *,
        dry_run: bool,
    ) -> ActionResult:
        spec = self.command_for(action)
        if spec is None:
            if action == ActionKind.KEEP_HALTED:
                return ActionResult(self.config.name, action, "kept_halted", detail="no start attempted")
            return ActionResult(self.config.name, action, "unavailable", detail="adapter_not_declared")
        digest = command_hash(spec.argv, cwd=spec.cwd)
        if dry_run:
            return ActionResult(self.config.name, action, "dry_run", command_sha256=digest)
        outcome = runner.execute(spec)
        return ActionResult(
            self.config.name,
            action,
            "succeeded" if outcome.succeeded else "failed",
            command_sha256=digest,
            returncode=outcome.returncode,
            detail=outcome.error or ("" if outcome.succeeded else "declared_adapter_failed"),
        )

    def prune_disposable(self, now: float, *, dry_run: bool) -> ActionResult:
        candidates: list[Path] = []
        for root in self.config.disposable_paths:
            discovered, _ = _discover_bounded(root, self.config.max_scan_entries)
            ordered = sorted(discovered, key=lambda path: (_mtime(path), str(path)))
            for candidate in ordered[: self.config.max_evidence_files]:
                try:
                    age = now - candidate.stat(follow_symlinks=False).st_mtime
                except OSError:
                    continue
                if age >= self.config.disposable_min_age_seconds:
                    candidates.append(candidate)
        if dry_run:
            return ActionResult(
                self.config.name,
                ActionKind.PRUNE_DISPOSABLE,
                "dry_run",
                detail=f"eligible_files={len(candidates)}",
            )
        removed: list[str] = []
        for candidate in candidates:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                continue
            removed.append(str(candidate))
        return ActionResult(
            self.config.name,
            ActionKind.PRUNE_DISPOSABLE,
            "succeeded",
            detail=f"removed_files={len(removed)}",
            artifacts=tuple(removed),
        )
