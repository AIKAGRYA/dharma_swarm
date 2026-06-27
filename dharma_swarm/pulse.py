"""DGC Pulse v2 — dharma_swarm daemon wrapping Claude Code headless.

The key insight: `claude -p` IS a real agent (tools, file access, bash).
dharma_swarm API calls are NOT. So we use dharma_swarm for:
  - Daemon scheduling (Garden Daemon heartbeat, quiet hours, rate limits)
  - Thread rotation (mechanistic/phenomenological/architectural/alignment/scaling)
  - Circuit breaker (3 failures → pause, downtrend → switch thread)
  - Telos gates (check prompt before sending)
  - Memory persistence (log results to strange loop)
  - Human overrides (.PAUSE, .FOCUS, .INJECT)
And `claude -p` for actual execution.

Usage:
  python3 -m dharma_swarm.pulse              # Single pulse
  python3 -m dharma_swarm.pulse --daemon     # Continuous (Garden Daemon cycle)
  python3 -m dharma_swarm.pulse --status     # Check state
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.context import (
    read_agni_state,
    read_manifest,
    read_memory_context,
    read_trishula_inbox,
)
from dharma_swarm.daemon_config import DaemonConfig, THREAD_PROMPTS, V7_BASE_RULES
from dharma_swarm.shakti import ShaktiLoop
from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore
from dharma_swarm.subconscious import SubconsciousStream
from dharma_swarm.thread_manager import ThreadManager
from dharma_swarm.telos_gates import check_with_reflective_reroute
from dharma_swarm.claude_cli import (
    resolve_claude_binary,
    run_claude_headless as _run_claude_headless_impl,
)
from dharma_swarm.api_keys import ANTHROPIC_API_KEY_ENV, env_value
from dharma_swarm.runtime_artifacts import append_pulse_log, freshest_pulse_log_path

logger = logging.getLogger(__name__)

HOME = Path.home()
DGC = HOME / "dgc-core"
STATE_DIR = HOME / ".dharma"
_LIVING_STATE_PATH = STATE_DIR / "living_state.json"
_DREAM_THRESHOLD = 50
_DREAM_HYSTERESIS = 10
_SHAKTI_INTERVAL_SECONDS = 900
_SHAKTI_SALIENCE_THRESHOLD = 0.7
_NON_LLM_PULSE_MODES = {"health", "health-only", "non-llm", "no-llm", "status"}


def build_prompt(
    thread: str,
    thread_prompt: str,
    agni_state: dict,
    memory_ctx: str,
    trishula_ctx: str,
    manifest_ctx: str,
    inject: str | None = None,
) -> str:
    """Build the pulse prompt with v7 rules and thread context."""
    now = datetime.now(timezone.utc)

    prompt = f"""You are DGC Pulse v2 — the autonomous heartbeat of Dhyana's system.
Time: {now.isoformat()}
Active thread: {thread}

{V7_BASE_RULES}

## Current Research Thread: {thread}
{thread_prompt}

## AGNI VPS State
{json.dumps(agni_state, indent=2)[:800]}

## Trishula Inbox
{trishula_ctx}

## Recent Memories
{memory_ctx}

## Ecosystem
{manifest_ctx}
"""

    if inject:
        prompt += f"\n## INJECTED FOCUS\n{inject}\n"

    prompt += """
## Your Task
1. Check if AGNI state is stale (PRIORITIES > 48h = stale)
2. Check trishula inbox for anything needing attention
3. Based on the active research thread, identify one concrete next action
4. If nothing needs action, log a witness observation about the system state

