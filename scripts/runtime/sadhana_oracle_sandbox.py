#!/usr/bin/env python3
"""Root custody membrane for the isolated SADHANA G10 evaluator.

The campaign supervisor may publish an exact request and input, but it never
executes or reads the held-out evaluator, policy, or verdict.  This worker
copies hash-pinned bytes into a fresh run directory and executes the evaluator
as a distinct static identity inside the systemd sandbox that invokes this
module.  A root receipt is made durable before the service-readable terminal.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import pwd
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MISSION_ID = "sadhana-10-20260823"
GOAL_ID = "G10_SAFETY_TCB"
CAMPAIGN_START = datetime(2026, 8, 22, 17, 15, 12, tzinfo=timezone.utc)
CAMPAIGN_STOP = datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc)
REQUEST_SCHEMA = "dharma.sadhana.oracle_launch_request.v1"
TERMINAL_SCHEMA = "dharma.sadhana.oracle_launch_terminal.v1"
SANDBOX_EVIDENCE_SCHEMA = "dharma.sadhana.oracle_sandbox_evidence.v1"
RUN_RECEIPT_SCHEMA = "dharma.sadhana.oracle_sandbox_run.v1"
SERVICE_ACCOUNT = "dharma-sadhana"
ORACLE_ACCOUNT = "dharma-sadhana-oracle"
REQUEST_ROOT = Path("/run/dharma-sadhana/oracle/requests")
TERMINAL_ROOT = Path("/run/dharma-sadhana/oracle/terminals")
INPUT_ROOT = Path("/var/lib/dharma-sadhana/oracle-inputs")
CLAIM_ROOT = Path("/var/lib/dharma-sadhana/oracle-claims")
RUN_ROOT = Path("/var/lib/dharma-sadhana/oracle-runs")
QUARANTINE_ROOT = Path("/var/lib/dharma-sadhana/oracle-quarantine")
RECEIPT_ROOT = Path("/etc/dharma-sadhana/receipts/oracle")
SANDBOX_EVIDENCE_PATH = RECEIPT_ROOT / "oracle-sandbox-evidence.v1.json"
WORKER_UNIT_PATH = Path("/etc/systemd/system/dharma-sadhana-oracle-sandbox.service")
EVALUATOR_PATH = Path(
    "/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/held-out/"
    "g10-evaluator.py"
)
POLICY_PATH = Path(
    "/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/held-out/"
    "g10-policy.json"
)
HELD_OUT_MANIFEST_PATH = Path(
    "/etc/dharma-sadhana/inputs/runtime/sadhana-10-20260823/held-out-oracle.json"
)
EVALUATOR_SHA256 = "1cfec1beb9a1d51dbdb31d1b01c7ca9f912664ec729ea55502c7c7ebedf75a18"
POLICY_SHA256 = "7e368aaabb57424e35b95b87f91b1dd7639a64a1bdf71bb5f4fae83f13890841"
REQUIRED_EVIDENCE_IDS = (
    "P01_AUTHORITY_BINDING",
    "P02_CONTRACT_BINDING",
    "P03_EFFECT_AUDIT",
    "P04_GENERATION_RECOVERY",
    "P05_LEADER_FENCING",
    "P06_ORACLE_SANDBOX",
    "P07_PAUSE_STOP",
    "P08_SECRET_BOUNDARY",
)
PYTHON_PATH = "/usr/bin/python3.12"
SETPRIV_PATH = "/usr/bin/setpriv"
MAX_PROTOCOL_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_ORACLE_BYTES = 4 * 1024 * 1024
_RAW_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@+-]{0,255}\Z")
_REQUEST_NAME = re.compile(r"([0-9a-f]{64})\.oracle\.json\Z")
_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "idempotency_key",
        "campaign_id",
        "mission_id",
        "goal_id",
        "task_id",
        "verifier_run_id",
        "manifest_digest",
        "evaluator_path",
        "evaluator_sha256",
        "policy_path",
        "policy_sha256",
        "input_path",
        "input_sha256",
        "sandbox_evidence_sha256",
        "request_digest",
    }
)
_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "request_digest",
        "status",
        "verdict_payload",
        "verdict_sha256",
        "sandbox_evidence_sha256",
        "completed_at",
        "failure_code",
        "terminal_digest",
    }
)


class OracleSandboxError(RuntimeError):
    """The release-owned evaluator membrane failed closed."""


class InvalidOracleRequest(OracleSandboxError):
    """One service-authored request is malformed and cannot be executed."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise OracleSandboxError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OracleSandboxError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: Mapping[str, Any], *, omit: str | None = None) -> str:
    unsigned = dict(value)
    if omit is not None:
        unsigned.pop(omit, None)
    return "sha256:" + hashlib.sha256(_canonical(unsigned)).hexdigest()


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_gid,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    _need(bool(nofollow and directory), "oracle custody requires no-follow dirfds")
    return os.O_RDONLY | nofollow | directory


