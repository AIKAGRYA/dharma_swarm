#!/usr/bin/env python3
"""Validate governed LLM prompt packs before agent execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

VALID_STATUSES = {"draft", "advisory", "candidate", "enforced"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
DESTRUCTIVE_TERMS = {
    "consolidate",
    "delete",
    "merge",
    "remove",
    "replace",
    "untangle",
}
REQUIRED_GLOBAL_CONSTRAINTS = {
    "no_single_detector_blocks",
    "no_auto_delete",
    "no_auto_merge",
    "before_after_evidence_required",
}
GATE_TOKENS = {
    "bandit",
    "fallow",
    "mypy",
    "pyright",
    "pytest",
    "quality",
    "semgrep",
    "slop_verify",
}


def load_prompt_pack(path: Path) -> JsonDict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_any(text: str, needles: set[str]) -> bool:
    normalized = text.lower()
    return any(re.search(rf"\b{re.escape(needle)}\b", normalized) for needle in needles)


def _lane_text(lane: JsonDict) -> str:
    parts = [
        str(lane.get("title", "")),
        str(lane.get("transcript", "")),
        str(lane.get("objective", "")),
    ]
    return "\n".join(parts)


def _validate_source(pack: JsonDict, errors: list[str], check_source_files: bool) -> set[str]:
    source = pack.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        return set()

    artifacts = source.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("source.source_artifacts must be a non-empty list")
        return set()

    completeness = source.get("completeness")
    if completeness == "partial" and not source.get("known_missing_slides"):
        errors.append("partial source must declare known_missing_slides")

    filenames: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"source_artifacts[{index}] must be an object")
            continue
        filename = artifact.get("filename")
        if not _is_nonempty_string(filename):
            errors.append(f"source_artifacts[{index}].filename is required")
        else:
            filenames.add(str(filename))
        sha = artifact.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            errors.append(f"source_artifacts[{index}].sha256 must be 64 lowercase hex chars")
        if check_source_files:
            source_path = artifact.get("source_path")
            if not _is_nonempty_string(source_path):
                errors.append(f"source_artifacts[{index}].source_path is required")
                continue
            path = Path(str(source_path)).expanduser()
            if not path.exists():
                errors.append(f"source artifact missing: {path}")
            elif isinstance(sha, str) and _sha256(path) != sha:
                errors.append(f"source artifact hash mismatch: {path}")
    return filenames


def _validate_lane(
    lane: JsonDict,
    index: int,
    source_filenames: set[str],
    lane_ids: set[str],
    errors: list[str],
) -> None:
    lane_id = lane.get("lane_id")
    if not _is_nonempty_string(lane_id):
        errors.append(f"lanes[{index}].lane_id is required")
    elif lane_id in lane_ids:
        errors.append(f"duplicate lane_id: {lane_id}")
    else:
        lane_ids.add(str(lane_id))

    for field in ("title", "source_artifact", "transcript", "objective", "risk_level"):
        if not _is_nonempty_string(lane.get(field)):
            errors.append(f"{lane_id or f'lanes[{index}]'}.{field} is required")

    if lane.get("source_artifact") not in source_filenames:
        errors.append(f"{lane_id or f'lanes[{index}]'}.source_artifact is not declared")

    transcript = lane.get("transcript")
    if isinstance(transcript, str) and len(transcript.strip()) < 80:
        errors.append(f"{lane_id or f'lanes[{index}]'}.transcript is too short")

    if lane.get("risk_level") not in VALID_RISK_LEVELS:
        errors.append(f"{lane_id or f'lanes[{index}]'}.risk_level is invalid")

    for field in ("required_detectors", "required_gates", "allowed_actions", "forbidden_actions"):
        values = lane.get(field)
        if not isinstance(values, list) or not values or not all(_is_nonempty_string(v) for v in values):
            errors.append(f"{lane_id or f'lanes[{index}]'}.{field} must be a non-empty string list")

    gate_text = " ".join(str(v).lower() for v in lane.get("required_gates", []))
    if not any(token in gate_text for token in GATE_TOKENS):
        errors.append(f"{lane_id or f'lanes[{index}]'} must name at least one real verification gate")

    lane_is_destructive = _contains_any(_lane_text(lane), DESTRUCTIVE_TERMS)
    if lane_is_destructive:
        if lane.get("manual_review_required") is not True:
            errors.append(f"{lane_id or f'lanes[{index}]'} destructive lane requires manual_review_required")
        if lane.get("requires_blast_radius") is not True:
            errors.append(f"{lane_id or f'lanes[{index}]'} destructive lane requires blast radius")
        forbidden = " ".join(str(v).lower() for v in lane.get("forbidden_actions", []))
        if "auto" not in forbidden:
            errors.append(f"{lane_id or f'lanes[{index}]'} destructive lane must forbid auto action")


def validate_prompt_pack(pack: JsonDict, *, check_source_files: bool = False) -> list[str]:
    errors: list[str] = []

    if pack.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not _is_nonempty_string(pack.get("pack_id")):
        errors.append("pack_id is required")
    if pack.get("status") not in VALID_STATUSES:
        errors.append("status is invalid")

    constraints = pack.get("global_constraints")
    if not isinstance(constraints, list):
        errors.append("global_constraints must be a list")
    else:
        missing = REQUIRED_GLOBAL_CONSTRAINTS.difference(set(constraints))
        for constraint in sorted(missing):
            errors.append(f"missing global constraint: {constraint}")

    gate_contract = pack.get("gate_contract")
    if not isinstance(gate_contract, dict):
        errors.append("gate_contract must be an object")
    else:
        for field in ("before_agent_run", "after_agent_run"):
            values = gate_contract.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"gate_contract.{field} must be a non-empty list")

    source_filenames = _validate_source(pack, errors, check_source_files)

    lanes = pack.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("lanes must be a non-empty list")
        return errors

    lane_ids: set[str] = set()
    for index, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            errors.append(f"lanes[{index}] must be an object")
            continue
        _validate_lane(lane, index, source_filenames, lane_ids, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, help="Prompt pack JSON file")
    parser.add_argument("--check-source-files", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result")
    args = parser.parse_args()

    errors = validate_prompt_pack(
        load_prompt_pack(args.pack),
        check_source_files=args.check_source_files,
    )
    result = {
        "path": str(args.pack),
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print(f"prompt pack valid: {args.pack}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
