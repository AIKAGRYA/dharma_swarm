#!/usr/bin/env python3
"""Supervise persistent Codex Composer seats and publish evidence-only replica presence."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import re
import signal
import socket
import ssl
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from codex_composer_seat import SeatStatus, ensure_seat
from dharma_swarm.spine.identity import process_boot_id
AGENT_UID = "codex_composer"
MEMORY_NAMESPACE = "agent:codex_composer"
IDENTITY_INVARIANT_DIGEST = "sha256:47079c5f0971a1a1ebeaa10b80790602d8bee6d0576746da04ee0347c24f76e8"
CANONICAL_ENVELOPE_SCHEMA = "dharma.nats.envelope.v1"
FLEET_HEARTBEAT_SCHEMA = "dharma.a2a.fleet_heartbeat.v1"
REPLICA_HEARTBEAT_SCHEMA = "dharma.a2a.codex_composer_replica.v1"
CANONICAL_PRESENCE_SUBJECT = f"dharma.agent.{AGENT_UID}.presence"
REPLICA_SUBJECT_PREFIX = f"dharma.a2a.{AGENT_UID}.replica"
EXPECTED_REPLICAS = {"agni": "delivery_relay", "rushabdev": "hot_standby", "meghadharma": "orientation_primary"}
EXPECTED_NATS_USERS = {
    "agni": "codex_composer_agni",
    "rushabdev": "codex_composer_rushabdev",
    "meghadharma": "codex_composer_primary",
}
_SAFE_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
class ReplicaConfigurationError(RuntimeError):
    """The replica cannot prove its configured identity or safety boundary."""
@dataclass(frozen=True, slots=True)
class ReplicaConfig:
    instance_id: str
    replica_role: str
    nats_url: str
    nats_user: str
    nats_password: str = field(repr=False)
    ca_file: Path | None = None
    card_path: Path = Path("/opt/dharma-codex-composer/codex_composer.agent-card.json")
    card_sha256: str = ""
    memory_path: Path = Path("/opt/dharma-codex-composer/codex_composer.memory.json")
    memory_sha256: str = ""
    workspace: Path = Path("/opt/dharma-codex-composer/repo")
    codex_bin: str = "codex"
    seat_user: str = "codex-composer-seat"
    tmux_session: str = AGENT_UID
    state_dir: Path = Path("/var/lib/dharma-codex-composer")
    interval_seconds: float = 20.0
    publish_canonical_presence: bool = False
    def __post_init__(self) -> None:
        if not _SAFE_TOKEN.fullmatch(self.instance_id):
            raise ReplicaConfigurationError("invalid replica instance id")
        expected_role = EXPECTED_REPLICAS.get(self.instance_id)
        if expected_role is None or self.replica_role != expected_role:
            raise ReplicaConfigurationError("replica role does not match canonical topology")
        if self.nats_user != EXPECTED_NATS_USERS.get(self.instance_id):
            raise ReplicaConfigurationError(
                "NATS transport principal does not match the replica instance"
            )
        parsed = urlparse(self.nats_url)
        if parsed.scheme not in {"nats", "tls", "ws", "wss"} or not parsed.hostname:
            raise ReplicaConfigurationError("invalid NATS URL")
        if parsed.username or parsed.password:
            raise ReplicaConfigurationError("NATS credentials must not be embedded in URL")
        if self.instance_id in {"agni", "rushabdev"}:
            if parsed.scheme != "wss":
                raise ReplicaConfigurationError("remote replicas require WSS transport")
            if (
                self.ca_file is None
                or not self.ca_file.is_absolute()
                or not self.ca_file.is_file()
            ):
                raise ReplicaConfigurationError("remote replicas require a pinned CA file")
        if self.instance_id == "meghadharma" and (
            parsed.scheme != "nats"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ReplicaConfigurationError(
                "the hub-local primary must use the loopback NATS listener"
            )
        if not self.nats_password:
            raise ReplicaConfigurationError("NATS password is required")
        if not _SHA256.fullmatch(self.card_sha256):
            raise ReplicaConfigurationError("invalid expected card sha256")
        if not _SHA256.fullmatch(self.memory_sha256):
            raise ReplicaConfigurationError("invalid expected memory sha256")
        if not self.tmux_session or not _SAFE_TOKEN.fullmatch(self.tmux_session):
            raise ReplicaConfigurationError("invalid tmux session")
        if not self.seat_user or not _SAFE_TOKEN.fullmatch(self.seat_user):
            raise ReplicaConfigurationError("invalid seat user")
        if not 5 <= self.interval_seconds <= 60:
            raise ReplicaConfigurationError("heartbeat interval must be between 5 and 60 seconds")
    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ReplicaConfig":
        env = os.environ if environ is None else environ
        def required(name: str) -> str:
            value = str(env.get(name, "")).strip()
            if not value:
                raise ReplicaConfigurationError(f"missing environment variable: {name}")
            return value
        def boolean(name: str) -> bool:
            return str(env.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}
        try:
            interval = float(env.get("CODEX_COMPOSER_HEARTBEAT_INTERVAL_SECONDS", "20"))
        except ValueError as exc:
            raise ReplicaConfigurationError("invalid heartbeat interval") from exc
        return cls(
            instance_id=required("CODEX_COMPOSER_INSTANCE_ID"),
            replica_role=required("CODEX_COMPOSER_REPLICA_ROLE"),
            nats_url=required("CODEX_COMPOSER_NATS_URL"),
            nats_user=required("CODEX_COMPOSER_NATS_USER"),
            nats_password=required("CODEX_COMPOSER_NATS_PASSWORD"),
            ca_file=(
                Path(required("CODEX_COMPOSER_CA_FILE"))
                if required("CODEX_COMPOSER_INSTANCE_ID") in {"agni", "rushabdev"}
                else None
            ),
            card_path=Path(required("CODEX_COMPOSER_CARD_PATH")),
            card_sha256=required("CODEX_COMPOSER_CARD_SHA256"),
            memory_path=Path(required("CODEX_COMPOSER_MEMORY_PATH")),
            memory_sha256=required("CODEX_COMPOSER_MEMORY_SHA256"),
            workspace=Path(env.get("CODEX_COMPOSER_WORKSPACE", "/opt/dharma-codex-composer/repo")),
            codex_bin=env.get("CODEX_COMPOSER_CODEX_BIN", "codex").strip() or "codex",
            seat_user=env.get("CODEX_COMPOSER_SEAT_USER", "codex-composer-seat").strip(),
            tmux_session=env.get("CODEX_COMPOSER_TMUX_SESSION", AGENT_UID).strip(),
            state_dir=Path(env.get("CODEX_COMPOSER_STATE_DIR", "/var/lib/dharma-codex-composer")),
            interval_seconds=interval,
            publish_canonical_presence=boolean("CODEX_COMPOSER_PUBLISH_CANONICAL_PRESENCE"),
        )
    @property
    def replica_subject(self) -> str:
        return f"{REPLICA_SUBJECT_PREFIX}.{self.instance_id}.heartbeat"
@dataclass(frozen=True, slots=True)
class BundleIntegrity:
    card_sha256: str
    memory_sha256: str
    bundle_sha256: str
    canonical_presence_instance: str
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sd_notify(message: str, environ: Mapping[str, str] | None = None) -> bool:
    """Send one bounded systemd notification without a runtime dependency."""
    env = os.environ if environ is None else environ
    address = str(env.get("NOTIFY_SOCKET", ""))
    if not address or len(message.encode("utf-8")) > 4096:
        return False
    if address.startswith("@"):  # Linux abstract Unix-domain socket.
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.connect(address)
            client.sendall(message.encode("utf-8"))
        return True
    except OSError:
        return False
def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str
    ).encode()
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReplicaConfigurationError(f"cannot load {label}") from exc
    if not isinstance(value, dict):
        raise ReplicaConfigurationError(f"{label} must be a JSON object")
    return value
def validate_bundle(config: ReplicaConfig) -> BundleIntegrity:
    card_digest = sha256_file(config.card_path)
    memory_digest = sha256_file(config.memory_path)
    if card_digest != config.card_sha256:
        raise ReplicaConfigurationError("card sha256 mismatch")
    if memory_digest != config.memory_sha256:
        raise ReplicaConfigurationError("memory sha256 mismatch")
    card = _json_object(config.card_path, "AgentCard")
    metadata = card.get("metadata")
    if (
        card.get("name") != AGENT_UID
        or card.get("agent_uid") != AGENT_UID
        or not isinstance(metadata, dict)
        or metadata.get("memory_namespace") != MEMORY_NAMESPACE
        or metadata.get("identity_invariant_digest") != IDENTITY_INVARIANT_DIGEST
        or metadata.get("logical_nats_identity") != AGENT_UID
        or metadata.get("semantic_consumer_enabled") is not False
        or metadata.get("execution_lease_required") is not True
    ):
        raise ReplicaConfigurationError("AgentCard identity contract mismatch")
    memory = _json_object(config.memory_path, "continuity memory")
    topology = ((memory.get("continuity") or {}).get("topology") or {})
    replicas = topology.get("replicas") if isinstance(topology, dict) else None
    observed = {
        item.get("instance_id"): item.get("role")
        for item in replicas or []
        if isinstance(item, dict)
    }
    principals = {
        item.get("instance_id"): item.get("transport_principal")
        for item in replicas or []
        if isinstance(item, dict)
    }
    primary = topology.get("canonical_presence_instance")
    if (
        memory.get("agent_uid") != AGENT_UID
        or memory.get("memory_namespace") != MEMORY_NAMESPACE
        or memory.get("identity_invariant_digest") != IDENTITY_INVARIANT_DIGEST
        or memory.get("authority") != "continuity_only_noncanonical"
        or observed != EXPECTED_REPLICAS
        or principals != EXPECTED_NATS_USERS
        or topology.get("logical_nats_identity") != AGENT_UID
        or topology.get("remote_transport") != "wss_tls"
        or primary not in EXPECTED_REPLICAS
    ):
        raise ReplicaConfigurationError("continuity-memory identity contract mismatch")
    if config.publish_canonical_presence != (config.instance_id == primary):
        raise ReplicaConfigurationError("canonical presence publisher does not match memory topology")
    bundle_digest = hashlib.sha256(
        canonical_bytes(
            {
                "agent_uid": AGENT_UID,
                "card_sha256": card_digest,
                "memory_sha256": memory_digest,
                "identity_invariant_digest": IDENTITY_INVARIANT_DIGEST,
            }
        )
    ).hexdigest()
    return BundleIntegrity(card_digest, memory_digest, bundle_digest, str(primary))
def _message_id(config: ReplicaConfig, boot_id: str, sequence: int, kind: str) -> str:
    return f"cc-{config.instance_id}-{boot_id[:12]}-{sequence:08d}-{kind}"


def _envelope_context(
    config: ReplicaConfig, *, message_id: str, boot_id: str
) -> dict[str, Any]:
    """Provide the current-main trace, actor, and causality envelope fields."""
    trace_id = hashlib.sha256(f"trace:{AGENT_UID}:{boot_id}".encode()).hexdigest()[:32]
    span_id = hashlib.sha256(message_id.encode()).hexdigest()[:16]
    correlation_id = f"cc-{config.instance_id}-{boot_id}"
    actor = {
        "from_agent": AGENT_UID,
        "to_agent": "fleet",
        "execution_agent": AGENT_UID,
        "session_id": boot_id,
    }
    causality = {
        "message_id": message_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": "",
        "correlation_id": correlation_id,
        "causation_id": "",
    }
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": "",
        "correlation_id": correlation_id,
        "causation_id": "",
        "actor": actor,
        "causality": causality,
    }
def build_replica_envelope(
    config: ReplicaConfig,
    integrity: BundleIntegrity,
    seat: SeatStatus,
    *,
    observed_at: datetime,
    boot_id: str,
    sequence: int,
) -> dict[str, Any]:
    timestamp = observed_at.astimezone(timezone.utc).isoformat()
    message_id = _message_id(config, boot_id, sequence, "replica")
    context = _envelope_context(config, message_id=message_id, boot_id=boot_id)
    return {
        "schema": CANONICAL_ENVELOPE_SCHEMA,
        "message_id": message_id,
        "subject": config.replica_subject,
        "from_agent": AGENT_UID,
        "to_agent": "fleet",
        **context,
        "kind": "heartbeat",
        "created_at": timestamp,
        "requires_ack": True,
        "payload": {
            "schema": REPLICA_HEARTBEAT_SCHEMA,
            "agent_uid": AGENT_UID,
            "instance_id": config.instance_id,
            "replica_role": config.replica_role,
            "status": "online" if seat.ready else "degraded",
            "observed_at": timestamp,
            "boot_id": boot_id,
            "card_sha256": integrity.card_sha256,
            "memory_sha256": integrity.memory_sha256,
            "bundle_sha256": integrity.bundle_sha256,
            "nats_identity": AGENT_UID,
            "transport_principal": config.nats_user,
            "semantic_consumer_enabled": False,
            "execution_lease_active": False,
            "seat": asdict(seat),
        },
    }
def build_canonical_presence_envelope(
    config: ReplicaConfig,
    integrity: BundleIntegrity,
    seat: SeatStatus,
    *,
    observed_at: datetime,
    boot_id: str,
    sequence: int,
) -> dict[str, Any]:
    timestamp = observed_at.astimezone(timezone.utc).isoformat()
    message_id = _message_id(config, boot_id, sequence, "presence")
    context = _envelope_context(config, message_id=message_id, boot_id=boot_id)
    return {
        "schema": CANONICAL_ENVELOPE_SCHEMA,
        "message_id": message_id,
        "subject": CANONICAL_PRESENCE_SUBJECT,
        "from_agent": AGENT_UID,
        "to_agent": "fleet",
        **context,
        "kind": "heartbeat",
        "created_at": timestamp,
        "requires_ack": True,
        "payload": {
            "schema": FLEET_HEARTBEAT_SCHEMA,
            "agent_uid": AGENT_UID,
            "status": "online" if seat.ready else "degraded",
            "last_heartbeat": timestamp,
            "metadata": {
                "instance_id": config.instance_id,
                "replica_role": config.replica_role,
                "boot_id": boot_id,
                "card_sha256": integrity.card_sha256,
                "memory_sha256": integrity.memory_sha256,
                "bundle_sha256": integrity.bundle_sha256,
                "nats_identity": AGENT_UID,
                "transport_principal": config.nats_user,
                "seat_state": seat.state,
                "tmux_session": seat.tmux_session,
                "pane_command": seat.pane_command,
                "codex_version": seat.codex_version,
                "semantic_consumer_enabled": False,
                "execution_lease_active": False,
                "replica_subject": config.replica_subject,
            },
        },
    }
def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
def _rotate_publish_log(
    path: Path,
    *,
    max_bytes: int = 50 * 1024 * 1024,
    generations: int = 8,
) -> None:
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    oldest = path.with_name(f"{path.name}.{generations}")
    oldest.unlink(missing_ok=True)
    for index in range(generations - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            source.replace(path.with_name(f"{path.name}.{index + 1}"))
    path.replace(path.with_name(f"{path.name}.1"))
def _append_publish_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_publish_log(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
async def _publish(js: Any, subject: str, envelope: dict[str, Any]) -> dict[str, Any]:
    message_id = str(envelope["message_id"])
    ack = await asyncio.wait_for(
        js.publish(
            subject,
            canonical_bytes(envelope),
            headers={"Nats-Msg-Id": message_id},
        ),
        timeout=12,
    )
    return {"subject": subject, "message_id": message_id, "stream": ack.stream, "seq": ack.seq}
async def run_service(config: ReplicaConfig) -> None:
    try:
        import nats
    except ImportError as exc:
        raise ReplicaConfigurationError("nats-py is required") from exc
    config.state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(config.state_dir, 0o700)
    boot_id = process_boot_id()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    _sd_notify("READY=1\nSTATUS=supervising Codex Composer presence\nWATCHDOG=1")
    sequence = 0
    backoff = 2.0
    tls_context = (
        ssl.create_default_context(cafile=str(config.ca_file))
        if config.ca_file is not None
        else None
    )
    while not stop.is_set():
        _sd_notify("WATCHDOG=1")
        connection: Any | None = None
        try:
            integrity = validate_bundle(config)
            connection = await nats.connect(
                servers=[config.nats_url],
                user=config.nats_user,
                password=config.nats_password,
                name=f"{AGENT_UID}/{config.instance_id}",
                connect_timeout=8,
                reconnect_time_wait=2,
                max_reconnect_attempts=-1,
                tls=tls_context,
            )
            js = connection.jetstream()
            backoff = 2.0
            while not stop.is_set():
                _sd_notify("WATCHDOG=1")
                sequence += 1
                integrity = validate_bundle(config)
                seat = await asyncio.to_thread(ensure_seat, config, integrity)
                observed_at = utc_now()
                replica = build_replica_envelope(
                    config,
                    integrity,
                    seat,
                    observed_at=observed_at,
                    boot_id=boot_id,
                    sequence=sequence,
                )
                stored = [await _publish(js, config.replica_subject, replica)]
                if config.publish_canonical_presence:
                    presence = build_canonical_presence_envelope(
                        config,
                        integrity,
                        seat,
                        observed_at=observed_at,
                        boot_id=boot_id,
                        sequence=sequence,
                    )
                    stored.append(await _publish(js, CANONICAL_PRESENCE_SUBJECT, presence))
                heartbeat = {
                    "schema_version": "dharma.codex_composer.replica_local_status.v1",
                    "agent_uid": AGENT_UID,
                    "instance_id": config.instance_id,
                    "replica_role": config.replica_role,
                    "observed_at": observed_at.isoformat(),
                    "status": "online" if seat.ready else "degraded",
                    "boot_id": boot_id,
                    "sequence": sequence,
                    "card_sha256": integrity.card_sha256,
                    "memory_sha256": integrity.memory_sha256,
                    "bundle_sha256": integrity.bundle_sha256,
                    "seat": asdict(seat),
                    "stored": stored,
                }
                _atomic_json(config.state_dir / "heartbeat.json", heartbeat)
                _append_publish_log(
                    config.state_dir / "publish-log.jsonl",
                    {
                        "schema_version": "dharma.codex_composer.replica_publish_log.v1",
                        **heartbeat,
                    },
                )
                _sd_notify("WATCHDOG=1\nSTATUS=replica heartbeat stored")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=config.interval_seconds)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _sd_notify("WATCHDOG=1\nSTATUS=replica degraded; retrying")
            _atomic_json(
                config.state_dir / "heartbeat.json",
                {
                    "schema_version": "dharma.codex_composer.replica_local_status.v1",
                    "agent_uid": AGENT_UID,
                    "instance_id": config.instance_id,
                    "status": "degraded",
                    "observed_at": utc_now().isoformat(),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:400],
                },
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60)
        finally:
            if connection is not None:
                try:
                    await connection.drain()
                except Exception:
                    await connection.close()
def main() -> int:
    config = ReplicaConfig.from_env()
    asyncio.run(run_service(config))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
