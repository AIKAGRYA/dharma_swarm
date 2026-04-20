"""Plain JSON helper for campaign manifest state.

The campaign manifest at ``~/.dharma/campaigns/{opp_id}/manifest.json`` is the
*single source of truth* for promotion state of an opportunity through the
6-stage curriculum. It is NOT a payload artifact, so this module is the right
primitive — ``ArtifactManifestStore`` is a sidecar manifest writer for an
existing payload artifact (per ``artifact_manifest.py:117``) and is the wrong
tool for state files.

Atomic semantics:
- Writes go to ``manifest.json.tmp`` then ``os.replace`` onto the target. This
  is crash-safe on POSIX: a partial write cannot leave the target half-updated.
- Reads tolerate missing files (return ``None``); JSON-decode errors are
  surfaced so a corrupted manifest is loud, not silent.

Schema version 1:
  {
    "schema_version": 1,
    "opportunity_id": "...",
    "title": "...",
    "domain": "...",
    "telos_alignment": 0.95,
    "created_at": "ISO",
    "updated_at": "ISO",
    "stages": {
      "scope": {
        "status": "pending|promoted|dispatched|completed|failed|quarantined|abandoned",
        "task_id": "..." | null,
        "promoted_at": "ISO" | null,
        "completed_at": "ISO" | null,
        "artifact_path": "scope.md" | null,
        "retry_count": 0,
        "last_retry_at": null,
        "next_retry_at": null,
        ...
      },
      ...
    },
    "review_logged": false,
    "gate_blocked": false,
    "throttled": false,
    "budget_blocked": false
  }
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAMPAIGN_ROOT = Path.home() / ".dharma" / "campaigns"
SCHEMA_VERSION = 1

# Stage list is the canonical curriculum order. PR1 only promotes ``scope``;
# PR2 adds ``validate``; PR4 wires ``deep_research`` to its own task type;
# PR5 adds ``capability`` and ``mvp``; ``first_artifact`` is deferred to PR7
# because it expects a built artifact (per template at curriculum_engine.py:153),
# not a memo, and so needs a different result contract.
CANONICAL_STAGES: tuple[str, ...] = (
    "scope",
    "validate",
    "deep_research",
    "capability",
    "mvp",
    "first_artifact",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _campaign_dir(opportunity_id: str) -> Path:
    return CAMPAIGN_ROOT / opportunity_id


def manifest_path(opportunity_id: str) -> Path:
    return _campaign_dir(opportunity_id) / "manifest.json"


def read_manifest(opportunity_id: str) -> dict[str, Any] | None:
    """Return the manifest dict, or ``None`` if no manifest exists."""
    path = manifest_path(opportunity_id)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def write_manifest(opportunity_id: str, data: dict[str, Any]) -> Path:
    """Atomically write the manifest. Returns the final path."""
    target = manifest_path(opportunity_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["updated_at"] = _utc_now_iso()
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)
    return target


def init_manifest(
    *,
    opportunity_id: str,
    title: str,
    domain: str,
    telos_alignment: float,
) -> dict[str, Any]:
    """Construct a fresh manifest dict (does not write to disk)."""
    now = _utc_now_iso()
    stages: dict[str, dict[str, Any]] = {
        stage: {
            "status": "pending",
            "task_id": None,
            "promoted_at": None,
            "completed_at": None,
            "artifact_path": None,
            "retry_count": 0,
            "last_retry_at": None,
            "next_retry_at": None,
        }
        for stage in CANONICAL_STAGES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "opportunity_id": opportunity_id,
        "title": title,
        "domain": domain,
        "telos_alignment": float(telos_alignment),
        "created_at": now,
        "updated_at": now,
        "stages": stages,
        "review_logged": False,
        "gate_blocked": False,
        "throttled": False,
        "budget_blocked": False,
    }


def update_stage(
    manifest: dict[str, Any],
    stage: str,
    **fields: Any,
) -> dict[str, Any]:
    """Merge ``fields`` into ``manifest['stages'][stage]`` in place. Returns the
    mutated manifest (for chaining)."""
    if stage not in manifest.get("stages", {}):
        raise KeyError(f"Unknown stage: {stage!r} (valid: {CANONICAL_STAGES})")
    manifest["stages"][stage].update(fields)
    return manifest


def list_campaign_ids() -> set[str]:
    """Return the set of opportunity_ids that have a manifest folder.

    Used by the refill loop (PR6) to derive ``addressed_ids`` from the
    filesystem rather than maintaining a separate index. Filesystem scan is
    the single source of truth.
    """
    if not CAMPAIGN_ROOT.exists():
        return set()
    out: set[str] = set()
    for child in CAMPAIGN_ROOT.iterdir():
        if child.is_dir() and (child / "manifest.json").exists():
            out.add(child.name)
    return out