## Rules
- Do NOT create files unless necessary
- Do NOT push to VPS — sync daemons handle it
- Log observations to ~/.dharma/witness/
- Be brief. Be real. No theater.
- SILENCE IS VALID — if nothing needs doing, say so in one sentence.
"""
    return prompt


def _resolve_claude_binary() -> str:
    """Compatibility wrapper for shared Claude CLI resolution."""
    return resolve_claude_binary()


def run_claude_headless(
    prompt: str,
    timeout: int = 600,
    model: str | None = None,
    *,
    bare: bool = True,
    permission_mode: str | None = "bypassPermissions",
    tools: str | None = "default",
) -> str:
    """Run Claude Code in headless mode — the REAL agent.

    NOTE: bare mode requires ANTHROPIC_API_KEY. When it's not set,
    returns a SKIP message immediately to avoid blocking the daemon
    process in U state (uninterruptible sleep) on the failed subprocess.
    """
    if bare and not env_value(ANTHROPIC_API_KEY_ENV):
        return (
            "SKIP: ANTHROPIC_API_KEY not set — "
            "claude bare mode unavailable. Set ANTHROPIC_API_KEY in .env "
            "or run `dgc orchestrate-live` without --bare once authenticated."
        )
    return _run_claude_headless_impl(
        prompt,
        timeout=timeout,
        model=model,
        bare=bare,
        permission_mode=permission_mode,
        tools=tools,
    )


def _load_living_state() -> dict[str, Any]:
    """Load persisted living-layer heartbeat state."""
    if not _LIVING_STATE_PATH.exists():
        return {
            "last_dream_density": 0,
            "last_shakti_at": 0,
        }
    try:
        data = json.loads(_LIVING_STATE_PATH.read_text())
        if not isinstance(data, dict):
            return {
                "last_dream_density": 0,
                "last_shakti_at": 0,
            }
        data.setdefault("last_dream_density", 0)
        data.setdefault("last_shakti_at", 0)
        return data
    except Exception:
        return {
            "last_dream_density": 0,
            "last_shakti_at": 0,
        }


def _save_living_state(state: dict[str, Any]) -> None:
    """Persist living-layer heartbeat state."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _LIVING_STATE_PATH.write_text(json.dumps(state, indent=2))
    except Exception as e:
        logger.warning("Failed to persist living state: %s", e)


def _non_llm_pulse_enabled() -> bool:
    """Return whether this process should write health pulses without LLM calls."""
    mode = os.getenv("DGC_PULSE_MODE", "").strip().lower()
    flag = os.getenv("DGC_PULSE_NO_LLM", "").strip().lower()
    return mode in _NON_LLM_PULSE_MODES or flag in {"1", "true", "yes", "on"}


def _safe_count_entries(path: Path) -> int | None:
    """Count one directory level without recursively walking large stores."""
    try:
        return sum(1 for _ in path.iterdir()) if path.exists() else 0
    except Exception:
        return None


def _safe_count_matching(path: Path, pattern: str) -> int | None:
    try:
        return sum(1 for _ in path.glob(pattern)) if path.exists() else 0
    except Exception:
        return None


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _memory_snapshot() -> dict[str, Any]:
    """Best-effort local memory facts without psutil or provider calls."""
    total_bytes: int | None = None
    try:
        total_bytes = int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except Exception:
        total_bytes = None
    return {"total_bytes": total_bytes}


def _disk_snapshot(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return {}
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": round((usage.free / usage.total) * 100, 2) if usage.total else None,
    }


def _pulse_log_snapshot() -> dict[str, Any]:
    path = freshest_pulse_log_path(STATE_DIR)
    if path is None:
        return {"exists": False}

    latest_block = ""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - 16384))
            tail = handle.read().decode("utf-8", errors="replace")
        if "--- PULSE @" in tail:
            latest_block = "--- PULSE @" + tail.rsplit("--- PULSE @", 1)[-1]
    except Exception:
        size = None

    latest_at = None
    latest_thread = None
    header = latest_block.splitlines()[0] if latest_block else ""
    match = re.search(r"--- PULSE @ ([^\s]+)(?: \[([^\]]+)\])?", header)
    if match:
        latest_at = match.group(1)
        latest_thread = match.group(2)

    excerpt = "\n".join(latest_block.splitlines()[1:4]).strip()
    lowered = latest_block.lower()
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "latest_at": latest_at,
        "latest_thread": latest_thread,
        "latest_excerpt": excerpt[:500],
        "credit_error_present": "credit balance" in lowered or "insufficient credit" in lowered,
    }


