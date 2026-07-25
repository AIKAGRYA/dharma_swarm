"""Diagnostics, health, and loop inspection commands."""

from __future__ import annotations

import asyncio
import json
import os
import time


# ---------------------------------------------------------------------------
# Commands — carried over from dgc-core
# ---------------------------------------------------------------------------


from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    HOME,
    _get_swarm,
    _pid_alive,
    _run,
    _tail,
)
from dharma_swarm.terminal_commands._status_helpers import (
    _canonical_pulse_summary,
)


def cmd_loops() -> None:
    """Show strange loop status and cascade history."""
    import json
    from pathlib import Path as P

    state_dir = P.home() / ".dharma"
    meta_dir = state_dir / "meta"

    # Recognition seed
    seed_path = meta_dir / "recognition_seed.md"
    if seed_path.exists():
        lines = seed_path.read_text().split("\n")
        print(f"Recognition seed: {len(seed_path.read_text())} chars ({lines[0].strip()})")
    else:
        print("Recognition seed: NOT YET GENERATED")

    # TCS
    tcs_path = state_dir / "stigmergy" / "mycelium_identity_tcs.json"
    if tcs_path.exists():
        try:
            d = json.loads(tcs_path.read_text())
            print(f"TCS: {d.get('tcs', '?')} ({d.get('regime', '?')})")
        except Exception:
            print("TCS: error reading")
    else:
        print("TCS: no data")

    # Cascade history
    history_path = meta_dir / "cascade_history.jsonl"
    if history_path.exists():
        lines = [l for l in history_path.read_text().strip().split("\n") if l.strip()]
        print(f"\nCascade history: {len(lines)} runs")
        for line in lines[-5:]:
            try:
                d = json.loads(line)
                status = "EIGENFORM" if d.get("eigenform_reached") else ("CONVERGED" if d.get("converged") else "INCOMPLETE")
                print(f"  {d.get('domain', '?')}: {status} fitness={d.get('best_fitness', 0):.3f} iter={d.get('iterations', 0)}")
            except json.JSONDecodeError:
                pass
    else:
        print("\nCascade history: no runs yet")

    # Daemon status
    pid_file = state_dir / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            print(f"\nDaemon: running (PID {pid})")
        except (ValueError, OSError):
            print("\nDaemon: dead (stale PID file)")
    else:
        print("\nDaemon: not running")

    # Domain summary (latest scores per domain)
    if history_path.exists():
        all_lines = [l for l in history_path.read_text().strip().split("\n") if l.strip()]
        latest_by_domain: dict[str, dict] = {}
        for line in all_lines:
            try:
                d = json.loads(line)
                domain_name = d.get("domain", "?")
                latest_by_domain[domain_name] = d
            except json.JSONDecodeError:
                pass
        if latest_by_domain:
            print("\nDomain states:")
            for name in sorted(latest_by_domain):
                d = latest_by_domain[name]
                status = "EIGENFORM" if d.get("eigenform_reached") else ("CONVERGED" if d.get("converged") else "INCOMPLETE")
                note = f" ({d.get('note', '')})" if d.get("note") else ""
                print(f"  {name:10s}: {status:10s} fitness={d.get('best_fitness', 0):.3f}{note}")

    # Scoring reports
    scoring_report = state_dir / "stigmergy" / "mycelium_scoring_report.json"
    skill_health = state_dir / "stigmergy" / "mycelium_skill_health.json"
    if scoring_report.exists():
        try:
            d = json.loads(scoring_report.read_text())
            print(f"\nModule scoring: {d.get('scored_count', '?')} modules, mean {d.get('mean_stars', 0):.2f} stars")
        except Exception:
            pass
    if skill_health.exists():
        try:
            d = json.loads(skill_health.read_text())
            print(f"Skill health:   {d.get('healthy', '?')}/{d.get('total_skills', '?')} healthy, mean {d.get('mean_stars', 0):.1f} stars")
        except Exception:
            pass

    # Signal bus
    try:
        from dharma_swarm.signal_bus import SignalBus
        bus = SignalBus.get()
        cascade_signals = bus.drain(["CASCADE_COMPLETE"])
        if cascade_signals:
            print(f"\nSignal bus: {len(cascade_signals)} cascade completion(s) pending")
        else:
            print("\nSignal bus: clear")
    except Exception:
        print("\nSignal bus: not available")


