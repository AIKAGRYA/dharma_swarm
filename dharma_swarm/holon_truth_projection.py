"""Project standalone Holon receipts into Dharma runtime truth.

The standalone ``holon`` package owns local receipts only. This parent-side
adapter makes those receipts visible in ``RuntimeStateStore`` without adding a
``dharma_swarm`` import to the standalone package.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.living_dock_verifier import verify_living_dock
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    DelegationRun,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity

PROJECTION_SCHEMA_VERSION = "dharma.holon_receipt_projection.v1"
SOURCE_RECEIPT_SCHEMA_VERSION = "holon.runtime_receipt.v1"

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class HolonReceiptProjection:
    """Result of projecting one standalone Holon receipt."""

    source_receipt_id: str
    parent_receipt_id: str
    run_id: str
    task_id: str
    correlation_id: str
    status: str
    artifact_ids: list[str] = field(default_factory=list)
    source_digest_verified: bool = False
    living_dock_status: str = ""
    already_projected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_holon_receipt(
    receipt_path: Path | str,
    *,
    runtime_state: RuntimeStateStore | None = None,
    runtime_db_path: Path | str | None = None,
    agents_root: Path | str | None = None,
    dharma_home: Path | str | None = None,
    session_id: str = "",
    mission_id: str = "",
    parent_run_id: str = "",
    require_living_dock: bool = False,
) -> HolonReceiptProjection:
    """Project a standalone receipt into the parent runtime truth spine."""

    path = Path(receipt_path).expanduser().resolve()
    source = _read_receipt(path)
    source_receipt_id = _required_text(source, "receipt_id")
    holon_name = _required_text(source, "subject")
    source_status = str(source.get("status") or "")
    created_at = _parse_utc(str(source.get("created_at") or ""))
    lifecycle_status = _lifecycle_status(source_status)
    root = Path(agents_root).expanduser().resolve() if agents_root else path.parents[1]

    living_report = verify_living_dock(
        holon_name,
        dharma_home=dharma_home,
        agents_root=root,
        require_dialogue=False,
        require_sanctum=False,
    )
    projection_block_reason = ""
    if require_living_dock and living_report.status == "fail":
        lifecycle_status = "blocked"
        projection_block_reason = "living_dock_verifier_failed"

    identity = _identity_for_receipt(
        source,
        holon_name=holon_name,
        session_id=session_id,
        mission_id=mission_id,
        parent_run_id=parent_run_id,
    )
    parent_receipt_id = f"rr_{_safe_id(identity.run_id)}_holon_projection"
    store = runtime_state or RuntimeStateStore(runtime_db_path)
    artifact_items = _artifact_items(source)
    artifact_ids = [
        _artifact_id(source_receipt_id, index, item)
        for index, item in enumerate(artifact_items, start=1)
    ]

    if _runtime_receipt_exists(store, parent_receipt_id):
        return HolonReceiptProjection(
            source_receipt_id=source_receipt_id,
            parent_receipt_id=parent_receipt_id,
            run_id=identity.run_id,
            task_id=identity.task_id,
            correlation_id=identity.correlation_id,
            status=lifecycle_status,
            artifact_ids=artifact_ids,
            source_digest_verified=_source_digest_verified(source),
            living_dock_status=living_report.status,
            already_projected=True,
        )

    source_digest_verified = _source_digest_verified(source)
    provider_context = _provider_context(source)
    artifact_refs = [f"artifact_records:{artifact_id}" for artifact_id in artifact_ids]
    projection_payload = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "source_receipt_ref": str(path),
        "source_receipt_id": source_receipt_id,
        "source_receipt_kind": str(source.get("kind") or ""),
        "source_receipt_status": source_status,
        "source_receipt_digest": str(source.get("digest") or ""),
        "source_digest_verified": source_digest_verified,
        "holon_name": holon_name,
        "standalone_side_effect_key": str(source.get("side_effect_key") or ""),
        "lifecycle_status": lifecycle_status,
        "projection_block_reason": projection_block_reason,
        "artifact_refs": artifact_refs,
        "standalone_artifact_refs": list(source.get("artifact_refs") or []),
        "verifier_refs": list(source.get("verifier_refs") or []),
        "living_dock": living_report.to_dict(),
        "provider_context": provider_context,
        "source_payload": dict(source.get("payload") or {}),
        **provider_context,
    }
    metadata = {
        "mission_id": mission_id or f"holon:{holon_name}",
        "mission": mission_id or f"holon:{holon_name}",
        "holon_receipt_projection": True,
        "source_receipt_id": source_receipt_id,
        "source_receipt_path": str(path),
        "source_receipt_digest": str(source.get("digest") or ""),
        "source_digest_verified": source_digest_verified,
        "living_dock_status": living_report.status,
        "projection_block_reason": projection_block_reason,
        **provider_context,
        **identity.to_metadata(),
    }

    store.record_execution_identity_sync(
        identity,
        source="holon_truth_projection",
        metadata={
            "surface": "holon_truth_projection",
            "source_receipt_id": source_receipt_id,
            "source_receipt_path": str(path),
            "source_digest_verified": source_digest_verified,
        },
    )
    store.create_task_claim_sync(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            status=lifecycle_status,
            session_id=identity.session_id,
            claimed_at=created_at,
            acked_at=created_at,
            heartbeat_at=created_at if lifecycle_status in {"claimed", "running"} else None,
            metadata=metadata,
        )
    )
    store.create_delegation_run_sync(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            status=lifecycle_status,
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            parent_run_id=identity.parent_run_id,
            assigned_by="holon_truth_projection",
            requested_output=["holon_cycle_result", "receipt_projection"],
            current_artifact_id=artifact_ids[0] if artifact_ids else "",
            started_at=created_at,
            completed_at=created_at if lifecycle_status in {"completed", "failed", "blocked"} else None,
            failure_code=projection_block_reason or _failure_code(source_status),
            metadata=metadata,
        )
    )
    _record_artifacts(
        store,
        identity=identity,
        source=source,
        source_path=path,
        artifact_items=artifact_items,
        artifact_ids=artifact_ids,
        created_at=created_at,
    )

    projection_side_effect_key = f"delegation_run:{identity.run_id}:{lifecycle_status}"
    store.record_receipt_for_identity_sync(
        identity,
        receipt_id=parent_receipt_id,
        receipt_type="side_effect_complete",
        status=lifecycle_status,
        side_effect_key=projection_side_effect_key,
        payload=projection_payload,
    )
    return HolonReceiptProjection(
        source_receipt_id=source_receipt_id,
        parent_receipt_id=parent_receipt_id,
        run_id=identity.run_id,
        task_id=identity.task_id,
        correlation_id=identity.correlation_id,
        status=lifecycle_status,
        artifact_ids=artifact_ids,
        source_digest_verified=source_digest_verified,
        living_dock_status=living_report.status,
        already_projected=False,
    )


def project_holon_receipt_dir(
    receipt_dir: Path | str,
    *,
    runtime_state: RuntimeStateStore | None = None,
    runtime_db_path: Path | str | None = None,
    agents_root: Path | str | None = None,
    dharma_home: Path | str | None = None,
    session_id: str = "",
    mission_id: str = "",
    require_living_dock: bool = False,
) -> list[HolonReceiptProjection]:
    """Project every standalone receipt JSON file in a Holon receipt directory."""

    root = Path(receipt_dir).expanduser().resolve()
    store = runtime_state or RuntimeStateStore(runtime_db_path)
    projections: list[HolonReceiptProjection] = []
    for path in sorted(root.glob("hrcpt_*.json")):
        projections.append(
            project_holon_receipt(
                path,
                runtime_state=store,
                agents_root=agents_root,
                dharma_home=dharma_home,
                session_id=session_id,
                mission_id=mission_id,
                require_living_dock=require_living_dock,
            )
        )
    return projections


def _read_receipt(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Holon receipt is not a JSON object: {path}")
    if data.get("schema_version") != SOURCE_RECEIPT_SCHEMA_VERSION:
        raise ValueError(f"unsupported Holon receipt schema: {data.get('schema_version')!r}")
    return data


def _required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"Holon receipt missing {key}")
    return value


def _safe_id(value: str) -> str:
    cleaned = _SAFE_ID_RE.sub("_", str(value or "").strip()).strip("_")
    return cleaned or "unknown"


def _parse_utc(raw: str) -> datetime:
    value = str(raw or "").strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _identity_for_receipt(
    source: dict[str, Any],
    *,
    holon_name: str,
    session_id: str,
    mission_id: str,
    parent_run_id: str,
) -> ExecutionIdentity:
    receipt_id = _safe_id(_required_text(source, "receipt_id"))
    metadata = dict((source.get("payload") or {}).get("metadata") or {})
    existing = ExecutionIdentity.from_metadata(metadata, require=False)
    if existing is not None:
        return existing.with_updates(
            agent_id=existing.agent_id or holon_name,
            session_id=existing.session_id or session_id,
            parent_run_id=existing.parent_run_id or parent_run_id,
            metadata={
                "holon_projection_source_receipt_id": receipt_id,
                "mission_id": mission_id or f"holon:{holon_name}",
            },
        )
    return ExecutionIdentity.new(
        task_id=f"task_holon_{receipt_id}",
        agent_id=holon_name,
        session_id=session_id or f"holon_projection_{holon_name}",
        trace_id=f"trace_holon_{receipt_id}",
        correlation_id=f"corr_holon_{receipt_id}",
        run_id=f"run_holon_{receipt_id}",
        claim_id=f"claim_holon_{receipt_id}",
        idempotency_key=f"idem_holon_{receipt_id}",
        parent_run_id=parent_run_id,
        metadata={
            "holon_projection_source_receipt_id": receipt_id,
            "mission_id": mission_id or f"holon:{holon_name}",
        },
    )


def _lifecycle_status(source_status: str) -> str:
    status = str(source_status or "").strip().lower()
    if status in {"ran", "pass", "completed", "ok", "verified"}:
        return "completed"
    if status in {"failed", "error"} or status.endswith(":error"):
        return "failed"
    if status.startswith("halted:") or status in {"warn", "blocked"}:
        return "blocked"
    if status in {"running", "claimed", "queued"}:
        return status
    return "blocked"


def _failure_code(source_status: str) -> str:
    lifecycle = _lifecycle_status(source_status)
    if lifecycle == "failed":
        return "holon_source_error"
    if lifecycle == "blocked":
        return "holon_source_blocked"
    return ""


def _provider_context(source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source.get("payload") or {})
    provider = str(payload.get("provider") or "").strip()
    model = str(payload.get("model") or "").strip()
    if provider and model:
        return {
            "actual_served_provider": provider,
            "actual_served_model": model,
            "provider_model_truth_source": "runtime_provider.actual_served",
            "provider_execution": True,
            "holon_provider_cost_usd": float(payload.get("cost_usd") or 0.0),
            "holon_provider_finish_reason": str(payload.get("finish_reason") or ""),
        }
    return {
        "provider_execution": False,
        "provider_model_applicability": "not_applicable",
        "no_provider_model_reason": f"standalone_holon_status:{source.get('status') or ''}",
    }


def _artifact_items(source: dict[str, Any]) -> list[dict[str, Any]]:
    payload = dict(source.get("payload") or {})
    items = [item for item in payload.get("artifacts") or [] if isinstance(item, dict)]
    if items:
        return items
    return [
        {"kind": "file", "path": str(path), "digest": ""}
        for path in source.get("artifact_refs") or []
        if str(path or "").strip()
    ]


def _artifact_id(source_receipt_id: str, index: int, item: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "source_receipt_id": source_receipt_id,
                "index": index,
                "path": str(item.get("path") or ""),
                "digest": str(item.get("digest") or ""),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return f"artifact_holon_{digest[:24]}"


def _record_artifacts(
    store: RuntimeStateStore,
    *,
    identity: ExecutionIdentity,
    source: dict[str, Any],
    source_path: Path,
    artifact_items: list[dict[str, Any]],
    artifact_ids: list[str],
    created_at: datetime,
) -> None:
    for artifact_id, item in zip(artifact_ids, artifact_items, strict=True):
        artifact_path = Path(str(item.get("path") or "")).expanduser()
        checksum = str(item.get("digest") or "")
        if not checksum and artifact_path.exists() and artifact_path.is_file():
            checksum = _sha256_file(artifact_path)
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind=str(item.get("kind") or "holon_artifact"),
            session_id=identity.session_id,
            task_id=identity.task_id,
            run_id=identity.run_id,
            trace_id=identity.trace_id,
            payload_path=str(artifact_path) if str(item.get("path") or "") else "",
            checksum=checksum,
            promotion_state="ephemeral",
            created_at=created_at,
            metadata={
                "source_receipt_id": str(source.get("receipt_id") or ""),
                "source_receipt_path": str(source_path),
                "source_artifact": dict(item),
            },
        )
        asyncio.run(store.record_artifact(record))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _source_digest_verified(source: dict[str, Any]) -> bool:
    observed = str(source.get("digest") or "")
    if not observed:
        return False
    material = {
        "schema_version": source.get("schema_version"),
        "kind": source.get("kind"),
        "subject": source.get("subject"),
        "status": source.get("status"),
        "side_effect_key": source.get("side_effect_key"),
        "payload": source.get("payload") or {},
        "artifact_refs": source.get("artifact_refs") or [],
        "verifier_refs": source.get("verifier_refs") or [],
        "receipt_id": source.get("receipt_id"),
    }
    return observed == _stable_digest(material)


def _stable_digest(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _runtime_receipt_exists(store: RuntimeStateStore, receipt_id: str) -> bool:
    store.init_db_sync()
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT 1 FROM runtime_receipts WHERE receipt_id = ? LIMIT 1",
            (receipt_id,),
        ).fetchone()
    return row is not None


__all__ = [
    "HolonReceiptProjection",
    "PROJECTION_SCHEMA_VERSION",
    "project_holon_receipt",
    "project_holon_receipt_dir",
]
