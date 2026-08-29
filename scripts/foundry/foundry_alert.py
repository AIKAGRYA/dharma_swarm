#!/usr/bin/env python3
"""Append a content-sealed OnFailure alert without reading secrets."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

_UNIT = re.compile(r"[A-Za-z0-9_.@:-]{1,160}")
_CATEGORY = re.compile(r"[a-z0-9_.:-]{1,80}")
_FINGERPRINT = re.compile(r"(?:sha256:)?[0-9a-f]{64}")
_MAX_ALERT_FILES = 4096


def _safe_state_root(raw: str) -> Path:
    supplied = Path(raw)
    if not supplied.is_absolute() or ".." in supplied.parts:
        raise ValueError("state root must be an absolute canonical path")
    cursor = Path(supplied.anchor)
    for part in supplied.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("state root may not traverse symlinks")
    return supplied.resolve(strict=False)


def _parse_time(raw: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--category", default="service_failure")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--fingerprint", default="")
    args = parser.parse_args(argv)
    if not _UNIT.fullmatch(args.unit):
        parser.error("invalid unit name")
    if not _CATEGORY.fullmatch(args.category):
        parser.error("invalid alert category")
    if args.fingerprint and not _FINGERPRINT.fullmatch(args.fingerprint):
        parser.error("invalid alert fingerprint")
    try:
        root = _safe_state_root(args.state_root)
    except ValueError as exc:
        parser.error(str(exc))
    if not root.is_dir() or root.is_symlink():
        parser.error("state root must already exist as a non-symlink directory")
    previous_umask = os.umask(0o077)
    try:
        alerts = root / "alerts"
        alerts.mkdir(mode=0o700, exist_ok=True)
        root_directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(root_directory)
        finally:
            os.close(root_directory)
        lock_path = root / ".alert-writer.lock"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            now = datetime.now(timezone.utc)
            body = {
                "schema_version": "foundry_failure_alert.v1",
                "unit": args.unit,
                "category": args.category,
                "observed_exit_code": args.exit_code,
                "fingerprint": args.fingerprint,
                "observed_at": now.isoformat(),
                "service_state_sha256": "",
                "service_state_read_error": "",
            }
            service_state = root / "service_state.json"
            if service_state.is_file():
                try:
                    body["service_state_sha256"] = hashlib.sha256(
                        service_state.read_bytes()
                    ).hexdigest()
                except OSError as exc:
                    body["service_state_read_error"] = type(exc).__name__
            if not body["fingerprint"]:
                body["fingerprint"] = "sha256:" + hashlib.sha256(json.dumps({
                    "unit": body["unit"],
                    "category": body["category"],
                    "observed_exit_code": body["observed_exit_code"],
                    "service_state_sha256": body["service_state_sha256"],
                    "service_state_read_error": body["service_state_read_error"],
                }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                    "utf-8"
                )).hexdigest()
            existing = sorted(islice(alerts.glob("*.json"), _MAX_ALERT_FILES + 1))
            # Identical health findings are limited to one per hour; identical
            # process failures are limited to one per five minutes.  Novel
            # alerts fail closed once the hard cap is reached instead of
            # falsely claiming that evidence was recorded.
            dedupe_window = timedelta(
                seconds=(
                    3600
                    if args.category.startswith(("progress_health", "status_"))
                    else 300
                )
            )
            for prior_path in existing:
                try:
                    prior = json.loads(prior_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError):
                    continue
                prior_time = _parse_time(prior.get("observed_at"))
                if (
                    prior.get("category") == body["category"]
                    and prior.get("fingerprint") == body["fingerprint"]
                    and prior_time is not None
                    and now - prior_time <= dedupe_window
                ):
                    print(json.dumps({
                        "foundry_alert_deduplicated": True,
                        "unit": body["unit"],
                        "category": body["category"],
                        "fingerprint": body["fingerprint"],
                    }, sort_keys=True, allow_nan=False))
                    return 0
            if len(existing) >= _MAX_ALERT_FILES:
                print(
                    "Foundry alert receipt cap reached; novel alert was not recorded",
                    file=sys.stderr,
                )
                return 3
            encoded_body = json.dumps(
                body, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            digest = hashlib.sha256(encoded_body.encode("utf-8")).hexdigest()
            payload = {**body, "digest": "sha256:" + digest}
            path = alerts / f"{body['observed_at'].replace(':', '')}__{digest[:16]}.json"
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(alerts, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            print(json.dumps({
                "foundry_alert_recorded": True,
                "unit": body["unit"],
                "category": body["category"],
                "fingerprint": body["fingerprint"],
                "receipt": path.name,
                "digest": payload["digest"],
            }, sort_keys=True, allow_nan=False))
    finally:
        os.umask(previous_umask)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
