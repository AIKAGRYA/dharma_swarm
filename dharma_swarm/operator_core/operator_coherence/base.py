"""Shared primitives for the Operator Coherence Cockpit projection."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # PyYAML is a project dependency, but keep the projection degradable.
    import yaml
except Exception:  # pragma: no cover - exercised only in broken envs
    yaml = None  # type: ignore[assignment]


SCHEMA_VERSION = "operator_coherence_cockpit.v0.1"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON_OUTPUT = DEFAULT_REPO_ROOT / "reports" / "governance" / "operator_coherence_cockpit.json"
DEFAULT_MARKDOWN_OUTPUT = DEFAULT_REPO_ROOT / "reports" / "governance" / "operator_coherence_cockpit.md"

KANBAN_LANES = [
    "Preserved Only",
    "Needs Decision",
    "Ready To Extract",
    "Active Branch",
    "Open PR",
    "Needs Repair",
    "Landing Queue",
    "Verified",
    "Archived",
]

READINESS_WEIGHTS = {
    "source_control_coherence": 0.20,
    "governance_legibility": 0.15,
    "test_ci_state": 0.15,
    "runtime_telemetry_liveness": 0.15,
    "operator_surface_usability": 0.10,
    "preservation_safety": 0.10,
    "external_product_proof": 0.10,
    "documentation_freshness": 0.05,
}

SURFACE_PROBES = [
    {
        "id": "dashboard",
        "label": "Dashboard app",
        "paths": ["dashboard/package.json", "dashboard/src/app/dashboard/page.tsx"],
    },
    {
        "id": "cockpit",
        "label": "Operator cockpit",
        "paths": [
            "dashboard/src/app/dashboard/cockpit/page.tsx",
            "dashboard/src/components/operator-coherence/OperatorCoherenceCockpit.tsx",
        ],
    },
    {
        "id": "control_surface_api",
        "label": "Control surface API",
        "paths": ["api/routers/control_surface.py", "dharma_swarm/operator_core/control_surface.py"],
    },
    {
        "id": "operator_coherence_api",
        "label": "Operator coherence API",
        "paths": ["api/routers/operator_coherence.py", "dharma_swarm/operator_core/operator_coherence_cockpit.py"],
    },
    {
        "id": "terminal",
        "label": "Terminal / TUI",
        "paths": ["terminal", "terminal-v2", "docs/ops/TMUX_AGENT_SUBSTRATE.md"],
    },
    {
        "id": "a2a",
        "label": "A2A substrate",
        "paths": ["dharma_swarm/a2a", "reports/a2a"],
    },
    {
        "id": "live_ops",
        "label": "Live ops census",
        "paths": ["scripts/runtime/live_ops_census.py", "docs/state/LIVE_OPS_DASHBOARD.md"],
    },
    {
        "id": "provider_model_routing",
        "label": "Provider/model routing",
        "paths": ["dharma_swarm/providers.py", "MODEL_ROUTING_MAP.md", "tests/test_model_router_telemetry.py"],
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).isoformat()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _file_age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    return max(0.0, (_utc_now().timestamp() - path.stat().st_mtime) / 3600.0)


def _safe_read_text(path: Path, max_chars: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _safe_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = datetime.strptime(text.replace("Z", "+0000"), fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _age_hours_from_iso(value: Any) -> float | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return max(0.0, (_utc_now() - parsed).total_seconds() / 3600.0)


def _run(cmd: list[str], *, cwd: Path, timeout: float = 6.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "command execution failed"}


def _evidence(
    source: str,
    *,
    kind: str = "file",
    detail: str = "",
    path: str | None = None,
    status: str | None = None,
    age_hours: float | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "source": source,
        "path": path or source,
        "detail": detail,
        "status": status or "observed",
        "observed_at": _iso(),
        "age_hours": age_hours,
    }


def _card(
    *,
    card_id: str,
    kind: str,
    title: str,
    status: str,
    lane: str,
    risk: str,
    next_action: str,
    evidence: list[dict[str, Any]],
    facets: dict[str, Any] | None = None,
    decision_type: str = "operator_decision",
    track: str = "",
    branch: str = "",
    pr: int | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_facets = {
        "origin_backed": False,
        "local_only": False,
        "dirty": False,
        "stale": False,
        "preserved": False,
        "live": False,
        "rogue": False,
        "tracked": False,
        "intentional": False,
        "operator_decision": decision_type == "operator_decision",
    }
    if facets:
        base_facets.update(facets)
    return {
        "id": card_id,
        "kind": kind,
        "title": title,
        "status": status,
        "lane": lane,
        "risk": risk,
        "next_action": next_action,
        "decision_type": decision_type,
        "track": track,
        "branch": branch,
        "pr": pr,
        "facets": base_facets,
        "evidence": evidence,
        "raw": raw or {},
    }


@dataclass
class ProbeContext:
    repo_root: Path
    include_github: bool = True
    include_live_probes: bool = True
    source_errors: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    tracks_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    track_keywords: dict[str, list[str]] = field(default_factory=dict)

    def error(self, source: str, error: str) -> None:
        _ = error
        self.source_errors.append({"source": source, "error": "probe failed", "timestamp": _iso()})
