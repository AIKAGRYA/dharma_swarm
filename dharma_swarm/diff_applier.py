"""Apply unified diffs to files with rollback and test integration.

Parses standard unified diff format, backs up affected files before
modification, and provides atomic apply-and-test: changes are kept only
when the test suite passes, rolled back otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.sandbox import terminate_process_group
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.spine.tollbooth import require_execution_tollbooth

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class ApplyResult(BaseModel):
    """Outcome of applying a unified diff."""

    success: bool
    files_changed: list[str] = []
    backup_paths: dict[str, str] = {}  # original -> backup
    error: str = ""


class ApplyTestResult(BaseModel):
    """Outcome of apply-then-test cycle."""

    applied: bool
    tests_passed: bool
    tests_output: str = ""
    files_changed: list[str] = []
    rolled_back: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Internal diff representation
# ---------------------------------------------------------------------------


@dataclass
class Hunk:
    """A single hunk from a unified diff."""

    src_start: int
    src_count: int
    dst_start: int
    dst_count: int
    lines: list[str] = field(default_factory=list)


@dataclass
class FilePatch:
    """All hunks targeting a single file."""

    old_path: str  # "a/foo.py" or "/dev/null"
    new_path: str  # "b/foo.py" or "/dev/null"
    hunks: list[Hunk] = field(default_factory=list)
    is_new_file: bool = False

    @property
    def target_path(self) -> str:
        """Return the effective file path (strip leading a/ or b/)."""
        if self.new_path == "/dev/null":
            return _strip_prefix(self.old_path)
        return _strip_prefix(self.new_path)


_HUNK_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@"
)


def _strip_prefix(path: str) -> str:
    """Remove leading ``a/`` or ``b/`` prefix from diff paths."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


# ---------------------------------------------------------------------------
# Diff parser
# ---------------------------------------------------------------------------


def parse_unified_diff(diff_text: str) -> list[FilePatch]:
    """Parse a unified diff into a list of per-file patches.

    Handles single and multi-file diffs, multi-hunk patches, new files, and
    context/addition/removal lines.
    """
    patches: list[FilePatch] = []
    current_patch: FilePatch | None = None
    current_hunk: Hunk | None = None
    lines = diff_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("--- "):
            old_path = line[4:].strip()
            if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                new_path = lines[i + 1][4:].strip()
                current_patch = FilePatch(
                    old_path=old_path,
                    new_path=new_path,
                    is_new_file=old_path == "/dev/null",
                )
                patches.append(current_patch)
                current_hunk = None
                i += 2
                continue

        match = _HUNK_RE.match(line)
        if match and current_patch is not None:
            current_hunk = Hunk(
                src_start=int(match.group(1)),
                src_count=(
                    int(match.group(2)) if match.group(2) is not None else 1
                ),
                dst_start=int(match.group(3)),
                dst_count=(
                    int(match.group(4)) if match.group(4) is not None else 1
                ),
            )
            current_patch.hunks.append(current_hunk)
            i += 1
            continue

        if current_hunk is not None and line[:1] in (" ", "+", "-"):
            current_hunk.lines.append(line)
            i += 1
            continue

        i += 1

    return patches


# ---------------------------------------------------------------------------
# DiffApplier
# ---------------------------------------------------------------------------


