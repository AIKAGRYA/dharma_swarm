#!/usr/bin/env python3
"""Quarantine stale A2A filesystem inbox contents with receipts.

The filesystem inbox is a compatibility dock, not the live-contact authority.
This tool supports a clean reset without deleting evidence in place: it moves
selected inbox files into a dated quarantine root, leaves a README pointer in
each drained inbox, and writes a machine-readable receipt.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOXES_ROOT = Path.home() / ".dharma" / "a2a_bus" / "inboxes"
DEFAULT_QUARANTINE_ROOT = Path.home() / ".dharma" / "a2a_bus" / "quarantine" / "inboxes"
DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "inbox_quarantine_receipts"
TRACK_PATH = "docs/governance/active_tracks/a2a-runtime-spine-2026-06/"


@dataclass(frozen=True)
class Candidate:
    path: Path
    agent: str
    reason: str
    age_hours: float | None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [
        char if char.isalnum() or char in ("_", "-", ".") else "_"
        for char in str(value or "")
    ]
    cleaned = "".join(chars).strip("_.-")
    return cleaned[:96] or fallback


def _file_age_hours(path: Path, *, now: datetime | None = None) -> float | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    now = now or datetime.now(timezone.utc)
    return max((now.timestamp() - mtime) / 3600.0, 0.0)


def _is_candidate_path(path: Path) -> bool:
    return path.exists() and path.name != "README.md"


def _entry_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if path.is_dir():
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
        return total
    return 0


def discover_candidates(
    inboxes_root: Path,
    *,
    agents: set[str],
    filenames: set[str],
    include_recent: bool,
    recent_hours: float,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    candidates: list[Candidate] = []
    skipped: list[dict[str, Any]] = []
    if not inboxes_root.exists():
        return candidates, [{"path": str(inboxes_root), "reason": "inboxes_root_missing"}]

    inbox_dirs = sorted(path for path in inboxes_root.iterdir() if path.is_dir())
    for inbox_dir in inbox_dirs:
        agent = inbox_dir.name
        if agents and agent not in agents:
            continue
        for path in sorted(inbox_dir.iterdir()):
            if not _is_candidate_path(path):
                skipped.append({"path": str(path), "agent": agent, "reason": "not_candidate_file"})
                continue
            if filenames and path.name not in filenames:
                skipped.append({"path": str(path), "agent": agent, "reason": "filename_filter_mismatch"})
                continue
            age_hours = _file_age_hours(path)
            if (
                not include_recent
                and age_hours is not None
                and age_hours < recent_hours
            ):
                skipped.append(
                    {
                        "path": str(path),
                        "agent": agent,
                        "reason": "recent_file_skipped",
                        "age_hours": round(age_hours, 3),
                    }
                )
                continue
            candidates.append(
                Candidate(
                    path=path,
                    agent=agent,
                    reason="selected",
                    age_hours=round(age_hours, 3) if age_hours is not None else None,
                )
            )
    return candidates, skipped


def _destination_for(candidate: Candidate, quarantine_run_root: Path) -> Path:
    agent = _safe_token(candidate.agent)
    dest_dir = quarantine_run_root / agent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / candidate.path.name
    if not dest.exists():
        return dest
    suffix = _entry_size(candidate.path)
    return dest_dir / f"{candidate.path.stem}.{suffix}{candidate.path.suffix}"


def _write_readme(
    inbox_dir: Path,
    *,
    moved_count: int,
    quarantine_path: Path,
    receipt_path: Path,
    when: str,
) -> None:
    text = f"""# A2A Inbox Quarantine

This filesystem inbox was drained at `{when}`.

- Files moved: `{moved_count}`
- Quarantine path: `{quarantine_path}`
- Receipt: `{receipt_path}`
- New active-track route: `{TRACK_PATH}`

