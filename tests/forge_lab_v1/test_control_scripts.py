from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

from dharma_swarm.forge_lab.provider_selftest import STAGED_FALLBACK_MODELS


REPO_ROOT = Path(__file__).resolve().parents[2]
FORGE_SCRIPT_ROOT = REPO_ROOT / "scripts" / "forge_lab"
LEGACY_ROOT = FORGE_SCRIPT_ROOT / "legacy_v0"
INVENTORY_PATH = LEGACY_ROOT / "inventory.json"

HOST_CAPTURE_NAMES = {
    "rsi-attach",
    "rsi-env",
    "rsi-fix-substrate",
    "rsi-keys-refresh",
    "rsi-loop",
    "rsi-mobile-help",
    "rsi-progress",
    "rsi-run",
    "rsi-selfcheck",
    "rsi-status",
    "rsi-stop",
    "rsi-tail",
    "rsi-update-main",
}


def _inventory() -> dict[str, object]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _entries() -> list[dict[str, object]]:
    files = _inventory()["files"]
    assert isinstance(files, list)
    return files


def test_legacy_inventory_covers_the_captured_host_control_surface() -> None:
    inventory = _inventory()
    entries = _entries()

    assert inventory["source_root"] == "/root/rsi-lab/bin"
    assert inventory["custody"] == "noncanonical_evidence"
    assert inventory["canonical_base"] == "/root/rsi-lab/current"
    assert inventory["installable"] is False
    assert inventory["executable"] is False
    assert {entry["name"] for entry in entries} == HOST_CAPTURE_NAMES
    assert {entry["path"] for entry in entries} == HOST_CAPTURE_NAMES
    assert {path.name for path in LEGACY_ROOT.glob("rsi-*")} == HOST_CAPTURE_NAMES


def test_tracked_legacy_content_matches_inventory_hashes_and_sizes() -> None:
    sha256_pattern = re.compile(r"[0-9a-f]{64}")

    for entry in _entries():
        path = LEGACY_ROOT / str(entry["path"])
        payload = path.read_bytes()

        assert path.is_file()
        assert path.stat().st_mode & 0o111 == 0
        assert len(payload) == entry["archived_size_bytes"]
        assert hashlib.sha256(payload).hexdigest() == entry["archived_sha256"]
        assert sha256_pattern.fullmatch(str(entry["source_sha256"]))
        assert entry["source_mode"] == "0755"


def test_legacy_inventory_classifies_live_secret_and_tmux_hazards() -> None:
    entries = _entries()
    by_name = {str(entry["name"]): entry for entry in entries}
    all_hazards = {
        str(hazard)
        for entry in entries
        for hazard in entry["hazards"]
    }

    assert {"live_network", "model_spend", "secret", "tmux"} <= all_hazards
    assert by_name["rsi-run"]["classification"] == "live_launcher"
    assert by_name["rsi-loop"]["classification"] == "live_launcher"
    assert by_name["rsi-env"]["classification"] == "environment_loader"
    assert by_name["rsi-fix-substrate"]["classification"] == "live_substrate_mutator"
    assert by_name["rsi-update-main"]["classification"] == "repository_mutator"
    assert by_name["rsi-attach"]["classification"] == "tmux_control"
    assert by_name["rsi-stop"]["classification"] == "tmux_control"


def test_legacy_scripts_are_verbatim_non_executable_custody_evidence() -> None:
    inventory = _inventory()

    assert inventory["capture"] == {
        "verbatim": True,
        "content_transformations": [],
    }
    assert all(entry["transformations"] == [] for entry in _entries())
    assert all(
        entry["source_sha256"] == entry["archived_sha256"]
        for entry in _entries()
    )


def test_canonical_launcher_is_never_custodied_as_legacy() -> None:
    canonical_launcher = FORGE_SCRIPT_ROOT / "rsi"

    assert _inventory()["canonical_launcher"] == "scripts/forge_lab/rsi"
    assert not (LEGACY_ROOT / "rsi").exists()
    if canonical_launcher.exists():
        assert canonical_launcher.parent == FORGE_SCRIPT_ROOT
        assert LEGACY_ROOT not in canonical_launcher.parents


