"""Status and mission helper functions for terminal commands."""

from __future__ import annotations

from datetime import date, datetime, timezone, tzinfo
from pathlib import Path
from typing import Any
import inspect
import json
import os
import subprocess
import time

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.terminal_commands._helpers import (
    DGC_CORE,
    _format_age,
    _parse_iso_datetime,
    _runtime_pid_status,
)
from dharma_swarm.terminal_commands._status_readonly import read_memory_entry_count

HOME = Path.home()
DHARMA_STATE = dharma_state_dir()
DHARMA_SWARM = HOME / "dharma_swarm"

MISSION_TRACKED_PATHS: tuple[str, ...] = (
    "dharma_swarm/evaluation_registry.py",
    "dharma_swarm/integrations/nvidia_rag.py",
    "dharma_swarm/integrations/data_flywheel.py",
    "dharma_swarm/integrations/reciprocity_commons.py",
    "dharma_swarm/ouroboros.py",
    "scripts/caffeine_until_jst.sh",
    "scripts/connection_finder.py",
    "scripts/ouroboros_experiment.py",
    "scripts/thinkodynamic_director.py",
    "docs/NVIDIA_INFRA_SELF_HEAL.md",
    "tests/test_evaluation_registry.py",
    "tests/test_integrations_nvidia_rag.py",
    "tests/test_integrations_data_flywheel.py",
    "tests/test_integrations_reciprocity_commons.py",
    "tests/test_ouroboros.py",
    "tests/tui/test_app_plan_mode.py",
)

MISSION_AUTONOMY_PROFILES: dict[str, dict[str, bool]] = {
    "ci": {"strict_core": True, "require_tracked": False},
    "ci-strict": {"strict_core": True, "require_tracked": True},
    "audit": {"strict_core": True, "require_tracked": True},
    "local": {"strict_core": False, "require_tracked": False},
}



def _pulse_sort_key(last_seen: str | None, source: Path) -> float:
    parsed = _parse_iso_datetime(last_seen)
    if parsed is not None:
        return parsed.timestamp()
    try:
        return source.stat().st_mtime
    except Exception:
        return 0.0


def _pulse_summary_from_log(path: Path) -> tuple[int, str | None, Path] | None:
    if not path.exists():
        return None
    try:
        count = 0
        last_seen: str | None = None
        for raw_line in path.read_text(errors="ignore").splitlines():
            line = raw_line.strip()
            if line.startswith("--- PULSE @"):
                count += 1
                marker = line[len("--- PULSE @"):].strip()
                timestamp = marker.split(" [", 1)[0].strip()
                if timestamp:
                    last_seen = timestamp
                continue
            marker = "pulse_"
            if marker not in line:
                continue
            start = line.rfind(marker)
            end = line.find(".md", start)
            if start == -1 or end == -1:
                continue
            count += 1
            raw_stamp = line[start + len(marker):end]
            try:
                timestamp = datetime.strptime(raw_stamp, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                last_seen = timestamp.isoformat()
            except ValueError:
                last_seen = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        if last_seen:
            return (count, last_seen, path)
        return (1, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), path)
    except Exception:
        return None


