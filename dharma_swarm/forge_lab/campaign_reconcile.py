"""Fail-closed campaign reconciliation and read-only cleanup planning."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable, Mapping, Sequence
from dharma_swarm.forge_lab.campaign_contract import CampaignContractError, validate_manifest
from dharma_swarm.forge_lab.campaign_reconcile_db import inspect_control_db
REPORT_SCHEMA = "forge_lab.reconciliation_report.v1"
INTENT_SCHEMA = "forge_lab.reconciliation_apply_intent.v1"
RECEIPT_SCHEMA = "forge_lab.reconciliation_apply_receipt.v1"
CLEANUP_SCHEMA = "forge_lab.cleanup_plan.v1"
_CAMPAIGN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_CATEGORIES = ("control", "receipts", "events", "checkpoints")
_SELF_DIGESTS = ("receipt_digest", "event_digest", "checkpoint_digest", "content_digest", "report_digest", "plan_digest")
_IDENTITIES = ("artifact_id", "receipt_id", "event_id", "checkpoint_id")
class ReconciliationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()
def content_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()
def _bdigest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
def _state(value: str | Path) -> Path:
    if value is None or not str(value):
        raise ReconciliationError("STATE_ROOT_UNBOUND", "explicit state_root required")
    path = Path(value)
    if not path.is_absolute():
        raise ReconciliationError(
            "STATE_ROOT_NOT_ABSOLUTE", "canonical state_root must be absolute"
        )
    return path.resolve()
def _campaign(value: str | None) -> str | None:
    if value is not None and not _CAMPAIGN_RE.fullmatch(value):
        raise ReconciliationError("INVALID_CAMPAIGN_ID", "campaign_id is not path-safe")
    return value
def _relpath(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(
        part in ("", ".", "..") for part in path.parts
    ):
        raise ReconciliationError("INVALID_ARTIFACT_PATH", "unsafe relative path")
    return path
def _relative(path: Path, state: Path) -> str:
    try:
        return path.relative_to(state).as_posix()
    except ValueError as exc:
        raise ReconciliationError("PATH_OUTSIDE_STATE", str(path)) from exc
def _lab(state: Path) -> Path:
    return state / ".dharma" / "forge_lab"
def _category_root(state: Path, category: str, campaign_id: str | None) -> Path:
    if category in ("cas", "manifest_cas"):
        return _lab(state) / "manifests"
    if category not in _CATEGORIES:
        raise ReconciliationError("INVALID_ARTIFACT_CATEGORY", category)
    if campaign_id is None:
        raise ReconciliationError("CAMPAIGN_ID_REQUIRED", category)
    return _lab(state) / "campaigns" / campaign_id / category
def _expectations(
    state: Path, values: Iterable[Mapping[str, Any]] | None,
    default_campaign: str | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: dict[tuple[str, str | None, str], str | None] = {}
    for raw in values or ():
        category = str(raw.get("category", ""))
        campaign_id = _campaign(raw.get("campaign_id", default_campaign))
        path = _relpath(str(raw.get("path", ""))).as_posix()
        digest = raw.get("digest", raw.get("sha256"))
        if digest is not None and not _DIGEST_RE.fullmatch(str(digest)):
            raise ReconciliationError("INVALID_EXPECTED_DIGEST", str(digest))
        _category_root(state, category, campaign_id)
        key = category, campaign_id, path
        if key in seen and seen[key] != digest:
            raise ReconciliationError("CONFLICTING_EXPECTATION", path)
        seen[key] = digest
        result.append({
            "campaign_id": campaign_id, "category": category, "digest": digest,
            "path": path, "required": bool(raw.get("required", True)),
        })
    return sorted(
        result,
        key=lambda item: (item["category"], item["campaign_id"] or "", item["path"]),
    )
def _finding(
    code: str, category: str, path: Path, state: Path, **detail: Any,
) -> dict[str, Any]:
    return {
        "category": category, "code": code, "detail": detail or None,
        "path": _relative(path, state), "severity": "error",
    }
def _campaigns(state: Path, requested: str | None) -> list[str]:
    if requested:
        return [requested]
    try:
        entries = os.scandir(_lab(state) / "campaigns")
    except OSError:
        return []
    with entries:
        return sorted(
            item.name for item in entries
            if item.is_dir(follow_symlinks=False)
            and _CAMPAIGN_RE.fullmatch(item.name)
        )
def _json_status(
    data: bytes, category: str, path: Path, state: Path,
    findings: list[dict[str, Any]],
) -> tuple[str | None, list[tuple[str, str, str, str]]]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(_finding(
            "CORRUPT_JSON", category, path, state, error=type(exc).__name__
        ))
        return None, []
    if not isinstance(value, dict):
        findings.append(_finding("INVALID_JSON_SHAPE", category, path, state))
        return None, []
    for field in _SELF_DIGESTS:
        if field not in value:
            continue
        body, declared = dict(value), value[field]
        body.pop(field)
        if not _DIGEST_RE.fullmatch(str(declared)) or content_digest(body) != declared:
            findings.append(_finding(
                "SELF_DIGEST_MISMATCH", category, path, state, field=field
            ))
    schema, identities = value.get("schema"), []
    for field in _IDENTITIES:
        identity = value.get(field)
        if isinstance(identity, str) and identity:
            identities.append((str(schema), field, identity, _bdigest(data)))
    return str(schema) if isinstance(schema, str) else None, identities
def _walk(
    root: Path, category: str, state: Path, observations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    identities: dict[tuple[str, str, str, str], tuple[str, str]],
) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in list(directories):
            path = base / name
            if path.is_symlink():
                directories.remove(name)
                findings.append(_finding("UNSAFE_SYMLINK", category, path, state))
        for name in sorted(files):
            path = base / name
            if path.is_symlink() or not path.is_file():
                code = "UNSAFE_SYMLINK" if path.is_symlink() else "UNSAFE_SPECIAL_FILE"
                findings.append(_finding(code, category, path, state))
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                findings.append(_finding(
                    "UNREADABLE_ARTIFACT", category, path, state,
                    error=type(exc).__name__,
                ))
                continue
            digest, schema, ids = _bdigest(data), None, []
            if path.suffix == ".json":
                schema, ids = _json_status(data, category, path, state, findings)
            if category == "manifest_cas":
                try:
                    manifest = validate_manifest(json.loads(data))
                except (CampaignContractError, json.JSONDecodeError, TypeError) as exc:
                    findings.append(_finding(
                        "CORRUPT_MANIFEST", category, path, state,
                        error=getattr(exc, "code", type(exc).__name__),
                    ))
                else:
                    filename_digest = "sha256:" + path.stem
                    if not _HEX64_RE.fullmatch(path.stem):
                        filename_digest = None
                    if manifest["manifest_digest"] != filename_digest:
                        findings.append(_finding(
                            "CAS_DIGEST_MISMATCH", category, path, state,
                            declared_digest=manifest["manifest_digest"],
                        ))
            relative = _relative(path, state)
            observations.append({
                "category": category, "digest": digest, "path": relative,
                "schema": schema, "size": len(data),
            })
            for schema_name, field, identity, identity_digest in ids:
                key = category, schema_name, field, identity
                prior = identities.get(key)
                if prior and prior[0] != identity_digest:
                    findings.append(_finding(
                        "CONFLICTING_ARTIFACT_IDENTITY", category, path, state,
                        conflicting_path=prior[1], identity_field=field,
                        identity_value=identity,
                    ))
                else:
                    identities[key] = identity_digest, relative
def _scan_root(
    root: Path, category: str, state: Path, observations: list[dict[str, Any]],
    findings: list[dict[str, Any]], repairs: list[dict[str, Any]],
    identities: dict[tuple[str, str, str, str], tuple[str, str]],
) -> None:
    try:
        mode = root.lstat().st_mode
    except FileNotFoundError:
        findings.append(_finding("MISSING_ROOT", category, root, state))
        repairs.append({
            "category": category, "operation": "create_directory",
            "path": _relative(root, state),
        })
        return
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        code = "UNSAFE_SYMLINK" if stat.S_ISLNK(mode) else "ROOT_NOT_DIRECTORY"
        findings.append(_finding(code, category, root, state))
        return
    _walk(root, category, state, observations, findings, identities)
def _scan_db(
    state: Path, observations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    path = _lab(state) / "campaigns" / "control.sqlite3"
    if not path.exists():
        return
    if path.is_symlink() or not path.is_file():
        findings.append(_finding("UNSAFE_CONTROL_DB", "control_db", path, state))
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        findings.append(_finding(
            "UNREADABLE_CONTROL_DB", "control_db", path, state,
            error=type(exc).__name__,
        ))
        return
    if data and not data.startswith(b"SQLite format 3\x00"):
        findings.append(_finding("CORRUPT_CONTROL_DB", "control_db", path, state))
    else:
        findings.extend(_finding(issue["code"], "control_db", path, state,
            **(issue.get("detail") or {})) for issue in inspect_control_db(path))
    observations.append({"category": "control_db", "digest": _bdigest(data),
        "path": _relative(path, state), "schema": "sqlite3", "size": len(data)})
    for suffix in ("-wal", "-shm"):
        internal = Path(str(path) + suffix)
        if internal.exists():
            findings.append(_finding(
                "DB_UNCHECKED_SQLITE_SIDECAR", "control_db", internal, state,
                size=internal.stat().st_size,
            ))
def _dry(
    state: Path, campaign_id: str | None,
    expected_artifacts: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    expected = _expectations(state, expected_artifacts, campaign_id)
    observations: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    identities: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    lab, campaigns = _lab(state), _campaigns(state, campaign_id)
    roots = [("manifest_cas", lab / "manifests")]
    roots += [
        (category, lab / "campaigns" / current / category)
        for current in campaigns for category in _CATEGORIES
    ]
    if campaign_id is None and not (lab / "campaigns").exists():
        roots.append(("campaigns", lab / "campaigns"))
    for category, path in roots:
        _scan_root(
            path, category, state, observations, findings, repairs, identities
        )
    _scan_db(state, observations, findings)
    observed = {item["path"]: item["digest"] for item in observations}
    for item in expected:
        path = _category_root(
            state, item["category"], item["campaign_id"]
        ) / _relpath(item["path"])
        actual = observed.get(_relative(path, state))
        if actual is None and item["required"]:
            findings.append(_finding(
                "MISSING_ARTIFACT", item["category"], path, state,
                expected_digest=item["digest"],
            ))
        elif item["digest"] is not None and actual != item["digest"]:
            findings.append(_finding(
                "ARTIFACT_DIGEST_MISMATCH", item["category"], path, state,
                actual_digest=actual, expected_digest=item["digest"],
            ))
    observations.sort(key=lambda item: (item["category"], item["path"]))
    findings.sort(key=lambda item: (item["code"], item["path"]))
    repairs.sort(key=lambda item: (item["operation"], item["path"]))
    result: dict[str, Any] = {
        "schema": REPORT_SCHEMA, "campaign_id": campaign_id,
        "campaign_ids_observed": campaigns, "state_root": str(state),
        "expected_artifacts": expected, "observations": observations,
        "findings": findings, "repairs": repairs,
        "summary": {
            "artifact_count": len(observations),
            "finding_count": len(findings), "repair_count": len(repairs),
            "status": "clean" if not findings else "divergent",
        },
        "authority": {
            "apply_operations": ["create_directory"],
            "creates_provider_evidence": False,
            "creates_scientific_evidence": False,
            "scope": "operational_integrity_only",
        },
    }
    result["report_digest"] = content_digest(result)
    return result
def _validate_report(report: Mapping[str, Any], digest: str) -> dict[str, Any]:
    value, declared = dict(report), report.get("report_digest")
    value.pop("report_digest", None)
    if (
        value.get("schema") != REPORT_SCHEMA
        or not _DIGEST_RE.fullmatch(str(digest))
        or declared != digest or content_digest(value) != digest
    ):
        raise ReconciliationError("REPORT_DIGEST_MISMATCH", "exact report required")
    value["report_digest"] = declared
    return value
def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ReconciliationError("UNSAFE_STATE_PATH", str(path))
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReconciliationError("CORRUPT_OPERATION_RECORD", str(path)) from exc
    if not isinstance(value, dict):
        raise ReconciliationError("CORRUPT_OPERATION_RECORD", str(path))
    return value
def _mkdir(path: Path, state: Path) -> None:
    _relative(path, state)
    cursor = state
    for part in path.relative_to(state).parts:
        cursor /= part
        try:
            mode = cursor.lstat().st_mode
        except FileNotFoundError:
            cursor.mkdir()
            continue
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ReconciliationError("UNSAFE_REPAIR_TARGET", str(cursor))
def _write_once(path: Path, payload: Mapping[str, Any], state: Path) -> None:
    _mkdir(path.parent, state)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_json(payload))
        handle.flush()
        os.fsync(handle.fileno())
def _apply(
    state: Path, report: Mapping[str, Any], digest: str, request_id: str,
) -> dict[str, Any]:
    value = _validate_report(report, digest)
    if value.get("state_root") != str(state):
        raise ReconciliationError("REPORT_STATE_MISMATCH", "wrong canonical state")
    operations = value.get("repairs")
    if not isinstance(operations, list):
        raise ReconciliationError("UNSAFE_REPAIR", "repairs must be a list")
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or set(operation) != {"category", "operation", "path"}
            or operation.get("operation") != "create_directory"
        ):
            raise ReconciliationError("UNSAFE_REPAIR", "create_directory only")
        _relpath(str(operation["path"]))
    operation_digest = content_digest(operations)
    ledger = (
        _lab(state) / "reconciliation_requests"
        / str(value.get("campaign_id") or "_all") / request_id
    )
    intent_path, completion_path = ledger / "intent.json", ledger / "completion.json"
    intent = {
        "schema": INTENT_SCHEMA, "campaign_id": value.get("campaign_id"),
        "operation_digest": operation_digest, "report_digest": digest,
        "request_id": request_id, "provider_evidence_authority": False,
        "scientific_evidence_authority": False,
    }
    if intent_path.exists():
        if _read(intent_path) != intent:
            raise ReconciliationError("REQUEST_ID_CONFLICT", request_id)
        if completion_path.exists():
            return _read(completion_path)
    else:
        if not operations:
            raise ReconciliationError("NO_SAFE_REPAIRS", "report has no safe repairs")
        fresh = _dry(state, value.get("campaign_id"), value["expected_artifacts"])
        if fresh["report_digest"] != digest:
            raise ReconciliationError("STALE_RECONCILIATION_REPORT", digest)
        try:
            _write_once(intent_path, intent, state)
        except FileExistsError:
            if _read(intent_path) != intent:
                raise ReconciliationError("REQUEST_ID_CONFLICT", request_id)
    for operation in operations:
        _mkdir(state / _relpath(operation["path"]), state)
    resulting = _dry(state, value.get("campaign_id"), value["expected_artifacts"])
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA, "campaign_id": value.get("campaign_id"),
        "operation_digest": operation_digest, "operations_applied": operations,
        "provider_evidence_created": False, "report_digest": digest,
        "request_id": request_id,
        "resulting_report_digest": resulting["report_digest"],
        "scientific_evidence_created": False, "status": "applied",
    }
    receipt["receipt_digest"] = content_digest(receipt)
    try:
        _write_once(completion_path, receipt, state)
    except FileExistsError:
        existing = _read(completion_path)
        if existing != receipt:
            raise ReconciliationError("REQUEST_ID_CONFLICT", "completion")
        return existing
    return receipt
def reconcile_state(
    state_root: str | Path, *, apply: bool = False,
    report: Mapping[str, Any] | None = None, report_digest: str | None = None,
    request_id: str | None = None, campaign_id: str | None = None,
    expected_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    state, campaign_id = _state(state_root), _campaign(campaign_id)
    if not apply:
        if report is not None or report_digest is not None or request_id is not None:
            raise ReconciliationError(
                "INVALID_DRY_RUN_ARGUMENT", "apply-only argument in dry-run"
            )
        return _dry(state, campaign_id, expected_artifacts)
    if report is None or report_digest is None:
        raise ReconciliationError("REPORT_REQUIRED", "report and digest required")
    if request_id is None or not _REQUEST_RE.fullmatch(request_id):
        raise ReconciliationError("INVALID_REQUEST_ID", "unsafe request_id")
    if campaign_id is not None and report.get("campaign_id") != campaign_id:
        raise ReconciliationError("REPORT_CAMPAIGN_MISMATCH", campaign_id)
    return _apply(state, report, report_digest, request_id)
def _snapshot(path: Path, state: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    observations: list[dict[str, Any]] = []
    if path.is_dir() and not path.is_symlink():
        _walk(path, "cleanup_residual", state, observations, [], {})
    elif path.is_file() and not path.is_symlink():
        data = path.read_bytes()
        observations.append({
            "category": "cleanup_residual", "digest": _bdigest(data),
            "path": _relative(path, state), "schema": None, "size": len(data),
        })
    return sorted(observations, key=lambda item: item["path"])
def plan_cleanup(
    state_root: str | Path, campaign_id: str, *, lifecycle_state: str,
    scratch_path: str | Path | None = None,
    residual_paths: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    state, campaign_id = _state(state_root), _campaign(campaign_id)
    assert campaign_id is not None
    paths: list[Path] = []
    if scratch_path is None:
        scratch = {"action": "none", "path": None, "state": "not_created"}
    else:
        scratch_candidate = Path(scratch_path)
        if not scratch_candidate.is_absolute():
            raise ReconciliationError("SCRATCH_PATH_NOT_ABSOLUTE", str(scratch_path))
        scratch_candidate = scratch_candidate.resolve()
        paths.append(scratch_candidate)
        scratch = {
            "action": "none", "path": _relative(scratch_candidate, state),
            "state": "present" if scratch_candidate.exists() else "missing",
        }
    for raw in residual_paths or ():
        candidate = Path(raw)
        if not candidate.is_absolute():
            raise ReconciliationError("RESIDUAL_PATH_NOT_ABSOLUTE", str(raw))
        candidate = candidate.resolve()
        _relative(candidate, state)
        if candidate not in paths:
            paths.append(candidate)
    residuals = [{
        "path": _relative(path, state), "present": path.exists(),
        "snapshot": _snapshot(path, state),
    } for path in sorted(paths)]
    result: dict[str, Any] = {
        "schema": CLEANUP_SCHEMA, "campaign_id": campaign_id,
        "lifecycle_state": lifecycle_state, "state_root": str(state),
        "scratch": scratch, "residuals_before_action": residuals,
        "actions": [], "deletion_authorized": False,
        "deletion_performed": False, "status": "recorded_no_action",
    }
    result["plan_digest"] = content_digest(result)
    return result
