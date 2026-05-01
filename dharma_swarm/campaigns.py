"""Durable campaign memory.

Campaigns are the organism's way of binding strategic intent across many
wake cycles, many agents, and sometimes many days.  A campaign is not a
transient task — it is first-class memory that the executive re-reads every
cycle and that pinned agents check in to.

Storage
-------

* ``~/.dharma/meta/active_campaigns.json`` — list[dict] of active campaigns.
  Rewritten atomically on every mutation.
* ``~/.dharma/meta/campaign_history.jsonl`` — append-only, one JSON record per
  line for each terminal transition (completed, abandoned, expired).

The executive already writes ``active_campaigns.json`` as ``[]`` on every
emission cycle (see ``shakti_zeitgeist_executive._emit_artifacts``).  Phase A
patches that path to preserve existing content instead of overwriting with
``[]``; until that patch lands, this module defends itself by merging with
what's on disk at write time.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_META_DIR = Path.home() / ".dharma" / "meta"
_ACTIVE_FILENAME = "active_campaigns.json"
_HISTORY_FILENAME = "campaign_history.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meta_dir(meta_dir: Path | None = None) -> Path:
    return meta_dir or _DEFAULT_META_DIR


def _active_path(meta_dir: Path | None = None) -> Path:
    return _meta_dir(meta_dir) / _ACTIVE_FILENAME


def _history_path(meta_dir: Path | None = None) -> Path:
    return _meta_dir(meta_dir) / _HISTORY_FILENAME


def promise_id_from_text(text: str) -> str:
    """Stable id for a heartbeat promise line.

    Hashes the stripped lowercase text so the same promise produces the same
    id on every run. Used by ``dgc promise:pin <id> <agent>``.
    """
    norm = (text or "").strip().lower()
    return "promise_" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]


def _normalize_campaign_record(
    record: dict[str, Any],
    *,
    envelope_primary: str = "",
) -> dict[str, Any] | None:
    campaign_id = str(
        record.get("campaign_id")
        or record.get("id")
        or record.get("name")
        or "",
    ).strip()
    if not campaign_id:
        return None

    normalized = dict(record)
    normalized["campaign_id"] = campaign_id
    normalized["status"] = str(normalized.get("status") or "active").strip() or "active"

    if not str(normalized.get("title") or "").strip():
        normalized["title"] = (
            str(normalized.get("goal") or "").strip()
            or str(normalized.get("name") or "").strip()
            or campaign_id
        )

    if not str(normalized.get("success_criteria") or "").strip():
        normalized["success_criteria"] = (
            str(normalized.get("goal") or "").strip()
            or str(normalized.get("why_now") or "").strip()
            or str(normalized.get("artifact_path") or "").strip()
            or str(normalized.get("title") or "").strip()
        )

    if not str(normalized.get("artifact_path") or "").strip():
        artifact_contract = str(normalized.get("artifact_contract") or "").strip()
        if artifact_contract:
            normalized["artifact_path"] = artifact_contract

    pinned_agents = normalized.get("pinned_agents")
    if isinstance(pinned_agents, list):
        normalized["pinned_agents"] = [str(agent) for agent in pinned_agents if str(agent).strip()]
    else:
        preferred_agents = normalized.get("preferred_agents")
        if isinstance(preferred_agents, list):
            normalized["pinned_agents"] = [str(agent) for agent in preferred_agents if str(agent).strip()]
        else:
            normalized["pinned_agents"] = []

    created = str(normalized.get("created") or "").strip()
    last_updated = str(
        normalized.get("last_check_in")
        or normalized.get("last_updated")
        or "",
    ).strip()
    if not created:
        normalized["created"] = last_updated or ""
    if not str(normalized.get("last_check_in") or "").strip():
        normalized["last_check_in"] = last_updated or str(normalized.get("created") or "").strip()

    if normalized.get("check_in_count") is None:
        normalized["check_in_count"] = 0

    if not isinstance(normalized.get("progress_markers"), list):
        normalized["progress_markers"] = []

    if normalized.get("primary") is None:
        priority = str(normalized.get("priority") or "").strip().lower()
        normalized["primary"] = bool(
            priority == "primary"
            or (envelope_primary and campaign_id == envelope_primary)
        )
    else:
        normalized["primary"] = bool(normalized.get("primary"))

    return normalized


def load_active(meta_dir: Path | None = None) -> list[dict[str, Any]]:
    path = _active_path(meta_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []

    envelope_primary = ""
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        candidates = data.get("campaigns")
        envelope_primary = str(data.get("primary_campaign") or "").strip()
    else:
        return []

    if not isinstance(candidates, list):
        return []

    active: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        normalized = _normalize_campaign_record(
            candidate,
            envelope_primary=envelope_primary,
        )
        if normalized is not None:
            active.append(normalized)

    _normalize_primary_flags(active)
    return active


def save_active(campaigns: list[dict[str, Any]], meta_dir: Path | None = None) -> None:
    _normalize_primary_flags(campaigns)
    path = _active_path(meta_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(campaigns, indent=2, default=str) + "\n")
    tmp.replace(path)


def append_history(record: dict[str, Any], meta_dir: Path | None = None) -> None:
    path = _history_path(meta_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def find_campaign(campaign_id: str, meta_dir: Path | None = None) -> dict[str, Any] | None:
    for c in load_active(meta_dir):
        if c.get("campaign_id") == campaign_id:
            return c
    return None


def find_campaign_domain(campaign_id: str, meta_dir: Path | None = None) -> str | None:
    c = find_campaign(campaign_id, meta_dir)
    return c.get("domain") if c else None


def find_by_agent(agent_name: str, meta_dir: Path | None = None) -> list[dict[str, Any]]:
    return [
        c for c in load_active(meta_dir)
        if agent_name in (c.get("pinned_agents") or [])
    ]


def active_primary(meta_dir: Path | None = None) -> dict[str, Any] | None:
    """Return the active primary campaign, or the earliest-created active campaign
    as a soft-primary proxy.

    Phase 1 implementation: if any active campaign has ``primary: true``, return it.
    Otherwise return the earliest-created active campaign (soft-primary). Phase 4
    will introduce the ``primary`` field as authoritative with a slot cap of 1.

    This helper is what non-pinned agents check when deciding how to self-task.
    """
    active = [c for c in load_active(meta_dir) if c.get("status", "active") == "active"]
    if not active:
        return None
    # Explicit primary wins (Phase 4 field)
    explicit = [c for c in active if c.get("primary") is True]
    if explicit:
        explicit.sort(key=lambda c: str(c.get("created", "")))
        return explicit[0]
    # Soft-primary: earliest-created active
    active.sort(key=lambda c: str(c.get("created", "")))
    return active[0]


def _normalize_primary_flags(campaigns: list[dict[str, Any]]) -> None:
    """Ensure at most one active campaign is marked primary.

    If none is explicitly primary, elect the earliest-created active campaign.
    """
    active_indexes = [
        i for i, c in enumerate(campaigns)
        if isinstance(c, dict) and c.get("status", "active") == "active"
    ]
    if not active_indexes:
        for c in campaigns:
            if isinstance(c, dict):
                c["primary"] = False
        return

    explicit_indexes = [i for i in active_indexes if campaigns[i].get("primary") is True]
    if explicit_indexes:
        winner = min(explicit_indexes, key=lambda i: str(campaigns[i].get("created", "")))
    else:
        winner = min(active_indexes, key=lambda i: str(campaigns[i].get("created", "")))

    for i, c in enumerate(campaigns):
        if not isinstance(c, dict):
            continue
        c["primary"] = bool(i == winner and c.get("status", "active") == "active")


def set_primary(campaign_id: str, meta_dir: Path | None = None) -> dict[str, Any] | None:
    """Mark exactly one active campaign as primary."""
    campaigns = load_active(meta_dir)
    target: dict[str, Any] | None = None
    for c in campaigns:
        if c.get("campaign_id") == campaign_id and c.get("status", "active") == "active":
            c["primary"] = True
            target = c
        else:
            c["primary"] = False
    if target is None:
        return None
    save_active(campaigns, meta_dir)
    return target


def create_campaign(
    campaign_id: str,
    domain: str,
    pinned_agents: list[str],
    *,
    title: str | None = None,
    deadline: str | None = None,
    success_criteria: str = "",
    source: str = "operator",
    linked_promise: str | None = None,
    primary: bool | None = None,
    artifact_path: str | None = None,
    meta_dir: Path | None = None,
) -> dict[str, Any]:
    """Create (or no-op if exists) an active campaign."""
    existing = load_active(meta_dir)
    if any(c.get("campaign_id") == campaign_id for c in existing):
        existing_record = next(c for c in existing if c.get("campaign_id") == campaign_id)
        updated = False
        if title and not str(existing_record.get("title") or "").strip():
            existing_record["title"] = title
            updated = True
        if success_criteria and not str(existing_record.get("success_criteria") or "").strip():
            existing_record["success_criteria"] = success_criteria
            updated = True
        resolved_artifact_path = artifact_path or f"~/.dharma/shared/campaigns/{campaign_id}.md"
        if resolved_artifact_path and not str(existing_record.get("artifact_path") or "").strip():
            existing_record["artifact_path"] = resolved_artifact_path
            updated = True
        if updated:
            save_active(existing, meta_dir)
        if primary is True:
            set_primary(campaign_id, meta_dir)
            return find_campaign(campaign_id, meta_dir)
        return existing_record

    now = _utc_now_iso()
    has_active_primary = any(
        c.get("status", "active") == "active" and c.get("primary") is True
        for c in existing
    )
    record: dict[str, Any] = {
        "campaign_id": campaign_id,
        "title": title or campaign_id,
        "domain": domain,
        "pinned_agents": list(pinned_agents or []),
        "source": source,
        "linked_promise": linked_promise,
        "artifact_path": artifact_path or f"~/.dharma/shared/campaigns/{campaign_id}.md",
        "success_criteria": success_criteria,
        "deadline": deadline,
        "created": now,
        "last_check_in": now,
        "check_in_count": 0,
        "status": "active",
        "primary": bool(primary) if primary is not None else (not has_active_primary),
        "progress_markers": [],
    }
    existing.append(record)
    save_active(existing, meta_dir)
    return record


def _append_progress_marker(
    campaign: dict[str, Any],
    *,
    marker: dict[str, Any],
) -> None:
    markers = list(campaign.get("progress_markers") or [])
    markers.append(marker)
    campaign["progress_markers"] = markers[-50:]


def mark_check_in(
    campaign_id: str,
    agent: str,
    note: str = "",
    *,
    extra: dict[str, Any] | None = None,
    meta_dir: Path | None = None,
) -> dict[str, Any] | None:
    campaigns = load_active(meta_dir)
    for c in campaigns:
        if c.get("campaign_id") != campaign_id:
            continue
        now = _utc_now_iso()
        c["last_check_in"] = now
        c["check_in_count"] = int(c.get("check_in_count", 0)) + 1
        marker = {
            "timestamp": now,
            "agent": agent,
            "note": note[:400],
        }
        if isinstance(extra, dict):
            marker.update(extra)
        _append_progress_marker(c, marker=marker)
        save_active(campaigns, meta_dir)
        return c
    return None


def mark_task_check_in(
    campaign_id: str,
    *,
    task_id: str,
    task_title: str,
    task_status: str,
    agent: str,
    note: str = "",
    meta_dir: Path | None = None,
) -> dict[str, Any] | None:
    status = str(task_status or "").strip().lower() or "unknown"
    task_label = str(task_title or task_id or "task").strip()[:200]
    detail = str(note or "").strip().replace("\n", " ")
    summary = f"{status}: {task_label}"
    if detail:
        summary = f"{summary} — {detail[:280]}"
    return mark_check_in(
        campaign_id,
        agent,
        note=summary,
        extra={
            "source": "task_board",
            "task_id": str(task_id or "").strip(),
            "task_title": task_label,
            "task_status": status,
        },
        meta_dir=meta_dir,
    )


def complete_campaign(
    campaign_id: str,
    outcome: str = "",
    status: str = "completed",
    meta_dir: Path | None = None,
) -> dict[str, Any] | None:
    campaigns = load_active(meta_dir)
    for i, c in enumerate(campaigns):
        if c.get("campaign_id") != campaign_id:
            continue
        c["status"] = status
        c["closed"] = _utc_now_iso()
        c["outcome"] = outcome
        append_history(c, meta_dir)
        campaigns.pop(i)
        save_active(campaigns, meta_dir)
        return c
    return None


def release_campaign(
    campaign_id: str,
    agent: str | None = None,
    meta_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Remove a single agent or close the campaign entirely if no agents left."""
    campaigns = load_active(meta_dir)
    for c in campaigns:
        if c.get("campaign_id") != campaign_id:
            continue
        if agent is None:
            return complete_campaign(
                campaign_id, outcome="released by operator",
                status="abandoned", meta_dir=meta_dir,
            )
        pinned = [a for a in (c.get("pinned_agents") or []) if a != agent]
        c["pinned_agents"] = pinned
        save_active(campaigns, meta_dir)
        if not pinned:
            return complete_campaign(
                campaign_id, outcome="last agent released",
                status="abandoned", meta_dir=meta_dir,
            )
        return c
    return None


