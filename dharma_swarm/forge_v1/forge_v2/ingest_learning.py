"""Ingest a closed Forge campaign into the Learning Spine (v0 entry point).

Pipeline:  campaign_meta_report.json
             -> signals.report_to_signals
             -> learning_store.append_signals  (append-only, idempotent)
             -> router_bridge.project_signals   (shadow recommendations only)
             -> darwin_bridge.project_signals   (shadow proposals only)
             -> promote.evaluate_signals        (refusal/promotion packets)

Reads CLOSED receipts only; performs no live model calls (so it runs anywhere,
including inside a Claude Code session). Leaves active campaigns and all live
router/Darwin state untouched.

    python -m dharma_swarm.forge_v1.forge_v2.ingest_learning --run-dir <closed_run_dir>
    python -m dharma_swarm.forge_v1.forge_v2.ingest_learning            # latest closed run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .signals import report_to_signals
from .learning_store import LearningStore, DEFAULT_ROOT
from . import router_bridge, darwin_bridge, promote

META_NAME = "campaign_meta_report.json"


def _run_root() -> Path:
    """Mirror scheduler.RUN_ROOT without importing the heavy live-run module."""
    try:
        from dharma_swarm.daemon_config import dharma_state_dir

        return dharma_state_dir() / "forge_v1" / "forge_v2" / "scheduler"
    except Exception:
        return Path("~/.dharma/forge_v1/forge_v2/scheduler").expanduser()


def discover_latest_closed_run(run_root: Path | None = None) -> Path | None:
    """Most-recently-modified scheduler run dir that has a campaign_meta_report.json
    (i.e. is CLOSED). Active runs without that file are skipped."""
    root = run_root or _run_root()
    if not root.exists():
        return None
    closed = [d for d in root.iterdir() if d.is_dir() and (d / META_NAME).exists()]
    if not closed:
        return None
    return max(closed, key=lambda d: (d / META_NAME).stat().st_mtime)


def _enrich_contamination(run_dir: Path) -> str | None:
    """Best-effort authoritative contamination from the run's decision_record.json
    campaigns. Any error -> None (signals.py falls back to its honest derivation)."""
    dr = run_dir / "decision_record.json"
    if not dr.exists():
        return None
    try:
        campaigns = json.loads(dr.read_text(encoding="utf-8")).get("campaigns", []) or []
        states = {str(c.get("contamination_state")) for c in campaigns if c.get("contamination_state")}
        if "possible_pretrain" in states:
            return "possible_pretrain"
        if len(states) == 1:
            return next(iter(states))
    except Exception:
        return None
    return None


def ingest_run(
    run_dir: Path | str,
    *,
    store_root: Path | str | None = None,
    dry_run: bool = False,
    epoch_id: str = "epoch_0",
) -> dict:
    """Ingest one closed run. Returns a full summary dict."""
    run_dir = Path(run_dir).expanduser()
    meta_path = run_dir / META_NAME
    store = LearningStore(root=store_root or DEFAULT_ROOT)
    run_id = run_dir.name

    if not meta_path.exists():
        store.record_malformed(str(meta_path), "campaign_meta_report.json missing")
        return {"ok": False, "error": "meta_report_missing", "run_dir": str(run_dir)}

    raw = meta_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        store.record_malformed(str(meta_path), f"json_decode_error: {exc}")
        return {"ok": False, "error": "meta_report_malformed", "run_dir": str(run_dir)}

    signals = report_to_signals(
        meta,
        source_report_sha256=sha,
        run_id=run_id,
        contamination_state=_enrich_contamination(run_dir),
        epoch_id=epoch_id,
    )

    packets = promote.evaluate_signals(signals)
    refused = sum(1 for p in packets if promote.is_refusal(p))

    summary = {
        "ok": True,
        "run_dir": str(run_dir),
        "run_id": run_id,
        "source_report_sha256": sha,
        "n_signals": len(signals),
        "dry_run": dry_run,
        "promotion": {
            "n_packets": len(packets),
            "n_refused": refused,
            "n_promotable": len(packets) - refused,
            "decisions": [{"arm": p["arm"], "decision": p["decision"]} for p in packets],
        },
    }

    if dry_run:
        summary["note"] = "dry-run: no store/shadow/packet writes"
        return summary

    summary["store"] = store.append_signals(
        signals, source_report_sha256=sha, run_id=run_id
    )
    summary["shadow_router"] = router_bridge.project_signals(signals, store_root=store.root)
    summary["shadow_darwin"] = darwin_bridge.project_signals(signals, store_root=store.root)

    packets_dir = store.root / "promotion_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / f"{run_id}.json").write_text(
        json.dumps(packets, indent=2, sort_keys=True), encoding="utf-8"
    )
    summary["promotion_packets_path"] = str(packets_dir / f"{run_id}.json")
    return summary


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest a closed Forge campaign into the Learning Spine.")
    ap.add_argument("--run-dir", default=None, help="Closed scheduler run dir (default: latest closed).")
    ap.add_argument("--store-root", default=None, help="Learning store root (default: ~/.dharma/forge_v1/learning_signals).")
    ap.add_argument("--epoch-id", default="epoch_0", help="Epoch tag carried on each signal (forward-compat).")
    ap.add_argument("--dry-run", action="store_true", help="Compute + report; write nothing.")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser() if args.run_dir else discover_latest_closed_run()
    if run_dir is None:
        print("no closed run found (no campaign_meta_report.json under RUN_ROOT)", file=sys.stderr)
        return 2

    summary = ingest_run(
        run_dir, store_root=args.store_root, dry_run=args.dry_run, epoch_id=args.epoch_id
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