def cmd_invariants() -> None:
    """Show the 4 computable system invariants.

    Reads REAL data from: catalytic graph, task board, evolution archive,
    and agent roster to compute invariants from actual system state.
    """
    from dharma_swarm.invariants import snapshot
    import numpy as np
    import json

    state_dir = dharma_state_dir()

    # 1. Catalytic graph → criticality + closure
    try:
        from dharma_swarm.catalytic_graph import CatalyticGraph
        graph = CatalyticGraph()
        if not graph.load():
            # No persisted graph — fall back to hardcoded seed
            graph.seed_ecosystem()
        mat, nodes = graph.adjacency_matrix()
        total_nodes = graph.node_count
        ac_sets = graph.detect_autocatalytic_sets()
        ac_count = sum(len(s) for s in ac_sets)
    except Exception:
        mat = np.zeros((0, 0))
        total_nodes = 0
        ac_count = 0

    # 2. Evolution archive → info retention (mutation rate vs selective advantage)
    mutation_rate = 0.0
    selective_advantage = 1.0
    genome_length = 9
    archive_coverage = 0.0
    try:
        archive_path = state_dir / "evolution" / "archive.jsonl"
        if archive_path.exists():
            entries = [json.loads(l) for l in archive_path.read_text().strip().split("\n") if l.strip()]
            if entries:
                genome_length = max(len(entries), 9)
                # Estimate mutation rate from recent entries
                recent = entries[-20:]
                if len(recent) >= 2:
                    fitnesses = [e.get("fitness", {}).get("weighted", 0.0) for e in recent]
                    if fitnesses:
                        selective_advantage = max(fitnesses) - min(fitnesses) + 0.01
                        mutation_rate = sum(1 for f in fitnesses if f < 0.3) / len(fitnesses)
                archive_coverage = len(set(e.get("component", "") for e in entries if e.get("component"))) / max(genome_length, 1)
    except Exception:
        pass

    # 3. Agent diversity → diversity equilibrium
    kv_diversity = None
    try:
        # Count unique active agent models from stigmergy
        marks_path = state_dir / "stigmergy" / "marks.jsonl"
        if marks_path.exists():
            lines = marks_path.read_text().strip().split("\n")[-100:]  # last 100 marks
            agents = set()
            for l in lines:
                if l.strip():
                    try:
                        m = json.loads(l)
                        agents.add(m.get("agent", ""))
                    except json.JSONDecodeError:
                        pass
            if agents:
                kv_diversity = min(len(agents) / 10.0, 1.0)  # normalize: 10 unique agents = 1.0
    except Exception:
        pass

    # 4. Task board → supplementary info for display
    task_info = ""
    try:
        import asyncio
        from dharma_swarm.task_board import TaskBoard
        db_path = state_dir / "db" / "tasks.db"
        if db_path.exists():
            board = TaskBoard(db_path)
            asyncio.get_event_loop().run_until_complete(board.init_db())
            stats = asyncio.get_event_loop().run_until_complete(board.stats())
            task_info = f"  Tasks: {stats.get('completed', 0)} completed, {stats.get('failed', 0)} failed, {stats.get('total', 0)} total"
    except Exception:
        pass

    snap = snapshot(
        adjacency_matrix=mat,
        total_nodes=total_nodes,
        autocatalytic_node_count=ac_count,
        mutation_rate=mutation_rate,
        selective_advantage=selective_advantage,
        genome_length=genome_length,
        archive_coverage=archive_coverage,
        kv_diversity=kv_diversity,
    )

    print("=== System Invariants ===")
    print(f"  Criticality (λ_max):   {snap.criticality:.4f}  [{snap.criticality_status}]")
    print(f"  Closure ratio:          {snap.closure_ratio:.4f}  [{snap.closure_status}]")
    print(f"  Info retention:         {snap.info_retention:.6f}  [{snap.info_retention_status}]")
    print(f"  Diversity equilibrium:  {snap.diversity_equilibrium:.4f}  [{snap.diversity_status}]")
    print(f"  Overall:                {snap.overall}")
    print(f"  Timestamp:              {snap.timestamp}")
    if task_info:
        print(task_info)
    # Data sources
    print(f"  Data: adj_matrix={mat.shape}, nodes={total_nodes}, ac_sets={ac_count}, "
          f"archive_cov={archive_coverage:.2f}, agents={snap.diversity_equilibrium:.2f}")


