#!/usr/bin/env python3
"""Evaluate the fixed Helm seat matrix from raw, pre-existing evidence.

This harness is intentionally offline.  It does not probe providers, inspect
credentials, drive tmux, or launch the terminal.  Its only authority-bearing
operation is one call to ``project_helm_on_call`` for one runtime epoch.

Evidence, when supplied, is a JSON array of strict raw ``RouteEvidence`` rows.
Serialized verdicts are never accepted as evidence.  Operational blockers are
separate observations and cannot promote an evaluator verdict.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.helm_route_truth_codec import (  # noqa: E402
    route_evidence_from_dict,
    route_verification_to_dict,
)
from dharma_swarm.helm_route_truth_evaluator import project_helm_on_call  # noqa: E402
from dharma_swarm.helm_route_truth_types import (  # noqa: E402
    HELM_SLICE1_SEATS,
    RouteEvidence,
    RouteVerdict,
)


REPORT_SCHEMA_VERSION = "dharma.helm.seat_matrix_run.v1"
BLOCKER_TYPES = frozenset(
    {
        "identity_unproven",
        "key_missing",
        "model_missing",
        "quota",
        "unsupported_transport",
    }
)
DEFAULT_BLOCKER = "identity_unproven"


class MatrixInputError(ValueError):
    """The requested run is malformed or violates a harness invariant."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MatrixInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MatrixInputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise MatrixInputError(f"invalid JSON in {path}: {exc.msg}") from exc


def load_evidence(path: Path) -> tuple[RouteEvidence, ...]:
    """Load only a strict JSON array of raw ``RouteEvidence`` rows."""

    payload = _load_json(path)
    if not isinstance(payload, list):
        raise MatrixInputError("evidence must be a JSON array of raw RouteEvidence rows")
    if len(payload) > len(HELM_SLICE1_SEATS):
        raise MatrixInputError("evidence cannot contain more than seven rows")
    rows: list[RouteEvidence] = []
    for index, item in enumerate(payload):
        try:
            rows.append(route_evidence_from_dict(item))
        except (TypeError, ValueError) as exc:
            raise MatrixInputError(
                f"evidence row {index} must be strict raw RouteEvidence: {exc}"
            ) from exc
    return tuple(rows)


def validate_blocker_map(value: Any) -> dict[str, str]:
    """Require one closed-vocabulary blocker observation for every fixed seat."""

    if not isinstance(value, Mapping):
        raise MatrixInputError("blocker manifest must be a JSON object")
    expected_ids = tuple(seat.seat_id for seat in HELM_SLICE1_SEATS)
    if set(value) != set(expected_ids):
        raise MatrixInputError("blocker manifest must contain exactly the seven fixed seat ids")
    result: dict[str, str] = {}
    for seat_id in expected_ids:
        blocker = value[seat_id]
        if not isinstance(blocker, str) or blocker not in BLOCKER_TYPES:
            choices = ", ".join(sorted(BLOCKER_TYPES))
            raise MatrixInputError(f"invalid blocker for {seat_id}; expected one of: {choices}")
        result[seat_id] = blocker
    return result


def load_blockers(path: Path) -> dict[str, str]:
    return validate_blocker_map(_load_json(path))


def _default_blockers() -> dict[str, str]:
    # With no external observation, only the absence of identity proof is known.
    # We deliberately do not infer key, funding, model, or transport state.
    return {seat.seat_id: DEFAULT_BLOCKER for seat in HELM_SLICE1_SEATS}


def _validate_epoch(runtime_epoch: str) -> str:
    if not isinstance(runtime_epoch, str) or not runtime_epoch.strip():
        raise MatrixInputError("runtime epoch must be a non-empty string")
    return runtime_epoch


def choose_runtime_epoch(
    evidences: Sequence[RouteEvidence],
    explicit_epoch: str | None,
) -> str:
    """Choose one epoch, rejecting evidence assembled across live processes."""

    evidence_epochs = {
        row.runtime_epoch
        for row in evidences
        if isinstance(row.runtime_epoch, str) and row.runtime_epoch.strip()
    }
    if len(evidence_epochs) > 1:
        raise MatrixInputError("evidence spans multiple runtime epochs")
    if explicit_epoch is not None:
        return _validate_epoch(explicit_epoch)
    if evidence_epochs:
        return _validate_epoch(next(iter(evidence_epochs)))
    return f"helm-seat-matrix:{uuid4()}"


