#!/usr/bin/env python3
"""Write a target-dock A2A domain reply artifact from a delivered inbox packet.

This helper creates the artifact consumed by ``a2a_domain_reply_worker.py``.
It does not publish to NATS and it does not claim peer-model processing unless
the caller explicitly provides that claim. The default output is a mechanical
target-dock receipt artifact, not a semantic agent reply.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.a2a_domain_reply_worker import (  # noqa: E402
    DEFAULT_OUTBOX_ROOT,
    DOMAIN_REPLY_ARTIFACT_SCHEMA,
    default_outbox_dir,
)
from scripts.runtime.a2a_send import resolve_agent_uid  # noqa: E402
from scripts.runtime.pr_merge_control import stamp, utc_now  # noqa: E402
from dharma_swarm.daemon_config import runtime_report_dir  # noqa: E402

DEFAULT_ARTIFACT_RECEIPT_DIR = runtime_report_dir("a2a", "domain_reply_artifacts")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in ("_", "-") else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _delivery_envelope(delivery_record: dict[str, Any]) -> dict[str, Any]:
    if str(delivery_record.get("schema_version") or "") != "dharma.a2a.inbox_delivery.v1":
        raise ValueError("delivery record must use schema dharma.a2a.inbox_delivery.v1")
    envelope = delivery_record.get("envelope")
    if not isinstance(envelope, dict):
        raise ValueError("delivery record is missing envelope object")
    return envelope


def build_domain_reply_artifact(
    *,
    delivery_record: dict[str, Any],
    agent_uid: str = "",
    verdict: str,
    summary: str,
    evidence_refs: list[str] | None = None,
    send_receipt_path: Path | None = None,
    peer_model_processed_claim: bool = False,
    semantic_reply_claim: bool | None = None,
    author_kind: str = "filesystem_delivery_handler",
) -> dict[str, Any]:
    envelope = _delivery_envelope(delivery_record)
    target_uid = resolve_agent_uid(agent_uid or str(delivery_record.get("agent_uid") or envelope.get("target_uid") or ""))
    if target_uid != resolve_agent_uid(str(delivery_record.get("agent_uid") or target_uid)):
        raise ValueError("agent_uid does not match delivery record agent_uid")
    packet_id = str(envelope.get("packet_id") or "")
    reply_subject = str(envelope.get("reply_subject") or "")
    if not packet_id:
        raise ValueError("delivery envelope is missing packet_id")
    if not reply_subject:
        raise ValueError("delivery envelope is missing reply_subject")
    if not summary.strip():
        raise ValueError("summary is required")
    semantic = bool(peer_model_processed_claim if semantic_reply_claim is None else semantic_reply_claim)
    artifact: dict[str, Any] = {
        "schema_version": DOMAIN_REPLY_ARTIFACT_SCHEMA,
        "created_at": utc_now(),
        "authored_by": target_uid,
        "agent_uid": target_uid,
        "author_kind": author_kind,
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "verdict": verdict,
        "summary": summary,
        "evidence_refs": list(evidence_refs or []),
        "peer_model_processed_claim": bool(peer_model_processed_claim),
        "semantic_reply_claim": semantic,
        "source_delivery_schema": str(delivery_record.get("schema_version") or ""),
        "source_delivery_envelope_sha256": str(delivery_record.get("envelope_sha256") or ""),
        "source_subject": str(delivery_record.get("source_subject") or ""),
        "source_bridge_kind": str(delivery_record.get("bridge_kind") or ""),
        "operator_contact_note": (
            "target-dock artifact authored from an inbox delivery record; "
            "semantic_reply_claim is explicit and defaults to false"
        ),
    }
    if send_receipt_path is not None:
        artifact["send_receipt_path"] = str(send_receipt_path.expanduser().resolve())
    return artifact


def artifact_path_for(
    *,
    outbox_root: Path,
    agent_uid: str,
    packet_id: str,
) -> Path:
    return default_outbox_dir(agent_uid, outbox_root=outbox_root) / f"{packet_id}-domain-reply.json"


def write_artifact_author_receipt(
    *,
    receipt_dir: Path,
    artifact_path: Path,
    artifact: dict[str, Any],
    delivery_record_path: Path,
) -> Path:
    receipt = {
        "schema_version": "dharma.a2a.domain_reply_artifact_author_receipt.v1",
        "timestamp": utc_now(),
        "status": "DOMAIN_REPLY_ARTIFACT_WRITTEN",
        "agent_uid": artifact["agent_uid"],
        "packet_id": artifact["packet_id"],
        "artifact_path": str(artifact_path),
        "delivery_record_path": str(delivery_record_path),
        "semantic_reply_claim": bool(artifact.get("semantic_reply_claim", False)),
        "peer_model_processed_claim": bool(artifact.get("peer_model_processed_claim", False)),
        "operator_contact_note": (
            "target-dock domain reply artifact was written; publishing requires "
            "scripts/runtime/a2a_domain_reply_worker.py"
        ),
    }
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / (
        f"{stamp()}-{_safe_token(receipt['agent_uid'])}-{_safe_token(receipt['packet_id'])}.json"
    )
    _write_json(path, receipt)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delivery-record", required=True, help="inbox delivery JSON from a2a_inbox_bridge.py")
    parser.add_argument("--send-receipt", default="", help="optional original A2A send receipt path")
    parser.add_argument("--agent-uid", default="", help="target agent uid; defaults to delivery record agent_uid")
    parser.add_argument("--outbox-root", default=str(DEFAULT_OUTBOX_ROOT))
    parser.add_argument("--receipt-dir", default=str(DEFAULT_ARTIFACT_RECEIPT_DIR))
    parser.add_argument("--verdict", default="received")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--author-kind", default="filesystem_delivery_handler")
    parser.add_argument("--peer-model-processed", action="store_true")
    parser.add_argument("--semantic-reply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    delivery_path = Path(args.delivery_record).expanduser().resolve()
    send_receipt_path = Path(args.send_receipt).expanduser().resolve() if args.send_receipt else None
    try:
        delivery_record = _read_json(delivery_path)
        artifact = build_domain_reply_artifact(
            delivery_record=delivery_record,
            agent_uid=args.agent_uid,
            verdict=args.verdict,
            summary=args.summary,
            evidence_refs=list(args.evidence_ref or []),
            send_receipt_path=send_receipt_path,
            peer_model_processed_claim=args.peer_model_processed,
            semantic_reply_claim=args.semantic_reply or args.peer_model_processed,
            author_kind=args.author_kind,
        )
        path = artifact_path_for(
            outbox_root=Path(args.outbox_root).expanduser().resolve(),
            agent_uid=str(artifact["agent_uid"]),
            packet_id=str(artifact["packet_id"]),
        )
        _write_json(path, artifact)
        receipt_path = write_artifact_author_receipt(
            receipt_dir=Path(args.receipt_dir),
            artifact_path=path,
            artifact=artifact,
            delivery_record_path=delivery_path,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    payload = {
        "status": "DOMAIN_REPLY_ARTIFACT_WRITTEN",
        "artifact_path": str(path),
        "receipt_path": str(receipt_path),
        "agent_uid": artifact["agent_uid"],
        "packet_id": artifact["packet_id"],
        "semantic_reply_claim": bool(artifact.get("semantic_reply_claim", False)),
        "peer_model_processed_claim": bool(artifact.get("peer_model_processed_claim", False)),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{payload['status']} agent_uid={payload['agent_uid']} packet_id={payload['packet_id']}")
        print(f"artifact: {payload['artifact_path']}")
        print(f"receipt: {payload['receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
