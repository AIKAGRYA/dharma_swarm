"""Read-only holon compass (Step 3a) — a NON-BINDING telos-alignment SIGNAL.

NOT a gate. NOT enforcement. NOT a PDP. After an exchange, score it against telos via the
existing ``ThinkodynamicScorer`` and append the signal to a per-holon log (+ warn on low
alignment). The holon is *pulled* toward telos by visibility, never *gated* — honest, and
aligned with the 2026-05-30 trust→compass pivot. The real PDP/PEP fence (Step 3b) is
deferred until a tripwire trips (real money / irreversibility / real autonomy).

⚠️ NEVER label this "enforced governance" — it cannot refuse. That is the exact mislabelling
the 2026-06-05 hostile safety audit flagged. It is a compass, not a fence.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"
LOW_ALIGNMENT = 0.4


def _signal_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "compass_signals.jsonl"


def score_exchange(user_message: str, holon_reply: str) -> dict:
    """Score one exchange against telos (pure, non-binding). Returns the signal dict."""
    from dharma_swarm.thinkodynamic_scorer import ThinkodynamicScorer

    score = ThinkodynamicScorer().score_text(prompt=user_message, response=holon_reply)
    return {
        "telos_alignment": round(float(score.telos_alignment), 4),
        "witness_quality": round(float(score.witness_quality), 4),
        "at": datetime.now(timezone.utc).isoformat(),
    }


def log_signal(name: str, user_message: str, holon_reply: str, agents_root: Path | None = None) -> dict:
    """Append a non-binding telos signal for an exchange. Warns on low alignment. NEVER blocks/raises.

    Returns the signal dict (so callers can surface it), but a holon is never *stopped* by it —
    that is the difference between a compass (this) and a gate (Step 3b).
    """
    sig = score_exchange(user_message, holon_reply)
    sig["holon"] = name
    path = _signal_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sig, ensure_ascii=False) + "\n")
    if sig["telos_alignment"] < LOW_ALIGNMENT:
        logger.warning(
            "[holon %s] low telos-alignment signal: %.2f (non-binding — compass, not gate)",
            name, sig["telos_alignment"],
        )
    return sig
