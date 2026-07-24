"""Tests for dharma_swarm.episode_ledger — versioned Episode Ledger events.

THE_KEEL §6: versioned + validated schemas; stable episode/attempt IDs;
explicit ordering/dedup; secret redaction before persistence; conflicting
observations stay visible; missing evidence fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.episode_ledger import (
    EPISODE_EVENT_SCHEMA_VERSION,
    EVENT_TYPES,
    EpisodeEvent,
    EpisodeLedgerWriter,
    LedgerValidationError,
    new_attempt_id,
    new_episode_id,
    project_episode,
    redact_payload,
)


def _event(event_type: str = "episode_opened", sequence: int = 0, **payload):
    return EpisodeEvent.new(
        event_type=event_type,
        episode_id="ep_test0000000001",
        attempt_id="at_test0000000001",
        sequence=sequence,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Schema: versioned, validated, round-trips
# ---------------------------------------------------------------------------


def test_lifecycle_event_vocabulary_is_the_keel_family():
    assert set(EVENT_TYPES) == {
        "episode_opened",
        "attempt_started",
        "observation_recorded",
        "effect_requested",
        "effect_resolved",
        "review_recorded",
        "episode_closed",
        "post_merge_observation",
    }


def test_event_round_trips_through_json():
    event = _event("observation_recorded", 3, note="tests green")
    rebuilt = EpisodeEvent.from_dict(json.loads(json.dumps(event.to_dict())))
    assert rebuilt == event
    assert rebuilt.schema_version == EPISODE_EVENT_SCHEMA_VERSION


def test_unknown_schema_version_fails_closed():
    payload = _event().to_dict()
    payload["schema_version"] = "episode_event.v999"
    with pytest.raises(LedgerValidationError, match="schema_version"):
        EpisodeEvent.from_dict(payload)


def test_unknown_event_type_fails_closed():
    with pytest.raises(LedgerValidationError, match="event_type"):
        _event("task_done")
    payload = _event().to_dict()
    payload["event_type"] = "task_done"
    with pytest.raises(LedgerValidationError, match="event_type"):
        EpisodeEvent.from_dict(payload)


def test_redaction_reaches_secrets_nested_in_lists():
    """Lists are not opaque leaves: a secret-like key inside a dict nested in a
    list (e.g. messages=[{"api_key": ...}]) must be masked before persistence,
    at any depth."""
    event = _event(
        "observation_recorded",
        1,
        messages=[{"api_key": "sk-live-1", "note": "ok"}],
        batches=[[{"token": "t0p"}]],
        plain=["keep", 1],
    )
    assert event.payload["messages"][0]["api_key"] == "[REDACTED]"
    assert event.payload["messages"][0]["note"] == "ok"
    assert event.payload["batches"][0][0]["token"] == "[REDACTED]"
    assert event.payload["plain"] == ["keep", 1]


def test_from_dict_requires_event_id():
    """A stored record with no event_id must fail closed, not silently mint a
    fresh identity — otherwise dedup and the tamper check cannot distinguish
    malformed historical data from valid events."""
    record = _event("observation_recorded", 1, note="ok").to_dict()
    del record["event_id"]
    with pytest.raises(LedgerValidationError, match="event_id"):
        EpisodeEvent.from_dict(record)
    record["event_id"] = ""
    with pytest.raises(LedgerValidationError, match="event_id"):
        EpisodeEvent.from_dict(record)


def test_fractional_sequence_fails_closed():
    """int() truncation must not launder sequence=1.9 into 1 — a non-integer
    sequence is a malformed event, and misordering it violates the validated
    schema."""
    with pytest.raises(LedgerValidationError, match="sequence"):
        EpisodeEvent.new(
            event_type="observation_recorded",
            episode_id="ep_test0000000001",
            attempt_id="at_test0000000001",
            sequence=1.9,  # type: ignore[arg-type]
            payload={"note": "x"},
        )
    record = _event("observation_recorded", 1, note="x").to_dict()
    record["sequence"] = 1.9
    with pytest.raises(LedgerValidationError, match="sequence"):
        EpisodeEvent.from_dict(record)


def test_missing_episode_id_fails_closed():
    with pytest.raises(LedgerValidationError, match="episode_id"):
        EpisodeEvent.new(
            event_type="episode_opened", episode_id="", attempt_id="", sequence=0
        )


def test_effect_events_require_idempotency_key():
    """effect_requested / effect_resolved carry the fence key — mandatory."""
    for event_type in ("effect_requested", "effect_resolved"):
        with pytest.raises(LedgerValidationError, match="idempotency_key"):
            _event(event_type, 1)
        ok = _event(event_type, 1, idempotency_key="idem-1", receipt_id="r-1")
        assert ok.payload["idempotency_key"] == "idem-1"


# ---------------------------------------------------------------------------
# Stable IDs and deterministic event identity
# ---------------------------------------------------------------------------


def test_episode_and_attempt_ids_are_stable_prefixed_and_unique():
    ep_a, ep_b = new_episode_id(), new_episode_id()
    at = new_attempt_id()
    assert ep_a.startswith("ep_") and at.startswith("at_")
    assert ep_a != ep_b


def test_event_id_is_deterministic_over_content():
    a = _event("observation_recorded", 2, note="x")
    b = EpisodeEvent.new(
        event_type="observation_recorded",
        episode_id=a.episode_id,
        attempt_id=a.attempt_id,
        sequence=2,
        payload={"note": "x"},
    )
    assert a.event_id == b.event_id
    assert a.event_id != _event("observation_recorded", 3, note="x").event_id


# ---------------------------------------------------------------------------
# Pure projector: ordering, dedup, visible conflicts, fail-closed closure
# ---------------------------------------------------------------------------


def test_projection_orders_by_sequence_and_dedupes():
    opened = _event("episode_opened", 0)
    obs = _event("observation_recorded", 2, note="late")
    started = _event("attempt_started", 1)
    state = project_episode([obs, opened, started, obs])
    assert [e.event_type for e in state.events] == [
        "episode_opened",
        "attempt_started",
        "observation_recorded",
    ]
    assert state.duplicate_event_ids == [obs.event_id]


def test_conflicting_observations_stay_visible():
    """Never last-write-wins: both observations survive projection."""
    a = _event("observation_recorded", 1, check="tests", verdict="pass")
    b = _event("observation_recorded", 2, check="tests", verdict="fail")
    state = project_episode([_event("episode_opened", 0), a, b])
    verdicts = [e.payload["verdict"] for e in state.observations]
    assert verdicts == ["pass", "fail"]


def test_closure_without_evidence_fails_closed():
    events = [_event("episode_opened", 0), _event("episode_closed", 1, outcome="ok")]
    state = project_episode(events)
    assert state.closed is True
    assert state.closure_valid is False, "closed with zero observations/reviews"

    with_evidence = [
        _event("episode_opened", 0),
        _event("observation_recorded", 1, note="ran tests"),
        _event("episode_closed", 2, outcome="ok"),
    ]
    assert project_episode(with_evidence).closure_valid is True


def test_late_evidence_cannot_validate_an_earlier_close():
    """Evidence appended AFTER episode_closed must not retroactively turn a
    close-without-evidence into a valid closure — ordering cannot be bypassed."""
    state = project_episode(
        [
            _event("episode_opened", 0),
            _event("episode_closed", 1, outcome="ok"),
            _event("observation_recorded", 2, note="late"),
        ]
    )
    assert state.closed is True
    assert state.closure_valid is False, "late evidence validated an earlier close"


def test_projection_rejects_mixed_episode_ids():
    """project_episode projects ONE episode; silently blending events from two
    episodes could let one episode's evidence validate another's closure."""
    mine = _event("episode_opened", 0)
    other = EpisodeEvent.new(
        event_type="episode_closed",
        episode_id="ep_other000000001",
        attempt_id="at_other000000001",
        sequence=1,
        payload={"outcome": "ok"},
    )
    with pytest.raises(LedgerValidationError, match="episode"):
        project_episode([mine, other])


# ---------------------------------------------------------------------------
# Persistence wrapper: append-only JSONL, redaction, write-side dedup
# ---------------------------------------------------------------------------


def test_redaction_masks_secretlike_keys_recursively():
    redacted = redact_payload(
        {"api_key": "sk-123", "nested": {"password": "hunter2"}, "note": "ok"}
    )
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["note"] == "ok"


def test_writer_appends_redacted_events_and_dedupes(tmp_path: Path):
    writer = EpisodeLedgerWriter(tmp_path / "episodes.jsonl")
    opened = _event("episode_opened", 0, token="sekrit")
    obs = _event("observation_recorded", 1, note="fine")

    assert writer.append(opened) is True
    assert writer.append(obs) is True
    assert writer.append(obs) is False, "duplicate event_id must not re-append"

    lines = (tmp_path / "episodes.jsonl").read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["payload"]["token"] == "[REDACTED]"
    assert first["schema_version"] == EPISODE_EVENT_SCHEMA_VERSION


def test_persisted_events_round_trip_through_from_dict(tmp_path: Path):
    """Redaction must not break the tamper check: a persisted event (secrets
    masked) re-validates via from_dict — so redaction happens at CONSTRUCTION
    and event identity is computed over what is actually persisted."""
    path = tmp_path / "episodes.jsonl"
    writer = EpisodeLedgerWriter(path)
    original = _event("observation_recorded", 1, api_key="sk-live-1", note="ok")
    assert original.payload["api_key"] == "[REDACTED]", "secret survived construction"
    writer.append(original)
    rebuilt = EpisodeEvent.from_dict(json.loads(path.read_text().splitlines()[0]))
    assert rebuilt == original


def test_append_refuses_payload_mutated_after_construction(tmp_path: Path):
    """The ledger is content-addressed: a payload mutated between construction
    and append no longer matches the already-computed event_id and must be
    refused, not persisted under a stale identity."""
    writer = EpisodeLedgerWriter(tmp_path / "episodes.jsonl")
    event = _event("observation_recorded", 1, note="ok")
    event.payload["note"] = "tampered"
    with pytest.raises(LedgerValidationError, match="altered"):
        writer.append(event)
    assert not (tmp_path / "episodes.jsonl").exists(), "tampered event was persisted"


def test_writer_survives_restart_dedup(tmp_path: Path):
    """A NEW writer over an existing file still refuses duplicates (rehydrates
    seen event_ids from disk)."""
    path = tmp_path / "episodes.jsonl"
    obs = _event("observation_recorded", 1, note="fine")
    assert EpisodeLedgerWriter(path).append(obs) is True
    assert EpisodeLedgerWriter(path).append(obs) is False
    assert len(path.read_text().splitlines()) == 1


def test_writer_recovers_from_corrupt_lines(tmp_path: Path):
    """A torn/corrupt line must not poison rehydration (corruption recovery)."""
    path = tmp_path / "episodes.jsonl"
    obs = _event("observation_recorded", 1, note="fine")
    EpisodeLedgerWriter(path).append(obs)
    with open(path, "a") as f:
        f.write("{torn json\n")
    writer = EpisodeLedgerWriter(path)
    assert writer.append(obs) is False
    assert writer.append(_event("review_recorded", 2, reviewer="codex")) is True


def test_squatted_event_id_cannot_suppress_the_real_event(tmp_path: Path):
    """A malformed line that merely CLAIMS a valid event_id must not poison
    write-side dedup: after restart, appending the genuine event still
    persists it (silent evidence loss is worse than a rejected duplicate)."""
    path = tmp_path / "episodes.jsonl"
    obs = _event("observation_recorded", 1, note="fine")
    path.write_text(json.dumps({"event_id": obs.event_id}) + "\n")
    writer = EpisodeLedgerWriter(path)
    assert writer.append(obs) is True, "squatted id suppressed the real event"
    persisted = [json.loads(x) for x in path.read_text().splitlines()]
    assert any(r.get("schema_version") == EPISODE_EVENT_SCHEMA_VERSION for r in persisted)


def test_writer_recovers_from_valid_json_non_object_lines(tmp_path: Path):
    """A line that parses as JSON but is not an object (null, number, string,
    array) must be skipped like any other corrupt line, not crash rehydration."""
    path = tmp_path / "episodes.jsonl"
    obs = _event("observation_recorded", 1, note="fine")
    EpisodeLedgerWriter(path).append(obs)
    with open(path, "a") as f:
        f.write("null\n42\n\"x\"\n[]\n")
    writer = EpisodeLedgerWriter(path)
    assert writer.append(obs) is False
    assert writer.append(_event("review_recorded", 2, reviewer="codex")) is True
