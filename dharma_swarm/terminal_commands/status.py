"""Status, health, and observability commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os


# ---------------------------------------------------------------------------
# Commands — carried over from dgc-core
# ---------------------------------------------------------------------------


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    _run,
)
from dharma_swarm.terminal_commands._status_helpers import (
    MISSION_AUTONOMY_PROFILES,
    MISSION_TRACKED_PATHS,
    _accelerators_enabled,
    _build_status_data,
    _core_mission_checks,
    _read_openclaw_summary,
    _resolve_mission_profile,
    _tracked_paths,
)

def cmd_status(*, as_json: bool = False) -> None:
    """System status overview."""
    data = _build_status_data()

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    print("=== DGC CORE STATUS ===\n")

    if "memory_entries" in data:
        print(f"Memory (async SQLite): {data['memory_entries']} recent entries")
    else:
        print(f"Memory: unavailable ({data.get('memory_error', 'unknown')})")

    pulse = data["pulse"]
    if pulse["last"]:
        source_note = f" via {pulse['source']}" if pulse["source"] is not None else ""
        print(f"Pulse: {pulse['count']} logged{source_note}, last: {pulse['last']}")
    else:
        print("Pulse: not yet run")

    print(f"Gates today: {data['gates_today']} checks")

    if "control_plane_snapshot" in data:
        print(f"Control plane snapshot: {data['control_plane_snapshot']}")

    if "loop_liveness" in data:
        ll = data["loop_liveness"]
        if ll.get("pid_alive") is False:
            print(
                f"Daemon loops: DEAD — liveness file claims {ll['running']} running "
                f"but owning pid {ll['pid']} is gone "
                f"(file is {ll['age_min']}m old; do not trust it)"
            )
        else:
            line = f"Daemon loops: {ll['running']} running"
            if ll["abandoned"]:
                line += f" | ABANDONED: {', '.join(ll['abandoned'])}"
            if ll["hot_restarts"]:
                hot = ", ".join(f"{k}x{v}" for k, v in ll["hot_restarts"].items())
                line += f" | hot restarts: {hot}"
            line += f" (as of {ll['age_min']}m ago, pid {ll['pid']})"
            print(line)

    agni = data.get("agni", {})
    if agni.get("synced"):
        if agni.get("working_md_age_min") is not None:
            print(f"\nAGNI workspace: synced, WORKING.md updated {agni['working_md_age_min']} min ago")
        else:
            print("\nAGNI workspace: synced but no WORKING.md")
    else:
        print("\nAGNI workspace: NOT SYNCED")

    if "trishula_messages" in data:
        print(f"Trishula inbox: {data['trishula_messages']} messages")

    if data.get("claude_code"):
        print(f"\nClaude Code: {data['claude_code']}")
    else:
        print("\nClaude Code: not found")

    print("\nMission spine: run `dgc mission-status` for full readiness lanes")
    print("Canonical topology: run `dgc canonical-status`")


def cmd_runtime_status(
    *,
    limit: int = 5,
    db_path: str | None = None,
    as_json: bool = False,
) -> None:
    """Show the canonical runtime control-plane summary."""
    if as_json:
        from dharma_swarm.tui_helpers import build_runtime_status_data

        print(
            json.dumps(
                build_runtime_status_data(
                    limit=limit,
                    runtime_db_path=Path(db_path) if db_path else None,
                ),
                indent=2,
            )
        )
    else:
        from dharma_swarm.tui_helpers import build_runtime_status_text

        print(
            build_runtime_status_text(
                limit=limit,
                runtime_db_path=Path(db_path) if db_path else None,
            )
        )


def cmd_mission_status(
    *,
    as_json: bool = False,
    strict_core: bool = False,
    require_tracked: bool = False,
    profile: str | None = None,
) -> int:
    """Mission-level readiness report across core + accelerator lanes.

    Returns:
        Process-style status code:
        - 0: pass
        - 2: strict core lane failure
        - 3: tracked wiring requirement failure
    """
    profile_name, profile_cfg = _resolve_mission_profile(profile)
    if profile and not profile_cfg:
        valid = ", ".join(sorted(MISSION_AUTONOMY_PROFILES))
        if as_json:
            print(
                json.dumps(
                    {
                        "exit_code": 4,
                        "error": f"Unknown autonomy profile: {profile}",
                        "valid_profiles": sorted(MISSION_AUTONOMY_PROFILES),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Unknown autonomy profile: {profile}")
            print(f"Valid profiles: {valid}")
        return 4

    if profile_cfg:
        strict_core = strict_core or bool(profile_cfg.get("strict_core", False))
        require_tracked = require_tracked or bool(
            profile_cfg.get("require_tracked", False)
        )

    core = _core_mission_checks()
    core_pass = sum(1 for v in core.values() if v)

    tracked = _tracked_paths(list(MISSION_TRACKED_PATHS))
    tracked_count = sum(1 for v in tracked.values() if v)
    local_only = [path for path, ok in tracked.items() if not ok]

    oc = _read_openclaw_summary()

    async def _probe_accelerators() -> dict[str, str]:
        if not _accelerators_enabled():
            return {
                "rag_health": "DORMANT",
                "ingest_health": "DORMANT",
                "flywheel_jobs": "DORMANT",
                "reciprocity_health": "DORMANT",
            }
        from dharma_swarm.integrations import (
            DataFlywheelClient,
            NvidiaRagClient,
            ReciprocityCommonsClient,
        )

        out: dict[str, str] = {}
        rag = NvidiaRagClient()
        fw = DataFlywheelClient()
        reciprocity = ReciprocityCommonsClient()
        for label, fn in (
            ("rag_health", lambda: rag.health(service="rag")),
            ("ingest_health", lambda: rag.health(service="ingest")),
            ("flywheel_jobs", fw.list_jobs),
            ("reciprocity_health", reciprocity.health),
        ):
            try:
                await fn()
                out[label] = "PASS"
            except Exception as exc:
                out[label] = f"BLOCKED: {exc}"
        return out

    try:
        accel = _run(_probe_accelerators())
    except Exception as exc:
        accel = {
            "rag_health": f"BLOCKED: {exc}",
            "ingest_health": f"BLOCKED: {exc}",
            "flywheel_jobs": f"BLOCKED: {exc}",
            "reciprocity_health": f"BLOCKED: {exc}",
        }

    core_ok = core_pass == len(core)
    tracked_ok = tracked_count == len(tracked)

    if strict_core and not core_ok:
        exit_code = 2
    elif require_tracked and not tracked_ok:
        exit_code = 3
    else:
        exit_code = 0

    report: dict[str, Any] = {
        "vision": (
            "open, self-evolving, evidence-grounded agent orchestrator "
            "with durable memory, quality gates, and optional accelerator lanes"
        ),
        "core": {
            "pass_count": core_pass,
            "total": len(core),
            "ok": core_ok,
            "checks": core,
        },
        "autonomy_profile": {
            "name": profile_name or "none",
            "strict_core": strict_core,
            "require_tracked": require_tracked,
            "trust_mode": (
                profile_cfg.get("trust_mode")
                if profile_cfg
                else os.getenv("DGC_TRUST_MODE", "internal_yolo")
            ),
            "description": (
                profile_cfg.get("description")
                if profile_cfg
                else "No profile selected."
            ),
        },
        "tracked_wiring": {
            "tracked_count": tracked_count,
            "total": len(tracked),
            "ok": tracked_ok,
            "local_only": local_only,
        },
        "openclaw": oc,
        "accelerators": accel,
        "exit_code": exit_code,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return exit_code

    print("=== DGC MISSION STATUS ===")
    print(f"Vision: {report['vision']}.")
    ap = report["autonomy_profile"]
    print(
        "Autonomy profile: "
        f"{ap['name']} "
        f"(strict_core={int(ap['strict_core'])}, "
        f"require_tracked={int(ap['require_tracked'])}, "
        f"trust_mode={ap['trust_mode']})"
    )
    print(f"\nCore intelligence lane: {core_pass}/{len(core)} wired")
    for key in sorted(core):
        status = "PASS" if core[key] else "MISS"
        print(f"  [{status}] {key}")

    print(f"\nTracked wiring footprint: {tracked_count}/{len(tracked)} in git")
    for path in local_only:
        print(f"  [LOCAL-ONLY] {path}")

    print("\nOpenClaw lane:")
    if not oc.get("present"):
        print("  [MISS] ~/.openclaw/openclaw.json not found")
    elif not oc.get("readable", True):
        print("  [MISS] openclaw.json exists but is unreadable")
    else:
        print(
            "  [PASS] config present "
            f"(agents={oc.get('agents_count', 0)}, providers={len(oc.get('providers', []))})"
        )

    print("\nAccelerator lane (optional):")
    for key in ("rag_health", "ingest_health", "flywheel_jobs", "reciprocity_health"):
        val = accel.get(key, "BLOCKED")
        print(f"  [{key}] {val}")

    print("\nInterpretation:")
    if core_ok:
        print("  Core lane is wired. Mission can proceed without accelerator deps.")
    else:
        print("  Core lane has gaps. Fix misses before scaling autonomy.")
    if not tracked_ok:
        print("  Promote LOCAL-ONLY files into git to avoid drift between sessions.")
    if strict_core and not core_ok:
        print("  Strict core mode failed.")
    if require_tracked and not tracked_ok:
        print("  Required-tracked mode failed.")

    return exit_code


def cmd_mission_brief(
    *,
    path: str | None = None,
    state_dir: str | None = None,
    as_json: bool = False,
) -> int:
    """Show the active mission continuity state for the director."""
    from dharma_swarm.mission_contract import load_active_mission_state, render_mission_brief

    try:
        artifact = load_active_mission_state(
            state_dir=state_dir or DHARMA_STATE,
            path=path,
        )
    except ValueError as exc:
        print(str(exc))
        return 1
    if artifact is None:
        state_root = Path(state_dir).expanduser() if state_dir else DHARMA_STATE
        mission_path = Path(path).expanduser() if path else state_root / "mission.json"
        print(f"No active mission state found at {mission_path}")
        return 1
    if as_json:
        print(json.dumps(artifact.model_dump(mode="json"), indent=2))
    else:
        print(render_mission_brief(artifact))
    return 0


def cmd_campaign_brief(
    *,
    path: str | None = None,
    state_dir: str | None = None,
    as_json: bool = False,
) -> int:
    """Show the active campaign continuity state for the director."""
    from dharma_swarm.mission_contract import load_active_campaign_state, render_campaign_brief

    try:
        artifact = load_active_campaign_state(
            state_dir=state_dir or DHARMA_STATE,
            path=path,
        )
    except ValueError as exc:
        print(str(exc))
        return 1
    if artifact is None:
        state_root = Path(state_dir).expanduser() if state_dir else DHARMA_STATE
        campaign_path = Path(path).expanduser() if path else state_root / "campaign.json"
        print(f"No active campaign state found at {campaign_path}")
        return 1
    if as_json:
        print(json.dumps(artifact.model_dump(mode="json"), indent=2))
    else:
        print(render_campaign_brief(artifact))
    return 0


def cmd_canonical_status(*, as_json: bool = False) -> int:
    """Show which local repos are canonical, support shells, or legacy."""
    from dharma_swarm.workspace_topology import build_workspace_topology

    topo = build_workspace_topology()
    if as_json:
        print(json.dumps(topo, indent=2))
        return 0

    print("=== DGC CANONICAL STATUS ===")
    for domain in ("dgc", "sab"):
        block = topo.get(domain, {})
        label = domain.upper()
        merged = "YES" if block.get("fully_merged") else "NO"
        print(f"\n[{label}] fully merged: {merged}")
        canonical_repo = block.get("canonical_repo") or "unknown"
        print(f"Canonical authority: {canonical_repo}")
        for repo in block.get("repos", []):
            if not repo.get("exists"):
                state = "missing"
            elif not repo.get("is_git"):
                state = "not-git"
            else:
                dirty = repo.get("dirty")
                if dirty is None:
                    state = "git-unknown"
                else:
                    counts = []
                    if repo.get("modified_count"):
                        counts.append(f"modified={repo['modified_count']}")
                    if repo.get("untracked_count"):
                        counts.append(f"untracked={repo['untracked_count']}")
                    suffix = f" ({', '.join(counts)})" if counts else ""
                    state = ("dirty" if dirty else "clean") + suffix
            marker = "canonical" if repo.get("canonical") else repo.get("role")
            branch = repo.get("branch") or "unknown-branch"
            print(f"  - {repo.get('name')}: {marker} | {branch} | {state}")
            print(f"    {repo.get('path')}")

    if topo.get("warnings"):
        print("\nWarnings:")
        for warning in topo["warnings"]:
            print(f"  - {warning}")

    merge_summary = topo.get("merge_summary") or {}
    if merge_summary:
        print("\nMerge ledger:")
        bits = []
        for key in ("snapshot", "branch", "head", "mission_exit", "tracked", "legacy_imported", "predictor_rows"):
            if merge_summary.get(key):
                bits.append(f"{key}={merge_summary[key]}")
        if bits:
            print(f"  - {' '.join(bits)}")

    answer = topo.get("operator_answer", {})
    print("\nOperator answer:")
    print(f"  - Use {answer.get('dgc_code_authority')} as DGC code authority")
    print(f"  - Use {answer.get('sab_runtime_authority')} as SAB runtime authority")
    print(f"  - Treat {answer.get('legacy_dgc_archive')} as legacy until explicitly archived/frozen")
    print(f"  - Treat {answer.get('sab_strategy_shell')} as SAB strategy shell, not runtime authority")
    return 0