def _collect_non_llm_health(thread: str) -> dict[str, Any]:
    """Collect a local-only health snapshot for credit-outage pulse mode."""
    daemon_report = _safe_json(STATE_DIR / "ops" / "daemon_runtime_dispatch_self_report.json")
    pid = _read_pid(STATE_DIR / "daemon.pid") or daemon_report.get("pid")
    try:
        pid_int = int(pid) if pid is not None else None
    except (TypeError, ValueError):
        pid_int = None

    pulse_log = _pulse_log_snapshot()
    credit_error_present = bool(pulse_log.get("credit_error_present"))
    credit_status = {
        "status": "provider_credit_exhausted" if credit_error_present else "not_observed_in_latest_pulse",
        "likely_pool": (
            "ANTHROPIC_API_KEY / Claude Code bare mode"
            if credit_error_present
            else None
        ),
        "basis": (
            "dharma_swarm.pulse calls run_claude_headless(..., model='sonnet'); "
            "claude_cli bare mode requires ANTHROPIC_API_KEY."
        ),
        "latest_excerpt": pulse_log.get("latest_excerpt"),
    }

    load_average = None
    try:
        load_average = os.getloadavg()
    except Exception:
        pass

    return {
        "schema": "dharma_swarm.pulse.health.v1",
        "mode": "non_llm",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "thread": thread,
        "daemon": {
            "pid": pid_int,
            "alive": _pid_alive(pid_int),
            "pid_file": str(STATE_DIR / "daemon.pid"),
            "runtime_dispatch": daemon_report.get("runtime_dispatch"),
            "runtime_report_updated_at": daemon_report.get("updated_at"),
        },
        "system": {
            "load_average": load_average,
            "memory": _memory_snapshot(),
            "disk": _disk_snapshot(STATE_DIR),
        },
        "runtime_counts": {
            "sessions_top_level": _safe_count_entries(STATE_DIR / "sessions"),
            "artifacts_top_level": _safe_count_entries(STATE_DIR / "artifacts"),
            "agent_runs_top_level": _safe_count_entries(STATE_DIR / "agent_runs"),
            "active_run_markers": _safe_count_matching(STATE_DIR / "agent_runs", "*_latest.json"),
            "ledgers_top_level": _safe_count_entries(STATE_DIR / "ledgers"),
            "agents_top_level": _safe_count_entries(STATE_DIR / "agents"),
        },
        "pulse_log": pulse_log,
        "credit_status": credit_status,
    }


def _run_non_llm_pulse(thread: str) -> str:
    snapshot = _collect_non_llm_health(thread)
    entry = (
        f"\n--- PULSE @ {snapshot['collected_at']} [health-non-llm] ---\n"
        f"{json.dumps(snapshot, indent=2, sort_keys=True)}\n"
    )
    append_pulse_log(STATE_DIR, entry)

    daemon = snapshot["daemon"]
    credit = snapshot["credit_status"]
    counts = snapshot["runtime_counts"]
    return (
        "HEALTH PULSE: "
        f"daemon_alive={daemon['alive']} pid={daemon['pid']} "
        f"credit_status={credit['status']} "
        f"sessions={counts['sessions_top_level']} "
        f"active_runs={counts['active_run_markers']} "
        f"artifacts={counts['artifacts_top_level']}"
    )


async def _run_living_layers(thread: str, pulse_result: str) -> dict[str, Any]:
    """Run subconscious + shakti heartbeat wiring from pulse.

    This is the "breathing" bridge:
    - Trigger subconscious dreams when stigmergy density crosses threshold.
    - Use hysteresis to avoid repeated dream spam.
    - Periodically run shakti perception and re-inject salient signals as marks.
    """
    summary: dict[str, Any] = {
        "density": 0,
        "dream_triggered": False,
        "dream_associations": 0,
        "shakti_perceptions": 0,
        "shakti_escalations": 0,
    }

    try:
        store = StigmergyStore()
        density = store.density()
        summary["density"] = density

        state = _load_living_state()
        now_ts = int(time.time())

        threshold = int(os.getenv("DGC_DREAM_THRESHOLD", str(_DREAM_THRESHOLD)))
        hysteresis = max(
            1, int(os.getenv("DGC_DREAM_HYSTERESIS", str(_DREAM_HYSTERESIS)))
        )
        last_dream_density = int(state.get("last_dream_density", 0))

        # Wake the subconscious only on meaningful density increases.
        if density >= threshold and density >= (last_dream_density + hysteresis):
            stream = SubconsciousStream(stigmergy=store)
            associations = await stream.dream()
            dream_count = len(associations)
            if dream_count > 0:
                summary["dream_triggered"] = True
                summary["dream_associations"] = dream_count
                state["last_dream_density"] = density

        # Run shakti on a cadence, or immediately after a dream.
        shakti_interval = max(
            60, int(os.getenv("DGC_SHAKTI_INTERVAL_SEC", str(_SHAKTI_INTERVAL_SECONDS)))
        )
        last_shakti_at = int(state.get("last_shakti_at", 0))
        should_run_shakti = summary["dream_triggered"] or (
            (now_ts - last_shakti_at) >= shakti_interval
        )
        if should_run_shakti:
            loop = ShaktiLoop(stigmergy=store)
            perceptions = await loop.perceive(
                current_context=pulse_result[:500],
                agent_role="pulse",
            )
            summary["shakti_perceptions"] = len(perceptions)

            salience_threshold = float(
                os.getenv("DGC_SHAKTI_SALIENCE", str(_SHAKTI_SALIENCE_THRESHOLD))
            )
            escalations = [
                p for p in perceptions
                if p.salience >= salience_threshold or p.impact_level in {"module", "system"}
            ]
            summary["shakti_escalations"] = len(escalations)

            # Feed high-salience perceptions back into lattice as connective marks.
            for p in escalations[:5]:
                mark = StigmergicMark(
                    agent="shakti-pulse",
                    file_path=p.connection or "shakti:unknown",
                    action="connect",
                    observation=(p.proposal or p.observation)[:200],
                    salience=p.salience,
                    connections=[thread, p.energy.value, p.impact_level],
                )
                await store.leave_mark(mark)

            state["last_shakti_at"] = now_ts

        _save_living_state(state)
    except Exception as e:
        logger.warning("Living layer heartbeat failed: %s", e)

    return summary


