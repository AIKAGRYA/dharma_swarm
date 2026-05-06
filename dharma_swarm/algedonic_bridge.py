"""Explicit bridge to the algedonic channel for non-organism callers.

WHY THIS EXISTS

``AlgedonicChannel.fire(signal)`` (vsm_channels.py:410) only invokes callbacks
registered on *that specific channel instance*. Live registration happens on
the running organism/swarm at ``organism.py:255`` and ``swarm.py:444`` — so a
fresh channel object created in a cron handler context will never reach
``swarm._algedonic_handler`` (the function that writes the jsonl, escalates
to EMERGENCY_HOLD, and pings the dashboard).

Callers like the cron-driven ``opportunity_dispatcher`` cannot rely on the
swarm's in-process channel being reachable. This bridge gives them a single
entrypoint that:

1. ALWAYS writes the signal to ``~/.dharma/algedonic_signals.jsonl`` directly,
   matching the schema at ``orchestrator.py:1698`` (``kind``, ``severity``,
   ``value``, ``action``, ``timestamp`` (unix epoch float)).
2. ALWAYS writes a witness mirror at
   ``~/.dharma/witness/{date}/{source}_signal.jsonl`` for operator audit.
3. Tries to resolve the live organism singleton via
   ``dharma_swarm.organism.get_organism``. If present, calls
   ``organism.algedonic.fire(signal)`` so registered callbacks (including
   ``swarm._algedonic_handler``) actually fire.
4. Independently of the live handler, if this signal is severity=="critical"
   AND the prior 2 criticals are within a 1h window, writes
   ``~/.dharma/EMERGENCY_HOLD`` — matching the escalation behavior at
   ``swarm.py:1467`` so the system halts even when the dispatcher cannot
   reach the swarm.

The result includes ``routed_to_live_handler`` so callers can tell whether
the in-process channel was actually invoked or only the on-disk fallback ran.

DOES NOT CREATE A NEW SCHEDULER OR EVENT BUS. Just plumbing.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

DHARMA_HOME = dharma_state_dir()
SIGNALS_PATH = DHARMA_HOME / "algedonic_signals.jsonl"
WITNESS_DIR = DHARMA_HOME / "witness"
EMERGENCY_HOLD_PATH = DHARMA_HOME / "EMERGENCY_HOLD"

# Window in which 3 criticals trigger an EMERGENCY_HOLD marker. Matches
# the spirit of swarm.py:1467 (which counts in-process criticals).
CRITICAL_WINDOW_SECONDS = 3600

VALID_SEVERITIES: frozenset[str] = frozenset({"warning", "critical", "emergency"})


@dataclass
class SignalResult:
    signal_id: str
    severity: str
    kind: str
    timestamp: float
    routed_to_live_handler: bool
    jsonl_written: bool
    witness_written: bool
    emergency_hold_written: bool
    error: str | None = None


def _normalize_severity(severity: str) -> str:
    sev = (severity or "").strip().lower()
    if sev not in VALID_SEVERITIES:
        # Don't silently downgrade; record what we got but log so the caller
        # sees they passed garbage. Default to "warning" so the signal still
        # lands.
        logger.warning("unknown severity %r — coercing to 'warning'", severity)
        return "warning"
    return sev


def _write_signals_jsonl(payload: dict[str, Any]) -> bool:
    """Append to ~/.dharma/algedonic_signals.jsonl. Returns True on success."""
    try:
        SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SIGNALS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except Exception:
        logger.exception("failed to append to algedonic_signals.jsonl")
        return False


def _write_witness(source: str, payload: dict[str, Any]) -> bool:
    """Append to ~/.dharma/witness/{date}/{source}_signal.jsonl."""
    try:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        wpath = WITNESS_DIR / date / f"{source}_signal.jsonl"
        wpath.parent.mkdir(parents=True, exist_ok=True)
        with wpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except Exception:
        logger.exception("failed to append to witness signal log")
        return False


def _count_recent_criticals(now_ts: float, window_seconds: int = CRITICAL_WINDOW_SECONDS) -> int:
    """Count criticals in the last ``window_seconds`` from the signals jsonl.
    Returns 0 if the file is missing or unreadable. Best-effort scan; we
    don't index — for the dispatcher's volume this is fine."""
    if not SIGNALS_PATH.exists():
        return 0
    threshold = now_ts - window_seconds
    count = 0
    try:
        for raw in SIGNALS_PATH.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if str(row.get("severity") or "").lower() != "critical":
                continue
            try:
                ts = float(row.get("timestamp") or 0.0)
            except (TypeError, ValueError):
                continue
            if ts >= threshold:
                count += 1
    except Exception:
        logger.exception("failed to scan algedonic_signals.jsonl for criticals")
    return count


def _maybe_write_emergency_hold(severity: str, payload: dict[str, Any]) -> bool:
    """If this signal is the third critical in the last hour, write the
    EMERGENCY_HOLD marker. The marker mirrors swarm.py:1467 so the system
    halts even when the in-process algedonic handler is not reachable.

    Returns True iff the marker was newly written by this call.
    """
    if severity != "critical":
        return False
    # ``_count_recent_criticals`` includes the just-written current signal.
    now = float(payload.get("timestamp") or time.time())
    count = _count_recent_criticals(now_ts=now)
    if count < 3:
        return False
    if EMERGENCY_HOLD_PATH.exists():
        # Already held — don't rewrite (preserve original timestamp).
        return False
    try:
        EMERGENCY_HOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
        EMERGENCY_HOLD_PATH.write_text(
            json.dumps({
                "held_at": datetime.now(timezone.utc).isoformat(),
                "reason": "algedonic_bridge: 3 criticals in 1h window",
                "trigger_signal_id": payload.get("signal_id"),
                "trigger_kind": payload.get("kind"),
                "trigger_action": payload.get("action"),
            }, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        logger.exception("failed to write EMERGENCY_HOLD marker")
        return False


def _try_route_to_live_organism(
    *,
    severity: str, kind: str, action: str, description: str, context: dict[str, Any],
) -> bool:
    """Attempt to call ``organism.algedonic.fire(signal)`` on the live
    organism singleton. Returns True iff the call actually ran.

    Failure modes (each returns False without raising):
    - module import error
    - organism singleton not registered
    - fire() raised
    """
    try:
        from dharma_swarm.organism import get_organism
    except Exception:
        logger.debug("organism module not importable", exc_info=True)
        return False
    try:
        org = get_organism()
    except Exception:
        logger.debug("get_organism raised", exc_info=True)
        return False
    if org is None:
        return False
    channel = getattr(org, "algedonic", None)
    if channel is None:
        return False
    try:
        from dharma_swarm.vsm_channels import AlgedonicSignal
        signal = AlgedonicSignal(
            severity=severity if severity != "warning" else "warning",
            source_system="S4",  # cron-driven dispatcher monitors environment
            title=f"{kind}: {action}"[:200],
            description=description or kind,
            recommended_action=str(context.get("recommended_action") or ""),
            context=context,
        )
    except Exception:
        logger.debug("AlgedonicSignal construction failed", exc_info=True)
        return False
    try:
        # fire() is async. If a loop is currently running (inside an async
        # caller), schedule on it. Otherwise run a fresh one.
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None:
            asyncio.ensure_future(channel.fire(signal))
        else:
            asyncio.run(channel.fire(signal))
    except Exception:
        logger.exception("organism.algedonic.fire raised")
        return False
    return True


def fire_signal(
    *,
    kind: str,
    severity: str,
    action: str,
    value: float | int | str = 0,
    description: str = "",
    source: str = "opportunity_dispatcher",
    context: dict[str, Any] | None = None,
) -> SignalResult:
    """Fire an algedonic signal through the bridge.

    Side effects (in order, each independent):
    1. Append signal to ``~/.dharma/algedonic_signals.jsonl`` (matches
       orchestrator.py:1698 schema for ``swarm._algedonic_handler`` consumers).
    2. Append witness mirror to
       ``~/.dharma/witness/{date}/{source}_signal.jsonl``.
    3. If a live organism singleton is present, route to its in-process
       algedonic channel so registered callbacks fire.
    4. If this is the third ``critical`` within the last hour AND the
       EMERGENCY_HOLD marker is not already present, write it.

    Returns a SignalResult describing what actually happened — callers can
    use ``routed_to_live_handler`` to see whether the in-process channel was
    invoked or only the on-disk fallback ran.
    """
    severity = _normalize_severity(severity)
    ctx = dict(context or {})
    sig_id = uuid.uuid4().hex[:16]
    ts = time.time()
    payload = {
        # Schema mirrors orchestrator.py:1698 — kind/severity/value/action/timestamp.
        "kind": kind,
        "severity": severity,
        "value": value,
        "action": action,
        "timestamp": ts,
        # Bridge-specific fields (consumers MUST tolerate extras).
        "signal_id": sig_id,
        "source": source,
        "description": description,
        "context": ctx,
    }

    jsonl_ok = _write_signals_jsonl(payload)
    witness_ok = _write_witness(source, payload)
    routed = _try_route_to_live_organism(
        severity=severity, kind=kind, action=action,
        description=description, context=ctx,
    )
    hold_written = False
    if jsonl_ok:
        # Only consider escalation if the jsonl write succeeded — otherwise
        # the count won't include the current signal and we'd undercount.
        hold_written = _maybe_write_emergency_hold(severity, payload)

    return SignalResult(
        signal_id=sig_id,
        severity=severity,
        kind=kind,
        timestamp=ts,
        routed_to_live_handler=routed,
        jsonl_written=jsonl_ok,
        witness_written=witness_ok,
        emergency_hold_written=hold_written,
    )
