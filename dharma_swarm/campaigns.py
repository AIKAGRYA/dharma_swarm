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


def load_active(meta_dir: Path | None = None) -> list[dict[str, Any]]:
    path = _active_path(meta_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, dict) and c.get("campaign_id")]


def save_active(campaigns: list[dict[str, Any]], meta_dir: Path | None = None) -> None:
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
    meta_dir: Path | None = None,
) -> dict[str, Any]:
    """Create (or no-op if exists) an active campaign."""
    existing = load_active(meta_dir)
    if any(c.get("campaign_id") == campaign_id for c in existing):
        return next(c for c in existing if c.get("campaign_id") == campaign_id)

    now = _utc_now_iso()
    record: dict[str, Any] = {
        "campaign_id": campaign_id,
        "title": title or campaign_id,
        "domain": domain,
        "pinned_agents": list(pinned_agents or []),
        "source": source,
        "linked_promise": linked_promise,
        "success_criteria": success_criteria,
        "deadline": deadline,
        "created": now,
        "last_check_in": now,
        "check_in_count": 0,
        "status": "active",
        "progress_markers": [],
    }
    existing.append(record)
    save_active(existing, meta_dir)
    return record


def mark_check_in(
    campaign_id: str,
    agent: str,
    note: str = "",
    meta_dir: Path | None = None,
) -> dict[str, Any] | None:
    campaigns = load_active(meta_dir)
    for c in campaigns:
        if c.get("campaign_id") != campaign_id:
            continue
        now = _utc_now_iso()
        c["last_check_in"] = now
        c["check_in_count"] = int(c.get("check_in_count", 0)) + 1
        markers = list(c.get("progress_markers") or [])
        markers.append({"timestamp": now, "agent": agent, "note": note[:400]})
        c["progress_markers"] = markers[-50:]  # keep last 50
        save_active(campaigns, meta_dir)
        return c
    return None


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
    "create_campaign",
    "mark_check_in",
    "complete_campaign",
    "release_campaign",
    "list_stale",
    "campaign_from_promise",
]
