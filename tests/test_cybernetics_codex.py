from __future__ import annotations

import json
import sqlite3

import yaml

from dharma_swarm.cybernetics_codex import (
    AGENT_ID,
    CALLSIGN,
    build_audit,
    build_external_worker_registration,
    format_markdown,
)


def _seed_runtime_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table delegation_runs (
            run_id text primary key,
            status text,
            failure_code text,
            started_at text,
            completed_at text,
            receipt_json text
        );
        create table runtime_receipts (
            receipt_id text primary key,
            created_at text
        );
        create table routing_decisions (
            id text primary key,
            created_at text
        );
        create table provider_attempts (
            id text primary key,
            created_at text
        );
        create table model_routing_outcomes (
            id text primary key,
            created_at text
        );
        create table external_outcomes (
            id text primary key,
            created_at text
        );
        """
    )
    conn.execute(
        """
        insert into delegation_runs
        values ('run_ok', 'completed', null, '2026-06-13T00:00:00Z',
                '2026-06-13T00:01:00Z', '{"ok": true}')
        """
    )
    conn.execute(
        """
        insert into delegation_runs
        values ('run_bad', 'failed', 'dispatch_dropoff', '2026-06-13T00:02:00Z',
                '2026-06-13T00:03:00Z', null)
        """
    )
    conn.execute(
        "insert into runtime_receipts values ('rr1', '2026-06-13T00:03:00Z')"
    )
    conn.commit()
    conn.close()


def test_build_audit_marks_loop1_partial_when_receipts_are_incomplete(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)

    report = build_audit(repo_root=tmp_path, state_dir=state)

    loop1 = report["loop_statuses"][0]
    assert loop1["id"] == "swarm_task_loop"
    assert loop1["verdict"] == "PARTIAL"
    assert "receipt_json coverage is 1/2" in loop1["blocker"]
    assert "dispatch_dropoff=1" in loop1["blocker"]


def test_one_wire_blocks_self_improvement_when_guardian_quorum_missing(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)

    report = build_audit(repo_root=tmp_path, state_dir=state)
    by_id = {row["id"]: row for row in report["loop_statuses"]}

    assert by_id["self_improvement"]["verdict"] == "BLOCKED"
    assert by_id["free_evolution_grind"]["verdict"] == "BLOCKED"
    assert "quorum" in by_id["self_improvement"]["blocker"]


def test_one_wire_reads_nested_guardian_threshold(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)
    guard = state / "forge_measurement_guardian" / "cycle-003-fitness-quorum-guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        json.dumps(
            {
                "authority_result": {
                    "confirmed_receipt_count": 3,
                    "domain_count": 1,
                    "eligible_to_set_archive_fitness": False,
                    "archive_fitness_changed": False,
                    "fitness_authority_granted": False,
                },
                "threshold_guard": {
                    "required_confirmed_receipts": 5,
                    "observed_confirmed_receipts": 3,
                    "required_distinct_domains": 3,
                    "observed_distinct_domains": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_audit(repo_root=tmp_path, state_dir=state)

    assert report["one_wire"]["confirmed"] == 3
    assert report["one_wire"]["domains"] == 1
    assert report["one_wire"]["blocker"] == "guardian quorum below threshold: N=3/5, M=1/3"


def test_steward_declares_forbidden_actions_and_verifier_commands(tmp_path):
    report = build_audit(repo_root=tmp_path, state_dir=tmp_path / ".dharma")

    forbidden = " ".join(report["agent"]["forbidden_actions"])
    assert "secrets" in forbidden
    assert "archive fitness" in forbidden
    assert "claim production closure" in forbidden
    assert "python3 scripts/governance/cybernetics_codex_audit.py --json" in report[
        "verifier_commands"
    ]
    assert "python3 scripts/governance/register_cybernetics_codex.py --dry-run" in report[
        "verifier_commands"
    ]


def test_markdown_report_contains_all_13_loops(tmp_path):
    report = build_audit(repo_root=tmp_path, state_dir=tmp_path / ".dharma")
    text = format_markdown(report)

    assert "# cybernetics_codex Audit" in text
    assert text.count("| ") >= 13
    assert "Swarm Task Loop" in text
    assert "Free Evolution Grind" in text


def test_manifest_registers_cybernetics_codex():
    data = yaml.safe_load(open("ACTIVE_SURFACE_MANIFEST.yaml", encoding="utf-8"))
    agents = {agent["id"]: agent for agent in data["agents"]}

    assert AGENT_ID in agents
    assert agents[AGENT_ID]["status"] == "shadow"
    assert agents[AGENT_ID]["module"] == "dharma_swarm/cybernetics_codex.py"
    assert agents[AGENT_ID]["seed"] == "docs/agents/cybernetics_codex/agent.seed.yaml"
    assert agents[AGENT_ID]["registration"]["a2a_card"].endswith(
        "/cybernetics-codex.json"
    )
    assert (
        agents[AGENT_ID]["registration"]["nats_subject"]
        == "dharma.a2a.cybernetics-codex"
    )
    assert agents[AGENT_ID]["registration"]["nats_runtime_status"] == "declared_not_started"
    assert "test_file_exists" in agents[AGENT_ID]["health_check_ids"]


def test_loop_closure_track_requires_steward_packet():
    data = yaml.safe_load(open("docs/governance/ACTIVE_TRACK.yaml", encoding="utf-8"))
    tracks = {track["id"]: track for track in data["active_tracks"]}
    criteria = {
        criterion["id"]
        for criterion in tracks["loop-closure-2026-06"]["completion_criteria"]
    }

    assert "cybernetics_codex_manifest_registered" in criteria
    assert "cybernetics_codex_seed_exists" in criteria
    assert "cybernetics_codex_soul_exists" in criteria
    assert "cybernetics_codex_context_desk_exists" in criteria
    assert "cybernetics_codex_audit_script_exists" in criteria
    assert "cybernetics_codex_registration_script_exists" in criteria


def test_agent_seed_and_context_desk_are_registered():
    seed = yaml.safe_load(
        open("docs/agents/cybernetics_codex/agent.seed.yaml", encoding="utf-8")
    )

    assert seed["agent_uid"] == AGENT_ID
    assert seed["callsign"] == CALLSIGN
    assert seed["authority"] == "external_worker_evidence_only"
    assert seed["identity_docs"]["soul"] == "SOUL.md"
    assert seed["identity_docs"]["context_engineering"] == "CONTEXT_ENGINEERING.md"
    assert seed["mailbox"]["nats_subject"] == "dharma.a2a.cybernetics-codex"
    assert seed["mailbox"]["runtime_status"] == "declared_not_started"


def test_build_audit_reports_seed_and_missing_live_registration(tmp_path):
    report = build_audit(repo_root=".", state_dir=tmp_path / ".dharma")

    assert report["seed_registration"]["registered"] is True
    assert report["seed_registration"]["agent_uid"] == AGENT_ID
    assert report["live_registration"]["registered"] is False
    assert "missing registration surfaces" in report["live_registration"]["blocker"]


def test_external_worker_registration_builder_is_default_deny(tmp_path):
    worker = build_external_worker_registration(dharma_home=tmp_path / ".dharma")

    assert worker.agent_uid == AGENT_ID
    assert worker.callsign == CALLSIGN
    assert worker.authority.value == "external_worker_evidence_only"
    assert worker.endpoint == "pending://manual"
    assert worker.mailbox == "nats://dharma.a2a.cybernetics-codex"
    assert worker.autonomy_policy.requires_approval is True
    assert worker.autonomy_policy.can_write_source is False
    assert worker.workspace_policy.repo_writes_allowed is False
    assert worker.metadata["nats_runtime_status"] == "declared_not_started"
