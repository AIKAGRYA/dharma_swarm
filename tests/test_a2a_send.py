import asyncio
import json
import os
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dharma_swarm.runtime_state import RuntimeStateStore
from scripts.runtime import pr_merge_control
from scripts.runtime import a2a_send


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "state"))


def _write_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "packet.md"
    packet.write_text("hello devin\n", encoding="utf-8")
    return packet


def test_build_envelope_shape(tmp_path):
    packet = _write_packet(tmp_path)
    env = a2a_send.build_envelope(
        to="devin", file_path=packet, sender="operator", kind="fleet.packet", packet_id="abc123"
    )
    assert env["schema_version"] == "dharma.a2a.send.v1"
    assert env["subject"] == "dharma.a2a.devin"
    assert env["ack_subject"] == "dharma.a2a.devin.ack.abc123"
    assert env["reply_subject"] == "dharma.a2a.devin.reply.abc123"
    assert env["to"] == "devin-roaming-2987d222"
    assert env["content"] == "hello devin\n"
    assert len(env["sha256"]) == 64


def test_build_envelope_generic_agent(tmp_path):
    packet = _write_packet(tmp_path)
    env = a2a_send.build_envelope(
        to="codex", file_path=packet, sender="operator", kind="fleet.packet", packet_id="x"
    )
    assert env["subject"] == "dharma.a2a.codex"
    assert env["to"] == "codex"
    assert env["route"] == "a2a"


def test_build_envelope_agent_inbox_route(tmp_path):
    packet = _write_packet(tmp_path)
    env = a2a_send.build_envelope(
        to="hermes",
        file_path=packet,
        sender="operator",
        kind="fleet.packet",
        packet_id="abc123",
        route=a2a_send.ROUTE_AGENT_INBOX,
    )
    assert env["subject"] == "dharma.agent.hermes-m5.inbox"
    assert env["ack_subject"] == "dharma.agent.hermes-m5.inbox.ack.abc123"
    assert env["reply_subject"] == "dharma.agent.hermes-m5.inbox.reply.abc123"
    assert env["to"] == "hermes-m5"
    assert env["target_uid"] == "hermes-m5"
    assert env["route"] == "agent-inbox"


def test_build_envelope_agent_inbox_allows_uid_override(tmp_path):
    packet = _write_packet(tmp_path)
    env = a2a_send.build_envelope(
        to="worker",
        file_path=packet,
        sender="operator",
        kind="fleet.packet",
        packet_id="abc123",
        route=a2a_send.ROUTE_AGENT_INBOX,
        agent_uid="worker_01",
    )
    assert env["subject"] == "dharma.agent.worker_01.inbox"
    assert env["to"] == "worker_01"


def test_agent_inbox_rejects_unsafe_uid(tmp_path):
    packet = _write_packet(tmp_path)
    try:
        a2a_send.build_envelope(
            to="bad.agent",
            file_path=packet,
            sender="operator",
            kind="fleet.packet",
            packet_id="abc123",
            route=a2a_send.ROUTE_AGENT_INBOX,
        )
    except ValueError as exc:
        assert "invalid agent uid" in str(exc)
    else:
        raise AssertionError("expected unsafe agent uid to be rejected")


def test_write_receipt(tmp_path):
    receipt = {"to": "devin", "packet_id": "abc123", "status": "PUBLISH_ACKED"}
    path = a2a_send.write_receipt(tmp_path / "receipts", receipt)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "PUBLISH_ACKED"


def test_write_receipt_preserves_concurrent_same_stamp(tmp_path, monkeypatch):
    monkeypatch.setattr(a2a_send, "stamp", lambda: "20260611T000000Z")
    receipt = {"to": "devin", "packet_id": "abc123", "status": "PUBLISH_ACKED"}
    receipt_dir = tmp_path / "receipts"

    with ThreadPoolExecutor(max_workers=12) as executor:
        paths = list(
            executor.map(
                lambda _: a2a_send.write_receipt(receipt_dir, dict(receipt)),
                range(12),
            )
        )

    assert len(set(paths)) == 12
    assert len(list(receipt_dir.glob("*.json"))) == 12


