#!/usr/bin/env python3
"""Drain one A2A delivery into semantic and domain artifacts.

This is deliberately after the inbox bridge. Handler ACK remains transport
evidence only; this worker creates separate model-authored semantic evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.a2a_domain_reply_artifact import (  # noqa: E402
    DEFAULT_ARTIFACT_RECEIPT_DIR,
    artifact_path_for,
    build_domain_reply_artifact,
    write_artifact_author_receipt,
)
from scripts.runtime.a2a_domain_reply_worker import DEFAULT_OUTBOX_ROOT  # noqa: E402
from scripts.runtime.model_critic_runner import DEFAULT_OUT_DIR as DEFAULT_SEMANTIC_RECEIPT_DIR  # noqa: E402
from scripts.runtime.model_critic_runner import run_model_critic  # noqa: E402
from scripts.runtime.pr_merge_control import stamp, utc_now  # noqa: E402
from dharma_swarm.models import ProviderType  # noqa: E402
from dharma_swarm.daemon_config import runtime_report_dir  # noqa: E402
from dharma_swarm.runtime_provider import (  # noqa: E402
    PREFERRED_LOW_COST_RUNTIME_PROVIDERS,
    preferred_runtime_provider_configs,
    resolve_runtime_provider_config,
)

DEFAULT_DRAIN_RECEIPT_DIR = runtime_report_dir("a2a", "semantic_inbox_drains")
DEFAULT_AGENT_UID = "codex_composer"
LEGACY_SCHEMA_VERSION = "dharma.a2a.codex_composer_semantic_inbox_drain.v1"
GENERIC_SCHEMA_VERSION = "dharma.a2a.semantic_inbox_drain.v1"
_DIRECT_RUNTIME_PROVIDER_ORDER = tuple(
    provider
    for provider in PREFERRED_LOW_COST_RUNTIME_PROVIDERS
    if provider
    not in {
        ProviderType.OLLAMA,
        ProviderType.CLAUDE_CODE,
        ProviderType.CODEX,
    }
)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    path.chmod(0o600)


def _safe_token(value: object, *, fallback: str = "unknown") -> str:
    chars = [char if char.isalnum() or char in {"_", "-"} else "_" for char in str(value or "")]
    return ("".join(chars).strip("_-") or fallback)[:96]


def _delivery_envelope(delivery_record: dict[str, Any]) -> dict[str, Any]:
    if str(delivery_record.get("schema_version") or "") != "dharma.a2a.inbox_delivery.v1":
        raise ValueError("delivery record must use schema dharma.a2a.inbox_delivery.v1")
    envelope = delivery_record.get("envelope")
    if not isinstance(envelope, dict):
        raise ValueError("delivery record is missing envelope object")
    return envelope


def _schema_version_for(agent_uid: str) -> str:
    if agent_uid == DEFAULT_AGENT_UID:
        return LEGACY_SCHEMA_VERSION
    return GENERIC_SCHEMA_VERSION


def _default_prompt(delivery_record: dict[str, Any], delivery_record_path: Path, *, agent_uid: str) -> str:
    envelope = _delivery_envelope(delivery_record)
    return (
        f"# {agent_uid} Semantic Inbox Drain\n\n"
        f"Read this delivered A2A packet as {agent_uid}. Produce a typed "
        "SemanticReceipt judgment. Do not claim handler ACK as semantic cognition.\n\n"
        f"- delivery_record: {delivery_record_path}\n"
        f"- packet_id: {envelope.get('packet_id')}\n"
        f"- reply_subject: {envelope.get('reply_subject')}\n\n"
        "Delivered envelope JSON:\n\n"
        "```json\n"
        f"{json.dumps(envelope, indent=2, sort_keys=True)}\n"
        "```\n"
    )


def _prompt_path_for(receipt_dir: Path, packet_id: str) -> Path:
    return receipt_dir / "prompts" / f"{_safe_token(packet_id)}.md"


def _source_audit_claim(semantic_receipt: dict[str, Any]) -> bool:
    if bool(semantic_receipt.get("source_audit_claim")):
        return True
    gates = semantic_receipt.get("acceptance_gates")
    if not isinstance(gates, list):
        return False
    for gate in gates:
        if not isinstance(gate, dict) or not bool(gate.get("met")):
            continue
        name = str(gate.get("name") or gate.get("condition") or "").casefold()
        if "source" in name and ("audit" in name or "inspect" in name):
            return True
    return False


def _summary_with_boundary(summary: str, *, semantic_claim: bool, source_audit_claim: bool) -> str:
    if not semantic_claim:
        return summary
    if source_audit_claim:
        return summary
    return "Semantic packet receipt only; source audit not claimed. Model summary: " + summary


def _semantic_audit_depth(*, semantic_claim: bool, source_audit_claim: bool) -> str:
    if source_audit_claim:
        return "source_audit"
    if semantic_claim:
        return "packet_only"
    return "typed_failure"


def _resolve_runtime_critic_defaults(
    *,
    provider: str | None,
    model: str | None,
) -> tuple[str, str]:
    """Resolve semantic-critic provider/model through runtime_provider."""

    if provider:
        try:
            provider_type = ProviderType(provider)
        except ValueError as exc:
            raise ValueError(f"unsupported runtime provider: {provider}") from exc
        cfg = resolve_runtime_provider_config(provider_type, model=model or None)
        if not cfg.available:
            raise RuntimeError(f"semantic inbox provider is not available: {provider}")
        resolved_model = cfg.default_model or model
        if not resolved_model:
            raise RuntimeError(f"semantic inbox provider has no resolved model: {provider}")
        return cfg.provider.value, resolved_model

    configs = preferred_runtime_provider_configs(
        model=model or None,
        provider_order=_DIRECT_RUNTIME_PROVIDER_ORDER,
    )
    if not configs:
        raise RuntimeError("no direct API runtime provider available for semantic inbox drain")
    cfg = configs[0]
    resolved_model = cfg.default_model or model
    if not resolved_model:
        raise RuntimeError(f"semantic inbox provider has no resolved model: {cfg.provider.value}")
    return cfg.provider.value, resolved_model


def drain_semantic_inbox(
    *,
    delivery_record_path: Path,
    send_receipt_path: Path | None = None,
    prompt_file: Path | None = None,
    mock_response_file: Path | None = None,
    outbox_root: Path = DEFAULT_OUTBOX_ROOT,
    semantic_receipt_dir: Path = DEFAULT_SEMANTIC_RECEIPT_DIR,
    artifact_receipt_dir: Path = DEFAULT_ARTIFACT_RECEIPT_DIR,
    drain_receipt_dir: Path = DEFAULT_DRAIN_RECEIPT_DIR,
    agent_uid: str = DEFAULT_AGENT_UID,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    delivery_record_path = delivery_record_path.expanduser().resolve()
    delivery_record = _read_json(delivery_record_path)
    envelope = _delivery_envelope(delivery_record)
    packet_id = str(envelope.get("packet_id") or "")
    reply_subject = str(envelope.get("reply_subject") or "")
    target_uid = str(delivery_record.get("agent_uid") or envelope.get("target_uid") or "")
    if target_uid != agent_uid:
        raise ValueError(f"delivery target {target_uid!r} is not {agent_uid!r}")
    if not packet_id or not reply_subject:
        raise ValueError("delivery envelope must include packet_id and reply_subject")

    if prompt_file is None:
        prompt_file = _prompt_path_for(drain_receipt_dir, packet_id)
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(
            _default_prompt(delivery_record, delivery_record_path, agent_uid=agent_uid),
            encoding="utf-8",
        )
    else:
        prompt_file = prompt_file.expanduser().resolve()
    if prompt_file.exists():
        prompt_file.chmod(0o600)

    critic_provider, critic_model = _resolve_runtime_critic_defaults(
        provider=provider,
        model=model,
    )
    critic_result = run_model_critic(
        prompt_file=prompt_file,
        provider=critic_provider,
        model=critic_model,
        out_dir=semantic_receipt_dir,
        agent_uid=agent_uid,
        review_target=f"a2a:{packet_id}",
        reply_to=reply_subject,
        correlation_id=packet_id,
        mock_response_file=mock_response_file.expanduser().resolve() if mock_response_file else None,
    )
    semantic_receipt = critic_result["receipt"]
    semantic_receipt_path = Path(str(critic_result["artifact_path"])).expanduser().resolve()
    semantic_claim = bool(semantic_receipt.get("semantic_reply_claim"))
    source_audit_claim = _source_audit_claim(semantic_receipt)
    verdict = str(semantic_receipt.get("verdict") or "reviewed")
    summary = _summary_with_boundary(
        str(semantic_receipt.get("summary") or "Semantic receipt written for A2A delivery."),
        semantic_claim=semantic_claim,
        source_audit_claim=source_audit_claim,
    )
    evidence_refs = [
        str(delivery_record_path),
        str(prompt_file),
        str(semantic_receipt_path),
    ]
    if send_receipt_path is not None:
        evidence_refs.append(str(send_receipt_path.expanduser().resolve()))

    artifact = build_domain_reply_artifact(
        delivery_record=delivery_record,
        agent_uid=agent_uid,
        verdict=verdict,
        summary=summary,
        evidence_refs=evidence_refs,
        send_receipt_path=send_receipt_path.expanduser().resolve() if send_receipt_path else None,
        peer_model_processed_claim=semantic_claim,
        semantic_reply_claim=semantic_claim,
        author_kind=f"{_safe_token(agent_uid)}_semantic_inbox_drain",
    )
    artifact["semantic_receipt_path"] = str(semantic_receipt_path)
    artifact["semantic_receipt_id"] = str(semantic_receipt.get("receipt_id") or "")
    artifact["semantic_claim_basis"] = str(semantic_receipt.get("semantic_claim_basis") or "")
    artifact["handler_ack_is_semantic_cognition"] = False
    artifact["source_audit_claim"] = source_audit_claim
    artifact["authenticated_target_runtime_claim"] = False
    semantic_audit_depth = _semantic_audit_depth(
        semantic_claim=semantic_claim,
        source_audit_claim=source_audit_claim,
    )
    artifact["semantic_audit_depth"] = semantic_audit_depth

    artifact_path = artifact_path_for(outbox_root=outbox_root, agent_uid=agent_uid, packet_id=packet_id)
    _write_json(artifact_path, artifact)
    artifact_author_receipt = write_artifact_author_receipt(
        receipt_dir=artifact_receipt_dir,
        artifact_path=artifact_path,
        artifact=artifact,
        delivery_record_path=delivery_record_path,
    )

    drain_receipt = {
        "schema_version": _schema_version_for(agent_uid),
        "timestamp": utc_now(),
        "status": "SEMANTIC_INBOX_DRAINED" if semantic_claim else "SEMANTIC_INBOX_DRAIN_TYPED_FAILURE",
        "agent_uid": agent_uid,
        "packet_id": packet_id,
        "reply_subject": reply_subject,
        "delivery_record_path": str(delivery_record_path),
        "prompt_file": str(prompt_file),
        "semantic_receipt_path": str(semantic_receipt_path),
        "semantic_receipt_id": str(semantic_receipt.get("receipt_id") or ""),
        "domain_reply_artifact_path": str(artifact_path),
        "domain_reply_artifact_author_receipt_path": str(artifact_author_receipt),
        "semantic_reply_claim": semantic_claim,
        "peer_model_processed_claim": semantic_claim,
        "source_audit_claim": source_audit_claim,
        "authenticated_target_runtime_claim": False,
        "semantic_audit_depth": semantic_audit_depth,
        "handler_ack_is_semantic_cognition": False,
        "typed_reply_publish_required_next": True,
        "operator_contact_note": (
            "This proves model-authored semantic drain and target-owned artifact creation. "
            "Publishing remains scripts/runtime/a2a_domain_reply_worker.py."
            if semantic_claim
            else "This records a typed semantic drain failure and target-owned artifact creation; "
            "it is not a semantic cognition proof. Publishing remains "
            "scripts/runtime/a2a_domain_reply_worker.py."
        ),
    }
    drain_receipt_dir.mkdir(parents=True, exist_ok=True)
    drain_receipt_path = drain_receipt_dir / f"{stamp()}-{_safe_token(agent_uid)}-{_safe_token(packet_id)}.json"
    _write_json(drain_receipt_path, drain_receipt)
    drain_receipt["drain_receipt_path"] = str(drain_receipt_path)
    return drain_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delivery-record", required=True)
    parser.add_argument("--send-receipt", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--mock-response-file", default="")
    parser.add_argument("--outbox-root", default=str(DEFAULT_OUTBOX_ROOT))
    parser.add_argument("--semantic-receipt-dir", default=str(DEFAULT_SEMANTIC_RECEIPT_DIR))
    parser.add_argument("--artifact-receipt-dir", default=str(DEFAULT_ARTIFACT_RECEIPT_DIR))
    parser.add_argument("--drain-receipt-dir", default=str(DEFAULT_DRAIN_RECEIPT_DIR))
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID)
    parser.add_argument("--provider", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        receipt = drain_semantic_inbox(
            delivery_record_path=Path(args.delivery_record),
            send_receipt_path=Path(args.send_receipt) if args.send_receipt else None,
            prompt_file=Path(args.prompt_file) if args.prompt_file else None,
            mock_response_file=Path(args.mock_response_file) if args.mock_response_file else None,
            outbox_root=Path(args.outbox_root),
            semantic_receipt_dir=Path(args.semantic_receipt_dir),
            artifact_receipt_dir=Path(args.artifact_receipt_dir),
            drain_receipt_dir=Path(args.drain_receipt_dir),
            agent_uid=args.agent_uid,
            provider=args.provider or None,
            model=args.model or None,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            f"{receipt['status']} packet_id={receipt['packet_id']} "
            f"semantic_reply_claim={receipt['semantic_reply_claim']}"
        )
        print(f"semantic_receipt: {receipt['semantic_receipt_path']}")
        print(f"domain_artifact: {receipt['domain_reply_artifact_path']}")
        print(f"drain_receipt: {receipt['drain_receipt_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
