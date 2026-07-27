#!/usr/bin/env python3
"""WP-LC4 disjoint checker: validate receipt-grounded provider consumption.

Opens ``runtime.db`` read-only, reads ``delegation_runs.receipt_json``, and
validates the four Loop-1 closure properties P1..P4 against the canonical
``apply_receipt_consumption_ranking`` implementation. Emits a typed receipt under
``~/.dharma/loop_closure/loop1_consumption_receipt.json``.

With ``--check`` the checker replays the last committed receipt if one exists;
on a fresh host with no receipt (or no host runtime rows) it exits ``0`` with a
``needs_host`` typed gap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.models import ProviderType
from dharma_swarm.receipt_consumption import (
    MAX_RECEIPT_DEMOTIONS,
    PROCESS_BOOT_ID,
    RECEIPT_CONSUMPTION_WINDOW,
    apply_receipt_consumption_ranking,
)

RECEIPT_SCHEMA = "dharma.loop1_consumption_check.v1"
DEFAULT_DB = Path.home() / ".dharma" / "state" / "runtime.db"
DEFAULT_RECEIPT = Path.home() / ".dharma" / "loop_closure" / "loop1_consumption_receipt.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_chain() -> list[ProviderType]:
    return [
        ProviderType.ANTHROPIC,
        ProviderType.OPENAI,
        ProviderType.OPENROUTER,
        ProviderType.OLLAMA,
    ]


def _resolve_db_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env_path = os.environ.get("DGC_ROUTER_RECEIPT_DB")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB


def _host_sha() -> str:
    repo = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - host tooling may be absent
        return "unknown"


def _read_receipt_rows(db_path: Path, window: int = RECEIPT_CONSUMPTION_WINDOW) -> list[dict[str, Any]]:
    """Return recent parsed receipt_json rows from a read-only runtime.db."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return []
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='delegation_runs'"
        )
        if not cur.fetchone():
            return []
        rows = conn.execute(
            "SELECT receipt_json FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
            "ORDER BY started_at DESC, rowid DESC LIMIT ?",
            (max(1, int(window)),),
        ).fetchall()
    finally:
        conn.close()

    parsed: list[dict[str, Any]] = []
    for (raw,) in rows:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                parsed.append(obj)
        except json.JSONDecodeError:
            continue
    return parsed


def _row_count(db_path: Path) -> int:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return 0
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='delegation_runs'"
        )
        if not cur.fetchone():
            return 0
        row = conn.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _provider_type(raw: object) -> ProviderType | None:
    value = str(raw or "").strip().lower()
    return next((provider for provider in ProviderType if provider.value == value), None)


def _is_failing_receipt(receipt: dict[str, Any]) -> bool:
    status = str(receipt.get("status") or "").strip().lower()
    error_source = str(receipt.get("error_source") or "").strip().lower()
    if status == "ok" and error_source in {"", "none"}:
        return False
    return bool(str(receipt.get("trace_id") or "").strip())


def _producer_boot_id(receipt: dict[str, Any]) -> str:
    attributes = receipt.get("attributes") or {}
    if isinstance(attributes, dict):
        return str(attributes.get("boot_id") or "").strip()
    return ""


def _receipt_row(
    trace_id: str,
    provider: ProviderType,
    *,
    status: str = "error",
    error_source: str = "provider",
    boot_id: str = "producer-boot",
) -> dict[str, Any]:
    """Test helper: build a receipt dict for fixture generation."""
    return {
        "trace_id": trace_id,
        "provider": provider.value,
        "status": status,
        "error_source": error_source,
        "attributes": {"boot_id": boot_id},
    }


def _write_test_db(path: Path, rows: list[dict[str, Any]]) -> None:
    """Test helper: populate a synthetic runtime.db with delegation_runs rows.

    This is exported only for tests; the checker itself never writes to the host
    database.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS delegation_runs (
            started_at TEXT NOT NULL,
            receipt_json TEXT
        )
        """
    )
    conn.execute("DELETE FROM delegation_runs")
    for index, row in enumerate(rows):
        conn.execute(
            "INSERT INTO delegation_runs(started_at, receipt_json) VALUES (?, ?)",
            (f"2026-07-15T00:00:{index:02d}Z", json.dumps(row)),
        )
    conn.commit()
    conn.close()


