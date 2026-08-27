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
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"
LOW_ALIGNMENT = 0.4
_HOLON_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")


def _canonical_holon_name(name: str) -> str:
    """Return one canonical registry component or reject it.

    The compass is callable outside the HTTP router, so it must enforce the
    registry-name contract at its own filesystem boundary.  Deriving the
    component with ``re.sub`` also makes the path sanitizer explicit to static
    analysis; equality is required so invalid input is rejected, not renamed.
    """
    if not isinstance(name, str) or _CONTROL_CHARACTER_RE.search(name):
        raise ValueError("holon name contains a control character")
    component = re.sub(r"[^A-Za-z0-9_.-]", "", name)
    if component != name or not _HOLON_NAME_RE.fullmatch(component):
        raise ValueError("holon name is not a canonical registry component")
    return component


def _confined_path(root: Path, *components: str) -> Path:
    """Resolve a candidate and prove it remains under ``root``.

    Resolving before the containment check catches an existing agent-directory
    or signal-file symlink that points outside the configured registry root.
    """
    resolved_root = os.path.realpath(os.fspath(root.expanduser()))
    candidate = os.path.realpath(os.path.join(resolved_root, *components))
    root_prefix = resolved_root if resolved_root.endswith(os.sep) else resolved_root + os.sep
    if not candidate.startswith(root_prefix):
        raise ValueError("holon signal path escapes the agents root")
    return Path(candidate)


def _signal_path(name: str, agents_root: Path | None = None) -> Path:
    component = _canonical_holon_name(name)
    return _confined_path(
        agents_root or AGENTS_ROOT,
        component,
        "compass_signals.jsonl",
    )


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
    try:
        safe_name = _canonical_holon_name(name)
        path = _signal_path(safe_name, agents_root)
    except ValueError:
        # A compass must not become a gate.  Reject unsafe persistence while
        # still returning the non-binding signal to the caller.
        sig["holon"] = "<invalid>"
        logger.warning("[holon] compass signal not persisted: invalid holon identifier or path")
        return sig

    sig["holon"] = safe_name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sig, ensure_ascii=False) + "\n")
    except OSError:
        # Persistence is best-effort and must not interrupt the dialogue path.
        logger.debug("[holon] compass signal persistence failed", exc_info=True)
    if sig["telos_alignment"] < LOW_ALIGNMENT:
        logger.warning(
            "[holon %s] low telos-alignment signal: %.2f (non-binding — compass, not gate)",
            safe_name, sig["telos_alignment"],
        )
    return sig
