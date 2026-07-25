"""Execution dispatch for scheduled cron jobs."""

from __future__ import annotations

import json
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.cron_algedonic_handlers import (
    run_algedonic_triage,
    run_provider_starvation_alert,
)
from dharma_swarm.cron_job_runtime import CronJobExecutionResult, CronJobRunStatus
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.context import (
    read_agni_state,
    read_manifest,
    read_memory_context,
    read_trishula_inbox,
)
from dharma_swarm.job_capabilities import (
    JobCapabilityProfile,
    JobExecutionSurface,
    resolve_job_capability_profile,
)
from dharma_swarm.cron_portable_context import (
    build_portable_job_prompt,
    persist_portable_job_output,
)
from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import complete_via_preferred_runtime_providers


_LOCAL_FALLBACK_ERROR_MARKERS = (
    "credit balance is too low",
    "not logged in",
    "please run /login",
    "claude cli not found",
    "unattended claude bare mode requires anthropic_api_key",
)

_ALLOWED_SHELL_COMMAND_PREFIXES = (
    ("python3", "scripts/consume_review_marks.py"),
    ("python3", "scripts/hermes_heartbeat_poll.py"),
    ("python3", "/Users/dhyana/dharmic-agora/scripts/sab_language_womb_tick.py"),
    ("/Users/dhyana/dharmic-agora/.venv/bin/python", "/Users/dhyana/dharmic-agora/scripts/sab_language_womb_tick.py"),
    ("python3", "scripts/check_provider_credits.py"),
    ("python3", "scripts/governance/name_drift_preflight.py"),
    (".venv/bin/python", "scripts/governance/name_drift_preflight.py"),
    ("bash", "scripts/refresh_provider_status.sh"),
    ("python3", "scripts/runtime/github_ingestor_runner.py"),
)


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    return default


def _run_system_map_populator(job: dict[str, Any]) -> CronJobExecutionResult:
    """Refresh reports/system_map/latest.json from local read-only probes."""

    import subprocess

    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "system_map_populator.py"
    if not script.exists():
        error = f"missing script: {script}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )
    args = ["python3", str(script)]
    audit_dir = str(job.get("audit_dir", "")).strip()
    output = str(job.get("output", "")).strip()
    if audit_dir:
        args.extend(["--audit-dir", audit_dir])
    if output:
        args.extend(["--output", output])
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=_as_int(job.get("timeout_sec"), 60),
        cwd=str(repo_root),
    )
    output_text = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    status = CronJobRunStatus.COMPLETED if proc.returncode == 0 else CronJobRunStatus.FAILED
    return CronJobExecutionResult(
        status=status,
        output=output_text or "(no output)",
        error=err if proc.returncode != 0 else "",
    )


def _run_shell_command(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run a shell command specified in the job's shell_command field.

    The command is split via shlex (no shell=True) to avoid injection risks.
    Commands come from cron_jobs.json and must match the operational allowlist.
    """

    import shlex
    import subprocess

    shell_cmd = str(job.get("shell_command", "")).strip()
    if not shell_cmd:
        error = "shell handler requires a 'shell_command' field"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )

    repo_root = Path(__file__).resolve().parent.parent
    timeout = _as_int(job.get("timeout_sec"), 120)
    args = shlex.split(shell_cmd)
    if not any(
        tuple(args[: len(prefix)]) == prefix
        for prefix in _ALLOWED_SHELL_COMMAND_PREFIXES
    ):
        error = f"shell handler command is not allowlisted: {args[0] if args else '(empty)'}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root),
        )
    except subprocess.TimeoutExpired:
        error = f"shell command timed out after {timeout}s: {shell_cmd}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output="",
            error=error,
        )
    except Exception as exc:
        error = f"shell command failed to launch: {exc}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output="",
            error=error,
        )

    output_text = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    status = CronJobRunStatus.COMPLETED if proc.returncode == 0 else CronJobRunStatus.FAILED
    return CronJobExecutionResult(
        status=status,
        output=output_text or "(no output)",
        error=err if proc.returncode != 0 else "",
    )


def _run_revenue_scout(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run the revenue scout daemon cycle."""
    try:
        from dharma_swarm.revenue.scout_daemon import revenue_scout_handler
        success, output, _error = revenue_scout_handler(job)
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED if success else CronJobRunStatus.FAILED,
            output=output,
            error=None if success else output[:500],
        )
    except Exception as exc:
        error = f"Revenue scout failed: {exc}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )


