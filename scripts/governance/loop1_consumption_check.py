#!/usr/bin/env python3
"""Verify Loop-1 receipt consumption from disjoint, read-only stores.

The checker reads producer receipts from runtime.db and a later consumer
decision from the router JSONL audit.  It deliberately does not invoke the
production ranking implementation.  A closure receipt is emitted only when
the two raw stores independently prove the cited traces, routing delta,
cross-boot boundary, and provider-chain integrity.

Hosts without the complete persisted witness return a digest-bound
``needs_host`` receipt and exit successfully.  Present but contradictory
evidence returns ``fail`` and exits non-zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "dharma.loop1_consumption_check.v1"
RECEIPT_CONSUMPTION_WINDOW = 50
ROUTING_AUDIT_WINDOW = 1_000
MAX_RECEIPT_DEMOTIONS = 2
DEFAULT_PROVIDER_ORDER = ["anthropic", "openai", "openrouter", "ollama"]

DEFAULT_DB = Path.home() / ".dharma" / "state" / "runtime.db"
DEFAULT_ROUTING_AUDIT = (
    Path.home() / ".dharma" / "logs" / "router" / "routing_decisions.jsonl"
)
DEFAULT_RECEIPT = (
    Path.home() / ".dharma" / "loop_closure" / "loop1_consumption_receipt.json"
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_EXCLUDED_FIELDS = frozenset({"content_digest", "observed_at"})
_AUDIT_REQUIRED_FIELDS = (
    "timestamp",
    "consumer_trace_id",
    "consumer_boot_id",
    "consumed_trace_ids",
    "decision_delta",
    "chain",
)


class EvidenceUnavailableError(Exception):
    """Required host evidence is absent, incomplete, or unreadable."""


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(payload: Mapping[str, Any]) -> str:
    """Digest every receipt field except freshness and the digest itself."""
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _DIGEST_EXCLUDED_FIELDS
    }
    return hashlib.sha256(_stable_json(stable).encode("utf-8")).hexdigest()


def _valid_content_digest(payload: Mapping[str, Any]) -> bool:
    claimed = payload.get("content_digest")
    return isinstance(claimed, str) and claimed == _digest(payload)


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["observed_at"] = _now()
    result["content_digest"] = _digest(result)
    return result


def _resolve_db_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    configured = os.environ.get("DGC_ROUTER_RECEIPT_DB", "").strip()
    return Path(configured) if configured else DEFAULT_DB


def _resolve_routing_audit_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    configured = os.environ.get("DGC_ROUTER_AUDIT_LOG", "").strip()
    return Path(configured) if configured else DEFAULT_ROUTING_AUDIT


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
    except (OSError, subprocess.SubprocessError):
        return ""
    candidate = result.stdout.strip().lower()
    return candidate if result.returncode == 0 and _SHA_RE.fullmatch(candidate) else ""


def _host_binding() -> tuple[dict[str, str], list[str]]:
    host_sha = _host_sha()
    image_digest = os.environ.get("DHARMA_CONTAINER_IMAGE_DIGEST", "").strip().lower()
    image_provenance = os.environ.get(
        "DHARMA_CONTAINER_IMAGE_PROVENANCE", ""
    ).strip()
    missing: list[str] = []
    if not host_sha:
        missing.append("host_sha")
    if not _IMAGE_DIGEST_RE.fullmatch(image_digest):
        missing.append("container_image_digest")
    if not image_provenance:
        missing.append("container_image_provenance")
    return (
        {
            "host_sha": host_sha,
            "container_image_digest": image_digest,
            "container_image_provenance": image_provenance,
        },
        missing,
    )


def _empty_receipt(
    db_path: Path,
    routing_audit_path: Path,
    host: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "outcome": "needs_host",
        "reason": "",
        "missing_evidence": [],
        "properties": [],
        "window": RECEIPT_CONSUMPTION_WINDOW,
        "max_demotions": MAX_RECEIPT_DEMOTIONS,
        "authorized_provider_order": list(DEFAULT_PROVIDER_ORDER),
        "producer_trace_id": "",
        "producer_trace_ids": [],
        "consumer_trace_id": "",
        "consumed_trace_ids": [],
        "decision_delta": {},
        "producer_boot_id": "",
        "producer_boot_ids": {},
        "consumer_boot_id": "",
        "chain_verified": False,
        "host_sha": host["host_sha"],
        "container_image_digest": host["container_image_digest"],
        "container_image_provenance": host["container_image_provenance"],
        "db_path": str(db_path.resolve()),
        "routing_audit_path": str(routing_audit_path.resolve()),
        "delegation_runs_row_count": 0,
        "receipt_rows_examined": 0,
        "routing_audit_rows_examined": 0,
        "routing_audit_line": 0,
        "routing_record_digest": "",
    }


def _typed_gap(
    reason: str,
    db_path: Path,
    routing_audit_path: Path,
    *,
    missing: Sequence[str],
    host: Mapping[str, str],
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = _empty_receipt(db_path, routing_audit_path, host)
    if evidence:
        receipt.update(evidence)
    receipt.update(
        outcome="needs_host",
        reason=reason,
        missing_evidence=sorted(set(missing)),
    )
    return _finalize(receipt)


def _open_readonly_db(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise EvidenceUnavailableError(f"runtime database is absent: {path}")
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection
    except sqlite3.Error as exc:
        raise EvidenceUnavailableError(f"runtime database is unreadable: {exc}") from exc


def _read_db_snapshot(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read count and bounded producer rows from one read-only snapshot."""
    connection = _open_readonly_db(path)
    try:
        connection.execute("BEGIN")
        table = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'delegation_runs'"
        ).fetchone()
        if table is None:
            raise EvidenceUnavailableError("delegation_runs table is absent")
        count_row = connection.execute(
            "SELECT COUNT(*) FROM delegation_runs"
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        raw_rows = connection.execute(
            "SELECT started_at, receipt_json FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
            "ORDER BY started_at DESC, rowid DESC LIMIT ?",
            (RECEIPT_CONSUMPTION_WINDOW,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise EvidenceUnavailableError(f"cannot read delegation receipts: {exc}") from exc
    finally:
        connection.close()

    rows: list[dict[str, Any]] = []
    for started_at, raw in raw_rows:
        try:
            receipt = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise EvidenceUnavailableError(
                f"selected receipt_json is malformed: {type(exc).__name__}"
            ) from exc
        if not isinstance(receipt, dict):
            raise EvidenceUnavailableError("selected receipt_json is not an object")
        rows.append({"started_at": str(started_at or "").strip(), "receipt": receipt})
    if not rows:
        raise EvidenceUnavailableError("no non-empty receipt rows are available")
    return rows, total


def _as_string_list(
    value: object,
    field: str,
    *,
    normalize: bool = False,
) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a list of non-empty strings")
    stripped = [item.strip() for item in value]
    return [item.lower() for item in stripped] if normalize else stripped


def _audit_value(record: Mapping[str, Any], key: str) -> Any:
    nested = record.get("receipt_consumption")
    if isinstance(nested, Mapping) and key in nested:
        return nested[key]
    return record.get(key)


def _looks_like_consumption(record: Mapping[str, Any]) -> bool:
    reasons = record.get("reasons")
    if isinstance(reasons, list) and "receipt_consumption_applied" in reasons:
        return True
    nested = record.get("receipt_consumption")
    if isinstance(nested, Mapping) and nested:
        return True
    return any(key in record for key in _AUDIT_REQUIRED_FIELDS[1:5])


def _read_audit_record(path: Path) -> tuple[dict[str, Any], int, int]:
    if not path.is_file():
        raise EvidenceUnavailableError(f"router audit is absent: {path}")
    recent: deque[tuple[int, str]] = deque(maxlen=ROUTING_AUDIT_WINDOW)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.strip():
                    recent.append((line_number, line))
    except (OSError, UnicodeError) as exc:
        raise EvidenceUnavailableError(f"router audit is unreadable: {exc}") from exc
    if not recent:
        raise EvidenceUnavailableError("router audit has no records")

    parsed: list[tuple[int, dict[str, Any]]] = []
    for line_number, raw in recent:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvidenceUnavailableError(
                f"router audit line {line_number} is malformed"
            ) from exc
        if not isinstance(value, dict):
            raise EvidenceUnavailableError(
                f"router audit line {line_number} is not an object"
            )
        parsed.append((line_number, value))

    newest_incomplete: tuple[int, list[str]] | None = None
    for line_number, record in reversed(parsed):
        if not _looks_like_consumption(record):
            continue
        missing = [
            field
            for field in _AUDIT_REQUIRED_FIELDS
            if _audit_value(record, field) in (None, "", [])
        ]
        reasons = record.get("reasons")
        if not isinstance(reasons, list) or "receipt_consumption_applied" not in reasons:
            missing.append("reasons.receipt_consumption_applied")
        if missing:
            if newest_incomplete is None:
                newest_incomplete = (line_number, missing)
            continue
        return record, line_number, len(parsed)

    if newest_incomplete is not None:
        line_number, missing = newest_incomplete
        fields = ", ".join(sorted(set(missing)))
        raise EvidenceUnavailableError(
            f"latest consumption audit evidence at line {line_number} is incomplete: {fields}"
        )
    raise EvidenceUnavailableError("router audit has no persisted consumption evidence")


def _parse_timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_failing(receipt: Mapping[str, Any]) -> bool:
    status = str(receipt.get("status") or "").strip().lower()
    error_source = str(receipt.get("error_source") or "").strip().lower()
    return not (status == "ok" and error_source in {"", "none"})


def _producer_boot_id(receipt: Mapping[str, Any]) -> str:
    attributes = receipt.get("attributes")
    if not isinstance(attributes, Mapping):
        return ""
    return str(attributes.get("boot_id") or "").strip()


def _expected_from_raw(
    rows: Sequence[Mapping[str, Any]],
    default_order: Sequence[str],
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    failures: dict[str, dict[str, Any]] = {}
    for row in rows:
        receipt = row["receipt"]
        provider = str(receipt.get("provider") or "").strip().lower()
        if provider not in default_order or provider in failures or not _is_failing(receipt):
            continue
        trace_id = str(receipt.get("trace_id") or "").strip()
        if not trace_id:
            raise EvidenceUnavailableError(
                f"failing {provider} producer receipt is missing trace_id"
            )
        failures[provider] = {
            "trace_id": trace_id,
            "boot_id": _producer_boot_id(receipt),
            "started_at": str(row["started_at"]),
        }

    demoted = [provider for provider in default_order if provider in failures][
        :MAX_RECEIPT_DEMOTIONS
    ]
    if not demoted:
        raise EvidenceUnavailableError("no failing producer receipts are available")
    consumed = [failures[provider]["trace_id"] for provider in demoted]
    return demoted, consumed, failures


def _normalize_audit(record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        consumed = _as_string_list(
            _audit_value(record, "consumed_trace_ids"), "consumed_trace_ids"
        )
        chain = _as_string_list(
            _audit_value(record, "chain"), "chain", normalize=True
        )
        delta_raw = _audit_value(record, "decision_delta")
        if not isinstance(delta_raw, Mapping):
            raise ValueError("decision_delta must be an object")
        default_order = _as_string_list(
            delta_raw.get("default_order"),
            "decision_delta.default_order",
            normalize=True,
        )
        reordered_order = _as_string_list(
            delta_raw.get("reordered_order"),
            "decision_delta.reordered_order",
            normalize=True,
        )
        demoted = _as_string_list(
            delta_raw.get("demoted_providers"),
            "decision_delta.demoted_providers",
            normalize=True,
        )
    except ValueError as exc:
        raise EvidenceUnavailableError(f"router audit evidence is malformed: {exc}") from exc

    return {
        "timestamp": str(_audit_value(record, "timestamp") or "").strip(),
        "consumer_trace_id": str(
            _audit_value(record, "consumer_trace_id") or ""
        ).strip(),
        "consumer_boot_id": str(
            _audit_value(record, "consumer_boot_id") or ""
        ).strip(),
        "consumed_trace_ids": consumed,
        "decision_delta": {
            "default_order": default_order,
            "reordered_order": reordered_order,
            "demoted_providers": demoted,
        },
        "chain": chain,
    }


def _evaluate(
    rows: Sequence[Mapping[str, Any]],
    audit_record: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit = _normalize_audit(audit_record)
    delta = audit["decision_delta"]
    default_order = delta["default_order"]
    reordered_order = delta["reordered_order"]
    demoted = delta["demoted_providers"]
    consumed = audit["consumed_trace_ids"]

    expected_demoted, expected_consumed, failures = _expected_from_raw(
        rows, default_order
    )
    expected_reordered = [
        provider for provider in default_order if provider not in expected_demoted
    ] + expected_demoted

    raw_trace_counts = Counter(
        str(row["receipt"].get("trace_id") or "").strip()
        for row in rows
        if str(row["receipt"].get("trace_id") or "").strip()
    )
    producer_by_trace = {
        value["trace_id"]: value for value in failures.values()
    }
    cited_producers = [producer_by_trace.get(trace_id) for trace_id in consumed]
    producer_present = all(item is not None for item in cited_producers)
    producer_unique = (
        len(consumed) == len(set(consumed))
        and all(raw_trace_counts[trace_id] == 1 for trace_id in consumed)
    )
    producer_failing = producer_present and all(
        trace_id in expected_consumed for trace_id in consumed
    )

    consumer_timestamp = _parse_timestamp(audit["timestamp"])
    producer_timestamps = [
        _parse_timestamp(item["started_at"])
        for item in cited_producers
        if item is not None
    ]
    timestamps_complete = (
        consumer_timestamp is not None
        and len(producer_timestamps) == len(consumed)
        and all(value is not None for value in producer_timestamps)
    )
    consumer_is_later = bool(
        timestamps_complete
        and all(consumer_timestamp > value for value in producer_timestamps if value)
    )
    consumer_trace_distinct = (
        bool(audit["consumer_trace_id"])
        and audit["consumer_trace_id"] not in set(consumed)
    )

    baseline_exact = default_order == DEFAULT_PROVIDER_ORDER
    same_members = (
        baseline_exact
        and len(default_order) == len(reordered_order) == len(audit["chain"])
        and len(default_order) == len(set(default_order))
        and set(default_order) == set(reordered_order) == set(audit["chain"])
    )
    bounded = (
        0 < len(demoted) <= MAX_RECEIPT_DEMOTIONS
        and len(consumed) == len(demoted)
        and len(demoted) == len(set(demoted))
    )
    delta_exact = (
        demoted == expected_demoted
        and consumed == expected_consumed
        and reordered_order == expected_reordered
    )
    persisted_chain_exact = audit["chain"] == reordered_order

    producer_boot_ids = {
        trace_id: (producer_by_trace.get(trace_id) or {}).get("boot_id", "")
        for trace_id in consumed
    }
    if producer_present and not all(producer_boot_ids.values()):
        raise EvidenceUnavailableError("cited producer receipt is missing boot_id")
    if producer_present and not timestamps_complete:
        raise EvidenceUnavailableError(
            "producer or consumer timestamp is missing or malformed"
        )
    boots_complete = bool(audit["consumer_boot_id"]) and all(
        producer_boot_ids.values()
    )
    cross_boot = boots_complete and all(
        boot_id != audit["consumer_boot_id"]
        for boot_id in producer_boot_ids.values()
    )

    properties = [
        {
            "property": "P1",
            "ok": producer_present and producer_unique and producer_failing,
            "detail": "cited trace IDs resolve uniquely to failing raw producer receipts",
        },
        {
            "property": "P2",
            "ok": consumer_trace_distinct and consumer_is_later,
            "detail": "persisted consumer decision cites exact earlier producer traces",
        },
        {
            "property": "P3",
            "ok": same_members and bounded and delta_exact and persisted_chain_exact,
            "detail": "persisted decision delta matches independent bounded recomputation",
        },
        {
            "property": "P4",
            "ok": boots_complete and cross_boot and same_members and persisted_chain_exact,
            "detail": "producer and consumer boot IDs differ and provider chain is intact",
        },
    ]
    evidence = {
        "producer_trace_id": consumed[0] if consumed else "",
        "producer_trace_ids": list(consumed),
        "consumer_trace_id": audit["consumer_trace_id"],
        "consumed_trace_ids": list(consumed),
        "decision_delta": delta,
        "producer_boot_id": producer_boot_ids.get(consumed[0], "") if consumed else "",
        "producer_boot_ids": producer_boot_ids,
        "consumer_boot_id": audit["consumer_boot_id"],
        "chain_verified": bool(same_members and persisted_chain_exact),
    }
    return properties, evidence


def _run(
    db_path: Path | None = None,
    routing_audit_path: Path | None = None,
) -> dict[str, Any]:
    db = _resolve_db_path(db_path)
    audit_path = _resolve_routing_audit_path(routing_audit_path)
    host, host_missing = _host_binding()
    base = _empty_receipt(db, audit_path, host)

    try:
        rows, row_count = _read_db_snapshot(db)
    except EvidenceUnavailableError as exc:
        return _typed_gap(
            str(exc),
            db,
            audit_path,
            missing=[*host_missing, "producer_receipts"],
            host=host,
        )
    base.update(
        delegation_runs_row_count=row_count,
        receipt_rows_examined=len(rows),
    )

    try:
        audit_record, audit_line, audit_rows_examined = _read_audit_record(audit_path)
    except EvidenceUnavailableError as exc:
        return _typed_gap(
            str(exc),
            db,
            audit_path,
            missing=[*host_missing, "consumer_routing_evidence"],
            host=host,
            evidence=base,
        )
    base.update(
        routing_audit_line=audit_line,
        routing_audit_rows_examined=audit_rows_examined,
        routing_record_digest=hashlib.sha256(
            _stable_json(audit_record).encode("utf-8")
        ).hexdigest(),
    )

    try:
        properties, evidence = _evaluate(rows, audit_record)
    except EvidenceUnavailableError as exc:
        return _typed_gap(
            str(exc),
            db,
            audit_path,
            missing=[*host_missing, "complete_chain_evidence"],
            host=host,
            evidence=base,
        )

    base.update(evidence)
    base["properties"] = properties
    properties_ok = all(item["ok"] for item in properties)
    if not properties_ok:
        base.update(
            outcome="fail",
            reason="persisted consumer evidence contradicts raw producer state",
            missing_evidence=[],
        )
    elif host_missing:
        base.update(
            outcome="needs_host",
            reason="host or container provenance is incomplete",
            missing_evidence=sorted(host_missing),
        )
    else:
        base.update(outcome="ok", reason="", missing_evidence=[])
    return _finalize(base)


def _write_receipt(receipt: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _verify_receipt_digest(prior: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    if not _valid_content_digest(prior) or not _valid_content_digest(current):
        return False
    prior_stable = {
        key: value
        for key, value in prior.items()
        if key not in _DIGEST_EXCLUDED_FIELDS
    }
    current_stable = {
        key: value
        for key, value in current.items()
        if key not in _DIGEST_EXCLUDED_FIELDS
    }
    return prior_stable == current_stable


def _receipts_equivalent(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return _verify_receipt_digest(a, b)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="replay a saved receipt")
    parser.add_argument("--db", type=Path, default=None, help="runtime.db to read")
    parser.add_argument(
        "--routing-audit",
        type=Path,
        default=None,
        help="router routing_decisions.jsonl to read",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_RECEIPT,
        help="receipt path to write or replay",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the generated receipt instead of writing it",
    )
    args = parser.parse_args(argv)

    db = _resolve_db_path(args.db)
    audit = _resolve_routing_audit_path(args.routing_audit)
    if args.check:
        prior = _read_receipt(args.receipt)
        if prior is None:
            host, host_missing = _host_binding()
            gap = _typed_gap(
                f"no saved receipt at {args.receipt}",
                db,
                audit,
                missing=[*host_missing, "saved_receipt"],
                host=host,
            )
            print(json.dumps(gap, indent=2, sort_keys=True))
            return 0
        current = _run(db, audit)
        if _verify_receipt_digest(prior, current):
            print(json.dumps(current, indent=2, sort_keys=True))
            return 0
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "observed_at": _now(),
                    "outcome": "fail",
                    "reason": "saved receipt digest is invalid or replay evidence diverged",
                    "prior_digest": prior.get("content_digest"),
                    "current": current,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    receipt = _run(db, audit)
    if args.stdout:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        _write_receipt(receipt, args.receipt)
        print(args.receipt)
    return 1 if receipt["outcome"] == "fail" else 0


def _default_chain() -> list[str]:
    """Return a copy of the documented provider order for fixture authors."""
    return list(DEFAULT_PROVIDER_ORDER)


def _run_p1_p4(
    db_path: Path | None = None,
    routing_audit_path: Path | None = None,
) -> dict[str, Any]:
    """Compatibility alias returning the complete P1..P4 receipt."""
    return _run(db_path, routing_audit_path)


if __name__ == "__main__":
    raise SystemExit(main())
