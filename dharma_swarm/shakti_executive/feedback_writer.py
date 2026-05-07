"""Write realized outcomes back into ``opportunity_board.json``.

This module closes the next concrete step on BR-002 (central VentureCell loop
is open). The shakti executive already READS Outcome / ValueEvent /
Contribution rows from the TelicSeam (see ``inputs.read_telic_feedback``),
but the WRITE side — feeding realized outcomes back into the board so future
scoring sees what already happened — was the missing edge.

What this module does:

- ``update_opportunity_outcome(opp_id, outcome, *, board_path=None)``
  appends an outcome record to the matching opportunity's
  ``realized_outcomes`` list and recomputes a ``learned_score_delta``
  derived from outcome success / fitness. Writes atomically (tmp + rename).

What this module does NOT do:

- It does NOT resolve ``proposal_id`` → ``opportunity_id``. That linkage lives
  upstream — Outcomes carry ``proposal_id`` (see
  ``dharma_swarm/telic_seam.py:record_outcome``), and the proposal is created
  from a campaign manifest at ``~/.dharma/campaigns/<opp_id>/manifest.json``
  by ``dharma_swarm/opportunity_dispatcher.py``. The caller is expected to
  walk that chain and pass the fully-resolved ``opp_id``.
- It does NOT register a caller. Wiring this writer into the existing telic
  seam outcome dispatcher is the follow-up step; until that lands, this
  module is a public-API library.

Design contracts:

- Idempotent on duplicate ``outcome_id``. If an outcome with the same id is
  already present in ``realized_outcomes``, the write is a no-op and returns
  ``False``.
- Atomic write. Uses tmp + rename, the same pattern as
  ``dharma_swarm/cron_scheduler.py:save_jobs`` (line 208).
- Best-effort backup. Writes the prior file to
  ``opportunity_board.json.bak.<ts>`` if it exists, matching the convention
  in ``tests/test_shakti_executive.py:51``.
- Silent on missing board. If the board file does not exist, this function
  is a no-op returning ``False`` rather than raising — outcomes can arrive
  before the board is initialized.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BOARD_PATH = Path.home() / ".dharma" / "meta" / "opportunity_board.json"


@dataclass(frozen=True)
class OutcomeRecord:
    """Minimal projection of a TelicSeam Outcome for board feedback.

    Constructed by the caller from an Outcome row read out of
    ``ontology.db``. We project to a small frozen shape so the writer's
    contract does not couple to the ontology schema.
    """

    outcome_id: str
    """Stable id from the ontology layer (Outcome.id). Used for dedup."""

    proposal_id: str
    """The ActionProposal id the outcome closed. Audit trail only."""

    success: bool
    """Whether the agent completed the task successfully."""

    fitness_score: float = 0.0
    """0.0–1.0 (or higher), agent self-reported. Drives learned_score_delta."""

    duration_ms: float = 0.0
    """Wall time. Audit trail only."""

    result_summary: str = ""
    """Short human-readable summary. Truncated upstream to 500 chars."""

    recorded_at: float = 0.0
    """Unix timestamp when the outcome was recorded. 0.0 = use now()."""


def _learned_score_delta(outcome: OutcomeRecord) -> float:
    """Convert a single outcome into a board-score adjustment.

    Conservative: success contributes +fitness, failure contributes
    -0.5 * (1.0 - fitness). Capped to [-1.0, +1.0] per single outcome so a
    single bad run cannot dominate the board score. The caller can sum
    deltas across multiple outcomes; the cap is per-row.
    """
    if outcome.success:
        delta = max(0.0, min(1.0, outcome.fitness_score))
    else:
        delta = -0.5 * (1.0 - max(0.0, min(1.0, outcome.fitness_score)))
    return max(-1.0, min(1.0, delta))


def _atomic_write_json(path: Path, payload: list[dict[str, Any]]) -> None:
    """Tmp-then-rename atomic write. Same pattern as cron_scheduler.py:208."""
    tmp = path.with_suffix(path.suffix + f".tmp.{int(time.time() * 1000)}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def update_opportunity_outcome(
    opp_id: str,
    outcome: OutcomeRecord,
    *,
    board_path: Path | None = None,
    backup: bool = True,
) -> bool:
    """Append an outcome to the matching opportunity's realized_outcomes list.

    Returns True on a successful append, False if the board does not exist,
    no matching opportunity is found, or the outcome was already recorded
    (idempotent). Writes atomically via tmp+rename.
    """
    path = (board_path or DEFAULT_BOARD_PATH).expanduser()
    if not path.exists():
        logger.debug("opportunity_board.json missing at %s; skipping", path)
        return False

    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read opportunity_board at %s: %s", path, exc)
        return False

    if not isinstance(rows, list):
        logger.warning("opportunity_board at %s is not a list; refusing to write", path)
        return False

    matched = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("opportunity_id") or "")
        if row_id != opp_id:
            continue
        matched = True

        existing = row.setdefault("realized_outcomes", [])
        if not isinstance(existing, list):
            logger.warning(
                "opportunity %s has non-list realized_outcomes; replacing", opp_id
            )
            existing = []
            row["realized_outcomes"] = existing

        if any(
            isinstance(prev, dict) and prev.get("outcome_id") == outcome.outcome_id
            for prev in existing
        ):
            return False  # idempotent: already recorded

        existing.append(
            {
                "outcome_id": outcome.outcome_id,
                "proposal_id": outcome.proposal_id,
                "success": outcome.success,
                "fitness_score": outcome.fitness_score,
                "duration_ms": outcome.duration_ms,
                "result_summary": outcome.result_summary,
                "recorded_at": outcome.recorded_at or time.time(),
            }
        )
        row["learned_score_delta"] = (
            float(row.get("learned_score_delta", 0.0)) + _learned_score_delta(outcome)
        )
        break

    if not matched:
        logger.debug("no opportunity matched id=%s; outcome dropped", opp_id)
        return False

    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
        try:
            backup_path.write_bytes(path.read_bytes())
        except OSError as exc:
            logger.warning("backup write failed for %s: %s", path, exc)

    _atomic_write_json(path, rows)
    return True