async def _store_pulse_result(result: str, thread: str) -> None:
    """Store pulse result in dharma_swarm memory."""
    try:
        from dharma_swarm.memory import StrangeLoopMemory
        from dharma_swarm.models import MemoryLayer

        db_path = STATE_DIR / "db" / "memory.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        mem = StrangeLoopMemory(db_path)
        await mem.init_db()
        await mem.remember(
            f"[pulse:{thread}] {result[:500]}",
            layer=MemoryLayer.WITNESS,
            source="pulse",
            tags=["pulse", thread],
        )
        await mem.close()
    except Exception as e:
        logger.warning("Failed to store pulse result: %s", e)


def pulse(config: DaemonConfig | None = None) -> str:
    """Execute one pulse cycle with full daemon infrastructure."""
    cfg = config or DaemonConfig()

    # Init state dir
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "db").mkdir(exist_ok=True)

    # Thread manager
    tm = ThreadManager(cfg, STATE_DIR)

    # Check human overrides
    pause_path = STATE_DIR / cfg.pause_file
    if pause_path.exists():
        return "PAUSED: .PAUSE file exists"

    focus = tm.check_focus_override(STATE_DIR)
    if focus:
        tm._current_thread = focus

    if _non_llm_pulse_enabled():
        return _run_non_llm_pulse(tm.current_thread)

    inject = tm.check_inject_override(STATE_DIR)

    # Check quiet hours — run sleep cycle instead of skipping
    if datetime.now().hour in cfg.quiet_hours:
        try:
            from dharma_swarm.sleep_cycle import SleepCycle
            store = StigmergyStore()
            stream = SubconsciousStream(stigmergy=store)
            cycle = SleepCycle(
                stigmergy_store=store,
                subconscious_stream=stream,
            )
            report = asyncio.run(cycle.run_full_cycle())
            summary = (
                f"SLEEP: phases={','.join(report.phases_completed)} "
                f"decayed={report.marks_decayed} "
                f"consolidated={report.memories_consolidated} "
                f"dreams={report.dreams_generated}"
            )
            if report.colony_rv is not None:
                summary += f" colony_rv={report.colony_rv:.3f}"
                # Feed colony R_V into evolution bridge
                try:
                    from dharma_swarm.ouroboros import colony_rv_reading
                    reading = colony_rv_reading(
                        report.density_before, report.density_after,
                    )
                    if reading.is_contracted:
                        summary += " [CONTRACTED]"
                except Exception:
                    logger.debug("Colony R_V reading failed", exc_info=True)
            if report.errors:
                summary += f" errors={len(report.errors)}"
            print(f"[pulse] {summary}")
            return summary
        except Exception as e:
            logger.warning("Sleep cycle failed: %s", e)
            return f"QUIET: Hour {datetime.now().hour} (sleep cycle error: {e})"

    # Check circuit breaker
    if cfg.circuit_breaker.is_broken:
        return "CIRCUIT BREAKER: Too many consecutive failures"

    # Gather context
    thread = tm.current_thread
    thread_prompt = THREAD_PROMPTS.get(thread, "")
    agni_state = read_agni_state()
    memory_ctx = read_memory_context()
    trishula_ctx = read_trishula_inbox()
    manifest_ctx = read_manifest()

    # Build prompt
    prompt = build_prompt(
        thread=thread,
        thread_prompt=thread_prompt,
        agni_state=agni_state,
        memory_ctx=memory_ctx,
        trishula_ctx=trishula_ctx,
        manifest_ctx=manifest_ctx,
        inject=inject,
    )

    # Telos gate check with bounded reflective reroute
    gate = check_with_reflective_reroute(
        action="pulse",
        content=prompt[:2000],
        tool_name="pulse_daemon",
        think_phase="before_complete",
        reflection=(
            f"Thread={thread}. Prompt assembled from memory, manifest, and inbox. "
            "Validate safety and continue with bounded action."
        ),
        max_reroutes=1,
        requirement_refs=[f"thread:{thread}", "daemon:pulse"],
    )
    if gate.result.decision.value == "block":
        return f"TELOS BLOCK: {gate.result.reason}"
    if gate.attempts:
        print(f"[pulse] witness reroute applied ({gate.attempts} attempts)")

    # Execute via Claude Code headless.
    # Use "sonnet" (not opus) for pulse — heartbeat checks don't need
    # the most expensive model, and opus drains credits fast.
    print(f"[pulse] Thread: {thread} | Executing...")
    result = run_claude_headless(prompt, model="sonnet")

    # Record
    tm.record_contribution()
    if result.startswith("ERROR") or result.startswith("TIMEOUT"):
        tripped = cfg.circuit_breaker.record_failure()
        if tripped:
            print("[pulse] Circuit breaker tripped! Rotating thread.")
            tm.rotate()
    else:
        cfg.circuit_breaker.record_success()

    # Store in memory (async)
    asyncio.run(_store_pulse_result(result, thread))

    # Living-layer heartbeat (subconscious + shakti)
    living_summary = asyncio.run(_run_living_layers(thread, result))
    if living_summary:
        print(
            "[pulse] Living: density={density} dream={dream} assoc={assoc} "
            "perceptions={perceptions} escalations={escalations}".format(
                density=living_summary.get("density", 0),
                dream="yes" if living_summary.get("dream_triggered") else "no",
                assoc=living_summary.get("dream_associations", 0),
                perceptions=living_summary.get("shakti_perceptions", 0),
                escalations=living_summary.get("shakti_escalations", 0),
            )
        )

    # Log to pulse log
    append_pulse_log(
        STATE_DIR,
        (
            f"\n--- PULSE @ {datetime.now(timezone.utc).isoformat()} [{thread}] ---\n"
            f"{result[:500]}\n"
        ),
    )

    # Rotate thread for next pulse
    tm.rotate()

    return result


