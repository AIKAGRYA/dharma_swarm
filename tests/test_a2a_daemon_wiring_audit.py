from __future__ import annotations

import json
import plistlib
from pathlib import Path

from scripts.runtime import a2a_daemon_wiring_audit


def _write_plist(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def test_valid_agni_daemon_passes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    module = repo / "dharma_swarm" / "operator_core" / "nats_live_contact.py"
    module.parent.mkdir(parents=True)
    module.write_text("# target exists\n", encoding="utf-8")
    launch_agents = tmp_path / "LaunchAgents"
    _write_plist(
        launch_agents / "com.dharma.a2a.valid.plist",
        {
            "Label": "com.dharma.a2a.valid",
            "ProgramArguments": [
                "/usr/bin/python3",
                "-m",
                "dharma_swarm.operator_core.nats_live_contact",
            ],
            "WorkingDirectory": str(repo),
            "EnvironmentVariables": {
                "DHARMA_NATS_URL": "wss://agni.example.invalid:8443",
            },
        },
    )

    audit = a2a_daemon_wiring_audit.build_audit(
        launch_agents_dir=launch_agents,
        expected_broker_scope="agni",
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert audit["status"] == "PASS"
    assert audit["candidate_count"] == 1
    assert audit["candidates"][0]["broker_scope"] == "agni"
    assert audit["candidates"][0]["issues"] == []


def test_missing_module_and_local_broker_fail(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    launch_agents = tmp_path / "LaunchAgents"
    error_log = tmp_path / "daemon.err.log"
    error_log.write_text(
        "/tmp/repo/.venv/bin/python: No module named dharma_swarm.operator_core.nats_a2a_bridge\n",
        encoding="utf-8",
    )
    _write_plist(
        launch_agents / "com.dharma.nats.bridge.plist",
        {
            "Label": "com.dharma.nats.bridge",
            "ProgramArguments": [
                "/usr/bin/python3",
                "-m",
                "dharma_swarm.operator_core.nats_a2a_bridge",
            ],
            "WorkingDirectory": str(repo),
            "EnvironmentVariables": {
                "DHARMA_NATS_URL": "nats://127.0.0.1:4222",
            },
            "StandardErrorPath": str(error_log),
        },
    )

    audit = a2a_daemon_wiring_audit.build_audit(
        launch_agents_dir=launch_agents,
        expected_broker_scope="agni",
        created_at="2026-06-13T00:00:00+00:00",
    )

    issues = {issue["type"] for issue in audit["candidates"][0]["issues"]}
    assert audit["status"] == "FAIL"
    assert "missing_module_target" in issues
    assert "broker_scope_mismatch" in issues
    assert "missing_python_module" in issues


def test_missing_relative_script_target_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    launch_agents = tmp_path / "LaunchAgents"
    _write_plist(
        launch_agents / "com.dharma.a2a.core-contact.plist",
        {
            "Label": "com.dharma.a2a.core-contact",
            "ProgramArguments": [
                "/usr/bin/python3",
                "scripts/runtime/a2a_core_contact.py",
            ],
            "WorkingDirectory": str(repo),
            "EnvironmentVariables": {
                "DHARMA_NATS_URL": "wss://agni.example.invalid:8443",
            },
        },
    )

    audit = a2a_daemon_wiring_audit.build_audit(
        launch_agents_dir=launch_agents,
        expected_broker_scope="agni",
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert audit["status"] == "FAIL"
    assert audit["candidates"][0]["issues"][0]["type"] == "missing_script_target"
    assert "scripts/runtime/a2a_core_contact.py" in audit["candidates"][0]["issues"][0]["message"]


def test_write_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    payload = {
        "schema_version": a2a_daemon_wiring_audit.SCHEMA_VERSION,
        "status": "PASS",
    }

    a2a_daemon_wiring_audit.write_receipt(receipt_path, payload)

    assert json.loads(receipt_path.read_text(encoding="utf-8")) == payload