The filesystem inbox is a dock/mirror surface. It is not proof of live agent
reachability. Future production contact must be proven through NATS ack tiers
and typed receipts.
"""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    (inbox_dir / "README.md").write_text(text, encoding="utf-8")


def write_receipt(receipt_dir: Path, payload: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"{stamp()}-a2a-inbox-quarantine.json"
    suffix = 1
    while path.exists():
        path = receipt_dir / f"{stamp()}-a2a-inbox-quarantine-{suffix}.json"
        suffix += 1
    payload["receipt_path"] = str(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_quarantine(
    *,
    inboxes_root: Path,
    quarantine_root: Path,
    receipt_dir: Path,
    agents: set[str],
    filenames: set[str],
    apply: bool,
    include_recent: bool,
    recent_hours: float,
) -> dict[str, Any]:
    when = utc_now()
    run_id = stamp()
    quarantine_run_root = quarantine_root / run_id
    candidates, skipped = discover_candidates(
        inboxes_root,
        agents=agents,
        filenames=filenames,
        include_recent=include_recent,
        recent_hours=recent_hours,
    )
    moved: list[dict[str, Any]] = []
    inbox_moved_counts: dict[str, int] = {}
    candidate_counts_by_agent: dict[str, int] = {}
    candidate_bytes_by_agent: dict[str, int] = {}
    for candidate in candidates:
        candidate_counts_by_agent[candidate.agent] = candidate_counts_by_agent.get(candidate.agent, 0) + 1
        candidate_bytes_by_agent[candidate.agent] = (
            candidate_bytes_by_agent.get(candidate.agent, 0) + _entry_size(candidate.path)
        )
    total_bytes = 0
    if apply:
        quarantine_run_root.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            try:
                size = _entry_size(candidate.path)
                dest = _destination_for(candidate, quarantine_run_root)
                shutil.move(str(candidate.path), str(dest))
            except (OSError, shutil.Error) as exc:
                skipped.append(
                    {
                        "path": str(candidate.path),
                        "agent": candidate.agent,
                        "reason": "move_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            total_bytes += size
            inbox_moved_counts[candidate.agent] = inbox_moved_counts.get(candidate.agent, 0) + 1
            moved.append(
                {
                    "from": str(candidate.path),
                    "to": str(dest),
                    "agent": candidate.agent,
                    "bytes": size,
                    "entry_type": "directory" if dest.is_dir() else "file",
                    "age_hours": candidate.age_hours,
                }
            )

    receipt = {
        "schema_version": "dharma.a2a.inbox_quarantine_receipt.v1",
        "timestamp": when,
        "mode": "apply" if apply else "dry_run",
        "status": "APPLIED" if apply else "DRY_RUN",
        "inboxes_root": str(inboxes_root),
        "quarantine_root": str(quarantine_root),
        "quarantine_run_root": str(quarantine_run_root),
        "agent_filter": sorted(agents),
        "filename_filter": sorted(filenames),
        "include_recent": include_recent,
        "recent_hours": recent_hours,
        "candidate_count": len(candidates),
        "candidate_counts_by_agent": dict(sorted(candidate_counts_by_agent.items())),
        "candidate_bytes_by_agent": dict(sorted(candidate_bytes_by_agent.items())),
        "candidate_preview": [
            {
                "path": str(candidate.path),
                "agent": candidate.agent,
                "age_hours": candidate.age_hours,
                "entry_type": "directory" if candidate.path.is_dir() else "file",
            }
            for candidate in candidates[:100]
        ],
        "moved_count": len(moved),
        "skipped_count": len(skipped),
        "moved_bytes": total_bytes,
        "moved": moved,
        "skipped": skipped,
        "track_path": TRACK_PATH,
    }
    receipt_path = write_receipt(receipt_dir, receipt)
    if apply:
        for agent, count in sorted(inbox_moved_counts.items()):
            _write_readme(
                inboxes_root / agent,
                moved_count=count,
                quarantine_path=quarantine_run_root / _safe_token(agent),
                receipt_path=receipt_path,
                when=when,
            )
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inboxes-root", default=str(DEFAULT_INBOXES_ROOT))
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--agent", action="append", default=[], help="agent inbox to drain; repeatable")
    parser.add_argument("--filename", action="append", default=[], help="exact inbox filename to drain; repeatable")
    parser.add_argument("--include-recent", action="store_true", help="include files newer than --recent-hours")
    parser.add_argument("--recent-hours", type=float, default=24.0)
    parser.add_argument("--apply", action="store_true", help="move files; default is dry-run only")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agents = {_safe_token(agent) for agent in args.agent}
    filenames = {str(name) for name in args.filename}
    receipt = run_quarantine(
        inboxes_root=Path(args.inboxes_root).expanduser(),
        quarantine_root=Path(args.quarantine_root).expanduser(),
        receipt_dir=Path(args.receipt_dir).expanduser(),
        agents=agents,
        filenames=filenames,
        apply=bool(args.apply),
        include_recent=bool(args.include_recent),
        recent_hours=max(args.recent_hours, 0.0),
    )
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            f"{receipt['status']} candidates={receipt['candidate_count']} "
            f"moved={receipt['moved_count']} skipped={receipt['skipped_count']}"
        )
        print(f"receipt: {receipt['receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
