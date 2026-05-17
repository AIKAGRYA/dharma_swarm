#!/usr/bin/env python3
"""Smoke the governed MemoryKernel write receipt API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.memory_kernel import (
    DEFAULT_WRITE_RECEIPT_PATH,
    MemoryKernelWriteReceiptInput,
    append_write_receipts,
    governed_write_receipt,
    load_write_receipt_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--receipt-out", type=Path, default=DEFAULT_WRITE_RECEIPT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt_path = _resolve_output(args.receipt_out, args.repo_root)
    allowed = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:write-receipt-smoke",),
            proposed_operation="append_proposal",
            target_surface="memory_kernel.write_receipts",
            reason="record governed proposal receipt without mutating memory",
            reviewer_state="human_approved",
        )
    )
    denied = governed_write_receipt(
        MemoryKernelWriteReceiptInput(
            source_atom_ids=("memory_atom:direct-mutation-smoke",),
            proposed_operation="update",
            target_surface="canon.primary",
            reason="direct canon mutation should be denied",
            reviewer_state="human_approved",
        )
    )
    if not args.dry_run:
        append_write_receipts(
            receipt_path,
            (allowed, denied),
            forbidden_roots=_memory_surface_roots(args.repo_root),
        )
    status = load_write_receipt_status(receipt_path)
    payload = {
        "allowed_receipt": allowed.to_json(),
        "denied_receipt": denied.to_json(),
        "status": status.to_json(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.fail_on_blocked and not status.ready:
        return 5
    return 0


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _memory_surface_roots(repo_root: Path) -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".dharma",
        home / ".smriti",
        home / ".codex" / "memories",
        repo_root / ".dharma",
        repo_root / ".swarm",
    )


if __name__ == "__main__":
    raise SystemExit(main())