def test_versioned_provider_refresh_is_credential_safe_and_spend_bounded() -> None:
    refresh = (FORGE_SCRIPT_ROOT / "rsi-provider-refresh").read_text(encoding="utf-8")
    assert "provider selftest" in refresh
    assert STAGED_FALLBACK_MODELS == ("glm-5.2", "deepseek-v4-pro:cloud")
    assert 'export RSI_LAB_STAGED_MODELS=' not in refresh
    assert "--profile staged" in refresh
    assert "--require-independent-routes 2" in refresh
    assert "--max-probes 6" in refresh
    assert "--min-refresh-interval-s 3000" in refresh
    assert "curl" not in refresh
    assert "Authorization" not in refresh
    assert "API_KEY" not in refresh
    assert "Bearer" not in refresh

    syntax = subprocess.run(
        ["bash", "-n", str(FORGE_SCRIPT_ROOT / "rsi-provider-refresh")],
        capture_output=True,
        check=False,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_unattended_timer_has_one_persistent_daily_utc_admission() -> None:
    timer = (FORGE_SCRIPT_ROOT / "systemd" / "rsi-lab-explore.timer").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 03:35:00 UTC" in timer
    assert "RandomizedDelaySec=25m" in timer
    assert "Persistent=true" in timer
    assert "*:35:00" not in timer


def test_refresh_installer_is_plan_only_by_default_and_retires_legacy_markers() -> None:
    installer = (FORGE_SCRIPT_ROOT / "rsi-provider-refresh-install").read_text(
        encoding="utf-8"
    )
    assert "apply=0" in installer
    assert "--apply" in installer
    assert "--request-id" in installer
    assert "--plan-digest" in installer
    assert "crontab_before_digest" in installer
    assert "ALREADY_APPLIED" in installer
    assert "/rsi-keys-refresh/ { next }" in installer
    assert "/current-main\\/state\\/rsi_runs/ { next }" in installer
    assert "17 * * * *" in installer
    assert 'mv -- "${legacy_script}"' in installer
    assert 'mv -- "${legacy_path}"' in installer
    assert "secret_values_recorded\":false" in installer
    assert "crontab \"${next}\"" in installer

    syntax = subprocess.run(
        ["bash", "-n", str(FORGE_SCRIPT_ROOT / "rsi-provider-refresh-install")],
        capture_output=True,
        check=False,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr


def _refresh_installer_fixture(tmp_path: Path) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cron_store = tmp_path / "crontab.txt"
    crontab = fake_bin / "crontab"
    crontab.write_text(
        """#!/bin/sh
if [ "${1:-}" = "-l" ]; then
    if [ -f "$CRON_STORE" ]; then
        /bin/cat "$CRON_STORE"
        exit 0
    fi
    echo 'no crontab for fixture' >&2
    exit 1
fi
/bin/cp "$1" "$CRON_STORE"
""",
        encoding="utf-8",
    )
    crontab.chmod(0o755)
    home = tmp_path / "home"
    refresh = home / ".dharma" / "bin" / "rsi-provider-refresh"
    refresh.parent.mkdir(parents=True)
    refresh.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    refresh.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "HOME": str(home),
            "CRON_STORE": str(cron_store),
            "RSI_LAB_STATE": str(tmp_path / "state"),
        }
    )
    return env, cron_store


def test_refresh_installer_plan_cas_apply_and_replay(tmp_path: Path) -> None:
    env, cron_store = _refresh_installer_fixture(tmp_path)
    installer = FORGE_SCRIPT_ROOT / "rsi-provider-refresh-install"
    cron_store.write_text(
        "5 * * * * /legacy/rsi-keys-refresh\n",
        encoding="utf-8",
    )
    planned = subprocess.run(
        [str(installer), "--plan"],
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    digest = re.search(r"plan_digest: (sha256:[0-9a-f]{64})", planned.stdout)
    assert planned.returncode == 0, planned.stderr
    assert digest is not None

    command = [
        str(installer),
        "--apply",
        "--plan-digest",
        digest.group(1),
        "--request-id",
        "fixture-refresh-install",
    ]
    applied = subprocess.run(
        command, env=env, capture_output=True, check=False, text=True
    )
    replay = subprocess.run(
        command, env=env, capture_output=True, check=False, text=True
    )

    assert applied.returncode == 0, applied.stderr
    assert "result: APPLIED" in applied.stdout
    assert replay.returncode == 0, replay.stderr
    assert "result: ALREADY_APPLIED" in replay.stdout
    assert cron_store.read_text(encoding="utf-8").count("rsi-provider-refresh") == 1
    receipt_line = next(
        line for line in applied.stdout.splitlines() if line.startswith("receipt: ")
    )
    receipt = json.loads(Path(receipt_line.removeprefix("receipt: ")).read_text())
    assert receipt["schema"] == "rsi_lab.provider_refresh_install.v2"
    assert receipt["plan_digest"] == digest.group(1)
    assert receipt["secret_values_recorded"] is False


def test_refresh_installer_refuses_stale_plan_and_unsafe_state_path(
    tmp_path: Path,
) -> None:
    env, cron_store = _refresh_installer_fixture(tmp_path)
    installer = FORGE_SCRIPT_ROOT / "rsi-provider-refresh-install"
    cron_store.write_text("MAILTO=operator@example.invalid\n", encoding="utf-8")
    planned = subprocess.run(
        [str(installer), "--plan"],
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    digest = re.search(r"plan_digest: (sha256:[0-9a-f]{64})", planned.stdout)
    assert digest is not None
    cron_store.write_text("MAILTO=changed@example.invalid\n", encoding="utf-8")
    stale = subprocess.run(
        [
            str(installer),
            "--apply",
            "--plan-digest",
            digest.group(1),
            "--request-id",
            "stale-refresh-install",
        ],
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert stale.returncode != 0
    assert "plan digest changed" in stale.stderr
    assert cron_store.read_text() == "MAILTO=changed@example.invalid\n"

    env["RSI_LAB_STATE"] = str(tmp_path / "unsafe;injected")
    unsafe = subprocess.run(
        [str(installer), "--plan"],
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert unsafe.returncode != 0
    assert "not canonical shell-safe" in unsafe.stderr
    assert not (tmp_path / "unsafe;injected").exists()
