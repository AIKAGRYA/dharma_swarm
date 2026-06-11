import json
import os
from pathlib import Path

from scripts.runtime import a2a_send


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


def test_write_receipt(tmp_path):
    receipt = {"to": "devin", "packet_id": "abc123", "status": "PUBLISH_ACKED"}
    path = a2a_send.write_receipt(tmp_path / "receipts", receipt)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "PUBLISH_ACKED"


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
    assert "NATS_SECRETS_MISSING" in out
    receipts = list((tmp_path / "r").glob("*.json"))
    assert len(receipts) == 1
    body = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert body["status"] == "NATS_SECRETS_MISSING"


def test_main_missing_file(tmp_path):
    code = a2a_send.main(
        ["--to", "devin", "--file", str(tmp_path / "nope.md"), "--receipt-dir", str(tmp_path)]
    )
    assert code == 2