def build_report(
    *,
    evidences: Sequence[RouteEvidence],
    blocker_map: Mapping[str, str] | None,
    now: datetime,
    runtime_epoch: str,
) -> dict[str, Any]:
    """Run the authoritative evaluator once and attach non-authoritative blockers."""

    runtime_epoch = _validate_epoch(runtime_epoch)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise MatrixInputError("evaluation time must be timezone-aware")
    blockers = _default_blockers() if blocker_map is None else validate_blocker_map(blocker_map)

    # This is the sole evaluation call: one process, timestamp, and runtime epoch.
    projection = project_helm_on_call(
        evidences,
        now=now,
        current_runtime_epoch=runtime_epoch,
    )
    rows = [route_verification_to_dict(row) for row in projection.seats]
    expected_ids = [seat.seat_id for seat in HELM_SLICE1_SEATS]
    if len(rows) != 7 or [row["seat_id"] for row in rows] != expected_ids:
        raise MatrixInputError("evaluator did not return the fixed ordered seven-seat matrix")
    if rows and all(row["reason"] == "malformed_evidence_batch" for row in rows):
        raise MatrixInputError("malformed evidence batch: seats must be known, unique, and ordered")

    blocker_rows = [
        {"seat_id": row["seat_id"], "blocker": blockers[row["seat_id"]]}
        for row in rows
        if row["verdict"] != RouteVerdict.ON_CALL.value
    ]
    if len(blocker_rows) != sum(
        row["verdict"] != RouteVerdict.ON_CALL.value for row in rows
    ):
        raise MatrixInputError("every non-ON_CALL row must have exactly one typed blocker")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": projection.state.value,
        "on_call_count": projection.on_call_count,
        "total": projection.total,
        "evaluated_at": rows[0]["evaluated_at"],
        "runtime_epoch": projection.runtime_epoch,
        "blocker_authority": "operational_observation_only",
        "blocker_vocabulary": sorted(BLOCKER_TYPES),
        "catalog": [
            {
                "seat_id": seat.seat_id,
                "display_label": seat.display_label,
                "logical_lineage": seat.logical_lineage,
                "admissible_served_identities": [
                    {"provider": provider, "model": model}
                    for provider, model in seat.admissible_served_identities
                ],
            }
            for seat in HELM_SLICE1_SEATS
        ],
        "route_verifications": rows,
        "blockers": blocker_rows,
    }


def validate_output_path(path: Path) -> Path:
    """Resolve an explicit report path and confine it to ``~/.dharma``."""

    root = (Path.home() / ".dharma").resolve()
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise MatrixInputError("--output must not be a symlink")
    candidate = expanded.resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise MatrixInputError("--output must be a file beneath ~/.dharma")
    if candidate.exists() and (candidate.is_dir() or candidate.is_symlink()):
        raise MatrixInputError("--output must name a regular file, not a directory or symlink")
    return candidate


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except OSError as exc:
        raise MatrixInputError(f"cannot write {path}: {exc}") from exc
    os.chmod(path, 0o600)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="explicit JSON report path beneath ~/.dharma",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="optional JSON array of strict raw RouteEvidence rows",
    )
    parser.add_argument(
        "--blockers",
        type=Path,
        help="optional complete JSON object mapping seat ids to typed blockers",
    )
    parser.add_argument(
        "--runtime-epoch",
        help="current runtime epoch; inferred from single-epoch evidence or generated",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = validate_output_path(args.output)
        evidences = load_evidence(args.evidence) if args.evidence else ()
        blocker_map = load_blockers(args.blockers) if args.blockers else None
        runtime_epoch = choose_runtime_epoch(evidences, args.runtime_epoch)
        report = build_report(
            evidences=evidences,
            blocker_map=blocker_map,
            now=datetime.now(timezone.utc),
            runtime_epoch=runtime_epoch,
        )
        write_report(output, report)
    except MatrixInputError as exc:
        print(f"helm-seat-matrix: {exc}", file=sys.stderr)
        return 2

    count = report["on_call_count"]
    rendered_count = "?" if count is None else str(count)
    print(f"wrote {output}: {rendered_count}/7 {report['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