def _open_directory(path: Path, *, uid: int, gid: int, mode: int) -> int:
    _need(path.is_absolute() and ".." not in path.parts, "oracle root path differs")
    descriptor = os.open("/", _directory_flags())
    try:
        for component in path.parts[1:]:
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        details = os.fstat(descriptor)
        _need(
            stat.S_ISDIR(details.st_mode)
            and details.st_uid == uid
            and details.st_gid == gid
            and stat.S_IMODE(details.st_mode) == mode,
            f"oracle directory custody differs: {path.name}",
        )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_at(
    directory: int,
    name: str,
    *,
    uid: int,
    gid: int,
    mode: int,
    maximum: int,
    label: str,
) -> tuple[bytes, os.stat_result]:
    _need("/" not in name and name not in {"", ".", ".."}, f"{label} name differs")
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory,
    )
    try:
        before = os.fstat(descriptor)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == uid
            and before.st_gid == gid
            and stat.S_IMODE(before.st_mode) == mode
            and before.st_nlink == 1
            and 0 < before.st_size <= maximum,
            f"{label} custody differs",
        )
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _need(_identity(before) == _identity(after), f"{label} changed while read")
    _need(len(raw) == before.st_size and len(raw) <= maximum, f"{label} read differs")
    return raw, before


def _read_path(
    path: Path,
    *,
    parent_uid: int,
    parent_gid: int,
    parent_mode: int,
    file_uid: int,
    file_gid: int,
    file_mode: int,
    maximum: int,
    label: str,
) -> tuple[bytes, os.stat_result]:
    directory = _open_directory(
        path.parent,
        uid=parent_uid,
        gid=parent_gid,
        mode=parent_mode,
    )
    try:
        return _read_at(
            directory,
            path.name,
            uid=file_uid,
            gid=file_gid,
            mode=file_mode,
            maximum=maximum,
            label=label,
        )
    finally:
        os.close(directory)


def _decode_canonical(raw: bytes, *, label: str, maximum: int) -> dict[str, Any]:
    _need(0 < len(raw) <= maximum and raw.endswith(b"\n"), f"{label} framing differs")
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OracleSandboxError(f"{label} is not strict JSON") from exc
    _need(type(payload) is dict and raw == _canonical(payload), f"{label} is not canonical")
    return payload


def _decode_evidence(raw: bytes, *, release_sha: str, worker_unit_sha256: str) -> dict[str, Any]:
    payload = _decode_canonical(raw, label="oracle sandbox evidence", maximum=MAX_PROTOCOL_BYTES)
    required = {
        "schema_version",
        "campaign_id",
        "release_sha",
        "worker_unit_path",
        "worker_unit_sha256",
        "private_network",
        "network_interfaces",
        "non_loopback_route_count",
        "protect_system_strict",
        "no_new_privileges",
        "oracle_identity_separated",
        "canonical_state_inaccessible",
        "credential_root_inaccessible",
        "probe_output_created_and_removed",
        "evaluator_executed",
        "verdict",
        "receipt_digest",
    }
    _need(set(payload) == required, "oracle sandbox evidence fields differ")
    _need(
        payload["schema_version"] == SANDBOX_EVIDENCE_SCHEMA
        and payload["campaign_id"] == MISSION_ID
        and payload["release_sha"] == release_sha
        and payload["worker_unit_path"] == str(WORKER_UNIT_PATH)
        and payload["worker_unit_sha256"] == worker_unit_sha256
        and payload["private_network"] is True
        and payload["network_interfaces"] == ["lo"]
        and payload["non_loopback_route_count"] == 0
        and payload["protect_system_strict"] is True
        and payload["no_new_privileges"] is True
        and payload["oracle_identity_separated"] is True
        and payload["canonical_state_inaccessible"] is True
        and payload["credential_root_inaccessible"] is True
        and payload["probe_output_created_and_removed"] is True
        and payload["evaluator_executed"] is False
        and payload["verdict"] == "PASS"
        and payload["receipt_digest"] == _digest(payload, omit="receipt_digest"),
        "oracle sandbox evidence binding differs",
    )
    return payload