def test_publish_and_wait_does_not_core_republish_after_ambiguous_jetstream_error(monkeypatch):
    class FakeSubscription:
        async def unsubscribe(self):
            return None

    class FakeJetStream:
        async def publish(self, *_args, **_kwargs):
            raise TimeoutError("pub ack timed out")

    class FakeConnection:
        def __init__(self):
            self.core_publish_calls = 0
            self.closed = False

        async def subscribe(self, *_args, **_kwargs):
            return FakeSubscription()

        def jetstream(self):
            return FakeJetStream()

        async def publish(self, *_args, **_kwargs):
            self.core_publish_calls += 1

        async def flush(self, **_kwargs):
            return None

        async def close(self):
            self.closed = True

    conn = FakeConnection()

    async def fake_connect(**_kwargs):
        return conn

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=fake_connect))
    envelope = {
        "subject": "dharma.a2a.devin",
        "ack_subject": "dharma.a2a.devin.ack.abc123",
        "reply_subject": "dharma.a2a.devin.reply.abc123",
        "packet_id": "abc123",
    }
    config = a2a_send.NATSConfig(
        endpoint="nats://127.0.0.1:4222",
        user="",
        credential="",
        missing=(),
    )

    result = asyncio.run(
        a2a_send._publish_and_wait(  # noqa: SLF001
            config,
            envelope,
            wait_s=0.0,
            timeout_s=0.1,
        )
    )

    assert result["status"] == a2a_send.STATUS_PUBLISH_FAILED
    assert result["transport_ack"] == "JETSTREAM_PUB_ACK_AMBIGUOUS"
    assert conn.core_publish_calls == 0
    assert conn.closed is True


def test_nats_config_leaves_plaintext_nats_without_bundled_ca(tmp_path, monkeypatch):
    bundled = tmp_path / "agni-ws-ca.pem"
    bundled.write_text("BUNDLED-CA", encoding="utf-8")
    monkeypatch.setattr(pr_merge_control, "DEFAULT_NATS_CA_PEM_PATH", bundled)
    monkeypatch.delenv("DEVIN_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("DHARMA_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("NATS_CA_PEM", raising=False)

    config = pr_merge_control._nats_config(  # noqa: SLF001
        {
            "NATS_URL": "nats://127.0.0.1:4222",
            "NATS_USER": "devin",
            "NATS_PASSWORD": "secret",
        },
        require_devin_secrets=False,
    )

    assert config.ca_pem == ""
    assert config.credential_family == "direct"


def test_nats_config_uses_bundled_ca_fallback_for_tls_urls(tmp_path, monkeypatch):
    bundled = tmp_path / "agni-ws-ca.pem"
    bundled.write_text("BUNDLED-CA", encoding="utf-8")
    monkeypatch.setattr(pr_merge_control, "DEFAULT_NATS_CA_PEM_PATH", bundled)
    monkeypatch.delenv("DEVIN_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("DHARMA_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("NATS_CA_PEM", raising=False)

    config = pr_merge_control._nats_config(  # noqa: SLF001
        {
            "NATS_URL": "wss://127.0.0.1:4222",
            "NATS_USER": "devin",
            "NATS_PASSWORD": "secret",
        },
        require_devin_secrets=False,
    )

    assert config.ca_pem == "BUNDLED-CA\n"


def test_nats_config_prefers_explicit_ca_env_over_bundled(tmp_path, monkeypatch):
    bundled = tmp_path / "agni-ws-ca.pem"
    bundled.write_text("BUNDLED-CA", encoding="utf-8")
    monkeypatch.setattr(pr_merge_control, "DEFAULT_NATS_CA_PEM_PATH", bundled)

    config = pr_merge_control._nats_config(  # noqa: SLF001
        {
            "NATS_URL": "nats://127.0.0.1:4222",
            "NATS_USER": "devin",
            "NATS_PASSWORD": "secret",
            "NATS_CA_PEM": "EXPLICIT-CA",
        },
        require_devin_secrets=False,
    )

    assert config.ca_pem == "EXPLICIT-CA\n"


def test_publish_and_wait_marks_permissions_denied_and_closes_connection(monkeypatch):
    class FakeSubscription:
        def __init__(self):
            self.unsubscribed = False

        async def unsubscribe(self):
            self.unsubscribed = True

    class FakeJetStream:
        def __init__(self, conn):
            self.conn = conn

        async def publish(self, subject, _data, timeout=None):
            await self.conn.error_cb(
                Exception(f"nats: permissions violation for publish to {subject}")
            )
            raise TimeoutError("pub ack timed out")

    class FakeConnection:
        def __init__(self):
            self.closed = False
            self.error_cb = None

        async def subscribe(self, *_args, **_kwargs):
            return FakeSubscription()

        def jetstream(self):
            return FakeJetStream(self)

        async def close(self):
            self.closed = True

    conn = FakeConnection()

    async def fake_connect(**kwargs):
        conn.error_cb = kwargs["error_cb"]
        return conn

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=fake_connect))
    envelope = {
        "subject": "dharma.a2a.perplexity",
        "ack_subject": "dharma.a2a.perplexity.ack.abc123",
        "reply_subject": "dharma.a2a.perplexity.reply.abc123",
        "packet_id": "abc123",
    }
    config = a2a_send.NATSConfig(
        endpoint="nats://127.0.0.1:4222",
        user="devin",
        credential="secret",
        missing=(),
    )

    result = asyncio.run(
        a2a_send._publish_and_wait(  # noqa: SLF001
            config,
            envelope,
            wait_s=0.0,
            timeout_s=0.1,
        )
    )

    assert result["status"] == a2a_send.STATUS_PERMISSIONS_DENIED
    assert "broker rejected publish to dharma.a2a.perplexity" in result["error"]
    assert result["permissions_denied_detail"] == result["error"]
    assert conn.closed is True