def _check_and_run_cron_jobs(cfg: DaemonConfig | None = None) -> None:
    """Check and run due cron jobs from `~/dharma_swarm/cron_jobs.json`."""
    _ = cfg  # reserved for future per-job policy wiring

    cron_file = Path.home() / "dharma_swarm" / "cron_jobs.json"
    if not cron_file.exists():
        return

    try:
        jobs = json.loads(cron_file.read_text())
    except Exception as e:
        print(f"[cron] Error reading cron_jobs.json: {e}")
        return

    if not isinstance(jobs, list):
        print("[cron] cron_jobs.json must be a JSON list")
        return

    # Load last run tracking
    last_run_file = STATE_DIR / "cron_last_run.json"
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        last_runs = json.loads(last_run_file.read_text())
        if not isinstance(last_runs, dict):
            last_runs = {}
    except Exception:
        last_runs = {}

    now = datetime.now()
    slot_key = now.strftime("%Y-%m-%dT%H:%M")
    did_run = False

    for job in jobs:
        if not isinstance(job, dict):
            continue
        if not job.get("enabled", False):
            continue

        job_id = str(job.get("id", "")).strip()
        if not job_id:
            continue
        trigger = str(job.get("trigger", "")).strip()
        last_run_key: str | None = None
        schedule_label = ""

        if trigger == "cron":
            schedule = job.get("schedule", {})
            if not isinstance(schedule, dict):
                continue
            try:
                hour = int(schedule.get("hour"))
                minute = int(schedule.get("minute", 0))
            except (TypeError, ValueError):
                continue
            if now.hour != hour or now.minute != minute:
                continue
            last_run_key = f"{job_id}:{slot_key}"
            if last_run_key in last_runs:
                continue
            schedule_label = f"hour={hour}, minute={minute}"
        elif trigger == "interval":
            try:
                interval_seconds = int(job.get("interval_seconds"))
            except (TypeError, ValueError):
                continue
            if interval_seconds <= 0:
                continue
            last_run_key = f"{job_id}:interval"
            raw_last_run = last_runs.get(last_run_key)
            last_run_dt: datetime | None = None
            if isinstance(raw_last_run, str):
                try:
                    last_run_dt = datetime.fromisoformat(raw_last_run)
                except ValueError:
                    last_run_dt = None
            if last_run_dt is not None:
                elapsed = (now - last_run_dt).total_seconds()
                if elapsed < interval_seconds:
                    continue
            schedule_label = f"every {interval_seconds}s"
        else:
            continue

        name = str(job.get("name", job_id))
        prompt = str(job.get("prompt", "")).strip()
        if not prompt:
            print(f"[cron] Skipping {job_id}: empty prompt")
            continue

        model = str(job.get("model", "")).strip() or None
        print(f"[cron] Running: {name} ({schedule_label})")

        gate = check_with_reflective_reroute(
            action=f"cron:{job_id}",
            content=prompt[:2000],
            tool_name="pulse_cron",
            think_phase="before_complete",
            reflection=(
                f"Cron job {job_id} scheduled as {schedule_label}. "
                "Validate safety and bounded execution."
            ),
            max_reroutes=1,
            requirement_refs=[f"cron:{job_id}"],
        )
        if gate.result.decision.value == "block":
            print(f"[cron] Blocked {job_id}: {gate.result.reason}")
            continue

        try:
            result = run_claude_headless(
                prompt=prompt,
                model=model,
            )
            print(f"[cron] {job_id}: {result[:150].replace(chr(10), ' ')}")

            last_runs[last_run_key] = now.isoformat()
            did_run = True
        except Exception as e:
            print(f"[cron] Error running {job_id}: {e}")

    if did_run:
        try:
            last_run_file.write_text(json.dumps(last_runs, indent=2))
        except Exception as e:
            print(f"[cron] Error persisting cron last-run state: {e}")


