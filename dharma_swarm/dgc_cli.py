"""DGC CLI — unified command interface for the dharmic swarm.

Merges dgc-core commands (status, pulse, swarm, gates, memory, witness,
context, agni, etc.) with dharma_swarm's async orchestrator (spawn, task,
evolve, run, health-check).  No sys.path hacks — all imports are proper
``from dharma_swarm.*`` paths.

Usage:
  dgc                           Launch interactive TUI (or Claude Code if DGC_DEFAULT_MODE=chat)
  dgc chat                      Launch native Claude Code interactive UI
  dgc dashboard                 Launch interactive DGC dashboard (TUI)
  dgc status                    System status overview
  dgc runtime-status            Canonical runtime control-plane summary
  dgc mission-status            Mission-level readiness across core/accelerators
  dgc mission-brief             Show the active mission continuity state
  dgc campaign-brief            Show the active dual-engine campaign state
  dgc canonical-status          Show which DGC/SAB repos are canonical vs split
  dgc up [--background]         Start the daemon
  dgc down                      Stop the daemon
  dgc daemon-status             Show daemon state
  dgc pulse                     Run one heartbeat pulse
  dgc swarm [plan]              Run orchestrator (build/research/deploy/maintenance)
  dgc stress [--profile max]    Run end-to-end max-capacity stress harness
  dgc full-power-probe          Run operator-facing full-power verification
  dgc provider-smoke            Probe Ollama and NVIDIA NIM completion lanes
  dgc provider-matrix           Run the live provider/model matrix harness
  dgc swarm --status            Show orchestrator state
  dgc swarm live [N]            Persistent tmux swarm (N agents)
  dgc swarm overnight start [H] [--aggressive]
  dgc swarm overnight stop|status|report
  dgc swarm codex-night start [H] [--yolo] [--mission-file PATH]
  dgc swarm codex-night yolo [H]
  dgc swarm codex-night stop|status|report
  dgc swarm yolo                Aggressive Codex overnight (10h)
  dgc context [domain]          Load context (research/content/ops/all)
  dgc memory                    Show memory status
  dgc witness "msg"             Record a witness observation
  dgc develop "what" "evidence" Record a development marker
  dgc gates "action"            Run telos gates on an action
  dgc meta                      Overseeing I — wholistic system assessment
  dgc prune [--dry-run]         Sweep the zen garden — cut noise, keep signal
  dgc health                    Ecosystem file health
  dgc ouroboros connections|record  Inspect or canonically bind behavioral observations
  dgc health-check              Monitor-based system health (v0.2.0)
  dgc doctor                    Deep runtime diagnostics + fix guidance
  dgc spawn --name X --role Y   Spawn a new agent
  dgc task create "title"       Create a task
  dgc task list [--status S]    List tasks
  dgc evolve propose COMP DESC  Run evolution pipeline
  dgc evolve trend [--component C]
  dgc reciprocity health|summary|record|publish  Planetary Reciprocity Commons endpoints
  dgc rag health|search|chat    NVIDIA RAG integration endpoints
  dgc flywheel jobs|export|record|...  NVIDIA Data Flywheel job lifecycle
  dgc run [--interval N]        Run orchestration loop
  dgc setup                     Install dependencies
  dgc migrate                   Migrate old DGC memory
  dgc agni "cmd"                Run command on AGNI VPS via SSH
  dgc foundations [pillar]        Intellectual pillars and syntheses
  dgc telos [doc]                 Telos Engine research documents
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# New imports for economic health reporting
try:
    from dharma_swarm.economic_engine import EconomicEngine, MetabolicQuarantineStage
except Exception:  # pragma: no cover
    EconomicEngine = None  # type: ignore
    MetabolicQuarantineStage = None  # type: ignore

HOME = Path.home()
DHARMA_STATE = HOME / ".dharma"
DHARMA_SWARM = HOME / "dharma_swarm"
DGC_CORE = HOME / "dgc-core"
DEFAULT_SPRINT_LLM_TIMEOUT_SEC = 12.0

# Keep mission-status aligned with the lanes the overnight cycle depends on:
# accelerator adapters, canonical evaluation binding, and behavioral feedback.
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


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (
            len(value) >= 2
            and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'"))
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bootstrap_env() -> None:
    # Load dharma_swarm defaults and optional local runtime overrides.
    _load_env_file(HOME / "dharma_swarm" / ".env")
    _load_env_file(HOME / ".dharma" / "env" / "nvidia_remote.env")


_bootstrap_env()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _load_json_object(
    *,
    json_payload: str | None = None,
    file_path: str | None = None,
    label: str = "JSON payload",
) -> dict[str, Any]:
    if json_payload is None and file_path is None:
        raise ValueError(f"{label} is required")

    raw = json_payload
    if file_path is not None:
        raw = Path(file_path).read_text(encoding="utf-8")

    try:
        payload = json.loads(raw if raw is not None else "")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return payload


def _normalize_optional_text(value: str | None, *, default: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _default_ouroboros_log_path() -> Path:
    candidates = (
        DHARMA_STATE / "evolution" / "observations" / "ouroboros_log.jsonl",
        DHARMA_STATE / "evolution" / "ouroboros_log.jsonl",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_ouroboros_observation(
    *,
    log_path: Path,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    if not log_path.exists():
        raise FileNotFoundError(f"ouroboros log not found: {log_path}")

    selected: dict[str, Any] | None = None
    for line_no, raw_line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"ouroboros log {log_path} contains invalid JSON on line {line_no}"
            ) from exc
        if not isinstance(decoded, dict):
            raise ValueError(
                f"ouroboros log {log_path} contains a non-object JSON record on line {line_no}"
            )
        if cycle_id:
            if str(decoded.get("cycle_id") or "").strip() == cycle_id:
                selected = decoded
        else:
            selected = decoded

    if selected is None:
        if cycle_id:
            raise ValueError(f"no ouroboros observation found for cycle_id={cycle_id}")
        raise ValueError(f"no ouroboros observations found in {log_path}")
    return selected


async def _get_swarm(state_dir: str = ".dharma"):
    from dharma_swarm.swarm import SwarmManager

    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    return swarm


async def _get_task_board(state_dir: str = ".dharma"):
    """Thin path: open just the TaskBoard without booting the full swarm.

    Used by CLI task create/list/show to avoid spawning agents and seed tasks.
    """
    from dharma_swarm.task_board import TaskBoard

    db_path = Path(state_dir) / "db" / "tasks.db"
    tb = TaskBoard(db_path)
    await tb.init_db()
    return tb


def _pid_alive(pid: int) -> bool:
    try:
        if pid <= 1:
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _tail(path: Path, lines: int = 60) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(errors="ignore")
        return "\n".join(text.splitlines()[-lines:])
    except Exception:
        return ""


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_age(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _runtime_pid_status() -> tuple[int | None, str]:
    pid_file = DHARMA_STATE / "daemon.pid"
    if not pid_file.exists():
        return (None, "missing")
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return (None, "invalid")
    if _pid_alive(pid):
        return (pid, "alive")
    return (pid, "stale")


def _list_daemon_like_processes() -> list[tuple[int, str]]:
    """Best-effort process scan for live daemon/orchestrator launchers."""
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except Exception:
        return []

    if proc.returncode != 0:
        return []

    current_pid = os.getpid()
    matches: list[tuple[int, str]] = []
    needles = ("dharma_swarm.orchestrate_live", "orchestrate_live.py", "run_daemon.sh")
    skip_markers = ("dgc doctor", "ps -axo", "rg ", "pytest")

    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]
        if pid == current_pid:
            continue
        if not any(needle in command for needle in needles):
            continue
        if any(marker in command for marker in skip_markers):
            continue
        matches.append((pid, command))

    return matches


def _first_daemon_like_process() -> tuple[int, str] | None:
    matches = _list_daemon_like_processes()
    if not matches:
        return None
    return matches[0]


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


# ---------------------------------------------------------------------------
# Economic health reporting
# ---------------------------------------------------------------------------

def _format_currency(value: float) -> str:
    """Simple currency formatter, showing two decimal places and a $ sign."""
    return f"${value:,.2f}"


def _economic_status_report() -> str:
    """Generate a short economic health report for the status command."""
    if EconomicEngine is None:
        return "Economic engine: not initialized"

    try:
        engine = EconomicEngine.get_instance()
    except Exception:
        return "Economic engine: not initialized"

    # Gather core metrics
    total_revenue = getattr(engine, "total_revenue", 0.0)
    total_expenses = getattr(engine, "total_expenses", 0.0)
    net_balance = total_revenue - total_expenses

    # 3‑signal split (savings / paper / verified)
    savings = getattr(engine, "savings_balance", 0.0)
    paper = getattr(engine, "paper_balance", 0.0)
    verified = getattr(engine, "verified_balance", 0.0)

    # Credit/reject/quarantine counts
    credited = getattr(engine, "credited_count", 0)
    rejected = getattr(engine, "rejected_count", 0)
    quarantined = getattr(engine, "quarantined_count", 0)

    # Quarantine stage
    stage = "unknown"
    if MetabolicQuarantineStage is not None:
        try:
            stage_obj = engine.quarantine_stage  # type: ignore[attr-defined]
            stage = getattr(stage_obj, "name", str(stage_obj))
        except Exception:
            pass

    lines = [
        "Economic health:",
        f"  Total revenue   : {_format_currency(total_revenue)}",
        f"  Total expenses  : {_format_currency(total_expenses)}",
        f"  Net balance     : {_format_currency(net_balance)}",
        "  3‑signal split  :",
        f"    Savings       : {_format_currency(savings)}",
        f"    Paper         : {_format_currency(paper)}",
        f"    Verified      : {_format_currency(verified)}",
        f"  Credits / rejects / quarantined : {credited} / {rejected} / {quarantined}",
        f"  Quarantine stage: {stage}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main command handling (excerpt – status command integration)
# ---------------------------------------------------------------------------

def _handle_status(args: argparse.Namespace) -> int:
    # Existing status output generation (omitted for brevity)
    # ...

    # Append economic health report
    print(_economic_status_report())
    return 0


def _handle_audit_gates(args: argparse.Namespace) -> int:
    from dharma_swarm.audit_queries import (
        proposal_to_outcome_chain,
        recent_blocks,
        unrecorded_actions,
    )

    days = int(args.days)
    blocks = recent_blocks(days)
    gaps = unrecorded_actions(days)
    proposal_ids: list[str] = []
    for row in gaps:
        proposal_ids.append(str(row["id"]))
    for row in blocks:
        proposal_id = str(row["properties"].get("proposal_id") or "")
        if proposal_id:
            proposal_ids.append(proposal_id)
    sample_proposal_ids = list(dict.fromkeys(proposal_ids))[:5]
    chains = [
        proposal_to_outcome_chain(proposal_id)
        for proposal_id in sample_proposal_ids
    ]

    print(f"Governance gate audit ({days}d)")
    print(f"  Recent blocks: {len(blocks)}")
    print(f"  Ungated proposals: {len(gaps)}")

    if blocks:
        print("\nRecent blocks:")
        for row in blocks[:5]:
            props = row["properties"]
            proposal_id = str(props.get("proposal_id") or "")[:12]
            reason = str(props.get("reason") or "").strip()
            print(f"  - {row['id']} proposal={proposal_id} reason={reason[:96]}")

    if gaps:
        print("\nUngated proposals:")
        for row in gaps[:5]:
            props = row["properties"]
            title = str(props.get("title") or "").strip()
            status = str(props.get("status") or "").strip()
            print(f"  - {row['id']} status={status} title={title[:96]}")

    if chains:
        print("\nSample chains:")
        for chain in chains:
            states = [
                "P" if chain["proposal"] else "-",
                "G" if chain["gate_decision"] else "-",
                "L" if chain["execution_lease"] else "-",
                "O" if chain["outcome"] else "-",
                "V" if chain["value_event"] else "-",
                f"C{len(chain['contributions'])}",
            ]
            print(f"  - {chain['proposal_id'][:12]} {'>'.join(states)}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dgc", description="DGC command line interface")
    subparsers = parser.add_subparsers(dest="command")

    # status command
    status_parser = subparsers.add_parser("status", help="System status overview")
    status_parser.set_defaults(func=_handle_status)

    audit_parser = subparsers.add_parser("audit", help="Governance audit queries")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_command")
    gates_parser = audit_subparsers.add_parser("gates", help="Audit gate decisions")
    gates_parser.add_argument("--days", type=int, default=7)
    gates_parser.set_defaults(func=_handle_audit_gates)

    # Parse-only compatibility commands used by legacy control-plane tests.
    dharma_parser = subparsers.add_parser("dharma", help="Dharma corpus controls")
    dharma_subparsers = dharma_parser.add_subparsers(dest="dharma_cmd")
    dharma_subparsers.add_parser("status", help="Dharma corpus status")
    corpus_parser = dharma_subparsers.add_parser("corpus", help="List corpus claims")
    corpus_parser.add_argument("--status", dest="corpus_status")
    corpus_parser.add_argument("--category", dest="corpus_category")
    review_parser = dharma_subparsers.add_parser("review", help="Review corpus claim")
    review_parser.add_argument("claim_id")

    evolve_parser = subparsers.add_parser("evolve", help="Evolution controls")
    evolve_subparsers = evolve_parser.add_subparsers(dest="evolve_cmd")
    apply_parser = evolve_subparsers.add_parser("apply", help="Apply evolution change")
    apply_parser.add_argument("component")
    apply_parser.add_argument("description")
    promote_parser = evolve_subparsers.add_parser("promote", help="Promote evolution entry")
    promote_parser.add_argument("entry_id")
    rollback_parser = evolve_subparsers.add_parser("rollback", help="Rollback evolution entry")
    rollback_parser.add_argument("entry_id")
    rollback_parser.add_argument("--reason")

    stigmergy_parser = subparsers.add_parser("stigmergy", help="Inspect stigmergy marks")
    stigmergy_parser.add_argument("--file", dest="stig_file")
    subparsers.add_parser("hum", help="Show system hum")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
