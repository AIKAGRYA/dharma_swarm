"""Pure, read-only canonical evidence reader for Mission Control A2A P0."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping, Protocol

from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.operator_core.semantic_receipt import (
    REQUIRED_FIELDS as SEMANTIC_REQUIRED_FIELDS,
    SemanticReceiptValidationError,
    validate_semantic_receipt,
)

DELIVERY_SCHEMA = "dharma.a2a.inbox_delivery.v1"
RESPONDER_SCHEMA = "dharma.a2a.codex_composer_semantic_responder.v1"
_DRAIN_LEGACY_SCHEMA = "dharma.a2a.codex_composer_semantic_inbox_drain.v1"
_DRAIN_GENERIC_SCHEMA = "dharma.a2a.semantic_inbox_drain.v1"
_ARTIFACT_SCHEMA = "dharma.a2a.domain_reply_artifact.v1"
_ARTIFACT_AUTHOR_SCHEMA = "dharma.a2a.domain_reply_artifact_author_receipt.v1"
_PUBLISH_SCHEMA = "dharma.a2a.domain_reply_publish_receipt.v1"
_DOMAIN_RECEIPT_SCHEMA = "dharma.a2a.domain_receipt.v1"
_SEND_RECEIPT_SCHEMA = "dharma.a2a.send_receipt.v1"
_PUBLISHED = "DOMAIN_REPLY_PUBLISHED"


class RefLike(Protocol):
    agent_uid: str
    packet_id: str
    delivery_id: str


class _IncompleteEvidence(Exception):
    """Absent/partial evidence proves no execution but is not corruption."""


def resolved_root(root: Path) -> Path:
    candidate = root.expanduser()
    try:
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise MissionControlError("trusted evidence root is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise MissionControlError("trusted evidence root is not a regular directory")
    return resolved


def safe_file(root: Path, *parts: str) -> Path:
    trusted = resolved_root(root)
    candidate = trusted.joinpath(*parts)
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise MissionControlError(
            f"trusted evidence file is unavailable: {candidate.name}",
        ) from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(
            f"trusted evidence file is not a regular file: {candidate.name}",
        )
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(trusted):
        raise MissionControlError("trusted evidence path escaped its injected root")
    return resolved


def read_bytes(path: Path, *, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise MissionControlError(
            f"could not open trusted evidence: {path.name}",
        ) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise MissionControlError(
                f"trusted evidence exceeds its read bound: {path.name}",
            )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
        ):
            raise MissionControlError(
                f"trusted evidence changed while read: {path.name}",
            )
        data = b"".join(chunks)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise MissionControlError(
            f"trusted evidence exceeds its read bound: {path.name}",
        )
    return data


def read_json(path: Path, *, limit: int) -> tuple[dict[str, Any], bytes]:
    raw = read_bytes(path, limit=limit)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionControlError(
            f"malformed trusted JSON evidence: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise MissionControlError(
            f"trusted JSON evidence must be an object: {path.name}",
        )
    return value, raw


def _optional_file(root: Path, *parts: str) -> Path | None:
    if not resolved_root(root).joinpath(*parts).exists():
        return None
    return safe_file(root, *parts)


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _exact_path(value: object, expected: Path, label: str) -> None:
    raw = str(value or "")
    if not raw:
        raise _IncompleteEvidence(label)
    declared = Path(raw)
    if not declared.is_absolute() or _absolute_lexical(declared) != expected:
        raise MissionControlError(
            f"{label} does not match its trusted canonical path",
        )


def _trusted_link(value: object, roots: tuple[Path, ...], label: str) -> Path:
    raw = str(value or "")
    if not raw:
        raise _IncompleteEvidence(label)
    declared = Path(raw)
    if not declared.is_absolute():
        raise MissionControlError(f"{label} must be an absolute trusted path")
    lexical = _absolute_lexical(declared)
    for configured in roots:
        trusted = resolved_root(configured)
        if lexical.is_relative_to(trusted):
            if not lexical.exists():
                raise _IncompleteEvidence(label)
            return safe_file(trusted, *lexical.relative_to(trusted).parts)
    if not roots:
        raise _IncompleteEvidence(label)
    raise MissionControlError(
        f"{label} is outside every injected trusted receipt root",
    )


def _field(
    mapping: Mapping[str, Any], key: str, expected: Any, label: str,
) -> None:
    if key not in mapping:
        raise _IncompleteEvidence(f"{label}.{key}")
    actual = mapping[key]
    if type(actual) is not type(expected) or actual != expected:
        raise MissionControlError(
            f"{label}.{key} contradicts native A2A identity",
        )


def _present(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping or mapping[key] in (None, ""):
        raise _IncompleteEvidence(f"{label}.{key}")
    return mapping[key]


def _exact_json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _exact_json_equal(first, second)
            for first, second in zip(left, right, strict=True)
        )
    return bool(left == right)


def _successful_send_statuses(agent_uid: str) -> frozenset[str]:
    label = "".join(
        char.upper() if char.isalnum() else "_" for char in agent_uid
    ).strip("_") or "AGENT"
    return frozenset({
        "PUBLISH_ACKED",
        "PUBLISH_DEDUPED",
        f"{label}_CONSUMED",
        f"{label}_REPLIED",
    })


class CanonicalA2AEvidenceReader:
    """Validate the exact canonical responder-to-domain-publish chain."""

    def __init__(
        self,
        *,
        responder_root: Path,
        outbox_root: Path,
        trusted_receipt_roots: tuple[Path, ...],
        max_bytes: int,
    ) -> None:
        self._responder_root = responder_root
        self._outbox_root = outbox_root
        self._trusted_roots = trusted_receipt_roots
        self._max = max_bytes

    def processed(
        self, ref: RefLike, delivery_path: Path,
    ) -> dict[str, Any] | None:
        relative = (
            ref.agent_uid, "nest", "semantic_responder", "processed_deliveries.jsonl",
        )
        candidate = resolved_root(self._responder_root).joinpath(*relative)
        if not candidate.exists():
            return None
        rows: list[dict[str, Any]] = []
        for line in read_bytes(safe_file(self._responder_root, *relative), limit=self._max).splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MissionControlError("processed-delivery evidence is malformed") from exc
            if isinstance(value, dict) and value.get("delivery_id") == ref.delivery_id:
                rows.append(value)
                if len(rows) > 1:
                    break
        if not rows:
            return None
        if len(rows) != 1:
            raise MissionControlError("delivery has conflicting processed records")
        row = rows[0]
        _field(row, "schema_version", RESPONDER_SCHEMA, "processed delivery")
        _field(row, "packet_id", ref.packet_id, "processed delivery")
        _exact_path(row.get("delivery_record_path"), delivery_path, "processed delivery path")
        return row

    def _response_path(self, ref: RefLike, value: object) -> Path:
        raw = str(value or "")
        if not raw:
            raise _IncompleteEvidence("processed receipt_path")
        declared = Path(raw)
        parent = resolved_root(self._responder_root).joinpath(
            ref.agent_uid, "nest", "semantic_responder", "receipts",
        )
        if not declared.is_absolute() or _absolute_lexical(declared).parent != parent:
            raise MissionControlError(
                "processed receipt_path is not the exact trusted responder path",
            )
        if not _absolute_lexical(declared).exists():
            raise _IncompleteEvidence("processed receipt_path")
        return safe_file(
            self._responder_root,
            ref.agent_uid,
            "nest",
            "semantic_responder",
            "receipts",
            declared.name,
        )

    def _semantic_chain(
        self,
        *,
        ref: RefLike,
        delivery_path: Path,
        delivery: Mapping[str, Any],
        envelope: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> tuple[Path, str, dict[str, Any]]:
        artifact_path = _optional_file(
            self._outbox_root, ref.agent_uid, f"{ref.packet_id}-domain-reply.json",
        )
        if artifact_path is None:
            raise _IncompleteEvidence("domain reply artifact")
        artifact, artifact_raw = read_json(artifact_path, limit=self._max)
        artifact_sha = hashlib.sha256(artifact_raw).hexdigest()
        drain = response.get("semantic_drain_receipt")
        if not isinstance(drain, dict):
            raise _IncompleteEvidence("semantic drain receipt")
        drain_schema = (
            _DRAIN_LEGACY_SCHEMA
            if ref.agent_uid == "codex_composer"
            else _DRAIN_GENERIC_SCHEMA
        )
        fields = {
            "schema_version": drain_schema,
            "status": "SEMANTIC_INBOX_DRAINED",
            "agent_uid": ref.agent_uid,
            "packet_id": ref.packet_id,
            "reply_subject": envelope.get("reply_subject"),
            "semantic_reply_claim": True,
            "peer_model_processed_claim": True,
            "authenticated_target_runtime_claim": False,
            "handler_ack_is_semantic_cognition": False,
            "typed_reply_publish_required_next": True,
        }
        for key, expected in fields.items():
            _field(drain, key, expected, "semantic drain receipt")
        _exact_path(drain.get("delivery_record_path"), delivery_path, "drain delivery path")
        _exact_path(drain.get("domain_reply_artifact_path"), artifact_path, "drain artifact path")
        drain_path = _trusted_link(
            drain.get("drain_receipt_path"), self._trusted_roots, "drain receipt path",
        )
        persisted, _ = read_json(drain_path, limit=self._max)
        expected_persisted = {
            key: value
            for key, value in drain.items()
            if key != "drain_receipt_path"
        }
        if not _exact_json_equal(persisted, expected_persisted):
            raise MissionControlError("nested semantic drain differs from its trusted receipt")

        semantic_path = _trusted_link(
            drain.get("semantic_receipt_path"), self._trusted_roots, "semantic receipt path",
        )
        semantic, _ = read_json(semantic_path, limit=self._max)
        if any(key not in semantic for key in SEMANTIC_REQUIRED_FIELDS):
            raise _IncompleteEvidence("semantic receipt fields")
        try:
            validated = validate_semantic_receipt(semantic)
        except SemanticReceiptValidationError as exc:
            raise MissionControlError("semantic receipt fails its canonical validator") from exc
        if validated != semantic:
            raise MissionControlError("semantic receipt is not canonically normalized")
        semantic_id = str(_present(semantic, "receipt_id", "semantic receipt"))
        semantic_fields = {
            "agent_uid": ref.agent_uid,
            "review_target": f"a2a:{ref.packet_id}",
            "correlation_id": ref.packet_id,
            "reply_to": envelope.get("reply_subject"),
            "authored_by_model": True,
            "semantic_reply_claim": True,
            "peer_model_processed_claim": True,
            "semantic_claim_basis": "validated_non_codex_model_artifact",
            "failure_type": "",
        }
        for key, expected in semantic_fields.items():
            _field(semantic, key, expected, "semantic receipt")
        _field(drain, "semantic_receipt_id", semantic_id, "semantic drain receipt")
        _exact_path(drain.get("semantic_receipt_path"), semantic_path, "drain semantic receipt path")

        artifact_fields = {
            "schema_version": _ARTIFACT_SCHEMA,
            "authored_by": ref.agent_uid,
            "agent_uid": ref.agent_uid,
            "author_kind": f"{ref.agent_uid}_semantic_inbox_drain",
            "packet_id": ref.packet_id,
            "reply_subject": envelope.get("reply_subject"),
            "peer_model_processed_claim": True,
            "semantic_reply_claim": True,
            "source_delivery_schema": DELIVERY_SCHEMA,
            "source_delivery_envelope_sha256": delivery.get("envelope_sha256"),
            "semantic_receipt_id": semantic_id,
            "semantic_claim_basis": semantic.get("semantic_claim_basis"),
            "handler_ack_is_semantic_cognition": False,
            "authenticated_target_runtime_claim": False,
        }
        for key, expected in artifact_fields.items():
            _field(artifact, key, expected, "domain reply artifact")
        _exact_path(artifact.get("semantic_receipt_path"), semantic_path, "artifact semantic receipt path")
        refs = artifact.get("evidence_refs")
        if not isinstance(refs, list):
            raise _IncompleteEvidence("artifact evidence_refs")
        if str(delivery_path) not in refs or str(semantic_path) not in refs:
            raise MissionControlError("artifact evidence refs do not bind delivery and semantic receipt")
        source_audit_claim = drain.get("source_audit_claim")
        if type(source_audit_claim) is not bool:
            raise MissionControlError(
                "semantic drain receipt.source_audit_claim must be boolean",
            )
        source_audit = source_audit_claim
        depth = "source_audit" if source_audit else "packet_only"
        _field(drain, "semantic_audit_depth", depth, "semantic drain receipt")
        _field(artifact, "source_audit_claim", source_audit, "domain reply artifact")
        _field(artifact, "semantic_audit_depth", depth, "domain reply artifact")

        author_path = _trusted_link(
            drain.get("domain_reply_artifact_author_receipt_path"),
            self._trusted_roots,
            "artifact author receipt path",
        )
        author, _ = read_json(author_path, limit=self._max)
        author_fields = {
            "schema_version": _ARTIFACT_AUTHOR_SCHEMA,
            "status": "DOMAIN_REPLY_ARTIFACT_WRITTEN",
            "agent_uid": ref.agent_uid,
            "packet_id": ref.packet_id,
            "semantic_reply_claim": True,
            "peer_model_processed_claim": True,
        }
        for key, expected in author_fields.items():
            _field(author, key, expected, "artifact author receipt")
        _exact_path(author.get("artifact_path"), artifact_path, "author artifact path")
        _exact_path(author.get("delivery_record_path"), delivery_path, "author delivery path")
        return artifact_path, artifact_sha, artifact

    def _publish_chain(
        self,
        *,
        ref: RefLike,
        envelope: Mapping[str, Any],
        response: Mapping[str, Any],
        artifact_path: Path,
        artifact_sha: str,
        artifact: Mapping[str, Any],
    ) -> None:
        publish = response.get("domain_reply_publish_receipt")
        if not isinstance(publish, dict):
            raise _IncompleteEvidence("domain publish receipt")
        fields = {
            "schema_version": _PUBLISH_SCHEMA,
            "status": _PUBLISHED,
            "agent_uid": ref.agent_uid,
            "packet_id": ref.packet_id,
            "reply_subject": envelope.get("reply_subject"),
            "reply_artifact_sha256": artifact_sha,
            "payload_schema": _DOMAIN_RECEIPT_SCHEMA,
            "semantic_reply_claim": True,
            "domain_receipt_claim": True,
            "target_owned_artifact_claim": True,
            "contact_evidence_tier": "DOMAIN_RECEIPTED",
            "reply_evidence_tier": "DOMAIN_RECEIPTED",
        }
        for key, expected in fields.items():
            _field(publish, key, expected, "domain publish receipt")
        _exact_path(publish.get("reply_artifact_path"), artifact_path, "publish artifact path")
        publish_path = _trusted_link(
            publish.get("receipt_path"), self._trusted_roots, "publish receipt path",
        )
        persisted, _ = read_json(publish_path, limit=self._max)
        expected_persisted = {
            key: value
            for key, value in publish.items()
            if key != "receipt_path"
        }
        if not _exact_json_equal(persisted, expected_persisted):
            raise MissionControlError("nested publish receipt differs from its trusted receipt")
        ack = publish.get("transport_ack")
        if (
            not isinstance(ack, dict)
            or ack.get("transport_ack") != "JETSTREAM_PUB_ACK"
            or type(ack.get("stream")) is not str
            or not ack["stream"]
            or type(ack.get("seq")) is not int
            or ack["seq"] < 1
        ):
            raise MissionControlError("domain publish has no canonical durable transport ack")
        payload = publish.get("domain_receipt_payload")
        if not isinstance(payload, dict):
            raise _IncompleteEvidence("domain receipt payload")
        payload_fields = {
            "schema_version": _DOMAIN_RECEIPT_SCHEMA,
            "from_agent": ref.agent_uid,
            "packet_id": ref.packet_id,
            "reply_subject": envelope.get("reply_subject"),
            "domain_receipt": True,
            "semantic_reply_claim": True,
            "target_owned_artifact_claim": True,
            "peer_model_processed_claim": True,
            "author_kind": artifact.get("author_kind"),
            "source_artifact_schema": _ARTIFACT_SCHEMA,
            "source_artifact_sha256": artifact_sha,
        }
        for key, expected in payload_fields.items():
            _field(payload, key, expected, "domain receipt payload")
        _exact_path(payload.get("source_artifact_path"), artifact_path, "domain payload artifact path")
        payload_sha = hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True).encode(),
        ).hexdigest()
        _field(publish, "payload_sha256", payload_sha, "domain publish receipt")
        message_id = "domain_reply_" + hashlib.sha256(
            f"{envelope.get('reply_subject')}|{payload_sha}".encode(),
        ).hexdigest()[:32]
        _field(publish, "message_id", message_id, "domain publish receipt")
        send_path = _trusted_link(
            publish.get("send_receipt_path"), self._trusted_roots, "send receipt path",
        )
        send, send_raw = read_json(send_path, limit=self._max)
        _field(send, "schema_version", _SEND_RECEIPT_SCHEMA, "send receipt")
        _field(send, "packet_id", ref.packet_id, "send receipt")
        _field(send, "reply_subject", envelope.get("reply_subject"), "send receipt")
        if send.get("status") not in _successful_send_statuses(ref.agent_uid):
            raise MissionControlError(
                "send receipt has no canonical successful status",
            )
        if str(send.get("target_uid") or send.get("to") or "") != ref.agent_uid:
            raise MissionControlError("send receipt target contradicts native A2A identity")
        _exact_path(payload.get("causation_send_receipt_path"), send_path, "domain payload send path")
        _field(
            payload,
            "causation_send_receipt_sha256",
            hashlib.sha256(send_raw).hexdigest(),
            "domain receipt payload",
        )
        _exact_path(response.get("send_receipt_path"), send_path, "responder send path")

    def canonical_execution(
        self,
        *,
        ref: RefLike,
        delivery_path: Path,
        delivery: Mapping[str, Any],
        envelope: Mapping[str, Any],
        processed: Mapping[str, Any] | None,
    ) -> tuple[str, str, bool]:
        if processed is None:
            return "", "", False
        status = str(processed.get("status") or "")
        if status != _PUBLISHED:
            return "", status, False
        try:
            _field(processed, "status", _PUBLISHED, "processed delivery")
            _field(processed, "reply_subject", envelope.get("reply_subject"), "processed delivery")
            response_path = self._response_path(ref, processed.get("receipt_path"))
            response, _ = read_json(response_path, limit=self._max)
            fields = {
                "schema_version": RESPONDER_SCHEMA,
                "status": _PUBLISHED,
                "agent_uid": ref.agent_uid,
                "delivery_id": ref.delivery_id,
                "packet_id": ref.packet_id,
                "reply_subject": envelope.get("reply_subject"),
                "semantic_reply_claim": True,
                "domain_receipt_claim": True,
                "handler_ack_is_semantic_cognition": False,
                "authenticated_target_runtime_claim": False,
                "no_publish": False,
            }
            for key, expected in fields.items():
                _field(response, key, expected, "semantic responder receipt")
            _exact_path(response.get("delivery_record_path"), delivery_path, "responder delivery path")
            _exact_path(response.get("receipt_path"), response_path, "responder receipt path")
            artifact_path, artifact_sha, artifact = self._semantic_chain(
                ref=ref,
                delivery_path=delivery_path,
                delivery=delivery,
                envelope=envelope,
                response=response,
            )
            self._publish_chain(
                ref=ref,
                envelope=envelope,
                response=response,
                artifact_path=artifact_path,
                artifact_sha=artifact_sha,
                artifact=artifact,
            )
            return artifact_sha, status, True
        except _IncompleteEvidence:
            return "", status, False


__all__ = [
    "CanonicalA2AEvidenceReader",
    "DELIVERY_SCHEMA",
    "read_bytes",
    "read_json",
    "safe_file",
]
