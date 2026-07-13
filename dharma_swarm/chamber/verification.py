"""Fresh-process verifier for the frozen Hyperbolic Chamber V0 bundle."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar, cast

from dharma_swarm.chamber.replay import (
    read_bundle,
    run_bundle_once,
    validate_manifest,
)
from dharma_swarm.chamber.replay_contract import (
    FRESH_REPLAY_SCHEMA,
    REPLAY_EXECUTED_SOURCE_PATHS,
    SINGLE_REPLAY_SCHEMA,
    ReplayValidationError,
)
from dharma_swarm.chamber.traces import canonical_json, stable_digest

_VERIFIER_SEAL = object()
_T = TypeVar("_T")


def _freeze_json(value: _T) -> _T:
    if isinstance(value, Mapping):
        return cast(
            _T,
            MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()}),
        )
    if isinstance(value, (list, tuple)):
        return cast(_T, tuple(_freeze_json(item) for item in value))
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, eq=False)
class _VerificationWitness:
    seal: object
    receipt_digest: str
    bundle_digest: str
    scope_digest: str
    source_revision: str

    def __reduce__(self) -> Any:
        raise TypeError("runtime verification witness is not serializable")


@dataclass(frozen=True, slots=True)
class FreshProcessVerification:
    bundle_id: str
    scenario_candidate_id: str
    control_candidate_id: str
    bundle_digest: str
    source_revision: str
    scope_digest: str
    replays_requested: int
    replays_completed: int
    replay_pids: tuple[int, ...]
    semantic_digest: str
    property_verdicts: Mapping[str, bool]
    control_property_verdicts: Mapping[str, bool]
    control_valid: bool
    replay_payload: Mapping[str, Any]
    process_environment_contract: Mapping[str, Any]
    command: tuple[str, ...]
    process_records: tuple[Mapping[str, Any], ...]
    python_executable: str
    python_version: str
    schema: str = FRESH_REPLAY_SCHEMA
    _witness: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "property_verdicts", _freeze_json(self.property_verdicts))
        object.__setattr__(
            self,
            "control_property_verdicts",
            _freeze_json(self.control_property_verdicts),
        )
        object.__setattr__(
            self,
            "process_records",
            tuple(_freeze_json(record) for record in self.process_records),
        )
        object.__setattr__(self, "replay_payload", _freeze_json(self.replay_payload))
        object.__setattr__(
            self,
            "process_environment_contract",
            _freeze_json(self.process_environment_contract),
        )

    @property
    def verified(self) -> bool:
        if not (
            self.replays_requested > 0
            and self.replays_completed == self.replays_requested
            and self.control_valid
            and len(self.replay_pids) == self.replays_completed
            and len(set(self.replay_pids)) == self.replays_completed
            and len(self.process_records) == self.replays_completed
        ):
            return False
        replay_digest = stable_digest(_thaw_json(self.replay_payload))
        environment = _thaw_json(self.process_environment_contract)
        return all(
            record.get("replay_index") == index
            and record.get("exit_code") == 0
            and record.get("completed_monotonic_ns", 0)
            >= record.get("started_monotonic_ns", 1)
            and record.get("replay_payload_digest") == replay_digest
            and record.get("process_environment_digest")
            == stable_digest({**environment, "home": record.get("home")})
            for index, record in enumerate(self.process_records, start=1)
        )

    def to_dict(self) -> dict[str, Any]:
        semantic = {
            "bundle_id": self.bundle_id,
            "scenario_candidate_id": self.scenario_candidate_id,
            "control_candidate_id": self.control_candidate_id,
            "bundle_digest": self.bundle_digest,
            "source_revision": self.source_revision,
            "scope_digest": self.scope_digest,
            "replays_requested": self.replays_requested,
            "replays_completed": self.replays_completed,
            "semantic_digest": self.semantic_digest,
            "property_verdicts": dict(self.property_verdicts),
            "control_property_verdicts": dict(self.control_property_verdicts),
            "control_valid": self.control_valid,
            "verified": self.verified,
            "python_executable": self.python_executable,
            "python_version": self.python_version,
        }
        transcript = [_thaw_json(record) for record in self.process_records]
        body = {
            "schema": self.schema,
            **semantic,
            "fresh_processes": True,
            "replay_pids": list(self.replay_pids),
            "command": list(self.command),
            "process_records": transcript,
            "replay_payload": _thaw_json(self.replay_payload),
            "process_environment_contract": _thaw_json(
                self.process_environment_contract
            ),
            "semantic_receipt_digest": stable_digest(semantic),
            "transcript_digest": stable_digest(transcript),
        }
        return {**body, "receipt_digest": stable_digest(body)}


def verification_is_attested(verification: FreshProcessVerification) -> bool:
    witness = verification._witness
    receipt = verification.to_dict()
    return (
        isinstance(witness, _VerificationWitness)
        and witness.seal is _VERIFIER_SEAL
        and witness.receipt_digest == receipt["receipt_digest"]
        and witness.bundle_digest == verification.bundle_digest
        and witness.scope_digest == verification.scope_digest
        and witness.source_revision == verification.source_revision
    )


def _fresh_environment(repo_root: Path, home: Path) -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        if key in os.environ
    }
    env.update(
        {
            "HOME": str(home),
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(repo_root.resolve()),
        }
    )
    return env


def _environment_contract(
    repo_root: Path,
    manifest: Mapping[str, str],
) -> dict[str, Any]:
    git_executable = shutil.which("git") or ""
    git_sha256 = (
        hashlib.sha256(Path(git_executable).read_bytes()).hexdigest()
        if git_executable
        else ""
    )
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "python_hash_seed": "0",
        "pythonpath": str(repo_root.resolve()),
        "path": os.environ.get("PATH", ""),
        "git_executable": git_executable,
        "git_sha256": git_sha256,
        "isolated_worker": True,
        "loaded_project_sources": sorted(REPLAY_EXECUTED_SOURCE_PATHS),
        "loaded_project_source_digests": {
            path: manifest[path] for path in REPLAY_EXECUTED_SOURCE_PATHS
        },
    }


def _expected_environment(
    repo_root: Path,
    home: Path,
    manifest: Mapping[str, str],
) -> dict[str, Any]:
    return {**_environment_contract(repo_root, manifest), "home": str(home)}


def verify_in_fresh_processes(
    bundle_path: Path,
    *,
    repo_root: Path,
    replays: int = 100,
    timeout_per_process: float = 15.0,
) -> FreshProcessVerification:
    if type(replays) is not int or replays < 1:
        raise ReplayValidationError("fresh-process replay count must be positive")
    bundle = read_bundle(bundle_path)
    validate_manifest(bundle, repo_root)
    bundle_payload = bundle.to_dict()
    bundle_text = canonical_json(bundle_payload)
    expected = run_bundle_once(bundle, repo_root)
    bundle_digest = str(bundle_payload["bundle_digest"])
    command = [
        sys.executable,
        str(repo_root.resolve() / "dharma_swarm/chamber/replay_worker.py"),
        "run-once-stdin",
        "--repo-root",
        str(repo_root.resolve()),
    ]
    payloads: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    stable_keys = (
        "bundle_id",
        "scenario_candidate_id",
        "control_candidate_id",
        "bundle_digest",
        "source_revision",
        "scope_digest",
        "semantic_digest",
        "scenario_semantic_digest",
        "control_semantic_digest",
        "property_verdicts",
        "control_property_verdicts",
        "control_valid",
    )
    for index in range(1, replays + 1):
        started = time.monotonic_ns()
        try:
            with tempfile.TemporaryDirectory(prefix="dharma-chamber-home-") as raw_home:
                home = Path(raw_home)
                proc = subprocess.run(
                    command,
                    input=bundle_text,
                    cwd=repo_root,
                    env=_fresh_environment(repo_root, home),
                    capture_output=True,
                    text=True,
                    timeout=timeout_per_process,
                    check=False,
                )
                expected_environment = _expected_environment(
                    repo_root,
                    home,
                    {entry.path: entry.sha256 for entry in bundle.manifest},
                )
        except subprocess.TimeoutExpired as exc:
            raise ReplayValidationError(f"fresh replay {index} timed out") from exc
        completed = time.monotonic_ns()
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()[:500]
            raise ReplayValidationError(
                f"fresh replay {index} exited {proc.returncode}: {detail}"
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ReplayValidationError(
                f"fresh replay {index} emitted non-JSON output"
            ) from exc
        if not isinstance(payload, dict) or payload.get("schema") != SINGLE_REPLAY_SCHEMA:
            raise ReplayValidationError(f"fresh replay {index} emitted wrong schema")
        for key in stable_keys:
            if payload.get(key) != expected.get(key):
                raise ReplayValidationError(
                    f"fresh replay {index} differs from parent snapshot on {key}"
                )
        process_environment = payload.get("process_environment")
        if process_environment != expected_environment:
            raise ReplayValidationError(f"fresh replay {index} environment differs")
        process_pid = payload.get("pid")
        if type(process_pid) is not int or process_pid < 1:
            raise ReplayValidationError(f"fresh replay {index} emitted invalid pid")
        payloads.append(payload)
        records.append(
            {
                "replay_index": index,
                "pid": process_pid,
                "exit_code": proc.returncode,
                "started_monotonic_ns": started,
                "completed_monotonic_ns": completed,
                "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
                "semantic_digest": str(payload["semantic_digest"]),
                "replay_payload_digest": stable_digest(
                    {key: payload[key] for key in stable_keys}
                ),
                "process_environment_digest": stable_digest(process_environment),
                "home": str(process_environment["home"]),
            }
        )

    manifest = {entry.path: entry.sha256 for entry in bundle.manifest}
    report = FreshProcessVerification(
        bundle_id=bundle.bundle_id,
        scenario_candidate_id=bundle.scenario_candidate_id,
        control_candidate_id=bundle.control_candidate_id,
        bundle_digest=bundle_digest,
        source_revision=bundle.source_revision,
        scope_digest=bundle.scope_digest,
        replays_requested=replays,
        replays_completed=len(payloads),
        replay_pids=tuple(int(payload["pid"]) for payload in payloads),
        semantic_digest=str(expected["semantic_digest"]),
        property_verdicts=dict(expected["property_verdicts"]),
        control_property_verdicts=dict(expected["control_property_verdicts"]),
        control_valid=bool(expected["control_valid"]),
        replay_payload={key: expected[key] for key in stable_keys},
        process_environment_contract=_environment_contract(repo_root, manifest),
        command=tuple(command),
        process_records=tuple(records),
        python_executable=sys.executable,
        python_version=sys.version.split()[0],
    )
    receipt_digest = str(report.to_dict()["receipt_digest"])
    witness = _VerificationWitness(
        _VERIFIER_SEAL,
        receipt_digest,
        bundle_digest,
        bundle.scope_digest,
        bundle.source_revision,
    )
    return replace(report, _witness=witness)


__all__ = [
    "FreshProcessVerification",
    "verification_is_attested",
    "verify_in_fresh_processes",
]