def _canonical_pulse_summary() -> tuple[int, str | None, Path | None]:
    candidates = [
        summary
        for summary in (
            _pulse_summary_from_log(DHARMA_STATE / "pulse.log"),
            _pulse_summary_from_log(DHARMA_STATE / "logs" / "pulse.log"),
        )
        if summary is not None
    ]

    cron_dir = DHARMA_STATE / "cron"
    pulse_artifacts = sorted(cron_dir.glob("pulse_*.md"))
    if pulse_artifacts:
        latest = pulse_artifacts[-1].stem.removeprefix("pulse_")
        try:
            timestamp = datetime.strptime(latest, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            candidates.append((len(pulse_artifacts), timestamp.isoformat(), pulse_artifacts[-1]))
        except ValueError:
            candidates.append(
                (
                    len(pulse_artifacts),
                    datetime.fromtimestamp(pulse_artifacts[-1].stat().st_mtime, timezone.utc).isoformat(),
                    pulse_artifacts[-1],
                )
            )

    if candidates:
        count, last_seen, source = max(candidates, key=lambda item: _pulse_sort_key(item[1], item[2]))
        return (count, last_seen, source)

    return (0, None, None)


def _witness_sort_key(path: Path, *, prefix: str, fmt: str) -> float:
    stem = path.stem
    raw_stamp = stem.removeprefix(prefix) if prefix else stem
    try:
        return datetime.strptime(raw_stamp, fmt).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0


def _latest_witness_count(
    directory: Path,
    *,
    pattern: str,
    prefix: str,
    fmt: str,
    local_date: date,
) -> int | None:
    if not directory.exists():
        return None

    candidates = sorted(
        directory.glob(pattern),
        key=lambda path: _witness_sort_key(path, prefix=prefix, fmt=fmt),
        reverse=True,
    )
    for witness_file in candidates:
        raw_stamp = (
            witness_file.stem.removeprefix(prefix) if prefix else witness_file.stem
        )
        try:
            witness_date = datetime.strptime(raw_stamp, fmt).date()
        except ValueError:
            continue
        if witness_date != local_date:
            continue
        try:
            with witness_file.open(encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        except Exception:
            continue
    return None


def _canonical_gate_count(
    *, now: datetime | None = None, local_timezone: tzinfo | None = None
) -> int:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_date = instant.astimezone(local_timezone).date()
    canonical_count = _latest_witness_count(
        DHARMA_STATE / "witness",
        pattern="witness_*.jsonl",
        prefix="witness_",
        fmt="%Y%m%d",
        local_date=local_date,
    )
    if canonical_count is not None:
        return canonical_count

    legacy_count = _latest_witness_count(
        DGC_CORE / "memory" / "witness",
        pattern="*.jsonl",
        prefix="",
        fmt="%Y-%m-%d",
        local_date=local_date,
    )
    if legacy_count is not None:
        return legacy_count

    return 0


def _control_plane_snapshot() -> str | None:
    details: list[str] = []

    _, _, pulse_source = _canonical_pulse_summary()
    if pulse_source is not None:
        details.append(f"pulse_source={pulse_source}")

    live_pid, live_pid_state = _runtime_pid_status()
    if live_pid is not None:
        details.append(f"runtime_pid={live_pid}")
    elif live_pid_state != "missing":
        details.append(f"runtime_pid={live_pid_state}")

    snapshot_path = DHARMA_STATE / "stigmergy" / "dgc_health.json"
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text())
        except Exception:
            details.append("dgc_health=unreadable")
        else:
            timestamp = str(payload.get("timestamp", "")).strip()
            freshness = "unknown"
            parsed_timestamp = _parse_iso_datetime(timestamp)
            if parsed_timestamp is not None:
                age_seconds = (
                    datetime.now(timezone.utc) - parsed_timestamp
                ).total_seconds()
                freshness = "fresh" if age_seconds <= 3600 else "stale"
                details.append(f"snapshot_age={_format_age(age_seconds)}")
            elif timestamp:
                freshness = "unknown"
            daemon_pid = payload.get("daemon_pid")
            details.append(f"dgc_health={freshness}")
            if daemon_pid is not None:
                details.append(f"daemon_pid={daemon_pid}")
                try:
                    snapshot_pid = int(daemon_pid)
                except (TypeError, ValueError):
                    snapshot_pid = None
                if snapshot_pid is not None and live_pid is not None and snapshot_pid != live_pid:
                    details.append("daemon_pid_mismatch")

    if not details:
        return None
    return " | ".join(details)


def _accelerator_mode() -> str:
    configured = any(
        os.getenv(key, "").strip()
        for key in (
            "DGC_NVIDIA_RAG_URL",
            "DGC_NVIDIA_INGEST_URL",
            "DGC_DATA_FLYWHEEL_URL",
            "DGC_RECIPROCITY_COMMONS_URL",
        )
    )
    raw = os.getenv("DGC_ACCELERATOR_MODE", "enabled" if configured else "dormant")
    mode = raw.strip().lower()
    return mode or ("enabled" if configured else "dormant")


def _accelerators_enabled() -> bool:
    return _accelerator_mode() not in {"0", "off", "disabled", "none", "dormant"}


# ---------------------------------------------------------------------------
# Commands — carried over from dgc-core
# ---------------------------------------------------------------------------


def _read_openclaw_summary() -> dict[str, Any]:
    """Best-effort OpenClaw summary from ~/.openclaw/openclaw.json."""
    oc_path = HOME / ".openclaw" / "openclaw.json"
    if not oc_path.exists():
        return {"present": False}
    try:
        payload = json.loads(oc_path.read_text())
    except Exception:
        return {"present": True, "readable": False}

    providers = []
    models = payload.get("models", {})
    if isinstance(models, dict):
        prov = models.get("providers", {})
        if isinstance(prov, dict):
            providers = sorted(prov.keys())

    agents_count = 0
    agents = payload.get("agents", {})
    if isinstance(agents, dict):
        lst = agents.get("list", [])
        if isinstance(lst, list):
            agents_count = len(lst)

    return {
        "present": True,
        "readable": True,
        "agents_count": agents_count,
        "providers": providers,
    }


def _tracked_paths(paths: list[str]) -> dict[str, bool]:
    """Return path->tracked bool for files relative to DHARMA_SWARM."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(DHARMA_SWARM), "ls-files", *paths],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        tracked = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    except Exception:
        tracked = set()
    return {p: (p in tracked) for p in paths}


def _core_mission_checks() -> dict[str, bool]:
    """Checks for core mission-critical intelligence wiring."""
    checks: dict[str, bool] = {}
    try:
        from dharma_swarm import evolution as evo

        checks["planner_executor"] = hasattr(evo, "EvolutionPlan")
        checks["circuit_breaker"] = "circuit_breaker_limit" in inspect.signature(
            evo.DarwinEngine.__init__
        ).parameters
        checks["traceability_fields"] = all(
            field in getattr(evo.Proposal, "model_fields", {})
            for field in ("spec_ref", "requirement_refs")
        )
    except Exception:
        checks["planner_executor"] = False
        checks["circuit_breaker"] = False
        checks["traceability_fields"] = False

    try:
        from dharma_swarm.telos_gates import TelosGatekeeper

        params = inspect.signature(TelosGatekeeper.check).parameters
        checks["think_points"] = (
            "think_phase" in params and "reflection" in params
        )
    except Exception:
        checks["think_points"] = False

    try:
        from dharma_swarm import startup_crew as sc

        checks["memory_survival_instinct"] = "MEMORY SURVIVAL INSTINCT" in str(
            getattr(sc, "MEMORY_SURVIVAL_INSTINCT", "")
        )
    except Exception:
        checks["memory_survival_instinct"] = False

    try:
        from dharma_swarm.tui import app as tui_app

        checks["tui_plan_mode_contract"] = "EnterPlanMode" in str(
            getattr(tui_app, "_PLAN_MODE_SYSTEM_PROMPT", "")
        )
    except Exception:
        checks["tui_plan_mode_contract"] = False

    return checks


MISSION_AUTONOMY_PROFILES: dict[str, dict[str, Any]] = {
    "readonly_audit": {
        "strict_core": True,
        "require_tracked": True,
        "trust_mode": "external_strict",
        "description": "Read-only verification lane with strict safety posture.",
    },
    "workspace_auto": {
        "strict_core": True,
        "require_tracked": True,
        "trust_mode": "internal_yolo",
        "description": "Default autonomous local workspace lane.",
    },
    "strict_external": {
        "strict_core": True,
        "require_tracked": True,
        "trust_mode": "external_strict",
        "description": "External-facing lane with strict trust mode.",
    },
    "yolo_local_container": {
        "strict_core": True,
        "require_tracked": True,
        "trust_mode": "internal_yolo",
        "description": "Fast lane intended for isolated local/container execution.",
    },
}


def _resolve_mission_profile(
    profile: str | None,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    if not profile:
        return None, None
    key = profile.strip().lower()
    cfg = MISSION_AUTONOMY_PROFILES.get(key)
    if not cfg:
        return None, None
    return key, cfg


# ---------------------------------------------------------------------------
# _build_status_data  (JSON-ready status payload)
# ---------------------------------------------------------------------------

def _build_status_data() -> dict:
    """Collect system status data as a JSON-ready dict."""

    data: dict[str, Any] = {}

    # Memory: status is observational and must never initialize runtime state.
    try:
        data["memory_entries"] = read_memory_entry_count(
            DHARMA_STATE / "db" / "memory.db"
        )
    except Exception as exc:
        data["memory_error"] = str(exc)

    # Pulse
    pulse_count, last_pulse, pulse_source = _canonical_pulse_summary()
    data["pulse"] = {
        "count": pulse_count,
        "last": last_pulse,
        "source": pulse_source,
    }

    # Gates
    data["gates_today"] = _canonical_gate_count()

    # Control plane
    snapshot = _control_plane_snapshot()
    if snapshot:
        data["control_plane_snapshot"] = snapshot

    # Loop liveness (projected by orchestrate_live's restart loop)
    try:
        liveness_path = DHARMA_STATE / "ops" / "loop_liveness.json"
        if liveness_path.exists():
            liveness = json.loads(liveness_path.read_text(encoding="utf-8"))
            age_s = time.time() - liveness_path.stat().st_mtime
            data["loop_liveness"] = {
                "running": len(liveness.get("running", [])),
                "abandoned": liveness.get("abandoned", []),
                "hot_restarts": {
                    k: v for k, v in liveness.get("restart_counts", {}).items() if v >= 3
                },
                "age_min": round(age_s / 60),
                "pid": liveness.get("pid"),
            }
    except Exception:
        pass

    # AGNI
    agni = HOME / "agni-workspace"
    if agni.exists():
        working = agni / "WORKING.md"
        if working.exists():
            age_min = (time.time() - working.stat().st_mtime) / 60
            data["agni"] = {"synced": True, "working_md_age_min": round(age_min)}
        else:
            data["agni"] = {"synced": True, "working_md": False}
    else:
        data["agni"] = {"synced": False}

    # Trishula
    trishula = HOME / "trishula" / "inbox"
    if trishula.exists():
        data["trishula_messages"] = len(list(trishula.glob("*.json")))

    # Claude Code
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5,
        )
        data["claude_code"] = result.stdout.strip()
    except Exception:
        data["claude_code"] = None

    return data
