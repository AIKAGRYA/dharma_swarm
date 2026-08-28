"""DGC CLI — unified command interface for the dharmic swarm.

Thin dispatcher: argparse definitions + match-case routing.
Command implementations live in dharma_swarm.terminal_commands.
See docs/plans/OPERATOR_COMMAND_VISION.md for the architecture vision.
"""

# This dispatcher deliberately re-exports compatibility names used by tests
# and downstream operator scripts.
# ruff: noqa: F401

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir

from dharma_swarm.terminal_commands._helpers import (
    DEFAULT_SPRINT_LLM_TIMEOUT_SEC,
    DHARMA_STATE,
    DHARMA_SWARM,
    HOME,
    _get_swarm,
)
from dharma_swarm.terminal_commands._status_helpers import (
    MISSION_AUTONOMY_PROFILES,
    MISSION_TRACKED_PATHS,
)
from dharma_swarm.terminal_commands.status import (
    cmd_status,
    cmd_runtime_status,
    cmd_mission_status,
    cmd_mission_brief,
    cmd_campaign_brief,
    cmd_canonical_status,
)
from dharma_swarm.terminal_commands.diagnostics import (
    cmd_loops,
    cmd_invariants,
    cmd_transcendence,
    cmd_health,
    cmd_health_check,
    cmd_doctor,
    cmd_ui,
    cmd_pulse,
    cmd_organism_pulse,
    cmd_daemon_status,
)
from dharma_swarm.terminal_commands.intent import (
    cmd_intent_plan,
    cmd_system_map,
)
from dharma_swarm.terminal_commands.lifecycle import (
    cmd_up,
    cmd_down,
    cmd_orchestrate_live,
    cmd_swarm,
    cmd_stress,
    cmd_full_power_probe,
    cmd_setup,
    cmd_migrate,
)
from dharma_swarm.terminal_commands.evolution import (
    cmd_evolve_propose,
    cmd_evolve_trend,
    cmd_evolve_apply,
    cmd_evolve_promote,
    cmd_evolve_rollback,
    cmd_evolve_auto,
    cmd_evolve_daemon,
)
from dharma_swarm.terminal_commands.agents import (
    cmd_spawn,
    _cmd_agent_wake,
    _cmd_agent_list,
    _cmd_agent_runs,
    _cmd_agent_talk,
    _cmd_agent_run,
    _cmd_agent_status,
    _cmd_agent_kill,
    cmd_task_create,
    cmd_task_list,
)
from dharma_swarm.terminal_commands.memory import (
    cmd_memory,
    cmd_context,
    cmd_context_search,
    cmd_witness,
    cmd_develop,
    cmd_agent_memory,
)
from dharma_swarm.terminal_commands.governance import (
    cmd_gates,
    cmd_dharma_status,
    cmd_dharma_corpus,
    cmd_dharma_review,
    cmd_foundations,
    cmd_telos,
    cmd_custodians,
)
from dharma_swarm.terminal_commands.data_loop import (
    cmd_flywheel_jobs,
    cmd_flywheel_export,
    cmd_flywheel_record,
    cmd_flywheel_start,
    cmd_flywheel_get,
    cmd_flywheel_cancel,
    cmd_flywheel_delete,
    cmd_flywheel_watch,
    cmd_reciprocity_health,
    cmd_reciprocity_summary,
    cmd_reciprocity_publish,
    cmd_reciprocity_record,
)
from dharma_swarm.terminal_commands.ouroboros import (
    cmd_ouroboros_connections,
    cmd_ouroboros_record,
    cmd_ledger,
)
from dharma_swarm.terminal_commands.semantic import (
    cmd_semantic_digest,
    cmd_semantic_research,
    cmd_semantic_synthesize,
    cmd_semantic_harden,
    cmd_semantic_brief,
    cmd_semantic_proof,
    cmd_semantic_status,
    cmd_rag_health,
    cmd_rag_search,
    cmd_rag_chat,
)
from dharma_swarm.terminal_commands.stigmergy import (
    cmd_stigmergy,
    cmd_hum,
    cmd_cascade,
    cmd_forge,
)
from dharma_swarm.terminal_commands.surfaces import (
    cmd_tui,
    cmd_chat,
)
from dharma_swarm.terminal_commands.operator import (
    cmd_cron,
    cmd_sprint,
    cmd_run,
    cmd_foreman,
    cmd_review,
    cmd_initiatives,
)
from dharma_swarm.terminal_commands.infrastructure import (
    cmd_agni,
    cmd_model,
    cmd_model_catalog,
    cmd_free_fleet,
    cmd_provider_smoke,
    cmd_provider_matrix,
    cmd_gateway,
    cmd_bootstrap,
    cmd_route,
    cmd_autonomy,
    cmd_compose,
    cmd_execute_compose,
    cmd_handoff,
)
from dharma_swarm.terminal_commands.meta import (
    cmd_xray,
    _run_prune,
    _run_meta,
    cmd_skills,
    cmd_cross,
    cmd_orchestrate,
    cmd_field_scan,
    cmd_field_gaps,
    cmd_field_position,
    cmd_field_unique,
    cmd_field_summary,
)

# Backward-compat re-exports: tests access internal helpers via cli.*
import subprocess  # noqa: F811 — tests patch dgc_cli.subprocess

from dharma_swarm.terminal_commands._helpers import (  # noqa: F811
    DGC_CORE,
    _load_ouroboros_observation,
    _run,
)
from dharma_swarm.terminal_commands._status_helpers import (  # noqa: F811
    _accelerator_mode,
    _core_mission_checks,
    _read_openclaw_summary,
    _tracked_paths,
)
from dharma_swarm.terminal_commands.surfaces import (  # noqa: F811
    _build_chat_context_snapshot,
)
from dharma_swarm.terminal_commands.data_loop import (  # noqa: F811
    _flywheel_export_payload,
    _flywheel_record_payload,
    _reciprocity_publish_payload,
    _reciprocity_record_payload,
)
from dharma_swarm.terminal_commands.ouroboros import (  # noqa: F811
    _ouroboros_record_payload,
)


_ENV_BOOTSTRAPPED = False


def _runtime_env_paths() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".zshrc",
        home / ".env",
        home / ".dharma" / ".env",
        home / ".dharma" / "daemon.env",
        home / ".dharma" / "agent_keys.env",
    )


