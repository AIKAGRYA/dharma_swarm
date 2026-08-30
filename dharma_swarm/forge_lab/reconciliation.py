"""Fenced, receipt-backed repair for a stale active-campaign projection.
Only ``ACTIVE_CAMPAIGN_MISSING_RUN`` is actionable. Planning never writes; apply
binds an exact digest, takes both Forge control locks, and atomically
moves the original projection into history before writing an immutable receipt.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from dharma_swarm.forge_lab.reconciliation_fs import (
    ReconciliationError,
    fsync_directory as _fsync,
    lock as _lock,
    mkdir as _mkdir,
    present as _present,
    read_json as _read,
    root as _root,
    unambiguous as _unambiguous,
)
from dharma_swarm.forge_lab.source_guard import CANONICAL_REPOSITORY, execution_source_status
from dharma_swarm.forge_lab.state_io import content_digest, now_utc, validate_digest, validate_safe_id, write_json_exclusive

FINDING = "ACTIVE_CAMPAIGN_MISSING_RUN"
ACTION = "QUARANTINE_STALE_ACTIVE_CAMPAIGN"
STATUS_SCHEMA = "rsi_lab.reconciliation_status.v1"
PLAN_SCHEMA = "rsi_lab.reconciliation_plan.v1"
RECEIPT_SCHEMA = "rsi_lab.reconciliation_action_receipt.v1"

_TERMINAL = {"COMPLETED", "FAILED", "PAUSED"}
_REQUEST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PROCESS_RE = re.compile(
    r"dharma_swarm\.forge_lab(?:\.rsi_cli)?\s+campaign\s+run\b|"
    r"(?:^|\s)(?:\S*/)?(?:rsi|rsilab)\s+campaign\s+run\b|"
    r"(?:^|\s)(?:\S*/)?rsi-unattended-explore(?:\s|$)|"
    r"rsi-manager-|rsi-overnight|forge_lab_v1_run", re.I,
)
_SOURCE_FIELDS = ("repo", "expected_repo", "commit", "remote", "canonical_repository",
                  "release_manifest_present", "release_manifest_commit")
SourceStatusProvider = Callable[[], Mapping[str, Any]]
ProcessProbe = Callable[[Mapping[str, Any]], bool]

@dataclass(frozen=True)
class _Projection:
    root_identity: dict[str, Any]
    marker: dict[str, Any]
    file_identity: dict[str, Any]
    campaign_id: str
    state: str
    marker_digest: str
    run_present: bool

def _projection(root: Path, root_identity: dict[str, Any]) -> _Projection | None:
    active = root / "active_campaign.json"
    if not _present(active):
        return None
    marker, file_identity = _read(root, active)
    state_value = marker.get("state")
    if not isinstance(state_value, str) or not state_value.strip():
        raise ReconciliationError("PROJECTION_INVALID", "active projection has no state")
    state = state_value.strip()
    if state in _TERMINAL:
        return None
    campaign_id = str(marker.get("campaign_id") or "")
    try:
        validate_safe_id(campaign_id, field="campaign_id")
    except ValueError as exc:
        raise ReconciliationError("PROJECTION_INVALID", str(exc)) from exc
    run = root / "campaigns" / "runs" / campaign_id
    _unambiguous(root, run)
    run_present = _present(run)
    if run_present and not (run.is_dir() and not run.is_symlink()):
        raise ReconciliationError("AMBIGUOUS_PATH", f"campaign run path is unsafe: {run}")
    return _Projection(root_identity, marker, file_identity, campaign_id, state,
                       content_digest(marker), run_present)

def reconciliation_status(*, forge_root: Path | None = None) -> dict[str, Any]:
    """Return the target finding without creating any filesystem object."""
    findings: list[dict[str, Any]] = []
    try:
        root, identity = _root(forge_root)
        projection = _projection(root, identity)
        if projection is not None and not projection.run_present:
            findings.append({"code": FINDING, "campaign": projection.campaign_id})
    except ReconciliationError as exc:
        findings.append({"code": exc.code, "detail": str(exc)})
    return {"schema": STATUS_SCHEMA, "ok": not findings, "read_only": True, "findings": findings}

def _finding(code: str, campaign_id: str | None) -> str | None:
    if code != FINDING:
        raise ReconciliationError("UNKNOWN_FINDING", f"finding is not actionable: {code!r}")
    if campaign_id is None:
        return None
    try:
        return validate_safe_id(campaign_id, field="campaign_id")
    except ValueError as exc:
        raise ReconciliationError("INVALID_CAMPAIGN_ID", str(exc)) from exc

def _source(provider: SourceStatusProvider | None) -> dict[str, Any]:
    try:
        status = dict((provider or execution_source_status)())
    except Exception as exc:
        raise ReconciliationError("SOURCE_UNAVAILABLE", "immutable source probe failed") from exc
    if status.get("ready") is not True:
        reasons = ",".join(map(str, status.get("reasons") or []))
        raise ReconciliationError("UNSAFE_SOURCE", reasons or "immutable source is not ready")
    identity = {field: status.get(field) for field in _SOURCE_FIELDS}
    commit, repo = str(identity["commit"] or ""), str(identity["repo"] or "")
    if (
        not _SHA_RE.fullmatch(commit) or not repo or repo != identity["expected_repo"]
        or identity["remote"] != CANONICAL_REPOSITORY
        or identity["canonical_repository"] != CANONICAL_REPOSITORY
        or identity["release_manifest_present"] is not True
        or identity["release_manifest_commit"] != commit
    ):
        raise ReconciliationError("UNSAFE_SOURCE", "immutable source identity is incomplete")
    return identity

def _default_probe(marker: Mapping[str, Any]) -> bool:
    for field in ("pid", "process_id", "controller_pid"):
        try:
            pid = int(marker.get(field) or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid > 1 and pid != os.getpid():
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError:
                return True
            else:
                return True
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,args="], capture_output=True, check=False, text=True,
            timeout=10, env={"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReconciliationError("PROCESS_PROBE_UNAVAILABLE", "process probe failed") from exc
    if result.returncode:
        raise ReconciliationError("PROCESS_PROBE_UNAVAILABLE", "process probe returned nonzero")
    return any(_PROCESS_RE.search(line) for line in result.stdout.splitlines())

def _quiescent(marker: Mapping[str, Any], probe: ProcessProbe | None) -> None:
    try:
        active = (probe or _default_probe)(marker)
    except ReconciliationError:
        raise
    except Exception as exc:
        raise ReconciliationError("PROCESS_PROBE_UNAVAILABLE", "process probe failed") from exc
    if active:
        raise ReconciliationError("ACTIVE_PROCESS_PRESENT", "an RSI campaign process is active")

def _admission(root: Path, projection: _Projection | None, campaign_id: str | None,
               probe: ProcessProbe | None) -> _Projection:
    if _present(root / "HALT"):
        raise ReconciliationError("HALT_PRESENT", f"operator HALT is present: {root / 'HALT'}")
    if projection is None:
        raise ReconciliationError("FINDING_NOT_PRESENT", "no nonterminal active projection exists")
    if campaign_id is not None and projection.campaign_id != campaign_id:
        raise ReconciliationError("FINDING_MISMATCH", "active campaign differs from requested finding")
    if projection.run_present:
        run = root / "campaigns" / "runs" / projection.campaign_id
        raise ReconciliationError("ACTIVE_RUN_PRESENT", f"campaign run exists: {run}")
    _quiescent(projection.marker, probe)
    return projection

def _history(projection: _Projection) -> Path:
    name = f"{projection.campaign_id}__{projection.marker_digest.removeprefix('sha256:')}.json"
    return Path("reconciliation/quarantine/active_campaign") / name

def _plan(projection: _Projection, source: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": PLAN_SCHEMA, "read_only": True, "action": ACTION,
        "finding": {"code": FINDING, "campaign": projection.campaign_id},
        "source_identity": source,
        "state_identity": {
            **projection.root_identity,
            "active_projection": {
                "relative_path": "active_campaign.json", "state": projection.state,
                "content_digest": projection.marker_digest, **projection.file_identity,
            },
        },
        "preconditions": {
            "halt_absent": True, "active_process_absent": True,
            "campaign_run_absent": True,
        },
        "mutation": {
            "kind": "atomic_quarantine_projection", "source": "active_campaign.json",
            "destination": _history(projection).as_posix(), "deletes_history": False,
        },
    }
    return {**body, "plan_digest": content_digest(body)}

def validate_reconciliation_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(plan)
    finding, mutation = payload.get("finding"), payload.get("mutation")
    if payload.get("schema") != PLAN_SCHEMA or payload.get("action") != ACTION:
        raise ReconciliationError("INVALID_PLAN", "unsupported reconciliation plan")
    if not isinstance(finding, dict) or finding.get("code") != FINDING:
        raise ReconciliationError("INVALID_PLAN", "plan finding is not actionable")
    claimed = str(payload.get("plan_digest") or "")
    try:
        validate_digest(claimed)
    except ValueError as exc:
        raise ReconciliationError("INVALID_PLAN_DIGEST", str(exc)) from exc
    unsigned = {key: value for key, value in payload.items() if key != "plan_digest"}
    if content_digest(unsigned) != claimed:
        raise ReconciliationError("PLAN_TAMPERED", "plan content does not match its digest")
    if not isinstance(mutation, dict) or mutation.get("kind") != "atomic_quarantine_projection":
        raise ReconciliationError("INVALID_PLAN", "plan mutation is not the bounded repair")
    return payload

def _current(code: str, campaign_id: str | None, forge_root: Path | None,
             source_status: SourceStatusProvider | None,
             process_probe: ProcessProbe | None) -> dict[str, Any]:
    requested = _finding(code, campaign_id)
    root, identity = _root(forge_root)
    source = _source(source_status)
    projection = _admission(root, _projection(root, identity), requested, process_probe)
    return _plan(projection, source)

def plan_reconciliation(*, finding_code: str = FINDING, campaign_id: str | None = None,
                        forge_root: Path | None = None,
                        source_status: SourceStatusProvider | None = None,
                        process_probe: ProcessProbe | None = None) -> dict[str, Any]:
    """Produce a deterministic read-only plan for one exact stale marker."""
    return _current(finding_code, campaign_id, forge_root, source_status, process_probe)

def _states(digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return ({"active_campaign": digest, "quarantine": None}, {"active_campaign": None, "quarantine": digest})

def _receipt(plan: Mapping[str, Any], request_id: str, recovered: bool) -> dict[str, Any]:
    digest = str(plan["state_identity"]["active_projection"]["content_digest"])
    before, after = _states(digest)
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA, "action": ACTION, "applied_at": now_utc(),
        "request_id": request_id, "plan_digest": plan["plan_digest"],
        "finding": plan["finding"], "source_identity": plan["source_identity"],
        "forge_root": plan["state_identity"]["path"],
        "projection_source": plan["mutation"]["source"],
        "quarantine_path": plan["mutation"]["destination"],
        "before": before, "before_digest": content_digest(before),
        "after": after, "after_digest": content_digest(after),
        "history_preserved": True, "recovered_after_interruption": recovered,
    }
    return {**body, "receipt_digest": content_digest(body)}

def _receipt_path(root: Path, request_id: str) -> Path:
    return root / "reconciliation" / "receipts" / f"{request_id}.json"

def _replay(root: Path, path: Path, request_id: str, digest: str) -> dict[str, Any]:
    receipt, _ = _read(root, path)
    if receipt.get("request_id") != request_id:
        raise ReconciliationError("RECEIPT_INVALID", "receipt request identity mismatch")
    if receipt.get("plan_digest") != digest:
        raise ReconciliationError("REQUEST_ID_REUSED", "request id is bound to another plan")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    if (receipt.get("schema"), receipt.get("action"), receipt.get("receipt_digest")) != (
        RECEIPT_SCHEMA, ACTION, content_digest(unsigned),
    ):
        raise ReconciliationError("RECEIPT_INVALID", "action receipt is invalid")
    if _present(root / "active_campaign.json"):
        raise ReconciliationError("REPLAY_STATE_DRIFT", "active projection reappeared")
    marker_digest = str((receipt.get("after") or {}).get("quarantine") or "")
    campaign = str((receipt.get("finding") or {}).get("campaign") or "")
    history = Path("reconciliation/quarantine/active_campaign") / (
        f"{campaign}__{marker_digest.removeprefix('sha256:')}.json"
    )
    if receipt.get("quarantine_path") != history.as_posix():
        raise ReconciliationError("RECEIPT_INVALID", "quarantine identity mismatch")
    marker, _ = _read(root, root / history)
    before, after = _states(content_digest(marker))
    if (receipt.get("before"), receipt.get("after"), receipt.get("before_digest"),
        receipt.get("after_digest")) != (before, after, content_digest(before), content_digest(after)):
        raise ReconciliationError("RECEIPT_INVALID", "state digests do not verify")
    return receipt

def _recover(root: Path, identity: dict[str, Any], source: dict[str, Any], digest: str,
             campaign_id: str | None, probe: ProcessProbe | None) -> dict[str, Any] | None:
    history_root = root / "reconciliation" / "quarantine" / "active_campaign"
    if not _present(history_root):
        return None
    _unambiguous(root, history_root)
    if not history_root.is_dir():
        raise ReconciliationError("AMBIGUOUS_PATH", f"unsafe history root: {history_root}")
    matches: list[dict[str, Any]] = []
    for path in sorted(history_root.glob("*.json")):
        marker, file_identity = _read(root, path)
        campaign, state = str(marker.get("campaign_id") or ""), str(marker.get("state") or "")
        if campaign_id is not None and campaign != campaign_id:
            continue
        try:
            validate_safe_id(campaign, field="campaign_id")
        except ValueError as exc:
            raise ReconciliationError("HISTORY_INVALID", str(exc)) from exc
        run = root / "campaigns" / "runs" / campaign
        _unambiguous(root, run)
        if _present(run):
            continue
        projection = _Projection(
            identity, marker, file_identity, campaign, state, content_digest(marker), False,
        )
        plan = _plan(projection, source)
        if plan["plan_digest"] == digest and root / _history(projection) == path:
            _quiescent(marker, probe)
            matches.append(plan)
    if len(matches) > 1:
        raise ReconciliationError("AMBIGUOUS_HISTORY", "multiple histories match the plan")
    return matches[0] if matches else None

def _result(receipt: dict[str, Any], path: Path, idempotent: bool) -> dict[str, Any]:
    return {
        "ok": True, "idempotent": idempotent, "request_id": receipt["request_id"],
        "plan_digest": receipt["plan_digest"], "campaign_id": receipt["finding"]["campaign"],
        "quarantine_path": receipt["quarantine_path"], "receipt_path": str(path),
        "receipt": receipt,
    }

def _outcome_unknown(history: Path, receipt_path: Path) -> ReconciliationError:
    return ReconciliationError(
        "APPLY_OUTCOME_UNKNOWN",
        "the projection may already be quarantined, but durable completion could not "
        f"be confirmed; inspect {history} and {receipt_path}, then retry with the "
        "same plan digest and request id; do not start a new reconciliation request",
    )

def _prepare_directory(root: Path, relative: Path, *, receipt: bool) -> Path:
    try:
        return _mkdir(root, relative)
    except Exception:
        label = "receipt" if receipt else "quarantine"
        raise ReconciliationError(
            "RECEIPT_PREPARE_FAILED" if receipt else "APPLY_PREPARE_FAILED",
            f"could not prepare the {label} directory before mutation; "
            "no projection was moved",
        ) from None

def _prepare_recovery_receipt_directory(
    root: Path, history: Path, receipt_path: Path,
) -> Path:
    try:
        return _mkdir(root, Path("reconciliation/receipts"))
    except Exception:
        raise _outcome_unknown(history, receipt_path) from None

def _sync_mutation(paths: tuple[Path, ...], history: Path, receipt_path: Path) -> None:
    try:
        for path in paths:
            _fsync(path)
    except Exception:
        raise _outcome_unknown(history, receipt_path) from None

def _persist_receipt(
    receipt_path: Path,
    receipt_dir: Path,
    receipt: dict[str, Any],
    history: Path,
) -> None:
    try:
        write_json_exclusive(receipt_path, receipt)
        _fsync(receipt_dir)
    except Exception:
        raise _outcome_unknown(history, receipt_path) from None

def apply_reconciliation(*, plan_digest: str, request_id: str,
                         finding_code: str = FINDING, campaign_id: str | None = None,
                         forge_root: Path | None = None,
                         source_status: SourceStatusProvider | None = None,
                         process_probe: ProcessProbe | None = None) -> dict[str, Any]:
    """Apply one exact quarantine plan, or replay its immutable receipt."""
    requested = _finding(finding_code, campaign_id)
    if not _REQUEST_RE.fullmatch(str(request_id or "")):
        raise ReconciliationError("INVALID_REQUEST_ID", "request id must be 3-96 safe characters")
    try:
        digest = validate_digest(plan_digest)
    except ValueError as exc:
        raise ReconciliationError("INVALID_PLAN_DIGEST", str(exc)) from exc
    root, identity = _root(forge_root)
    receipt_path = _receipt_path(root, request_id)
    with _lock(root, Path("unattended_explore/runner.lock")):
        with _lock(root, Path("campaigns/control.lock")):
            source = _source(source_status)
            projection = _projection(root, _root(root)[1])
            if _present(root / "HALT"):
                raise ReconciliationError("HALT_PRESENT", f"operator HALT is present: {root / 'HALT'}")
            _quiescent(projection.marker if projection else {}, process_probe)
            if _present(receipt_path):
                return _result(_replay(root, receipt_path, request_id, digest), receipt_path, True)
            if projection is None:
                plan = _recover(root, identity, source, digest, requested, process_probe)
                if plan is None:
                    raise ReconciliationError("STALE_PLAN", "planned projection is no longer present")
                history = root / Path(str(plan["mutation"]["destination"]))
                receipt_dir = _prepare_recovery_receipt_directory(
                    root, history, receipt_path,
                )
                receipt = _receipt(plan, request_id, True)
                _persist_receipt(receipt_path, receipt_dir, receipt, history)
                return _result(receipt, receipt_path, False)
            projection = _admission(root, projection, requested, process_probe)
            current = _plan(projection, source)
            if current["plan_digest"] != digest:
                raise ReconciliationError("STALE_PLAN", "current state does not match exact plan")
            history_relative = Path(str(current["mutation"]["destination"]))
            history_dir = _prepare_directory(
                root, history_relative.parent, receipt=False,
            )
            receipt_dir = _prepare_directory(
                root, Path("reconciliation/receipts"), receipt=True,
            )
            final = _current(finding_code, campaign_id, root, source_status, process_probe)
            if final["plan_digest"] != digest:
                raise ReconciliationError("STALE_PLAN", "state changed immediately before apply")
            active, history = root / "active_campaign.json", root / history_relative
            if _present(history):
                raise ReconciliationError("HISTORY_COLLISION", f"history already exists: {history}")
            _unambiguous(root, active)
            try:
                os.rename(active, history)
            except OSError as exc:
                raise ReconciliationError("ATOMIC_MOVE_FAILED", "could not quarantine projection") from exc
            _sync_mutation((root, history_dir), history, receipt_path)
            moved, _ = _read(root, history)
            expected = final["state_identity"]["active_projection"]["content_digest"]
            if _present(active) or content_digest(moved) != expected:
                raise ReconciliationError("MOVE_READBACK_FAILED", "quarantine readback mismatch")
            receipt = _receipt(final, request_id, False)
            _persist_receipt(receipt_path, receipt_dir, receipt, history)
            return _result(receipt, receipt_path, False)

__all__ = ["ACTION", "FINDING", "PLAN_SCHEMA", "RECEIPT_SCHEMA", "STATUS_SCHEMA",
           "ReconciliationError", "apply_reconciliation", "plan_reconciliation",
           "reconciliation_status", "validate_reconciliation_plan"]
