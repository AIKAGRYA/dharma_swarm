"""Atomic serialized-file I/O for the graph persistence kernel."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


def read_serialized_state(path: Path, serializer: Any) -> dict[str, Any]:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("schema") != "dharma_swarm.graph.persistence.serialized.v1":
        return envelope
    payload = base64.b64decode(str(envelope["payload"]))
    state = serializer.loads_typed((str(envelope["type"]), payload))
    if not isinstance(state, dict):
        raise TypeError("graph persistence serializer must decode a mapping")
    return state


def atomic_write_serialized(
    target: Path, payload: Mapping[str, Any], serializer: Any
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload_type, serialized = serializer.dumps_typed(dict(payload))
    envelope = {
        "schema": "dharma_swarm.graph.persistence.serialized.v1",
        "type": payload_type,
        "payload": base64.b64encode(serialized).decode("ascii"),
    }
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), suffix=".tmp", prefix=".gthread_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
