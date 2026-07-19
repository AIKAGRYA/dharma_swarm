"""Apply unified diffs to files with rollback and test integration.

Parses standard unified diff format, backs up affected files before
modification, and provides atomic apply-and-test: changes are kept only
when the test suite passes, rolled back otherwise.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.sandbox import await_cleanup, terminate_process_group
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
    created_files: list[str] = []
    error: str = ""
    # True when the idempotency fence replayed a prior completed apply of the
    # same diff content instead of splicing it in a second time.
    deduplicated: bool = False


def _apply_side_effect_key(proposal_id: str, diff_text: str) -> str:
    """Content-addressed side-effect key for one consequential diff apply."""
    digest = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    return f"self_mod:apply:{proposal_id or 'adhoc'}:{digest}"


def _fence_claim_key(side_effect_key: str) -> str:
    """Deterministic claim idempotency key (same ``sek_`` convention as
    graph/durable_invoker): every applier of the same diff — including a
    crash-requeued one with a re-minted ExecutionIdentity — races on the
    SAME (idempotency_key, side_effect_key) row."""
    return f"sek_{hashlib.sha256(side_effect_key.encode('utf-8')).hexdigest()}"


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

    Handles:
    - Single and multi-file diffs
    - Multi-hunk patches
    - New file creation (old path ``/dev/null``)
    - Context, addition, and removal lines

    Args:
        diff_text: The full unified diff string.

    Returns:
        A list of ``FilePatch`` objects.

    Raises:
        ValueError: If the diff contains malformed hunk headers.
    """
    patches: list[FilePatch] = []
    current_patch: FilePatch | None = None
    current_hunk: Hunk | None = None
    lines = diff_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- / +++ pair signals a new file patch
        if line.startswith("--- "):
            old_path = line[4:].strip()
            # Expect +++ on the next line
            if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                new_path = lines[i + 1][4:].strip()
                is_new = old_path == "/dev/null"
                current_patch = FilePatch(
                    old_path=old_path,
                    new_path=new_path,
                    is_new_file=is_new,
                )
                patches.append(current_patch)
                current_hunk = None
                i += 2
                continue

        # Hunk header
        m = _HUNK_RE.match(line)
        if m and current_patch is not None:
            current_hunk = Hunk(
                src_start=int(m.group(1)),
                src_count=int(m.group(2)) if m.group(2) is not None else 1,
                dst_start=int(m.group(3)),
                dst_count=int(m.group(4)) if m.group(4) is not None else 1,
            )
            current_patch.hunks.append(current_hunk)
            i += 1
            continue

        # Hunk body: context, add, or remove lines
        if current_hunk is not None and line[:1] in (" ", "+", "-"):
            current_hunk.lines.append(line)
            i += 1
            continue

        # Skip diff metadata lines (diff --git, index, etc.)
        i += 1

    return patches


# ---------------------------------------------------------------------------
# DiffApplier
# ---------------------------------------------------------------------------


