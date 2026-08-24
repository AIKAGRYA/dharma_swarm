"""Bounded campaign control for the hermetic five-run RSI pilot.

The pilot exercises planning, idempotency, lifecycle events, paired evidence,
receipts, and closeout without importing providers or candidate code.  Its
result has ``ControlPlaneTestOnly`` modality and cannot support an RSI claim.
Live EXPLORE remains fail-closed until the broker and isolated grader exist.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.state_io import (
    append_jsonl,
    atomic_json,
    content_digest,
    forge_state_root,
    now_utc,
    safe_json,
    validate_digest,
    validate_safe_id,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.version import PACKAGE_VERSION, source_commit, source_tree_state

PILOT_PROFILE = "pilot-five-offline"
MANIFEST_SCHEMA = "rsi_lab.campaign_manifest.v2"
EVENT_SCHEMA = "rsi_lab.campaign_event.v2"
ATTEMPT_SCHEMA = "rsi_lab.pilot_attempt.v2"
CLOSEOUT_SCHEMA = "rsi_lab.pilot_closeout.v2"


class CampaignError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _campaign_root() -> Path:
    return forge_state_root() / "campaigns"


def _manifest_payload(profile: str) -> dict[str, Any]:
    if profile != PILOT_PROFILE:
        raise CampaignError(
            "PROFILE_NOT_RUNNABLE",
            "only pilot-five-offline is implemented; live EXPLORE remains fail-closed",
        )
    return {
        "schema": MANIFEST_SCHEMA,
        "created_at": now_utc(),
        "profile": profile,
        "mode": "hermetic_control_plane_pilot",
        "source": {
            "package_version": PACKAGE_VERSION,
            "commit": source_commit(),
            "tree_state": source_tree_state(),
        },
        "run_count": 5,
        "comparison": {
            "design": "paired_seed_child_same_task",
            "fixture": "integer_double_v1",
            "tasks_per_run": 1,
        },
        "caps": {
            "provider_calls": 0,
            "tokens": 0,
            "usd": 0.0,
            "max_concurrency": 1,
            "absolute_wall_seconds": 30,
        },
        "containment": {
            "network": "not_used",
            "provider_credentials": "not_loaded",
            "candidate_code": "not_executed",
        },
        "claim_boundary": {
            "epistemic_modality": "ControlPlaneTestOnly",
            "scientific_verdict": "inconclusive",
            "positive_rsi_claim": False,
        },
    }


def plan_campaign(profile: str) -> dict[str, Any]:
    manifest = _manifest_payload(profile)
    digest = content_digest(manifest)
    stored = {**manifest, "manifest_digest": digest}
    path = _campaign_root() / "manifests" / f"{digest.removeprefix('sha256:')}.json"
    existing = safe_json(path)
    if existing is not None and existing != stored:
        raise CampaignError("MANIFEST_COLLISION", f"manifest path collision: {path}")
    if existing is None:
        atomic_json(path, stored)
    return {"manifest": stored, "manifest_digest": digest, "path": str(path)}


def _load_manifest(digest: str) -> dict[str, Any]:
    validate_digest(digest)
    path = _campaign_root() / "manifests" / f"{digest.removeprefix('sha256:')}.json"
    payload = safe_json(path)
    if payload is None:
        raise CampaignError("MANIFEST_NOT_FOUND", f"manifest not found: {digest}")
    claimed = payload.get("manifest_digest")
    unsigned = {key: value for key, value in payload.items() if key != "manifest_digest"}
    if claimed != digest or content_digest(unsigned) != digest:
        raise CampaignError("MANIFEST_TAMPERED", f"manifest digest mismatch: {digest}")
    if payload.get("profile") != PILOT_PROFILE or payload.get("run_count") != 5:
        raise CampaignError("MANIFEST_NOT_RUNNABLE", "manifest is not the fixed five-run pilot")
    return payload


@contextmanager
def _control_lock() -> Iterator[None]:
    path = _campaign_root() / "control.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CampaignError("CAMPAIGN_BUSY", "another campaign controller holds the lock") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _campaign_id(manifest_digest: str, request_id: str) -> str:
    raw = f"{manifest_digest}:{request_id}".encode("utf-8")
    return "campaign-pilot-" + hashlib.sha256(raw).hexdigest()[:16]


def _signed(payload: dict[str, Any], digest_field: str) -> dict[str, Any]:
    signed = dict(payload)
    signed[digest_field] = content_digest(payload)
    return signed


def _unsigned(payload: dict[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != digest_field}


def _expected_steps(run_count: int) -> list[tuple[str, int | None]]:
    return [
        ("CREATED", None),
        ("PREFLIGHTING", None),
        ("READY", None),
        ("RUNNING", None),
        *(("RUNNING", index) for index in range(1, run_count + 1)),
        ("DRAINING", None),
        ("CLOSING", None),
        ("COMPLETED", None),
    ]


def _read_events_strict(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CampaignError("EVENT_LOG_UNREADABLE", f"cannot read event log: {path}") from exc
    if text and not text.endswith("\n"):
        raise CampaignError("EVENT_LOG_TRUNCATED", "event log lacks terminal newline")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise CampaignError("EVENT_LOG_MALFORMED", f"blank event at line {line_number}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CampaignError(
                "EVENT_LOG_MALFORMED", f"invalid JSON event at line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise CampaignError(
                "EVENT_LOG_MALFORMED", f"non-object event at line {line_number}"
            )
        rows.append(row)
    return rows


def _validate_event_chain(
    run_dir: Path,
    *,
    campaign_id: str,
    manifest_digest: str,
    request_id: str,
    run_count: int,
) -> list[dict[str, Any]]:
    rows = _read_events_strict(run_dir / "events.jsonl")
    steps = _expected_steps(run_count)
    if len(rows) > len(steps):
        raise CampaignError("EVENT_CHAIN_INVALID", "event log exceeds fixed pilot schedule")
    previous_digest: str | None = None
    previous_state: str | None = None
    for index, row in enumerate(rows):
        expected_state, expected_attempt = steps[index]
        claimed_digest = row.get("event_digest")
        if (
            row.get("schema") != EVENT_SCHEMA
            or row.get("campaign_id") != campaign_id
            or row.get("manifest_digest") != manifest_digest
            or row.get("request_id") != request_id
            or row.get("sequence") != index + 1
            or row.get("state") != expected_state
            or row.get("previous_state") != previous_state
            or row.get("previous_event_digest") != previous_digest
            or claimed_digest != content_digest(_unsigned(row, "event_digest"))
        ):
            raise CampaignError(
                "EVENT_CHAIN_INVALID", f"event chain mismatch at sequence {index + 1}"
            )
        detail = row.get("detail")
        if not isinstance(detail, dict):
            raise CampaignError("EVENT_CHAIN_INVALID", "event detail must be an object")
        if expected_attempt is None and detail:
            raise CampaignError(
                "EVENT_CHAIN_INVALID", f"unexpected detail at sequence {index + 1}"
            )
        if expected_attempt is not None:
            expected_path = f"attempts/attempt_{expected_attempt:03d}.json"
            if (
                detail.get("attempt_completed") != expected_attempt
                or detail.get("attempt_receipt") != expected_path
                or not isinstance(detail.get("attempt_digest"), str)
            ):
                raise CampaignError(
                    "EVENT_CHAIN_INVALID",
                    f"attempt event mismatch at sequence {index + 1}",
                )
        previous_digest = str(claimed_digest)
        previous_state = str(row["state"])
    return rows


def _append_event(
    run_dir: Path,
    campaign_id: str,
    manifest_digest: str,
    sequence: int,
    previous: str | None,
    previous_event_digest: str | None,
    state: str,
    request_id: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = _signed({
        "schema": EVENT_SCHEMA,
        "campaign_id": campaign_id,
        "manifest_digest": manifest_digest,
        "sequence": sequence,
        "previous_state": previous,
        "previous_event_digest": previous_event_digest,
        "state": state,
        "request_id": request_id,
        "at": now_utc(),
        "detail": detail or {},
        "fencing_token": None,
    }, "event_digest")
    append_jsonl(run_dir / "events.jsonl", event)
    return event


def _paired_attempt(
    index: int,
    campaign_id: str,
    manifest_digest: str,
    previous_attempt_digest: str | None,
    *,
    at: str | None = None,
) -> dict[str, Any]:
    # Both arms intentionally execute the same tiny deterministic fixture.  The
    # receipt proves pairing and harness repeatability, never model improvement.
    task_input = index + 1
    expected = task_input * 2
    seed_output = task_input * 2
    child_output = task_input + task_input
    return _signed({
        "schema": ATTEMPT_SCHEMA,
        "campaign_id": campaign_id,
        "manifest_digest": manifest_digest,
        "attempt": index + 1,
        "previous_attempt_digest": previous_attempt_digest,
        "task_id": f"integer-double-v1-{index + 1}",
        "paired_task_digest": content_digest({"input": task_input, "expected": expected}),
        "seed": {"output": seed_output, "passed": seed_output == expected},
        "child": {"output": child_output, "passed": child_output == expected},
        "delta": int(child_output == expected) - int(seed_output == expected),
        "evidence_class": "ControlPlaneTestOnly",
        "scientific_verdict": "inconclusive",
        "positive_rsi_claim": False,
        "provider_calls": 0,
        "tokens": 0,
        "usd": 0.0,
        "at": at or now_utc(),
    }, "attempt_digest")


def _validate_attempts(
    run_dir: Path,
    *,
    campaign_id: str,
    manifest_digest: str,
    run_count: int,
) -> list[dict[str, Any]]:
    attempts_dir = run_dir / "attempts"
    if not attempts_dir.exists():
        return []
    paths = sorted(path for path in attempts_dir.iterdir() if path.is_file())
    expected_names = [f"attempt_{index:03d}.json" for index in range(1, len(paths) + 1)]
    if [path.name for path in paths] != expected_names or len(paths) > run_count:
        raise CampaignError(
            "ATTEMPT_SET_INVALID", "attempt receipts are non-sequential or exceed the plan"
        )
    rows: list[dict[str, Any]] = []
    previous_digest: str | None = None
    for index, path in enumerate(paths):
        payload = safe_json(path)
        if payload is None:
            raise CampaignError("ATTEMPT_RECEIPT_INVALID", f"invalid attempt receipt: {path}")
        expected = _paired_attempt(
            index,
            campaign_id,
            manifest_digest,
            previous_digest,
            at=str(payload.get("at") or ""),
        )
        if payload != expected:
            raise CampaignError(
                "ATTEMPT_RECEIPT_INVALID", f"attempt receipt mismatch: {path.name}"
            )
        previous_digest = str(payload["attempt_digest"])
        rows.append(payload)
    return rows


def _validate_partial_run(
    run_dir: Path,
    *,
    campaign_id: str,
    manifest_digest: str,
    request_id: str,
    run_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = _validate_event_chain(
        run_dir,
        campaign_id=campaign_id,
        manifest_digest=manifest_digest,
        request_id=request_id,
        run_count=run_count,
    )
    attempts = _validate_attempts(
        run_dir,
        campaign_id=campaign_id,
        manifest_digest=manifest_digest,
        run_count=run_count,
    )
    if len(events) < 4 and attempts:
        raise CampaignError(
            "CAMPAIGN_RESUME_UNSAFE", "attempt exists before RUNNING preflight state"
        )
    attempt_event_count = max(0, min(len(events) - 4, run_count))
    if len(attempts) not in {attempt_event_count, attempt_event_count + 1}:
        raise CampaignError(
            "CAMPAIGN_RESUME_UNSAFE",
            "attempt/event counts are not a crash-safe prefix",
        )
    if len(attempts) == attempt_event_count + 1 and len(events) >= 4 + run_count:
        raise CampaignError(
            "CAMPAIGN_RESUME_UNSAFE", "orphan attempt appears after terminal attempt events"
        )
    for index in range(attempt_event_count):
        event = events[4 + index]
        attempt = attempts[index]
        if event["detail"].get("attempt_digest") != attempt.get("attempt_digest"):
            raise CampaignError(
                "CAMPAIGN_RESUME_UNSAFE",
                f"attempt event digest mismatch for attempt {index + 1}",
            )
    return events, attempts


def _validate_closeout(
    payload: dict[str, Any],
    *,
    campaign_id: str,
    manifest_digest: str,
    request_id: str,
    events: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> None:
    attempt_digests = [str(row["attempt_digest"]) for row in attempts]
    event_digests = [str(row["event_digest"]) for row in events]
    if (
        payload.get("schema") != CLOSEOUT_SCHEMA
        or payload.get("campaign_id") != campaign_id
        or payload.get("manifest_digest") != manifest_digest
        or payload.get("request_id") != request_id
        or payload.get("state") != "COMPLETED"
        or payload.get("attempt_count") != len(attempts)
        or payload.get("paired_attempt_count")
        != sum(1 for row in attempts if row.get("paired_task_digest"))
        or payload.get("all_fixture_checks_passed")
        != all(row["seed"]["passed"] and row["child"]["passed"] for row in attempts)
        or payload.get("caps_observed")
        != {"provider_calls": 0, "tokens": 0, "usd": 0.0}
        or payload.get("evidence_class") != "ControlPlaneTestOnly"
        or payload.get("scientific_verdict") != "inconclusive"
        or payload.get("positive_rsi_claim") is not False
        or payload.get("attempt_receipt_digests") != attempt_digests
        or payload.get("attempts_digest") != content_digest(attempt_digests)
        or payload.get("terminal_event_digest")
        != (event_digests[-1] if event_digests else None)
        or payload.get("event_chain_digest") != content_digest(event_digests)
        or payload.get("closeout_digest")
        != content_digest(_unsigned(payload, "closeout_digest"))
    ):
        raise CampaignError("CLOSEOUT_INVALID", "closeout does not seal campaign evidence")


def _ensure_event(
    events: list[dict[str, Any]],
    *,
    step_index: int,
    run_dir: Path,
    campaign_id: str,
    manifest_digest: str,
    request_id: str,
    state: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_detail = detail or {}
    if len(events) > step_index:
        event = events[step_index]
        if event.get("state") != state or event.get("detail") != expected_detail:
            raise CampaignError(
                "CAMPAIGN_RESUME_UNSAFE",
                f"existing event differs from expected step {step_index + 1}",
            )
        return event
    if len(events) != step_index:
        raise CampaignError("CAMPAIGN_RESUME_UNSAFE", "event schedule contains a gap")
    previous = events[-1] if events else None
    event = _append_event(
        run_dir,
        campaign_id,
        manifest_digest,
        step_index + 1,
        str(previous["state"]) if previous else None,
        str(previous["event_digest"]) if previous else None,
        state,
        request_id,
        expected_detail,
    )
    events.append(event)
    return event


def run_campaign(manifest_digest: str, request_id: str) -> dict[str, Any]:
    validate_safe_id(request_id, field="request_id")
    manifest = _load_manifest(manifest_digest)
    campaign_id = _campaign_id(manifest_digest, request_id)
    run_dir = _campaign_root() / "runs" / campaign_id
    closeout_path = run_dir / "closeout.json"

    with _control_lock():
        run_dir.mkdir(parents=True, exist_ok=True)
        active_path = forge_state_root() / "active_campaign.json"
        run_count = int(manifest["run_count"])
        events, attempts = _validate_partial_run(
            run_dir,
            campaign_id=campaign_id,
            manifest_digest=manifest_digest,
            request_id=request_id,
            run_count=run_count,
        )
        was_partial = bool(events or attempts)
        if closeout_path.exists():
            existing = safe_json(closeout_path)
            if existing is None:
                raise CampaignError("CLOSEOUT_INVALID", "closeout is unreadable")
            _validate_closeout(
                existing,
                campaign_id=campaign_id,
                manifest_digest=manifest_digest,
                request_id=request_id,
                events=events,
                attempts=attempts,
            )
            atomic_json(
                active_path,
                {
                    "campaign_id": campaign_id,
                    "manifest_digest": manifest_digest,
                    "state": "COMPLETED",
                    "updated_at": now_utc(),
                },
            )
            return {"campaign_id": campaign_id, "idempotent": True, "closeout": existing}

        for step_index, state in enumerate(("CREATED", "PREFLIGHTING", "READY", "RUNNING")):
            _ensure_event(
                events,
                step_index=step_index,
                run_dir=run_dir,
                campaign_id=campaign_id,
                manifest_digest=manifest_digest,
                request_id=request_id,
                state=state,
            )
            atomic_json(
                active_path,
                {
                    "campaign_id": campaign_id,
                    "manifest_digest": manifest_digest,
                    "state": state,
                    "updated_at": now_utc(),
                },
            )

        for index in range(run_count):
            if index < len(attempts):
                attempt = attempts[index]
            else:
                previous_attempt_digest = (
                    str(attempts[-1]["attempt_digest"]) if attempts else None
                )
                attempt = _paired_attempt(
                    index,
                    campaign_id,
                    manifest_digest,
                    previous_attempt_digest,
                )
                try:
                    write_json_exclusive(
                        run_dir / "attempts" / f"attempt_{index + 1:03d}.json",
                        attempt,
                    )
                except FileExistsError as exc:
                    raise CampaignError(
                        "ATTEMPT_RECEIPT_COLLISION",
                        f"attempt {index + 1} already exists outside validated resume state",
                    ) from exc
                attempts.append(attempt)
            _ensure_event(
                events,
                step_index=4 + index,
                run_dir=run_dir,
                campaign_id=campaign_id,
                manifest_digest=manifest_digest,
                request_id=request_id,
                state="RUNNING",
                detail={
                    "attempt_completed": index + 1,
                    "attempt_receipt": f"attempts/attempt_{index + 1:03d}.json",
                    "attempt_digest": attempt["attempt_digest"],
                },
            )

        for offset, state in enumerate(("DRAINING", "CLOSING", "COMPLETED")):
            _ensure_event(
                events,
                step_index=4 + run_count + offset,
                run_dir=run_dir,
                campaign_id=campaign_id,
                manifest_digest=manifest_digest,
                request_id=request_id,
                state=state,
            )

        attempt_digests = [str(row["attempt_digest"]) for row in attempts]
        event_digests = [str(row["event_digest"]) for row in events]
        closeout = _signed({
            "schema": CLOSEOUT_SCHEMA,
            "campaign_id": campaign_id,
            "manifest_digest": manifest_digest,
            "request_id": request_id,
            "state": "COMPLETED",
            "attempt_count": len(attempts),
            "paired_attempt_count": sum(
                1 for row in attempts if row.get("paired_task_digest")
            ),
            "all_fixture_checks_passed": all(
                row["seed"]["passed"] and row["child"]["passed"] for row in attempts
            ),
            "caps_observed": {"provider_calls": 0, "tokens": 0, "usd": 0.0},
            "attempt_receipt_digests": attempt_digests,
            "attempts_digest": content_digest(attempt_digests),
            "terminal_event_digest": event_digests[-1],
            "event_chain_digest": content_digest(event_digests),
            "evidence_class": "ControlPlaneTestOnly",
            "scientific_verdict": "inconclusive",
            "positive_rsi_claim": False,
            "resumed_after_interruption": was_partial,
            "finished_at": now_utc(),
        }, "closeout_digest")
        try:
            write_json_exclusive(closeout_path, closeout)
        except FileExistsError as exc:
            raise CampaignError(
                "CLOSEOUT_COLLISION", "closeout appeared during serialized campaign run"
            ) from exc
        _validate_closeout(
            closeout,
            campaign_id=campaign_id,
            manifest_digest=manifest_digest,
            request_id=request_id,
            events=events,
            attempts=attempts,
        )
        atomic_json(
            active_path,
            {
                "campaign_id": campaign_id,
                "manifest_digest": manifest_digest,
                "state": "COMPLETED",
                "updated_at": now_utc(),
            },
        )
        return {
            "campaign_id": campaign_id,
            "idempotent": False,
            "resumed": was_partial,
            "closeout": closeout,
        }


def _run_rows() -> list[dict[str, Any]]:
    root = _campaign_root() / "runs"
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        closeout: dict[str, Any] | None = None
        try:
            raw_events = _read_events_strict(directory / "events.jsonl")
            if not raw_events:
                raise CampaignError("CAMPAIGN_EMPTY", "campaign has no event evidence")
            manifest_digest = str(raw_events[0].get("manifest_digest") or "")
            request_id = str(raw_events[0].get("request_id") or "")
            events, attempts = _validate_partial_run(
                directory,
                campaign_id=directory.name,
                manifest_digest=manifest_digest,
                request_id=request_id,
                run_count=5,
            )
            closeout_path = directory / "closeout.json"
            if closeout_path.exists():
                closeout = safe_json(closeout_path)
                if closeout is None:
                    raise CampaignError("CLOSEOUT_INVALID", "closeout is unreadable")
                _validate_closeout(
                    closeout,
                    campaign_id=directory.name,
                    manifest_digest=manifest_digest,
                    request_id=request_id,
                    events=events,
                    attempts=attempts,
                )
            integrity, integrity_error = "verified", None
        except CampaignError as exc:
            events, attempts = [], []
            manifest_digest = None
            integrity, integrity_error = "failed", exc.code
        rows.append(
            {
                "campaign_id": directory.name,
                "state": (
                    (closeout or {}).get("state")
                    or (events[-1].get("state") if events else "CORRUPT")
                ),
                "event_count": len(events),
                "attempt_count": len(attempts),
                "manifest_digest": manifest_digest,
                "updated_at": (closeout or {}).get("finished_at")
                or (events[-1].get("at") if events else None),
                "integrity": integrity,
                "integrity_error": integrity_error,
            }
        )
    return sorted(rows, key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def list_campaigns(state: str | None = None) -> dict[str, Any]:
    rows = _run_rows()
    if state:
        rows = [row for row in rows if str(row.get("state", "")).lower() == state.lower()]
    return {"campaigns": rows, "count": len(rows)}


def campaign_status(campaign_id: str | None = None) -> dict[str, Any]:
    rows = _run_rows()
    if campaign_id is None:
        if not rows:
            return {"campaign": None}
        campaign_id = str(rows[0]["campaign_id"])
    validate_safe_id(campaign_id, field="campaign")
    row = next((item for item in rows if item["campaign_id"] == campaign_id), None)
    if row is None:
        raise CampaignError("CAMPAIGN_NOT_FOUND", f"campaign not found: {campaign_id}")
    return {
        "campaign": row,
        "closeout": (
            safe_json(_campaign_root() / "runs" / campaign_id / "closeout.json")
            if row.get("integrity") == "verified"
            else None
        ),
    }


def campaign_progress(campaign_id: str | None = None) -> dict[str, Any]:
    status = campaign_status(campaign_id)
    row = status.get("campaign")
    if row is None:
        return {"campaign": None, "completed": 0, "planned": 0}
    return {
        "campaign": row["campaign_id"],
        "state": row["state"],
        "completed": row["attempt_count"],
        "planned": 5,
        "fraction": row["attempt_count"] / 5,
    }


def campaign_events(campaign_id: str, after: int | None = None) -> dict[str, Any]:
    validate_safe_id(campaign_id, field="campaign")
    run_dir = _campaign_root() / "runs" / campaign_id
    path = run_dir / "events.jsonl"
    if not path.is_file():
        raise CampaignError("CAMPAIGN_NOT_FOUND", f"campaign not found: {campaign_id}")
    raw = _read_events_strict(path)
    if not raw:
        raise CampaignError("CAMPAIGN_EMPTY", "campaign has no events")
    rows, _attempts = _validate_partial_run(
        run_dir,
        campaign_id=campaign_id,
        manifest_digest=str(raw[0].get("manifest_digest") or ""),
        request_id=str(raw[0].get("request_id") or ""),
        run_count=5,
    )
    if after is not None:
        rows = [row for row in rows if int(row.get("sequence", 0)) > after]
    return {"campaign": campaign_id, "events": rows, "count": len(rows)}


__all__ = [
    "CampaignError",
    "PILOT_PROFILE",
    "campaign_events",
    "campaign_progress",
    "campaign_status",
    "list_campaigns",
    "plan_campaign",
    "run_campaign",
]