def _bootstrap_env() -> None:
    """Load local runtime env once, then normalize dkeys aliases."""
    global _ENV_BOOTSTRAPPED

    from dharma_swarm.api_keys import bootstrap_runtime_env

    should_load_files = not bool(os.environ.get("PYTEST_CURRENT_TEST")) or (
        os.environ.get("DGC_TEST_ENABLE_ENV_BOOTSTRAP", "").strip() == "1"
    )
    should_force = not _ENV_BOOTSTRAPPED
    _ENV_BOOTSTRAPPED = True
    bootstrap_runtime_env(
        env_paths=_runtime_env_paths(),
        include_files=should_load_files,
        force=should_force,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dgc",
        description="DGC -- Dharmic Godel Claw unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # -- living map --
    p_map = sub.add_parser("map", help="Living map — all 8 layers, regenerated fresh from live sources")
    p_map.add_argument("--json", action="store_true", help="JSON output")
    p_map.add_argument("--layer", type=int, default=None, help="Single layer (0-7)")
    map_sub = p_map.add_subparsers(dest="map_cmd")
    p_map_list = map_sub.add_parser("list", help="List organs from reports/system_map/latest.json")
    p_map_list.add_argument("--path", default="reports/system_map/latest.json")
    p_map_list.add_argument("--json", dest="system_map_json_output", action="store_true")
    p_map_drifted = map_sub.add_parser("drifted", help="List drifted/partial/unknown organs")
    p_map_drifted.add_argument("--path", default="reports/system_map/latest.json")
    p_map_drifted.add_argument("--json", dest="system_map_json_output", action="store_true")
    p_map_gaps = map_sub.add_parser("gaps", help="List next bindable gaps")
    p_map_gaps.add_argument("--path", default="reports/system_map/latest.json")
    p_map_gaps.add_argument("--json", dest="system_map_json_output", action="store_true")
    p_map_show = map_sub.add_parser("show", help="Show one organ from reports/system_map/latest.json")
    p_map_show.add_argument("organ")
    p_map_show.add_argument("--path", default="reports/system_map/latest.json")
    p_map_show.add_argument("--json", dest="system_map_json_output", action="store_true")

    # -- status --
    p_status = sub.add_parser("status", help="System status overview")
    p_status.add_argument("--json", action="store_true", help="Emit JSON output")
    p_runtime = sub.add_parser("runtime-status", help="Canonical runtime control-plane summary")
    p_runtime.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of recent rows to show for active runs/artifacts/actions",
    )
    p_runtime.add_argument(
        "--db-path",
        default=None,
        help="Override runtime SQLite path (defaults to ~/.dharma/state/runtime.db)",
    )
    p_runtime.add_argument("--json", action="store_true", help="Emit JSON output")
    p_mission = sub.add_parser("mission-status", help="Mission readiness lanes + gap report")
    p_mission.add_argument("--json", action="store_true", help="Emit JSON report")
    p_mission.add_argument(
        "--strict-core",
        action="store_true",
        help="Exit non-zero if core lane is not fully wired",
    )
    p_mission.add_argument(
        "--require-tracked",
        action="store_true",
        help="Exit non-zero if mission-critical files are local-only",
    )
    p_mission.add_argument(
        "--profile",
        choices=sorted(MISSION_AUTONOMY_PROFILES),
        default=None,
        help=(
            "Apply autonomy profile defaults for strict checks "
            "(strict-core/require-tracked)."
        ),
    )
    p_mbrief = sub.add_parser("mission-brief", help="Show active mission continuity state")
    p_mbrief.add_argument("--json", action="store_true", help="Emit mission continuity as JSON")
    p_mbrief.add_argument(
        "--path",
        default=None,
        help="Explicit path to mission.json or thinkodynamic latest.json",
    )
    p_mbrief.add_argument(
        "--state-dir",
        default=None,
        help="Override state root (defaults to ~/.dharma)",
    )
    p_cbrief = sub.add_parser("campaign-brief", help="Show active campaign continuity state")
    p_cbrief.add_argument("--json", action="store_true", help="Emit campaign continuity as JSON")
    p_cbrief.add_argument(
        "--path",
        default=None,
        help="Explicit path to campaign.json",
    )
    p_cbrief.add_argument(
        "--state-dir",
        default=None,
        help="Override state root (defaults to ~/.dharma)",
    )
    p_canonical = sub.add_parser("canonical-status", help="Show canonical DGC/SAB repo topology")
    p_canonical.add_argument("--json", action="store_true", help="Emit JSON report")

    # -- value-events --
    p_ve = sub.add_parser("value-events", help="List operator_brief ValueEvents grouped by agent")
    p_ve.add_argument("--since", required=True, help="Show events since date (YYYY-MM-DD or ISO-8601)")
    p_ve.add_argument("--json", action="store_true", help="Emit JSON output")
    p_ve.add_argument("--registry-path", default=None, help="Override ontology registry path")

    # -- trace-attractor --
    p_trace = sub.add_parser(
        "trace-attractor",
        help="Project a trace_id into an operator-visible AttractorPacket",
    )
    p_trace.add_argument("--trace-id", required=True, help="Trace identifier to project")
    p_trace.add_argument("--json", action="store_true", help="Emit deterministic JSON output")
    p_trace.add_argument("--registry-path", default=None, help="Override ontology registry path")
    p_trace.add_argument("--runtime-db", default=None, help="Override runtime SQLite path")
    p_trace.add_argument("--telemetry-db", default=None, help="Override telemetry SQLite path")
    p_trace.add_argument("--board-db", default=None, help="Optional BoardStore event-log SQLite path")
    p_trace.add_argument("--sakshi-log", default=None, help="Optional Sakshi provenance JSONL path")

    # -- chat --
    p_chat = sub.add_parser("chat", help="Launch native Claude Code interactive UI")
    p_chat.add_argument(
        "-c",
        "--continue",
        dest="continue_last",
        action="store_true",
        help="Continue the most recent Claude session in this directory",
    )
    p_chat.add_argument(
        "--offline",
        action="store_true",
        help="Disable nonessential network traffic for Claude session",
    )
    p_chat.add_argument("--model", default=None, help="Claude model alias/name")
    p_chat.add_argument(
        "--effort",
        choices=["low", "medium", "high"],
        default=None,
        help="Reasoning effort level",
    )
    p_chat.add_argument(
        "--no-context",
        action="store_true",
        help="Do not append DGC state snapshot to Claude system prompt",
    )

    # -- dashboard --
    sub.add_parser("dashboard", help="Launch DGC dashboard (TUI)")

    # -- ui --
    p_ui = sub.add_parser("ui", help="Show canonical operator-surface launch paths")
    p_ui.add_argument(
        "surface",
        nargs="?",
        default="list",
        choices=("list", "tui", "api", "next", "lens"),
        help="Surface to describe: list, tui, api, next, or lens",
    )

    # -- up --
    p_up = sub.add_parser("up", help="Start the daemon")
    p_up.add_argument("--background", action="store_true")

    # -- down --
    sub.add_parser("down", help="Stop the daemon")

    # -- daemon-status --
    sub.add_parser("daemon-status", help="Show daemon state")

    # -- pulse --
    sub.add_parser("pulse", help="Run one heartbeat pulse")

    # -- organism-pulse (the canonical 9-stage heartbeat) --
    p_org_pulse = sub.add_parser(
        "organism-pulse",
        help="Run one canonical organism pulse (sense→constrain→execute→evaluate→adapt)",
    )
    p_org_pulse.add_argument("--task", type=str, default=None, help="Task to execute")
    p_org_pulse.add_argument("--dry-run", action="store_true", help="Health-only, no execution")

    # -- invariants --
    sub.add_parser("invariants", help="Show the 4 computable system invariants")

    # -- transcendence --
    sub.add_parser("transcendence", help="Show transcendence metrics (ensemble vs individual)")

    # -- orchestrate-live --
    p_orch_live = sub.add_parser(
        "orchestrate-live",
        help="Run all DGC systems concurrently (live orchestrator)",
    )
    p_orch_live.add_argument("--background", action="store_true", help="Run in background")

    # -- swarm (captures all remaining args) --
    p_swarm = sub.add_parser("swarm", help="Swarm orchestrator + overnight/live")
    p_swarm.add_argument("swarm_args", nargs="*", default=[])

    # -- stress --
    p_stress = sub.add_parser("stress", help="Run max-capacity DGC stress harness")
    p_stress.add_argument("--profile", choices=["quick", "full", "max"], default="full")
    p_stress.add_argument("--state-dir", default=str(HOME / ".dharma" / "stress_lab"))
    p_stress.add_argument(
        "--provider-mode",
        choices=["auto", "mock", "claude", "codex", "openrouter"],
        default="auto",
    )
    p_stress.add_argument("--agents", type=int, default=8)
    p_stress.add_argument("--tasks", type=int, default=36)
    p_stress.add_argument("--evolutions", type=int, default=24)
    p_stress.add_argument("--evolution-concurrency", type=int, default=6)
    p_stress.add_argument("--cli-rounds", type=int, default=2)
    p_stress.add_argument("--cli-concurrency", type=int, default=8)
    p_stress.add_argument("--orchestration-timeout-sec", type=int, default=240)
    p_stress.add_argument("--external-timeout-sec", type=int, default=120)
    p_stress.add_argument("--external-research", action="store_true")
    p_probe = sub.add_parser(
        "full-power-probe",
        aliases=["probe"],
        help="Run the reusable operator-facing full-power probe",
    )
    p_probe.add_argument(
        "--route-task",
        default="test the full power of dgc from inside the system and show what it can do",
    )
    p_probe.add_argument(
        "--context-search-query",
        default="mechanistic thread reports unfinished work active modules evidence paths",
    )
    p_probe.add_argument(
        "--compose-task",
        default=(
            "Probe DGC full power from inside this workspace, verify the mechanistic "
            "thread snapshot, and produce a concrete artifact"
        ),
    )
    p_probe.add_argument(
        "--autonomy-action",
        default="run a broad but safe local full-power probe without mutating external systems",
    )
    p_probe.add_argument("--skip-sprint-probe", action="store_true")
    p_probe.add_argument("--skip-stress", action="store_true")
    p_probe.add_argument("--skip-pytest", action="store_true")

    p_provider = sub.add_parser("provider-smoke", help="Probe local and external provider lanes")
    p_provider.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p_provider.add_argument("--ollama-model", default=None, help="Override Ollama model")
    p_provider.add_argument("--nim-model", default=None, help="Override NVIDIA NIM model")
    p_provider.add_argument(
        "--qwen-provider",
        default=None,
        help="Force a Qwen3.5 Surgical Coder dashboard smoke against a specific provider",
    )
    p_provider.add_argument(
        "--qwen-task",
        default=None,
        help="Override the read-only Qwen dashboard smoke task",
    )
    p_provider.add_argument(
        "--telemetry-db",
        default=None,
        help="Persist probe outcomes into the canonical telemetry DB at this path",
    )
    p_matrix = sub.add_parser(
        "provider-matrix",
        help="Run the live provider/model matrix harness",
    )
    p_matrix.add_argument("--profile", choices=["quick", "live25"], default="live25")
    p_matrix.add_argument("--corpus", choices=["deployment", "workspace"], default="deployment")
    p_matrix.add_argument("--max-targets", type=int, default=None)
    p_matrix.add_argument("--max-prompts", type=int, default=None)
    p_matrix.add_argument("--timeout-seconds", type=float, default=45.0)
    p_matrix.add_argument("--concurrency", type=int, default=4)
    p_matrix.add_argument("--budget-units", type=int, default=40)
    p_matrix.add_argument("--artifact-dir", default=None)
    p_matrix.add_argument("--include-unavailable", action="store_true")
    p_matrix.add_argument("--no-artifacts", action="store_true")
    p_matrix.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # -- context --
    p_ctx = sub.add_parser("context", help="Load context for a domain")
    p_ctx.add_argument("domain", nargs="?", default="all")

    # -- memory --
    p_mem = sub.add_parser("memory", help="Common memory surface")
    p_mem.add_argument("--top-k", type=int, default=5, help="Maximum retrieval hits for query/common/gate")
    p_mem.add_argument("--json", action="store_true", help="Emit JSON for supported memory modes")
    mem_sub = p_mem.add_subparsers(dest="memory_cmd")
    p_mem_status = mem_sub.add_parser("status", help="Show common memory status")
    # SUPPRESS keeps the parent-level --json value when the trailing flag is absent
    p_mem_status.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Emit JSON status"
    )
    p_mem_query = mem_sub.add_parser("query", help="Query common governed memory")
    p_mem_query.add_argument("memory_query", nargs="+")
    p_mem_common = mem_sub.add_parser("common", help="Build an agent handoff memory pack")
    p_mem_common.add_argument("memory_task", nargs="+")
    p_mem_brief = mem_sub.add_parser("brief", help="Alias for memory common")
    p_mem_brief.add_argument("memory_task", nargs="+")
    mem_sub.add_parser("ingest", help="Backfill live wiki concepts into common memory")
    mem_sub.add_parser("gate", help="Run the common memory system gate")
    mem_sub.add_parser("metabolize", help="Run ingest + gates and write a metabolism receipt")
    p_mem_schedule = mem_sub.add_parser("schedule", help="Register recurring Memory Common metabolism")
    p_mem_schedule.add_argument(
        "--schedule",
        default="every 24h",
        help="Recurring cron schedule for Memory Common metabolism",
    )

    # -- witness --
    p_wit = sub.add_parser("witness", help="Record a witness observation")
    p_wit.add_argument("message", nargs="+")

    # -- develop --
    p_dev = sub.add_parser("develop", help="Record a development marker")
    p_dev.add_argument("what", help="What was developed")
    p_dev.add_argument("evidence", nargs="+", help="Evidence")

    # -- gates --
    p_gates = sub.add_parser("gates", help="Run telos gates on an action")
    p_gates.add_argument("action", nargs="+")
    p_gates.add_argument("--json", action="store_true", help="Emit JSON output")

    # -- health --
    p_health = sub.add_parser("health", help="Ecosystem file health")
    p_health.add_argument("--json", action="store_true", help="Emit JSON output")

    # -- health-check (v0.2.0 monitor) --
    sub.add_parser("health-check", help="Monitor-based system health check")

    # -- verify-baseline (claude_hooks bridge) --
    sub.add_parser("verify-baseline", help="Full baseline verification (gates + health)")

    # -- doctor --
    p_doc = sub.add_parser("doctor", help="Deep runtime diagnostics and fix guidance")
    p_doc.add_argument(
        "doctor_action",
        nargs="?",
        default="run",
        choices=("run", "latest", "schedule", "watch"),
        help="Doctor action: run (default), latest, schedule, or watch",
    )
    p_doc.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p_doc.add_argument("--strict", action="store_true", help="Exit non-zero on WARN")
    p_doc.add_argument("--quick", action="store_true", help="Skip deep network/package probes")
    p_doc.add_argument("--timeout", type=float, default=1.5, help="Probe timeout seconds")
    p_doc.add_argument(
        "--schedule",
        default="every 6h",
        help="Recurring schedule for `dgc doctor schedule`",
    )
    p_doc.add_argument(
        "--interval-sec",
        type=float,
        default=1800.0,
        help="Loop interval seconds for `dgc doctor watch`",
    )
    p_doc.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Optional max iterations for `dgc doctor watch`",
    )

    # -- setup --
    sub.add_parser("setup", help="Install dependencies")

    # -- migrate --
    sub.add_parser("migrate", help="Migrate old DGC memory")

    # -- model --
    p_model = sub.add_parser("model", help="Model management and switching")
    p_model.add_argument("action", nargs="?", default="status",
                         help="Action: status (default), list, or model alias (opus/sonnet/haiku/gpt-4o)")

    # -- agni --
    p_agni = sub.add_parser("agni", help="Run command on AGNI VPS")
    p_agni.add_argument("remote_cmd", nargs="+")

    # -- spawn --
    p_spawn = sub.add_parser("spawn", help="Spawn a new agent")
    p_spawn.add_argument("--name", required=True)
    p_spawn.add_argument("--role", default="general")
    p_spawn.add_argument("--model", default="anthropic/claude-opus-4-6")

    # -- agent (autonomous agents with tool use) --
    p_agent = sub.add_parser("agent", help="Autonomous agents with multi-step reasoning and tool use")
    agent_sub = p_agent.add_subparsers(dest="agent_cmd")

    p_agent_wake = agent_sub.add_parser("wake", help="Wake an agent with a task")
    p_agent_wake.add_argument("name", help="Agent name (researcher/coder/scout/reviewer/witness or custom)")
    p_agent_wake.add_argument("--task", "-t", required=True, help="Task for the agent")
    p_agent_wake.add_argument("--model", "-m", default=None, help="Override model")

    agent_sub.add_parser("list", help="List available preset agents")

    agent_sub.add_parser("runs", help="Show recent agent run reports")

    p_agent_talk = agent_sub.add_parser(
        "talk",
        help="Talk to a registered sovereign holon (read-only)",
    )
    p_agent_talk.add_argument("name", help="Registered holon name, e.g. opus_composer")
    p_agent_talk.add_argument("message", nargs="+", help="Message for the holon")
    p_agent_talk.add_argument(
        "--mode",
        choices=("declared-first", "free-first"),
        default="declared-first",
        help="Routing mode: identity-declared model first, or explicit free-first chain",
    )
    p_agent_talk.add_argument("--max-tokens", type=int, default=400)

    p_agent_run = agent_sub.add_parser(
        "run",
        help="Run governed wake cycles for a registered sovereign holon",
    )
    p_agent_run.add_argument("name", help="Registered holon name, e.g. opus_composer")
    p_agent_run.add_argument("--cycles", "-n", type=int, default=1)
    p_agent_run.add_argument(
        "--mode",
        choices=("declared-first", "free-first"),
        default="declared-first",
        help="Routing mode: identity-declared model first, or explicit free-first chain",
    )

    p_agent_status = agent_sub.add_parser(
        "status",
        help="Read-only holon health/status projection",
    )
    p_agent_status.add_argument("name", nargs="?", default=None)
    p_agent_status.add_argument("--json", action="store_true", help="Emit JSON output")

    p_agent_kill = agent_sub.add_parser(
        "kill",
        help="Raise (or clear) the durable kill signal for a registered holon",
    )
    p_agent_kill.add_argument("name", help="Registered holon name, e.g. opus_composer")
    p_agent_kill.add_argument("--reason", default="", help="Why the holon is being halted")
    p_agent_kill.add_argument("--clear", action="store_true", help="Clear an existing kill signal")

    # -- task --
    p_task = sub.add_parser("task", help="Task management")
    task_sub = p_task.add_subparsers(dest="task_cmd")

    p_tc = task_sub.add_parser("create", help="Create a task")
    p_tc.add_argument("title")
    p_tc.add_argument("--description", default="")
    p_tc.add_argument("--priority", default="normal")

    p_tl = task_sub.add_parser("list", help="List tasks")
    p_tl.add_argument("--status", dest="status_filter", default=None)

    # -- evolve --
    p_evolve = sub.add_parser("evolve", help="Evolution engine commands")
    evolve_sub = p_evolve.add_subparsers(dest="evolve_cmd")

    p_ep = evolve_sub.add_parser("propose", help="Propose an evolution")
    p_ep.add_argument("component", help="Module or file being changed")
    p_ep.add_argument("description", help="Description of the change")
    p_ep.add_argument("--change-type", default="mutation")
    p_ep.add_argument("--diff", default="")

    p_et = evolve_sub.add_parser("trend", help="Show fitness trend")
    p_et.add_argument("--component", default=None)

    p_ea = evolve_sub.add_parser("apply", help="Apply evolution with sandbox")
    p_ea.add_argument("component")
    p_ea.add_argument("description")

    p_epr = evolve_sub.add_parser("promote", help="Promote a canary")
    p_epr.add_argument("entry_id")

    p_erb = evolve_sub.add_parser("rollback", help="Rollback a deployment")
    p_erb.add_argument("entry_id")
    p_erb.add_argument("--reason", default="Manual rollback")

    p_eauto = evolve_sub.add_parser("auto", help="LLM-powered autonomous evolution")
    p_eauto.add_argument("--files", nargs="*", help="Source files to evolve (default: core modules)")
    p_eauto.add_argument("--model", default="")
    p_eauto.add_argument("--context", default="", help="Focus area or context for the LLM")
    p_eauto.add_argument("--single-model", action="store_true", help="Use only --model instead of full roster")
    p_eauto.add_argument("--shadow", action="store_true", default=True, help="Dry-run: generate proposals but don't apply diffs")
    p_eauto.add_argument("--token-budget", type=int, default=0, help="Max tokens per session (0=unlimited)")

    p_edaemon = evolve_sub.add_parser("daemon", help="Run continuous autonomous evolution")
    p_edaemon.add_argument("--interval", type=float, default=1800.0, help="Seconds between cycles (default: 30min)")
    p_edaemon.add_argument("--threshold", type=float, default=0.6, help="Min fitness to auto-commit")
    p_edaemon.add_argument("--model", default="")
    p_edaemon.add_argument("--cycles", type=int, default=None, help="Max cycles (default: infinite)")
    p_edaemon.add_argument("--single-model", action="store_true", help="Use only --model instead of full roster")
    p_edaemon.add_argument("--shadow", action="store_true", default=True, help="Dry-run: generate proposals but don't apply diffs")
    p_edaemon.add_argument("--token-budget", type=int, default=0, help="Max tokens per session (0=unlimited)")

    # -- dharma --
    p_dharma = sub.add_parser("dharma", help="Dharma subsystem commands")
    dharma_sub = p_dharma.add_subparsers(dest="dharma_cmd")

    dharma_sub.add_parser("status", help="Dharma subsystem status")

    p_dc = dharma_sub.add_parser("corpus", help="List corpus claims")
    p_dc.add_argument("--status", dest="corpus_status", default=None)
    p_dc.add_argument("--category", dest="corpus_category", default=None)

    p_dr = dharma_sub.add_parser("review", help="Review a claim")
    p_dr.add_argument("claim_id")

    # -- stigmergy --
    p_stig = sub.add_parser("stigmergy", help="Stigmergy marks and hot paths")
    p_stig.add_argument("--file", dest="stig_file", default=None)
    p_stig.add_argument("--json", action="store_true", help="Emit JSON output")

    # -- hum --
    sub.add_parser("hum", help="Subconscious associations")

    # -- cascade --
    p_cascade = sub.add_parser("cascade", help="Run strange loop cascade domain")
    p_cascade.add_argument("domain", nargs="?", default="code",
                           help="Domain: code, skill, product, research, meta, all")
    p_cascade.add_argument("--seed-path", default=None, help="Path to seed file")
    p_cascade.add_argument("--seed-skill", default=None, help="Skill name to seed")
    p_cascade.add_argument("--seed-project", default=None, help="Project directory to seed (product domain)")
    p_cascade.add_argument("--track", default=None, help="Research track: rv, phoenix, contemplative")
    p_cascade.add_argument("--max-iter", type=int, default=None, help="Override max iterations")

    # -- forge --
    p_forge = sub.add_parser("forge", help="Score artifact through quality forge")
    p_forge.add_argument("path", nargs="?", default=None, help="Path to score (or 'self')")
    p_forge.add_argument("--batch", default=None, help="Score all files in directory")

    # -- loops --
    sub.add_parser("loops", help="Show strange loop status and cascade history")

    # -- run --
    p_run = sub.add_parser("run", help="Run orchestration loop")
    p_run.add_argument("--interval", type=float, default=2.0)

    # -- rag --
    p_rag = sub.add_parser("rag", help="NVIDIA RAG integration commands")
    rag_sub = p_rag.add_subparsers(dest="rag_cmd")

    p_rh = rag_sub.add_parser("health", help="Check rag/ingestor health")
    p_rh.add_argument(
        "--service",
        choices=["rag", "ingest"],
        default="rag",
    )
    p_rh.add_argument(
        "--no-deps",
        action="store_true",
        help="Skip dependency checks",
    )

    p_rs = rag_sub.add_parser("search", help="Query RAG search endpoint")
    p_rs.add_argument("query", nargs="+")
    p_rs.add_argument("--top-k", type=int, default=5)
    p_rs.add_argument("--collection", default=None)

    p_rc = rag_sub.add_parser("chat", help="Run grounded chat completion")
    p_rc.add_argument("prompt", nargs="+")
    p_rc.add_argument("--model", default=None)

    # -- flywheel --
    p_fw = sub.add_parser("flywheel", help="NVIDIA Data Flywheel commands")
    fw_sub = p_fw.add_subparsers(dest="flywheel_cmd")

    fw_sub.add_parser("jobs", help="List flywheel jobs")

    p_fwe = fw_sub.add_parser("export", help="Build a local canonical flywheel export")
    p_fwe.add_argument("--run-id", required=True)
    p_fwe.add_argument("--workload-id", required=True)
    p_fwe.add_argument("--client-id", required=True)
    p_fwe.add_argument("--trace-id", default=None)
    p_fwe.add_argument("--db-path", default=None)
    p_fwe.add_argument("--event-log-dir", default=None)
    p_fwe.add_argument("--export-root", default=None)

    p_fwr = fw_sub.add_parser("record", help="Record a flywheel job result into canonical runtime truth")
    p_fwr.add_argument("job_id")
    p_fwr.add_argument("--workload-id", default=None)
    p_fwr.add_argument("--client-id", default=None)
    p_fwr.add_argument("--run-id", default=None)
    p_fwr.add_argument("--session-id", default=None)
    p_fwr.add_argument("--task-id", default=None)
    p_fwr.add_argument("--trace-id", default=None)
    p_fwr.add_argument("--db-path", default=None)
    p_fwr.add_argument("--event-log-dir", default=None)
    p_fwr.add_argument("--workspace-root", default=None)
    p_fwr.add_argument("--provenance-root", default=None)

    p_fws = fw_sub.add_parser("start", help="Start a flywheel job")
    p_fws.add_argument("--workload-id", required=True)
    p_fws.add_argument("--client-id", required=True)
    p_fws.add_argument("--eval-size", type=int, default=20)
    p_fws.add_argument("--val-ratio", type=float, default=0.1)
    p_fws.add_argument("--min-total-records", type=int, default=50)
    p_fws.add_argument("--limit", type=int, default=10000)
    p_fws.add_argument("--run-id", default=None)
    p_fws.add_argument("--trace-id", default=None)
    p_fws.add_argument("--db-path", default=None)
    p_fws.add_argument("--event-log-dir", default=None)
    p_fws.add_argument("--export-root", default=None)

    p_fwg = fw_sub.add_parser("get", help="Get flywheel job details")
    p_fwg.add_argument("job_id")

    p_fwc = fw_sub.add_parser("cancel", help="Cancel flywheel job")
    p_fwc.add_argument("job_id")

    p_fwd = fw_sub.add_parser("delete", help="Delete flywheel job")
    p_fwd.add_argument("job_id")

    p_fww = fw_sub.add_parser("watch", help="Wait for job completion")
    p_fww.add_argument("job_id")
    p_fww.add_argument("--poll-sec", type=float, default=5.0)
    p_fww.add_argument("--timeout-sec", type=float, default=1800.0)

    # -- reciprocity --
    p_recip = sub.add_parser(
        "reciprocity",
        help="Planetary Reciprocity Commons commands",
    )
    reciprocity_sub = p_recip.add_subparsers(dest="reciprocity_cmd")

    reciprocity_sub.add_parser("health", help="Check reciprocity service health")
    reciprocity_sub.add_parser("summary", help="Fetch the current ledger summary")

    p_recp = reciprocity_sub.add_parser(
        "publish",
        help="Publish a reciprocity record to the service",
    )
    p_recp.add_argument(
        "publish_type",
        choices=["activity", "obligation", "project", "outcome"],
    )
    p_recp_payload = p_recp.add_mutually_exclusive_group(required=True)
    p_recp_payload.add_argument(
        "--json",
        dest="publish_json",
        default=None,
        help="Inline JSON object payload",
    )
    p_recp_payload.add_argument(
        "--file",
        dest="publish_file",
        default=None,
        help="Path to a JSON payload file",
    )

    p_recr = reciprocity_sub.add_parser(
        "record",
        help="Record the current reciprocity ledger summary into canonical runtime truth",
    )
    p_recr.add_argument("--run-id", default=None)
    p_recr.add_argument("--session-id", default=None)
    p_recr.add_argument("--task-id", default=None)
    p_recr.add_argument("--trace-id", default=None)
    p_recr.add_argument("--summary-type", default="ledger_summary")
    p_recr_payload = p_recr.add_mutually_exclusive_group(required=False)
    p_recr_payload.add_argument(
        "--json",
        dest="record_json",
        default=None,
        help="Inline JSON ledger summary payload to record instead of fetching live",
    )
    p_recr_payload.add_argument(
        "--file",
        dest="record_file",
        default=None,
        help="Path to a JSON ledger summary payload file to record instead of fetching live",
    )
    p_recr.add_argument("--db-path", default=None)
    p_recr.add_argument("--event-log-dir", default=None)
    p_recr.add_argument("--workspace-root", default=None)
    p_recr.add_argument("--provenance-root", default=None)

    # -- ouroboros --
    p_ouro = sub.add_parser("ouroboros", help="Behavioral self-observation tools")
    ouro_sub = p_ouro.add_subparsers(dest="ouroboros_cmd")

    p_ouro_conn = ouro_sub.add_parser(
        "connections",
        help="Profile module docstrings and surface H0/H1 behavioral structure",
    )
    p_ouro_conn.add_argument("--package-dir", default=None)
    p_ouro_conn.add_argument("--threshold", type=float, default=0.08)
    p_ouro_conn.add_argument("--disagreement-threshold", type=float, default=0.1)
    p_ouro_conn.add_argument("--min-text-length", type=int, default=50)
    p_ouro_conn.add_argument("--limit", type=int, default=15)
    p_ouro_conn.add_argument("--json", dest="as_json", action="store_true")

    p_ouro_record = ouro_sub.add_parser(
        "record",
        help="Record the latest ouroboros observation into canonical runtime truth",
    )
    p_ouro_record.add_argument("--run-id", default=None)
    p_ouro_record.add_argument("--session-id", default=None)
    p_ouro_record.add_argument("--task-id", default=None)
    p_ouro_record.add_argument("--trace-id", default=None)
    p_ouro_record.add_argument("--log-path", default=None)
    p_ouro_record.add_argument("--cycle-id", default=None)
    p_ouro_record_payload = p_ouro_record.add_mutually_exclusive_group(required=False)
    p_ouro_record_payload.add_argument(
        "--json",
        dest="observation_json",
        default=None,
        help="Inline JSON ouroboros observation payload to record instead of reading the log",
    )
    p_ouro_record_payload.add_argument(
        "--file",
        dest="observation_file",
        default=None,
        help="Path to a JSON ouroboros observation payload file to record instead of reading the log",
    )
    p_ouro_record.add_argument("--db-path", default=None)
    p_ouro_record.add_argument("--event-log-dir", default=None)
    p_ouro_record.add_argument("--workspace-root", default=None)
    p_ouro_record.add_argument("--provenance-root", default=None)

    # -- eval --
    p_eval = sub.add_parser("eval", help="ECC eval harness — measure system health")
    eval_sub = p_eval.add_subparsers(dest="eval_cmd")
    eval_sub.add_parser("run", help="Run all evals and print scorecard")
    eval_sub.add_parser("report", help="Print latest eval report")
    eval_sub.add_parser("trend", help="Show historical pass rates")
    eval_sub.add_parser("dashboard", help="Single-screen eval dashboard")

    # -- self-improve --
    p_si = sub.add_parser("self-improve", help="Self-improvement cycle — strange loop")
    si_sub = p_si.add_subparsers(dest="si_cmd")
    si_sub.add_parser("status", help="Show self-improvement status")
    si_sub.add_parser("history", help="Show cycle history")
    si_sub.add_parser("run", help="Run one cycle manually (requires DHARMA_SELF_IMPROVE=1)")

    # -- log --
    p_log = sub.add_parser("log", help="Conversation log — what was said + promises")
    log_sub = p_log.add_subparsers(dest="log_cmd")
    log_sub.add_parser("recent", help="Show recent conversation entries (default)")
    log_sub.add_parser("promises", help="Show detected promises/commitments")
    log_sub.add_parser("stats", help="Conversation statistics")
    p_log_search = log_sub.add_parser("search", help="Search promises")
    p_log_search.add_argument("query", nargs="+", help="Search query")

    # -- audit --
    p_audit = sub.add_parser("audit", help="Harness audit — 7-dimension scorecard")
    audit_sub = p_audit.add_subparsers(dest="audit_cmd")
    audit_sub.add_parser("run", help="Run audit and print scorecard (default)")
    audit_sub.add_parser("trend", help="Show audit trend over time")

    # -- review --
    sub.add_parser("review", help="Review bridge — ruff findings as evolution proposals")

    # -- instincts --
    p_inst = sub.add_parser("instincts", help="Instinct bridge — ECC ↔ fitness signals")
    inst_sub = p_inst.add_subparsers(dest="instinct_cmd")
    inst_sub.add_parser("status", help="Show bridge status")
    inst_sub.add_parser("sync", help="Process new observations and emit signals")

    # -- loop-status --
    sub.add_parser("loop-status", help="Loop supervisor — health of all loops")

    # -- spine --
    p_spine = sub.add_parser("spine", help="Runtime truth spine — live EvidenceReceipt stream")
    spine_sub = p_spine.add_subparsers(dest="spine_cmd")
    p_spine_tail = spine_sub.add_parser(
        "tail", help="Tail the live EvidenceReceipt stream (one line per receipt)"
    )
    p_spine_tail.add_argument(
        "--limit", type=int, default=20, help="Number of receipts to show (default 20)"
    )
    p_spine_tail.add_argument(
        "--follow", action="store_true", help="Poll for new receipts every 2s until Ctrl-C"
    )

    # -- skills --
    sub.add_parser("skills", help="List discovered skills (v0.4.0)")

    # -- route --
    p_route = sub.add_parser("route", help="Route a task to best skill (v0.4.0)")
    p_route.add_argument("task_desc", nargs="+", help="Task description")

    # -- orchestrate --
    p_orch = sub.add_parser("orchestrate", help="Decompose and orchestrate a task (v0.4.0)")
    p_orch.add_argument("orch_desc", nargs="+", help="Task description")

    # -- autonomy --
    p_auto = sub.add_parser("autonomy", help="Check autonomy for an action (v0.4.0)")
    p_auto.add_argument("auto_action", nargs="+", help="Action to check")

    # -- context-search --
    p_cs = sub.add_parser("context-search", help="Search for task-relevant context (v0.4.0)")
    p_cs.add_argument("cs_query", nargs="+", help="Search query")
    p_cs.add_argument("--budget", type=int, default=10000)

    # -- intent-plan --
    p_ip = sub.add_parser(
        "intent-plan",
        help="Inspect the intent-to-work-packet pipeline for a prompt (non-executing)",
    )
    p_ip.add_argument("ip_prompt", nargs="+", help="Operator prompt to analyze")
    p_ip.add_argument("--json", action="store_true", help="Emit JSON output (default)")

    # -- compose (v0.4.1) --
    p_comp = sub.add_parser("compose", help="Compose a task into DAG execution plan (v0.4.1)")
    p_comp.add_argument("comp_desc", nargs="+", help="Task description")

    # -- execute-compose (v0.4.2) --
    p_exec_comp = sub.add_parser("execute-compose", help="Compose and execute a task DAG end-to-end")
    p_exec_comp.add_argument("exec_comp_desc", nargs="+", help="Task description")

    # -- overnight (autonomous overnight loop) --
    p_overnight = sub.add_parser("overnight", help="Run overnight autonomous loop")
    p_overnight.add_argument("--hours", type=float, default=8.0, help="Duration in hours")
    p_overnight.add_argument("--dry-run", action="store_true", help="Simulate without real execution")
    p_overnight.add_argument("--autonomy", type=int, default=1, help="Autonomy level (0-3)")
    p_overnight.add_argument("--max-tokens", type=int, default=500_000, help="Token budget")
    p_overnight.add_argument("--cycle-timeout", type=float, default=900.0, help="Seconds per cycle")

    # -- handoff (v0.4.1) --
    p_ho = sub.add_parser("handoff", help="Create a structured agent handoff (v0.4.1)")
    p_ho.add_argument("--from", dest="ho_from", required=True, help="Source agent")
    p_ho.add_argument("--to", dest="ho_to", required=True, help="Target agent")
    p_ho.add_argument("--context", dest="ho_context", required=True, help="Task context")
    p_ho.add_argument("content", nargs="+", help="Handoff content")

    # -- agent-memory (v0.4.1) --
    p_am = sub.add_parser("agent-memory", help="Agent self-editing memory (v0.4.1)")
    p_am.add_argument("mem_agent", help="Agent name")

    # -- sprint --
    p_sprint = sub.add_parser("sprint", help="Generate today's adaptive 8-hour sprint prompt")
    p_sprint.add_argument(
        "--output", default=None, help="Output path (default: ~/.dharma/shared/SPRINT_8H_<date>.md)"
    )
    p_sprint.add_argument(
        "--local", action="store_true", help="Generate without LLM (offline mode)"
    )
    p_sprint.add_argument("--test-summary", default="", help="Test results to include")
    p_sprint.add_argument("--prev-todo", default="", help="Previous TODO items to include")
    p_sprint.add_argument(
        "--llm-timeout-sec",
        type=float,
        default=DEFAULT_SPRINT_LLM_TIMEOUT_SEC,
        help="Timeout for remote sprint prompt generation before local fallback",
    )

    # -- ledger --
    p_ledger = sub.add_parser("ledger", help="Inspect orchestrator session ledgers")
    ledger_sub = p_ledger.add_subparsers(dest="ledger_cmd")

    p_ledger_tail = ledger_sub.add_parser("tail", help="Show recent ledger events")
    p_ledger_tail.add_argument("-n", type=int, default=20, help="Number of events")
    p_ledger_tail.add_argument("--session", default=None, help="Session ID (default: most recent)")
    p_ledger_tail.add_argument(
        "--kind", choices=["task", "progress", "all"], default="all", help="Which ledger"
    )

    ledger_sub.add_parser("sessions", help="List recent sessions")
    p_ledger_search = ledger_sub.add_parser("search", help="Search indexed ledger events")
    p_ledger_search.add_argument("query", nargs="+", help="Search query")
    p_ledger_search.add_argument("-n", type=int, default=10, help="Number of matches")
    p_ledger_search.add_argument("--session", default=None, help="Limit search to one session ID")
    p_ledger_search.add_argument(
        "--kind", choices=["task", "progress", "all"], default="all", help="Which ledger"
    )
    p_ledger_search.add_argument("--db-path", default=None, help="Override runtime state DB path")
    p_ledger_search.add_argument(
        "--no-sync-ledgers",
        action="store_true",
        help="Skip ledger-dir reindex before searching",
    )
    p_ledger_search.add_argument(
        "--limit-sessions",
        type=int,
        default=None,
        help="Limit reindex to the most recent N sessions",
    )
    p_ledger_index = ledger_sub.add_parser("index", help="Index ledger JSONL into runtime search store")
    p_ledger_index.add_argument("--session", default=None, help="Index only one session ID")
    p_ledger_index.add_argument("--db-path", default=None, help="Override runtime state DB path")
    p_ledger_index.add_argument(
        "--limit-sessions",
        type=int,
        default=None,
        help="Limit indexing to the most recent N sessions",
    )

    # -- semantic --
    p_sem = sub.add_parser("semantic", help="Semantic Evolution Engine commands")
    sem_sub = p_sem.add_subparsers(dest="semantic_cmd")

    p_sd = sem_sub.add_parser("digest", help="Read codebase and build concept graph")
    p_sd.add_argument("--root", default=str(DHARMA_SWARM), help="Project root")
    p_sd.add_argument("--output", default=None, help="Graph output path")
    p_sd.add_argument(
        "--max-files",
        type=int,
        default=500,
        help="Safety cap on files processed during digest",
    )
    p_sd.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in the digest",
    )

    p_sr = sem_sub.add_parser("research", help="Annotate graph with external research")
    p_sr.add_argument("--graph", default=None, help="Path to concept graph JSON")

    p_ss = sem_sub.add_parser("synthesize", help="Generate file cluster specs")
    p_ss.add_argument("--graph", default=None, help="Path to concept graph JSON")
    p_ss.add_argument("--max-clusters", type=int, default=10)

    p_sh = sem_sub.add_parser("harden", help="Run 6-angle hardening on clusters")
    p_sh.add_argument("--graph", default=None, help="Path to concept graph JSON")
    p_sh.add_argument("--root", default=str(DHARMA_SWARM), help="Project root")

    p_sb = sem_sub.add_parser("brief", help="Compile semantic clusters into campaign briefs")
    p_sb.add_argument("--graph", default=None, help="Path to concept graph JSON")
    p_sb.add_argument("--root", default=str(DHARMA_SWARM), help="Project root")
    p_sb.add_argument("--max-briefs", type=int, default=3)
    p_sb.add_argument("--json-output", default=None, help="Output path for brief packet JSON")
    p_sb.add_argument("--markdown-output", default=None, help="Output path for brief packet markdown")
    p_sb.add_argument("--state-dir", default=None, help="Override state root for campaign updates")
    p_sb.add_argument("--campaign-path", default=None, help="Explicit campaign.json path")

    p_sst = sem_sub.add_parser("status", help="Semantic graph status overview")
    p_sst.add_argument("--graph", default=None, help="Path to concept graph JSON")

    p_sp = sem_sub.add_parser("proof", help="Run live end-to-end proof of the semantic pipeline")
    p_sp.add_argument("--root", default=str(DHARMA_SWARM), help="Project root")

    # -- bootstrap --
    sub.add_parser("bootstrap", help="Generate bootstrap manifest (NOW.json) — orients any new LLM instance")

    # -- field (D3: External AI Field Intelligence) --
    p_field = sub.add_parser("field", help="D3 External AI Field Intelligence Engine")
    field_sub = p_field.add_subparsers(dest="field_cmd")
    field_sub.add_parser("scan", help="Full D3 field intelligence scan with all reports")
    field_sub.add_parser("gaps", help="Show DGC capability gaps vs external field")
    field_sub.add_parser("position", help="Show DGC competitive positioning")
    field_sub.add_parser("unique", help="Show DGC unique moats")
    field_sub.add_parser("summary", help="Field KB summary statistics")

    # -- ginko (Shakti Ginko Economic Engine) --
    p_ginko = sub.add_parser("ginko", help="Shakti Ginko autonomous economic engine")
    ginko_sub = p_ginko.add_subparsers(dest="ginko_cmd")
    ginko_sub.add_parser("status", help="Ginko VentureCell status + Brier dashboard")
    ginko_sub.add_parser("dashboard", help="Full Brier score dashboard report")
    ginko_sub.add_parser("register-crons", help="Register Ginko cron jobs")
    ginko_sub.add_parser("edge", help="Check edge validation status")
    ginko_sub.add_parser("pull", help="Pull market data from all sources")
    ginko_sub.add_parser("signals", help="Generate signal report")
    p_ginko_predict = ginko_sub.add_parser("predict", help="Record a new prediction")
    p_ginko_predict.add_argument("question", help="Yes/no question to predict")
    p_ginko_predict.add_argument("probability", type=float, help="Probability of YES (0.0-1.0)")
    p_ginko_predict.add_argument("--category", default="general", help="Prediction category")
    p_ginko_predict.add_argument("--resolve-by", default=None, help="Resolution date (ISO format)")
    p_ginko_resolve = ginko_sub.add_parser("resolve", help="Resolve a prediction")
    p_ginko_resolve.add_argument("prediction_id", help="Prediction ID to resolve")
    p_ginko_resolve.add_argument("outcome", type=float, help="Outcome: 1.0=YES, 0.0=NO")
    ginko_sub.add_parser("brier", help="Show Brier score dashboard")
    ginko_sub.add_parser("report", help="Generate daily intelligence report")
    ginko_sub.add_parser("portfolio", help="Show paper portfolio status")
    ginko_sub.add_parser("cycle", help="Run full daily cycle")
    ginko_sub.add_parser("fleet", help="List all agents with status and fitness")

    # -- foundations (intellectual pillars and syntheses) --
    p_foundations = sub.add_parser("foundations", help="Intellectual pillars and syntheses")
    p_foundations.add_argument("pillar", nargs="?", default=None, help="Pillar name to preview")

    p_telos = sub.add_parser("telos", help="Telos Engine research documents")
    p_telos.add_argument("doc", nargs="?", default=None, help="Document name to preview")

    sub.add_parser("meta", help="Overseeing I — wholistic system assessment")

    p_prune = sub.add_parser("prune", help="Sweep the zen garden — cut noise, keep signal")
    p_prune.add_argument("--dry-run", action="store_true", help="Show what would be pruned without doing it")
    p_prune.add_argument("--stig-threshold", type=float, default=0.3, help="Stigmergy salience threshold (default 0.3)")
    p_prune.add_argument("--bridge-threshold", type=float, default=0.2, help="Bridge confidence threshold (default 0.2)")
    p_prune.add_argument("--trace-days", type=int, default=14, help="Archive traces older than N days (default 14)")

    # -- xray (Phase 14: Repo X-Ray Product) --
    p_xray = sub.add_parser("xray", help="Run Repo X-Ray — codebase analysis for any repo")
    p_xray.add_argument("repo_path", help="Path to repository to analyze")
    p_xray.add_argument("--output", "-o", default=None, help="Output file path")
    p_xray.add_argument("--json", action="store_true", dest="as_json", help="Output JSON instead of markdown")
    p_xray.add_argument("--exclude", nargs="*", default=None, help="Path patterns to exclude")
    p_xray.add_argument(
        "--packet",
        action="store_true",
        help="Generate a productized Repo X-Ray packet directory instead of a single report file",
    )
    p_xray.add_argument(
        "--buyer",
        default="CTO or founder under shipping pressure",
        help="Target buyer persona for the productized packet",
    )

    # -- foreman (Phase 15: Focused Quality Forge) --
    p_foreman = sub.add_parser("foreman", help="The Foreman — focused quality forge")
    foreman_sub = p_foreman.add_subparsers(dest="foreman_cmd")
    p_fm_add = foreman_sub.add_parser("add", help="Register a project")
    p_fm_add.add_argument("path", help="Path to the project root")
    p_fm_add.add_argument("--name", default=None, help="Friendly project name")
    p_fm_add.add_argument("--test-command", default=None, help="Test command (e.g. 'pytest')")
    p_fm_add.add_argument("--exclude", nargs="*", default=None, help="Path patterns to exclude")
    p_fm_run = foreman_sub.add_parser("run", help="Run one forge cycle")
    p_fm_run.add_argument("--level", default="observe", choices=["observe", "advise", "build"], help="Execution level")
    p_fm_run.add_argument("--project", default=None, help="Filter to one project")
    p_fm_run.add_argument("--skip-tests", action="store_true", help="Skip running test suites")
    foreman_sub.add_parser("status", help="Show quality dashboard")
    p_fm_cron = foreman_sub.add_parser("cron", help="Start recurring forge cycle")
    p_fm_cron.add_argument("--schedule", default="every 4h", help="Cron schedule")
    p_fm_cron.add_argument("--level", default="advise", choices=["observe", "advise", "build"], help="Execution level")

    # -- review-cycle (Phase 13: Quality Ratchet) -- renamed to avoid conflict with 'review' subparser
    p_review = sub.add_parser("review-cycle", help="Generate 6-hour review cycle report")
    p_review.add_argument("--hours", type=float, default=6.0, help="Review window in hours")
    p_review.add_argument("--skip-tests", action="store_true", help="Skip running tests")

    # -- initiatives (Phase 13: Iteration Depth Tracker) --
    p_init = sub.add_parser("initiatives", help="Initiative depth ledger")
    init_sub = p_init.add_subparsers(dest="init_cmd")
    init_sub.add_parser("list", help="List all initiatives")
    p_init_add = init_sub.add_parser("add", help="Add a new initiative")
    p_init_add.add_argument("--title", required=True, help="Initiative title")
    p_init_add.add_argument("--description", default="", help="Description")
    p_init_promote = init_sub.add_parser("promote", help="Promote an initiative")
    p_init_promote.add_argument("initiative_id", help="Initiative ID")
    p_init_abandon = init_sub.add_parser("abandon", help="Abandon an initiative")
    p_init_abandon.add_argument("initiative_id", help="Initiative ID")
    p_init_abandon.add_argument("--reason", required=True, help="Reason for abandonment")
    init_sub.add_parser("summary", help="Show initiative summary")

    # -- cron (v0.6.0: Hermes-inspired cron scheduler) --
    p_cron = sub.add_parser("cron", help="Cron job scheduler (v0.6.0)")
    cron_sub = p_cron.add_subparsers(dest="cron_cmd")
    p_cron_add = cron_sub.add_parser("add", help="Add a new cron job")
    p_cron_add.add_argument("prompt", help="Task prompt to execute")
    p_cron_add.add_argument("schedule", help="Schedule: '30m', 'every 2h', '0 9 * * *'")
    p_cron_add.add_argument("--name", default=None, help="Friendly job name")
    p_cron_add.add_argument("--repeat", type=int, default=None, help="Repeat count (None=forever)")
    p_cron_add.add_argument("--deliver", default="local", help="Delivery target")
    p_cron_add.add_argument("--urgent", action="store_true", help="Run even during quiet hours")
    cron_sub.add_parser("list", help="List all cron jobs")
    p_cron_rm = cron_sub.add_parser("remove", help="Remove a cron job")
    p_cron_rm.add_argument("job_id", help="Job ID to remove")
    cron_sub.add_parser("tick", help="Manually trigger a cron tick")
    p_cron_daemon = cron_sub.add_parser("daemon", help="Run the cron scheduler as a local daemon")
    p_cron_daemon.add_argument(
        "--interval-sec",
        type=float,
        default=60.0,
        help="Seconds between cron ticks",
    )
    p_cron_daemon.add_argument(
        "--max-loops",
        type=int,
        default=None,
        help="Stop after N tick loops (useful for testing)",
    )
    p_cron_daemon.add_argument(
        "--no-run-immediately",
        dest="run_immediately",
        action="store_false",
        help="Sleep for one interval before the first tick",
    )
    p_cron_daemon.set_defaults(run_immediately=True)

    # -- gateway (v0.6.0: Hermes-inspired messaging gateway) --
    p_gw = sub.add_parser("gateway", help="Start messaging gateway (v0.6.0)")
    p_gw.add_argument("--config", default=None, help="Path to gateway.yaml")

    p_ff = sub.add_parser("free-fleet", help="Show free-tier OpenRouter model fleet")
    p_ff.add_argument("--tier", type=int, default=None, help="Filter to tier 1, 2, or 3")
    p_ff.add_argument("--json", dest="json", action="store_true", default=False, help="Output as JSON")
    p_ff.add_argument("--set-env", dest="set_env", action="store_true", default=False, help="Print shell export command")
    p_mc = sub.add_parser("model-catalog", help="Show canonical model packs and routing selectors")
    p_mc.add_argument("selector", nargs="?", default=None, help="Pack selector, e.g. 'top open models' or 'tier one models'")
    p_mc.add_argument("--json", dest="json", action="store_true", default=False, help="Output as JSON")

    # -- custodians (Phase 17: Autonomous Code Maintenance Fleet) --
    p_cust = sub.add_parser("custodians", help="Autonomous code maintenance fleet")
    cust_sub = p_cust.add_subparsers(dest="custodians_cmd")
    p_cust_run = cust_sub.add_parser("run", help="Run custodian maintenance cycle")
    p_cust_run.add_argument("--roles", default=None, help="Comma-separated roles (default: all)")
    p_cust_run.add_argument("--dry-run", dest="dry_run", action="store_true", default=True, help="Show what would be done (default)")
    p_cust_run.add_argument("--execute", dest="dry_run", action="store_false", help="Actually execute changes")
    cust_sub.add_parser("status", help="Show custodian fleet status")
    cust_sub.add_parser("schedule", help="Create recurring custodian cron jobs")

    # -- cross (YATAGARASU: Cross-Pollination Engine) --
    p_cross = sub.add_parser("cross", help="YATAGARASU cross-pollination — weave lattice connections")
    cross_sub = p_cross.add_subparsers(dest="cross_cmd")
    p_cross_run = cross_sub.add_parser("run", help="Run one cross-pollination session")
    p_cross_run.add_argument("--max-edges", type=int, default=5, help="Max missing edges to investigate (default: 5)")
    p_cross_run.add_argument("--dry-run", dest="dry_run", action="store_true", default=False, help="Show candidates without calling LLM")
    cross_sub.add_parser("status", help="Catalytic graph health + last run")
    cross_sub.add_parser("fly", help="Full murder flight — YATAGARASU + 5 KARASU + TOMBI")

    return parser



# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the unified DGC CLI."""
    _bootstrap_env()

    # Compatibility shim: legacy habit `DGC TUI` / `dgc tui`
    if len(sys.argv) >= 2 and sys.argv[1].lower() == "tui":
        sys.argv = [sys.argv[0], "--tui", *sys.argv[2:]]

    # Optional default mode toggle: `DGC_DEFAULT_MODE=chat dgc`
    if len(sys.argv) < 2:
        default_mode = os.getenv("DGC_DEFAULT_MODE", "tui").strip().lower()
        if default_mode in {"chat", "claude", "cc"}:
            cmd_chat(
                continue_last=False,
                offline=os.getenv("DGC_CHAT_OFFLINE", "").strip() in {"1", "true", "yes", "on"},
                model=os.getenv("DGC_CHAT_MODEL") or None,
                effort=os.getenv("DGC_CHAT_EFFORT") or None,
                include_context=os.getenv("DGC_CHAT_NO_CONTEXT", "").strip().lower()
                not in {"1", "true", "yes", "on"},
            )
            return
        try:
            cmd_tui()
        except ImportError as e:
            print(f"TUI not available ({e}). Run: cd terminal && bun run start")
            print("Falling back to status...\n")
            cmd_status()
        except Exception as e:
            print(f"TUI error: {e}")
            print("Falling back to status...\n")
            cmd_status()
        return

    # Explicit --tui -> launch TUI
    if sys.argv[1] == "--tui":
        try:
            cmd_tui()
        except ImportError as e:
            print(f"TUI not available ({e}). Run: cd terminal && bun run start")
            print("Falling back to status...\n")
            cmd_status()
        except Exception as e:
            print(f"TUI error: {e}")
            print("Falling back to status...\n")
            cmd_status()
        return

    parser = _build_parser()
    args = parser.parse_args()

    match args.command:
        case "chat":
            cmd_chat(
                continue_last=args.continue_last,
                offline=args.offline,
                model=args.model,
                effort=args.effort,
                include_context=not args.no_context,
            )
        case "dashboard":
            cmd_tui()
        case "ui":
            cmd_ui(getattr(args, "surface", "list"))
        case "status":
            cmd_status(as_json=args.json)
        case "runtime-status":
            cmd_runtime_status(limit=args.limit, db_path=args.db_path, as_json=args.json)
        case "mission-status":
            rc = cmd_mission_status(
                as_json=args.json,
                strict_core=args.strict_core,
                require_tracked=args.require_tracked,
                profile=args.profile,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "mission-brief":
            rc = cmd_mission_brief(
                path=args.path,
                state_dir=args.state_dir,
                as_json=args.json,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "campaign-brief":
            rc = cmd_campaign_brief(
                path=args.path,
                state_dir=args.state_dir,
                as_json=args.json,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "canonical-status":
            rc = cmd_canonical_status(as_json=args.json)
            if rc != 0:
                raise SystemExit(rc)
        case "value-events":
            from dharma_swarm.operator_brief.value_events import run_value_events
            print(run_value_events(
                since=args.since,
                as_json=args.json,
                registry_path=args.registry_path,
            ))
        case "trace-attractor":
            from dharma_swarm.trace_attractor.cli import run_trace_attractor
            print(run_trace_attractor(
                trace_id=args.trace_id,
                as_json=args.json,
                registry_path=args.registry_path,
                runtime_db=args.runtime_db,
                telemetry_db=args.telemetry_db,
                board_db=args.board_db,
                sakshi_log=args.sakshi_log,
            ))
        case "up":
            cmd_up(background=args.background)
        case "down":
            cmd_down()
        case "daemon-status":
            cmd_daemon_status()
        case "pulse":
            cmd_pulse()
        case "orchestrate-live":
            cmd_orchestrate_live(background=args.background)
        case "overnight":
            import asyncio as _aio
            from dharma_swarm.overnight_director import run_overnight as _run_overnight
            _result = _aio.run(_run_overnight(
                hours=args.hours,
                dry_run=args.dry_run,
                autonomy_level=args.autonomy,
                max_tokens=args.max_tokens,
                cycle_timeout=args.cycle_timeout,
            ))
            print(json.dumps(_result, indent=2))
        case "swarm":
            cmd_swarm(args.swarm_args)
        case "stress":
            cmd_stress(
                profile=args.profile,
                state_dir=args.state_dir,
                provider_mode=args.provider_mode,
                agents=args.agents,
                tasks=args.tasks,
                evolutions=args.evolutions,
                evolution_concurrency=args.evolution_concurrency,
                cli_rounds=args.cli_rounds,
                cli_concurrency=args.cli_concurrency,
                orchestration_timeout_sec=args.orchestration_timeout_sec,
                external_research=args.external_research,
                external_timeout_sec=args.external_timeout_sec,
            )
        case "full-power-probe" | "probe":
            cmd_full_power_probe(
                route_task=args.route_task,
                context_search_query=args.context_search_query,
                compose_task=args.compose_task,
                autonomy_action=args.autonomy_action,
                skip_sprint_probe=args.skip_sprint_probe,
                skip_stress=args.skip_stress,
                skip_pytest=args.skip_pytest,
            )
        case "provider-smoke":
            rc = cmd_provider_smoke(
                ollama_model=args.ollama_model,
                nim_model=args.nim_model,
                qwen_provider=args.qwen_provider,
                qwen_task=args.qwen_task,
                telemetry_db=args.telemetry_db,
                as_json=args.json,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "provider-matrix":
            rc = cmd_provider_matrix(
                profile=args.profile,
                corpus=args.corpus,
                max_targets=args.max_targets,
                max_prompts=args.max_prompts,
                timeout_seconds=args.timeout_seconds,
                concurrency=args.concurrency,
                budget_units=args.budget_units,
                artifact_dir=args.artifact_dir,
                include_unavailable=args.include_unavailable,
                write_artifacts=not args.no_artifacts,
                as_json=args.json,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "context":
            cmd_context(args.domain)
        case "memory":
            memory_text = ""
            if getattr(args, "memory_cmd", None) in {"query"}:
                memory_text = " ".join(args.memory_query)
            elif getattr(args, "memory_cmd", None) in {"common", "brief"}:
                memory_text = " ".join(args.memory_task)
            elif getattr(args, "memory_cmd", None) == "schedule":
                memory_text = getattr(args, "schedule", "every 24h")
            cmd_memory(
                args.memory_cmd,
                text=memory_text,
                top_k=args.top_k,
                as_json=args.json,
            )
        case "witness":
            cmd_witness(" ".join(args.message))
        case "develop":
            cmd_develop(args.what, " ".join(args.evidence))
        case "gates":
            cmd_gates(" ".join(args.action), as_json=args.json)
        case "organism-pulse":
            cmd_organism_pulse(task=args.task, dry_run=args.dry_run)
        case "invariants":
            cmd_invariants()
        case "transcendence":
            cmd_transcendence()
        case "health":
            cmd_health(as_json=args.json)
        case "cascade":
            cmd_cascade(
                domain=args.domain,
                seed_path=args.seed_path,
                seed_skill=args.seed_skill,
                seed_project=args.seed_project,
                track=args.track,
                max_iter=args.max_iter,
            )
        case "forge":
            cmd_forge(path=args.path, batch=args.batch)
        case "loops":
            cmd_loops()
        case "health-check":
            rc = cmd_health_check()
            if rc != 0:
                raise SystemExit(rc)
        case "verify-baseline":
            from dharma_swarm.claude_hooks import verify_baseline
            import json as _json
            result = verify_baseline()
            print(_json.dumps(result, indent=2))
            gates = result.get("gates", {})
            health = result.get("health", {})
            status = health.get("status", "unknown") if isinstance(health, dict) else "unknown"
            print(f"\nGates: {gates.get('passed', '?')}/{gates.get('total', '?')} | Health: {status}")
            if gates.get("decision") == "BLOCK":
                raise SystemExit(1)
        case "doctor":
            rc = cmd_doctor(
                doctor_cmd=args.doctor_action,
                as_json=args.json,
                strict=args.strict,
                quick=args.quick,
                timeout=args.timeout,
                schedule=args.schedule,
                interval_sec=args.interval_sec,
                max_runs=args.max_runs,
            )
            if rc != 0:
                raise SystemExit(rc)
        case "setup":
            cmd_setup()
        case "migrate":
            cmd_migrate()
        case "model":
            cmd_model(action=args.action)
        case "agni":
            cmd_agni(" ".join(args.remote_cmd))
        case "spawn":
            cmd_spawn(name=args.name, role=args.role, model=args.model)
        case "agent":
            match args.agent_cmd:
                case "wake":
                    _cmd_agent_wake(args.name, args.task, args.model)
                case "list":
                    _cmd_agent_list()
                case "runs":
                    _cmd_agent_runs()
                case "talk" | "run" | "status" | "kill":
                    # Holon subcommands fail closed with a concise error, never a traceback.
                    try:
                        match args.agent_cmd:
                            case "talk":
                                _cmd_agent_talk(
                                    args.name,
                                    " ".join(args.message),
                                    routing_mode=args.mode,
                                    max_tokens=args.max_tokens,
                                )
                            case "run":
                                _cmd_agent_run(
                                    args.name,
                                    cycles=args.cycles,
                                    routing_mode=args.mode,
                                )
                            case "status":
                                _cmd_agent_status(args.name, as_json=args.json)
                            case "kill":
                                _cmd_agent_kill(
                                    args.name,
                                    reason=args.reason,
                                    clear=args.clear,
                                )
                    except Exception as e:
                        print(f"Agent command failed: {e}")
                        raise SystemExit(2)
                case _:
                    parser.parse_args(["agent", "--help"])
        case "task":
            match args.task_cmd:
                case "create":
                    cmd_task_create(args.title, args.description, args.priority)
                case "list":
                    cmd_task_list(args.status_filter)
                case _:
                    parser.parse_args(["task", "--help"])
        case "evolve":
            match args.evolve_cmd:
                case "propose":
                    cmd_evolve_propose(
                        args.component, args.description,
                        args.change_type, args.diff,
                    )
                case "trend":
                    cmd_evolve_trend(args.component)
                case "apply":
                    cmd_evolve_apply(args.component, args.description)
                case "promote":
                    cmd_evolve_promote(args.entry_id)
                case "rollback":
                    cmd_evolve_rollback(args.entry_id, args.reason)
                case "auto":
                    cmd_evolve_auto(
                        args.files, args.model, args.context,
                        single_model=args.single_model,
                        shadow=args.shadow,
                        token_budget=args.token_budget,
                    )
                case "daemon":
                    cmd_evolve_daemon(
                        args.interval, args.threshold, args.model, args.cycles,
                        single_model=args.single_model,
                        shadow=args.shadow,
                        token_budget=args.token_budget,
                    )
                case _:
                    parser.parse_args(["evolve", "--help"])
        case "run":
            cmd_run(interval=args.interval)
        case "rag":
            try:
                match args.rag_cmd:
                    case "health":
                        cmd_rag_health(
                            service=args.service,
                            check_dependencies=not args.no_deps,
                        )
                    case "search":
                        cmd_rag_search(
                            query=" ".join(args.query),
                            top_k=args.top_k,
                            collection=args.collection,
                        )
                    case "chat":
                        cmd_rag_chat(prompt=" ".join(args.prompt), model=args.model)
                    case _:
                        parser.parse_args(["rag", "--help"])
            except Exception as e:
                print(f"RAG command failed: {e}")
                raise SystemExit(2)
        case "flywheel":
            try:
                match args.flywheel_cmd:
                    case "jobs":
                        cmd_flywheel_jobs()
                    case "export":
                        cmd_flywheel_export(
                            run_id=args.run_id,
                            workload_id=args.workload_id,
                            client_id=args.client_id,
                            trace_id=args.trace_id,
                            db_path=args.db_path,
                            event_log_dir=args.event_log_dir,
                            export_root=args.export_root,
                        )
                    case "record":
                        cmd_flywheel_record(
                            job_id=args.job_id,
                            workload_id=args.workload_id,
                            client_id=args.client_id,
                            run_id=args.run_id,
                            session_id=args.session_id,
                            task_id=args.task_id,
                            trace_id=args.trace_id,
                            db_path=args.db_path,
                            event_log_dir=args.event_log_dir,
                            workspace_root=args.workspace_root,
                            provenance_root=args.provenance_root,
                        )
                    case "start":
                        cmd_flywheel_start(
                            workload_id=args.workload_id,
                            client_id=args.client_id,
                            eval_size=args.eval_size,
                            val_ratio=args.val_ratio,
                            min_total_records=args.min_total_records,
                            limit=args.limit,
                            run_id=args.run_id,
                            trace_id=args.trace_id,
                            db_path=args.db_path,
                            event_log_dir=args.event_log_dir,
                            export_root=args.export_root,
                        )
                    case "get":
                        cmd_flywheel_get(args.job_id)
                    case "cancel":
                        cmd_flywheel_cancel(args.job_id)
                    case "delete":
                        cmd_flywheel_delete(args.job_id)
                    case "watch":
                        cmd_flywheel_watch(args.job_id, args.poll_sec, args.timeout_sec)
                    case _:
                        parser.parse_args(["flywheel", "--help"])
            except Exception as e:
                print(f"Flywheel command failed: {e}")
                raise SystemExit(2)
        case "reciprocity":
            try:
                match args.reciprocity_cmd:
                    case "health":
                        cmd_reciprocity_health()
                    case "summary":
                        cmd_reciprocity_summary()
                    case "publish":
                        cmd_reciprocity_publish(
                            record_type=args.publish_type,
                            json_payload=args.publish_json,
                            file_path=args.publish_file,
                        )
                    case "record":
                        cmd_reciprocity_record(
                            run_id=args.run_id,
                            session_id=args.session_id,
                            task_id=args.task_id,
                            trace_id=args.trace_id,
                            summary_type=args.summary_type,
                            json_payload=args.record_json,
                            file_path=args.record_file,
                            db_path=args.db_path,
                            event_log_dir=args.event_log_dir,
                            workspace_root=args.workspace_root,
                            provenance_root=args.provenance_root,
                        )
                    case _:
                        parser.parse_args(["reciprocity", "--help"])
            except Exception as e:
                print(f"Reciprocity command failed: {e}")
                raise SystemExit(2)
        case "ouroboros":
            try:
                match args.ouroboros_cmd:
                    case "connections":
                        cmd_ouroboros_connections(
                            package_dir=args.package_dir,
                            threshold=args.threshold,
                            disagreement_threshold=args.disagreement_threshold,
                            min_text_length=args.min_text_length,
                            limit=args.limit,
                            as_json=args.as_json,
                        )
                    case "record":
                        cmd_ouroboros_record(
                            run_id=args.run_id,
                            session_id=args.session_id,
                            task_id=args.task_id,
                            trace_id=args.trace_id,
                            log_path=args.log_path,
                            cycle_id=args.cycle_id,
                            json_payload=args.observation_json,
                            file_path=args.observation_file,
                            db_path=args.db_path,
                            event_log_dir=args.event_log_dir,
                            workspace_root=args.workspace_root,
                            provenance_root=args.provenance_root,
                        )
                    case _:
                        parser.parse_args(["ouroboros", "--help"])
            except Exception as e:
                print(f"Ouroboros command failed: {e}")
                raise SystemExit(2)
        case "dharma":
            match args.dharma_cmd:
                case "status":
                    cmd_dharma_status()
                case "corpus":
                    cmd_dharma_corpus(args.corpus_status, args.corpus_category)
                case "review":
                    cmd_dharma_review(args.claim_id)
                case _:
                    parser.parse_args(["dharma", "--help"])
        case "stigmergy":
            cmd_stigmergy(args.stig_file, as_json=args.json)
        case "hum":
            cmd_hum()
        case "eval":
            from dharma_swarm.ecc_eval_harness import (
                cmd_eval_run, cmd_eval_report, cmd_eval_trend,
                cmd_eval_dashboard,
            )
            match args.eval_cmd:
                case "run":
                    import asyncio as _aio
                    rc = _aio.run(cmd_eval_run())
                    if rc != 0:
                        raise SystemExit(rc)
                case "report":
                    rc = cmd_eval_report()
                    if rc != 0:
                        raise SystemExit(rc)
                case "trend":
                    rc = cmd_eval_trend()
                    if rc != 0:
                        raise SystemExit(rc)
                case "dashboard":
                    rc = cmd_eval_dashboard()
                    if rc != 0:
                        raise SystemExit(rc)
                case _:
                    parser.parse_args(["eval", "--help"])
        case "log":
            import subprocess as _sp_log
            checker = str(dharma_state_dir() / "conversation_log" / "promise_checker.py")
            match args.log_cmd:
                case "promises":
                    _sp_log.run([sys.executable, checker, "--promises"])
                case "stats":
                    _sp_log.run([sys.executable, checker, "--stats"])
                case "search":
                    _sp_log.run([sys.executable, checker, "--search", " ".join(args.query)])
                case _:
                    _sp_log.run([sys.executable, checker, "--log"])
        case "self-improve":
            match args.si_cmd:
                case "status":
                    from dharma_swarm.self_improve import cmd_self_improve_status
                    rc = cmd_self_improve_status()
                    if rc != 0:
                        raise SystemExit(rc)
                case "history":
                    from dharma_swarm.self_improve import cmd_self_improve_history
                    rc = cmd_self_improve_history()
                    if rc != 0:
                        raise SystemExit(rc)
                case "run":
                    from dharma_swarm.self_improve import cmd_self_improve_run
                    import asyncio as _aio3
                    rc = _aio3.run(cmd_self_improve_run())
                    if rc != 0:
                        raise SystemExit(rc)
                case _:
                    from dharma_swarm.self_improve import cmd_self_improve_status
                    cmd_self_improve_status()
        case "audit":
            match args.audit_cmd:
                case "trend":
                    from dharma_swarm.harness_audit import cmd_audit_trend
                    rc = cmd_audit_trend()
                    if rc != 0:
                        raise SystemExit(rc)
                case _:
                    from dharma_swarm.harness_audit import cmd_audit
                    rc = cmd_audit()
                    if rc != 0:
                        raise SystemExit(rc)
        case "review":
            from dharma_swarm.review_bridge import cmd_review_scan
            rc = cmd_review_scan()
            if rc != 0:
                raise SystemExit(rc)
        case "instincts":
            match args.instinct_cmd:
                case "status":
                    from dharma_swarm.instinct_bridge import cmd_instincts_status
                    rc = cmd_instincts_status()
                    if rc != 0:
                        raise SystemExit(rc)
                case "sync":
                    from dharma_swarm.instinct_bridge import cmd_instincts_sync
                    import asyncio as _aio2
                    rc = _aio2.run(cmd_instincts_sync())
                    if rc != 0:
                        raise SystemExit(rc)
                case _:
                    parser.parse_args(["instincts", "--help"])
        case "loop-status":
            from dharma_swarm.loop_supervisor import cmd_loop_status
            rc = cmd_loop_status()
            if rc != 0:
                raise SystemExit(rc)
        case "spine":
            match args.spine_cmd:
                case "tail":
                    from dharma_swarm.operator_core.spine_tail import cmd_spine_tail
                    rc = cmd_spine_tail(limit=args.limit, follow=args.follow)
                    if rc != 0:
                        raise SystemExit(rc)
                case _:
                    parser.parse_args(["spine", "--help"])
        case "skills":
            cmd_skills()
        case "route":
            cmd_route(" ".join(args.task_desc))
        case "orchestrate":
            cmd_orchestrate(" ".join(args.orch_desc))
        case "autonomy":
            cmd_autonomy(" ".join(args.auto_action))
        case "context-search":
            cmd_context_search(" ".join(args.cs_query))
        case "intent-plan":
            cmd_intent_plan(" ".join(args.ip_prompt))
        case "compose":
            cmd_compose(" ".join(args.comp_desc))
        case "execute-compose":
            cmd_execute_compose(" ".join(args.exec_comp_desc))
        case "handoff":
            cmd_handoff(args.ho_from, args.ho_to, args.ho_context,
                        " ".join(args.content))
        case "agent-memory":
            cmd_agent_memory(args.mem_agent)
        case "sprint":
            cmd_sprint(
                output=args.output,
                local=args.local,
                test_summary=args.test_summary,
                prev_todo=args.prev_todo,
                llm_timeout_sec=args.llm_timeout_sec,
            )
        case "ledger":
            cmd_ledger(
                ledger_cmd=args.ledger_cmd,
                n=getattr(args, "n", 20),
                session=getattr(args, "session", None),
                kind=getattr(args, "kind", "all"),
                query=" ".join(getattr(args, "query", []) or []),
                db_path=getattr(args, "db_path", None),
                sync_ledgers=not getattr(args, "no_sync_ledgers", False),
                limit_sessions=getattr(args, "limit_sessions", None),
            )
        case "semantic":
            try:
                match args.semantic_cmd:
                    case "digest":
                        cmd_semantic_digest(
                            root=args.root,
                            output=args.output,
                            include_tests=args.include_tests,
                            max_files=args.max_files,
                        )
                    case "research":
                        cmd_semantic_research(graph_path=args.graph)
                    case "synthesize":
                        cmd_semantic_synthesize(
                            graph_path=args.graph,
                            max_clusters=args.max_clusters,
                        )
                    case "harden":
                        cmd_semantic_harden(
                            graph_path=args.graph,
                            root=args.root,
                        )
                    case "brief":
                        cmd_semantic_brief(
                            graph_path=args.graph,
                            root=args.root,
                            max_briefs=args.max_briefs,
                            json_output=args.json_output,
                            markdown_output=args.markdown_output,
                            state_dir=args.state_dir,
                            campaign_path=args.campaign_path,
                        )
                    case "status":
                        cmd_semantic_status(graph_path=args.graph)
                    case "proof":
                        cmd_semantic_proof(root=args.root)
                    case _:
                        parser.parse_args(["semantic", "--help"])
            except Exception as e:
                print(f"Semantic command failed: {e}")
                raise SystemExit(2)
        case "bootstrap":
            cmd_bootstrap()
        case "field":
            try:
                match args.field_cmd:
                    case "scan":
                        cmd_field_scan()
                    case "gaps":
                        cmd_field_gaps()
                    case "position":
                        cmd_field_position()
                    case "unique":
                        cmd_field_unique()
                    case "summary":
                        cmd_field_summary()
                    case _:
                        parser.parse_args(["field", "--help"])
            except Exception as e:
                print(f"Field command failed: {e}")
                raise SystemExit(2)
        case "ginko":
            try:
                match args.ginko_cmd:
                    case "status":
                        from dharma_swarm.ginko_orchestrator import ginko_status
                        print(ginko_status())
                    case "dashboard":
                        from dharma_swarm.ginko_brier import format_dashboard_report
                        print(format_dashboard_report())
                    case "edge":
                        from dharma_swarm.ginko_orchestrator import check_edge_validation
                        import json as _json
                        result = check_edge_validation()
                        print(_json.dumps(result, indent=2, default=str))
                    case "register-crons":
                        from dharma_swarm.ginko_orchestrator import register_ginko_crons
                        created = register_ginko_crons()
                        if created:
                            for j in created:
                                print(f"  Created: {j['name']} ({j.get('schedule_display', '')})")
                        else:
                            print("  All Ginko crons already registered.")
                    case "pull":
                        import asyncio as _aio
                        from dharma_swarm.ginko_orchestrator import action_data_pull
                        result = _aio.run(action_data_pull())
                        print("Data pull complete:")
                        print(f"  Macro: {'yes' if result.get('macro_available') else 'no'}")
                        print(f"  Stocks: {result.get('stocks_count', 0)}")
                        print(f"  Crypto: {result.get('crypto_count', 0)}")
                        if result.get('errors'):
                            print(f"  Errors: {', '.join(result['errors'])}")
                    case "signals":
                        import asyncio as _aio
                        from dharma_swarm.ginko_orchestrator import action_generate_signals
                        result = _aio.run(action_generate_signals())
                        if result.get("error"):
                            print(f"Error: {result['error']}")
                        else:
                            print(result.get("report_text", "No report generated"))
                    case "predict":
                        from dharma_swarm.ginko_brier import record_prediction
                        from datetime import datetime, timedelta, timezone
                        resolve_by = args.resolve_by or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                        pred = record_prediction(
                            question=args.question,
                            probability=args.probability,
                            resolve_by=resolve_by,
                            category=args.category,
                        )
                        print("Prediction recorded:")
                        print(f"  ID: {pred.id}")
                        print(f"  Question: {pred.question}")
                        print(f"  Probability: {pred.probability:.0%}")
                        print(f"  Resolve by: {pred.resolve_by}")
                    case "resolve":
                        from dharma_swarm.ginko_brier import resolve_prediction
                        pred = resolve_prediction(args.prediction_id, args.outcome)
                        if pred:
                            print(f"Resolved: {pred.question}")
                            print(f"  Outcome: {'YES' if pred.outcome == 1.0 else 'NO'}")
                            print(f"  Brier score: {pred.brier_score:.4f}")
                        else:
                            print(f"Prediction {args.prediction_id} not found or already resolved")
                    case "brier":
                        from dharma_swarm.ginko_brier import format_dashboard_report
                        print(format_dashboard_report())
                    case "report":
                        import asyncio as _aio
                        from dharma_swarm.ginko_orchestrator import action_generate_report
                        result = _aio.run(action_generate_report())
                        print(result.get("report_text", "No report generated"))
                    case "portfolio":
                        try:
                            from dharma_swarm.ginko_paper_trade import PaperPortfolio
                            import json as _json
                            p = PaperPortfolio()
                            stats = p.get_portfolio_stats()
                            print("Dharmic Quant — Paper Portfolio")
                            print("=" * 40)
                            print(f"  Total value: ${stats.get('total_value', 0):,.2f}")
                            print(f"  Cash: ${stats.get('cash', 0):,.2f}")
                            print(f"  P&L: {stats.get('total_pnl_pct', 0):+.2f}%")
                            print(f"  Open positions: {stats.get('open_positions', 0)}")
                            print(f"  Sharpe ratio: {stats.get('sharpe_ratio', 0):.2f}")
                            print(f"  Max drawdown: {stats.get('max_drawdown', 0):.1%}")
                            print(f"  Win rate: {stats.get('win_rate', 0):.1%}")
                            print(f"  Trades: {stats.get('trade_count', 0)}")
                        except Exception as e:
                            print(f"Portfolio not available: {e}")
                    case "cycle":
                        import asyncio as _aio
                        from dharma_swarm.ginko_orchestrator import action_full_cycle
                        print("Running full Ginko cycle...")
                        result = _aio.run(action_full_cycle())
                        import json as _json
                        for phase, data in result.items():
                            if phase == "total_duration_ms":
                                continue
                            status = "ERROR" if isinstance(data, dict) and "error" in data else "OK"
                            print(f"  {phase}: {status}")
                        print(f"\nTotal duration: {result.get('total_duration_ms', 0)}ms")
                    case "fleet":
                        try:
                            from dharma_swarm.ginko_agents import GinkoFleet
                            fleet = GinkoFleet()
                            agents = fleet.list_agents()
                            print("Dharmic Quant — Agent Fleet")
                            print("=" * 40)
                            for a in agents:
                                status = a.status if hasattr(a, 'status') else 'unknown'
                                fitness = a.fitness if hasattr(a, 'fitness') else 0.0
                                calls = a.total_calls if hasattr(a, 'total_calls') else 0
                                name = a.name if hasattr(a, 'name') else str(a)
                                role = a.role if hasattr(a, 'role') else ''
                                print(f"  {name.upper():12s} {role:20s} fitness={fitness:.0%} calls={calls} [{status}]")
                        except Exception as e:
                            print(f"Fleet not available: {e}")
                    case _:
                        print("Usage: dgc ginko {status|pull|signals|predict|resolve|brier|report|portfolio|cycle|fleet|dashboard|edge|register-crons}")
            except Exception as e:
                print(f"Ginko command failed: {e}")
                raise SystemExit(2)
        case "foundations":
            cmd_foundations(args.pillar)
        case "telos":
            cmd_telos(args.doc)
        case "meta":
            _run_meta()
        case "prune":
            _run_prune(
                dry_run=getattr(args, "dry_run", False),
                stig_threshold=getattr(args, "stig_threshold", 0.3),
                bridge_threshold=getattr(args, "bridge_threshold", 0.2),
                trace_days=getattr(args, "trace_days", 14),
            )
        case "xray":
            cmd_xray(
                repo_path=args.repo_path,
                output=args.output,
                as_json=args.as_json,
                exclude=getattr(args, "exclude", None),
                packet=getattr(args, "packet", False),
                buyer=getattr(args, "buyer", "CTO or founder under shipping pressure"),
            )
        case "foreman":
            cmd_foreman(
                foreman_cmd=args.foreman_cmd,
                path=getattr(args, "path", ""),
                name=getattr(args, "name", None),
                test_command=getattr(args, "test_command", None),
                exclude=getattr(args, "exclude", None),
                level=getattr(args, "level", "observe"),
                project=getattr(args, "project", None),
                skip_tests=getattr(args, "skip_tests", False),
                schedule=getattr(args, "schedule", "every 4h"),
            )
        case "review-cycle":
            cmd_review(
                hours=args.hours,
                skip_tests=args.skip_tests,
            )
        case "initiatives":
            cmd_initiatives(
                init_cmd=args.init_cmd,
                title=getattr(args, "title", ""),
                description=getattr(args, "description", ""),
                initiative_id=getattr(args, "initiative_id", ""),
                reason=getattr(args, "reason", ""),
            )
        case "cron":
            cmd_cron(
                cron_cmd=args.cron_cmd,
                prompt=getattr(args, "prompt", ""),
                schedule=getattr(args, "schedule", ""),
                name=getattr(args, "name", None),
                repeat=getattr(args, "repeat", None),
                deliver=getattr(args, "deliver", "local"),
                urgent=getattr(args, "urgent", False),
                job_id=getattr(args, "job_id", ""),
                interval_sec=getattr(args, "interval_sec", 60.0),
                max_loops=getattr(args, "max_loops", None),
                run_immediately=getattr(args, "run_immediately", True),
            )
        case "map":
            if getattr(args, "map_cmd", None):
                raise SystemExit(
                    cmd_system_map(
                        map_cmd=args.map_cmd,
                        organ=getattr(args, "organ", None),
                        map_path=getattr(args, "path", "reports/system_map/latest.json"),
                        json_output=getattr(args, "system_map_json_output", False),
                    )
                )
            from dharma_swarm.living_map import generate, generate_json
            if getattr(args, "json", False):
                import json as _json
                print(_json.dumps(generate_json(), indent=2, default=str))
            else:
                print(generate(layer=getattr(args, "layer", None)))
        case "gateway":
            cmd_gateway(config_path=args.config)
        case "free-fleet":
            cmd_free_fleet(tier=args.tier, as_json=args.json, set_env=args.set_env)
        case "model-catalog":
            cmd_model_catalog(selector=args.selector, as_json=args.json)
        case "custodians":
            cmd_custodians(
                custodians_cmd=args.custodians_cmd,
                roles=getattr(args, "roles", None),
                dry_run=getattr(args, "dry_run", True),
            )
        case "cross":
            cmd_cross(
                cross_cmd=args.cross_cmd,
                max_edges=getattr(args, "max_edges", 5),
                dry_run=getattr(args, "dry_run", False),
            )
        case _:
            parser.print_help()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Backward-compat patch propagation: tests monkeypatch attributes on this
# module (e.g. ``monkeypatch.setattr(cli, "HOME", tmp)``).  After extraction
# the cmd_* functions live in terminal_commands/* and resolve names via their
# own module __dict__.  The custom __setattr__ below intercepts patches on
# *this* module and mirrors them to every terminal_commands module that
# imported the same name, so existing tests work unchanged.
# ---------------------------------------------------------------------------
import types as _types  # noqa: E402

_TC = "dharma_swarm.terminal_commands"

_PATCH_TARGETS: dict[str, list[str]] = {
    "HOME": [
        f"{_TC}._helpers", f"{_TC}._status_helpers",
        f"{_TC}.status", f"{_TC}.diagnostics",
        f"{_TC}.surfaces", f"{_TC}.infrastructure",
    ],
    "DHARMA_STATE": [
        f"{_TC}._helpers", f"{_TC}._status_helpers",
        f"{_TC}.status", f"{_TC}.diagnostics", f"{_TC}.lifecycle",
        f"{_TC}.agents", f"{_TC}.data_loop", f"{_TC}.governance",
        f"{_TC}.memory", f"{_TC}.meta", f"{_TC}.ouroboros",
        f"{_TC}.semantic", f"{_TC}.stigmergy", f"{_TC}.surfaces",
    ],
    "DHARMA_SWARM": [
        f"{_TC}._helpers", f"{_TC}._status_helpers",
        f"{_TC}.data_loop", f"{_TC}.governance",
        f"{_TC}.infrastructure", f"{_TC}.lifecycle",
        f"{_TC}.meta", f"{_TC}.ouroboros",
        f"{_TC}.semantic", f"{_TC}.surfaces",
    ],
    "DGC_CORE": [
        f"{_TC}._helpers", f"{_TC}._status_helpers", f"{_TC}.lifecycle",
    ],
    "subprocess": [
        f"{_TC}._helpers", f"{_TC}._status_helpers",
        f"{_TC}.lifecycle", f"{_TC}.status", f"{_TC}.diagnostics",
        f"{_TC}.infrastructure", f"{_TC}.meta",
        f"{_TC}.semantic", f"{_TC}.surfaces",
    ],
    "_run": [
        f"{_TC}.status", f"{_TC}.agents", f"{_TC}.data_loop",
        f"{_TC}.diagnostics", f"{_TC}.evolution", f"{_TC}.governance",
        f"{_TC}.infrastructure", f"{_TC}.lifecycle", f"{_TC}.memory",
        f"{_TC}.meta", f"{_TC}.operator", f"{_TC}.ouroboros",
        f"{_TC}.semantic", f"{_TC}.stigmergy",
    ],
    "_core_mission_checks": [f"{_TC}.status"],
    "_tracked_paths": [f"{_TC}.status"],
    "_read_openclaw_summary": [f"{_TC}.status"],
    "_flywheel_export_payload": [f"{_TC}.data_loop"],
    "_flywheel_record_payload": [f"{_TC}.data_loop"],
    "_reciprocity_publish_payload": [f"{_TC}.data_loop"],
    "_reciprocity_record_payload": [f"{_TC}.data_loop"],
    "_load_ouroboros_observation": [f"{_TC}.data_loop", f"{_TC}.ouroboros"],
    "_ouroboros_record_payload": [f"{_TC}.ouroboros"],
}


class _PropagatingModule(_types.ModuleType):
    """Mirror ``setattr`` calls to terminal_commands sub-modules."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for mod_name in _PATCH_TARGETS.get(name, ()):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                _types.ModuleType.__setattr__(mod, name, value)


sys.modules[__name__].__class__ = _PropagatingModule
