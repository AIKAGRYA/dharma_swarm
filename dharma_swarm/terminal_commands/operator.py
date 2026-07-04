"""Operator workflow commands (cron, sprint, foreman, review, initiatives)."""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Cron and Gateway commands (v0.6.0)
# ---------------------------------------------------------------------------


from dharma_swarm.terminal_commands._helpers import (
    DEFAULT_SPRINT_LLM_TIMEOUT_SEC,
    _get_swarm,
    _run,
)

def cmd_cron(
    cron_cmd: str | None,
    prompt: str = "",
    schedule: str = "",
    name: str | None = None,
    repeat: int | None = None,
    deliver: str = "local",
    urgent: bool = False,
    job_id: str = "",
    interval_sec: float = 60.0,
    max_loops: int | None = None,
    run_immediately: bool = True,
) -> None:
    """Cron scheduler commands."""
    from dharma_swarm.cron_scheduler import (
        create_job,
        list_jobs,
        remove_job,
        tick,
    )
    from dharma_swarm.cron_daemon import run_cron_daemon
    from dharma_swarm.cron_runner import run_cron_job

    match cron_cmd:
        case "add":
            job = create_job(
                prompt=prompt,
                schedule=schedule,
                name=name,
                repeat=repeat,
                deliver=deliver,
                urgent=urgent,
            )
            print(f"  Created job {job['id']}: {job['name']}")
            print(f"  Schedule: {job['schedule_display']}")
            print(f"  Next run: {job.get('next_run_at', 'N/A')}")
        case "list":
            jobs = list_jobs(include_disabled=True)
            if not jobs:
                print("  No cron jobs.")
                return
            for j in jobs:
                status = j.get("last_status") or "UNKNOWN"
                enabled = "✓" if j.get("enabled", True) else "✗"
                repeat = j.get("repeat") or {}
                completed = repeat.get("completed", 0)
                times = repeat.get("times")
                repeat_str = f"{completed}/{times}" if times else f"{completed}/∞"
                job_id = str(j.get("id") or "-")
                job_name = str(
                    j.get("name")
                    or j.get("handler")
                    or j.get("prompt")
                    or job_id
                )
                print(f"  {enabled} {job_id}  {job_name[:40]:<40}  "
                      f"{j.get('schedule_display', '?'):<20}  "
                      f"runs={repeat_str}  last={status}")
        case "remove":
            if remove_job(job_id):
                print(f"  Removed job {job_id}")
            else:
                print(f"  Job {job_id} not found")
        case "tick":
            executed = tick(verbose=True, run_fn=run_cron_job)
            print(f"  Tick complete: {executed} job(s) executed")
        case "daemon":
            executed = run_cron_daemon(
                interval_sec=interval_sec,
                max_loops=max_loops,
                run_immediately=run_immediately,
                tick_verbose=False,
            )
            print(f"  Cron daemon exited: {executed} job(s) executed")
        case _:
            print("Usage: dgc cron {add|list|remove|tick|daemon}")


# ---------------------------------------------------------------------------
# Sprint generator
# ---------------------------------------------------------------------------

def cmd_sprint(
    output: str | None = None,
    local: bool = False,
    test_summary: str = "",
    prev_todo: str = "",
    llm_timeout_sec: float = DEFAULT_SPRINT_LLM_TIMEOUT_SEC,
) -> None:
    """Generate today's adaptive 8-hour sprint prompt from live system state."""
    from datetime import date as _date
    from dharma_swarm.master_prompt_engineer import (
        gather_system_state,
        generate_evolved_prompt,
        generate_local_prompt,
        _SHARED_DIR,
    )
    from dharma_swarm.research_deadlines import deadline_line

    today = _date.today().strftime("%Y%m%d")
    out_path = Path(output) if output else _SHARED_DIR / f"SPRINT_8H_{today}.md"
    research_line = deadline_line()

    print(f"[sprint] Generating sprint for {today}")
    print(f"  Research deadline: {research_line}")

    state = gather_system_state()
    live = state.get("live_signals", {})
    morning_ok = "no morning" not in live.get("morning_brief", "no morning")
    dream_ok = "no dream" not in live.get("dream_seeds", "no dream")
    handoff_ok = "no handoff" not in live.get("sprint_handoff", "no handoff")
    print(f"  signals: morning={'yes' if morning_ok else 'none'} "
          f"dreams={'yes' if dream_ok else 'none'} "
          f"handoff={'yes' if handoff_ok else 'none'}")

    if local:
        prompt_text = generate_local_prompt(
            test_summary=test_summary,
            prev_todo=prev_todo,
            deadline_line=research_line,
        )
        mode = "local"
    else:
        try:
            import asyncio as _asyncio
            prompt_text = _asyncio.run(generate_evolved_prompt(
                system_state=state,
                test_summary=test_summary,
                prev_todo=prev_todo,
                deadline_line=research_line,
                llm_timeout_sec=llm_timeout_sec,
            ))
            mode = "LLM"
        except Exception as exc:
            print(f"  LLM unavailable ({exc}), using local mode")
            prompt_text = generate_local_prompt(
                test_summary=test_summary,
                prev_todo=prev_todo,
                deadline_line=research_line,
            )
            mode = "local (fallback)"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"# 8-HOUR SPRINT — {today}\n"
        f"**Generated**: {_date.today().isoformat()} | **Mode**: {mode}\n"
        f"**Research deadline**: {research_line}\n\n"
        + prompt_text
    )
    print(f"[sprint] Written to: {out_path}")
    print(f"  length: {len(prompt_text):,} chars | mode: {mode}")


