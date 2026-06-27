from __future__ import annotations

import json
import stat
from pathlib import Path

from scripts.runtime import a2a_domain_reply_artifact


def _delivery_record(tmp_path: Path) -> Path:
    path = tmp_path / "delivery.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": "hermes-m5",
                "bridge_kind": "filesystem_delivery_handler",
                "source_subject": "dharma.agent.hermes-m5.inbox",
                "envelope_sha256": "abc123",
                "envelope": {
                    "packet_id": "packet-1",
                    "reply_subject": "dharma.agent.hermes-m5.inbox.reply.packet-1",
                    "target_uid": "hermes-m5",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def test_build_domain_reply_artifact_defaults_to_nonsemantic_handler_receipt(tmp_path: Path) -> None:
    delivery = json.loads(_delivery_record(tmp_path).read_text(encoding="utf-8"))

    artifact = a2a_domain_reply_artifact.build_domain_reply_artifact(
        delivery_record=delivery,
        verdict="received",
        summary="Bridge-owned delivery was reviewed mechanically.",
    )

    assert artifact["schema_version"] == "dharma.a2a.domain_reply_artifact.v1"
    assert artifact["authored_by"] == "hermes-m5"
    assert artifact["packet_id"] == "packet-1"
    assert artifact["peer_model_processed_claim"] is False
    assert artifact["semantic_reply_claim"] is False
    assert artifact["authenticated_target_runtime_claim"] is False
    assert artifact["author_kind"] == "filesystem_delivery_handler"


def test_cli_writes_target_outbox_artifact_and_author_receipt(tmp_path: Path, capsys) -> None:
    delivery_path = _delivery_record(tmp_path)
    outbox_root = tmp_path / "outboxes"
    receipt_dir = tmp_path / "receipts"

    code = a2a_domain_reply_artifact.main(
        [
            "--delivery-record",
            str(delivery_path),
            "--outbox-root",
            str(outbox_root),
            "--receipt-dir",
            str(receipt_dir),
            "--summary",
            "Target dock wrote a mechanical domain receipt artifact.",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    artifact_path = Path(payload["artifact_path"])
    assert artifact_path == outbox_root / "hermes-m5" / "packet-1-domain-reply.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["authored_by"] == "hermes-m5"
    assert artifact["semantic_reply_claim"] is False
    assert Path(payload["receipt_path"]).is_file()
    assert stat.S_IMODE(artifact_path.stat().st_mode) == 0o600


def test_artifact_path_sanitizes_packet_id(tmp_path: Path) -> None:
    path = a2a_domain_reply_artifact.artifact_path_for(
        outbox_root=tmp_path / "outboxes",
        agent_uid="hermes-m5",
        packet_id="../../escape",
    )

    assert path.parent == (tmp_path / "outboxes" / "hermes-m5").resolve()
    assert path.name == "escape-domain-reply.json"
