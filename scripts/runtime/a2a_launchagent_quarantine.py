#!/usr/bin/env python3
"""Quarantine broken A2A/NATS LaunchAgent declarations with receipts.

This is a cleanup tool for stale launchd declarations, not a daemon manager. It
does not load, unload, start, stop, or kill jobs. It moves selected plist files
out of ``~/Library/LaunchAgents`` into a dated quarantine root, leaves one
pointer README, and writes a machine-readable receipt.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.launchagent_quarantine_receipt.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / "2026-06-13"
    / "A2A_DAEMON_WIRING_AUDIT.json"
)
DEFAULT_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
DEFAULT_QUARANTINE_ROOT = (
    Path.home() / ".dharma" / "a2a_bus" / "quarantine" / "launch_agents"
)
DEFAULT_RECEIPT_DIR = REPO_ROOT / "reports" / "a2a" / "launchagent_quarantine_receipts"
POINTER_NAME = "DHARMA_A2A_RUNTIME_SPINE_README.md"
TRACK_PATH = "docs/governance/active_tracks/a2a-runtime-spine-2026-06/"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def load_audit(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def select_candidates(
    audit: dict[str, Any],
    *,
    launch_agents_dir: Path,
    labels: set[str],
    statuses: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in audit.get("candidates", []):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        status = str(item.get("status") or "")
        path_text = str(item.get("path") or "")
        if labels and label not in labels:
            skipped.append({"label": label, "path": path_text, "reason": "label_not_selected"})
            continue
        if statuses and status not in statuses:
            skipped.append({"label": label, "path": path_text, "reason": "status_not_selected"})
            continue
        path = Path(path_text).expanduser()
        if path.suffix != ".plist":
            skipped.append({"label": label, "path": path_text, "reason": "not_plist"})
            continue
        if not _is_under(path, launch_agents_dir):
            skipped.append({"label": label, "path": path_text, "reason": "outside_launch_agents_dir"})
            continue
        if not path.exists():
            skipped.append({"label": label, "path": path_text, "reason": "missing_source"})
            continue
        candidates.append(
            {
                "label": label,
                "status": status,
                "path": str(path),
                "issue_types": [
                    str(issue.get("type"))
                    for issue in item.get("issues", [])
                    if isinstance(issue, dict) and issue.get("type")
                ],
                "program_arguments": item.get("program_arguments", []),
                "working_directory": item.get("working_directory"),
                "broker_scope": item.get("broker_scope"),
            }
        )
    return candidates, skipped


def _dest_for(source: Path, quarantine_run_root: Path) -> Path:
    dest = quarantine_run_root / source.name
    if not dest.exists():
        return dest
    suffix = source.stat().st_size if source.exists() else "duplicate"
    return quarantine_run_root / f"{source.stem}.{suffix}{source.suffix}"


def write_pointer(
    launch_agents_dir: Path,
    *,
    receipt_path: Path,
    quarantine_run_root: Path,
    moved_count: int,
    when: str,
) -> Path:
    text = f"""# Dharma A2A Runtime Spine LaunchAgent Pointer

Broken Dharma A2A/NATS LaunchAgent plist files were quarantined at `{when}`.

- Moved plist count: `{moved_count}`
- Quarantine path: `{quarantine_run_root}`
- Receipt: `{receipt_path}`
- Active track: `{TRACK_PATH}`

The quarantined plists were stale declarations that pointed at deleted modules,
deleted scripts, or the wrong broker scope. Production A2A/NATS contact must be
proven by the active-track receipts and AGNI target-owned handler records, not
by legacy filesystem inboxes or crash-looping launchd jobs.

