from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from dharma_swarm.daemon_config import dharma_state_dir, runtime_report_dir


def _send_receipt_payload(
    packet_id: str,
    *,
    target: str = "codex_composer",
    reply_subject: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": packet_id,
        "to": target,
        "target_uid": target,
        "route": "agent-inbox",
        "subject": f"dharma.agent.{target}.inbox",
        "ack_subject": f"dharma.agent.{target}.inbox.ack.{packet_id}",
        "reply_subject": reply_subject
        or f"dharma.agent.{target}.inbox.reply.{packet_id}",
        "file": f"inter_agent/{target}/inbound/{packet_id}.md",
        "sha256": "a" * 64,
    }
    payload.update(overrides)
    return payload


def _write_send_receipt(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_runtime_report_dir_honors_state_authority(monkeypatch, tmp_path: Path) -> None:
    state_root = tmp_path / "runtime-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "lower-priority-home"))

    assert runtime_report_dir("a2a", "send_receipts") == (
        state_root / "reports" / "a2a" / "send_receipts"
    )


def test_state_authority_expands_user_and_normalizes_absolute(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("DHARMA_STATE_DIR", "~/.dharma")

    assert dharma_state_dir("DHARMA_STATE_DIR") == (tmp_path / ".dharma").resolve()
    assert runtime_report_dir() == (tmp_path / ".dharma" / "reports").resolve()


@pytest.mark.parametrize("state_value", [None, ""])
def test_missing_or_empty_state_authority_falls_back_to_dharma_home(
    monkeypatch,
    tmp_path: Path,
    state_value: str | None,
) -> None:
    legacy_home = tmp_path / "legacy-home"
    if state_value is None:
        monkeypatch.delenv("DHARMA_STATE_DIR", raising=False)
    else:
        monkeypatch.setenv("DHARMA_STATE_DIR", state_value)
    monkeypatch.setenv("DHARMA_HOME", str(legacy_home))

    assert dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME") == legacy_home
    assert runtime_report_dir() == legacy_home / "reports"


def test_empty_state_authorities_fall_back_to_user_dharma(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", "")
    monkeypatch.setenv("DHARMA_HOME", "")

    assert dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME") == Path.home() / ".dharma"
    assert runtime_report_dir() == Path.home() / ".dharma" / "reports"


@pytest.mark.parametrize("parts", [("..", "repo"), ("/tmp", "receipts")])
def test_runtime_report_dir_rejects_authority_escape(parts: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="below the Dharma report root"):
        runtime_report_dir(*parts)


def test_runtime_receipt_defaults_are_outside_the_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    state_root = tmp_path / "runtime-state"
    probe = textwrap.dedent(
        """\
        from pathlib import Path

        from api.routers import control_surface
        from dharma_swarm.daemon_config import runtime_report_dir
        from scripts.runtime import (
            a2a_domain_reply_artifact,
            a2a_domain_reply_worker,
            a2a_inbox_bridge,
            a2a_reply_capture,
            a2a_send,
            codex_composer_semantic_inbox_drain,
            codex_composer_semantic_responder,
            model_critic_runner,
            palantir_pilot_a2a_worker,
        )

        report_root = runtime_report_dir()
        repo_root = Path.cwd()
        defaults = (
            a2a_send.DEFAULT_RECEIPT_DIR,
            a2a_inbox_bridge.DEFAULT_RECEIPT_DIR,
            a2a_reply_capture.DEFAULT_SEND_RECEIPT_ROOT,
            a2a_reply_capture.DEFAULT_REPLY_RECEIPT_ROOT,
            a2a_domain_reply_worker.DEFAULT_RECEIPT_DIR,
            a2a_domain_reply_artifact.DEFAULT_ARTIFACT_RECEIPT_DIR,
            codex_composer_semantic_inbox_drain.DEFAULT_DRAIN_RECEIPT_DIR,
            codex_composer_semantic_inbox_drain.DEFAULT_SEMANTIC_RECEIPT_DIR,
            codex_composer_semantic_responder.DEFAULT_SEND_RECEIPT_ROOT,
            model_critic_runner.DEFAULT_OUT_DIR,
            palantir_pilot_a2a_worker.DEFAULT_RECEIPT_DIR,
            control_surface._A2A_SEND_RECEIPT_ROOT,
            control_surface._A2A_INBOX_BRIDGE_RECEIPT_ROOT,
            control_surface._A2A_DOMAIN_REPLY_RECEIPT_ROOT,
            control_surface._A2A_REPLY_RECEIPT_ROOT,
            control_surface._SEMANTIC_RECEIPT_ROOT,
        )

        for path in defaults:
            assert path.is_relative_to(report_root), (path, report_root)
            assert not path.is_relative_to(repo_root), (path, repo_root)
        """
    )
    env = os.environ.copy()
    env.update(
        {
            "DHARMA_STATE_DIR": str(state_root),
            "DHARMA_HOME": str(tmp_path / "lower-priority-home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_default_send_receipt_readers_drain_legacy_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as semantic_responder

    primary_root = tmp_path / "state" / "reports" / "a2a" / "send_receipts"
    legacy_root = tmp_path / "repo" / "reports" / "a2a" / "send_receipts"
    legacy_root.mkdir(parents=True)
    receipt = _send_receipt_payload("packet-legacy")
    legacy_path = legacy_root / "legacy.json"
    legacy_path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(a2a_reply_capture, "DEFAULT_SEND_RECEIPT_ROOT", primary_root)
    monkeypatch.setattr(semantic_responder, "DEFAULT_SEND_RECEIPT_ROOT", primary_root)

    targets = a2a_reply_capture.pending_reply_targets(
        primary_root,
        legacy_send_receipt_root=legacy_root,
    )
    found = semantic_responder.find_send_receipt(
        primary_root,
        agent_uid="codex_composer",
        packet_id="packet-legacy",
        reply_subject="dharma.agent.codex_composer.inbox.reply.packet-legacy",
        legacy_send_receipt_root=legacy_root,
    )

    assert [target.send_receipt_path for target in targets] == [legacy_path]
    assert found == legacy_path
    assert legacy_root.resolve() != a2a_reply_capture.LEGACY_REPO_SEND_RECEIPT_ROOT.resolve()


def test_explicit_send_receipt_root_does_not_inherit_legacy_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as semantic_responder

    default_root = tmp_path / "default"
    explicit_root = tmp_path / "explicit"
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    receipt = _send_receipt_payload("packet-legacy")
    (legacy_root / "legacy.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(a2a_reply_capture, "DEFAULT_SEND_RECEIPT_ROOT", default_root)
    monkeypatch.setattr(semantic_responder, "DEFAULT_SEND_RECEIPT_ROOT", default_root)

    assert not a2a_reply_capture.pending_reply_targets(
        explicit_root,
        legacy_send_receipt_root=legacy_root,
    )
    assert (
        semantic_responder.find_send_receipt(
            explicit_root,
            agent_uid="codex_composer",
            packet_id="packet-legacy",
            reply_subject="dharma.agent.codex_composer.inbox.reply.packet-legacy",
            legacy_send_receipt_root=legacy_root,
        )
        is None
    )
    # CLI callers carry this explicit/default distinction separately, so even
    # spelling the canonical path explicitly cannot opt into legacy authority.
    assert not a2a_reply_capture.pending_reply_targets(
        default_root,
        legacy_send_receipt_root=legacy_root,
        use_legacy_fallback=False,
    )
    assert (
        semantic_responder.find_send_receipt(
            default_root,
            agent_uid="codex_composer",
            packet_id="packet-legacy",
            reply_subject="dharma.agent.codex_composer.inbox.reply.packet-legacy",
            legacy_send_receipt_root=legacy_root,
            use_legacy_fallback=False,
        )
        is None
    )


@pytest.mark.parametrize("authority", ["environment", "cli"])
def test_semantic_responder_runtime_entry_drains_named_previous_release_root(
    monkeypatch,
    tmp_path: Path,
    authority: str,
) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as responder

    packet_id = "packet-previous-release"
    reply_subject = f"dharma.agent.codex_composer.inbox.reply.{packet_id}"
    primary_root = tmp_path / "state" / "reports" / "a2a" / "send_receipts"
    previous_root = tmp_path / "release-previous" / "reports" / "a2a" / "send_receipts"
    previous_path = _write_send_receipt(
        previous_root / "send.json",
        _send_receipt_payload(packet_id, reply_subject=reply_subject),
    )
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    (inbox_dir / "delivery.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": "codex_composer",
                "envelope_sha256": "delivery-sha",
                "envelope": {
                    "packet_id": packet_id,
                    "reply_subject": reply_subject,
                    "target_uid": "codex_composer",
                    "content": "test-only semantic request",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(a2a_reply_capture, "DEFAULT_SEND_RECEIPT_ROOT", primary_root)
    monkeypatch.setattr(responder, "DEFAULT_SEND_RECEIPT_ROOT", primary_root)
    monkeypatch.delenv(a2a_reply_capture.LEGACY_SEND_RECEIPT_ROOT_ENV, raising=False)

    artifact = tmp_path / "outbox" / "reply.json"
    publish_paths: list[Path] = []

    def fake_drain(**_: object) -> dict[str, object]:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("{}\n", encoding="utf-8")
        return {
            "status": "SEMANTIC_INBOX_DRAINED",
            "packet_id": packet_id,
            "domain_reply_artifact_path": str(artifact),
            "semantic_reply_claim": True,
        }

    def fake_publish(**kwargs: object) -> dict[str, object]:
        publish_paths.append(Path(str(kwargs["send_receipt_path"])))
        return {"status": "DOMAIN_REPLY_PUBLISHED"}

    original_run_once = responder.run_once

    def run_once_with_local_effects(**kwargs: object) -> list[dict[str, object]]:
        return original_run_once(
            **kwargs,
            drain_func=fake_drain,
            publish_func=fake_publish,
        )

    monkeypatch.setattr(responder, "run_once", run_once_with_local_effects)
    args = [
        "once",
        "--inbox-dir",
        str(inbox_dir),
        "--state-dir",
        str(tmp_path / "responder-state"),
        "--outbox-root",
        str(tmp_path / "outbox"),
        "--semantic-receipt-dir",
        str(tmp_path / "semantic"),
        "--artifact-receipt-dir",
        str(tmp_path / "artifacts"),
        "--drain-receipt-dir",
        str(tmp_path / "drain"),
        "--domain-reply-receipt-dir",
        str(tmp_path / "domain"),
        "--provider",
        "test",
        "--model",
        "test",
        "--no-canonical-state",
    ]
    if authority == "environment":
        monkeypatch.setenv(
            a2a_reply_capture.LEGACY_SEND_RECEIPT_ROOT_ENV,
            str(previous_root),
        )
    else:
        args.extend(["--legacy-send-receipt-root", str(previous_root)])

    assert responder.main(args) == 0
    assert publish_paths == [previous_path.resolve()]


def test_send_receipt_scan_is_bounded_and_schema_strict(tmp_path: Path) -> None:
    from scripts.runtime import a2a_reply_capture

    root = tmp_path / "send"
    valid = _write_send_receipt(
        root / "valid.json",
        _send_receipt_payload("packet-valid"),
    )
    _write_send_receipt(
        root / "wrong-schema.json",
        _send_receipt_payload(
            "packet-wrong-schema",
            schema_version="dharma.a2a.domain_receipt.v1",
        ),
    )
    _write_send_receipt(
        root / "wildcard.json",
        _send_receipt_payload(
            "packet-wildcard",
            reply_subject="dharma.agent.codex_composer.inbox.reply.*",
        ),
    )
    _write_send_receipt(
        root / "redirect.json",
        _send_receipt_payload(
            "packet-redirect",
            reply_subject="dharma.agent.codex_composer.inbox.reply.someone-else",
        ),
    )
    _write_send_receipt(
        root / "missing-target.json",
        _send_receipt_payload("packet-no-target", to="", target_uid=""),
    )
    outside = _write_send_receipt(
        tmp_path / "outside.json",
        _send_receipt_payload("packet-symlink"),
    )
    (root / "symlink.json").symlink_to(outside)
    nested = _write_send_receipt(
        root / "nested" / "nested.json",
        _send_receipt_payload("packet-nested"),
    )
    oversized = root / "oversized.json"
    oversized.write_text(
        json.dumps(
            _send_receipt_payload(
                "packet-oversized",
                padding="x" * a2a_reply_capture.MAX_SEND_RECEIPT_BYTES,
            )
        ),
        encoding="utf-8",
    )

    targets = a2a_reply_capture.pending_reply_targets(
        root,
        use_legacy_fallback=False,
    )

    assert [target.send_receipt_path for target in targets] == [valid]
    assert nested not in [target.send_receipt_path for target in targets]


def test_identical_migration_copy_deduplicates_to_primary(tmp_path: Path) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as responder

    primary = tmp_path / "primary"
    legacy = tmp_path / "legacy"
    receipt = _send_receipt_payload("packet-copy")
    primary_path = _write_send_receipt(primary / "primary.json", receipt)
    _write_send_receipt(legacy / "legacy.json", receipt)
    reply_subject = str(receipt["reply_subject"])

    targets = a2a_reply_capture.pending_reply_targets(
        primary,
        legacy_send_receipt_root=legacy,
        use_legacy_fallback=True,
    )
    found = responder.find_send_receipt(
        primary,
        agent_uid="codex_composer",
        packet_id="packet-copy",
        reply_subject=reply_subject,
        legacy_send_receipt_root=legacy,
        use_legacy_fallback=True,
    )

    assert [target.send_receipt_path for target in targets] == [primary_path]
    assert found == primary_path


def test_conflicting_migration_copy_fails_closed(tmp_path: Path) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as responder

    primary = tmp_path / "primary"
    legacy = tmp_path / "legacy"
    receipt = _send_receipt_payload("packet-collision")
    _write_send_receipt(primary / "primary.json", receipt)
    _write_send_receipt(
        legacy / "legacy.json",
        {**receipt, "to": "codex-composer-alias"},
    )
    reply_subject = str(receipt["reply_subject"])

    with pytest.raises(
        a2a_reply_capture.SendReceiptCollisionError,
        match="conflicting A2A send receipts",
    ):
        a2a_reply_capture.pending_reply_targets(
            primary,
            legacy_send_receipt_root=legacy,
            use_legacy_fallback=True,
        )
    with pytest.raises(a2a_reply_capture.SendReceiptCollisionError):
        responder.find_send_receipt(
            primary,
            agent_uid="codex_composer",
            packet_id="packet-collision",
            reply_subject=reply_subject,
            legacy_send_receipt_root=legacy,
            use_legacy_fallback=True,
        )


@pytest.mark.parametrize("invalid_kind", ["wrong-schema", "symlink", "oversized"])
def test_invalid_primary_copy_cannot_fall_through_to_legacy(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    from scripts.runtime import a2a_reply_capture
    from scripts.runtime import codex_composer_semantic_responder as responder

    packet_id = "packet-shadow"
    receipt = _send_receipt_payload(packet_id)
    primary = tmp_path / "primary"
    legacy = tmp_path / "legacy"
    primary.mkdir()
    legacy_path = _write_send_receipt(legacy / f"{packet_id}.json", receipt)
    primary_path = primary / legacy_path.name
    if invalid_kind == "wrong-schema":
        _write_send_receipt(
            primary_path,
            {**receipt, "schema_version": "dharma.a2a.domain_receipt.v1"},
        )
    elif invalid_kind == "symlink":
        outside = _write_send_receipt(tmp_path / "outside-shadow.json", receipt)
        primary_path.symlink_to(outside)
    else:
        _write_send_receipt(
            primary_path,
            {
                **receipt,
                "padding": "x" * a2a_reply_capture.MAX_SEND_RECEIPT_BYTES,
            },
        )

    with pytest.raises(
        a2a_reply_capture.SendReceiptCollisionError,
        match="invalid primary A2A send receipt shadows legacy candidate",
    ):
        a2a_reply_capture.pending_reply_targets(
            primary,
            legacy_send_receipt_root=legacy,
            use_legacy_fallback=True,
        )
    with pytest.raises(a2a_reply_capture.SendReceiptCollisionError):
        responder.find_send_receipt(
            primary,
            agent_uid="codex_composer",
            packet_id=packet_id,
            reply_subject=str(receipt["reply_subject"]),
            legacy_send_receipt_root=legacy,
            use_legacy_fallback=True,
        )


def test_legacy_send_receipt_authority_must_be_absolute(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from scripts.runtime import a2a_reply_capture

    monkeypatch.setattr(
        a2a_reply_capture,
        "DEFAULT_SEND_RECEIPT_ROOT",
        tmp_path / "primary",
    )
    monkeypatch.setenv(
        a2a_reply_capture.LEGACY_SEND_RECEIPT_ROOT_ENV,
        "relative/legacy-root",
    )

    with pytest.raises(ValueError, match="absolute directory"):
        a2a_reply_capture.pending_reply_targets(tmp_path / "primary")