def cmd_transcendence() -> None:
    """Show transcendence metrics (ensemble vs individual)."""
    try:
        from dharma_swarm.ginko_brier import ensemble_brier_report
        report = ensemble_brier_report()
        print("=== Transcendence Report ===")
        print(f"  Status: {report['status']}")
        if report.get("ensemble_brier") is not None:
            print(f"  Ensemble Brier:       {report['ensemble_brier']}")
            print(f"  Best Individual:      {report.get('best_individual_brier', 'N/A')}")
            print(f"  Mean Individual:      {report.get('mean_individual_brier', 'N/A')}")
            print(f"  Transcendence Margin: {report.get('transcendence_margin', 'N/A')}")
            print(f"  Aggregation Lift:     {report.get('aggregation_lift', 'N/A')}")
            print(f"  Transcended:          {report.get('transcended', 'N/A')}")
        if report.get("individual_briers"):
            print(f"\n  Individual Brier Scores:")
            for src, score in sorted(report["individual_briers"].items()):
                print(f"    {src}: {score}")
    except Exception as e:
        print(f"Transcendence report unavailable: {e}")


def cmd_health(*, as_json: bool = False) -> None:
    """Check ecosystem file health."""
    try:
        from dharma_swarm.ecosystem_map import check_health

        h = check_health()

        if as_json:
            print(json.dumps(h, indent=2, default=str))
            return

        print(f"Ecosystem: {h['ok']} OK, {h['missing']} MISSING")
        if h["details"]:
            print("\nMissing paths:")
            for p, d in h["details"].items():
                print(f"  {p} -- {d}")
    except ImportError:
        if as_json:
            print(json.dumps({"error": "ecosystem_map not available"}))
        else:
            print("ecosystem_map not available")


def cmd_health_check() -> None:
    """Monitor-based system health check (v0.2.0)."""
    async def _check():
        swarm = await _get_swarm()
        report = await swarm.health_check()
        status = report.get("overall_status", "unknown")
        print(f"Overall: {status}")
        print(f"  Total traces: {report.get('total_traces', 0)}")
        print(f"  Traces last hour: {report.get('traces_last_hour', 0)}")
        print(f"  Failure rate: {report.get('failure_rate', 0):.1%}")
        mean_f = report.get("mean_fitness")
        if mean_f is not None:
            print(f"  Mean fitness: {mean_f:.3f}")
        anomalies = report.get("anomalies", [])
        if anomalies:
            print(f"\nAnomalies ({len(anomalies)}):")
            for a in anomalies:
                print(f"  [{a.get('severity', '?')}] {a.get('description', '')}")
        await swarm.shutdown()

    _run(_check())


def cmd_doctor(
    *,
    doctor_cmd: str = "run",
    as_json: bool = False,
    strict: bool = False,
    quick: bool = False,
    timeout: float = 1.5,
    schedule: str = "every 6h",
    interval_sec: float = 1800.0,
    max_runs: int | None = None,
) -> int:
    """Deep readiness diagnostics and recurring assurance control."""
    from dharma_swarm.doctor import (
        create_doctor_job,
        doctor_exit_code,
        load_latest_doctor_report,
        render_doctor_report,
        run_doctor,
        write_doctor_artifacts,
    )

    if doctor_cmd == "schedule":
        job = create_doctor_job(
            schedule=schedule,
            quick=quick,
            strict=strict,
            timeout_seconds=timeout,
        )
        print(f"Doctor job created: {job['id']}")
        print(f"  Name: {job['name']}")
        print(f"  Schedule: {job.get('schedule_display', schedule)}")
        print(f"  Handler: {job.get('handler', 'doctor_assurance')}")
        print("  Next step: ensure `dgc cron daemon` or the launchd cron service is running.")
        return 0

    if doctor_cmd == "latest":
        report = load_latest_doctor_report()
        if report is None:
            print("No cached Doctor report found at ~/.dharma/doctor/latest_report.json")
            return 1
        if as_json:
            print(json.dumps(report, indent=2))
        else:
            print(render_doctor_report(report))
        return doctor_exit_code(report, strict=strict)

    if doctor_cmd == "watch":
        runs = 0
        while True:
            report = run_doctor(timeout_seconds=timeout, quick=quick)
            write_doctor_artifacts(report)
            if runs:
                print()
            print(render_doctor_report(report) if not as_json else json.dumps(report, indent=2))
            runs += 1
            if max_runs is not None and runs >= max_runs:
                return doctor_exit_code(report, strict=strict)
            time.sleep(max(1.0, interval_sec))

    report = run_doctor(timeout_seconds=timeout, quick=quick)
    write_doctor_artifacts(report)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(render_doctor_report(report))
    return doctor_exit_code(report, strict=strict)