def _ranking(
    db_path: Path,
    chain: list[ProviderType],
    consumer_boot_id: str,
) -> tuple[list[ProviderType], bool, Any]:
    """Call the canonical ranking function against a read-only database."""
    return apply_receipt_consumption_ranking(
        list(chain),
        db_path=db_path,
        boot_id=consumer_boot_id,
    )


def _p1_result(
    rows: list[dict[str, Any]],
    chain: list[ProviderType],
    reordered: list[ProviderType],
    applied: bool,
    evidence: Any,
) -> dict[str, Any]:
    """P1: consumed failing receipts demote their providers within the chain."""
    failing = [r for r in rows if _is_failing_receipt(r)]
    if not failing:
        return {
            "property": "P1",
            "ok": True,
            "triggered": False,
            "detail": "no failing receipt observed",
        }

    demoted = set(evidence.decision_delta.get("demoted_providers", []))
    reordered_values = [p.value for p in reordered]
    consumed_trace_ids = set(evidence.consumed_trace_ids)
    consumed_providers = {
        _provider_type(r.get("provider"))
        for r in failing
        if str(r.get("trace_id") or "") in consumed_trace_ids
    }
    consumed_providers.discard(None)

    ok = (
        applied
        and consumed_providers
        and consumed_providers.issubset(set(chain))
        and all(p.value in demoted for p in consumed_providers)
        and set(reordered_values) == set(p.value for p in chain)
        and len(reordered_values) == len(chain)
    )
    return {
        "property": "P1",
        "ok": ok,
        "triggered": True,
        "detail": (
            "consumed failing providers demoted"
            if ok
            else "consumed failing provider was not demoted"
        ),
        "consumed_trace_ids": list(consumed_trace_ids),
        "demoted_providers": list(demoted),
        "reordered_order": reordered_values,
    }


def _p2_result(
    rows: list[dict[str, Any]],
    chain: list[ProviderType],
    reordered: list[ProviderType],
    applied: bool,
    evidence: Any,
) -> dict[str, Any]:
    """P2: with no failing receipts, the default order is preserved."""
    failing = [r for r in rows if _is_failing_receipt(r)]
    if failing:
        return {
            "property": "P2",
            "ok": True,
            "triggered": False,
            "detail": "failing receipts present; P2 not observed",
        }

    reordered_values = [p.value for p in reordered]
    chain_values = [p.value for p in chain]
    ok = not applied and reordered_values == chain_values and evidence.consumed_trace_ids == ()
    return {
        "property": "P2",
        "ok": ok,
        "triggered": True,
        "detail": "no failing receipts keep default order" if ok else "default order was not preserved",
        "reordered_order": reordered_values,
    }


def _p3_result(
    rows: list[dict[str, Any]],
    reordered: list[ProviderType],
    applied: bool,
    evidence: Any,
    consumer_boot_id: str,
) -> dict[str, Any]:
    """P3: a failing receipt from a different boot_id is still consumed."""
    failing = [r for r in rows if _is_failing_receipt(r)]
    if not failing:
        return {
            "property": "P3",
            "ok": True,
            "triggered": False,
            "detail": "no failing receipts observed",
        }

    consumed = set(evidence.consumed_trace_ids)
    self_citation = [
        r
        for r in failing
        if _producer_boot_id(r) == consumer_boot_id
        and str(r.get("trace_id") or "") in consumed
    ]
    if self_citation:
        return {
            "property": "P3",
            "ok": False,
            "triggered": True,
            "detail": "self-citation spoof detected",
            "consumer_boot_id": consumer_boot_id,
            "self_citation_trace_ids": [str(r.get("trace_id")) for r in self_citation],
        }

    cross_boot = [r for r in failing if _producer_boot_id(r) not in ("", consumer_boot_id)]
    if not cross_boot:
        return {
            "property": "P3",
            "ok": True,
            "triggered": False,
            "detail": "no cross-boot failing receipt observed",
        }

    consumed_cross = [r for r in cross_boot if str(r.get("trace_id") or "") in consumed]
    ok = bool(consumed_cross) and applied
    detail = (
        f"cross-boot trace(s) consumed: {[r.get('trace_id') for r in consumed_cross]}"
        if ok
        else "cross-boot failing receipt was not consumed"
    )
    return {
        "property": "P3",
        "ok": ok,
        "triggered": True,
        "detail": detail,
        "consumer_boot_id": consumer_boot_id,
        "consumed_trace_ids": list(consumed),
        "cross_boot_trace_ids": [str(r.get("trace_id")) for r in consumed_cross],
    }