def list_stale(
    executive_interval_s: float = 2700.0,
    staleness_factor: float = 2.0,
    meta_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Active campaigns whose last_check_in is older than factor * interval."""
    now = datetime.now(timezone.utc)
    stale: list[dict[str, Any]] = []
    for c in load_active(meta_dir):
        ts_raw = c.get("last_check_in") or c.get("created")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except Exception:
            continue
        elapsed = (now - ts).total_seconds()
        if elapsed >= executive_interval_s * staleness_factor:
            stale.append({**c, "elapsed_seconds": round(elapsed, 0)})
    return stale


def campaign_from_promise(
    promise_text: str,
    agent: str,
    domain: str,
    *,
    deadline: str | None = None,
    meta_dir: Path | None = None,
) -> dict[str, Any]:
    """Shortcut: create a campaign from a heartbeat promise string."""
    pid = promise_id_from_text(promise_text)
    campaign_id = pid.replace("promise_", "camp_")
    return create_campaign(
        campaign_id=campaign_id,
        domain=domain,
        pinned_agents=[agent],
        title=promise_text[:120],
        deadline=deadline,
        success_criteria=promise_text,
        source="promise",
        linked_promise=pid,
        meta_dir=meta_dir,
    )


__all__ = [
    "promise_id_from_text",
    "load_active",
    "save_active",
    "append_history",
    "find_campaign",
    "find_campaign_domain",
    "find_by_agent",
    "active_primary",
    "set_primary",
    "create_campaign",
    "mark_check_in",
    "mark_task_check_in",
    "complete_campaign",
    "release_campaign",
    "list_stale",
    "campaign_from_promise",
]
