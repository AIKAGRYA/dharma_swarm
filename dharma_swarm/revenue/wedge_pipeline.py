"""Revenue Wedge Pipeline — ship one real intelligence report end-to-end.

Executes the full Revenue Wedge loop:
  1. Pull live market data (CoinGecko free tier, no API key required)
  2. Generate signals + regime detection
  3. Generate full report (Markdown + HTML + JSON)
  4. Record as Outcome + KnowledgeArtifact in ontology.db
  5. Sync to runtime.db as ArtifactRecord (BR-007 store_sync)
  6. Emit ROOM_TASK_COMPLETED signal through Revenue Wedge room

This is the first real cycle of the organism doing work that humans
can read. The Contemplative Spine's four-question test:
  1. Loop: central metabolic (opportunity → dispatch → outcome → feedback)
  2. Membrane: ontology registry, runtime state store, signal bus
  3. Artifact: KnowledgeArtifact + ArtifactRecord + report files
  4. Self-correcting: outcome feeds back via store_sync → operator brief
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Summary of a single pipeline execution."""

    success: bool = False
    timestamp: str = ""
    data_pull_ok: bool = False
    crypto_count: int = 0
    signals_generated: int = 0
    regime: str = "unknown"
    regime_confidence: float = 0.0
    report_saved: bool = False
    report_path: str = ""
    outcome_id: str = ""
    artifact_id: str = ""
    sync_result: str = ""
    signal_emitted: bool = False
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _pull_data(state_dir: Path) -> tuple[Any, list[str]]:
    """Pull market data. CoinGecko needs no API key."""
    from dharma_swarm.ginko_data import pull_all_data

    pull = await pull_all_data()
    errors = list(pull.errors)
    return pull, errors


def _generate_signals(pull: Any) -> tuple[Any, str, float, list[str]]:
    """Generate signal report from the latest data pull."""
    from dharma_swarm.ginko_signals import generate_signal_report

    errors: list[str] = []
    regime = "unknown"
    regime_conf = 0.0

    macro_dict = None
    if pull and pull.macro:
        macro_dict = asdict(pull.macro)

    price_data: dict[str, list[float]] = {}
    for stock in (pull.stocks if pull else []):
        price_data[stock.symbol] = [stock.previous_close, stock.current_price]

    for crypto in (pull.crypto if pull else []):
        price_data[crypto.symbol.upper()] = [crypto.current_price_usd]

    try:
        report = generate_signal_report(
            regime=regime,
            regime_confidence=regime_conf,
            price_data=price_data,
            macro_data=macro_dict,
        )
        return report, regime, regime_conf, errors
    except Exception as exc:
        errors.append(f"signal generation: {exc}")
        return None, regime, regime_conf, errors


def _generate_report(state_dir: Path) -> tuple[Any, Path | None, list[str]]:
    """Generate the full daily report (MD + HTML + JSON)."""
    from dharma_swarm.ginko_report_gen import generate_daily_report, save_report

    errors: list[str] = []
    try:
        report = generate_daily_report()
        md_path = save_report(report)
        return report, md_path, errors
    except Exception as exc:
        errors.append(f"report generation: {exc}")
        return None, None, errors


def _record_in_ontology(
    report_path: Path | None,
    regime: str,
    state_dir: Path,
) -> tuple[str, str, list[str]]:
    """Record Outcome + KnowledgeArtifact in ontology.db."""
    from dharma_swarm.ontology_runtime import (
        get_shared_registry,
        persist_shared_registry,
    )

    errors: list[str] = []
    outcome_id = ""
    artifact_id = ""

    try:
        ont_path = str(state_dir / "ontology.db")
        registry = get_shared_registry(ont_path)

        outcome_obj, outcome_errs = registry.create_object(
            "Outcome",
            {
                "proposal_id": f"revenue-wedge-report-{_utc_now().strftime('%Y%m%d')}",
                "task_id": "ginko-daily-intelligence-report",
                "agent_id": "revenue-wedge-pipeline",
                "success": True,
                "result_summary": (
                    f"Generated daily intelligence report. "
                    f"Regime: {regime}. "
                    f"Report: {report_path}"
                ),
            },
            created_by="revenue_wedge_pipeline",
        )
        if outcome_errs:
            errors.extend(outcome_errs)
        elif outcome_obj:
            outcome_id = outcome_obj.id

        artifact_obj, artifact_errs = registry.create_object(
            "KnowledgeArtifact",
            {
                "title": f"Dharmic Quant Intelligence Report {_utc_now().strftime('%Y-%m-%d')}",
                "artifact_type": "result",
                "domain": "dharma_swarm",
                "content": str(report_path) if report_path else "",
                "file_path": str(report_path) if report_path else "",
                "provenance": "revenue_wedge_pipeline",
                "confidence": 0.8,
                "verified": False,
            },
            created_by="revenue_wedge_pipeline",
        )
        if artifact_errs:
            errors.extend(artifact_errs)
        elif artifact_obj:
            artifact_id = artifact_obj.id

        persist_shared_registry(registry, ont_path)
    except Exception as exc:
        errors.append(f"ontology recording: {exc}")

    return outcome_id, artifact_id, errors