def _run_tcs_heartbeat(job: dict[str, Any]) -> CronJobExecutionResult:
    """Sample IdentityMonitor.measure() and append identity history locally."""

    try:
        from dharma_swarm.identity import IdentityMonitor

        state_dir = (
            Path(str(job["state_dir"])).expanduser()
            if job.get("state_dir")
            else dharma_state_dir()
        )
        monitor = IdentityMonitor(state_dir=state_dir)
        state = asyncio.run(
            monitor.measure(threat_boost=_as_bool(job.get("threat_boost"), False))
        )
        raw_history_path = str(job.get("history_path") or "").strip()
        history_path = Path(raw_history_path).expanduser() if raw_history_path else None
        monitor.save_history(history_path)
        written_path = history_path or (state_dir / "meta" / "identity_history.jsonl")
        output = (
            "TCS heartbeat: "
            f"tcs={state.tcs:.4f} regime={state.regime} "
            f"gpr={state.gpr:.4f} bsi={state.bsi:.4f} rm={state.rm:.4f} "
            f"history={written_path}"
        )
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=output,
            metadata={
                "tcs": state.tcs,
                "gpr": state.gpr,
                "bsi": state.bsi,
                "rm": state.rm,
                "regime": state.regime,
                "history_path": str(written_path),
            },
        )
    except Exception as exc:
        error = f"TCS heartbeat failed: {exc}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )


def _run_overnight_director(job: dict[str, Any]) -> CronJobExecutionResult:
    """Launch the overnight director as a long-running process."""
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        from dharma_swarm.overnight_director import run_overnight

        hours = float(job.get("hours", 8.0))
        autonomy = int(job.get("autonomy", 1))
        max_tokens = int(job.get("max_tokens", 500_000))
        external_wait_handoff = _as_bool(job.get("external_wait_handoff"), False)
        raw_resume_state = job.get("_resume_state")
        resume_state = raw_resume_state if isinstance(raw_resume_state, dict) else {}
        resume_metadata = resume_state.get("metadata", {}) if isinstance(resume_state.get("metadata", {}), dict) else {}
        run_date = str(resume_metadata.get("overnight_run_date", "")).strip() or None
        result = asyncio.run(run_overnight(
            hours=hours,
            autonomy_level=autonomy,
            max_tokens=max_tokens,
            external_wait_handoff=external_wait_handoff,
            run_date=run_date,
            resume_temporal_run=run_date is not None,
        ))
        summary = json.dumps(result, indent=2, default=str)[:5000]
        header = f"# Cron Job: {job.get('name', 'Overnight Director')}\n\n"
        if result.get("status") == "waiting":
            wake_at = None
            raw_wake_at = result.get("wake_at")
            if raw_wake_at:
                try:
                    wake_at = datetime.fromisoformat(str(raw_wake_at))
                except ValueError:
                    wake_at = None
            return CronJobExecutionResult(
                status=CronJobRunStatus.WAITING_EXTERNAL,
                output=header + summary,
                next_action=str(result.get("next_action", "")),
                wake_at=wake_at,
                metadata={
                    "overnight_run_date": str(result.get("date", run_date or "")),
                    "resume_task_id": str(result.get("resume_task_id", "")),
                    "wait_id": str(result.get("wait_id", "")),
                },
            )
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=header + summary,
        )
    except Exception as exc:
        error = f"Overnight director failed: {exc}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error[:500],
        )


def _headless_failure_supports_local_fallback(result: str) -> bool:
    lowered = result.lower()
    return any(marker in lowered for marker in _LOCAL_FALLBACK_ERROR_MARKERS)


