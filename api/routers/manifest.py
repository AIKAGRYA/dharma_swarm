"""Manifest Health API — declared-vs-observed comparison + repo SSoT views.

GET /api/manifest/health          → full health report (all sections)
GET /api/manifest/summary         → counts only (live / degraded / broken / stub)
GET /api/manifest/entity/{id}     → single entity detail
GET /api/manifest/active-track    → ACTIVE_TRACK.yaml parsed (id, name, status, next_items, ttl)
GET /api/manifest/recent-commits  → recent commits on current branch (git log)
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manifest", tags=["manifest"])

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _get_report() -> dict[str, Any]:
    from dharma_swarm.manifest_health import build_health_report
    return build_health_report()


@router.get("/health")
async def manifest_health() -> ApiResponse:
    """Full manifest health report with all sections and checks."""
    try:
        report = _get_report()
        if "error" in report and report["error"]:
            return ApiResponse(data=report, error=report["error"])
        return ApiResponse(data=report)
    except Exception as e:
        logger.exception("manifest/health failed")
        return ApiResponse(data=None, error=str(e))


@router.get("/summary")
async def manifest_summary() -> ApiResponse:
    """Lightweight summary: counts by observed status."""
    try:
        report = _get_report()
        return ApiResponse(data={
            "manifest_version": report.get("manifest_version"),
            "last_updated": report.get("last_updated"),
            "summary": report.get("summary", {}),
        })
    except Exception as e:
        logger.exception("manifest/summary failed")
        return ApiResponse(data=None, error=str(e))


@router.get("/entity/{entity_id}")
async def manifest_entity(entity_id: str) -> ApiResponse:
    """Single entity health detail by ID."""
    try:
        report = _get_report()
        for section in report.get("sections", []):
            for entity in section.get("entities", []):
                if entity["id"] == entity_id:
                    return ApiResponse(data=entity)
        raise HTTPException(status_code=404, detail=f"entity '{entity_id}' not found in manifest")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("manifest/entity failed")
        return ApiResponse(data=None, error=str(e))


def _parse_active_track() -> dict[str, Any]:
    """Parse docs/governance/ACTIVE_TRACK.yaml using PyYAML.

    Returns a flat projection of the active_track block: id, name, status,
    verified_at, ttl_days, owner, description (first line only — body block
    can be long), completion_criteria (list of id+kind), non_goals, and the
    raw active_track dict for callers that want everything.
    """
    track_path = _REPO_ROOT / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    if not track_path.exists():
        return {"error": "ACTIVE_TRACK.yaml not found", "path": str(track_path)}
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(track_path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        return {"error": f"yaml parse failed: {e}"}
    track = doc.get("active_track") or {}
    description = track.get("description", "") or ""
    desc_short = description.strip().splitlines()[0] if description.strip() else None
    criteria = track.get("completion_criteria") or []
    completion_brief = [
        {"id": c.get("id"), "kind": c.get("kind")}
        for c in criteria if isinstance(c, dict)
    ]
    return {
        "id": track.get("id"),
        "name": track.get("name"),
        "status": track.get("status"),
        "verified_at": str(track.get("verified_at") or "") or None,
        "ttl_days": track.get("ttl_days"),
        "owner": track.get("owner"),
        "description": desc_short,
        "surfaces_count": len(track.get("surfaces") or []),
        "completion_criteria_count": len(completion_brief),
        "completion_criteria": completion_brief,
        "non_goals": track.get("non_goals") or [],
        "companion_manifest": track.get("companion_manifest"),
    }


@router.get("/active-track")
async def active_track() -> ApiResponse:
    """Current ACTIVE_TRACK.yaml parsed — id, status, next_items, TTL."""
    try:
        return ApiResponse(data=_parse_active_track())
    except Exception as e:
        logger.exception("manifest/active-track failed")
        return ApiResponse(data=None, error=str(e))


def _git_recent_commits(limit: int = 20) -> dict[str, Any]:
    """Run `git log` on the repo root and parse into structured rows."""
    fmt = "%H%x1f%h%x1f%an%x1f%ar%x1f%s"
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", f"--pretty=format:{fmt}"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        return {"error": f"git log failed: {exc.stderr}", "commits": [], "branch": None}
    except FileNotFoundError:
        return {"error": "git not found", "commits": [], "branch": None}
    except subprocess.TimeoutExpired:
        return {"error": "git log timeout", "commits": [], "branch": None}

    commits = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) < 5:
            continue
        commits.append({
            "sha": parts[0],
            "short_sha": parts[1],
            "author": parts[2],
            "relative": parts[3],
            "subject": parts[4],
        })

    branch: str | None = None
    try:
        b = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        branch = b.stdout.strip() or None
    except Exception:
        branch = None

    return {"commits": commits, "branch": branch, "count": len(commits)}


@router.get("/recent-commits")
async def recent_commits(limit: int = 20) -> ApiResponse:
    """Recent commits on the current branch — short_sha, author, relative, subject."""
    try:
        capped = max(1, min(limit, 100))
        return ApiResponse(data=_git_recent_commits(capped))
    except Exception as e:
        logger.exception("manifest/recent-commits failed")
        return ApiResponse(data=None, error=str(e))
