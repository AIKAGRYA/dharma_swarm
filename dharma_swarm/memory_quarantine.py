"""Quality-quarantine gate for StrangeLoop / latent-gold recall surfaces.

2026-07-25 memory audit §5.11: quality tags were cosmetic — every recall
surface served ``low_quality`` rows into context bundles. 11,897 of 12,065
live rows (98.6%) carry the tag, so flipping a blind predicate would empty
the Always-On section of every bundle fleet-wide. Hence three modes via
``DHARMA_MEMORY_QUALITY_QUARANTINE``:

  off      — legacy behavior, no counting.
  shadow   — DEFAULT. Serve legacy results but stamp would_be_excluded
             counts into a JSONL receipt for 1wk+ before any enforce flip.
  enforce  — quarantined rows excluded from recall (still readable via
             explicit ``include_quarantined=True``).

Receipt store role (ANTI_SLOP Rule 2): derived-view telemetry only —
append-only JSONL at ``<state>/witness/memory_quarantine_shadow.jsonl``,
truncatable at will, never read back by runtime code.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

QUARANTINE_ENV = "DHARMA_MEMORY_QUALITY_QUARANTINE"
MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"
_MODES = {MODE_OFF, MODE_SHADOW, MODE_ENFORCE}

LOW_QUALITY_TAG = "low_quality"
# Mirrors StrangeLoopMemory.FITNESS_THRESHOLD; used only when tags are unknown.
QUALITY_FLOOR = 0.6

# SQL twin of is_quarantined() for sites that filter in the SELECT itself
# (tags is a JSON-encoded list of strings, so the quoted form is exact).
SQL_NOT_QUARANTINED = "tags NOT LIKE '%\"low_quality\"%'"

RECEIPT_RELPATH = Path("witness") / "memory_quarantine_shadow.jsonl"
_RECEIPT_MAX_BYTES = 64 * 1024 * 1024

# In-process tally of receipt-append failures; recorded so the broad handler
# in record_shadow_receipt is observable, not a silent swallow (AS-09).
RECEIPT_WRITE_FAILURES = {"count": 0}


def quarantine_mode() -> str:
    """Read the gate mode from the environment (default: shadow)."""
    raw = os.environ.get(QUARANTINE_ENV, MODE_SHADOW).strip().lower()
    if raw not in _MODES:
        logger.warning(
            "Unknown %s=%r; falling back to shadow", QUARANTINE_ENV, raw
        )
        return MODE_SHADOW
    return raw


def is_quarantined(
    tags: list[str] | None,
    witness_quality: float | None = None,
) -> bool:
    """True when a memory row belongs to the quality quarantine lane.

    The write-time tag is the authority (it respects bypass_fitness for
    system messages); witness_quality is only a fallback when tags are
    unavailable to the caller.
    """
    if tags is not None:
        return LOW_QUALITY_TAG in tags
    if witness_quality is not None:
        return witness_quality < QUALITY_FLOOR
    return False


def is_shard_quarantined(text: str) -> bool:
    """Quarantine predicate for idea shards (no write-time quality tag)."""
    from dharma_swarm.memory import _assess_quality

    return _assess_quality(text) < QUALITY_FLOOR


def record_shadow_receipt(
    *,
    site: str,
    served: int,
    would_be_excluded: int,
    state_dir: Path | None,
) -> None:
    """Append one shadow-mode receipt line; never raises into recall."""
    if served <= 0:
        return
    try:
        base = state_dir or (Path.home() / ".dharma")
        path = base / RECEIPT_RELPATH
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _RECEIPT_MAX_BYTES:
            logger.warning("Quarantine receipt file over size cap; skipping write")
            return
        line = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "site": site,
                "mode": MODE_SHADOW,
                "served": served,
                "would_be_excluded": would_be_excluded,
                # Discriminators so pytest/tooling traffic is separable from
                # organism traffic when reading the shadow denominators.
                "pid": os.getpid(),
                "state": str(base),
            },
            sort_keys=True,
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        RECEIPT_WRITE_FAILURES["count"] += 1
        logger.debug("Quarantine shadow receipt write failed", exc_info=True)