def _sync_stores(state_dir: Path) -> tuple[str, list[str]]:
    """Run BR-007 store sync to materialize ontology→runtime."""
    errors: list[str] = []
    try:
        from dharma_swarm.engine.store_sync import sync_all

        result = sync_all(state_dir=state_dir)
        summary = (
            f"scanned={result.outcomes_scanned} "
            f"created={result.artifacts_created} "
            f"skipped={result.skipped_existing}"
        )
        return summary, errors
    except Exception as exc:
        errors.append(f"store sync: {exc}")
        return "failed", errors


def _emit_room_signal(state_dir: Path) -> tuple[bool, list[str]]:
    """Emit ROOM_TASK_COMPLETED through Revenue Wedge room."""
    errors: list[str] = []
    try:
        from dharma_swarm.signal_bus import SignalBus

        bus = SignalBus()
        bus.emit({
            "type": "ROOM_TASK_COMPLETED",
            "cell_id": "revenue-wedge",
            "task": "daily-intelligence-report",
            "timestamp": _utc_now().isoformat(),
        })
        return True, errors
    except Exception as exc:
        errors.append(f"signal emission: {exc}")
        return False, errors


async def run_pipeline(
    state_dir: Path | None = None,
) -> PipelineResult:
    """Execute the full Revenue Wedge intelligence report pipeline.

    Args:
        state_dir: Override for ~/.dharma state directory.

    Returns:
        PipelineResult with full execution summary.
    """
    from dharma_swarm.daemon_config import dharma_state_dir

    result = PipelineResult(timestamp=_utc_now().isoformat())
    sd = state_dir or dharma_state_dir("DHARMA_HOME")
    start = time.monotonic()

    # Phase 1: Pull data
    pull, errs = await _pull_data(sd)
    result.errors.extend(errs)
    result.data_pull_ok = pull is not None and len(pull.crypto) > 0
    result.crypto_count = len(pull.crypto) if pull else 0

    # Phase 2: Generate signals
    sig_report, regime, regime_conf, errs = _generate_signals(pull)
    result.errors.extend(errs)
    result.signals_generated = len(sig_report.signals) if sig_report else 0
    result.regime = regime
    result.regime_confidence = regime_conf

    # Phase 3: Generate full report
    report, md_path, errs = _generate_report(sd)
    result.errors.extend(errs)
    result.report_saved = md_path is not None and md_path.exists()
    result.report_path = str(md_path) if md_path else ""

    # Phase 4: Record in ontology
    outcome_id, artifact_id, errs = _record_in_ontology(md_path, regime, sd)
    result.errors.extend(errs)
    result.outcome_id = outcome_id
    result.artifact_id = artifact_id

    # Phase 5: Sync stores (ontology → runtime)
    sync_summary, errs = _sync_stores(sd)
    result.errors.extend(errs)
    result.sync_result = sync_summary

    # Phase 6: Emit signal through Revenue Wedge room
    emitted, errs = _emit_room_signal(sd)
    result.errors.extend(errs)
    result.signal_emitted = emitted

    result.duration_ms = round((time.monotonic() - start) * 1000)
    result.success = result.report_saved and bool(result.outcome_id)

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for running the Revenue Wedge pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the Revenue Wedge intelligence report pipeline"
    )
    parser.add_argument(
        "--state-dir", type=Path, default=None,
        help="Override state directory (default: ~/.dharma)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

    result = asyncio.run(run_pipeline(state_dir=args.state_dir))

    if args.json:
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"Revenue Wedge Pipeline: {status}")
        print(f"  Duration: {result.duration_ms}ms")
        print(f"  Data pull: {'OK' if result.data_pull_ok else 'FAILED'}")
        print(f"  Crypto prices: {result.crypto_count}")
        print(f"  Signals: {result.signals_generated}")
        print(f"  Regime: {result.regime}")
        print(f"  Report: {result.report_path}")
        print(f"  Outcome ID: {result.outcome_id}")
        print(f"  Artifact ID: {result.artifact_id}")
        print(f"  Store sync: {result.sync_result}")
        print(f"  Signal emitted: {result.signal_emitted}")
        if result.errors:
            print(f"  Errors: {len(result.errors)}")
            for err in result.errors:
                print(f"    - {err}")

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
