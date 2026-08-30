"""Event-chain validation for the hermetic five-run RSI pilot campaign.

Split out of ``campaign_control`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import (
    append_jsonl,
    content_digest,
    now_utc,
    safe_json,
)

EVENT_SCHEMA = "rsi_lab.campaign_event.v2"
ATTEMPT_SCHEMA = "rsi_lab.pilot_attempt.v2"
CLOSEOUT_SCHEMA = "rsi_lab.pilot_closeout.v2"


class CampaignError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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