def _p4_result(
    rows: list[dict[str, Any]],
    chain: list[ProviderType],
    reordered: list[ProviderType],
    applied: bool,
    evidence: Any,
) -> dict[str, Any]:
    """P4: all providers failing still demotes at most MAX and excludes none."""
    failing = [r for r in rows if _is_failing_receipt(r)]
    failing_providers = {_provider_type(r.get("provider")) for r in failing}
    failing_providers.discard(None)
    chain_set = set(chain)
    if failing_providers != chain_set:
        return {
            "property": "P4",
            "ok": True,
            "triggered": False,
            "detail": "not all providers observed failing; P4 not observed",
        }

    demoted = evidence.decision_delta.get("demoted_providers", [])
    reordered_values = [p.value for p in reordered]
    ok = (
        applied
        and len(reordered) == len(chain)
        and set(reordered_values) == set(p.value for p in chain)
        and len(demoted) <= MAX_RECEIPT_DEMOTIONS
        and len(evidence.consumed_trace_ids) <= MAX_RECEIPT_DEMOTIONS
    )
    return {
        "property": "P4",
        "ok": ok,
        "triggered": True,
        "detail": f"all providers failing demotes at most {MAX_RECEIPT_DEMOTIONS} and excludes none",
        "demoted_count": len(demoted),
        "demoted_providers": demoted,
        "reordered_order": reordered_values,
    }


def _run(
    db_path: Path | None = None,
    *,
    consumer_boot_id: str = PROCESS_BOOT_ID,
) -> dict[str, Any]:
    """Read a runtime.db and validate P1..P4, returning a typed receipt."""
    path = _resolve_db_path(db_path)
    rows = _read_receipt_rows(path)

    if not rows:
        return _typed_gap(f"no receipt rows in {path}", path)

    chain = _default_chain()
    reordered, applied, evidence = _ranking(path, chain, consumer_boot_id)

    properties = [
        _p1_result(rows, chain, reordered, applied, evidence),
        _p2_result(rows, chain, reordered, applied, evidence),
        _p3_result(rows, reordered, applied, evidence, consumer_boot_id),
        _p4_result(rows, chain, reordered, applied, evidence),
    ]
    all_ok = all(p["ok"] for p in properties)

    consumed_trace_ids = list(evidence.consumed_trace_ids)
    producer_trace_id = consumed_trace_ids[0] if consumed_trace_ids else ""
    producer_boot_id = ""
    if producer_trace_id:
        for receipt in rows:
            if str(receipt.get("trace_id") or "") == producer_trace_id:
                producer_boot_id = _producer_boot_id(receipt)
                break

    content: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "outcome": "ok" if all_ok else "fail",
        "properties": properties,
        "window": RECEIPT_CONSUMPTION_WINDOW,
        "max_demotions": MAX_RECEIPT_DEMOTIONS,
        "consumed_trace_ids": consumed_trace_ids,
        "decision_delta": evidence.decision_delta,
        "producer_trace_id": producer_trace_id,
        "consumer_trace_id": uuid4().hex,
        "producer_boot_id": producer_boot_id,
        "consumer_boot_id": consumer_boot_id,
        "chain_verified": (
            set(p.value for p in reordered) == set(p.value for p in chain)
            and len(reordered) == len(chain)
        ),
        "host_sha": _host_sha(),
        "container_image_digest": os.environ.get("DHARMA_CONTAINER_IMAGE_DIGEST", "unknown"),
        "db_path": str(path.resolve()),
        "delegation_runs_row_count": _row_count(path),
    }
    content["content_digest"] = _digest(content)
    content["observed_at"] = _now()
    return content


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(payload: Mapping[str, Any]) -> str:
    """Canonical digest over receipt content, excluding volatile fields."""
    normalized = {
        k: v
        for k, v in payload.items()
        if k not in {"digest", "content_digest", "observed_at", "producer_trace_id", "consumer_trace_id"}
    }
    return hashlib.sha256(_stable_json(normalized).encode("utf-8")).hexdigest()


def _write_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _typed_gap(reason: str, db_path: Path | None = None) -> dict[str, Any]:
    """Emit a typed needs_host receipt when host runtime stores are absent."""
    path = _resolve_db_path(db_path)
    content: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "observed_at": _now(),
        "outcome": "needs_host",
        "reason": reason,
        "host_sha": _host_sha(),
        "container_image_digest": os.environ.get("DHARMA_CONTAINER_IMAGE_DIGEST", "unknown"),
        "db_path": str(path.resolve()),
        "delegation_runs_row_count": 0,
    }
    content["content_digest"] = _digest(content)
    return content