def cmd_ui(surface: str = "list") -> None:
    """Print the canonical operator-surface map."""
    root = HOME / "dharma_swarm"
    dashboard_dir = root / "dashboard"
    lines: list[str] = []

    if surface == "tui":
        lines.extend(
            [
                "TUI",
                f"- primary operator cockpit: dgc dashboard",
                f"- direct module: python3 -m dharma_swarm.tui",
                f"- code: {root / 'dharma_swarm' / 'tui' / 'app.py'}",
            ]
        )
    elif surface == "api":
        lines.extend(
            [
                "API",
                f"- command: cd {root} && python3 -m uvicorn api.main:app --port 8000",
                "- url: http://127.0.0.1:8000",
                "- docs: http://127.0.0.1:8000/docs",
            ]
        )
    elif surface == "next":
        lines.extend(
            [
                "DHARMA COMMAND",
                f"- command: cd {dashboard_dir} && npm run dev",
                "- url: http://127.0.0.1:3000/dashboard",
                "- backend dependency: api.main on port 8000",
                f"- frontend root: {dashboard_dir}",
            ]
        )
    elif surface == "lens":
        lines.extend(
            [
                "SWARMLENS",
                f"- command: cd {root} && python3 -m uvicorn dharma_swarm.swarmlens_app:app --port 8080",
                "- url: http://127.0.0.1:8080",
                "- likely the older website you remember",
                f"- code: {root / 'dharma_swarm' / 'swarmlens_app.py'}",
            ]
        )
    else:
        lines.extend(
            [
                "Operator surfaces",
                "- `dgc dashboard` -> primary terminal TUI",
                f"  code: {root / 'dharma_swarm' / 'tui' / 'app.py'}",
                "- `dgc ui next` -> newer web control plane",
                f"  launch: cd {dashboard_dir} && npm run dev",
                "  url: http://127.0.0.1:3000/dashboard",
                "  needs backend: python3 -m uvicorn api.main:app --port 8000",
                "- `dgc ui lens` -> older SwarmLens website",
                f"  launch: cd {root} && python3 -m uvicorn dharma_swarm.swarmlens_app:app --port 8080",
                "  url: http://127.0.0.1:8080",
                "  note: this is likely the older website you remember",
                "- `dgc ui api` -> backend API only",
                "  url: http://127.0.0.1:8000/docs",
            ]
        )

    print("\n".join(lines))


def cmd_pulse() -> None:
    """Run one heartbeat pulse."""
    from dharma_swarm.pulse import pulse

    response = pulse()
    print(response)


def cmd_organism_pulse(task: str | None = None, dry_run: bool = False) -> None:
    """Run one canonical organism pulse (9 stages)."""

    async def _run():
        from dharma_swarm.organism_pulse import run_pulse

        result = await run_pulse(
            task=None if dry_run else task,
            persist=True,
        )
        print(f"Pulse {result.pulse_id}")
        print(f"  Duration: {result.duration_ms:.0f}ms")
        print(f"  Health:   {result.overall_health}")
        print(f"  Gate:     {result.gate_decision}")
        print(f"  Agents:   {result.agent_count}")
        if result.invariants:
            inv = result.invariants
            print(f"  Invariants:")
            print(f"    Criticality:  {inv.criticality:.4f} ({inv.criticality_status})")
            print(f"    Closure:      {inv.closure_ratio:.4f} ({inv.closure_status})")
            print(f"    Info Retain:   {inv.info_retention:.6f} ({inv.info_retention_status})")
            print(f"    Diversity:    {inv.diversity_equilibrium:.4f} ({inv.diversity_status})")
            print(f"    Overall:      {inv.overall}")
        if result.transcendence_metrics:
            tm = result.transcendence_metrics
            print(f"  Transcendence:")
            print(f"    Margin:    {tm.transcendence_margin:.4f}")
            print(f"    Diversity: {tm.behavioral_div:.4f}")
            print(f"    Families:  {tm.n_model_families}")
        if result.prediction:
            print(f"  Self-Prediction:")
            print(f"    Predicted: {result.prediction.predicted_duration_ms:.0f}ms")
            if result.prediction.duration_error is not None:
                print(f"    Error:     {result.prediction.duration_error:.0f}ms")
            if result.prediction.surprise:
                print(f"    SURPRISE detected!")
        print(f"  Stages: {result.stage_timings}")

    asyncio.run(_run())


def cmd_daemon_status() -> None:
    """Show daemon state."""
    pid_file = DHARMA_STATE / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            print("  status: stale PID file")
        else:
            if _pid_alive(pid):
                print(f"  status: running (PID {pid})")
            else:
                print("  status: stale PID file")
    else:
        print("  status: not running")
    pulse_count, last_pulse, pulse_source = _canonical_pulse_summary()
    if last_pulse and pulse_source is not None:
        print(f"  pulse_log: {pulse_count} logged via {pulse_source}, last: {last_pulse}")
        for line in _tail(pulse_source, lines=5).splitlines():
            print(f"    {line[:120]}")
    else:
        print("  pulse_log: no entries")
