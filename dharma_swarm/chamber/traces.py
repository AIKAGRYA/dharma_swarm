"""chamber_gym_trace.v1 — the E5 trace mandate: no gym run without capture.

Elevation spec E5 (docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md):
every chamber gym run logs one trace row per task in this pinned schema so the
distillation corpus (doctrine env 12) exists the day distillation is earned.
A gym receipt that does not pin its trace corpus sha256 fails its closure
check by construction.

Deliberately mirrors the arena's labeled-trace conventions
(coordination/arena/corpus.py: deterministic sort_keys JSONL + corpus sha256)
WITHOUT importing from arena surfaces — shared receipt format, disjoint
surfaces (RSI-lab boundary contract, dossier §2d).

Every row is deterministic and replayable: same solver outputs against the
same frozen taskpack yield the same bytes, so the corpus is verifiable
evidence, not accumulated state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CHAMBER_GYM_TRACE_SCHEMA = "chamber_gym_trace.v1"


def canonical_json(payload: object) -> str:
    """Same canonical form as check_track_status / spine.receipt digests."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SeatAnswer:
    """One seat's answer to one task, with the identity needed for the E1
    transcendence decomposition (per-seat error profiles) and the env-12
    distillation corpus (which model produced what, at what cost)."""

    seat_id: str
    answer: str
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    correct: bool | None = None  # per-seat label when the scorer scores seats


@dataclass(frozen=True, slots=True)
class GymTraceRow:
    """One task x one gym run. ``correct`` is the DETERMINISTIC scorer's label
    for the aggregated answer — the sole correctness authority (never a judge,
    never a vote)."""

    env_id: str
    task_id: str
    taskpack_sha: str
    scorer_hash: str
    seed: int
    answers: tuple[SeatAnswer, ...]
    aggregated_answer: str
    correct: bool
    schema: str = CHAMBER_GYM_TRACE_SCHEMA
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["answers"] = [asdict(a) for a in self.answers]
        row["digest"] = stable_digest({k: v for k, v in row.items() if k != "digest"})
        return row


def render_corpus_jsonl(rows: list[dict[str, Any]]) -> str:
    """Deterministic JSONL (same rows -> same bytes -> same sha)."""
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def corpus_sha256(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(render_corpus_jsonl(rows).encode("utf-8")).hexdigest()


def verify_row_digest(row: dict[str, Any]) -> bool:
    stored = str(row.get("digest", ""))
    return bool(stored) and stored == stable_digest(
        {k: v for k, v in row.items() if k != "digest"}
    )


def write_corpus(rows: list[dict[str, Any]], path: Path) -> str:
    """Write the corpus and return its sha256 (the value a gym receipt MUST
    pin — the E5 closure check). Refuses rows with missing/invalid digests."""
    for i, row in enumerate(rows):
        if row.get("schema") != CHAMBER_GYM_TRACE_SCHEMA:
            raise ValueError(f"row {i}: wrong schema {row.get('schema')!r}")
        if not verify_row_digest(row):
            raise ValueError(f"row {i}: missing or invalid digest")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_corpus_jsonl(rows), encoding="utf-8")
    return corpus_sha256(rows)


def read_corpus(path: Path) -> list[dict[str, Any]]:
    """Read + verify a trace corpus; tampered rows are an error, not a skip."""
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"trace corpus {path} row {i}: not a JSON object")
        if not verify_row_digest(row):
            raise ValueError(f"trace corpus {path} row {i}: digest mismatch")
        rows.append(row)
    return rows


__all__ = [
    "CHAMBER_GYM_TRACE_SCHEMA",
    "GymTraceRow",
    "SeatAnswer",
    "canonical_json",
    "corpus_sha256",
    "read_corpus",
    "render_corpus_jsonl",
    "stable_digest",
    "verify_row_digest",
    "write_corpus",
]