class DiffApplier:
    """Applies unified diffs to files safely with rollback capability.

    Args:
        workspace: Root directory for resolving relative paths in the diff.
            Defaults to the current working directory.
    """

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
        """Parse and apply a unified diff.

        1. Parse the diff to extract file paths and hunks.
        2. Back up affected files.
        3. Apply changes.
        4. Return ``ApplyResult`` with files changed and backup paths.

        If *dry_run* is ``True``, validates the diff without writing.

        Args:
            diff_text: Unified diff text.
            dry_run: When set, only validate -- do not modify files.

        Returns:
            An ``ApplyResult`` describing what was (or would be) changed.
        """
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

        effective_require = self._require_identity if require_identity is None else require_identity
        identity: ExecutionIdentity | None = None
        fence_key = ""
        fence_claim: ExecutionIdentity | None = None
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
                fence_key = _apply_side_effect_key(
                    proposal_id or identity.proposal_id, stripped
                )
                fence_claim = identity.with_updates(
                    idempotency_key=_fence_claim_key(fence_key)
                )
                try:
                    begun = await self._runtime_state.try_begin_idempotent_side_effect(
                        fence_claim,
                        fence_key,
                        metadata={"surface": "self_modification"},
                    )
                except Exception:
                    # Fail-open (availability doctrine): the apply proceeds
                    # unfenced, loudly — never silently blocked by the store.
                    logger.warning(
                        "diff_applier: idempotency begin failed for %s;"
                        " applying WITHOUT fence",
                        fence_key,
                        exc_info=True,
                    )
                    begun, fence_claim = True, None
                if not begun and fence_claim is not None:
                    record = await self._runtime_state.get_idempotency_record(
                        fence_claim.idempotency_key, fence_key
                    )
                    prior_status = getattr(record, "status", "") if record else ""
                    if prior_status == "completed":
                        self._runtime_state.record_self_mod_receipt_sync(
                            identity,
                            stage="apply",
                            status="deduplicated",
                            proposal_id=proposal_id or identity.proposal_id,
                            payload={"side_effect_key": fence_key},
                        )
                        return ApplyResult(success=True, deduplicated=True)
                    if prior_status == "started":
                        # A live concurrent apply holds this diff; a second
                        # positional splice would corrupt the files.
                        return ApplyResult(
                            success=False,
                            error=(
                                "duplicate apply in flight for"
                                f" side_effect_key={fence_key}"
                            ),
                        )
                    # failed / unreadable prior attempt: retry re-executes.
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
        created_files: list[str] = []

        for patch in patches:
            target = self.workspace / patch.target_path

            # Validate: if not a new file, the target must exist
            if not patch.is_new_file and not target.exists():
                if identity is not None and self._runtime_state is not None:
                    self._runtime_state.record_self_mod_receipt_sync(
                        identity,
                        stage="apply",
                        status="failed",
                        proposal_id=proposal_id or identity.proposal_id,
                        payload={"file": patch.target_path, "error": "target_missing"},
                    )
                await self._complete_apply_fence(fence_claim, fence_key, status="failed")
                return ApplyResult(
                    success=False,
                    error=f"Target file does not exist: {patch.target_path}",
                    files_changed=files_changed,
                    backup_paths=backup_paths,
                )

            if dry_run:
                files_changed.append(patch.target_path)
                continue

            # Back up existing file
            if target.exists():
                backup = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(str(target), str(backup))
                backup_paths[str(target)] = str(backup)

            # Apply hunks
            try:
                self._apply_patch(target, patch)
            except Exception as exc:
                if identity is not None and self._runtime_state is not None:
                    self._runtime_state.record_self_mod_receipt_sync(
                        identity,
                        stage="apply",
                        status="failed",
                        proposal_id=proposal_id or identity.proposal_id,
                        payload={"file": patch.target_path, "error": type(exc).__name__},
                    )
                await self._complete_apply_fence(fence_claim, fence_key, status="failed")
                return ApplyResult(
                    success=False,
                    error=f"Failed applying patch to {patch.target_path}: {exc}",
                    files_changed=files_changed,
                    backup_paths=backup_paths,
                )

            files_changed.append(patch.target_path)
            if patch.is_new_file and str(target) not in backup_paths:
                created_files.append(patch.target_path)

        if identity is not None and self._runtime_state is not None:
            self._runtime_state.record_self_mod_receipt_sync(
                identity,
                stage="apply",
                status="applied",
                proposal_id=proposal_id or identity.proposal_id,
                payload={"files": files_changed},
            )
        await self._complete_apply_fence(fence_claim, fence_key, status="completed")
        return ApplyResult(
            success=True,
            files_changed=files_changed,
            backup_paths=backup_paths,
            created_files=created_files,
        )

    async def _complete_apply_fence(
        self,
        fence_claim: ExecutionIdentity | None,
        fence_key: str,
        *,
        status: str,
    ) -> None:
        """Resolve the apply's idempotency row, fail-open (never break apply)."""
        if fence_claim is None or not fence_key or self._runtime_state is None:
            return
        try:
            await self._runtime_state.complete_idempotent_side_effect(
                fence_claim, fence_key, status=status
            )
        except Exception:
            logger.warning(
                "diff_applier: fence completion failed for %s", fence_key, exc_info=True
            )

    async def rollback(self, result: ApplyResult) -> None:
        """Restore backups and unlink only paths created by this apply."""
        for original, backup in result.backup_paths.items():
            backup_path = Path(backup)
            original_path = Path(original)
            if backup_path.exists():
                shutil.copy2(str(backup_path), str(original_path))
                backup_path.unlink()
                logger.debug("Rolled back %s from %s", original, backup)
        for relative in result.created_files:
            candidate = self.workspace / relative
            parent = candidate.parent.resolve(strict=False)
            if parent.is_relative_to(self.workspace):
                # Do not resolve the final component: unlink a replacement
                # symlink itself, never the file it points at.
                (parent / candidate.name).unlink(missing_ok=True)

    async def apply_and_test(
        self,
        diff_text: str,
        test_command: str = "python3 -m pytest tests/ -q --tb=short",
        timeout: float = 120.0,
    ) -> ApplyTestResult:
        """Apply a diff, run tests, and rollback on failure.

        Caller cancellation terminates the test process, restores the workspace,
        and then propagates ``CancelledError`` to the orchestrator.
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
            try:
                if proc is not None:
                    await terminate_process_group(proc)
            finally:
                await await_cleanup(self.rollback(apply_result))
            return ApplyTestResult(
                applied=True,
                tests_passed=False,
                tests_output="Test command timed out",
                files_changed=apply_result.files_changed,
                rolled_back=True,
                error=f"Test command timed out after {timeout}s",
            )
        except asyncio.CancelledError:
            try:
                if proc is not None:
                    await terminate_process_group(proc)
            finally:
                await await_cleanup(self.rollback(apply_result))
            raise
        except OSError as exc:
            await await_cleanup(self.rollback(apply_result))
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

        await await_cleanup(self.rollback(apply_result))
        return ApplyTestResult(
            applied=True,
            tests_passed=False,
            tests_output=combined,
            files_changed=apply_result.files_changed,
            rolled_back=True,
        )

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _apply_patch(target: Path, patch: FilePatch) -> None:
        """Apply all hunks from *patch* to *target.

        For new files, creates the file with added lines.
        For existing files, applies hunks in reverse order to preserve
        line number validity.
        """
        if patch.is_new_file:
            target.parent.mkdir(parents=True, exist_ok=True)
            content_lines: list[str] = []
            for hunk in patch.hunks:
                for line in hunk.lines:
                    if line.startswith("+"):
                        content_lines.append(line[1:])
                    elif line.startswith(" "):
                        content_lines.append(line[1:])
            target.write_text("\n".join(content_lines) + "\n" if content_lines else "", encoding="utf-8")
            return

        source_lines = target.read_text(encoding="utf-8").splitlines()

        # Apply hunks in reverse order so earlier hunks don't shift later ones
        for hunk in reversed(patch.hunks):
            new_lines: list[str] = []
            for line in hunk.lines:
                if line.startswith("+"):
                    new_lines.append(line[1:])
                elif line.startswith(" "):
                    new_lines.append(line[1:])
                # "-" lines are removed (not added to new_lines)

            start = hunk.src_start - 1  # diff is 1-indexed
            end = start + hunk.src_count
            source_lines[start:end] = new_lines

        target.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