# ---------------------------------------------------------------------------
# Ledger viewer
# ---------------------------------------------------------------------------


def cmd_run(interval: float) -> None:
    """Run the orchestration loop."""
    async def _run_loop():
        swarm = await _get_swarm()
        print("DHARMA SWARM running. Ctrl+C to stop.")
        try:
            await swarm.run(interval=interval)
        except KeyboardInterrupt:
            pass
        finally:
            await swarm.shutdown()
            print("Swarm stopped.")

    _run(_run_loop())


def cmd_foreman(
    foreman_cmd: str | None = None,
    path: str = "",
    name: str | None = None,
    test_command: str | None = None,
    exclude: list[str] | None = None,
    level: str = "observe",
    project: str | None = None,
    skip_tests: bool = False,
    schedule: str = "every 4h",
) -> None:
    """Foreman Quality Forge commands."""
    from dharma_swarm.foreman import (
        add_project,
        format_status,
        run_cycle,
        create_foreman_cron_job,
    )

    match foreman_cmd:
        case "add":
            if not path:
                print("  Error: path is required")
                return
            entry = add_project(
                path=path,
                name=name,
                test_command=test_command,
                exclude=exclude or [],
            )
            print(f"  Registered: {entry.name} ({entry.path})")
        case "run":
            if level not in ("observe", "advise", "build"):
                print(f"  Error: level must be observe/advise/build, got {level}")
                return
            report = run_cycle(
                level=level,
                project_filter=project,
                skip_tests=skip_tests,
            )
            print(f"  Forge cycle complete ({report.duration_seconds}s, {len(report.per_project)} projects)\n")
            for p in report.per_project:
                weakest = p["weakest_dimension"]
                print(f"  {p['name']}: {p['grade']} (avg={p['avg_quality']:.2f})")
                print(f"    weakest: {weakest}={p['dimensions'][weakest]:.2f}")
                print(f"    → {p['task']['task']}")
        case "status":
            print(format_status())
        case "cron":
            job = create_foreman_cron_job(every=schedule, level=level)
            print(f"  Foreman cron job: {job.get('id', '?')}")
            print(f"  Schedule: {job.get('schedule_display', schedule)}")
            print(f"  Level: {level}")
        case _:
            print("Usage: dgc foreman {add|run|status|cron}")
            print("  add <path>          Register a project")
            print("  run [--level L]     Run one forge cycle")
            print("  status              Show quality dashboard")
            print("  cron [--schedule S] Start recurring forge")


def cmd_review(hours: float = 6.0, skip_tests: bool = False) -> None:
    """Manually trigger a review cycle report."""
    from dharma_swarm.review_cycle import generate_review_sync

    print(f"  Generating {hours:.0f}h review cycle report...")
    report = generate_review_sync(
        hours=hours,
        run_tests=not skip_tests,
    )
    print(report)


def cmd_initiatives(
    init_cmd: str | None = None,
    title: str = "",
    description: str = "",
    initiative_id: str = "",
    reason: str = "",
) -> None:
    """Initiative depth ledger commands."""
    from dharma_swarm.iteration_depth import IterationLedger

    ledger = IterationLedger()
    ledger.load()

    match init_cmd:
        case "list":
            inits = ledger.get_all()
            if not inits:
                print("  No initiatives tracked.")
                return
            for i in sorted(inits, key=lambda x: x.updated_at, reverse=True):
                icon = {"seed": "\U0001f331", "growing": "\U0001f33f",
                        "solid": "\U0001faa8", "shipped": "\U0001f680",
                        "abandoned": "\u274c"}.get(i.status.value, "?")
                print(f"  {icon} {i.id}  {i.title[:40]:<40}  "
                      f"iter={i.iteration_count}  quality={i.quality_score:.3f}  "
                      f"status={i.status.value}")
        case "add":
            if not title:
                print("  Error: --title is required")
                return
            init = ledger.create(title=title, description=description)
            print(f"  Created initiative {init.id}: {init.title}")
        case "abandon":
            if not initiative_id or not reason:
                print("  Error: initiative_id and --reason are required")
                return
            if ledger.abandon(initiative_id, reason):
                print(f"  Abandoned {initiative_id}: {reason}")
            else:
                print(f"  Initiative {initiative_id} not found")
        case "promote":
            if not initiative_id:
                print("  Error: initiative_id is required")
                return
            ok, msg = ledger.promote(initiative_id)
            icon = '\u2705' if ok else '\u274c'
            print(f"  {icon} {msg}")
        case "summary":
            summary = ledger.summary()
            print(f"  Total: {summary['total']}  Active: {summary['active_count']}")
            print(f"  Avg iterations: {summary['avg_iterations']}  "
                  f"Avg quality: {summary['avg_quality']:.3f}")
            if summary["shallow"]:
                print(f"  Shallow ({summary['shallow_count']}):")
                for s in summary["shallow"]:
                    print(f"    - {s['title']}: {s['iterations']} iterations")
            if summary["ready_to_promote"]:
                print(f"  Ready to promote:")
                for r in summary["ready_to_promote"]:
                    print(f"    - {r['title']}: quality={r['quality']:.3f}")
        case _:
            print("Usage: dgc initiatives {list|add|abandon|promote|summary}")