def daemon_loop(config: DaemonConfig | None = None):
    """Run continuous pulse loop with Garden Daemon parameters."""
    cfg = config or DaemonConfig()
    interval = int(cfg.heartbeat_interval)
    max_daily = cfg.max_daily_contributions
    daily_count = 0
    last_date = datetime.now().date()

    print(f"DGC Pulse v2 daemon starting.")
    print(f"  Heartbeat: {interval}s ({interval/3600:.1f}h)")
    print(f"  Max daily: {max_daily}")
    print(f"  Quiet hours: {cfg.quiet_hours}")
    print(f"  Threads: {cfg.threads}")

    while True:
        now = datetime.now()

        # Reset daily counter
        if now.date() != last_date:
            daily_count = 0
            last_date = now.date()

        # Rate limit
        if daily_count >= max_daily:
            print(f"[{now.isoformat()[:19]}] Daily limit ({max_daily}) reached. Sleeping.")
            time.sleep(3600)
            continue

        try:
            print(f"\n[{now.isoformat()[:19]}] Pulsing... (#{daily_count + 1}/{max_daily})")
            result = pulse(cfg)
            if not result.startswith(("PAUSED", "QUIET", "CIRCUIT", "HEALTH PULSE")):
                daily_count += 1
            print(f"Result: {result[:200]}")
        except Exception as e:
            print(f"Pulse error: {e}")

        # Check and run any due cron jobs
        _check_and_run_cron_jobs(cfg)

        time.sleep(interval)


def show_status():
    """Show pulse status from dharma_swarm state."""
    log_path = freshest_pulse_log_path(STATE_DIR) or (STATE_DIR / "pulse.log")
    if not log_path.exists():
        print("No pulse log yet.")
        return

    # Show last 3 entries
    content = log_path.read_text()
    entries = content.split("--- PULSE @")
    if len(entries) <= 1:
        print("No pulses recorded yet.")
        return

    print(f"Total pulse entries: {len(entries) - 1}")
    for entry in entries[-3:]:
        if entry.strip():
            print(f"--- PULSE @{entry[:300]}")

    # Thread state
    try:
        cfg = DaemonConfig()
        tm = ThreadManager(cfg, STATE_DIR)
        stats = tm.stats()
        print(f"\nCurrent thread: {stats['current_thread']}")
        print(f"Contributions: {stats['contributions']}")
    except Exception:
        logger.debug("Thread stats display failed", exc_info=True)


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        daemon_loop()
    elif "--status" in sys.argv:
        show_status()
    elif "--swarm" in sys.argv:
        # Spawn a full swarm instead of a single pulse
        from dharma_swarm.orchestrate import run
        plan = sys.argv[sys.argv.index("--swarm") + 1] if len(sys.argv) > sys.argv.index("--swarm") + 1 else None
        run(plan)
    else:
        result = pulse()
        print(result)
