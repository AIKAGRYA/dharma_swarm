from __future__ import annotations

from pathlib import Path

from scripts.runtime import a2a_hermes_broadcast_guard


FIXTURE = '''#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
COMMS_DIR = HERMES_HOME / "comms"
A2A_BUS = HERMES_HOME / "scripts" / "a2a_bus.py"

def broadcast_a2a(alerts, route_status):
    if not A2A_BUS.exists():
        return
    payload = {"alerts": alerts, "route_status": route_status}
    subprocess.run(
        [sys.executable, str(A2A_BUS), "broadcast", "--body", json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
'''

BRIDGE_FIXTURE = '''#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path
from typing import Any

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
A2A_BUS = HERMES_HOME / "scripts" / "a2a_bus.py"

def broadcast(event: dict[str, Any]) -> None:
    if not A2A_BUS.exists():
        return
    subprocess.run(
        ["python3", str(A2A_BUS), "broadcast", "--body", json.dumps(event)],
        capture_output=True,
        text=True,
        timeout=10,
    )
'''


def _write_fixture(root: Path) -> Path:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    router = scripts / "alert_router.py"
    router.write_text(FIXTURE, encoding="utf-8")
    (scripts / "a2a_bus.py").write_text("# bus\n", encoding="utf-8")
    return router


def _write_bridge_fixture(root: Path) -> Path:
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    bridge = scripts / "dharma_bridge.py"
    bridge.write_text(BRIDGE_FIXTURE, encoding="utf-8")
    (scripts / "a2a_bus.py").write_text("# bus\n", encoding="utf-8")
    return bridge


def test_dry_run_detects_legacy_broadcast_without_disabling(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)

    payload = a2a_hermes_broadcast_guard.build_receipt(
        hermes_home=hermes_home,
        alert_router=router,
        backup_root=tmp_path / "backup",
        receipt_path=tmp_path / "receipt.json",
        apply=False,
        created_at="2026-06-12T00:00:00+00:00",
    )

    assert payload["status"] == "DRY_RUN"
    assert payload["broadcast_disabled"] is False
    assert payload["result"]["before"]["legacy_broadcast_call_present"] is True
    assert payload["result"]["before"]["guard_present"] is False


def test_apply_patches_router_creates_backup_and_disable_flag(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)
    receipt_path = tmp_path / "receipt.json"

    payload = a2a_hermes_broadcast_guard.build_receipt(
        hermes_home=hermes_home,
        alert_router=router,
        backup_root=tmp_path / "backup",
        receipt_path=receipt_path,
        apply=True,
        created_at="2026-06-12T00:00:00+00:00",
    )

    assert payload["status"] == "APPLIED"
    assert payload["broadcast_disabled"] is True
    assert payload["result"]["patched"] is True
    backup_path = payload["result"]["backup_path"]
    assert backup_path is not None
    assert Path(backup_path).exists()
    assert a2a_hermes_broadcast_guard.GUARD_START in router.read_text(encoding="utf-8")
    assert (hermes_home / "comms" / "DISABLE_A2A_BROADCAST").exists()


def test_apply_patches_dharma_bridge_broadcast_source_too(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)
    bridge = _write_bridge_fixture(hermes_home)

    payload = a2a_hermes_broadcast_guard.build_receipt(
        hermes_home=hermes_home,
        alert_router=router,
        dharma_bridge=bridge,
        backup_root=tmp_path / "backup",
        receipt_path=tmp_path / "receipt.json",
        apply=True,
        created_at="2026-06-12T00:00:00+00:00",
    )

    assert payload["status"] == "APPLIED"
    assert payload["broadcast_disabled"] is True
    assert payload["result"]["after"]["unguarded_legacy_broadcast_sources"] == []
    assert payload["result"]["after"]["dharma_bridge_guard_present"] is True
    assert a2a_hermes_broadcast_guard.GUARD_START in bridge.read_text(encoding="utf-8")


def test_disable_flag_does_not_hide_unguarded_dharma_bridge(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)
    bridge = _write_bridge_fixture(hermes_home)
    (hermes_home / "comms").mkdir(parents=True)
    (hermes_home / "comms" / "DISABLE_A2A_BROADCAST").write_text("disabled\n", encoding="utf-8")
    patched_router, _ = a2a_hermes_broadcast_guard.patch_alert_router_text(router.read_text(encoding="utf-8"))
    router.write_text(patched_router, encoding="utf-8")

    payload = a2a_hermes_broadcast_guard.build_receipt(
        hermes_home=hermes_home,
        alert_router=router,
        dharma_bridge=bridge,
        backup_root=tmp_path / "backup",
        receipt_path=tmp_path / "receipt.json",
        apply=False,
        created_at="2026-06-12T00:00:00+00:00",
    )

    assert payload["broadcast_disabled"] is False
    assert payload["result"]["after"]["unguarded_legacy_broadcast_sources"] == ["dharma_bridge.py"]


def test_apply_is_idempotent_after_guard_present(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)
    kwargs = {
        "hermes_home": hermes_home,
        "alert_router": router,
        "backup_root": tmp_path / "backup",
        "receipt_path": tmp_path / "receipt.json",
        "apply": True,
    }

    first = a2a_hermes_broadcast_guard.build_receipt(**kwargs, created_at="2026-06-12T00:00:00+00:00")
    second = a2a_hermes_broadcast_guard.build_receipt(**kwargs, created_at="2026-06-12T00:01:00+00:00")

    assert first["status"] == "APPLIED"
    assert second["status"] == "ALREADY_GUARDED"
    assert second["broadcast_disabled"] is True
    assert second["result"]["patched"] is False


def test_check_mode_fails_until_apply_succeeds(tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    router = _write_fixture(hermes_home)
    common = [
        "--hermes-home",
        str(hermes_home),
        "--alert-router",
        str(router),
        "--backup-root",
        str(tmp_path / "backup"),
        "--receipt-path",
        str(tmp_path / "receipt.json"),
        "--check",
    ]

    assert a2a_hermes_broadcast_guard.main(common) == 1
    assert a2a_hermes_broadcast_guard.main([*common, "--apply"]) == 0