Restore only by copying a specific plist back from the quarantine path after the
target module/script and broker scope are repaired.
"""
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    path = launch_agents_dir / POINTER_NAME
    path.write_text(text, encoding="utf-8")
    return path


def write_quarantine_readme(
    quarantine_run_root: Path,
    *,
    receipt_path: Path,
    candidates: list[dict[str, Any]],
    when: str,
) -> Path:
    lines = [
        "# A2A LaunchAgent Quarantine",
        "",
        f"Created at: `{when}`",
        f"Receipt: `{receipt_path}`",
        f"Active track: `{TRACK_PATH}`",
        "",
        "Moved declarations:",
    ]
    for candidate in candidates:
        lines.append(
            f"- `{candidate['label']}` from `{candidate['path']}` "
            f"issues={candidate.get('issue_types', [])}"
        )
    lines.extend(
        [
            "",
            "These files are backups. They are not production-ready declarations.",
        ]
    )
    quarantine_run_root.mkdir(parents=True, exist_ok=True)
    path = quarantine_run_root / "README.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_receipt(receipt_dir: Path, payload: dict[str, Any]) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"{stamp()}-a2a-launchagent-quarantine.json"
    suffix = 1
    while path.exists():
        path = receipt_dir / f"{stamp()}-a2a-launchagent-quarantine-{suffix}.json"
        suffix += 1
    payload["receipt_path"] = str(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_quarantine(
    *,
    audit_path: Path,
    launch_agents_dir: Path,
    quarantine_root: Path,
    receipt_dir: Path,
    labels: set[str],
    statuses: set[str],
    apply: bool,
) -> dict[str, Any]:
    when = utc_now()
    run_id = stamp()
    quarantine_run_root = quarantine_root / run_id
    audit = load_audit(audit_path)
    candidates, skipped = select_candidates(
        audit,
        launch_agents_dir=launch_agents_dir,
        labels=labels,
        statuses=statuses,
    )
    moved: list[dict[str, Any]] = []
    if apply:
        quarantine_run_root.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            source = Path(str(candidate["path"]))
            dest = _dest_for(source, quarantine_run_root)
            try:
                size = source.stat().st_size
                shutil.move(str(source), str(dest))
            except (OSError, shutil.Error) as exc:
                skipped.append(
                    {
                        "label": candidate["label"],
                        "path": str(source),
                        "reason": "move_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            moved.append(
                {
                    "label": candidate["label"],
                    "from": str(source),
                    "to": str(dest),
                    "bytes": size,
                    "issue_types": candidate.get("issue_types", []),
                }
            )

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": when,
        "mode": "apply" if apply else "dry_run",
        "status": "APPLIED" if apply else "DRY_RUN",
        "production_claim": False,
        "launchctl_mutated": False,
        "audit_path": str(audit_path),
        "launch_agents_dir": str(launch_agents_dir),
        "quarantine_root": str(quarantine_root),
        "quarantine_run_root": str(quarantine_run_root),
        "active_track": TRACK_PATH,
        "selected_statuses": sorted(statuses),
        "selected_labels": sorted(labels),
        "candidate_count": len(candidates),
        "candidate_labels": [candidate["label"] for candidate in candidates],
        "moved_count": len(moved),
        "moved": moved,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "interpretation": (
            "APPLIED means stale LaunchAgent plist files were moved out of the "
            "LaunchAgents directory with backups. It does not prove that live "
            "A2A handlers or production quorum are ready."
        ),
    }
    receipt_path = write_receipt(receipt_dir, receipt)
    if apply:
        pointer_path = write_pointer(
            launch_agents_dir,
            receipt_path=receipt_path,
            quarantine_run_root=quarantine_run_root,
            moved_count=len(moved),
            when=when,
        )
        readme_path = write_quarantine_readme(
            quarantine_run_root,
            receipt_path=receipt_path,
            candidates=candidates,
            when=when,
        )
        receipt["pointer_path"] = str(pointer_path)
        receipt["quarantine_readme_path"] = str(readme_path)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT))
    parser.add_argument("--launch-agents-dir", default=str(DEFAULT_LAUNCH_AGENTS_DIR))
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="LaunchAgent label to select. Repeatable. Defaults to all matching statuses.",
    )
    parser.add_argument(
        "--status",
        action="append",
        default=["FAIL"],
        help="Audit status to select. Repeatable. Defaults to FAIL.",
    )
    parser.add_argument("--apply", action="store_true", help="Move selected plist files.")
    parser.add_argument("--json", action="store_true", help="Print full JSON receipt.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    receipt = run_quarantine(
        audit_path=Path(args.audit_path).expanduser(),
        launch_agents_dir=Path(args.launch_agents_dir).expanduser(),
        quarantine_root=Path(args.quarantine_root).expanduser(),
        receipt_dir=Path(args.receipt_dir).expanduser(),
        labels=set(args.label),
        statuses=set(args.status),
        apply=args.apply,
    )
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            f"{receipt['status']} candidates={receipt['candidate_count']} "
            f"moved={receipt['moved_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
