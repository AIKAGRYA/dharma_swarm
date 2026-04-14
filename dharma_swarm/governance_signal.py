"""Governance overlay — the binding surface between Shakti executive and dispatch.

The executive (Phase 1) writes allocation weights, opportunity scores, and
state to ``~/.dharma/meta/``. Historically nothing read those artifacts, so
the executive was diagnostic only. This module closes that loop: the
orchestrator and coordination-synthesis paths call into here to convert
executive intelligence into runtime pressure on task selection.

What this module does, and doesn't
----------------------------------

DOES:

* Read ``allocation_weights.json`` and compute per-domain dispatch multipliers
  (clamped by default to ``[0.5, 2.0]`` — hard starvation never overrides
  the invariant that every ready task eventually runs).
* Read optional supplementary governance files
  (``promise_pressure.json``, ``disagreement_quarantine.json``,
  ``challenge_pressure.json``) if the executive has emitted them.
* Fold active campaigns into domain accounting so campaign-pinned work
  isn't starve-boosted twice.
* Stable-sort a list of tasks by their governance multiplier.

DOES NOT:

* Drop tasks. Demotion only.
* Write files. All outputs are return values.
* Touch the EFE/fitness selection logic in ``orchestrator._select_idle_agent``.
* Touch ``dgm_loop.py``.

Activation is guarded by ``DGC_GOVERNANCE_OVERLAY``. When unset or ``"0"``,
``reorder_by_governance`` returns tasks unchanged with an empty reason list,
making this module a no-op in production until explicitly enabled.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.campaigns import load_active as load_active_campaigns
from dharma_swarm.domain_classify import infer_domain
from dharma_swarm.shakti_zeitgeist_executive import DOMAINS

logger = logging.getLogger(__name__)

_DEFAULT_META_DIR = Path.home() / ".dharma" / "meta"
_CACHE_TTL_SECONDS = 30.0
_STALE_AFTER_SECONDS = 600.0  # fall back to neutral if files >10min old
_NEUTRAL_WEIGHT = 1.0 / len(DOMAINS)  # 0.125

# Clamp bounds for the first 48h — loosen only after observation.
_CLAMP_MIN = 0.5
_CLAMP_MAX = 2.0
_DIRECTED_MULTIPLIER = math.inf

_ENV_FLAG = "DGC_GOVERNANCE_OVERLAY"


# ---------------------------------------------------------------------------
# Snapshot dataclass
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GovernanceSnapshot:
    """In-memory view of what the executive has most recently written."""

    per_domain: dict[str, float] = field(default_factory=dict)
    starvation_boosts: dict[str, float] = field(default_factory=dict)
    churn_penalties: dict[str, float] = field(default_factory=dict)
    quarantine_topics: set[str] = field(default_factory=set)
    promise_pressure: dict[str, float] = field(default_factory=dict)
    challenge_multiplier: dict[str, float] = field(default_factory=dict)
    active_campaign_domains: set[str] = field(default_factory=set)
    loaded_at: float = 0.0
    source_mtime: float = 0.0
    is_stale: bool = True

    def domain_weight(self, domain: str) -> float:
        return self.per_domain.get(domain, _NEUTRAL_WEIGHT)


# ---------------------------------------------------------------------------
# Loader — mtime-keyed 30s cache
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {"snap": None, "key": None, "loaded_at": 0.0}


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.warning("governance: failed to parse %s", path)
        return None


def _file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _neutral_snapshot(loaded_at: float, is_stale: bool = True) -> GovernanceSnapshot:
    return GovernanceSnapshot(
        per_domain={d: _NEUTRAL_WEIGHT for d in DOMAINS},
        loaded_at=loaded_at,
        is_stale=is_stale,
    )


def load_governance(meta_dir: Path | None = None, force: bool = False) -> GovernanceSnapshot:
    """Return a current GovernanceSnapshot, using a 30s mtime cache."""
    base = meta_dir or _DEFAULT_META_DIR
    alloc_path = base / "allocation_weights.json"
    quarantine_path = base / "disagreement_quarantine.json"
    promise_path = base / "promise_pressure.json"
    challenge_path = base / "challenge_pressure.json"

    # Cache key: tuple of (path, mtime) for each governance file.
    key = (
        _file_mtime(alloc_path),
        _file_mtime(quarantine_path),
        _file_mtime(promise_path),
        _file_mtime(challenge_path),
    )

    now = time.monotonic()
    if (
        not force
        and _cache["snap"] is not None
        and _cache["key"] == key
        and (now - _cache["loaded_at"]) < _CACHE_TTL_SECONDS
    ):
        return _cache["snap"]  # type: ignore[return-value]

    alloc = _read_json(alloc_path)
    if not isinstance(alloc, dict):
        snap = _neutral_snapshot(loaded_at=now, is_stale=True)
        _cache.update(snap=snap, key=key, loaded_at=now)
        return snap

    # Staleness: weights older than 10min → neutral.
    mtime = _file_mtime(alloc_path)
    file_age = (datetime.now(timezone.utc).timestamp() - mtime) if mtime else 1e9
    if file_age > _STALE_AFTER_SECONDS:
        snap = _neutral_snapshot(loaded_at=now, is_stale=True)
        snap.source_mtime = mtime
        _cache.update(snap=snap, key=key, loaded_at=now)
        return snap

    per_domain = {str(k): float(v) for k, v in (alloc.get("per_domain") or {}).items()}
    starvation = {str(k): float(v) for k, v in (alloc.get("starvation_boosts") or {}).items()}
    churn = {str(k): float(v) for k, v in (alloc.get("churn_penalties") or {}).items()}

    # Fill missing domains with neutral so callers always get a value.
    for d in DOMAINS:
        per_domain.setdefault(d, _NEUTRAL_WEIGHT)

    quarantine_topics: set[str] = set()
    quarantine = _read_json(quarantine_path)
    if isinstance(quarantine, dict):
        topics = quarantine.get("topics") or []
        for t in topics:
            if isinstance(t, str) and t.strip():
                quarantine_topics.add(t.strip().lower())
        for t in quarantine.get("active", []) or []:
            if isinstance(t, dict):
                v = str(t.get("topic", "")).strip().lower()
                if v:
                    quarantine_topics.add(v)
    elif isinstance(quarantine, list):
        for item in quarantine:
            if isinstance(item, str):
                quarantine_topics.add(item.strip().lower())
            elif isinstance(item, dict):
                v = str(item.get("topic", "")).strip().lower()
                if v:
                    quarantine_topics.add(v)

    promise_pressure: dict[str, float] = {}
    prom = _read_json(promise_path)
    if isinstance(prom, dict):
        items = prom.get("promises") or []
    elif isinstance(prom, list):
        items = prom
    else:
        items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        score = float(item.get("urgency", 0.0) or 0.0)
        if pid and score > 0:
            promise_pressure[pid] = score

    challenge_multiplier: dict[str, float] = {}
    challenge = _read_json(challenge_path)
    if isinstance(challenge, dict):
        per = challenge.get("per_domain") or {}
        for k, v in per.items():
            try:
                challenge_multiplier[str(k)] = float(v)
            except Exception:
                pass

    # Active-campaign domain accounting — prevents double-starve.
    active_campaign_domains: set[str] = set()
    try:
        for c in load_active_campaigns(base):
            d = c.get("domain")
            if isinstance(d, str) and d in DOMAINS:
                active_campaign_domains.add(d)
    except Exception:
        pass

    snap = GovernanceSnapshot(
        per_domain=per_domain,
        starvation_boosts=starvation,
        churn_penalties=churn,
        quarantine_topics=quarantine_topics,
        promise_pressure=promise_pressure,
        challenge_multiplier=challenge_multiplier,
        active_campaign_domains=active_campaign_domains,
        loaded_at=now,
        source_mtime=mtime,
        is_stale=False,
    )
    _cache.update(snap=snap, key=key, loaded_at=now)
    return snap


def invalidate_cache() -> None:
    _cache.update(snap=None, key=None, loaded_at=0.0)


# ---------------------------------------------------------------------------
# Multiplier + reorder
# ---------------------------------------------------------------------------


def _task_text_lower(task: Any) -> str:
    parts = [
        str(getattr(task, "title", "") or ""),
        str(getattr(task, "description", "") or ""),
    ]
    meta = getattr(task, "metadata", None)
    if isinstance(meta, dict):
        parts.append(str(meta.get("topic", "") or ""))
        parts.append(str(meta.get("campaign_id", "") or ""))
    return " ".join(parts).lower()


def _is_quarantined(task: Any, quarantine: set[str]) -> bool:
    if not quarantine:
        return False
    text = _task_text_lower(task)
    return any(topic in text for topic in quarantine if topic)


def _metadata_get(task: Any, key: str, default: Any = None) -> Any:
    meta = getattr(task, "metadata", None)
    if not isinstance(meta, dict):
        return default
    return meta.get(key, default)


def governance_multiplier(
    task: Any,
    snap: GovernanceSnapshot,
) -> tuple[float, list[str]]:
    """Compute a (multiplier, reasons) pair for a task.

    Higher multiplier = higher priority. 1.0 = neutral.  Quarantine yields 0.0
    (caller may interpret as skip). ``"directed"`` domain yields ``+inf``.
    """
    reasons: list[str] = []
    domain = infer_domain(task)

    # Directed override — operator authority bypasses governance.
    if domain == "directed" or _metadata_get(task, "directed") is True:
        reasons.append("directed_override")
        return _DIRECTED_MULTIPLIER, reasons

    if _is_quarantined(task, snap.quarantine_topics):
        reasons.append("quarantine_skip")
        return 0.0, reasons

    # Base multiplier from allocation weight.
    weight = snap.domain_weight(domain)
    base = weight / _NEUTRAL_WEIGHT  # 0.125 → 1.0
    multiplier = base
    reasons.append(f"alloc({domain})={base:.2f}")

    boost = snap.starvation_boosts.get(domain, 0.0)
    if boost > 0:
        # Starvation boost ramped only if no active campaign already covers it.
        if domain in snap.active_campaign_domains:
            reasons.append("campaign_active_no_starve_boost")
        else:
            multiplier += boost * 4.0  # convert weight-units to multiplier-units
            reasons.append(f"starv(+{boost * 4.0:.2f})")

    penalty = snap.churn_penalties.get(domain, 0.0)
    if penalty > 0:
        multiplier -= penalty * 2.0
        reasons.append(f"churn(-{penalty * 2.0:.2f})")

    challenge = snap.challenge_multiplier.get(domain, 0.0)
    if challenge > 0:
        multiplier += challenge
        reasons.append(f"challenge(+{challenge:.2f})")

    linked_promise = _metadata_get(task, "linked_promise")
    if isinstance(linked_promise, str):
        pressure = snap.promise_pressure.get(linked_promise, 0.0)
        if pressure > 0:
            multiplier += pressure
            reasons.append(f"promise(+{pressure:.2f})")

    # Clamp for first 48h.
    clamped = max(_CLAMP_MIN, min(_CLAMP_MAX, multiplier))
    if clamped != multiplier:
        reasons.append(f"clamped({_CLAMP_MIN}-{_CLAMP_MAX})")
    return clamped, reasons


def is_overlay_enabled() -> bool:
    return os.environ.get(_ENV_FLAG, "0").strip() not in ("", "0", "false", "False", "no")


def reorder_by_governance(
    tasks: Iterable[Any],
    snap: GovernanceSnapshot | None = None,
    *,
    enabled: bool | None = None,
) -> tuple[list[Any], list[str]]:
    """Stable-sort tasks by governance multiplier (descending).

    Returns (reordered_tasks, reasons_log).  When the overlay flag is off,
    returns tasks unchanged with an empty reason list — callers can wire the
    call unconditionally and rely on the flag to gate runtime behavior.
    """
    tasks_list = list(tasks)
    if enabled is False or (enabled is None and not is_overlay_enabled()):
        return tasks_list, []
    if not tasks_list:
        return tasks_list, []

    if snap is None:
        snap = load_governance()

    scored: list[tuple[float, int, Any, list[str]]] = []
    reasons_all: list[str] = []
    for i, t in enumerate(tasks_list):
        mult, reasons = governance_multiplier(t, snap)
        task_id = str(getattr(t, "id", i))
        if mult == 0.0:
            reasons_all.append(f"skip({task_id}):quarantine")
        elif mult == _DIRECTED_MULTIPLIER:
            reasons_all.append(f"directed({task_id})")
        elif any(r for r in reasons if not r.startswith("alloc(")):
            # Only log non-trivial reorders.
            reasons_all.append(f"{task_id}:{'+'.join(reasons)}({mult:.2f})")
        scored.append((mult, i, t, reasons))

    # Quarantined (multiplier 0) go to the back but are NOT dropped.
    def sort_key(row: tuple[float, int, Any, list[str]]) -> tuple[float, int]:
        mult, i, _, _ = row
        # Sort by -multiplier first (highest priority first); stable in i.
        if mult == _DIRECTED_MULTIPLIER:
            primary = -1e18
        else:
            primary = -mult
        return (primary, i)

    scored.sort(key=sort_key)
    reordered = [row[2] for row in scored]
    return reordered, reasons_all


__all__ = [
    "GovernanceSnapshot",
    "load_governance",
    "invalidate_cache",
    "governance_multiplier",
    "reorder_by_governance",
    "is_overlay_enabled",
]
