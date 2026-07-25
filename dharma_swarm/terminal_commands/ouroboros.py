"""Ouroboros behavioral observation and ledger commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
    _default_ouroboros_log_path,
    _load_json_object,
    _load_ouroboros_observation,
    _normalize_optional_text,
    _run,
    dharma_state_dir,
)


def cmd_ouroboros_connections(
    *,
    package_dir: str | None = None,
    threshold: float = 0.08,
    disagreement_threshold: float = 0.1,
    min_text_length: int = 50,
    limit: int = 15,
    as_json: bool = False,
) -> None:
    """Profile module docstrings and report behavioral affinities/disagreements."""
    from dharma_swarm.ouroboros import profile_python_modules

    if limit < 0:
        raise ValueError("limit must be >= 0")
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    if disagreement_threshold < 0:
        raise ValueError("disagreement_threshold must be >= 0")

    target_dir = Path(package_dir) if package_dir else DHARMA_SWARM / "dharma_swarm"
    finder, profiles = profile_python_modules(
        target_dir,
        min_text_length=min_text_length,
    )
    connections = finder.find_connections(threshold=threshold)
    disagreements = finder.find_h1_disagreements(threshold=disagreement_threshold)
    payload = {
        "package_dir": str(target_dir),
        "profiles": profiles,
        "connections": connections,
        "disagreements": disagreements,
        "summary": {
            "modules_profiled": len(profiles),
            "connections": len(connections),
            "disagreements": len(disagreements),
            "threshold": threshold,
            "disagreement_threshold": disagreement_threshold,
            "min_text_length": min_text_length,
        },
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"Profiling {len(profiles)} modules from {target_dir}...\n")
    for row in profiles[:limit]:
        print(
            f"  {row['module']:<30} "
            f"entropy={row['entropy']:.3f}  "
            f"self_ref={row['self_reference_density']:.4f}  "
            f"swabhaav={row['swabhaav_ratio']:.3f}  "
            f"recog={row['recognition_type']}"
        )
    if len(profiles) > limit:
        print(f"  ... {len(profiles) - limit} more module profiles")

    print("\n" + "=" * 80)
    print("H0: STRUCTURAL CONNECTIONS (similar behavioral profiles)")
    print("=" * 80)
    if connections:
        for conn in connections[:limit]:
            print(
                f"  {conn['module_a']:<25} <-> {conn['module_b']:<25} "
                f"d={conn['distance']:.4f}  type={conn['connection_type']}"
            )
        if len(connections) > limit:
            print(f"  ... {len(connections) - limit} more H0 connections")
    else:
        print(f"  No close connections found (threshold={threshold:.3f})")

    print("\n" + "=" * 80)
    print("H1: PRODUCTIVE DISAGREEMENTS (divergent profiles)")
    print("=" * 80)
    if disagreements:
        for dis in disagreements[:limit]:
            print(
                f"  {dis['module_a']:<25} =/= {dis['module_b']:<25} "
                f"d={dis['distance']:.4f}  "
                f"type={dis['disagreement_type']}  "
                f"({dis['recognition_a']} vs {dis['recognition_b']})"
            )
        if len(disagreements) > limit:
            print(f"  ... {len(disagreements) - limit} more H1 disagreements")
    else:
        print(f"  No H1 disagreements found (threshold={disagreement_threshold:.3f})")

    print("\n" + "=" * 80)
    print("SYNTHESIS")
    print("=" * 80)
    print(f"\n  Modules profiled: {len(profiles)}")
    print(f"  H0 connections:   {len(connections)}")
    print(f"  H1 disagreements: {len(disagreements)}")


async def _ouroboros_record_payload(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    log_path: str | None = None,
    cycle_id: str | None = None,
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> dict[str, Any]:
    from dharma_swarm.evaluation_registry import EvaluationRegistry
    from dharma_swarm.memory_lattice import MemoryLattice
    from dharma_swarm.runtime_state import RuntimeStateStore

    normalized_run_id = _normalize_optional_text(run_id)
    normalized_session_id = _normalize_optional_text(session_id)
    normalized_task_id = _normalize_optional_text(task_id)
    normalized_trace_id = _normalize_optional_text(trace_id) or None
    normalized_cycle_id = _normalize_optional_text(cycle_id) or None
    if not normalized_run_id and not normalized_session_id:
        raise ValueError("session_id or run_id is required to record evaluation outputs canonically")

    inline_payload_requested = json_payload is not None or file_path is not None
    if inline_payload_requested and (log_path is not None or normalized_cycle_id is not None):
        raise ValueError(
            "ouroboros record accepts either --json/--file or --log-path/--cycle-id, not both"
        )

    resolved_log_path: Path | None
    if inline_payload_requested:
        observation_payload = _load_json_object(
            json_payload=json_payload,
            file_path=file_path,
            label="ouroboros observation payload",
        )
        resolved_log_path = None
    else:
        resolved_log_path = Path(log_path) if log_path else _default_ouroboros_log_path()
        observation_payload = _load_ouroboros_observation(
            log_path=resolved_log_path,
            cycle_id=normalized_cycle_id,
        )

    runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
    memory_lattice = MemoryLattice(
        db_path=runtime_state.db_path,
        event_log_dir=Path(event_log_dir) if event_log_dir else None,
    )
    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=Path(workspace_root) if workspace_root else None,
        provenance_root=Path(provenance_root) if provenance_root else None,
    )
    try:
        result = await registry.record_ouroboros_observation(
            observation_payload,
            run_id=normalized_run_id,
            session_id=normalized_session_id,
            task_id=normalized_task_id,
            trace_id=normalized_trace_id,
            created_by="dgc_cli",
        )
    finally:
        await memory_lattice.close()

    return {
        "observation": observation_payload,
        "log_path": str(resolved_log_path) if resolved_log_path is not None else None,
        "registry": {
            "artifact_id": result.artifact.artifact_id,
            "manifest_path": str(result.manifest_path),
            "summary": dict(result.summary),
            "fact_ids": [fact.fact_id for fact in result.facts],
            "receipt_event_id": str(result.receipt.get("event_id", "")),
        },
    }


def cmd_ouroboros_record(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    log_path: str | None = None,
    cycle_id: str | None = None,
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> None:
    """Record an ouroboros observation into canonical runtime truth."""

    payload = _run(
        _ouroboros_record_payload(
            run_id=run_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            log_path=log_path,
            cycle_id=cycle_id,
            json_payload=json_payload,
            file_path=file_path,
            db_path=db_path,
            event_log_dir=event_log_dir,
            workspace_root=workspace_root,
            provenance_root=provenance_root,
        )
    )
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# v0.4.0: Oz-inspired commands
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Ledger viewer
# ---------------------------------------------------------------------------

def cmd_ledger(
    ledger_cmd: str | None = None,
    n: int = 20,
    session: str | None = None,
    kind: str = "all",
    query: str | None = None,
    db_path: str | None = None,
    sync_ledgers: bool = True,
    limit_sessions: int | None = None,
) -> None:
    """Inspect orchestrator session ledgers."""
    ledger_base = dharma_state_dir() / "ledgers"

    if ledger_cmd == "sessions" or ledger_cmd is None:
        if not ledger_base.exists():
            print("No ledgers directory found at ~/.dharma/ledgers/")
            return
        sessions = sorted(
            (p for p in ledger_base.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        if not sessions:
            print("No sessions found.")
            return
        print(f"{'Session ID':<22} {'Task':>6} {'Progress':>10} {'Age':>10}")
        print("-" * 52)
        import time as _time
        now = _time.time()
        for sess in sessions:
            tf = sess / "task_ledger.jsonl"
            pf = sess / "progress_ledger.jsonl"
            tc = sum(1 for _ in open(tf)) if tf.exists() else 0
            pc = sum(1 for _ in open(pf)) if pf.exists() else 0
            age_h = (now - sess.stat().st_mtime) / 3600
            age_s = f"{age_h:.1f}h" if age_h < 48 else f"{age_h/24:.0f}d"
            print(f"{sess.name:<22} {tc:>6} {pc:>10} {age_s:>10}")
        if ledger_cmd is None:
            print("\nUsage: dgc ledger tail | dgc ledger sessions")
        return

    if ledger_cmd == "tail":
        if not ledger_base.exists():
            print("No ledgers directory found.")
            return
        sessions = sorted(
            (p for p in ledger_base.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not sessions:
            print("No sessions found.")
            return
        target = (ledger_base / session) if session else sessions[0]
        if not target.exists():
            print(f"Session not found: {session}")
            return
        print(f"Session: {target.name}")

        def _tail_file(path: Path, label: str) -> None:
            if not path.exists():
                return
            lines = [l for l in path.read_text().splitlines() if l.strip()][-n:]
            if not lines:
                return
            print(f"\n{label} ({path.name})")
            for line in lines:
                try:
                    ev = json.loads(line)
                    ts = ev.get("ts_utc", "")[:19]
                    event = ev.get("event", "?")
                    tid = ev.get("task_id", "")[:8]
                    extra = ""
                    if "duration_sec" in ev:
                        extra = f" ({ev['duration_sec']:.2f}s)"
                    if "failure_signature" in ev:
                        extra = f" sig={ev['failure_signature'][:50]}"
                    print(f"  {ts}  {event:<28} {tid}{extra}")
                except Exception:
                    print(f"  {line[:120]}")

        if kind in ("task", "all"):
            _tail_file(target / "task_ledger.jsonl", "Task Ledger")
        if kind in ("progress", "all"):
            _tail_file(target / "progress_ledger.jsonl", "Progress Ledger")
        return

    if ledger_cmd == "index":
        from dharma_swarm.runtime_state import RuntimeStateStore

        runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
        sessions_scanned, events_scanned = runtime_state.index_ledgers_sync(
            ledger_base=ledger_base,
            session_id=session,
            limit_sessions=limit_sessions,
        )
        print(
            f"Indexed {events_scanned} ledger events across "
            f"{sessions_scanned} session(s) into {runtime_state.db_path}"
        )
        return

    if ledger_cmd == "search":
        from dharma_swarm.runtime_state import RuntimeStateStore

        normalized_query = (query or "").strip()
        if not normalized_query:
            print("Search query is required.")
            return
        runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
        if sync_ledgers:
            runtime_state.index_ledgers_sync(
                ledger_base=ledger_base,
                session_id=session,
                limit_sessions=limit_sessions,
            )
        ledger_kind = None if kind == "all" else kind
        results = runtime_state.search_session_events_sync(
            normalized_query,
            session_id=session,
            ledger_kind=ledger_kind,
            limit=n,
        )
        if not results:
            print(f"No indexed ledger events matched: {normalized_query}")
            return
        print(f"Search: {normalized_query}")
        for item in results:
            ts = item.created_at.isoformat()[:19]
            task = item.task_id[:8] if item.task_id else "-"
            summary = item.summary or item.event_text
            summary = " ".join(summary.split())
            if len(summary) > 96:
                summary = summary[:93] + "..."
            print(
                f"  {ts}  {item.session_id:<22} {item.ledger_kind:<8} "
                f"{item.event_name:<28} {task}  {summary}"
            )
        return

    print(f"Unknown ledger subcommand: {ledger_cmd}")
    print("Usage: dgc ledger tail | dgc ledger sessions | dgc ledger search | dgc ledger index")


# ---------------------------------------------------------------------------
# Semantic Evolution Engine
# ---------------------------------------------------------------------------

_DEFAULT_GRAPH_PATH = DHARMA_STATE / "semantic" / "concept_graph.json"
