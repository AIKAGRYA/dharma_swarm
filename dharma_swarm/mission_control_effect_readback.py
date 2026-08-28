"""Historical exact readback for the governed repository-effect fence."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from dharma_swarm.mission_control_effect_fence_store import row_binding
from dharma_swarm.mission_control_effect_records import (
    EffectFenceRecord,
    EffectTerminalRecord,
)
from dharma_swarm.mission_control_effect_terminal_store import existing_terminal
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_FENCE_TABLE,
    require_effect_fence_schema,
)


def _time(raw: object) -> datetime:
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effect fence timestamp is naive")
    return value


def read_effect_fence(
    runtime_database: Path, effect_key: str,
) -> EffectFenceRecord | None:
    """Read historical evidence; this does not assert current target bytes."""

    uri = f"file:{Path(runtime_database).resolve(strict=True)}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        require_effect_fence_schema(db)
        rows = db.execute(
            f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE effect_key=? LIMIT 2",
            (effect_key,),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise sqlite3.IntegrityError("effect fence readback is not unique")
        row, binding = rows[0], row_binding(rows[0])
        terminal: EffectTerminalRecord | None = None
        if row["state"] == "consumed":
            terminal = existing_terminal(db, row)
        return EffectFenceRecord(
            str(row["fence_id"]), str(row["state"]), binding,
            _time(row["fence_created_at"]), _time(row["warrant_issued_at"]),
            _time(row["warrant_expires_at"]), int(row["claim_generation"]),
            str(row["claimed_by"]),
            _time(row["consuming_at"]) if row["consuming_at"] else None,
            terminal, str(row["quarantine_reason"]), str(row["observed_sha256"]),
            _time(row["quarantined_at"]) if row["quarantined_at"] else None,
        )


__all__ = ["read_effect_fence"]