def test_publish_and_wait_ignores_subscribe_permission_violation(monkeypatch):
    class FakeSubscription:
        async def unsubscribe(self):
            return None

    class FakeJetStream:
        async def publish(self, subject, _data, timeout=None):
            await conn.error_cb(
                Exception(
                    f'nats: permissions violation for subscription to "{subject}.ack"'
                )
            )
            raise TimeoutError("pub ack timed out")

    class FakeConnection:
        def __init__(self):
            self.closed = False
            self.error_cb = None

        async def subscribe(self, *_args, **_kwargs):
            return FakeSubscription()

        def jetstream(self):
            return FakeJetStream()

        async def close(self):
            self.closed = True

    conn = FakeConnection()

    async def fake_connect(**kwargs):
        conn.error_cb = kwargs["error_cb"]
        return conn

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=fake_connect))
    envelope = {
        "subject": "dharma.a2a.perplexity",
        "ack_subject": "dharma.a2a.perplexity.ack.abc123",
        "reply_subject": "dharma.a2a.perplexity.reply.abc123",
        "packet_id": "abc123",
    }
    config = a2a_send.NATSConfig(
        endpoint="nats://127.0.0.1:4222",
        user="devin",
        credential="secret",
        missing=(),
    )

    result = asyncio.run(
        a2a_send._publish_and_wait(  # noqa: SLF001
            config,
            envelope,
            wait_s=0.0,
            timeout_s=0.1,
        )
    )

    assert result["status"] == a2a_send.STATUS_PUBLISH_FAILED
    assert result["permissions_denied_detail"] is None
    assert result["error"] == "TimeoutError"
    assert conn.closed is True


def test_main_secrets_missing(tmp_path, monkeypatch, capsys):
    for name in list(os.environ):
        if "NATS" in name:
            monkeypatch.delenv(name, raising=False)
    packet = _write_packet(tmp_path)
    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )
    assert code == 3
    out = capsys.readouterr().out
    assert "a2a_send: <recorded>" in out
    assert "packet_id=" not in out
    assert "subject=" not in out
    assert str(tmp_path) not in out
    assert "receipt: <written>" in out
    receipts = list((tmp_path / "r").glob("*.json"))
    assert len(receipts) == 1
    body = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert body["status"] == "NATS_SECRETS_MISSING"
    assert body["ack_tier"] is None
    assert body["contact_evidence_tier"] == "NO_CONTACT"
    assert body["live_contact_claim"] is False
    assert body["collaboration_claim"] == "none"


