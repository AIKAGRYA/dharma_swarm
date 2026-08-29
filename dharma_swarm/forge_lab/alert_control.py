"""Durable, redacted local alert sink for RSI systemd failure handlers."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.state_io import forge_state_root, now_utc
from dharma_swarm.forge_lab.unattended_receipts import append_chain

ALERT_SCHEMA = "rsi_lab.alert_chain.v1"


@contextmanager
def _alert_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise RuntimeError(f"unsafe alert lock: {path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def record_alert(
    *,
    unit: str,
    result: str | None = None,
    exit_status: str | None = None,
    source: str = "systemd_on_failure",
) -> dict[str, Any]:
    root = forge_state_root() / "alerts"
    with _alert_lock(root / ".alert.lock"):
        return append_chain(
            root / "rsi_lab_alerts.jsonl",
            {
                "kind": "alert_created",
                "at": now_utc(),
                "unit": str(unit)[:160],
                "result": str(result or "unknown")[:96],
                "exit_status": str(exit_status or "unknown")[:96],
                "source": str(source)[:96],
                "delivery": "durable_local_pending_operator_ack",
                "secret_values_recorded": False,
            },
            schema=ALERT_SCHEMA,
            digest_field="alert_digest",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rsi-alert")
    parser.add_argument("--unit", required=True)
    parser.add_argument("--result")
    parser.add_argument("--exit-status")
    args = parser.parse_args(argv)
    os.umask(0o077)
    receipt = record_alert(
        unit=args.unit,
        result=args.result,
        exit_status=args.exit_status,
    )
    print(json.dumps({"ok": True, "alert_digest": receipt["alert_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ALERT_SCHEMA", "record_alert"]