def _decode_request(
    raw: bytes,
    *,
    filename: str,
    evidence_digest: str,
    held_out_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        payload = _decode_canonical(raw, label="oracle request", maximum=MAX_PROTOCOL_BYTES)
        _need(set(payload) == _REQUEST_FIELDS, "oracle request fields differ")
        _need(all(type(value) is str for value in payload.values()), "oracle request types differ")
        request_id = payload["request_id"]
        match = _REQUEST_NAME.fullmatch(filename)
        _need(match is not None and match.group(1) == request_id, "oracle request filename differs")
        _need(_RAW_SHA.fullmatch(request_id) is not None, "oracle request id differs")
        _need(
            all(_ID.fullmatch(payload[key]) is not None for key in ("idempotency_key", "task_id", "verifier_run_id")),
            "oracle request identifiers differ",
        )
        _need(
            request_id == hashlib.sha256(payload["idempotency_key"].encode("utf-8")).hexdigest(),
            "oracle request idempotency binding differs",
        )
        _need(
            payload["schema_version"] == REQUEST_SCHEMA
            and payload["campaign_id"] == MISSION_ID
            and payload["mission_id"] == MISSION_ID
            and payload["goal_id"] == GOAL_ID,
            "oracle request campaign binding differs",
        )
        _need(
            all(
                _SHA.fullmatch(payload[key]) is not None
                for key in (
                    "manifest_digest",
                    "evaluator_sha256",
                    "policy_sha256",
                    "input_sha256",
                    "sandbox_evidence_sha256",
                    "request_digest",
                )
            ),
            "oracle request digest shape differs",
        )
        expected_input = INPUT_ROOT / payload["verifier_run_id"] / "input.json"
        _need(
            payload["evaluator_path"] == str(EVALUATOR_PATH)
            and payload["evaluator_sha256"] == f"sha256:{EVALUATOR_SHA256}"
            and payload["policy_path"] == str(POLICY_PATH)
            and payload["policy_sha256"] == f"sha256:{POLICY_SHA256}"
            and payload["input_path"] == str(expected_input)
            and payload["sandbox_evidence_sha256"] == evidence_digest,
            "oracle request path or evidence binding differs",
        )
        _need(
            payload["request_digest"] == _digest(payload, omit="request_digest"),
            "oracle request self-digest differs",
        )
        _need(
            payload["manifest_digest"] == held_out_manifest.get("manifest_digest")
            and payload["task_id"] == held_out_manifest.get("task_id")
            and payload["evaluator_path"] == held_out_manifest.get("evaluator_path")
            and payload["evaluator_sha256"] == held_out_manifest.get("evaluator_sha256")
            and payload["policy_path"] == held_out_manifest.get("policy_path")
            and payload["policy_sha256"] == held_out_manifest.get("policy_sha256"),
            "oracle request differs from held-out manifest",
        )
        return payload
    except OracleSandboxError as exc:
        raise InvalidOracleRequest(str(exc)) from exc


def _decode_held_out_manifest(raw: bytes) -> dict[str, Any]:
    payload = _decode_canonical(raw, label="held-out oracle manifest", maximum=MAX_PROTOCOL_BYTES)
    required = {
        "schema_version",
        "campaign_id",
        "mission_id",
        "goal_id",
        "task_id",
        "task_creation_hash",
        "evaluator_path",
        "evaluator_sha256",
        "policy_path",
        "policy_sha256",
        "required_evidence_ids",
        "oracle_version",
        "manifest_digest",
    }
    _need(set(payload) == required, "held-out oracle manifest fields differ")
    _need(
        payload["schema_version"] == "dharma.sadhana.held_out_oracle_manifest.v1"
        and payload["campaign_id"] == MISSION_ID
        and payload["mission_id"] == MISSION_ID
        and payload["goal_id"] == GOAL_ID
        and payload["evaluator_path"] == str(EVALUATOR_PATH)
        and payload["evaluator_sha256"] == f"sha256:{EVALUATOR_SHA256}"
        and payload["policy_path"] == str(POLICY_PATH)
        and payload["policy_sha256"] == f"sha256:{POLICY_SHA256}"
        and payload["required_evidence_ids"] == list(REQUIRED_EVIDENCE_IDS)
        and payload["oracle_version"] == "v1"
        and _ID.fullmatch(str(payload["task_id"])) is not None
        and _RAW_SHA.fullmatch(str(payload["task_creation_hash"])) is not None
        and _SHA.fullmatch(str(payload["manifest_digest"])) is not None
        and payload["manifest_digest"] == _digest(payload, omit="manifest_digest"),
        "held-out oracle manifest binding differs",
    )
    return payload


def _write_all(descriptor: int, raw: bytes) -> None:
    view = memoryview(raw)
    while view:
        written = os.write(descriptor, view)
        _need(written > 0, "oracle publication write failed")
        view = view[written:]


def _publish_noreplace(
    path: Path,
    raw: bytes,
    *,
    uid: int,
    gid: int,
    mode: int,
    existing_label: str,
) -> bool:
    directory = os.open(path.parent, _directory_flags())
    temporary_name = f".partial-{path.name}-{secrets.token_hex(16)}"
    descriptor = -1
    try:
        try:
            existing, _ = _read_at(
                directory,
                path.name,
                uid=uid,
                gid=gid,
                mode=mode,
                maximum=max(MAX_PROTOCOL_BYTES, len(raw)),
                label=existing_label,
            )
        except FileNotFoundError:
            existing = None
        if existing is not None:
            _need(existing == raw, f"{existing_label} replay conflicts")
            os.fsync(directory)
            return False
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        _write_all(descriptor, raw)
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(
                temporary_name,
                path.name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
        except FileExistsError:
            winner, _ = _read_at(
                directory,
                path.name,
                uid=uid,
                gid=gid,
                mode=mode,
                maximum=max(MAX_PROTOCOL_BYTES, len(raw)),
                label=existing_label,
            )
            _need(winner == raw, f"{existing_label} publication conflicts")
            return False
        finally:
            try:
                os.unlink(temporary_name, dir_fd=directory)
            except FileNotFoundError:
                pass
        os.fsync(directory)
        return True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def _copy_private(
    destination: Path,
    raw: bytes,
    *,
    uid: int,
    gid: int,
    mode: int,
) -> os.stat_result:
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        _write_all(descriptor, raw)
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        result = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    return result


def _load_context(
    *, release_sha: str, service: pwd.struct_passwd
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    _need(_RAW_SHA.fullmatch(release_sha) is not None, "oracle release SHA differs")
    worker_unit_raw, _ = _read_path(
        WORKER_UNIT_PATH,
        parent_uid=0,
        parent_gid=0,
        parent_mode=0o755,
        file_uid=0,
        file_gid=0,
        file_mode=0o644,
        maximum=MAX_PROTOCOL_BYTES,
        label="installed oracle worker unit",
    )
    worker_sha = hashlib.sha256(worker_unit_raw).hexdigest()
    evidence_raw, _ = _read_path(
        SANDBOX_EVIDENCE_PATH,
        parent_uid=0,
        parent_gid=0,
        parent_mode=0o700,
        file_uid=0,
        file_gid=0,
        file_mode=0o600,
        maximum=MAX_PROTOCOL_BYTES,
        label="oracle sandbox evidence",
    )
    evidence = _decode_evidence(
        evidence_raw,
        release_sha=release_sha,
        worker_unit_sha256=worker_sha,
    )
    manifest_raw, _ = _read_path(
        HELD_OUT_MANIFEST_PATH,
        parent_uid=0,
        parent_gid=service.pw_gid,
        parent_mode=0o750,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        file_mode=0o600,
        maximum=MAX_PROTOCOL_BYTES,
        label="held-out oracle manifest",
    )
    manifest = _decode_held_out_manifest(manifest_raw)
    evaluator, _ = _read_path(
        EVALUATOR_PATH,
        parent_uid=0,
        parent_gid=service.pw_gid,
        parent_mode=0o750,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        file_mode=0o600,
        maximum=MAX_ORACLE_BYTES,
        label="held-out evaluator",
    )
    policy, _ = _read_path(
        POLICY_PATH,
        parent_uid=0,
        parent_gid=service.pw_gid,
        parent_mode=0o750,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        file_mode=0o600,
        maximum=MAX_ORACLE_BYTES,
        label="held-out policy",
    )
    _need(hashlib.sha256(evaluator).hexdigest() == EVALUATOR_SHA256, "evaluator hash differs")
    _need(hashlib.sha256(policy).hexdigest() == POLICY_SHA256, "policy hash differs")
    return evidence, manifest, evaluator, policy


def _read_input(payload: Mapping[str, Any], service: pwd.struct_passwd) -> tuple[bytes, os.stat_result]:
    run_root = INPUT_ROOT / str(payload["verifier_run_id"])
    input_path = run_root / "input.json"
    raw, identity = _read_path(
        input_path,
        parent_uid=service.pw_uid,
        parent_gid=service.pw_gid,
        parent_mode=0o700,
        file_uid=service.pw_uid,
        file_gid=service.pw_gid,
        file_mode=0o600,
        maximum=MAX_INPUT_BYTES,
        label="oracle input",
    )
    _need(
        "sha256:" + hashlib.sha256(raw).hexdigest() == payload["input_sha256"],
        "oracle input hash differs",
    )
    _decode_canonical(raw, label="oracle input", maximum=MAX_INPUT_BYTES)
    return raw, identity


def _terminal_payload(
    request: Mapping[str, Any],
    *,
    evidence_digest: str,
    verdict: dict[str, Any] | None,
    failure_code: str,
    completed_at: datetime,
) -> dict[str, Any]:
    completed = verdict is not None
    payload: dict[str, Any] = {
        "schema_version": TERMINAL_SCHEMA,
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "status": "completed" if completed else "failed",
        "verdict_payload": verdict,
        "verdict_sha256": _digest(verdict) if completed else "sha256:" + "0" * 64,
        "sandbox_evidence_sha256": evidence_digest,
        "completed_at": completed_at.astimezone(timezone.utc).isoformat(),
        "failure_code": "" if completed else failure_code,
    }
    payload["terminal_digest"] = _digest(payload)
    _need(set(payload) == _TERMINAL_FIELDS, "oracle terminal fields differ")
    return payload


def _run_receipt(
    request: Mapping[str, Any],
    terminal: Mapping[str, Any],
    *,
    input_identity: os.stat_result,
    output_identity: os.stat_result | None,
    output_sha256: str,
    evidence_digest: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": RUN_RECEIPT_SCHEMA,
        "campaign_id": MISSION_ID,
        "request_id": request["request_id"],
        "request_digest": request["request_digest"],
        "manifest_digest": request["manifest_digest"],
        "evaluator_sha256": request["evaluator_sha256"],
        "policy_sha256": request["policy_sha256"],
        "input_sha256": request["input_sha256"],
        "input_source_identity": {
            "dev": input_identity.st_dev,
            "ino": input_identity.st_ino,
            "size": input_identity.st_size,
        },
        "output_identity": (
            None
            if output_identity is None
            else {
                "dev": output_identity.st_dev,
                "ino": output_identity.st_ino,
                "size": output_identity.st_size,
                "uid": output_identity.st_uid,
                "gid": output_identity.st_gid,
                "mode": f"{stat.S_IMODE(output_identity.st_mode):04o}",
            }
        ),
        "output_sha256": output_sha256,
        "sandbox_evidence_sha256": evidence_digest,
        "network_mode": "none",
        "filesystem_mode": "read_only_except_new_output",
        "terminal_payload": dict(terminal),
        "terminal_digest": terminal["terminal_digest"],
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _digest(receipt, omit="receipt_digest")
    return receipt


def _require_solo_unit_process(
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> None:
    """Prove no evaluator child or daemon survives before output admission."""
    try:
        lines = (proc_root / "self/cgroup").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise OracleSandboxError("oracle cgroup membership is unavailable") from exc
    unified = [line.split(":", 2)[2] for line in lines if line.startswith("0::")]
    _need(len(unified) == 1, "oracle worker requires one unified cgroup")
    relative = unified[0].lstrip("/")
    members_path = cgroup_root / relative / "cgroup.procs"
    try:
        members = {
            int(line)
            for line in members_path.read_text(encoding="ascii").splitlines()
            if line
        }
    except (OSError, ValueError) as exc:
        raise OracleSandboxError("oracle cgroup process proof is unavailable") from exc
    _need(members == {os.getpid()}, "oracle evaluator left a surviving child process")


def _publish_terminal_from_receipt(
    receipt: Mapping[str, Any], *, service: pwd.struct_passwd
) -> None:
    terminal = receipt.get("terminal_payload")
    _need(type(terminal) is dict, "oracle run receipt terminal is absent")
    raw = _canonical(terminal)
    _publish_noreplace(
        TERMINAL_ROOT / f"{receipt['request_id']}.terminal.json",
        raw,
        uid=service.pw_uid,
        gid=service.pw_gid,
        mode=0o600,
        existing_label="oracle launch terminal",
    )


def _run_one(
    payload: Mapping[str, Any],
    *,
    raw: bytes,
    evaluator: bytes,
    policy: bytes,
    evidence_digest: str,
    service: pwd.struct_passwd,
    oracle: pwd.struct_passwd,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    process_barrier: Callable[[], None] = _require_solo_unit_process,
    root_uid: int = 0,
    root_gid: int = 0,
) -> None:
    request_id = str(payload["request_id"])
    receipt_path = RECEIPT_ROOT / f"{request_id}.sandbox.json"
    if receipt_path.exists() and not receipt_path.is_symlink():
        receipt_raw, _ = _read_path(
            receipt_path,
            parent_uid=root_uid,
            parent_gid=root_gid,
            parent_mode=0o700,
            file_uid=root_uid,
            file_gid=root_gid,
            file_mode=0o400,
            maximum=MAX_PROTOCOL_BYTES,
            label="oracle run receipt",
        )
        receipt = _decode_canonical(receipt_raw, label="oracle run receipt", maximum=MAX_PROTOCOL_BYTES)
        _need(
            receipt.get("schema_version") == RUN_RECEIPT_SCHEMA
            and receipt.get("request_digest") == payload["request_digest"]
            and receipt.get("receipt_digest") == _digest(receipt, omit="receipt_digest"),
            "oracle run receipt replay binding differs",
        )
        _publish_terminal_from_receipt(receipt, service=service)
        return

    _publish_noreplace(
        CLAIM_ROOT / f"{request_id}.request.json",
        raw,
        uid=root_uid,
        gid=root_gid,
        mode=0o400,
        existing_label="oracle immutable request claim",
    )
    input_raw, input_identity = _read_input(payload, service)
    run = RUN_ROOT / f"{request_id}.run-{secrets.token_hex(16)}"
    os.mkdir(run, 0o750)
    os.chown(run, root_uid, oracle.pw_gid)
    os.chmod(run, 0o750)
    output = run / "output"
    os.mkdir(output, 0o700)
    os.chown(output, oracle.pw_uid, oracle.pw_gid)
    evaluator_copy = run / "g10-evaluator.py"
    policy_copy = run / "g10-policy.json"
    input_copy = run / "input.json"
    _copy_private(
        evaluator_copy, evaluator, uid=root_uid, gid=oracle.pw_gid, mode=0o440
    )
    _copy_private(
        policy_copy, policy, uid=root_uid, gid=oracle.pw_gid, mode=0o440
    )
    _copy_private(
        input_copy, input_raw, uid=root_uid, gid=oracle.pw_gid, mode=0o440
    )
    run_descriptor = os.open(run, _directory_flags())
    try:
        os.fsync(run_descriptor)
    finally:
        os.close(run_descriptor)
    verdict_path = output / "verdict.json"
    argv = (
        SETPRIV_PATH,
        f"--reuid={oracle.pw_uid}",
        f"--regid={oracle.pw_gid}",
        "--clear-groups",
        "--no-new-privs",
        "--bounding-set=-all",
        "--inh-caps=-all",
        "--ambient-caps=-all",
        "--",
        PYTHON_PATH,
        str(evaluator_copy),
        "--policy",
        str(policy_copy),
        "--input",
        str(input_copy),
        "--output",
        str(verdict_path),
    )
    failure_code = ""
    process_barrier()
    try:
        result = runner(
            argv,
            cwd=output,
            env={
                "HOME": "/nonexistent",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
            check=False,
        )
        if result.returncode != 0:
            failure_code = "evaluator_exit_nonzero"
    except subprocess.TimeoutExpired:
        failure_code = "evaluator_timeout"
    process_barrier()
    verdict: dict[str, Any] | None = None
    output_identity: os.stat_result | None = None
    output_sha256 = "sha256:" + "0" * 64
    if not failure_code:
        entries = sorted(path.name for path in output.iterdir())
        _need(entries == ["verdict.json"], "oracle output directory fields differ")
        verdict_raw, output_identity = _read_path(
            verdict_path,
            parent_uid=oracle.pw_uid,
            parent_gid=oracle.pw_gid,
            parent_mode=0o700,
            file_uid=oracle.pw_uid,
            file_gid=oracle.pw_gid,
            file_mode=0o600,
            maximum=MAX_ORACLE_BYTES,
            label="oracle verdict",
        )
        verdict = _decode_canonical(verdict_raw, label="oracle verdict", maximum=MAX_ORACLE_BYTES)
        output_sha256 = "sha256:" + hashlib.sha256(verdict_raw).hexdigest()
    completed = now()
    _need(completed.tzinfo is not None and completed < CAMPAIGN_STOP, "oracle completion clock differs")
    terminal = _terminal_payload(
        payload,
        evidence_digest=evidence_digest,
        verdict=verdict,
        failure_code=failure_code,
        completed_at=completed,
    )
    receipt = _run_receipt(
        payload,
        terminal,
        input_identity=input_identity,
        output_identity=output_identity,
        output_sha256=output_sha256,
        evidence_digest=evidence_digest,
    )
    _publish_noreplace(
        receipt_path,
        _canonical(receipt),
        uid=root_uid,
        gid=root_gid,
        mode=0o400,
        existing_label="oracle run receipt",
    )
    _publish_terminal_from_receipt(receipt, service=service)


def _accounts() -> tuple[pwd.struct_passwd, pwd.struct_passwd]:
    try:
        service = pwd.getpwnam(SERVICE_ACCOUNT)
        oracle = pwd.getpwnam(ORACLE_ACCOUNT)
    except KeyError as exc:
        raise OracleSandboxError("oracle static identity is absent") from exc
    _need(
        service.pw_uid > 0
        and service.pw_gid > 0
        and oracle.pw_uid > 0
        and oracle.pw_gid > 0
        and service.pw_uid != oracle.pw_uid
        and service.pw_gid != oracle.pw_gid
        and oracle.pw_shell == "/usr/sbin/nologin",
        "oracle static identity differs",
    )
    return service, oracle


def _guard_clock(now: datetime | None = None) -> datetime:
    observed = now or datetime.now(timezone.utc)
    _need(observed.tzinfo is not None, "oracle clock must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    _need(
        CAMPAIGN_START <= observed < CAMPAIGN_STOP,
        "oracle worker is outside the exact campaign timebox",
    )
    return observed


def _ensure_directory(path: Path, *, uid: int, gid: int, mode: int) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    details = path.lstat()
    _need(
        not path.is_symlink()
        and stat.S_ISDIR(details.st_mode)
        and details.st_uid == uid
        and details.st_gid == gid
        and stat.S_IMODE(details.st_mode) == mode,
        f"oracle runtime directory custody differs: {path.name}",
    )


def prepare() -> dict[str, Any]:
    """Recreate only the fixed volatile and persistent oracle custody roots."""
    _need(os.geteuid() == 0, "oracle runtime preparation requires root")
    service, oracle = _accounts()
    roots = (
        (Path("/run/dharma-sadhana"), 0, 0, 0o711),
        (Path("/run/dharma-sadhana/oracle"), 0, 0, 0o711),
        (REQUEST_ROOT, service.pw_uid, service.pw_gid, 0o700),
        (TERMINAL_ROOT, 0, service.pw_gid, 0o750),
        (INPUT_ROOT, service.pw_uid, service.pw_gid, 0o700),
        (CLAIM_ROOT, 0, 0, 0o700),
        (RUN_ROOT, 0, oracle.pw_gid, 0o710),
        (QUARANTINE_ROOT, 0, 0, 0o700),
        (RECEIPT_ROOT, 0, 0, 0o700),
    )
    for path, uid, gid, mode in roots:
        _ensure_directory(path, uid=uid, gid=gid, mode=mode)
    return {"status": "oracle_runtime_prepared"}


def reconcile(*, release_sha: str) -> dict[str, Any]:
    _need(os.geteuid() == 0, "oracle reconciliation requires root")
    _guard_clock()
    service, oracle = _accounts()
    evidence, manifest, evaluator, policy = _load_context(
        release_sha=release_sha,
        service=service,
    )
    evidence_digest = str(evidence["receipt_digest"])
    request_directory = _open_directory(
        REQUEST_ROOT,
        uid=service.pw_uid,
        gid=service.pw_gid,
        mode=0o700,
    )
    failures: list[str] = []
    processed = 0
    try:
        names = sorted(os.listdir(request_directory), key=os.fsencode)
        for name in names:
            if _REQUEST_NAME.fullmatch(name) is None:
                failures.append("foreign-request-entry")
                continue
            try:
                raw, _ = _read_at(
                    request_directory,
                    name,
                    uid=service.pw_uid,
                    gid=service.pw_gid,
                    mode=0o600,
                    maximum=MAX_PROTOCOL_BYTES,
                    label="oracle launch request",
                )
                payload = _decode_request(
                    raw,
                    filename=name,
                    evidence_digest=evidence_digest,
                    held_out_manifest=manifest,
                )
                _run_one(
                    payload,
                    raw=raw,
                    evaluator=evaluator,
                    policy=policy,
                    evidence_digest=evidence_digest,
                    service=service,
                    oracle=oracle,
                )
                processed += 1
            except (FileNotFoundError, InvalidOracleRequest) as exc:
                failures.append(type(exc).__name__)
                continue
    finally:
        os.close(request_directory)
    if failures:
        raise OracleSandboxError(
            f"oracle reconciliation completed with {len(failures)} rejected entries"
        )
    return {"status": "oracle_requests_reconciled", "processed": processed}


def _non_loopback_routes() -> int:
    count = 0
    for path in (Path("/proc/net/route"), Path("/proc/net/ipv6_route")):
        try:
            lines = path.read_text(encoding="ascii").splitlines()
        except OSError as exc:
            raise OracleSandboxError("oracle network route proof unavailable") from exc
        for line in lines[1:] if path.name == "route" else lines:
            fields = line.split()
            if not fields:
                continue
            interface = fields[0] if path.name == "route" else fields[-1]
            if interface != "lo":
                count += 1
    return count


def _assert_inaccessible(path: Path, label: str) -> bool:
    try:
        os.stat(path)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.ENOENT}:
            return True
        raise OracleSandboxError(f"{label} access proof failed") from exc
    raise OracleSandboxError(f"{label} remains visible in oracle namespace")


def probe(*, release_sha: str) -> dict[str, Any]:
    _need(os.geteuid() == 0, "oracle sandbox probe requires root")
    _guard_clock()
    service, oracle = _accounts()
    _need(_RAW_SHA.fullmatch(release_sha) is not None, "oracle probe release SHA differs")
    interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    _need(interfaces == ["lo"], "oracle sandbox has a non-loopback interface")
    routes = _non_loopback_routes()
    _need(routes == 0, "oracle sandbox has a non-loopback route")
    status = Path("/proc/self/status").read_text(encoding="ascii")
    no_new_privileges = any(
        line.split() == ["NoNewPrivs:", "1"] for line in status.splitlines()
    )
    _need(no_new_privileges, "oracle sandbox lacks no-new-privileges")
    unit_raw, _ = _read_path(
        WORKER_UNIT_PATH,
        parent_uid=0,
        parent_gid=0,
        parent_mode=0o755,
        file_uid=0,
        file_gid=0,
        file_mode=0o644,
        maximum=MAX_PROTOCOL_BYTES,
        label="installed oracle worker unit",
    )
    unit_text = unit_raw.decode("utf-8")
    _need(
        "PrivateNetwork=true" in unit_text
        and "ProtectSystem=strict" in unit_text
        and "NoNewPrivileges=true" in unit_text,
        "oracle worker unit sandbox differs",
    )
    canonical_inaccessible = _assert_inaccessible(
        Path("/var/lib/dharma-sadhana/state"), "canonical state"
    )
    credential_inaccessible = _assert_inaccessible(
        Path("/etc/dharma-sadhana/credentials"), "credential root"
    )
    probe_root = RUN_ROOT / ".probe-output"
    descriptor = os.open(
        probe_root,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        _write_all(descriptor, b"sandbox-probe\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    probe_root.unlink()
    run_descriptor = os.open(RUN_ROOT, _directory_flags())
    try:
        os.fsync(run_descriptor)
    finally:
        os.close(run_descriptor)
    receipt: dict[str, Any] = {
        "schema_version": SANDBOX_EVIDENCE_SCHEMA,
        "campaign_id": MISSION_ID,
        "release_sha": release_sha,
        "worker_unit_path": str(WORKER_UNIT_PATH),
        "worker_unit_sha256": hashlib.sha256(unit_raw).hexdigest(),
        "private_network": True,
        "network_interfaces": interfaces,
        "non_loopback_route_count": routes,
        "protect_system_strict": True,
        "no_new_privileges": True,
        "oracle_identity_separated": (
            oracle.pw_uid != service.pw_uid and oracle.pw_gid != service.pw_gid
        ),
        "canonical_state_inaccessible": canonical_inaccessible,
        "credential_root_inaccessible": credential_inaccessible,
        "probe_output_created_and_removed": True,
        "evaluator_executed": False,
        "verdict": "PASS",
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _digest(receipt, omit="receipt_digest")
    _publish_noreplace(
        SANDBOX_EVIDENCE_PATH,
        _canonical(receipt),
        uid=0,
        gid=0,
        mode=0o600,
        existing_label="oracle sandbox evidence",
    )
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    for name in ("probe", "reconcile"):
        child = commands.add_parser(name)
        child.add_argument("--release-sha", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        output = prepare()
    elif args.command == "probe":
        result = probe(release_sha=args.release_sha)
        output = {"status": "oracle_sandbox_proven", "receipt_digest": result["receipt_digest"]}
    else:
        output = reconcile(release_sha=args.release_sha)
    print(json.dumps(output, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OracleSandboxError as exc:
        print(f"oracle sandbox contract rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
