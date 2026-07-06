from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.runtime.fugu_ultra_semantic_responder import (
    DEFAULT_AGENT_UID,
    FuguCallResult,
    delivery_from_path,
    is_relevant,
    process_delivery,
    run_once,
)

ROOT = Path(__file__).resolve().parents[1]


def _delivery_record(tmp_path: Path, *, packet_id: str = "packet-1", content: str = "hello fugu") -> Path:
    path = tmp_path / "inbox" / f"{packet_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": DEFAULT_AGENT_UID,
                "bridge_kind": "filesystem_delivery_handler",
                "source_subject": f"dharma.agent.{DEFAULT_AGENT_UID}.inbox",
                "envelope_sha256": "abc123",
                "envelope": {
                    "packet_id": packet_id,
                    "reply_subject": f"dharma.agent.{DEFAULT_AGENT_UID}.inbox.reply.{packet_id}",
                    "target_uid": DEFAULT_AGENT_UID,
                    "from": "codex_composer",
                    "content": content,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _send_receipt(tmp_path: Path, *, packet_id: str = "packet-1") -> Path:
    path = tmp_path / "send_receipts" / "send.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.send_receipt.v1",
                "packet_id": packet_id,
                "target_uid": DEFAULT_AGENT_UID,
                "to": DEFAULT_AGENT_UID,
                "from": "codex_composer",
                "status": "FUGU_ULTRA_CONSUMED",
                "contact_evidence_tier": "HANDLER_ACKED",
                "reply_subject": f"dharma.agent.{DEFAULT_AGENT_UID}.inbox.reply.{packet_id}",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _fake_fugu(prompt: str) -> FuguCallResult:
    assert "fugu_ultra A2A/NATS semantic response task" in prompt
    return FuguCallResult(
        text="Verdict: relevant. Build the responder, keep custody boundaries, and ask Fable/Codex for critique.",
        latency_ms=123,
        raw={"model": "fugu-ultra", "usage": {"total_tokens": 42}},
        prompt_sha256="p" * 64,
        raw_response_sha256="r" * 64,
        max_tokens=1600,
    )


def _fake_publish(**kwargs: Any) -> dict[str, Any]:
    artifact_path = Path(kwargs["reply_artifact_path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["semantic_reply_claim"] is True
    return {
        "status": "DOMAIN_REPLY_PUBLISHED",
        "packet_id": artifact["packet_id"],
        "domain_receipt_claim": True,
        "semantic_reply_claim": True,
        "receipt_path": str(kwargs["receipt_dir"] / "domain-publish.json"),
    }


def test_relevance_accepts_direct_target(tmp_path: Path) -> None:
    delivery = delivery_from_path(_delivery_record(tmp_path), agent_uid=DEFAULT_AGENT_UID)
    assert delivery is not None
    relevant, reason = is_relevant(delivery)
    assert relevant is True
    assert reason == "direct_target"


def test_process_delivery_writes_semantic_artifact_and_publish_receipt(tmp_path: Path) -> None:
    delivery = delivery_from_path(_delivery_record(tmp_path), agent_uid=DEFAULT_AGENT_UID)
    assert delivery is not None
    _send_receipt(tmp_path)

    receipt = process_delivery(
        delivery,
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_receipts",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=1,
        flush_timeout_s=1,
        fugu_call=_fake_fugu,
        publish_func=_fake_publish,
    )

    assert receipt["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert receipt["semantic_reply_claim"] is True
    assert receipt["domain_receipt_claim"] is True
    semantic = json.loads(Path(receipt["semantic_receipt_path"]).read_text(encoding="utf-8"))
    assert semantic["model_identity"] == {"provider": "sakana", "model": "fugu-ultra"}
    assert semantic["semantic_reply_claim"] is True
    artifact = json.loads(Path(receipt["domain_reply_artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["authored_by"] == DEFAULT_AGENT_UID
    assert artifact["semantic_reply_claim"] is True
    assert artifact["semantic_receipt_path"] == receipt["semantic_receipt_path"]


def test_run_once_marks_success_processed_and_projects_state(tmp_path: Path) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    canonical_state = tmp_path / "a2a_bus" / "state" / "fugu_ultra.json"
    canonical_state.parent.mkdir(parents=True, exist_ok=True)
    canonical_state.write_text('{"agent_uid":"fugu_ultra"}\n', encoding="utf-8")

    receipts = run_once(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_receipts",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=1,
        flush_timeout_s=1,
        limit=1,
        lease_ttl_s=60,
        canonical_state_path=canonical_state,
        fugu_call=_fake_fugu,
        publish_func=_fake_publish,
    )

    assert len(receipts) == 1
    processed = (tmp_path / "state" / "processed_deliveries.jsonl").read_text(encoding="utf-8")
    assert "DOMAIN_REPLY_PUBLISHED" in processed
    heartbeat = json.loads((tmp_path / "state" / "heartbeat.json").read_text(encoding="utf-8"))
    assert heartbeat["status"] == "processed_delivery"
    projected = json.loads(canonical_state.read_text(encoding="utf-8"))
    assert projected["wake_loop_active"] is True
    assert projected["fugu_semantic_responder"]["service_id"] == "fugu-ultra-semantic-responder"


def test_fugu_launchd_scripts_are_syntax_valid_and_render(tmp_path: Path) -> None:
    for script in [
        "scripts/start_fugu_ultra_semantic_responder_launchd.sh",
        "scripts/status_fugu_ultra_semantic_responder_launchd.sh",
        "scripts/stop_fugu_ultra_semantic_responder_launchd.sh",
    ]:
        subprocess.run(["bash", "-n", str(ROOT / script)], check=True)

    plan_dir = tmp_path / "plans"
    env = {**__import__("os").environ, "PLAN_DIR": str(plan_dir), "HOME": str(tmp_path / "home")}
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/start_fugu_ultra_semantic_responder_launchd.sh"), "--render-only"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    plist = plan_dir / "com.dharma.fugu-ultra-semantic-responder.plist"
    assert plist.exists()
    text = plist.read_text(encoding="utf-8")
    assert "scripts/runtime/fugu_ultra_semantic_responder.py" in text
    assert "KeepAlive" in text
    assert "No launchctl bootstrap/kickstart commands were run" in result.stdout
