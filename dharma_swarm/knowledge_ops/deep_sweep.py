"""Deep sweep — the automated, capped version of the manual wide-research run.

Runs on a SEPARATE, lower-frequency cadence from the hourly world_scout job
(daily, by cron config -- see cron_jobs.json's signal_deep_sweep entry, which
defaults to enabled=false: spending real LLM budget automatically is a bigger
decision than free API scraping and should be turned on deliberately, not
silently). Orchestrates:

  1. the Go scout across the capped DefaultBeats() set (tools/world_scout_go
     --fetch --beats)
  2. movement clustering (reuses world_radar.analysis.build_world_signal_board
     -- no new clustering logic)
  3. rolling-window persistence (world_radar.theme_window) so "what's new
     this cycle" is cheap to answer instead of re-verifying everything daily
  4. a CAPPED verification pass (max_verifications, default small) on the
     newest/highest-scoring themes, dispatched through invoke_agent() -- the
     spine's one blessed invocation path -- never an ad-hoc parallel dispatch
  5. one synthesis call producing a short digest

Governance floor held: this module writes ONLY under the runtime state dir
(meta/world_radar/deep_sweep/), never MemoryKernel, canon, or a
proposed_tracks draft. Per CLAUDE.md, loop-generated runtime artifacts never
enter git -- this is exactly that kind of artifact, unlike the one-off manual
research digest this module's design was demonstrated by
(reports/research/2026-07-01_signal_synthesis_live_run/), which was a
reviewable, committed record of a single hand-run exercise, not a recurring
job's output.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.claude_cli import run_claude_headless
from dharma_swarm.spine.invoke import invoke_agent
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision
from dharma_swarm.world_radar.analysis import build_world_signal_board
from dharma_swarm.world_radar.theme_window import (
    load_theme_window,
    save_theme_window,
    update_theme_window,
)

DEFAULT_MAX_VERIFICATIONS = 8
SUCCESS_RECEIPT_STATUSES = {"ok", "completed", "success"}

ScoutResult = tuple[list[dict[str, Any]], str | None, dict[str, int | str | bool]]
IngestResult = tuple[list[dict[str, Any]], str | None]
ScoutFn = Callable[..., ScoutResult]
IngestFn = Callable[..., IngestResult]
DispatchFn = Callable[..., Awaitable[EvidenceReceipt]]


def _default_go_scout(**kwargs: Any) -> ScoutResult:
    from dharma_swarm.world_radar.go_bridge import _run_go_scout

    return _run_go_scout(**kwargs)


def _default_go_ingestor(**kwargs: Any) -> IngestResult:
    from dharma_swarm.world_radar.go_bridge import _run_go_ingestor

    return _run_go_ingestor(**kwargs)


def _receipt_succeeded(receipt: EvidenceReceipt) -> bool:
    return str(receipt.status).lower() in SUCCESS_RECEIPT_STATUSES


def _receipt_output(receipt: EvidenceReceipt) -> str:
    return str(receipt.attributes.get("output_text") or "")


_VALID_VERIFICATION_VERDICTS = ("confirmed_real", "unverifiable", "likely_fabricated")


def _has_valid_verification_verdict(output_text: str) -> bool:
    lowered = output_text.lower()
    return any(verdict in lowered for verdict in _VALID_VERIFICATION_VERDICTS)


def _receipt_failure_detail(receipt: EvidenceReceipt) -> str:
    detail = str(receipt.error_detail or "").strip()
    return detail or _receipt_output(receipt) or f"receipt status={receipt.status}"


def _claude_output_failure(output: str) -> tuple[str, str, str | None]:
    stripped = output.lstrip()
    lowered = stripped.lower()
    if lowered.startswith("timeout:"):
        return "timeout", "timeout", output
    if lowered.startswith(("error:", "error (", "error(")):
        return "failed", "provider_failed", output
    return "ok", "none", None


def _new_context_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"signal-deep-sweep-{stamp}-{uuid.uuid4().hex[:8]}"


def _movement_id(movement: dict[str, Any]) -> str:
    return str(movement.get("movement_id") or "")


def _weighted_score(movement: dict[str, Any]) -> float:
    try:
        return float(movement.get("weighted_score", 0.0) or 0.0)
    except (TypeError, ValueError, OverflowError):
        return 0.0


async def _headless_invoker(
    *,
    task: dict[str, Any],
    agent_id: str,
    context_id: str,
    routing: RoutingDecision,
) -> EvidenceReceipt:
    """AgentInvoker backed by run_claude_headless (the keyless claude_code
    lane). Never raises -- every outcome (success, error, timeout) becomes a
    real EvidenceReceipt, per the spine's one-blessed-path contract. The
    result text is stashed in attributes["output_text"]: EvidenceReceipt's
    own fields are dispatch-provenance shaped, not a general return-value
    carrier, and attributes is exactly where orchestrator.py's own invoker
    closure puts call-site-specific detail.
    """
    prompt = str(task.get("prompt") or "")
    timeout = int(task.get("timeout", 300))
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    # run_claude_headless's own default is bare=True, which fast-fails unless
    # ANTHROPIC_API_KEY is set -- that's the opposite of the keyless
    # claude_code/subscription lane this module is documented to use. Request
    # bare=False explicitly so a Max/Pro subscription setup without an API
    # key can actually dispatch (Codex review finding, deep_sweep.py:117).
    output = run_claude_headless(prompt, timeout=timeout, bare=False)
    latency_ms = int((time.monotonic() - t0) * 1000)
    finished = datetime.now(timezone.utc)

    status, error_source, error_detail = _claude_output_failure(output)

    return EvidenceReceipt(
        # trace_id is the cross-layer correlation identity (aliased
        # dharma.correlation_id in to_otel_span) shared by every receipt in
        # this cycle; task_id below already carries the per-task identity, so
        # trace_id must be the cycle's context_id, not the per-task id, or
        # receipts from one deep-sweep cycle can't be joined in telemetry
        # (Copilot review finding, deep_sweep.py:92).
        trace_id=context_id,
        context_id=context_id,
        task_id=str(task.get("id", "")),
        agent_id=agent_id,
        provider="claude_code",
        model=routing.model or "",
        operation="invoke_agent",
        provider_attempted=True,
        status=status,  # type: ignore[arg-type]
        error_source=error_source,  # type: ignore[arg-type]
        error_detail=error_detail,
        started_at=started,
        finished_at=finished,
        latency_ms=latency_ms,
        routing_decision_id=routing.decision_id,
        attributes={"router": "signal_deep_sweep", "output_text": output[:4000]},
    )


async def _dispatch(
    prompt: str,
    *,
    context_id: str,
    task_id: str,
    reason: str,
    timeout: int = 300,
) -> EvidenceReceipt:
    """The one call site every deep-sweep LLM interaction routes through --
    invoke_agent(), never a bespoke dispatch path."""
    routing = RoutingDecision(
        agent_id="signal_deep_sweep",
        provider="claude_code",
        model="",
        reason=reason,
        router_name="signal_deep_sweep",
        context_id=context_id,
        task_id=task_id,
    )
    task: dict[str, Any] = {"id": task_id, "prompt": prompt, "timeout": timeout}
    return await invoke_agent(
        task,
        agent_id="signal_deep_sweep",
        context_id=context_id,
        routing=routing,
        invoker=_headless_invoker,
    )


def _verification_prompt(title: str, summary: str, url: str = "") -> str:
    # Movements from build_world_signal_board carry a concrete primary_url
    # (arxiv/GitHub/Reddit/HN); omitting it left the verifier guessing at an
    # artifact from title/summary text alone even when the exact URL to fetch
    # was already known (Codex review finding, deep_sweep.py:285).
    url_line = f'URL: "{url}". ' if url else ""
    return (
        "Verify this claim as rigorously as you can using web search/fetch if available. "
        f'Title: "{title}". Summary: "{summary}". {url_line}'
        "Attempt to directly verify a claimed concrete artifact (URL, repo, paper ID) rather than "
        "just re-reading search snippets. Report exactly one of: confirmed_real / unverifiable / "
        "likely_fabricated, with 2-3 sentences of evidence."
    )


def _synthesis_prompt(movements: list[dict[str, Any]], verifications: list[dict[str, Any]]) -> str:
    return (
        "Produce a short markdown digest (a few paragraphs, not exhaustive) of this research-sweep "
        f"cycle. {len(movements)} clustered signals were found this cycle, {len(verifications)} were "
        "verified.\n\n"
        f"MOVEMENTS (JSON, truncated to 50): {json.dumps(movements[:50], default=str)}\n\n"
        f"VERIFICATIONS (JSON): {json.dumps(verifications, default=str)}\n\n"
        "Summarize what's notable, flag anything verification found likely_fabricated by name, and "
        "note any recurring themes (movements with a high occurrence_count in the rolling window are "
        "recurring across cycles, not new)."
    )


async def run_deep_sweep(
    state_dir: Path,
    *,
    max_verifications: int = DEFAULT_MAX_VERIFICATIONS,
    scout_timeout_s: int = 300,
    verification_timeout_s: int = 300,
    synthesis_timeout_s: int = 300,
    scout_fn: ScoutFn = _default_go_scout,
    ingest_fn: IngestFn = _default_go_ingestor,
    dispatch_fn: DispatchFn = _dispatch,
) -> dict[str, Any]:
    """The capped, automated deep sweep.

    scout_fn/dispatch_fn are injectable purely for testing -- production
    callers should never override them; the defaults are the real Go scout
    and the real invoke_agent-backed dispatcher.
    """
    state = state_dir.expanduser().resolve()
    meta = state / "meta"
    radar = meta / "world_radar"
    out_dir = radar / "deep_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)
    context_id = _new_context_id()

    scout_rows, scout_error, scout_counts = scout_fn(
        state=state,
        output_path=radar / "deep_sweep_observations.jsonl",
        health_path=radar / "deep_sweep_health.json",
        timeout_s=scout_timeout_s,
        beats=True,
    )

    signal_path = radar / "deep_sweep_signals.jsonl"
    ingest_error: str | None = None
    ingested_rows: list[dict[str, Any]] = []
    if scout_rows:
        raw_path = radar / "deep_sweep_raw_observations.jsonl"
        _write_jsonl(raw_path, scout_rows)
        ingested_rows, ingest_error = ingest_fn(
            input_path=raw_path,
            output_path=signal_path,
            min_score=0.0,
            timeout_s=scout_timeout_s,
            receipt_dir=radar / "deep_sweep_receipts",
            correlation_id=context_id,
        )

    # Only fall back to raw scout rows when ingestion actually FAILED
    # (ingest_error set), not merely because a successful ingest legitimately
    # accepted zero rows -- `ingested_rows or scout_rows` would resurrect
    # rejected/unscored raw observations as verification candidates even when
    # the ingestor correctly rejected all of them (Codex review finding,
    # deep_sweep.py:248).
    board_rows = ingested_rows if (ingested_rows or ingest_error is None) else scout_rows
    board = build_world_signal_board(board_rows) if board_rows else {"movements": []}
    movements = [m for m in board.get("movements", []) if isinstance(m, dict)]

    # Fold THIS cycle's own beat-derived movements into the rolling window --
    # not meta/world_signal_board.json (that's the separate, hourly
    # world_scout job's file; reading it here would silently track the wrong
    # job's movements, or nothing at all if world_scout hasn't run recently).
    window_path = radar / "theme_window.json"
    window = load_theme_window(window_path)
    _, newly_seen = update_theme_window(window, movements)
    newly_seen_ids = set(newly_seen)

    candidates = [m for m in movements if _movement_id(m) in newly_seen_ids]
    candidates.sort(key=_weighted_score, reverse=True)
    capped = candidates[: max(0, max_verifications)]

    verifications: list[dict[str, Any]] = []
    verification_error: str | None = None
    failed_receipts = 0
    # Only a movement whose verification actually SUCCEEDED is persisted into
    # the window as "seen" this cycle; a capped movement that times out or
    # gets a failed receipt must remain newly_seen so a rerun retries it,
    # instead of looking "already seen" and never getting another attempt
    # (Codex review finding, deep_sweep.py:266).
    succeeded_ids: set[str] = set()
    for movement in capped:
        title = str(movement.get("title") or "")
        summary = str(movement.get("summary") or "")
        url = str(movement.get("primary_url") or "")
        try:
            receipt = await dispatch_fn(
                _verification_prompt(title, summary, url),
                context_id=context_id,
                task_id=str(movement.get("movement_id", "")),
                reason="deep_sweep verification",
                timeout=verification_timeout_s,
            )
            verifications.append(
                {
                    "movement_id": movement.get("movement_id"),
                    "title": title,
                    "status": receipt.status,
                    "output": receipt.attributes.get("output_text", ""),
                    "receipt_id": str(receipt.receipt_id),
                }
            )
            # A dispatch-level success (status="ok") is not the same as a
            # USABLE verification: malformed/empty model output that never
            # names one of the three required verdicts must not permanently
            # suppress the claim by marking it "seen" (Codex review finding,
            # deep_sweep.py:301).
            if _receipt_succeeded(receipt) and _has_valid_verification_verdict(
                _receipt_output(receipt)
            ):
                succeeded_ids.add(_movement_id(movement))
            else:
                failed_receipts += 1
        except Exception as exc:  # noqa: BLE001 -- one bad verification must not sink the cycle
            verification_error = str(exc)[:200]
            failed_receipts += 1
            verifications.append(
                {
                    "movement_id": movement.get("movement_id"),
                    "title": title,
                    "status": "failed",
                    "output": "",
                    "error": verification_error,
                }
            )
    if failed_receipts and verification_error is None:
        verification_error = f"{failed_receipts} verification receipt(s) failed or timed out"

    persist_movements = [
        m for m in movements if _movement_id(m) not in newly_seen_ids or _movement_id(m) in succeeded_ids
    ]
    updated_window, _ = update_theme_window(window, persist_movements)
    save_theme_window(window_path, updated_window)

    # The synthesis prompt asks the model to flag high-occurrence recurring
    # themes, but build_world_signal_board's movements never carry
    # occurrence_count -- that field only lives in the theme window. Merge it
    # in so the prompt can actually reference what it's told to (Codex review
    # finding, deep_sweep.py:316).
    for movement in movements:
        entry = updated_window.get(_movement_id(movement))
        if entry is not None:
            movement["occurrence_count"] = entry.occurrence_count

    digest_text = ""
    synthesis_error: str | None = None
    if movements:
        try:
            synthesis_receipt = await dispatch_fn(
                _synthesis_prompt(movements, verifications),
                context_id=context_id,
                task_id="synthesis",
                reason="deep_sweep synthesis",
                timeout=synthesis_timeout_s,
            )
            if _receipt_succeeded(synthesis_receipt):
                digest_text = _receipt_output(synthesis_receipt)
            else:
                synthesis_error = _receipt_failure_detail(synthesis_receipt)[:200]
        except Exception as exc:  # noqa: BLE001
            synthesis_error = str(exc)[:200]

    cycle_dir = out_dir / context_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    (cycle_dir / "movements.json").write_text(json.dumps(movements, indent=2, default=str), encoding="utf-8")
    (cycle_dir / "verifications.json").write_text(json.dumps(verifications, indent=2), encoding="utf-8")
    (cycle_dir / "digest.md").write_text(digest_text, encoding="utf-8")

    likely_fabricated = [
        v
        for v in verifications
        if "likely_fabricated" in str(v.get("output") or "").lower()
    ]

    return {
        "context_id": context_id,
        "scout_error": scout_error,
        "ingest_error": ingest_error,
        "scout_source_counts": scout_counts,
        "movements_count": len(movements),
        "newly_seen_count": len(newly_seen_ids),
        "verifications_count": len(verifications),
        "verification_backlog_count": max(len(candidates) - len(capped), 0),
        "failed_verification_count": failed_receipts,
        "likely_fabricated_count": len(likely_fabricated),
        "verification_error": verification_error,
        "synthesis_error": synthesis_error,
        "digest_path": str(cycle_dir / "digest.md"),
        "cycle_dir": str(cycle_dir),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


__all__ = [
    "DEFAULT_MAX_VERIFICATIONS",
    "run_deep_sweep",
]
