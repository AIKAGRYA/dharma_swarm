#!/usr/bin/env python3
"""Minimal live trigger for tools/github_ingestor_go (go-g04 work packet).

Watches a drop directory for GitHub event payload envelopes and runs each one
through the Go GitHub ingestor, which emits a normalized
``go_evidence_receipt.v0`` receipt. Receipts land in the sidecar dir that
``dharma_swarm/operator_core/go_github_bridge.py`` reads. This runner is a
thin trigger only: it never calls the GitHub API, never dispatches agents, and
never decides policy — it converts dropped payload files into receipts.

Envelope format (one JSON file per event, dropped into the inbox):

    {
      "event_type": "github_pull_request",   # required; see SupportedEventTypes
      "payload": { ... },                     # required: raw GitHub event payload
      "source_url": "https://github.com/...", # optional
      "correlation_id": "..."                 # optional; generated when absent
    }

Processed envelopes move to ``<inbox>/processed/``; failures move to
``<inbox>/failed/`` with a ``.error.txt`` sidecar. HOST-AWARE: with neither a
prebuilt binary (`make go-build`) nor a Go toolchain the runner reports
``needs_host``, leaves payloads in place, and exits 0.

Usage:
    python3 scripts/runtime/github_ingestor_runner.py [--inbox DIR] [--receipt-dir DIR] [--max-files N]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.world_radar.go_bridge import _go_invocation  # noqa: E402
from dharma_swarm.world_radar.go_invoke import go_toolchain_capable  # noqa: E402

MODULE_DIR = REPO_ROOT / "tools" / "github_ingestor_go"
SUPPORTED_EVENT_TYPES = (
    "github_pull_request",
    "github_commit",
    "github_check_run",
    "github_release",
)


def default_inbox_dir() -> Path:
    return dharma_state_dir() / "meta" / "github_ingest_inbox"


def default_receipt_dir() -> Path:
    return dharma_state_dir() / "go_receipts" / "github"


def _host_ready(module_dir: Path) -> bool:
    # Count the prebuilt binary only when it is actually executable, mirroring
    # _go_invocation()'s own test (binary.is_file() and os.access(X_OK)). A
    # stale/non-executable file named like the binary would otherwise pass this
    # gate while _go_invocation() falls back to `go run .`, which fails without a
    # Go toolchain and pushes queued envelopes to failed/ instead of leaving
    # them for a capable host (needs_host).
    binary = module_dir / module_dir.name
    if binary.is_file() and os.access(binary, os.X_OK):
        return True
    # Version-aware (WP-0C2, TIT-003): a Go toolchain that does not satisfy
    # the module's go.mod directive is needs_host, never an execution attempt
    # — attempting `go run .` with an incompatible toolchain would fail and
    # push queued envelopes to failed/ instead of leaving them for a capable
    # host.
    return go_toolchain_capable(module_dir)


def process_inbox(
    *,
    inbox_dir: Path,
    receipt_dir: Path,
    module_dir: Path = MODULE_DIR,
    max_files: int = 20,
    timeout_s: int = 30,
) -> dict:
    """Run every pending envelope through the Go ingestor. Returns a summary."""
    summary: dict = {
        "schema_version": "github_ingestor_runner_summary.v1",
        "inbox_dir": str(inbox_dir),
        "receipt_dir": str(receipt_dir),
        "status": "ok",
        "processed": 0,
        "failed": 0,
        "receipts": [],
        "errors": [],
    }
    if not module_dir.exists():
        summary["status"] = "failed"
        summary["errors"].append(f"missing Go module: {module_dir}")
        return summary
    if not _host_ready(module_dir):
        summary["status"] = "needs_host"
        summary["errors"].append(
            "no prebuilt github_ingestor_go binary (run `make go-build`) and no Go toolchain"
        )
        return summary

    inbox_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = inbox_dir / "processed"
    failed_dir = inbox_dir / "failed"
    pending = sorted(p for p in inbox_dir.glob("*.json") if p.is_file())[:max_files]
    cmd_prefix, invocation_mode = _go_invocation(module_dir)
    summary["invocation_mode"] = invocation_mode

    for envelope_path in pending:
        error = _process_one(
            envelope_path=envelope_path,
            receipt_dir=receipt_dir,
            module_dir=module_dir,
            cmd_prefix=cmd_prefix,
            timeout_s=timeout_s,
            summary=summary,
        )
        if error is None:
            summary["processed"] += 1
            _move_to(envelope_path, processed_dir)
        else:
            summary["failed"] += 1
            summary["errors"].append(f"{envelope_path.name}: {error}")
            moved = _move_to(envelope_path, failed_dir)
            moved.with_suffix(".error.txt").write_text(error + "\n", encoding="utf-8")
    if summary["failed"]:
        summary["status"] = "degraded"
    return summary


def _process_one(
    *,
    envelope_path: Path,
    receipt_dir: Path,
    module_dir: Path,
    cmd_prefix: list[str],
    timeout_s: int,
    summary: dict,
) -> str | None:
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"unreadable envelope: {exc}"
    if not isinstance(envelope, dict):
        return "envelope must be a JSON object"
    event_type = str(envelope.get("event_type") or "")
    if event_type not in SUPPORTED_EVENT_TYPES:
        return f"unsupported event_type: {event_type!r} (supported: {', '.join(SUPPORTED_EVENT_TYPES)})"
    payload = envelope.get("payload")
    if not isinstance(payload, (dict, list)):
        return "envelope missing 'payload' object"

    correlation_id = str(
        envelope.get("correlation_id") or f"github_ingest_{time.time_ns()}"
    )
    receipt_path = receipt_dir / f"{envelope_path.stem}_{time.time_ns()}.json"
    payload_path = receipt_dir / f".{envelope_path.stem}.payload.tmp.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    cmd = cmd_prefix + [
        "--input",
        str(payload_path),
        "--output",
        str(receipt_path),
        "--event-type",
        event_type,
        "--correlation-id",
        correlation_id,
    ]
    source_url = str(envelope.get("source_url") or "")
    if source_url:
        cmd.extend(["--source-url", source_url])
    try:
        proc = subprocess.run(
            cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s
        )
    except FileNotFoundError as exc:
        return f"github_ingestor_go could not start: {exc}"
    except subprocess.TimeoutExpired:
        return f"github_ingestor_go timed out after {timeout_s}s"
    finally:
        payload_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "github_ingestor_go failed").strip()[:1000]
    if not receipt_path.exists():
        return "github_ingestor_go exited 0 but wrote no receipt"
    summary["receipts"].append(str(receipt_path))
    return None


def _move_to(path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        dest = dest_dir / f"{path.stem}_{time.time_ns()}{path.suffix}"
    return path.rename(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", default=None, help="watched payload drop dir")
    parser.add_argument("--receipt-dir", default=None, help="receipt output dir")
    parser.add_argument("--max-files", type=int, default=20)
    parser.add_argument("--timeout-sec", type=int, default=30)
    args = parser.parse_args()

    summary = process_inbox(
        inbox_dir=Path(args.inbox).expanduser() if args.inbox else default_inbox_dir(),
        receipt_dir=(
            Path(args.receipt_dir).expanduser() if args.receipt_dir else default_receipt_dir()
        ),
        max_files=args.max_files,
        timeout_s=args.timeout_sec,
    )
    print(json.dumps(summary, indent=2))
    # needs_host is not a failure (host-aware doctrine); degraded/failed is.
    return 0 if summary["status"] in {"ok", "needs_host"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
