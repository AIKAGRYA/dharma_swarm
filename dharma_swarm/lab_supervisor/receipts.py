"""Append-only, hash-chained receipts for supervisor ticks."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA = "dharma.lab_supervisor.tick_receipt.v1"


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def receipt_hash(payload: dict[str, Any]) -> str:
    candidate = dict(payload)
    candidate.pop("record_hash", None)
    return "sha256:" + hashlib.sha256(canonical_json(candidate).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainStatus:
    valid: bool
    count: int
    last_hash: str
    errors: tuple[str, ...] = ()


class ReceiptChain:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._cache_key: tuple[int, int, int] | None = None
        self._cache_status: ChainStatus | None = None
        self._cache_latches: dict[str, list[str]] | None = None

    def _stat_key(self) -> tuple[int, int, int] | None:
        try:
            stat = self.path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError:
            return (-1, -1, -1)
        return (int(stat.st_ino), int(stat.st_size), int(stat.st_mtime_ns))

    def _scan(self) -> tuple[ChainStatus, dict[str, list[str]]]:
        """Stream-verify once per unchanged file and rebuild irreversible latches.

        A five-minute service must not load or reparse its complete multi-year
        history several times per tick.  The stat-bound cache is invalidated on
        append, while strict JSONL parsing still rejects blank, truncated, and
        non-object rows fail closed.
        """

        key_before = self._stat_key()
        if (
            key_before == self._cache_key
            and self._cache_status is not None
            and self._cache_latches is not None
        ):
            return self._cache_status, {
                name: list(reasons) for name, reasons in self._cache_latches.items()
            }
        if key_before is None:
            status = ChainStatus(True, 0, "")
            self._cache_key = None
            self._cache_status = status
            self._cache_latches = {}
            return status, {}
        if self.path.is_symlink() or not self.path.is_file():
            return ChainStatus(False, 0, "", ("receipt path is not a regular file",)), {}

        previous = ""
        errors: list[str] = []
        latched: dict[str, list[str]] = {}
        count = 0
        try:
            with self.path.open("rb") as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    count = line_number
                    if not raw_line.endswith(b"\n"):
                        errors.append(f"line {line_number}: truncated row")
                    if not raw_line.strip():
                        errors.append(f"line {line_number}: blank row")
                        continue
                    try:
                        row = json.loads(raw_line)
                    except (UnicodeError, json.JSONDecodeError) as exc:
                        errors.append(f"line {line_number}: invalid JSON ({type(exc).__name__})")
                        continue
                    if not isinstance(row, dict):
                        errors.append(f"line {line_number}: receipt is not an object")
                        continue
                    if row.get("schema") != RECEIPT_SCHEMA:
                        errors.append(f"row {line_number}: schema mismatch")
                    if row.get("sequence") != line_number:
                        errors.append(f"row {line_number}: sequence mismatch")
                    if row.get("previous_hash", "") != previous:
                        errors.append(f"row {line_number}: previous hash mismatch")
                    expected = receipt_hash(row)
                    if row.get("record_hash") != expected:
                        errors.append(f"row {line_number}: record hash mismatch")
                    previous = str(row.get("record_hash") or "")
                    assessments = row.get("assessments", [])
                    if not isinstance(assessments, list):
                        errors.append(f"row {line_number}: assessments are not a list")
                        assessments = []
                    for assessment in assessments:
                        if not isinstance(assessment, dict):
                            errors.append(
                                f"row {line_number}: assessment is not an object"
                            )
                            continue
                        if (
                            assessment.get("state") != "Halted"
                            and not assessment.get("halt_latched")
                        ):
                            continue
                        name = str(assessment.get("lab") or "")
                        if not name:
                            errors.append(f"row {line_number}: halted assessment has no lab")
                            continue
                        reasons_raw = assessment.get("reasons", [])
                        if not isinstance(reasons_raw, list):
                            errors.append(
                                f"row {line_number}: halted reasons are not a list"
                            )
                            continue
                        latched.setdefault(name, []).extend(
                            str(value) for value in reasons_raw
                        )
        except (OSError, UnicodeError) as exc:
            errors.append(f"receipt chain unreadable:{type(exc).__name__}")

        key_after = self._stat_key()
        if key_after != key_before:
            errors.append("receipt file changed during verification")
        status = ChainStatus(not errors, count, previous, tuple(errors))
        normalized = {
            name: sorted(set(reasons)) for name, reasons in latched.items()
        }
        if key_after == key_before:
            self._cache_key = key_after
            self._cache_status = status
            self._cache_latches = normalized
        return status, {name: list(reasons) for name, reasons in normalized.items()}

    def verify(self) -> ChainStatus:
        return self._scan()[0]

    def append(self, payload: dict[str, Any]) -> str:
        status = self.verify()
        if not status.valid:
            raise RuntimeError(f"receipt chain invalid: {status.errors}")
        row = {
            "schema": RECEIPT_SCHEMA,
            "sequence": status.count + 1,
            "previous_hash": status.last_hash,
            **payload,
        }
        row["record_hash"] = receipt_hash(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._cache_key = None
        self._cache_status = None
        self._cache_latches = None
        return str(row["record_hash"])

    def latched_labs(self) -> dict[str, list[str]]:
        """Rebuild irreversible halt latches from retained evidence."""

        status, latched = self._scan()
        return latched if status.valid else {}
