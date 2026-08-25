"""Status must derive health from fresh, sealed evidence—not a stale score/PID."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.live import LiveResult, write_live_receipt
from dharma_swarm.foundry.status import (
    CANONICAL_REMOTE,
    EXIT_DEGRADED,
    EXIT_OK,
    EXIT_TERMINAL,
    EXIT_UNHEALTHY,
    assess_status,
)


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _service(root, **updates):
    payload = {
        "schema_version": "foundry_service_state.v1",
        "boot_id": "boot-1",
        "pid": 123,
        "code_sha": "a" * 40,
        "status": "running",
        "mode": "campaign",
        "cycles_run": 4,
        "total_proposed": 12,
        "provider_failures": 0,
        "heartbeat_at": NOW.isoformat(),
    }
    payload.update(updates)
    root.mkdir(parents=True, exist_ok=True)
    (root / "service_state.json").write_text(json.dumps(payload))


def _assess(root, **kwargs):
    return assess_status(
        repo_root=root / "repo",
        state_root=root,
        expected_sha=kwargs.pop("expected_sha", "a" * 40),
        now=NOW,
        git_probe=kwargs.pop(
            "git_probe", lambda repo: ("a" * 40, False, CANONICAL_REMOTE, "")
        ),
        process_probe=kwargs.pop(
            "process_probe", lambda pid: (True, "python foundry_daemon.py --mode campaign")
        ),
        runtime_probe=kwargs.pop("runtime_probe", lambda mode: {"all": True}),
        **kwargs,
    )


def _fresh_receipt(root):
    result = LiveResult("groq", "m", 1, 1, 1.0)
    result.ran_at = NOW.isoformat()
    write_live_receipt(result, state_root=root)


def test_healthy_requires_fresh_process_sha_dependencies_and_receipt(tmp_path):
    _service(tmp_path)
    _fresh_receipt(tmp_path)
    payload, code = _assess(tmp_path)
    assert code == EXIT_OK
    assert payload["verdict"] == "healthy"
    assert "score" not in payload["health_basis"]


def test_stale_heartbeat_is_unhealthy_even_if_pid_is_alive(tmp_path):
    _service(tmp_path, heartbeat_at=(NOW - timedelta(hours=2)).isoformat())
    _fresh_receipt(tmp_path)
    payload, code = _assess(tmp_path, max_heartbeat_age_seconds=900)
    assert code == EXIT_UNHEALTHY
    assert "heartbeat_stale" in payload["problems"]


def test_reused_pid_or_code_sha_mismatch_is_unhealthy(tmp_path):
    _service(tmp_path)
    _fresh_receipt(tmp_path)
    payload, code = _assess(
        tmp_path,
        git_probe=lambda repo: ("b" * 40, False, CANONICAL_REMOTE, ""),
        process_probe=lambda pid: (True, "unrelated-worker"),
    )
    assert code == EXIT_UNHEALTHY
    assert "code_sha_mismatch" in payload["problems"]
    assert "pid_missing_or_reused" in payload["problems"]


def test_provider_outage_is_visible_degraded_state(tmp_path):
    _service(
        tmp_path,
        status="degraded_provider_outage",
        provider_failures=8,
        consecutive_provider_outages=2,
    )
    _fresh_receipt(tmp_path)
    payload, code = _assess(tmp_path)
    assert code == EXIT_DEGRADED
    assert payload["service"]["consecutive_provider_outages"] == 2
    assert "provider_outage_active" in payload["warnings"]


def test_terminal_kill_dominates_stale_pid_or_score(tmp_path):
    _service(tmp_path)
    killswitch.persist_terminal_kill(
        tmp_path, category="replication_failure", reason="mismatch"
    )
    payload, code = _assess(tmp_path)
    assert code == EXIT_TERMINAL
    assert payload["verdict"] == "killed"


def test_no_receipt_evidence_is_degraded_not_healthy(tmp_path):
    _service(tmp_path)
    payload, code = _assess(tmp_path)
    assert code == EXIT_DEGRADED
    assert "no_receipt_evidence" in payload["warnings"]


def test_expected_release_remote_and_untracked_cleanliness_are_mandatory(tmp_path):
    _service(tmp_path)
    _fresh_receipt(tmp_path)
    payload, code = _assess(
        tmp_path,
        expected_sha="b" * 40,
        git_probe=lambda repo: (
            "a" * 40,
            True,
            "https://github.com/not-authority/dharma_swarm.git",
            "",
        ),
    )
    assert code == EXIT_UNHEALTHY
    assert "expected_sha_mismatch" in payload["problems"]
    assert "canonical_remote_mismatch" in payload["problems"]
    assert "checkout_dirty_unsealed_code" in payload["problems"]


def test_uppercase_quarantine_json_is_terminal(tmp_path):
    _service(tmp_path)
    _fresh_receipt(tmp_path)
    (tmp_path / "QUARANTINE.json").write_text("{}", encoding="utf-8")
    payload, code = _assess(tmp_path)
    assert code == EXIT_TERMINAL
    assert payload["verdict"] == "quarantined"


def test_unresolved_spend_reservation_is_visible_degraded_evidence(tmp_path):
    _service(tmp_path)
    _fresh_receipt(tmp_path)
    (tmp_path / "spend_ledger.json").write_text(json.dumps({
        "schema_version": "foundry_spend_ledger.v2",
        "month": NOW.strftime("%Y-%m"),
        "committed_spend_usd": 1.0,
        "reservations": [{
            "reservation_id": "crash-hold",
            "amount_usd": 5.0,
            "created_at": NOW.isoformat(),
            "target_id": "t",
            "boot_id": "boot-old",
        }],
        "spend_usd": 6.0,
    }), encoding="utf-8")
    payload, code = _assess(tmp_path)
    assert code == EXIT_DEGRADED
    assert payload["spend_ledger"]["reserved_spend_usd"] == 5.0
    assert "spend_reservations_unresolved:1" in payload["warnings"]