class DiffApplier:
    """Applies unified diffs to files safely with rollback capability."""

    def __init__(
        self,
        workspace: Path | None = None,
        *,
        runtime_state: RuntimeStateStore | None = None,
        require_identity: bool = False,
    ) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self._runtime_state = runtime_state
        self._require_identity = require_identity

    async def apply(
        self,
        diff_text: str,
        dry_run: bool = False,
        *,
        execution_identity: ExecutionIdentity | None = None,
        require_identity: bool | None = None,
        proposal_id: str = "",
    ) -> ApplyResult:
        """Parse and apply a unified diff, backing up every existing target."""
        stripped = diff_text.strip()
        if not stripped:
            return ApplyResult(success=True)

        try:
            patches = parse_unified_diff(stripped)
        except ValueError as exc:
            return ApplyResult(success=False, error=str(exc))

        if not patches:
            return ApplyResult(success=True)

        # PR-001 fail-closed backstop: never write into a protected live checkout.
        # dry_run validates without writing, so it is exempt.
        if not dry_run:
            from dharma_swarm.evolution_safety import (
                LiveMutationDenied,
                guard_writable_target,
            )

            try:
                guard_writable_target(self.workspace)
                for patch in patches:
                    guard_writable_target(self.workspace / patch.target_path)
            except LiveMutationDenied as exc:
                return ApplyResult(success=False, error=str(exc))

        effective_require = (
            self._require_identity
            if require_identity is None
            else require_identity
        )
        identity: ExecutionIdentity | None = None
        if not dry_run:
            try:
                identity = require_execution_tollbooth(
                    execution_identity=execution_identity,
                    runtime_state=self._runtime_state,
                    surface="diff_applier",
                    action="apply",
                    require_identity=effective_require,
                )
            except MissingExecutionIdentity as exc:
                return ApplyResult(success=False, error=str(exc))
            if identity is not None and self._runtime_state is not None:
                self._runtime_state.record_execution_identity_sync(
                    identity,
                    source="diff_applier.apply",
                    metadata={"surface": "self_modification"},
                )
                self._runtime_state.record_self_mod_receipt_sync(
                    identity,
                    stage="apply",
                    status="requested",
                    proposal_id=proposal_id or identity.proposal_id,
                    payload={
                        "files": [patch.target_path for patch in patches],
                        "dry_run": dry_run,
                    },
                )

        files_changed: list[str] = []
        backup_paths: dict[str, str] = {}

        for patch in patches:
            target = self.workspace / patch.target_path

            if not patch.is_new_file and not target.exists():
                if identity is not None and self._runtime_state is not None:
                    self._runtime_state.record_self_mod_receipt_sync(
                        identity,
                        stage="apply",
                        status="failed",
                        proposal_id=proposal_id or identity.proposal_id,
                        payload={
                            "file": patch.target_path,
                            "error": "target_missing",
                        },
                    )
                return ApplyResult(
                    success=False,
                    error=f"Target file does not exist: {patch.target_path}",
                    files_changed=files_changed,
                    backup_paths=backup_paths,
                )

            if dry_run:
                files_changed.append(patch.target_path)
                continue

            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(str(target), str(backup))
                backup_paths[str(target)] = str(backup)

            try:
                self._apply_patch(target, patch)
            except Exception as exc:
                if identity is not None and self._runtime_state is not None:
                    self._runtime_state.record_self_mod_receipt_sync(
                        identity,
                        stage="apply",
                        status="failed",
                        proposal_id=proposal_id or identity.proposal_id,
                        payload={
                            "file": patch.target_path,
                            "error": type(exc).__name__,
                        },
                    )
                return ApplyResult(
                    success=False,
                    error=f"Failed applying patch to {patch.target_path}: {exc}",
                    files_changed=files_changed,
                    backup_paths=backup_paths,
                )

            files_changed.append(patch.target_path)

        if identity is not None and self._runtime_state is not None:
            self._runtime_state.record_self_mod_receipt_sync(
                identity,
                stage="apply",
                status="applied",
                proposal_id=proposal_id or identity.proposal_id,
                payload={"files": files_changed},
            )
        return ApplyResult(
            success=True,
            files_changed=files_changed,
            backup_paths=backup_paths,
        )

    async def rollback(self, result: ApplyResult) -> None:
        """Restore files from backups recorded in *result*."""
        for original, backup in result.backup_paths.items():
            backup_path = Path(backup)
            original_path = Path(original)
            if backup_path.exists():
                shutil.copy2(str(backup_path), str(original_path))
                backup_path.unlink()
                logger.debug("Rolled back %s from %s", original, backup)

    async def apply_and_test(
        self,
        diff_text: str,
        test_command: str = "python3 -m pytest tests/ -q --tb=short",
        timeout: float = 120.0,
    ) -> ApplyTestResult:
        """Apply a diff, run tests, and roll back on failure or timeout.

        Caller cancellation is preserved after the command is terminated and
        the workspace is restored. Cancellation is not translated into an
        ordinary test result because upstream orchestration relies on that
        control-flow signal.
        """
        apply_result = await self.apply(diff_text)
        if not apply_result.success:
            return ApplyTestResult(
                applied=False,
                tests_passed=False,
                error=apply_result.error,
            )

        if not apply_result.files_changed:
            return ApplyTestResult(
                applied=True,
                tests_passed=True,
                files_changed=[],
            )

        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_shell(
                test_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                start_new_session=True,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            if proc is not None:
                await terminate_process_group(proc)
            await self.rollback(apply_result)
            return ApplyTestResult(
                applied=True,
                tests_passed=False,
                tests_output="Test command timed out",
                files_changed=apply_result.files_changed,
                rolled_back=True,
                error=f"Test command timed out after {timeout}s",
            )
        except asyncio.CancelledError:
            if proc is not None:
                await terminate_process_group(proc)
            await asyncio.shield(self.rollback(apply_result))
            raise
        except OSError as exc:
            await self.rollback(apply_result)
            return ApplyTestResult(
                applied=True,
                tests_passed=False,
                tests_output="",
                files_changed=apply_result.files_changed,
                rolled_back=True,
                error=f"Failed to run test command: {exc}",
            )

        output = stdout_bytes.decode(errors="replace")
        err_output = stderr_bytes.decode(errors="replace")
        combined = (output + "\n" + err_output).strip()
        returncode = proc.returncode if proc.returncode is not None else -1

        if returncode == 0:
            for backup in apply_result.backup_paths.values():
                Path(backup).unlink(missing_ok=True)
            return ApplyTestResult(
                applied=True,
                tests_passed=True,
                tests_output=combined,
                files_changed=apply_result.files_changed,
            )

        await self.rollback(apply_result)
        return ApplyTestResult(
            applied=True,
            tests_passed=False,
            tests_output=combined,
            files_changed=apply_result.files_changed,
            rolled_back=True,
        )

    @staticmethod
    def _apply_patch(target: Path, patch: FilePatch) -> None:
        """Apply all hunks from *patch* to *target*."""
        if patch.is_new_file:
            target.parent.mkdir(parents=True, exist_ok=True)
            content_lines: list[str] = []
            for hunk in patch.hunks:
                for line in hunk.lines:
                    if line.startswith("+"):
                        content_lines.append(line[1:])
                    elif line.startswith(" "):
                        content_lines.append(line[1:])
            target.write_text(
                "\n".join(content_lines) + "\n" if content_lines else "",
                encoding="utf-8",
            )
            return

        source_lines = target.read_text(encoding="utf-8").splitlines()

        for hunk in reversed(patch.hunks):
            new_lines: list[str] = []
            for line in hunk.lines:
                if line.startswith("+"):
                    new_lines.append(line[1:])
                elif line.startswith(" "):
                    new_lines.append(line[1:])

            start = hunk.src_start - 1
            end = start + hunk.src_count
            source_lines[start:end] = new_lines

        target.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
