#!/usr/bin/env python3
"""Disable legacy Hermes file-bus broadcast amplification with a receipt.

Hermes may still queue alerts or bridge summaries locally, but it must not
mirror one `to=all` payload into every filesystem inbox and create false A2A
work.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.hermes_broadcast_guard.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATE = "2026-06-13"
DEFAULT_HERMES_HOME = Path.home() / ".hermes"
DEFAULT_BACKUP_ROOT = Path.home() / ".dharma" / "a2a_bus" / "quarantine" / "hermes_broadcast_guard"
DEFAULT_RECEIPT = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "hermes_broadcast_guard"
    / DEFAULT_DATE
    / "HERMES_LEGACY_BROADCAST_GUARD_APPLIED.json"
)

GUARD_START = "    # DHARMA_A2A_BROADCAST_GUARD_START"
GUARD_END = "    # DHARMA_A2A_BROADCAST_GUARD_END"
LEGACY_BROADCAST_SIGNATURE = '"broadcast"'
ALERT_ROUTER_FUNCTION_SIGNATURE = "def broadcast_a2a(alerts, route_status):\n"
DHARMA_BRIDGE_FUNCTION_SIGNATURE = "def broadcast(event: dict[str, Any]) -> None:\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_flag_path(hermes_home: Path) -> Path:
    return hermes_home / "comms" / "DISABLE_A2A_BROADCAST"


def default_alert_router(hermes_home: Path) -> Path:
    return hermes_home / "scripts" / "alert_router.py"


def default_dharma_bridge(hermes_home: Path) -> Path:
    return hermes_home / "scripts" / "dharma_bridge.py"


def default_a2a_bus(hermes_home: Path) -> Path:
    return hermes_home / "scripts" / "a2a_bus.py"


def load_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def guard_block(*, disable_file_expr: str) -> str:
    return (
        f"{GUARD_START}\n"
        '    disable_env = os.environ.get("HERMES_DISABLE_A2A_BROADCAST", "").strip().lower()\n'
        f"    disable_file = {disable_file_expr}\n"
        '    if disable_env in {"1", "true", "yes", "on"} or disable_file.exists():\n'
        "        return\n"
        f"{GUARD_END}\n"
    )


def patch_alert_router_text(text: str) -> tuple[str, bool]:
    if GUARD_START in text:
        return text, False
    if ALERT_ROUTER_FUNCTION_SIGNATURE not in text:
        raise ValueError("broadcast_a2a function signature not found")
    return (
        text.replace(
            ALERT_ROUTER_FUNCTION_SIGNATURE,
            ALERT_ROUTER_FUNCTION_SIGNATURE + guard_block(disable_file_expr='COMMS_DIR / "DISABLE_A2A_BROADCAST"'),
            1,
        ),
        True,
    )


def patch_dharma_bridge_text(text: str) -> tuple[str, bool]:
    if GUARD_START in text:
        return text, False
    if DHARMA_BRIDGE_FUNCTION_SIGNATURE not in text:
        raise ValueError("dharma_bridge broadcast function signature not found")
    return (
        text.replace(
            DHARMA_BRIDGE_FUNCTION_SIGNATURE,
            DHARMA_BRIDGE_FUNCTION_SIGNATURE
            + guard_block(disable_file_expr='HERMES_HOME / "comms" / "DISABLE_A2A_BROADCAST"'),
            1,
        ),
        True,
    )


def _legacy_present(text: str | None, *, function_name: str) -> bool:
    return bool(
        text
        and "A2A_BUS" in text
        and LEGACY_BROADCAST_SIGNATURE in text
        and function_name in text
    )


def analyze_guard(
    *,
    hermes_home: Path,
    alert_router: Path | None = None,
    dharma_bridge: Path | None = None,
) -> dict[str, Any]:
    router = alert_router or default_alert_router(hermes_home)
    bridge = dharma_bridge or default_dharma_bridge(hermes_home)
    a2a_bus = default_a2a_bus(hermes_home)
    flag_path = default_flag_path(hermes_home)
    router_text = load_text(router)
    bridge_text = load_text(bridge)
    alert_router_guard_present = bool(router_text and GUARD_START in router_text and GUARD_END in router_text)
    dharma_bridge_guard_present = bool(bridge_text and GUARD_START in bridge_text and GUARD_END in bridge_text)
    alert_router_legacy_present = _legacy_present(router_text, function_name="broadcast_a2a")
    dharma_bridge_legacy_present = _legacy_present(bridge_text, function_name="broadcast")
    unguarded = []
    if alert_router_legacy_present and not alert_router_guard_present:
        unguarded.append("alert_router.py")
    if dharma_bridge_legacy_present and not dharma_bridge_guard_present:
        unguarded.append("dharma_bridge.py")
    guard_present = not unguarded
    return {
        "hermes_home": str(hermes_home),
        "alert_router_path": str(router),
        "alert_router_exists": router.exists(),
        "alert_router_guard_present": alert_router_guard_present,
        "alert_router_legacy_broadcast_call_present": alert_router_legacy_present,
        "dharma_bridge_path": str(bridge),
        "dharma_bridge_exists": bridge.exists(),
        "dharma_bridge_guard_present": dharma_bridge_guard_present,
        "dharma_bridge_legacy_broadcast_call_present": dharma_bridge_legacy_present,
        "a2a_bus_path": str(a2a_bus),
        "a2a_bus_exists": a2a_bus.exists(),
        "flag_path": str(flag_path),
        "flag_file_present": flag_path.exists(),
        "guard_present": guard_present,
        "legacy_broadcast_call_present": alert_router_legacy_present or dharma_bridge_legacy_present,
        "unguarded_legacy_broadcast_sources": unguarded,
    }


def write_disable_flag(*, flag_path: Path, receipt_path: Path, backup_paths: list[str]) -> None:
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    backup_line = "Backups: " + ", ".join(backup_paths) if backup_paths else "Backups: unchanged/already guarded"
    flag_path.write_text(
        "\n".join(
            [
                "Hermes legacy A2A broadcast disabled.",
                "",
                "Reason: legacy Hermes scripts used a2a_bus.py broadcast, which copied",
                "one `to=all` payload into every filesystem inbox. The filesystem inbox",
                "is a compatibility dock, not production live-contact authority.",
                "",
                f"Receipt: {receipt_path}",
                backup_line,
                "",
                "To re-enable intentionally, remove this flag only after AGNI target-owned",
                "handler receipts replace filesystem broadcast fanout.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def apply_guard(
    *,
    hermes_home: Path,
    alert_router: Path,
    dharma_bridge: Path,
    backup_root: Path,
    receipt_path: Path,
    created_at: str,
) -> dict[str, Any]:
    before = analyze_guard(hermes_home=hermes_home, alert_router=alert_router, dharma_bridge=dharma_bridge)
    errors: list[str] = []
    backup_paths: list[str] = []
    patched_files: list[str] = []
    backup_dir = backup_root / created_at.replace(":", "").replace("+", "Z")

    patch_targets = [
        ("alert_router.py", alert_router, patch_alert_router_text),
        ("dharma_bridge.py", dharma_bridge, patch_dharma_bridge_text),
    ]
    for label, path, patcher in patch_targets:
        text = load_text(path)
        if text is None:
            continue
        try:
            patched_text, patched = patcher(text)
        except ValueError as exc:
            if _legacy_present(text, function_name="broadcast"):
                errors.append(f"{label}: {exc}")
            continue
        if patched:
            backup_path = backup_dir / label
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            path.write_text(patched_text, encoding="utf-8")
            patched_files.append(str(path))
            backup_paths.append(str(backup_path))

    if not errors:
        write_disable_flag(
            flag_path=default_flag_path(hermes_home),
            receipt_path=receipt_path,
            backup_paths=backup_paths,
        )

    after = analyze_guard(hermes_home=hermes_home, alert_router=alert_router, dharma_bridge=dharma_bridge)
    status = "FAILED" if errors or after["unguarded_legacy_broadcast_sources"] else "APPLIED" if patched_files else "ALREADY_GUARDED"
    return {
        "status": status,
        "errors": [*errors, *(f"unguarded: {source}" for source in after["unguarded_legacy_broadcast_sources"])],
        "patched": bool(patched_files),
        "patched_files": patched_files,
        "backup_path": backup_paths[0] if len(backup_paths) == 1 else None,
        "backup_paths": backup_paths,
        "before": before,
        "after": after,
    }


def build_receipt(
    *,
    hermes_home: Path,
    alert_router: Path,
    backup_root: Path,
    receipt_path: Path,
    apply: bool,
    dharma_bridge: Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or utc_now()
    bridge = dharma_bridge or default_dharma_bridge(hermes_home)
    if apply:
        result = apply_guard(
            hermes_home=hermes_home,
            alert_router=alert_router,
            dharma_bridge=bridge,
            backup_root=backup_root,
            receipt_path=receipt_path,
            created_at=timestamp,
        )
    else:
        result = {
            "status": "DRY_RUN",
            "errors": [],
            "patched": False,
            "patched_files": [],
            "backup_path": None,
            "backup_paths": [],
            "before": analyze_guard(hermes_home=hermes_home, alert_router=alert_router, dharma_bridge=bridge),
            "after": analyze_guard(hermes_home=hermes_home, alert_router=alert_router, dharma_bridge=bridge),
        }

    after = result["after"]
    broadcast_disabled = bool(after["guard_present"] and after["flag_file_present"])
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": timestamp,
        "status": result["status"],
        "production_claim": False,
        "operation": "disable_hermes_legacy_file_bus_broadcast",
        "mutation_applied": apply,
        "broadcast_disabled": broadcast_disabled,
        "filesystem_inbox_authority_claim": False,
        "interpretation": (
            "This disables known Hermes legacy file-bus broadcast amplification. "
            "It does not prove AGNI handler contact, peer review, domain receipt, "
            "or production readiness."
        ),
        "result": result,
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hermes-home", default=str(DEFAULT_HERMES_HOME))
    parser.add_argument("--alert-router", default=None)
    parser.add_argument("--dharma-bridge", default=None)
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--apply", action="store_true", help="Patch alert_router.py and write the disable flag.")
    parser.add_argument("--write", action="store_true", help="Write the JSON receipt.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero unless broadcast is disabled.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv or sys.argv[1:])
    hermes_home = Path(args.hermes_home).expanduser()
    receipt_path = Path(args.receipt_path).expanduser()
    alert_router = Path(args.alert_router).expanduser() if args.alert_router else default_alert_router(hermes_home)
    dharma_bridge = Path(args.dharma_bridge).expanduser() if args.dharma_bridge else default_dharma_bridge(hermes_home)
    payload = build_receipt(
        hermes_home=hermes_home,
        alert_router=alert_router,
        dharma_bridge=dharma_bridge,
        backup_root=Path(args.backup_root).expanduser(),
        receipt_path=receipt_path,
        apply=args.apply,
    )
    if args.write:
        write_receipt(receipt_path, payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} broadcast_disabled={payload['broadcast_disabled']} "
            f"unguarded={payload['result']['after']['unguarded_legacy_broadcast_sources']}"
        )
    if args.check and not payload["broadcast_disabled"]:
        return 1
    return 0 if payload["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
