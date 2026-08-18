"""Canonical, non-admission NATS status projection for compact onboarding."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.operator_core.onboarding import cli, nats_status, render


REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts" / "governance" / "agent_onboard.py"


class _FakeConnection:
    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _create_declared_mirrors(home: Path) -> None:
    for display_path in nats_status.FILESYSTEM_MIRROR_PATHS:
        target = home / display_path.removeprefix("~/").rstrip("/")
        if target.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture\n", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)


def _load_compatibility_shim() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_onboard_nats_status_contract",
        ONBOARD_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_verdict": "READY",
        "exit_code": 0,
        "stable_core": {
            "repository": {
                "branch": "test/onboarding-nats",
                "head": "1" * 40,
            },
            "portfolio": {"tracks": []},
            "orientation": {
                "broken_register": {},
                "static_surfaces": {},
            },
            "required_reading": [],
        },
        "live_delta": {
            "repo_state": {
                "base": "origin/main",
                "dirty": False,
                "conflicted": False,
                "ahead": 0,
                "behind": 0,
            },
            "conditions": [],
            "toolchain": {},
            "projection_freshness": {},
        },
        "extensions": {"nats_substrate": status},
    }


def test_canonical_spec_contract_links_shim_and_collector() -> None:
    shim = _load_compatibility_shim()

    assert (
        nats_status.SPEC_PATH
        == shim.NATS_SUBSTRATE_SPEC_PATH
        == "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
    )


def test_collection_uses_only_bounded_local_tcp_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[str, int], float]] = []

    def connect(address: tuple[str, int], timeout: float) -> _FakeConnection:
        calls.append((address, timeout))
        return _FakeConnection()

    monkeypatch.setenv("NATS_URL", "nats://external.invalid:9999")
    monkeypatch.setenv("DHARMA_NATS_URL", "nats://external.invalid:8888")
    monkeypatch.setattr(nats_status.socket, "create_connection", connect)

    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    assert calls == [
        (
            (nats_status.LOCAL_TCP_HOST, nats_status.LOCAL_TCP_PORT),
            nats_status.TCP_PROBE_TIMEOUT_SECONDS,
        )
    ]
    assert status["tcp_host"] == "127.0.0.1"
    assert status["tcp_port"] == 4222
    assert status["tcp_listening"] is True
    assert status["probe_scope"] == "local_tcp_listener_only"
    assert status["jetstream_ack_verified"] is False
    assert status["live_contact_claim"] is False


def test_unavailable_local_listener_is_observed_without_becoming_a_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> _FakeConnection:
        raise OSError("fixture listener absent")

    monkeypatch.setattr(nats_status.socket, "create_connection", unavailable)

    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    assert status["tcp_listening"] is False
    assert status["jetstream_ack_verified"] is False
    assert status["live_contact_claim"] is False


def test_collection_reports_each_declared_compatibility_mirror(tmp_path: Path) -> None:
    _create_declared_mirrors(tmp_path)

    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    assert [row["path"] for row in status["filesystem_mirrors"]] == list(
        nats_status.FILESYSTEM_MIRROR_PATHS
    )
    assert all(row["exists"] is True for row in status["filesystem_mirrors"])
    assert status["filesystem_mirrors_exist"] is True


def test_collection_never_promotes_mirrors_to_live_transport_proof(
    tmp_path: Path,
) -> None:
    _create_declared_mirrors(tmp_path)

    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    assert nats_status.MIRRORS_ARE_LIVE_TRANSPORT_PROOF is False
    assert status["mirrors_are_live_transport_proof"] is False
    assert status["live_contact_claim"] is False


def test_human_renderer_names_status_and_warning(tmp_path: Path) -> None:
    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    output = render.render_compact(_receipt(status))

    assert "NATS SUBSTRATE — LOCAL OBSERVATION ONLY" in output
    assert "Spec: docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md" in output
    assert "Local TCP 127.0.0.1:4222:" in output
    assert "Compatibility filesystem A2A mirrors:" in output
    assert (
        "WARNING: compatibility filesystem mirrors are not live-transport proof."
        in output
    )
    assert "No JetStream ack or live contact is claimed." in output


def test_json_renderer_projects_exact_nonadmission_status(tmp_path: Path) -> None:
    status = nats_status.collect_nats_substrate_status(home=tmp_path)

    projection = render.machine_projection(_receipt(status))

    assert projection["nats_substrate"] == status
    assert projection["nats_substrate"]["spec_path"] == (
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
    )
    assert projection["nats_substrate"]["tcp_host"] == "127.0.0.1"
    assert projection["nats_substrate"]["tcp_port"] == 4222
    assert projection["nats_substrate"]["mirrors_are_live_transport_proof"] is False
    assert projection["nats_substrate"]["jetstream_ack_verified"] is False
    assert projection["nats_substrate"]["live_contact_claim"] is False


def test_real_cli_projects_nats_status_in_human_and_json_modes(
    tmp_path: Path,
) -> None:
    environment = {
        **os.environ,
        "DHARMA_OPS_DIR": str(tmp_path / "ops"),
        "NATS_URL": "nats://external.invalid:9999",
        "DHARMA_NATS_URL": "nats://external.invalid:8888",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    json_result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--json"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    human_result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    payload = json.loads(json_result.stdout)
    assert json_result.returncode == human_result.returncode == payload["exit_code"]
    assert payload["nats_substrate"]["spec_path"] == (
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
    )
    assert payload["nats_substrate"]["tcp_host"] == "127.0.0.1"
    assert payload["nats_substrate"]["tcp_port"] == 4222
    assert payload["nats_substrate"]["mirrors_are_live_transport_proof"] is False
    assert "NATS SUBSTRATE — LOCAL OBSERVATION ONLY" in human_result.stdout
    assert "No JetStream ack or live contact is claimed." in human_result.stdout


def test_nats_observation_does_not_change_typed_exit_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = nats_status.collect_nats_substrate_status(home=tmp_path)

    def run_with_listener(listening: bool, ops_name: str) -> tuple[int, str]:
        projection = {**base, "tcp_listening": listening}
        monkeypatch.setattr(
            cli.nats_status,
            "collect_nats_substrate_status",
            lambda: projection,
        )
        monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / ops_name))
        exit_code = cli.assemble_and_run(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["nats_substrate"]["tcp_listening"] is listening
        return exit_code, payload["verdict"]

    unavailable = run_with_listener(False, "ops-unavailable")
    listening = run_with_listener(True, "ops-listening")

    assert unavailable == listening