def _verify_receipt_digest(prior: dict[str, Any], current: dict[str, Any]) -> bool:
    """Return True when ``current`` reproduces the stable content of ``prior``."""
    excluded = {"digest", "content_digest", "observed_at", "producer_trace_id", "consumer_trace_id"}
    prior_stable = {k: v for k, v in prior.items() if k not in excluded}
    current_stable = {k: v for k, v in current.items() if k not in excluded}
    prior_digest = prior.get("content_digest")
    prior_recomputed = _digest(prior_stable)
    if prior_digest != prior_recomputed:
        return False
    current_recomputed = _digest(current_stable)
    return prior_recomputed == current_recomputed


def _receipts_equivalent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Backwards-compatible alias used by tests; delegates to digest verification."""
    return _verify_receipt_digest(a, b)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="replay the committed receipt")
    parser.add_argument("--db", type=Path, default=None, help="runtime.db to read")
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_RECEIPT,
        help="path to the receipt to write or replay",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the receipt to stdout instead of writing it",
    )
    args = parser.parse_args(argv)

    db_path = args.db or (
        Path(os.environ["DGC_ROUTER_RECEIPT_DB"])
        if os.environ.get("DGC_ROUTER_RECEIPT_DB")
        else None
    )

    if args.check:
        prior = _read_receipt(args.receipt)
        if prior is None:
            gap = _typed_gap(f"no committed receipt at {args.receipt}", db_path)
            print(json.dumps(gap, indent=2, sort_keys=True))
            return 0

        # Replay using the stored consumer boot_id so process-identity fields are stable.
        replay_boot_id = prior.get("consumer_boot_id") or PROCESS_BOOT_ID
        current = _run(db_path, consumer_boot_id=replay_boot_id)
        if _verify_receipt_digest(prior, current):
            print(json.dumps(current, indent=2, sort_keys=True))
            return 0

        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "observed_at": _now(),
                    "outcome": "fail",
                    "reason": "replayed P1..P4 do not match committed receipt content digest",
                    "prior_digest": prior.get("content_digest"),
                    "current": current,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    receipt = _run(db_path)
    if args.stdout:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        _write_receipt(receipt, args.receipt)
        print(args.receipt)
    return 0 if receipt["outcome"] in ("ok", "needs_host") else 1


def _run_p1_p4(db_path: Path | None = None) -> dict[str, Any]:
    """Backwards-compatible alias used by tests; returns a full receipt."""
    return _run(db_path)


def p1_failing_receipt_reorders(
    db_path: Path,
    chain: list[ProviderType],
    consumer_boot_id: str = PROCESS_BOOT_ID,
) -> dict[str, Any]:
    """P1: a failing provider receipt is demoted within the chain."""
    rows = _read_receipt_rows(db_path)
    reordered, applied, evidence = _ranking(db_path, chain, consumer_boot_id)
    return _p1_result(rows, chain, reordered, applied, evidence)


def p2_no_failures_keep_default(
    db_path: Path,
    chain: list[ProviderType],
    consumer_boot_id: str = PROCESS_BOOT_ID,
) -> dict[str, Any]:
    """P2: with no failing receipts, the default order is preserved."""
    rows = _read_receipt_rows(db_path)
    reordered, applied, evidence = _ranking(db_path, chain, consumer_boot_id)
    return _p2_result(rows, chain, reordered, applied, evidence)


def p3_cross_boot_consumes_prior(
    db_path: Path,
    chain: list[ProviderType],
    consumer_boot_id: str = PROCESS_BOOT_ID,
) -> dict[str, Any]:
    """P3: a failing receipt from a different boot_id is still consumed."""
    rows = _read_receipt_rows(db_path)
    reordered, applied, evidence = _ranking(db_path, chain, consumer_boot_id)
    return _p3_result(rows, reordered, applied, evidence, consumer_boot_id)


def p4_poisoning_bound(
    db_path: Path,
    chain: list[ProviderType],
    consumer_boot_id: str = PROCESS_BOOT_ID,
) -> dict[str, Any]:
    """P4: all providers failing still demotes at most MAX and excludes none."""
    rows = _read_receipt_rows(db_path)
    reordered, applied, evidence = _ranking(db_path, chain, consumer_boot_id)
    return _p4_result(rows, chain, reordered, applied, evidence)


if __name__ == "__main__":
    raise SystemExit(main())
