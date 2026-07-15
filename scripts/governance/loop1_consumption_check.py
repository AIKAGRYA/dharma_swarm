#!/usr/bin/env python3
"""Disjoint read-only verifier for Loop 1 produce→consume closure (WP-LC4)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_kernel.write_receipts import stable_digest, utc_now  # noqa: E402
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB  # noqa: E402
from dharma_swarm.spine.receipt import (  # noqa: E402
    DEFAULT_MACHINE_RECEIPT_PATH,
    _read_verified_machine_receipt_chain,
)


SCHEMA = "dharma_swarm.loop1_consumption.v1"
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT / "reports" / "loop_closure" / "loop1_consumption_receipt.json"
)
CORE_KEYS = (
    "schema",
    "producer_trace_id",
    "consumer_trace_id",
    "consumed_trace_ids",
    "decision_delta",
    "producer_boot_id",
    "consumer_boot_id",
    "chain_verified",
    "delegation_runs_row_count",
)


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _default_witness_path(db_path: Path) -> Path:
    try:
        if db_path.resolve() == Path(DEFAULT_RUNTIME_DB).resolve():
            return DEFAULT_MACHINE_RECEIPT_PATH
    except OSError:
        pass
    return db_path.with_name("claim_evidence_receipts.jsonl")


def _receipt_rows(db_path: Path) -> tuple[list[dict[str, Any]], int]:
    conn = _connect_ro(db_path)
    try:
        row_count = int(
            conn.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0]
        )
        raw_rows = conn.execute(
            """
            SELECT started_at, trace_id, receipt_json, rowid
            FROM delegation_runs
            WHERE receipt_json IS NOT NULL AND receipt_json != ''
            ORDER BY started_at ASC, rowid ASC
            """
        ).fetchall()
    finally:
        conn.close()

    rows: list[dict[str, Any]] = []
    for started_at, column_trace_id, raw_receipt, rowid in raw_rows:
        receipt = json.loads(str(raw_receipt))
        if not isinstance(receipt, dict):
            raise ValueError(f"delegation_runs row {rowid} receipt is not an object")
        receipt["_started_at"] = str(started_at)
        receipt["_rowid"] = int(rowid)
        receipt["_trace_id"] = str(receipt.get("trace_id") or column_trace_id or "")
        rows.append(receipt)
    return rows, row_count


def _witness_trace_ids(path: Path) -> set[str]:
    rows = _read_verified_machine_receipt_chain(path)
    return {
        str((row.get("attributes") or {}).get("trace_id") or "")
        for row in rows
        if isinstance(row.get("attributes"), dict)
    } - {""}


def _consumption_payload(receipt: dict[str, Any]) -> dict[str, Any] | None:
    attributes = receipt.get("attributes")
    if not isinstance(attributes, dict):
        return None
    payload = attributes.get("loop1_consumption")
    return payload if isinstance(payload, dict) else None


def analyze(
    db_path: Path,
    witness_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    """Re-derive one valid P1→P4 chain from raw runtime truth surfaces."""

    findings: list[str] = []
    try:
        rows, row_count = _receipt_rows(db_path)
    except Exception as exc:
        return {}, [f"runtime receipt read failed: {type(exc).__name__}: {exc}"]
    try:
        witness_traces = _witness_trace_ids(witness_path)
    except Exception as exc:
        return {}, [f"witness chain verification failed: {type(exc).__name__}: {exc}"]

    by_trace: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, receipt in enumerate(rows):
        trace_id = str(receipt.get("_trace_id") or "")
        if trace_id:
            by_trace[trace_id] = (index, receipt)

    saw_candidate = False
    for consumer_index, consumer in enumerate(rows):
        payload = _consumption_payload(consumer)
        if payload is None:
            continue
        consumed = tuple(
            str(item) for item in payload.get("consumed_trace_ids") or [] if str(item)
        )
        if not consumed:
            continue
        saw_candidate = True
        candidate_findings: list[str] = []
        consumer_trace = str(consumer.get("_trace_id") or "")
        if consumer_trace in consumed:
            candidate_findings.append(
                f"consumer {consumer_trace or '<missing>'} contains self-citation"
            )

        producers: list[dict[str, Any]] = []
        for trace_id in consumed:
            found = by_trace.get(trace_id)
            if found is None:
                candidate_findings.append(f"consumed trace {trace_id} is absent")
                continue
            producer_index, producer = found
            if producer_index >= consumer_index:
                candidate_findings.append(
                    f"consumed trace {trace_id} is not from a prior cycle"
                )
            producers.append(producer)

        delta = payload.get("decision_delta")
        if not isinstance(delta, dict) or not delta:
            candidate_findings.append("consumer decision_delta is empty")
        elif delta.get("default_order") == delta.get("reordered_order"):
            candidate_findings.append("consumer decision_delta records no order change")

        consumer_attributes = consumer.get("attributes") or {}
        consumer_boot = str(
            payload.get("boot_id")
            or (
                consumer_attributes.get("boot_id")
                if isinstance(consumer_attributes, dict)
                else ""
            )
            or ""
        )
        producer_boot = ""
        if producers:
            producer_attributes = producers[0].get("attributes") or {}
            if isinstance(producer_attributes, dict):
                producer_boot = str(producer_attributes.get("boot_id") or "")
        if not producer_boot or not consumer_boot:
            candidate_findings.append("producer or consumer boot_id is missing")
        elif producer_boot == consumer_boot:
            candidate_findings.append("producer and consumer boot_id are identical")

        required_witnesses = {*consumed, consumer_trace}
        missing_witnesses = sorted(required_witnesses - witness_traces - {""})
        if missing_witnesses:
            candidate_findings.append(
                "witness chain lacks traces: " + ", ".join(missing_witnesses)
            )

        if candidate_findings:
            findings.extend(candidate_findings)
            continue

        return (
            {
                "schema": SCHEMA,
                "producer_trace_id": consumed[0],
                "consumer_trace_id": consumer_trace,
                "consumed_trace_ids": list(consumed),
                "decision_delta": delta,
                "producer_boot_id": producer_boot,
                "consumer_boot_id": consumer_boot,
                "chain_verified": True,
                "delegation_runs_row_count": row_count,
            },
            [],
        )

    if not saw_candidate:
        findings.append("no later receipt cites a prior receipt consumption")
    return {}, findings


def _receipt_digest(body: dict[str, Any]) -> str:
    return stable_digest({key: value for key, value in body.items() if key != "digest"})


def build_receipt(
    *,
    db_path: Path,
    witness_path: Path,
    host_sha: str,
    container_image_digest: str,
) -> dict[str, Any]:
    core, findings = analyze(db_path, witness_path)
    if findings:
        raise ValueError("; ".join(findings))
    body = {
        **core,
        "observed_at": utc_now(),
        "host_sha": host_sha,
        "container_image_digest": container_image_digest,
        "db_path": str(db_path),
        "content_digest": stable_digest(core),
        "outcome": "ok",
    }
    body["digest"] = _receipt_digest(body)
    return body


def check(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    db_path: Path = Path(DEFAULT_RUNTIME_DB),
    witness_path: Path | None = None,
) -> list[str]:
    """Replay a committed receipt against raw stores without writing."""

    witness_path = witness_path or _default_witness_path(db_path)
    findings: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"receipt missing: {receipt_path}"]
    except (OSError, json.JSONDecodeError) as exc:
        return [f"receipt unreadable: {type(exc).__name__}: {exc}"]
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]
    if receipt.get("digest") != _receipt_digest(receipt):
        findings.append("receipt digest mismatch")

    core, replay_findings = analyze(db_path, witness_path)
    findings.extend(replay_findings)
    if replay_findings:
        return findings
    if receipt.get("content_digest") != stable_digest(core):
        findings.append("receipt content_digest does not match raw-store replay")
    for key in CORE_KEYS:
        if receipt.get(key) != core.get(key):
            findings.append(f"receipt {key} does not match raw-store replay")
    return findings


def _needs_host(db_path: Path, witness_path: Path) -> dict[str, Any]:
    gaps = []
    if not db_path.exists():
        gaps.append("loop1_runtime_db_needs_host")
    if not witness_path.exists():
        gaps.append("loop1_witness_chain_needs_host")
    return {
        "schema": SCHEMA,
        "outcome": "needs_host",
        "chain_verified": False,
        "gaps": gaps,
        "db_path": str(db_path),
        "witness_path": str(witness_path),
    }


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="replay without writing")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--db", type=Path, default=Path(DEFAULT_RUNTIME_DB))
    parser.add_argument("--witness", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--host-sha", default="")
    parser.add_argument("--container-image-digest", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    witness_path = args.witness or _default_witness_path(args.db)
    if not args.db.exists() or not witness_path.exists():
        payload = _needs_host(args.db, witness_path)
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print("loop1_consumption_check: needs_host")
            for gap in payload["gaps"]:
                print(f"- {gap}")
        return 0

    if args.check:
        findings = check(args.out, db_path=args.db, witness_path=witness_path)
        if findings:
            if args.json:
                print(json.dumps({"outcome": "fail", "findings": findings}))
            else:
                print("loop1_consumption_check --check: FAIL")
                for finding in findings:
                    print(f"- {finding}")
            return 1
        if args.json:
            print(json.dumps({"outcome": "ok", "chain_verified": True}))
        else:
            print("loop1_consumption_check --check: OK")
        return 0

    try:
        receipt = build_receipt(
            db_path=args.db,
            witness_path=witness_path,
            host_sha=args.host_sha or _git_sha(),
            container_image_digest=(
                args.container_image_digest
                or os.environ.get("DHARMA_CONTAINER_IMAGE_DIGEST", "")
            ),
        )
    except ValueError as exc:
        print(f"loop1_consumption_check: FAIL: {exc}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True) if args.json else args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
