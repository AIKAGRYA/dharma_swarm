"""Bounded subprocess lifecycle helpers for the Claude adapter."""

from __future__ import annotations

import asyncio
from typing import Any


async def drain_stderr_tail(stream: Any, *, limit_bytes: int = 65_536) -> str:
    """Drain a child pipe concurrently while retaining a bounded text tail."""

    tail = bytearray()
    while chunk := await stream.read(8192):
        tail.extend(chunk)
        if len(tail) > limit_bytes:
            del tail[:-limit_bytes]
    return bytes(tail).decode("utf-8", errors="replace").strip()


async def terminate_process(process: Any, *, timeout_seconds: float = 5.0) -> None:
    """Terminate and reap a child, escalating to kill after a bounded wait."""

    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()
