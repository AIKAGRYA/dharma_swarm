#!/usr/bin/env python3
"""Validate A2A production readiness quorum records.

The quorum is an evidence gate, not a voting ritual. A READY aggregate requires
at least two persistent agent IDs, at least three model families, numeric
readiness percentages with median >= 80, no red blockers, and evidence refs on
every reviewer record.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum"
REVIEWER_SCHEMA = "dharma.a2a.prod_readiness_reviewer.v1"
AGGREGATE_SCHEMA = "dharma.a2a.prod_readiness_quorum.v1"
NON_REVIEWER_RECORD_NAMES = {
    "QUORUM_BLOCKER_STATUS.json",
    "QUORUM_DELIVERY_STATUS.json",
    "REVIEWER_ROUTE_HEALTH.json",
    "SOLICITATION_RECEIPT.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _evidence_ref_exists(ref: str, source: Path) -> bool:
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path.exists()
    return any(
        candidate.exists()
        for candidate in (
            REPO_ROOT / path,
            source.parent / path,
        )
    )


def _record_errors(record: dict[str, Any], source: Path) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != REVIEWER_SCHEMA:
        errors.append(f"{source}: schema_version must be {REVIEWER_SCHEMA}")
    for field in ("agent_id", "model_family", "role", "verdict", "created_at"):
        if not isinstance(record.get(field), str) or not record.get(field, "").strip():
            errors.append(f"{source}: {field} must be a non-empty string")
    percent = record.get("readiness_percent")
    if not _is_number(percent) or percent < 0 or percent > 100:
        errors.append(f"{source}: readiness_percent must be a number from 0 to 100")
    if not isinstance(record.get("red_blockers"), list):
        errors.append(f"{source}: red_blockers must be a list")
    evidence_refs = record.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append(f"{source}: evidence_refs must be a non-empty list")
    else:
        for ref in evidence_refs:
            if not isinstance(ref, str) or not ref.strip():
                errors.append(f"{source}: every evidence_ref must be a non-empty string")
                continue
            if ref.startswith(("http://", "https://")):
                errors.append(f"{source}: evidence_ref must be a local path, not URL: {ref}")
                continue
            if not _evidence_ref_exists(ref, source):
                errors.append(f"{source}: evidence_ref does not exist: {ref}")
    return errors


def load_reviewer_records(record_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if not record_dir.exists():
        return records, [f"{record_dir}: record directory missing"]
    for path in sorted(record_dir.glob("*.json")):
        if path.name == "latest.json" or path.name in NON_REVIEWER_RECORD_NAMES:
            continue
        if path.name.endswith("_SEND.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: unreadable JSON ({type(exc).__name__}: {exc})")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}: reviewer record must be a JSON object")
            continue
        record["_source"] = str(path)
        errors.extend(_record_errors(record, path))
        records.append(record)
    return records, errors


def aggregate_quorum(record_dir: Path) -> dict[str, Any]:
    records, errors = load_reviewer_records(record_dir)
    agent_ids = sorted({str(r.get("agent_id")) for r in records if r.get("agent_id")})
    model_families = sorted({str(r.get("model_family")) for r in records if r.get("model_family")})
    percents = [
        float(r["readiness_percent"])
        for r in records
        if _is_number(r.get("readiness_percent"))
    ]
    roles = [str(r.get("role", "")).lower() for r in records]
    red_blocker_records = [
        str(r.get("agent_id", r.get("_source", "unknown")))
        for r in records
        if isinstance(r.get("red_blockers"), list) and r.get("red_blockers")
    ]

    missing: list[str] = []
    if len(agent_ids) < 2:
        missing.append("at least two persistent agent IDs")
    if len(model_families) < 3:
        missing.append("at least three model families")
    if len(percents) != len(records) or not records:
        missing.append("numeric readiness percentages for every reviewer")
    median = statistics.median(percents) if percents else 0.0
    if median < 80:
        missing.append("median readiness >= 80")
    if red_blocker_records:
        missing.append("zero red blockers")
    if not any("security" in role or "adversarial" in role or "paranoid" in role for role in roles):
        missing.append("one adversarial/security-minded reviewer")
    if not any("ops" in role or "devops" in role or "operations" in role for role in roles):
        missing.append("one operations/devops-minded reviewer")
    if errors:
        missing.append("valid reviewer record schema")

    ready = not missing
    return {
        "schema_version": AGGREGATE_SCHEMA,
        "created_at": utc_now(),
        "record_dir": str(record_dir),
        "status": "READY" if ready else "NOT_READY",
        "ready": ready,
        "reviewer_count": len(records),
        "agent_ids": agent_ids,
        "model_families": model_families,
        "readiness_percent_median": median,
        "red_blocker_records": red_blocker_records,
        "missing_requirements": missing,
        "errors": errors,
        "reviewers": [
            {
                "agent_id": r.get("agent_id"),
                "model_family": r.get("model_family"),
                "role": r.get("role"),
                "readiness_percent": r.get("readiness_percent"),
                "verdict": r.get("verdict"),
                "red_blocker_count": len(r.get("red_blockers") or []),
                "evidence_ref_count": len(r.get("evidence_refs") or []),
                "source": r.get("_source"),
            }
            for r in records
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--date", help="Reviewer record subdirectory, e.g. 2026-06-13")
    parser.add_argument("--record-dir", type=Path, help="Explicit reviewer record directory")
    parser.add_argument("--write-latest", action="store_true")
    parser.add_argument("--allow-not-ready", action="store_true")
    args = parser.parse_args(argv)

    record_dir = args.record_dir or (args.root / (args.date or datetime.now(timezone.utc).date().isoformat()))
    aggregate = aggregate_quorum(record_dir)
    output = json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(output)

    if args.write_latest:
        args.root.mkdir(parents=True, exist_ok=True)
        (args.root / "latest.json").write_text(output, encoding="utf-8")

    if aggregate["ready"] or args.allow_not_ready:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