def test_main_missing_file(tmp_path):
    code = a2a_send.main(
        ["--to", "devin", "--file", str(tmp_path / "nope.md"), "--receipt-dir", str(tmp_path)]
    )
    assert code == 2


def test_main_json_console_redacts_subjects_and_paths(tmp_path, monkeypatch, capsys):
    for name in list(os.environ):
        if "NATS" in name:
            monkeypatch.delenv(name, raising=False)
    packet = _write_packet(tmp_path)
    code = a2a_send.main(
        [
            "--to",
            "devin",
            "--file",
            str(packet),
            "--receipt-dir",
            str(tmp_path / "r"),
            "--json",
        ]
    )
    assert code == 3
    console_body = json.loads(capsys.readouterr().out)
    assert console_body["packet_id"] == "<redacted>"
    assert console_body["status"] == "<recorded>"
    assert console_body["subject"] == "<redacted>"
    assert console_body["ack_subject"] == "<redacted>"
    assert console_body["reply_subject"] == "<redacted>"
    assert console_body["file"] == "<redacted>"
    assert console_body["receipt_path"] == "<written>"

    receipts = list((tmp_path / "r").glob("*.json"))
    assert len(receipts) == 1
    stored_body = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert stored_body["subject"] == "dharma.a2a.devin"


