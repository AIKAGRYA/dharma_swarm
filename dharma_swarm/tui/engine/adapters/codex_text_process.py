"""Bounded subprocess transport primitives for the sealed Codex text lane."""

from __future__ import annotations

import asyncio
import contextlib
from typing import AsyncIterator


class CodexTextProcessMixin:
    """Own raw-byte I/O limits and deterministic subprocess cleanup."""

    _READ_CHUNK_SIZE = 64 * 1024
    _MAX_PENDING_EVENT_BYTES = 8 * 1024 * 1024
    _MAX_TOTAL_STDOUT_BYTES = 16 * 1024 * 1024
    _MAX_ASSISTANT_BYTES = 4 * 1024 * 1024
    _CANCEL_GRACE_SECONDS = 5.0

    async def _spawn_process(
        self,
        command: list[str],
        environment: dict[str, str],
    ) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._workdir),
            env=environment,
        )

    async def _write_prompt(
        self,
        process: asyncio.subprocess.Process,
        prompt: bytes,
    ) -> None:
        if process.stdin is None:
            raise RuntimeError("Codex text subprocess stdin is unavailable")
        process.stdin.write(prompt)
        await process.stdin.drain()
        process.stdin.close()
        wait_closed = getattr(process.stdin, "wait_closed", None)
        if callable(wait_closed):
            with contextlib.suppress(Exception):
                await wait_closed()

    async def _iter_stdout_lines(
        self,
        process: asyncio.subprocess.Process,
    ) -> AsyncIterator[str]:
        if process.stdout is None:
            return
        pending = bytearray()
        total_bytes = 0
        while True:
            chunk = await process.stdout.read(self._READ_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > self._MAX_TOTAL_STDOUT_BYTES:
                raise ValueError("Codex text provider output exceeded the total limit")
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                if newline > self._MAX_PENDING_EVENT_BYTES:
                    raise ValueError(
                        "Codex text provider event exceeded the buffer limit"
                    )
                raw = bytes(pending[:newline])
                del pending[: newline + 1]
                yield raw.decode("utf-8", errors="strict")
            if len(pending) > self._MAX_PENDING_EVENT_BYTES:
                raise ValueError("Codex text provider event exceeded the buffer limit")
        if pending:
            if len(pending) > self._MAX_PENDING_EVENT_BYTES:
                raise ValueError("Codex text provider event exceeded the buffer limit")
            yield pending.decode("utf-8", errors="strict")

    async def _discard_stderr(self, process: asyncio.subprocess.Process) -> None:
        if process.stderr is None:
            return
        while True:
            try:
                chunk = await process.stderr.read(self._READ_CHUNK_SIZE)
            except TypeError:
                chunk = await process.stderr.read()
            if not chunk:
                return

    async def _terminate_process(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self._CANCEL_GRACE_SECONDS,
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
