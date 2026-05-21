from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from scripts.runtime import persistent_agent_census as census


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    _write(path, "\n".join(json.dumps(row) for row in rows) + "\n")


def _row(rows: list[census.ReadinessRow], name: str) -> census.ReadinessRow:
    matches = [row for row in rows if row.name == name]
    assert len(matches) == 1
    return matches[0]


def _runtime_db(state: Path) -> Path:
    db_path = state / "state" / "runtime.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE task_claims (
                claim_id TEXT, task_id TEXT, session_id TEXT, agent_id TEXT, status TEXT,
                claimed_at TEXT, acked_at TEXT, heartbeat_at TEXT, stale_after TEXT,
                recovered_at TEXT, retry_count INTEGER, metadata_json TEXT, trace_id TEXT
            );
            CREATE TABLE delegation_runs (
                run_id TEXT, session_id TEXT, task_id TEXT, claim_id TEXT, parent_run_id TEXT,
                assigned_by TEXT, assigned_to TEXT, requested_output_json TEXT,
                current_artifact_id TEXT, status TEXT, started_at TEXT, completed_at TEXT,
                failure_code TEXT, metadata_json TEXT, trace_id TEXT
            );
            CREATE TABLE session_events (
                event_id TEXT, session_id TEXT, ledger_kind TEXT, event_name TEXT,
                task_id TEXT, run_id TEXT, agent_id TEXT, summary TEXT, event_text TEXT,
                payload_json TEXT, created_at TEXT
            );
            CREATE TABLE sessions (
                session_id TEXT, operator_id TEXT, status TEXT, current_task_id TEXT,
                active_bundle_id TEXT, metadata_json TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE context_bundles (
                bundle_id TEXT, session_id TEXT, task_id TEXT, run_id TEXT,
                token_budget INTEGER, rendered_text TEXT, sections_json TEXT,
                source_refs_json TEXT, checksum TEXT, created_at TEXT, metadata_json TEXT
            );
            CREATE TABLE routing_decisions (
                decision_id TEXT, session_id TEXT, task_id TEXT, run_id TEXT,
                action_name TEXT, route_path TEXT, selected_provider TEXT,
                selected_model_hint TEXT, confidence REAL, requires_human INTEGER,
                reasons_json TEXT, metadata_json TEXT, created_at TEXT
            );
            CREATE TABLE memory_facts (
                fact_id TEXT, session_id TEXT, task_id TEXT, fact_kind TEXT,
                truth_state TEXT, text TEXT, confidence REAL, valid_from TEXT,
                valid_to TEXT, source_event_id TEXT, source_artifact_id TEXT,
                provenance_json TEXT, metadata_json TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE artifact_records (
                artifact_id TEXT, session_id TEXT, task_id TEXT, run_id TEXT,
                artifact_kind TEXT, manifest_path TEXT, payload_path TEXT, checksum TEXT,
                parent_artifact_id TEXT, promotion_state TEXT, created_at TEXT,
                metadata_json TEXT
            );
            CREATE TABLE external_outcomes (
                outcome_id TEXT, session_id TEXT, task_id TEXT, run_id TEXT,
                outcome_kind TEXT, subject_id TEXT, value TEXT, unit TEXT,
                confidence REAL, status TEXT, summary TEXT, metadata_json TEXT, created_at TEXT
            );
            CREATE TABLE workspace_leases (
                lease_id TEXT, zone_path TEXT, holder_run_id TEXT, mode TEXT,
                base_hash TEXT, acquired_at TEXT, expires_at TEXT, released_at TEXT,
                metadata_json TEXT
            );
            """
        )
    return db_path


def _insert_complete_chain(
    db_path: Path,
    *,
    agent: str = "agent",
    suffix: str = "a",
    at: datetime | None = None,
    include_context: bool = True,
    include_route: bool = True,
    include_memory: bool = True,
    include_artifact: bool = True,
    include_outcome: bool = True,
    governed: bool = False,
    lease: bool = False,
) -> None:
    now = at or census._utc_now()
    stale_after = now + timedelta(minutes=10)
    session_id = f"s-{suffix}"
    task_id = f"t-{suffix}"
    claim_id = f"c-{suffix}"
    run_id = f"r-{suffix}"
    metadata = json.dumps({"execution_lease_required": True}) if governed else "{}"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO task_claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                claim_id,
                task_id,
                session_id,
                agent,
                "running",
                None,
                None,
                census._iso(now),
                census._iso(stale_after),
                None,
                0,
                metadata,
                None,
            ),
        )
        db.execute(
            "INSERT INTO delegation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                session_id,
                task_id,
                claim_id,
                None,
                "operator",
                agent,
                "{}",
                None,
                "running",
                census._iso(now),
                None,
                None,
                "{}",
                None,
            ),
        )
        db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
            (session_id, "operator", "active", task_id, None, "{}", census._iso(now), census._iso(now)),
        )
        if include_context:
            db.execute(
                "INSERT INTO context_bundles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (f"b-{suffix}", session_id, task_id, run_id, 100, "context", "[]", "[]", "sha", census._iso(now), "{}"),
            )
        if include_route:
            db.execute(
                "INSERT INTO routing_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"d-{suffix}", session_id, task_id, run_id, "act", "route", "provider", "model", 1.0, 0, "[]", "{}", census._iso(now)),
            )
        if include_memory:
            db.executemany(
                "INSERT INTO session_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (f"mread-{suffix}", session_id, "runtime", "memory_read", task_id, run_id, agent, "memory recall", "", "{}", census._iso(now)),
                    (f"mwrite-{suffix}", session_id, "runtime", "memory_write", task_id, run_id, agent, "persisted memory", "", "{}", census._iso(now)),
                ],
            )
        if include_artifact:
            db.execute(
                "INSERT INTO artifact_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"a-{suffix}", session_id, task_id, run_id, "runtime", "manifest", "payload", "sha", None, "draft", census._iso(now), "{}"),
            )
        if include_outcome:
            db.execute(
                "INSERT INTO external_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"o-{suffix}", session_id, task_id, run_id, "task", agent, "1", "unit", 1.0, "succeeded", "done", "{}", census._iso(now)),
            )
        if lease:
            db.execute(
                "INSERT INTO workspace_leases VALUES (?,?,?,?,?,?,?,?,?)",
                (f"l-{suffix}", "/tmp/work", run_id, "write", "base", census._iso(now), census._iso(stale_after), None, "{}"),
            )


def test_registered_agent_workers_do_not_promote_without_l4_receipts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "home" / ".dharma"
    for name in ["cyber-glm5", "cyber-kimi25", "cyber-opus"]:
        agent_dir = state / "agents" / name
        _write_json(
            agent_dir / "identity.json",
            {
                "name": name,
                "model": "test-model",
                "tasks_completed": 1,
                "tasks_failed": 0,
            },
        )
        _write_jsonl(
            agent_dir / "task_log.jsonl",
            [
                {
                    "task": "recent useful work",
                    "success": True,
                    "timestamp": "2026-05-18T07:47:44+00:00",
                }
            ],
        )

    rows = census.build_readiness_rows(
        repo_root=repo,
        state_root=state,
        agora_root=tmp_path / "missing-agora",
    )

    for name in ["cyber-glm5", "cyber-kimi25", "cyber-opus"]:
        row = _row(rows, name)
        assert row.current_tier == "L2"
        assert row.registered_identity is True
        assert row.passport_present is False
        assert row.wake_claim_present is False
        assert row.runtime_session_present is False
        assert row.count_as_l4 is False
        assert row.next_required_action == "create signed agent passport"


def test_legacy_ginko_agent_registry_paths_are_read_only_compatibility(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "home" / ".dharma"
    _write_json(
        state / "ginko" / "agents" / "legacy-worker" / "identity.json",
        {
            "name": "legacy-worker",
            "model": "legacy-model",
            "tasks_completed": 0,
            "tasks_failed": 0,
        },
    )
    _write_json(
        state / "agents" / "primary-worker" / "identity.json",
        {
            "name": "primary-worker",
            "model": "primary-model",
            "tasks_completed": 0,
            "tasks_failed": 0,
        },
    )
    _write_json(
        state / "ginko" / "agents" / "primary-worker" / "identity.json",
        {
            "name": "primary-worker",
            "model": "legacy-shadow",
            "tasks_completed": 99,
            "tasks_failed": 0,
        },
    )

    rows = census.build_readiness_rows(
        repo_root=repo,
        state_root=state,
        agora_root=tmp_path / "missing-agora",
    )

    assert _row(rows, "primary-worker").identity_path == str(
        state / "agents" / "primary-worker" / "identity.json"
    )
    assert len([row for row in rows if row.name == "primary-worker"]) == 1
    assert _row(rows, "legacy-worker").identity_path == str(
        state / "ginko" / "agents" / "legacy-worker" / "identity.json"
    )


def test_l4_requires_recent_success_even_when_other_evidence_is_true() -> None:
    row = census._row(
        candidate_kind="registered_worker",
        name="synthetic",
        current_tier="L3",
        registered_identity=True,
        passport_present=True,
        wake_claim_present=True,
        runtime_session_present=True,
        delegation_run_present=True,
        context_bundle_present=True,
        routing_decision_present=True,
        memory_receipts_present=True,
        artifact_present=True,
        outcome_present=True,
        current_process_present=True,
    )

    assert row.count_as_l4 is False
    assert row.next_required_action == "emit recent successful Outcome or ExternalOutcome"


def test_runtime_evidence_must_belong_to_one_live_chain(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    db_path = _runtime_db(state)
    _insert_complete_chain(
        db_path,
        include_artifact=False,
        include_outcome=False,
        suffix="context-side",
    )
    _insert_complete_chain(
        db_path,
        include_context=False,
        include_route=False,
        include_memory=False,
        suffix="outcome-side",
    )

    probe = census.RuntimeProbe(db_path)
    try:
        flags, _, _, _ = census._probe_agent_runtime("agent", probe)
    finally:
        probe.close()

    assert flags["wake_claim_present"] is True
    assert flags["delegation_run_present"] is True
    assert not (
        flags["context_bundle_present"]
        and flags["routing_decision_present"]
        and flags["memory_receipts_present"]
        and flags["artifact_present"]
        and flags["outcome_present"]
        and flags["recent_success_present"]
    )


def test_runtime_probe_prefers_newest_complete_chain_on_tie(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    db_path = _runtime_db(state)
    base = datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc)
    _insert_complete_chain(db_path, suffix="old", at=base)
    _insert_complete_chain(db_path, suffix="new", at=base + timedelta(minutes=1))

    probe = census.RuntimeProbe(db_path)
    try:
        flags, evidence, _, success_at = census._probe_agent_runtime(
            "agent",
            probe,
            now=base + timedelta(minutes=2),
        )
    finally:
        probe.close()

    assert flags["recent_success_present"] is True
    assert success_at == base + timedelta(minutes=1)
    assert any("#task_claim:c-new" in item for item in evidence)


def test_complete_recent_chain_can_count_as_l4_when_identity_and_process_exist(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    db_path = _runtime_db(state)
    _insert_complete_chain(db_path)

    probe = census.RuntimeProbe(db_path)
    try:
        flags, _, _, success_at = census._probe_agent_runtime("agent", probe)
    finally:
        probe.close()
    row = census._row(
        candidate_kind="registered_worker",
        name="agent",
        current_tier="L3",
        registered_identity=True,
        passport_present=True,
        current_process_present=True,
        last_success_at=census._iso(success_at),
        **flags,
    )

    assert row.count_as_l4 is True
    assert row.next_required_action == "ready for L4 review"


def test_governed_chain_requires_execution_lease(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    db_path = _runtime_db(state)
    _insert_complete_chain(db_path, governed=True)

    probe = census.RuntimeProbe(db_path)
    try:
        flags, _, _, success_at = census._probe_agent_runtime("agent", probe)
    finally:
        probe.close()
    row = census._row(
        candidate_kind="registered_worker",
        name="agent",
        current_tier="L3",
        registered_identity=True,
        passport_present=True,
        current_process_present=True,
        last_success_at=census._iso(success_at),
        **flags,
    )

    assert row.execution_lease_required is True
    assert row.execution_lease_present is False
    assert row.count_as_l4 is False
    assert row.next_required_action == "record ExecutionLease for governed action"


def test_conductor_malformed_database_error_blocks_l4(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "home" / ".dharma"
    _write_json(
        state / "profiles" / "conductor_claude.json",
        {"name": "conductor_claude", "model": "claude-opus-4-6"},
    )
    _write_json(
        state / "agent_runs" / "conductor_claude_latest.json",
        {"errors": ["Error: Credit balance is too low"]},
    )
    _write_jsonl(
        state / "witness" / "conductor_conductor_claude.jsonl",
        [
            {
                "event": "ERROR",
                "error": "database disk image is malformed",
                "timestamp": "2026-05-20T13:14:55+00:00",
            }
        ],
    )

    rows = census.build_readiness_rows(
        repo_root=repo,
        state_root=state,
        agora_root=tmp_path / "missing-agora",
    )

    row = _row(rows, "conductor_claude")
    assert row.current_tier == "L3"
    assert row.count_as_l4 is False
    assert "database disk image is malformed" in row.blocking_errors
    assert row.next_required_action == "repair malformed conductor memory database"


def test_conductor_malformed_database_error_is_not_masked_by_newer_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "home" / ".dharma"
    _write_json(
        state / "profiles" / "conductor_codex.json",
        {"name": "conductor_codex", "model": "codex"},
    )
    _write_jsonl(
        state / "witness" / "conductor_conductor_codex.jsonl",
        [
            {
                "event": "ERROR",
                "detail": "database disk image is malformed",
                "timestamp": "2026-05-20T13:14:55+00:00",
            },
            {
                "event": "ERROR",
                "detail": "provider timeout",
                "timestamp": "2026-05-20T13:15:55+00:00",
            },
        ],
    )

    rows = census.build_readiness_rows(
        repo_root=repo,
        state_root=state,
        agora_root=tmp_path / "missing-agora",
    )

    row = _row(rows, "conductor_codex")
    assert "database disk image is malformed" in row.blocking_errors
    assert row.next_required_action == "repair malformed conductor memory database"


def test_cron_daemons_and_frameworks_never_count_as_l4(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "home" / ".dharma"
    agora = tmp_path / "dharmic-agora"
    _write_json(
        state / "cron" / "jobs.json",
        {
            "jobs": [
                {
                    "id": "job-1",
                    "name": "Shakti Executive Opportunity Board",
                    "enabled": True,
                    "last_status": "ok",
                }
            ]
        },
    )
    _write(agora / "agora" / "coordinator.py", "# framework\n")
    _write(agora / "agora" / "auth.py", "# auth\n")

    rows = census.build_readiness_rows(
        repo_root=repo,
        state_root=state,
        agora_root=agora,
    )

    false_positive_names = {
        "cron:Shakti Executive Opportunity Board",
        "dharma_swarm_orchestrate_live_daemon",
        "dharma_swarm_cron_daemon",
        "dharmic_agora_agent_frameworks",
    }
    found = {row.name: row for row in rows if row.name in false_positive_names}
    assert set(found) == false_positive_names
    for row in found.values():
        assert row.registered_identity is False
        assert row.count_as_l4 is False
        assert row.next_required_action == "exclude from cultivation: not an identity-bearing agent"


def test_write_outputs_schema_and_secret_sanitization(tmp_path: Path) -> None:
    state = tmp_path / "home" / ".dharma"
    agent_dir = state / "agents" / "leaky"
    _write_json(
        agent_dir / "identity.json",
        {
            "name": "leaky",
            "model": "test-model",
            "tasks_completed": 0,
            "tasks_failed": 1,
        },
    )
    _write_jsonl(
        agent_dir / "task_log.jsonl",
        [
            {
                "task": "failed provider call",
                "success": False,
                "timestamp": "2026-05-20T00:00:00+00:00",
                "response_preview": "provider said token=abcdef123456 and sk-abcdef1234567890",
            }
        ],
    )
    rows = census.build_readiness_rows(
        repo_root=tmp_path / "repo",
        state_root=state,
        agora_root=tmp_path / "missing-agora",
    )
    jsonl_path, report_path, schema_path = census.write_outputs(rows, tmp_path / "out")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["required"] == census.READINESS_FIELDS

    output_text = (
        jsonl_path.read_text(encoding="utf-8")
        + report_path.read_text(encoding="utf-8")
        + schema_path.read_text(encoding="utf-8")
    )
    assert "abcdef123456" not in output_text
    assert "sk-abcdef1234567890" not in output_text
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert set(census.READINESS_FIELDS) <= set(row)
        jsonschema.validate(row, schema)