def test_main_nats_client_missing_is_specific(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    monkeypatch.setattr(a2a_send.shutil, "which", lambda name: None)

    async def missing_client(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'nats'", name="nats")

    monkeypatch.setattr(a2a_send, "_publish_and_wait", missing_client)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 4
    out = capsys.readouterr().out
    assert "a2a_send: <recorded>" in out
    assert "NATS_CLIENT_MISSING" not in out
    assert "packet_id=" not in out
    assert "subject=" not in out
    assert str(tmp_path) not in out
    assert "receipt: <written>" in out
    receipts = list((tmp_path / "r").glob("*.json"))
    assert len(receipts) == 1
    body = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert body["status"] == "NATS_CLIENT_MISSING"
    assert body["ack_tier"] is None
    assert body["contact_evidence_tier"] == "NO_CONTACT"
    assert body["live_contact_claim"] is False
    assert body["collaboration_claim"] == "none"
    assert "python_client_error" in body


def test_main_permissions_denied_records_receipt_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")

    async def denied(*_args, **_kwargs):
        return {
            "status": a2a_send.STATUS_PERMISSIONS_DENIED,
            "ack_tier": None,
            "consumed": False,
            "replied": False,
            "reply_payload": None,
            "permissions_denied_detail": (
                "broker rejected publish to dharma.a2a.perplexity: the devin NATS credential "
                "is not authorized to publish to this lane (server-side ACL)"
            ),
            "error": (
                "broker rejected publish to dharma.a2a.perplexity: the devin NATS credential "
                "is not authorized to publish to this lane (server-side ACL)"
            ),
        }

    monkeypatch.setattr(a2a_send, "_publish_and_wait", denied)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "perplexity", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 1
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == a2a_send.STATUS_PERMISSIONS_DENIED
    assert receipt["permissions_denied_detail"].startswith("broker rejected publish to dharma.a2a.perplexity")
    assert receipt["contact_evidence_tier"] == "NO_CONTACT"
    assert receipt["live_contact_claim"] is False


def test_main_nats_client_missing_uses_cli_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    monkeypatch.setenv("NATS_USER", "fleet")
    monkeypatch.setenv("NATS_PASSWORD", "super-secret")
    monkeypatch.setattr(a2a_send.shutil, "which", lambda name: "/opt/homebrew/bin/nats")

    async def missing_client(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'nats'", name="nats")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})

        class Proc:
            returncode = 0
            stdout = 'Published 424 bytes to "dharma.a2a.devin"\n'
            stderr = ""

        return Proc()

    monkeypatch.setattr(a2a_send, "_publish_and_wait", missing_client)
    monkeypatch.setattr(a2a_send.subprocess, "run", fake_run)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 0
    assert calls
    call = calls[0]
    assert call["cmd"][-1] == "dharma.a2a.devin"
    assert "--jetstream" in call["cmd"]
    assert "--force-stdin" in call["cmd"]
    assert "super-secret" not in " ".join(call["cmd"])
    assert call["env"]["NATS_PASSWORD"] == "super-secret"
    assert "NATS_COLOR" not in call["env"]
    assert "hello devin" in call["input"]

    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == "PUBLISH_ACKED"
    assert receipt["runtime_truth_ref"]["receipt_id"].startswith("rr_run_a2a_send_")
    assert receipt["ack_tier"] == "PUBLISH_ACCEPTED"
    assert receipt["transport_ack"] == "NATS_CLI_JETSTREAM_PUB_ACK"
    assert receipt["cli_fallback_used"] is True
    assert receipt["contact_evidence_tier"] == "PUBLISH_ACCEPTED"
    assert receipt["live_contact_claim"] is False
    assert receipt["collaboration_claim"] == "publish_only"
    assert "super-secret" not in json.dumps(receipt)


def test_main_cli_fallback_can_publish_agent_inbox_route(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    monkeypatch.setattr(a2a_send.shutil, "which", lambda name: "/opt/homebrew/bin/nats")

    async def missing_client(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'nats'", name="nats")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})

        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return Proc()

    monkeypatch.setattr(a2a_send, "_publish_and_wait", missing_client)
    monkeypatch.setattr(a2a_send.subprocess, "run", fake_run)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        [
            "--to",
            "hermes",
            "--route",
            "agent-inbox",
            "--file",
            str(packet),
            "--receipt-dir",
            str(tmp_path / "r"),
        ]
    )

    assert code == 0
    assert calls[0]["cmd"][-1] == "dharma.agent.hermes-m5.inbox"
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["route"] == "agent-inbox"
    assert receipt["target_uid"] == "hermes-m5"
    assert receipt["subject"] == "dharma.agent.hermes-m5.inbox"
    assert receipt["ack_tier"] == "PUBLISH_ACCEPTED"
    assert receipt["live_contact_claim"] is False


def test_main_nats_cli_fallback_failure_is_publish_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    monkeypatch.setattr(a2a_send.shutil, "which", lambda name: "/opt/homebrew/bin/nats")

    async def missing_client(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'nats'", name="nats")

    def fake_run(cmd, **kwargs):
        class Proc:
            returncode = 1
            stdout = ""
            stderr = "nats: no responders"

        return Proc()

    monkeypatch.setattr(a2a_send, "_publish_and_wait", missing_client)
    monkeypatch.setattr(a2a_send.subprocess, "run", fake_run)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 1
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == "PUBLISH_FAILED"
    assert receipt["ack_tier"] is None
    assert receipt["contact_evidence_tier"] == "NO_CONTACT"
    assert receipt["live_contact_claim"] is False
    assert "python_client_error" in receipt


def test_main_publish_only_is_not_live_collaboration(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")

    async def publish_only(*args, **kwargs):
        return {
            "status": a2a_send.STATUS_PUBLISH_ACKED,
            "ack_tier": a2a_send.ACK_TIER_PUBLISH_ACCEPTED,
            "transport_ack": "JETSTREAM_PUB_ACK",
            "stream": "DHARMA_A2A",
            "seq": 42,
            "consumed": False,
            "replied": False,
            "reply_payload": None,
        }

    monkeypatch.setattr(a2a_send, "_publish_and_wait", publish_only)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 0
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["ack_tier"] == "PUBLISH_ACCEPTED"
    assert receipt["transport_ack"] == "JETSTREAM_PUB_ACK"
    assert receipt["contact_evidence_tier"] == "PUBLISH_ACCEPTED"
    assert receipt["live_contact_claim"] is False
    assert receipt["collaboration_claim"] == "publish_only"
    assert receipt["runtime_truth_ref"]["spine_evidence_receipt_ref"]["operation"] == "a2a_send.publish"


def test_main_publish_runtime_receipt_associates_spine_evidence_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")

    async def publish_only(*args, **kwargs):
        return {
            "status": a2a_send.STATUS_PUBLISH_ACKED,
            "ack_tier": a2a_send.ACK_TIER_PUBLISH_ACCEPTED,
            "transport_ack": "JETSTREAM_PUB_ACK",
            "stream": "DHARMA_A2A",
            "seq": 42,
            "consumed": False,
            "replied": False,
            "reply_payload": None,
        }

    monkeypatch.setattr(a2a_send, "_publish_and_wait", publish_only)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 0
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    evidence_ref = receipt["spine_evidence_receipt_ref"]
    assert evidence_ref["operation"] == "a2a_send.publish"
    assert receipt["runtime_truth_ref"]["spine_evidence_receipt_ref"] == evidence_ref

    store = RuntimeStateStore(tmp_path / "state" / "runtime.db")
    runtime_receipts = asyncio.run(store.list_runtime_receipts(receipt_type="a2a_send"))
    assert len(runtime_receipts) == 1
    runtime_receipt = runtime_receipts[0]
    payload = runtime_receipt.payload
    evidence = payload["spine_evidence_receipt"]
    assert payload["spine_evidence_receipt_ref"] == evidence_ref
    assert evidence["receipt_id"] == evidence_ref["receipt_id"]
    assert evidence["operation"] == "a2a_send.publish"
    assert evidence["status"] == "ok"
    assert evidence["trace_id"] == runtime_receipt.trace_id
    assert evidence["span_id"] == runtime_receipt.run_id
    assert evidence["attributes"]["correlation_id"] == runtime_receipt.correlation_id
    assert evidence["attributes"]["idempotency_key"] == runtime_receipt.idempotency_key
    assert evidence["attributes"]["side_effect_key"] == runtime_receipt.side_effect_key

    dispatch_evidence = asyncio.run(store.list_runtime_receipts(receipt_type="dispatch_evidence"))
    assert dispatch_evidence == []


def test_main_runtime_warrant_denial_blocks_publish(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    calls = 0

    def deny_warrant(*_args, **_kwargs):
        raise a2a_send.RuntimeWarrantDenied("blocked by test warrant")

    async def publish_only(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            "status": a2a_send.STATUS_PUBLISH_ACKED,
            "ack_tier": a2a_send.ACK_TIER_PUBLISH_ACCEPTED,
        }

    monkeypatch.setattr(a2a_send, "_issue_runtime_warrant_for_publish", deny_warrant)
    monkeypatch.setattr(a2a_send, "_publish_and_wait", publish_only)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 1
    assert calls == 0
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == "PUBLISH_FAILED"
    assert "RuntimeWarrantDenied" in receipt["error"]
    assert receipt["contact_evidence_tier"] == "NO_CONTACT"
    assert receipt["spine_evidence_receipt_ref"]["status"] == "dropped"

    store = RuntimeStateStore(tmp_path / "state" / "runtime.db")
    runtime_receipts = asyncio.run(store.list_runtime_receipts(receipt_type="a2a_send"))
    assert len(runtime_receipts) == 1
    evidence = runtime_receipts[0].payload["spine_evidence_receipt"]
    assert evidence["status"] == "dropped"
    assert evidence["error_source"] == "guardrail_blocked"


def test_main_handler_ack_is_live_contact(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")

    async def handler_ack(*args, **kwargs):
        return {
            "status": "DEVIN_CONSUMED",
            "ack_tier": a2a_send.ACK_TIER_HANDLER_ACKED,
            "transport_ack": "JETSTREAM_PUB_ACK",
            "stream": "DHARMA_A2A",
            "seq": 43,
            "consumed": True,
            "replied": False,
            "reply_payload": None,
        }

    monkeypatch.setattr(a2a_send, "_publish_and_wait", handler_ack)
    packet = _write_packet(tmp_path)

    code = a2a_send.main(
        ["--to", "devin", "--file", str(packet), "--receipt-dir", str(tmp_path / "r")]
    )

    assert code == 0
    receipt = json.loads(next((tmp_path / "r").glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["ack_tier"] == "HANDLER_ACKED"
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["live_contact_claim"] is True
    assert receipt["collaboration_claim"] == "handler_ack"


def test_main_duplicate_packet_id_skips_second_publish(tmp_path, monkeypatch):
    monkeypatch.setenv("NATS_URL", "nats://127.0.0.1:4222")
    calls = 0

    async def publish_only(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            "status": a2a_send.STATUS_PUBLISH_ACKED,
            "ack_tier": a2a_send.ACK_TIER_PUBLISH_ACCEPTED,
            "transport_ack": "JETSTREAM_PUB_ACK",
            "stream": "DHARMA_A2A",
            "seq": calls,
            "consumed": False,
            "replied": False,
            "reply_payload": None,
        }

    monkeypatch.setattr(a2a_send, "_publish_and_wait", publish_only)
    packet = _write_packet(tmp_path)
    args = [
        "--to",
        "devin",
        "--file",
        str(packet),
        "--receipt-dir",
        str(tmp_path / "r"),
        "--packet-id",
        "fixed-packet",
    ]

    assert a2a_send.main(args) == 0
    assert a2a_send.main(args) == 0

    receipts = sorted((tmp_path / "r").glob("*.json"))
    assert calls == 1
    assert len(receipts) >= 1
    bodies = [json.loads(path.read_text(encoding="utf-8")) for path in receipts]
    assert any(body["status"] == "PUBLISH_ACKED" for body in bodies)
    assert any(body["status"] == "PUBLISH_DEDUPED" for body in bodies)
    deduped = next(body for body in bodies if body["status"] == "PUBLISH_DEDUPED")
    assert deduped["runtime_truth_ref"]["idempotency_inserted"] is False
    assert deduped["collaboration_claim"] == "duplicate_publish_skipped"


def test_route_a2a_rejects_unsafe_recipient(tmp_path):
    packet = _write_packet(tmp_path)
    for bad in ("bad.agent", "bad agent", "bad*agent", "bad>agent", "bad/agent", "bad\\agent", ""):
        try:
            a2a_send.build_envelope(
                to=bad,
                file_path=packet,
                sender="operator",
                kind="fleet.packet",
                packet_id="abc123",
                route=a2a_send.ROUTE_A2A,
            )
        except ValueError as exc:
            assert "invalid a2a recipient" in str(exc)
        else:
            raise AssertionError(f"expected unsafe a2a recipient {bad!r} to be rejected")


def test_publish_failure_receipt_omits_exception_text(monkeypatch):
    class FakeSubscription:
        async def unsubscribe(self):
            return None

    class FakeJetStream:
        async def publish(self, *_args, **_kwargs):
            raise RuntimeError("connect to nats://user:super-secret@127.0.0.1 refused")

    class FakeConnection:
        async def subscribe(self, *_args, **_kwargs):
            return FakeSubscription()

        def jetstream(self):
            return FakeJetStream()

        async def publish(self, *_args, **_kwargs):
            return None

        async def flush(self, **_kwargs):
            return None

        async def close(self):
            return None

    async def fake_connect(**_kwargs):
        return FakeConnection()

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=fake_connect))
    envelope = {
        "subject": "dharma.a2a.devin",
        "ack_subject": "dharma.a2a.devin.ack.abc123",
        "reply_subject": "dharma.a2a.devin.reply.abc123",
        "packet_id": "abc123",
    }
    config = a2a_send.NATSConfig(
        endpoint="nats://127.0.0.1:4222",
        user="",
        credential="",
        missing=(),
    )

    result = asyncio.run(
        a2a_send._publish_and_wait(  # noqa: SLF001
            config,
            envelope,
            wait_s=0.0,
            timeout_s=0.1,
        )
    )

    assert result["status"] == a2a_send.STATUS_PUBLISH_FAILED
    assert result["error"] == "RuntimeError"
    assert "super-secret" not in json.dumps(result)
