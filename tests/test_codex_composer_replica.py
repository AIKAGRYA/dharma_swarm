from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/runtime/codex_composer_replica.py"
sys.path.insert(0, str(MODULE_PATH.parent))
seat = importlib.import_module("codex_composer_seat")

SPEC = importlib.util.spec_from_file_location("codex_composer_replica", MODULE_PATH)
assert SPEC and SPEC.loader
replica = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replica
SPEC.loader.exec_module(replica)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config(
    tmp_path: Path,
    *,
    instance: str = "meghadharma",
    role: str = "orientation_primary",
    canonical: bool = True,
):
    card = ROOT / "examples/agents/codex_composer.agent-card.json"
    memory = ROOT / "examples/agents/codex_composer.memory.json"
    workspace = tmp_path / "repo"
    workspace.mkdir(exist_ok=True)
    return replica.ReplicaConfig(
        instance_id=instance,
        replica_role=role,
        nats_url=(
            "nats://127.0.0.1:4222"
            if instance == "meghadharma"
            else "wss://hub.example:9443"
        ),
        nats_user=replica.EXPECTED_NATS_USERS[instance],
        nats_password="test-only-password",
        card_path=card,
        card_sha256=_digest(card),
        memory_path=memory,
        memory_sha256=_digest(memory),
        workspace=workspace,
        codex_bin="codex",
        tmux_session="codex_composer",
        state_dir=tmp_path / "state",
        interval_seconds=20,
        publish_canonical_presence=canonical,
    )


