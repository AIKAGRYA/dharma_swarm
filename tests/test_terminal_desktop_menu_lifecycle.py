"""Shipped native lifecycle helpers and launch decisions, with no GUI activation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from dharma_swarm.terminal_bridge_desktop_status import read_status

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("helm_menu_builder_lifecycle", ROOT / "scripts/build_helm_menu.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
NATIVE = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("xcrun"),
                            reason="native lifecycle checks require macOS and Xcode tools")


@pytest.fixture(scope="module")
def executable():
    state = Path.home() / ".dharma/helm-desktop-build/test-native-lifecycle"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build_helm_menu.py"),
                             "--state-dir", str(state), "--json"],
                            capture_output=True, text=True, timeout=240, check=True)
    return Path(json.loads(result.stdout)["executable"])


def native(executable, *args):
    result = subprocess.run([str(executable), *args], capture_output=True, text=True, timeout=5, check=True)
    return json.loads(result.stdout)


@NATIVE
def test_burst_has_trailing_refresh_and_expiration_runs_during_menu_tracking(executable):
    result = native(executable, "--check-lifecycle")
    assert result["refresh_count"] == 2
    assert 0.005 < result["trailing_refresh_seconds"] < 0.25
    assert result["expiry_ticks_during_menu_tracking"] > 0


@NATIVE
@pytest.mark.parametrize("value,exit_code,expected", [
    ({"ok": True, "outcome": "attached_elsewhere", "detail": "Existing seat is attached in another terminal"}, 0, False),
    ({"ok": True, "outcome": "attachment_pending", "detail": "A prior attachment is still pending"}, 0, False),
    ({"ok": False, "error": "Bounded failure"}, 1, True),
])
def test_action_notice_retains_successful_but_incomplete_outcomes(executable, tmp_path, value, exit_code, expected):
    path = tmp_path / "result.json"
    path.write_text(json.dumps(value))
    result = native(executable, "--check-action-result", str(path), "--exit-code", str(exit_code))
    assert result["failed"] is expected
    assert result["detail"] == value.get("detail", value.get("error"))


@NATIVE
def test_focused_action_has_no_alert_and_notice_text_is_bounded(executable, tmp_path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"ok": True, "outcome": "focused"}))
    assert native(executable, "--check-action-result", str(path)) == {"notice": None}
    path.write_text(json.dumps({"ok": False, "error": "a" * 4000}))
    result = native(executable, "--check-action-result", str(path), "--exit-code", "1")
    assert len(result["detail"]) == 1200


@NATIVE
@pytest.mark.parametrize("duplicate", ["root", "escaped", "nested"])
def test_native_rejects_duplicate_object_keys_like_owner_reader(executable, tmp_path, duplicate):
    observed = datetime.now(timezone.utc) - timedelta(milliseconds=100)
    value = {"schema_version": "dharma.helm.desktop_status.v1", "authority": "observation_only",
             "owner": {"id": "bridge:test", "pid": os.getpid(), "epoch": "fixture"},
             "sequence": 1, "observed_at": observed.isoformat(), "expires_at": (observed + timedelta(seconds=3)).isoformat(),
             "phase": "idle", "session_id": None, "request_id": None,
             "route": {"requested_provider_id": None, "requested_model_id": None},
             "pending_approvals": None, "repo_root": str(ROOT),
             "seat": {"tmux_socket": "CODEX_MANAGED_helm_desktop", "tmux_session": "helm_desktop"}}
    text = json.dumps(value)
    if duplicate == "root":
        text = text.replace('"sequence": 1', '"sequence": 1, "sequence": 2')
    elif duplicate == "escaped":
        text = text.replace('"sequence": 1', '"sequence": 1, "seque\\u006ece": 2')
    else:
        text = text.replace('"epoch": "fixture"', '"epoch": "fixture", "epoch": "second"')
    path = tmp_path.resolve() / "status.json"
    path.write_text(text)
    path.chmod(0o600)
    assert read_status(path)["availability"] == "invalid"
    assert native(executable, "--check-status", "--status-file", str(path))["availability"] == "invalid"


def test_bundle_identity_is_stable_per_state_and_distinct_across_states(tmp_path):
    assert builder.bundle_identifier(tmp_path / "one") == builder.bundle_identifier(tmp_path / "one")
    assert builder.bundle_identifier(tmp_path / "one") != builder.bundle_identifier(tmp_path / "two")


@pytest.fixture
def held_instance(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    configuration = {"--profile": "research", "--state-dir": str(state), "--build-id": "build-one"}
    receipt = state / "menu-instance.json"
    receipt.write_text(json.dumps({"schema": "dharma.helm.menu_instance.v1", "pid": os.getpid(), "configuration": configuration}))
    receipt.chmod(0o600)
    descriptor = os.open(state / "menu-instance.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield state, configuration
    finally:
        os.close(descriptor)


def test_matching_live_configuration_reuses_without_launching(held_instance):
    state, configuration = held_instance
    result = builder.launch_menu(state / "apps/Helm.app", state, configuration,
                                 runner=lambda *args, **kwargs: pytest.fail("matching instance must not launch or probe processes"))
    assert result["outcome"] == "reused"
    assert result["reused"] and not result["launch_requested"]


@pytest.mark.parametrize("patch", [{"--profile": "operations"}, {"--build-id": "build-two"}])
def test_configuration_or_build_mismatch_preserves_running_menu(held_instance, patch):
    state, configuration = held_instance
    result = builder.launch_menu(state / "apps/Helm.app", state, {**configuration, **patch},
                                 runner=lambda *args, **kwargs: pytest.fail("mismatch must not launch or terminate processes"))
    assert result["outcome"] == "config_mismatch"
    assert not result["launch_requested"] and not result["ok"]
    assert "Quit Menu" in result["detail"]


def test_unlocked_stale_receipt_does_not_prove_running_menu(tmp_path):
    (tmp_path / "menu-instance.lock").touch(mode=0o600)
    (tmp_path / "menu-instance.json").write_text('{"pid":1234}')
    assert builder.instance_status(tmp_path, {}) == {"outcome": "not_running"}


@pytest.mark.parametrize("matching", [True, False])
def test_launch_requires_observed_matching_instance_to_claim_success(tmp_path, matching):
    calls = []
    observations = iter([{"outcome": "not_running"}, {"outcome": "reused", "pid": 55} if matching else {"outcome": "not_running"}])

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    result = builder.launch_menu(tmp_path / "Helm.app", tmp_path, {"--profile": "research"}, runner=runner,
                                 observe=lambda *_: next(observations), timeout_seconds=0)
    assert result["outcome"] == ("launched" if matching else "launch_requested")
    assert result["ok"] is matching
    assert result["launch_requested"]
    assert calls[-1] == ["open", str(tmp_path / "Helm.app"), "--args", "--profile", "research"]
    assert not any("-n" in call or "kill" in call for call in calls)


def test_older_untracked_menu_is_not_duplicated(tmp_path):
    app = tmp_path / "Helm.app"
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=f" 55 {app}/Contents/MacOS/HelmMenu\n", stderr="")

    result = builder.launch_menu(app, tmp_path, {}, runner=runner, observe=lambda *_: {"outcome": "not_running"})
    assert result["outcome"] == "config_mismatch"
    assert len(calls) == 1
    assert calls[0][0] == "/bin/ps"