def _one_line(text: str, *, limit: int = 180) -> str:
    collapsed = " ".join(part.strip() for part in text.splitlines() if part.strip())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _assurance_critical_summary() -> str:
    scans_dir = Path.home() / ".dharma" / "assurance" / "scans"
    if not scans_dir.exists():
        return "Assurance: no scan summaries found."

    critical_total = 0
    scanned = 0
    for path in sorted(scans_dir.glob("*latest.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        scanned += 1
        summary = payload.get("summary")
        if isinstance(summary, dict):
            try:
                critical_total += int(summary.get("critical", 0) or 0)
            except (TypeError, ValueError):
                pass
            continue
        findings = payload.get("findings")
        if isinstance(findings, list):
            critical_total += sum(
                1
                for finding in findings
                if isinstance(finding, dict)
                and str(finding.get("severity", "")).lower() == "critical"
            )

    if scanned == 0:
        return "Assurance: no readable latest scan summaries."

    noun = "finding" if critical_total == 1 else "findings"
    scan_noun = "scan" if scanned == 1 else "scans"
    return f"Assurance: {critical_total} CRITICAL {noun} across {scanned} latest {scan_noun}."


def _local_pulse_fallback(remote_error: str) -> str:
    agni_state = read_agni_state()
    if agni_state.get("priorities_stale"):
        age = agni_state.get("priorities_age_hours", "?")
        agni_summary = f"priorities stale ({age}h)"
    elif agni_state:
        agni_summary = "state files present"
    else:
        agni_summary = "state unavailable"

    return "\n".join(
        [
            "Mode: local (fallback)",
            f"Claude unavailable: {remote_error}",
            f"AGNI: {agni_summary}",
            f"Trishula: {_one_line(read_trishula_inbox())}",
            _assurance_critical_summary(),
            f"Memory: {_one_line(read_memory_context(limit=3))}",
            f"Ecosystem: {_one_line(read_manifest())}",
            "Witness: heartbeat preserved locally while the Claude lane is unavailable.",
        ]
    )


def _build_local_fallback(job: dict[str, Any], remote_error: str) -> str | None:
    mode = str(job.get("fallback_mode", "")).strip().lower()
    if mode == "local_pulse":
        return _local_pulse_fallback(remote_error)
    return None


def _result_from_legacy(
    success: bool,
    output: str,
    error: str | None,
) -> CronJobExecutionResult:
    return CronJobExecutionResult(
        status=CronJobRunStatus.COMPLETED if success else CronJobRunStatus.FAILED,
        output=output,
        error=error or "",
    )


def _portable_model_overrides(
    provider_order: tuple[ProviderType, ...],
    requested_model: str | None,
) -> tuple[str | None, str | None]:
    if not requested_model:
        return None, None
    lowered = requested_model.strip().lower()
    if lowered in {"flash", "haiku", "sonnet", "opus"}:
        return None, None

    openrouter_model = (
        requested_model
        if any(
            provider in provider_order
            for provider in (ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE)
        )
        else None
    )
    anthropic_model = (
        requested_model if ProviderType.ANTHROPIC in provider_order else None
    )
    return openrouter_model, anthropic_model


def _format_hosted_completion_output(
    job: dict[str, Any],
    *,
    surface: str,
    provider: str,
    model: str,
    content: str,
) -> str:
    header = f"# Cron Job: {job.get('name', job.get('id', 'unnamed'))}\n\n"
    route = f"Route: surface={surface} provider={provider} model={model}"
    return header + route + "\n\n" + content


def _run_hosted_portable_prompt(
    job: dict[str, Any],
    profile: JobCapabilityProfile,
    *,
    surface_label: str,
) -> tuple[bool, str, str | None]:
    prompt = build_portable_job_prompt(job)
    if not prompt:
        error = "Cron job prompt is empty"
        return False, error, error

    requested_model = str(job.get("model", "")).strip() or None
    openrouter_model, anthropic_model = _portable_model_overrides(
        profile.provider_order,
        requested_model,
    )
    timeout_seconds = _as_float(job.get("timeout_sec"), 600.0)

    try:
        response, config = asyncio.run(
            complete_via_preferred_runtime_providers(
                messages=[{"role": "user", "content": prompt}],
                system=str(job.get("system", "")).strip(),
                openrouter_model=openrouter_model,
                anthropic_model=anthropic_model,
                max_tokens=_as_int(job.get("max_tokens"), 4096),
                temperature=_as_float(job.get("temperature"), 0.7),
                provider_order=profile.provider_order,
                working_dir=str(job.get("working_dir", "")).strip() or None,
                timeout_seconds=timeout_seconds,
            )
        )
    except Exception as exc:
        error = str(exc) or "Portable hosted execution failed"
        header = f"# Cron Job: {job.get('name', job.get('id', 'unnamed'))}\n\n"
        return False, header + error, error[:500]

    provider = response.provider or config.provider.value
    model = response.model or config.default_model or requested_model or "unknown"
    try:
        artifact_path = persist_portable_job_output(job, response.content)
    except Exception as exc:
        error = f"Portable artifact persistence failed: {exc}"
        header = f"# Cron Job: {job.get('name', job.get('id', 'unnamed'))}\n\n"
        return False, header + error, error[:500]
    output = _format_hosted_completion_output(
        job,
        surface=surface_label,
        provider=provider,
        model=model,
        content=response.content,
    )
    if artifact_path is not None:
        output = output + f"\n\nArtifact: wrote {artifact_path}"
    return True, output, None


def _run_headless_prompt(job: dict[str, Any]) -> tuple[bool, str, str | None]:
    from dharma_swarm.pulse import run_claude_headless

    profile = resolve_job_capability_profile(job)
    prompt = str(job.get("prompt", "")).strip()
    if not prompt:
        error = "Cron job prompt is empty"
        return False, error, error

    # Legacy headless prompts often assume local file reads or shell actions,
    # so hosted portability stays explicit rather than automatic.
    if profile.prefers_hosted_api:
        return _run_hosted_portable_prompt(
            job,
            profile,
            surface_label=JobExecutionSurface.HOSTED_API.value,
        )

    result = run_claude_headless(
        prompt=prompt,
        timeout=_as_int(job.get("timeout_sec"), 600),
        model=str(job.get("model", "")).strip() or None,
    )
    success = not result.startswith(("ERROR:", "TIMEOUT:", "Error (rc="))
    header = f"# Cron Job: {job.get('name', job.get('id', 'unnamed'))}\n\n"
    if (
        not success
        and profile.allows_hosted_fallback
        and _headless_failure_supports_local_fallback(result)
    ):
        hosted_success, hosted_output, hosted_error = _run_hosted_portable_prompt(
            job,
            profile,
            surface_label="hosted_api_fallback",
        )
        if hosted_success:
            return True, hosted_output, None
        if hosted_error:
            result = f"{result}\nHosted fallback failed: {hosted_error}"
    if not success and _headless_failure_supports_local_fallback(result):
        fallback_output = _build_local_fallback(job, result)
        if fallback_output is not None:
            return True, header + fallback_output, None
    return success, header + result, None if success else result[:500]

def _run_scout_sweep(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run all domain scouts sequentially."""
    import asyncio

    try:
        from dharma_swarm.scout_framework import run_all_scouts
        model = str(job.get("scout_model", "")).strip() or None
        reports = asyncio.run(run_all_scouts(model_override=model))
        from dharma_swarm.scout_report import report_summary
        lines = [report_summary(r) for r in reports]
        output = f"Scout sweep: {len(reports)} domains\n" + "\n".join(lines)
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=output,
        )
    except Exception as e:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_scout_synthesis(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run synthesis agent on latest scout reports."""
    import asyncio

    try:
        from dharma_swarm.synthesis_agent import run_synthesis
        path = asyncio.run(run_synthesis())
        if path:
            output = f"Synthesis written: {path}"
            return CronJobExecutionResult(
                status=CronJobRunStatus.COMPLETED,
                output=output,
            )
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output="No scout reports found",
            error="No scout reports found",
        )
    except Exception as e:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_shakti_executive(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run the Layer C executive that refreshes the opportunity board."""

    try:
        from dharma_swarm.shakti_executive import ShaktiExecutive

        top_k = int(job.get("top_k", 12))
        min_score = float(job.get("min_score", 45.0))
        write = _as_bool(job.get("write"), False) and not _as_bool(job.get("dry_run"), False)
        state_dir = job.get("state_dir") or None
        res = ShaktiExecutive(state_dir=state_dir).run(
            write=write,
            top_k=top_k,
            min_score=min_score,
        )
        if res.errors:
            return CronJobExecutionResult(
                status=CronJobRunStatus.FAILED,
                output=f"shakti_executive errors: {list(res.errors)}",
                error="; ".join(res.errors)[:500],
            )
        output = (
            f"shakti_executive: dry_run={res.dry_run} scanned={res.scanned_signals} "
            f"selected={res.selected_candidates} board_before={res.board_count_before} "
            f"board_after={res.board_count_after}"
        )
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=output,
        )
    except Exception as e:  # noqa: BLE001
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_frontier_dispatcher(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run a single dispatcher tick from opportunity board into task board."""

    try:
        from dharma_swarm.opportunity_dispatcher import main as dispatcher_main

        argv: list[str] = []
        if job.get("dry_run"):
            argv.append("--dry-run")
        max_promotions = job.get("max_promotions")
        if max_promotions is not None:
            argv.extend(["--max", str(int(max_promotions))])
        rc = dispatcher_main(argv)
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED if rc == 0 else CronJobRunStatus.FAILED,
            output=f"opportunity_dispatcher exit_code={rc}",
        )
    except Exception as e:  # noqa: BLE001
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_frontier_refill(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run a single refill cycle for top pending opportunities."""

    try:
        from dharma_swarm.opportunity_refill import refill_frontier_tasks_pending

        top_k = int(job.get("top_k", 3))
        min_telos = float(job.get("min_telos_alignment", 0.5))
        dry_run = _as_bool(job.get("dry_run"), False)
        res = refill_frontier_tasks_pending(
            top_k=top_k,
            min_telos_alignment=min_telos,
            dry_run=dry_run,
        )
        if res.error:
            return CronJobExecutionResult(
                status=CronJobRunStatus.FAILED,
                output=f"frontier_refill error: {res.error}",
                error=res.error,
            )
        output = (
            f"frontier_refill: paused={res.paused} board={res.board_count} "
            f"addressed={res.addressed_count} appended_rows={res.appended_rows} "
            f"appended_ids={res.appended_opportunity_ids}"
        )
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=output,
        )
    except Exception as e:  # noqa: BLE001
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_store_sync(job: dict[str, Any]) -> CronJobExecutionResult:
    """BR-007: sync ontology.db outcomes → runtime.db artifact_records."""
    try:
        from dharma_swarm.engine.store_sync import sync_all
        res = sync_all()
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=(
                f"store_sync: scanned={res.outcomes_scanned} "
                f"created={res.artifacts_created} "
                f"skipped={res.skipped_existing} "
                f"errors={res.errors}"
            ),
        )
    except Exception as e:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_world_scout(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run the external world radar and canonicalize promoted signals."""

    fetch_enabled = _as_bool(job.get("fetch"), False) or _as_bool(
        os.environ.get("DHARMA_WORLD_SCOUT_FETCH"),
        False,
    )
    if not fetch_enabled:
        return CronJobExecutionResult(
            status=CronJobRunStatus.WAITING_EXTERNAL,
            output=(
                "world_scout fetch disabled; set job.fetch=true or "
                "DHARMA_WORLD_SCOUT_FETCH=1 to scan live public sources"
            ),
            metadata={"fetch_enabled": False},
        )

    try:
        from dharma_swarm.world_radar.go_bridge import run_world_radar_go_once
        from dharma_swarm.zeitgeist import ZeitgeistScanner

        state_dir = job.get("state_dir") or None
        result = run_world_radar_go_once(
            state_dir=state_dir,
            scout_fetch=True,
            min_score=_as_float(job.get("min_score"), 0.45),
            timeout_s=_as_int(job.get("timeout_sec"), 60),
        )
        canonical_signals = asyncio.run(
            ZeitgeistScanner(
                state_dir=Path(str(state_dir)).expanduser() if state_dir else None
            ).scan()
        )
        # Read-only follow-on: turn promotion-ready zeitgeist signals into
        # MemoryKernel promotion PROPOSALS (READY_FOR_REVIEW, human-gated).
        # Never mutates memory; defensively wrapped so it can't break the scout.
        promotion_summary: dict[str, Any] = {}
        try:
            from dharma_swarm.knowledge_ops.zeitgeist_promotion import (
                run_zeitgeist_promotion,
            )

            promotion_state = (
                Path(str(state_dir)).expanduser()
                if state_dir
                else dharma_state_dir()
            )
            promotion_summary = run_zeitgeist_promotion(promotion_state)
        except Exception as promo_exc:  # noqa: BLE001
            promotion_summary = {"error": str(promo_exc)[:200]}
        promotion_error = str(promotion_summary.get("error", ""))
        output = (
            "world_scout: "
            f"raw={result.raw_observations} signals={result.emitted_signals} "
            f"promotion_ready={result.promotion_ready} "
            f"incubations={result.incubations_written} "
            f"zeitgeist={len(canonical_signals)} "
            f"promotion_proposals={promotion_summary.get('proposal_count', 0)} "
            f"brief={result.brief_path} health={result.health_path}"
        )
        # Surface a promotion-hook failure so it is not reported identically to a
        # clean run with zero proposals (the follow-on is non-fatal to the scout,
        # but a silent write/import failure must be visible to the operator).
        if promotion_error:
            output = f"{output} promotion_error={promotion_error}"
        if result.errors:
            output = f"{output} errors={list(result.errors)}"
        combined_error = "; ".join(result.errors)[:500] if result.errors else ""
        if promotion_error and not combined_error:
            combined_error = f"promotion_hook: {promotion_error}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED if result.ok else CronJobRunStatus.FAILED,
            output=output,
            error=combined_error,
            metadata={
                "fetch_enabled": True,
                "raw_observations": result.raw_observations,
                "emitted_signals": result.emitted_signals,
                "promotion_ready": result.promotion_ready,
                "incubations_written": result.incubations_written,
                "canonical_zeitgeist_signals": len(canonical_signals),
                "promotion_proposals": promotion_summary.get("proposal_count", 0),
                "promotion_error": promotion_error,
                "promotion_review_md": promotion_summary.get("review_md", ""),
                "board_path": result.board_path,
                "brief_path": result.brief_path,
                "health_path": result.health_path,
            },
        )
    except Exception as e:  # noqa: BLE001
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def _run_operator_brief(job: dict[str, Any]) -> CronJobExecutionResult:
    """Cron handler for the ontology-native Operator Brief seam (v0).

    Default-disabled via ``DHARMA_OPERATOR_BRIEF_ENABLED``. When the
    flag is off, the handler reports ``WAITING_EXTERNAL`` (meaning:
    "ran but did nothing, awaiting flag flip") and performs no source
    mutation. See ``docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md``.
    """
    try:
        from dharma_swarm.operator_brief.insight_brief import cron_run
        result = cron_run(job)
        status = result.get("status", "unknown")
        outcome = result.get("outcome", "")
        if status == "disabled":
            return CronJobExecutionResult(
                status=CronJobRunStatus.WAITING_EXTERNAL,
                output=f"operator_brief disabled: {result.get('reason', '')}",
                metadata=result,
            )
        if outcome == "success":
            return CronJobExecutionResult(
                status=CronJobRunStatus.COMPLETED,
                output=(
                    f"operator_brief artifact={result.get('artifact_id')} "
                    f"witnesses={len(result.get('witness_log_ids', []))}"
                ),
                metadata=result,
            )
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=f"operator_brief outcome={outcome}",
            error=outcome,
            metadata=result,
        )
    except Exception as e:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


def execute_cron_job(job: dict[str, Any]) -> CronJobExecutionResult:
    """Dispatch a cron job to the configured runner with structured status.

    Supported handlers:
        headless_prompt  — default, runs prompt via Claude headless
        doctor_assurance — recurring DGC Doctor sweep with persisted reports
        review_cycle     — 6-hour review cycle
        foreman          — foreman quality forge cycle
        custodians       — custodian maintenance fleet (no quality re-scan)
        custodians_forge — custodian fleet + foreman quality re-scan
        shakti_executive — Layer C opportunity board refresh
        frontier_dispatcher — promote opportunity rows into tasks
        frontier_refill — bootstrap top opportunities into frontier queue
        system_map_populator — local system map refresh
        tcs_heartbeat   — local IdentityMonitor time-series sample
        world_scout     — external zeitgeist radar and scout cascade
        store_sync      — materialize ontology outcomes into runtime artifacts
        provider_starvation_alert — emit algedonic signal for provider-chain starvation
        algedonic_triage — drain pain-signal cursor and write P0 alert summary
        memory_common_metabolism — ingest promoted memory and gate retrieval
    """
    handler = str(job.get("handler", "headless_prompt")).strip() or "headless_prompt"

    if handler == "headless_prompt":
        return _result_from_legacy(*_run_headless_prompt(job))
    if handler == "overnight_director":
        return _run_overnight_director(job)
    if handler == "doctor_assurance":
        from dharma_swarm.doctor import doctor_run_fn
        return _result_from_legacy(*doctor_run_fn(job))
    if handler == "review_cycle":
        from dharma_swarm.review_cycle import review_run_fn
        return _result_from_legacy(*review_run_fn(job))
    if handler == "foreman":
        from dharma_swarm.foreman import foreman_run_fn
        return _result_from_legacy(*foreman_run_fn(job))
    if handler == "custodians":
        from dharma_swarm.custodians import custodians_run_fn
        return _result_from_legacy(*custodians_run_fn(job))
    if handler == "custodians_forge":
        from dharma_swarm.foreman import custodians_forge_fn
        return _result_from_legacy(*custodians_forge_fn(job))

    if handler == "scout_sweep":
        return _run_scout_sweep(job)
    if handler == "scout_synthesis":
        return _run_scout_synthesis(job)
    if handler == "shakti_executive":
        return _run_shakti_executive(job)
    if handler == "frontier_dispatcher":
        return _run_frontier_dispatcher(job)
    if handler == "frontier_refill":
        return _run_frontier_refill(job)
    if handler == "operator_brief":
        return _run_operator_brief(job)
    if handler == "system_map_populator":
        return _run_system_map_populator(job)
    if handler == "tcs_heartbeat":
        return _run_tcs_heartbeat(job)
    if handler == "revenue_scout":
        return _run_revenue_scout(job)
    if handler == "world_scout":
        return _run_world_scout(job)
    if handler == "signal_deep_sweep":
        from dharma_swarm.cron_signal_deep_sweep import run_signal_deep_sweep_job

        return run_signal_deep_sweep_job(job)
    if handler == "store_sync":
        return _run_store_sync(job)
    if handler == "provider_starvation_alert":
        return run_provider_starvation_alert(job)
    if handler == "algedonic_triage":
        return run_algedonic_triage(job)
    if handler == "memory_common_metabolism":
        from dharma_swarm.memory_common import memory_common_cron_run_fn

        return _result_from_legacy(*memory_common_cron_run_fn(job))
    if handler == "shell":
        return _run_shell_command(job)

    error = f"Unsupported cron handler: {handler}"
    return CronJobExecutionResult(
        status=CronJobRunStatus.FAILED,
        output=error,
        error=error,
    )


def run_cron_job(job: dict[str, Any]) -> tuple[bool, str, str | None]:
    """Dispatch a cron job to the configured runner."""

    result = execute_cron_job(job)
    success = result.status in {
        CronJobRunStatus.COMPLETED,
        CronJobRunStatus.WAITING_EXTERNAL,
        CronJobRunStatus.READY_TO_RESUME,
    }
    error = None if success else (result.error or result.output[:500] or "Cron job failed")

    # Report to KaizenOps
    try:
        from dharma_swarm.kaizen_ops_local import KaizenOpsLocal
        ops = KaizenOpsLocal()
        ops.ingest_cron_result(
            job_id=str(job.get("id", "unknown")),
            status=result.status.value,
            job_name=str(job.get("name", "")),
            error=result.error or "",
        )
        ops.close()
    except Exception:
        pass  # KaizenOps is non-blocking

    return success, result.output, error