def test_config_redacts_password_and_rejects_identity_drift(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert "test-only-password" not in repr(config)

    with pytest.raises(replica.ReplicaConfigurationError, match="transport principal"):
        replica.ReplicaConfig(
            **{
                **{name: getattr(config, name) for name in config.__dataclass_fields__},
                "nats_user": "other-agent",
            }
        )
    with pytest.raises(replica.ReplicaConfigurationError, match="embedded"):
        replica.ReplicaConfig(
            **{
                **{name: getattr(config, name) for name in config.__dataclass_fields__},
                "nats_url": "nats://codex_composer:secret@hub.example:4222",
            }
        )


@pytest.mark.parametrize(
    ("instance", "role", "canonical"),
    [
        ("agni", "delivery_relay", False),
        ("rushabdev", "hot_standby", False),
        ("meghadharma", "orientation_primary", True),
    ],
)
def test_bundle_integrity_accepts_only_versioned_topology(
    tmp_path: Path, instance: str, role: str, canonical: bool
) -> None:
    config = _config(tmp_path, instance=instance, role=role, canonical=canonical)
    integrity = replica.validate_bundle(config)

    assert len(integrity.bundle_sha256) == 64
    assert integrity.canonical_presence_instance == "meghadharma"


def test_bundle_integrity_fails_closed_on_hash_or_primary_drift(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(replica.ReplicaConfigurationError, match="publisher"):
        replica.validate_bundle(
            replica.ReplicaConfig(
                **{
                    **{name: getattr(config, name) for name in config.__dataclass_fields__},
                    "publish_canonical_presence": False,
                }
            )
        )

    copied = tmp_path / "card.json"
    copied.write_bytes(config.card_path.read_bytes() + b"\n")
    with pytest.raises(replica.ReplicaConfigurationError, match="card sha256"):
        replica.validate_bundle(
            replica.ReplicaConfig(
                **{
                    **{name: getattr(config, name) for name in config.__dataclass_fields__},
                    "card_path": copied,
                }
            )
        )


def test_replica_and_canonical_envelopes_preserve_authority_boundary(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    integrity = replica.validate_bundle(config)
    seat = replica.SeatStatus(
        True,
        "ready",
        "codex_composer",
        seat_user="codex-composer-seat",
        pane_command="codex",
        codex_version="codex-cli 0.144.5",
        contract_sha256="b" * 64,
        workspace=str(tmp_path / "repo"),
    )
    observed = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)

    instance = replica.build_replica_envelope(
        config,
        integrity,
        seat,
        observed_at=observed,
        boot_id="a" * 32,
        sequence=7,
    )
    presence = replica.build_canonical_presence_envelope(
        config,
        integrity,
        seat,
        observed_at=observed,
        boot_id="a" * 32,
        sequence=7,
    )

    assert instance["subject"] == (
        "dharma.a2a.codex_composer.replica.meghadharma.heartbeat"
    )
    assert instance["payload"]["instance_id"] == "meghadharma"
    assert instance["payload"]["semantic_consumer_enabled"] is False
    assert instance["payload"]["execution_lease_active"] is False
    assert presence["subject"] == "dharma.agent.codex_composer.presence"
    assert presence["payload"]["schema"] == "dharma.a2a.fleet_heartbeat.v1"
    assert presence["payload"]["metadata"]["instance_id"] == "meghadharma"
    assert presence["payload"]["metadata"]["semantic_consumer_enabled"] is False
    assert json.loads(replica.canonical_bytes(presence)) == presence


def test_tmux_launch_command_is_read_only_and_contains_no_nats_secret(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    command = seat.codex_tmux_command(config, "/usr/local/bin/codex")
    rendered = " ".join(command)

    assert command[:5] == ["tmux", "new-session", "-d", "-s", "codex_composer"]
    assert "-s read-only" in rendered
    assert "-a on-request" in rendered
    assert "test-only-password" not in rendered
    assert "do not consume NATS tasks" in rendered


def test_seat_environment_excludes_nats_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    account = type("Account", (), {"pw_dir": str(tmp_path / "seat-home")})
    monkeypatch.setattr(seat.pwd, "getpwnam", lambda _: account)

    seat_env = seat._seat_env(config)

    assert "CODEX_COMPOSER_NATS_PASSWORD" not in seat_env
    assert "test-only-password" not in json.dumps(seat_env)
    assert seat_env["HOME"] == str(tmp_path / "seat-home")
    assert not seat.seat_environment_contains_secret(config)


def test_ensure_seat_adopts_only_matching_contract_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(seat.shutil, "which", lambda _: "/usr/local/bin/codex")
    account = type("Account", (), {"pw_dir": str(tmp_path / "seat-home")})
    monkeypatch.setattr(seat.pwd, "getpwnam", lambda _: account)
    calls: list[list[str]] = []
    integrity = replica.validate_bundle(config)
    marker = seat.seat_contract_sha256(config, integrity, "/usr/local/bin/codex")

    def fake_run(args: list[str], *, timeout: float = 15, env=None):
        calls.append(args)
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, "codex-cli 0.144.5\n", "")
        if "has-session" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        if "show-option" in args:
            return subprocess.CompletedProcess(args, 0, marker + "\n", "")
        return subprocess.CompletedProcess(
            args, 0, f"codex\t{config.workspace}\n", ""
        )

    monkeypatch.setattr(seat, "_run", fake_run)
    status = seat.ensure_seat(config, integrity)

    assert status.ready
    assert status.pane_command == "codex"
    assert not any("login" in call for call in calls)


def test_ensure_seat_rejects_unmarked_existing_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    integrity = replica.validate_bundle(config)
    monkeypatch.setattr(seat.shutil, "which", lambda _: "/usr/local/bin/codex")
    account = type("Account", (), {"pw_dir": str(tmp_path / "seat-home")})
    monkeypatch.setattr(seat.pwd, "getpwnam", lambda _: account)

    def fake_run(args: list[str], *, timeout: float = 15, env=None):
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, "codex-cli 0.144.5\n", "")
        if "has-session" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        if "show-option" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(
            args, 0, f"node\t{config.workspace}\n", ""
        )

    monkeypatch.setattr(seat, "_run", fake_run)

    status = seat.ensure_seat(config, integrity)

    assert not status.ready
    assert status.state == "tmux_present_unverified"


def test_receipt_rotation_is_bounded(tmp_path: Path) -> None:
    receipt = tmp_path / "receipts.jsonl"
    receipt.write_text("old\n", encoding="utf-8")
    replica._rotate_receipts(receipt, max_bytes=1, generations=2)

    assert not receipt.exists()
    assert (tmp_path / "receipts.jsonl.1").read_text(encoding="utf-8") == "old\n"

    receipt.write_text("new\n", encoding="utf-8")
    replica._rotate_receipts(receipt, max_bytes=1, generations=2)

    assert (tmp_path / "receipts.jsonl.1").read_text(encoding="utf-8") == "new\n"
    assert (tmp_path / "receipts.jsonl.2").read_text(encoding="utf-8") == "old\n"
