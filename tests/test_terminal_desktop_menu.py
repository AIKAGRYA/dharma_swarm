"""Exercise the shipped Swift executable against the owner's public JSON contract."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from dharma_swarm.terminal_bridge_desktop_status import read_status

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("xcrun"),
                                reason="native menu checks require macOS and Xcode command line tools")


@pytest.fixture(scope="module")
def menu_executable():
    state = Path.home() / ".dharma/helm-desktop-build/test-native"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build_helm_menu.py"),
                             "--state-dir", str(state), "--json"],
                            capture_output=True, text=True, timeout=240, check=True)
    return Path(json.loads(result.stdout)["executable"])


def snapshot():
    now = datetime.now(timezone.utc) - timedelta(milliseconds=100)
    return {"schema_version": "dharma.helm.desktop_status.v1", "authority": "observation_only",
            "owner": {"id": "bridge:menu-fixture", "pid": os.getpid(), "epoch": "fixture-epoch"},
            "sequence": 1, "observed_at": now.isoformat(), "expires_at": (now + timedelta(seconds=3)).isoformat(),
            "phase": "idle", "session_id": None, "request_id": None,
            "route": {"requested_provider_id": "requested-provider", "requested_model_id": "requested-model"},
            "pending_approvals": None, "repo_root": str(ROOT),
            "seat": {"tmux_socket": "CODEX_MANAGED_helm_desktop", "tmux_session": "helm_desktop"}}


def native(executable, path, *arguments):
    result = subprocess.run([str(executable), "--check-status", "--status-file", str(path), *arguments],
                            capture_output=True, text=True, check=True, timeout=5)
    return json.loads(result.stdout)


def publish(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)


def test_native_consumes_same_owner_and_explicit_lifecycle(menu_executable, tmp_path):
    path = tmp_path.resolve() / "status.json"
    for phase in ("starting", "idle", "running", "cancelling", "closed"):
        value = {**snapshot(), "phase": phase}
        publish(path, value)
        python, swift = read_status(path), native(menu_executable, path, "--repo-root", str(ROOT))
        assert swift["availability"] == python["availability"]
        assert swift["reason"] == python["reason"]
        assert swift["owner_id"] == value["owner"]["id"]
        assert swift["owner_epoch"] == value["owner"]["epoch"]
        assert swift["phase"] == phase
        assert swift["authority"] == "observation_only"


@pytest.mark.parametrize("patch", [
    {"authority": "execution_allowed"}, {"phase": []}, {"sequence": True}, {"sequence": 0},
    {"pending_approvals": False}, {"pending_approvals": 2**31}, {"request_id": "untrusted\ntext"},
    {"owner": {"id": "owner", "pid": True, "epoch": "epoch"}}, {"repo_root": "relative"},
    {"prompt": "must not be accepted"}, {"route": {"served_model_id": "unverified"}},
    {"seat": {"tmux_socket": "default", "tmux_session": "operator"}},
    {"seat": {"tmux_socket": "CODEX_MANAGED_ok", "tmux_session": None}},
])
def test_both_consumers_reject_invalid_snapshot(menu_executable, tmp_path, patch):
    path = tmp_path.resolve() / "status.json"
    publish(path, {**snapshot(), **patch})
    assert read_status(path)["availability"] == native(menu_executable, path)["availability"] == "invalid"


@pytest.mark.parametrize("condition", ["expired", "future", "long_expiry", "dead"])
def test_native_freshness_has_no_success_fallback(menu_executable, tmp_path, condition):
    path, value = tmp_path.resolve() / "status.json", snapshot()
    observed = datetime.fromisoformat(value["observed_at"])
    if condition == "expired":
        value.update(observed_at=(observed - timedelta(seconds=4)).isoformat(),
                     expires_at=(observed - timedelta(seconds=1)).isoformat())
    elif condition == "future":
        value.update(observed_at=(observed + timedelta(seconds=10)).isoformat(),
                     expires_at=(observed + timedelta(seconds=13)).isoformat())
    elif condition == "long_expiry":
        value["expires_at"] = (observed + timedelta(seconds=4)).isoformat()
    else:
        child = subprocess.Popen(["/usr/bin/true"])
        child.wait(timeout=5)
        value["owner"]["pid"] = child.pid
    publish(path, value)
    python, swift = read_status(path), native(menu_executable, path)
    assert swift["availability"] == python["availability"]
    assert swift["availability"] in {"invalid", "stale"}
    assert swift["title"] in {"Helm · offline", "Helm · stale"}


def test_native_rejects_wrong_seat_and_unsafe_files(menu_executable, tmp_path):
    path = tmp_path.resolve() / "status.json"
    assert native(menu_executable, path)["availability"] == "unavailable"
    assert not path.exists()
    publish(path, snapshot())
    wrong = native(menu_executable, path, "--repo-root", str(ROOT), "--session", "another_seat")
    assert wrong["availability"] == "invalid"
    assert "owner_id" not in wrong
    link = path.parent / "linked.json"
    link.symlink_to(path)
    assert native(menu_executable, link)["availability"] == "invalid"
    path.chmod(0o644)
    assert native(menu_executable, path)["availability"] == "invalid"
    path.chmod(0o600)
    path.write_bytes(b" " * 65_537)
    assert native(menu_executable, path)["availability"] == "invalid"
