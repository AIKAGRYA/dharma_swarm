from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import yaml

from dharma_swarm.cybernetics_codex import (
    AGENT_ID,
    CALLSIGN,
    _routing_adaptation_after_truth_summary,
    _served_provider_truth_summary,
    build_audit,
    build_loop_statuses,
    read_one_wire_summary,
)
from dharma_swarm.cybernetics_codex_format import format_markdown, sanitize_audit_paths
from dharma_swarm.cybernetics_codex_registration import build_external_worker_registration


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
            metadata_json text,
            receipt_json text
        );
        create table runtime_receipts (
            receipt_id text primary key,
            run_id text,
            status text,
            payload_json text,
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
                '2026-06-13T00:01:00Z',
                '{"actual_served_provider": "openai", "actual_served_model": "gpt-5"}',
                null)
        """
    )
    conn.execute(
        """
        insert into delegation_runs
        values ('run_bad', 'failed', 'dispatch_dropoff', '2026-06-13T00:02:00Z',
                '2026-06-13T00:03:00Z', '{}', null)
        """
    )
    conn.execute(
        """
        insert into delegation_runs
        values ('run_late_a2a', 'completed', null, '2026-06-13T00:04:00Z',
                '2026-06-13T00:05:00Z', '{}', null)
        """
    )
    conn.execute(
        """
        insert into runtime_receipts
        values ('rr1', 'run_ok', 'completed',
                '{"served_provider": "openai", "served_model": "gpt-5"}',
                '2026-06-13T00:01:00Z')
        """
    )
    conn.execute(
        """
        insert into runtime_receipts
        values ('rr_late', 'run_late_a2a', 'completed',
                '{"served_provider": "anthropic", "served_model": "claude-opus-4"}',
                '2026-06-13T00:05:00Z')
        """
    )
    conn.commit()
    conn.close()


def test_build_audit_marks_loop1_partial_when_dispatch_dropoff_exists(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)

    report = build_audit(repo_root=tmp_path, state_dir=state)

    loop1 = report["loop_statuses"][0]
    assert loop1["id"] == "swarm_task_loop"
    assert loop1["verdict"] == "PARTIAL"
    assert "dispatch_dropoff=1" in loop1["blocker"]
    assert "receipt_json is orchestrator-surface only" in loop1["blocker"]


def test_build_audit_marks_loop1_harness_proven_when_bounded_replay_is_green(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)
    report_path = (
        tmp_path
        / "reports"
        / "loop_closure"
        / "cybernetics_codex"
        / "2026-06-18_loop1_bounded_spine_dispatch.json"
    )
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "provider": "ollama",
                "model": "llama3.2:latest",
                "spine_dispatch": "1",
                "read_only_boot": "1",
                "ollama_force_local": "1",
                "tasks_requested": 3,
                "tasks_completed": 3,
                "tasks_failed": 0,
                "dispatch_dropoffs": 0,
                "tick_errors": [],
                "evidence_receipts": {"r1": "ok", "r2": "ok", "r3": "ok"},
                "served_provider_truth": {
                    "completed_runs_with_truth": 3,
                    "delegation_receipts_with_truth": 3,
                    "sample": {
                        "source": "receipt_json",
                        "served_provider": "ollama",
                        "served_model": "llama3.2:latest",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_audit(repo_root=tmp_path, state_dir=state)

    loop1 = report["loop_statuses"][0]
    assert loop1["verdict"] == "HARNESS_PROVEN"
    assert "bounded replay proves" in loop1["blocker"]
    assert "not CLOSED_LIVE" in loop1["blocker"]
    assert "bounded_replays.loop1" in loop1["evidence"]
    assert report["bounded_replays"]["loop1"]["closed"] is True
    assert report["bounded_replays"]["loop1"]["harness_proven"] is True
    assert report["bounded_replays"]["loop1"]["closed_live"] is False
    assert report["bounded_replays"]["loop1"]["completed_runs_with_truth"] == 3
    assert loop1["live_owner_surface_criterion"].startswith("runtime.delegation_runs")


def test_loop1_accepts_a2a_runtime_receipt_truth_without_receipt_json(tmp_path):
    state = tmp_path / ".dharma"
    db = state / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    _seed_runtime_db(db)

    report = build_audit(
        repo_root=tmp_path,
        state_dir=state,
        since="2026-06-13T00:03:30Z",
    )

    loop1 = report["loop_statuses"][0]
    assert loop1["id"] == "swarm_task_loop"
    assert loop1["verdict"] == "NEEDS_ADVERSARIAL_REVIEW"
    assert "served provider/model truth exists" in loop1["blocker"]
    assert report["runtime"]["receipt_json"]["rows_with_receipt_json"] == 0
    assert report["runtime"]["receipt_json"]["a2a_empty_is_success"] is True
    truth = report["runtime"]["provider_truth"]
    assert truth["runtime_receipts"]["rows_with_served_provider_model"] == 1
    assert truth["runtime_receipts"]["completed_rows_with_served_provider_model"] == 1
    assert truth["runtime_receipts"]["sample"]["served_provider"] == "anthropic"


def test_loop1_closed_live_requires_later_correlated_routing_read():
    runtime = {
        "delegation_runs": {"total": 1, "completed": 1},
        "failure_codes": [],
        "provider_truth": {
            "delegation_runs": {"completed_with_served_provider_model": 1},
            "runtime_receipts": {"rows_with_served_provider_model": 0},
            "routing_adaptation": {
                "has_later_causal_read": False,
                "latest_served_truth": "2026-06-13T00:01:00Z",
            },
        },
    }
    bounded = {"loop1": {"harness_proven": True, "tasks_completed": 1, "tasks_requested": 1}}

    rows = {row["number"]: row for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)}
    assert rows[1]["verdict"] == "HARNESS_PROVEN"
    assert "no later correlated routing/adaptation read" in rows[1]["blocker"]

    runtime["provider_truth"]["routing_adaptation"] = {
        "has_later_causal_read": True,
        "latest_served_truth": "2026-06-13T00:01:00Z",
        "tables": {},
    }
    rows = {row["number"]: row for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)}
    assert rows[1]["verdict"] == "HARNESS_PROVEN"

    runtime["provider_truth"]["routing_adaptation"] = {
        "has_later_causal_read": True,
        "latest_served_truth": "2026-06-13T00:01:00Z",
        "tables": {
            "routing_decisions": {
                "correlated_rows_after_served_truth": 1,
            },
        },
    }
    rows = {row["number"]: row for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)}
    assert rows[1]["verdict"] == "CLOSED_LIVE"
    assert "runtime.provider_truth.routing_adaptation" in rows[1]["evidence"]


def test_loop1_closed_live_requires_completed_delegation_work():
    runtime = {
        "delegation_runs": {"total": 1, "completed": 0},
        "failure_codes": [],
        "provider_truth": {
            "delegation_runs": {"completed_with_served_provider_model": 0},
            "runtime_receipts": {"rows_with_served_provider_model": 1},
            "routing_adaptation": {
                "has_later_causal_read": True,
                "latest_served_truth": "2026-06-13T00:01:00Z",
                "tables": {
                    "routing_decisions": {
                        "correlated_rows_after_served_truth": 1,
                    },
                },
            },
        },
    }
    bounded = {"loop1": {"harness_proven": True, "tasks_completed": 1, "tasks_requested": 1}}

    rows = {
        row["number"]: row
        for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)
    }

    assert rows[1]["verdict"] == "HARNESS_PROVEN"
    assert "no completed delegation runs" in rows[1]["blocker"]


def test_loop1_closed_live_ignores_receipt_truth_from_non_completed_work():
    runtime = {
        "delegation_runs": {"total": 1, "completed": 1},
        "failure_codes": [],
        "provider_truth": {
            "delegation_runs": {"completed_with_served_provider_model": 0},
            "runtime_receipts": {
                "rows_with_served_provider_model": 1,
                "completed_rows_with_served_provider_model": 0,
            },
            "routing_adaptation": {
                "has_later_causal_read": True,
                "latest_served_truth": "2026-06-13T00:01:00Z",
                "tables": {
                    "routing_decisions": {
                        "correlated_rows_after_served_truth": 1,
                    },
                },
            },
        },
    }
    bounded = {"loop1": {"harness_proven": True, "tasks_completed": 1, "tasks_requested": 1}}

    rows = {
        row["number"]: row
        for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)
    }

    assert rows[1]["verdict"] == "HARNESS_PROVEN"
    assert "no served provider/model truth from completed work" in rows[1]["blocker"]

    runtime["provider_truth"]["runtime_receipts"][
        "completed_rows_with_served_provider_model"
    ] = 1
    rows = {
        row["number"]: row
        for row in build_loop_statuses(runtime, {}, {}, bounded_replays=bounded)
    }
    assert rows[1]["verdict"] == "CLOSED_LIVE"


def test_served_provider_truth_uses_only_completed_runs_for_causal_routing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table delegation_runs (
            run_id text primary key,
            status text,
            started_at text,
            completed_at text,
            metadata_json text,
            receipt_json text
        );
        create table runtime_receipts (
            receipt_id text primary key,
            run_id text,
            status text,
            payload_json text,
            created_at text
        );
        create table routing_decisions (
            id text primary key,
            run_id text,
            created_at text
        );
        insert into delegation_runs
        values ('run_ok', 'completed', '2026-06-13T00:00:00Z',
                '2026-06-13T00:01:00Z', '{}', null);
        insert into delegation_runs
        values ('run_failed', 'failed', '2026-06-13T00:02:00Z',
                '2026-06-13T00:03:00Z', '{}', null);
        insert into runtime_receipts
        values ('rr_failed', 'run_failed', 'failed',
                '{"served_provider": "anthropic", "served_model": "claude-opus-4"}',
                '2026-06-13T00:03:00Z');
        insert into routing_decisions
        values ('route_failed', 'run_failed', '2026-06-13T00:04:00Z');
        """
    )

    summary = _served_provider_truth_summary(conn)

    assert summary["runtime_receipts"]["rows_with_served_provider_model"] == 1
    assert summary["runtime_receipts"]["completed_rows_with_served_provider_model"] == 0
    assert summary["routing_adaptation"]["has_later_causal_read"] is False


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


def test_one_wire_audit_uses_archive_quorum_floors(tmp_path):
    state = tmp_path / ".dharma"
    guard = state / "forge_measurement_guardian" / "cycle-003-fitness-quorum-guard.json"
    guard.parent.mkdir(parents=True)
    guard.write_text(
        json.dumps(
            {
                "authority_result": {
                    "confirmed_receipt_count": 4,
                    "domain_count": 2,
                    "eligible_to_set_archive_fitness": True,
                    "fitness_authority_granted": True,
                },
                "threshold_guard": {
                    "required_confirmed_receipts": 0,
                    "observed_confirmed_receipts": 4,
                    "required_distinct_domains": 0,
                    "observed_distinct_domains": 2,
                },
            }
        ),
        encoding="utf-8",
    )

    one_wire = read_one_wire_summary(state)

    assert one_wire["required_confirmed"] == 5
    assert one_wire["required_domains"] == 3
    assert one_wire["eligible"] is False
    assert one_wire["blocker"] == "guardian quorum below threshold: N=4/5, M=2/3"


def test_routing_adaptation_chunks_large_truth_run_sets():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        create table routing_decisions (
            id text primary key,
            run_id text,
            created_at text
        );
        insert into routing_decisions
        values ('rd1', 'run_1100', '2026-06-13T00:02:00Z');
        """
    )
    truth_run_ids = {f"run_{index}" for index in range(1200)}

    summary = _routing_adaptation_after_truth_summary(
        conn,
        latest_truth="2026-06-13T00:01:00Z",
        truth_run_ids=truth_run_ids,
    )

    table = summary["tables"]["routing_decisions"]
    assert table["correlated_rows_after_served_truth"] == 1
    assert summary["has_later_causal_read"] is True


def test_routing_adaptation_counts_after_each_run_truth_timestamp():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        create table routing_decisions (
            id text primary key,
            run_id text,
            created_at text
        );
        insert into routing_decisions
        values ('rd1', 'run_a', '2026-06-13T00:02:00Z');
        """
    )

    summary = _routing_adaptation_after_truth_summary(
        conn,
        latest_truth="2026-06-13T00:05:00Z",
        truth_run_ids={"run_a", "run_b"},
        truth_timestamps_by_run_id={
            "run_a": "2026-06-13T00:01:00Z",
            "run_b": "2026-06-13T00:05:00Z",
        },
    )

    table = summary["tables"]["routing_decisions"]
    assert table["rows_after_served_truth"] == 0
    assert table["correlated_rows_after_served_truth"] == 1
    assert summary["has_later_causal_read"] is True


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
    assert report["verdict_tiers"]["HARNESS_PROVEN"]
    assert report["verdict_tiers"]["CLOSED_LIVE"]


def test_markdown_report_contains_all_13_loops(tmp_path):
    report = build_audit(repo_root=tmp_path, state_dir=tmp_path / ".dharma")
    text = format_markdown(report)

    assert "# cybernetics_codex Audit" in text
    assert text.count("| ") >= 13
    assert "loop1_harness_proven" in text
    assert "loop1_closed:" not in text
    assert "Swarm Task Loop" in text
    assert "Free Evolution Grind" in text


def test_markdown_replay_table_uses_closed_alias_for_harness_proven(tmp_path):
    report = build_audit(repo_root=tmp_path, state_dir=tmp_path / ".dharma")
    report["bounded_replays"] = {
        "loop2": {
            "closed": True,
            "closed_live": False,
            "path": str(tmp_path / "reports" / "loop2.json"),
        }
    }

    text = format_markdown(report)

    assert "| loop2 | True | False | n/a | `loop2.json` |" in text


def test_audit_output_normalizes_local_paths(tmp_path):
    report = build_audit(repo_root=tmp_path, state_dir=tmp_path / ".dharma")
    report["repo_root"] = "/Users/dhyana/dw-worktrees/g"
    report["state_dir"] = "/Users/dhyana/.dharma"
    report["runtime"]["path"] = "/Users/dhyana/.dharma/state/runtime.db"
    report["bounded_replays"]["loop1"]["path"] = (
        "/Users/dhyana/dw-worktrees/g/reports/loop_closure/cybernetics_codex/loop1.json"
    )
    report["active_track"]["owned_surfaces"] = [
        "/Users/dhyana/dw-worktrees/g/reports/loop_closure/cybernetics_codex",
        "/opt/foreign/private-surface",
    ]
    report["runtime"]["raw_status"] = (
        "heartbeat=/Users/dhyana/.dharma/a2a_bus/worker.json\n"
        "log=/var/folders/zz/random/T/worker.log\n"
        "fallback=/opt/foreign/private.log\n"
        "mailbox=nats://dharma.agent.cybernetics_codex.inbox\n"
        "docs=https://example.test/evidence/packet"
    )
    report["live_registration"]["mailbox"] = "nats://dharma.agent.cybernetics_codex.inbox"
    report["live_registration"]["evidence_url"] = "https://example.test/evidence/packet"

    output_report = sanitize_audit_paths(report)
    text = format_markdown(report)

    assert output_report["runtime"]["path"] == "$DHARMA_STATE/state/runtime.db"
    assert output_report["bounded_replays"]["loop1"]["path"] == (
        "$REPO_ROOT/reports/loop_closure/cybernetics_codex/loop1.json"
    )
    assert "$DHARMA_STATE/state/runtime.db" in text
    assert "$REPO_ROOT/reports/loop_closure/cybernetics_codex/loop1.json" in text
    assert output_report["active_track"]["owned_surfaces"] == [
        "$REPO_ROOT/reports/loop_closure/cybernetics_codex",
        "<absolute-path>",
    ]
    assert output_report["runtime"]["raw_status"] == (
        "heartbeat=$DHARMA_STATE/a2a_bus/worker.json\n"
        "log=$TMPDIR\n"
        "fallback=<absolute-path>\n"
        "mailbox=nats://dharma.agent.cybernetics_codex.inbox\n"
        "docs=https://example.test/evidence/packet"
    )
    assert (
        output_report["live_registration"]["mailbox"]
        == "nats://dharma.agent.cybernetics_codex.inbox"
    )
    assert (
        output_report["live_registration"]["evidence_url"]
        == "https://example.test/evidence/packet"
    )
    assert "/Users/dhyana" not in text


def test_committed_cybernetics_audit_artifacts_do_not_commit_machine_paths():
    repo_root = Path(__file__).resolve().parents[1]
    loop_reports = repo_root / "reports/loop_closure/cybernetics_codex"
    council_reports = repo_root / "reports/agentops/decorrelated_review_council"
    artifacts = [
        repo_root / "reports/loop_closure/cybernetics_codex/latest_audit.md",
        repo_root / "reports/loop_closure/cybernetics_codex/latest_audit.json",
        *loop_reports.glob("2026-07-01_loop*.json"),
        *council_reports.glob("20260702T*.json"),
    ]
    for artifact in artifacts:
        text = artifact.read_text(encoding="utf-8")
        assert "/Users/dhyana" not in text
        assert "/private/tmp" not in text
        assert "/var/folders" not in text


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
        == "dharma.agent.cybernetics_codex.inbox"
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
    assert "cybernetics_codex_loop_verdict_map_matches_claim_boundary" in criteria
    assert "cybernetics_codex_live_owner_criteria_declared" in criteria
    assert "cybernetics_codex_closed_live_count_zero" in criteria
    assert "cybernetics_codex_harness_proven_count_11" in criteria
    assert not any(criterion.endswith("_closed_live") for criterion in criteria)


def test_agent_seed_and_context_desk_are_registered():
    seed = yaml.safe_load(
        open("docs/agents/cybernetics_codex/agent.seed.yaml", encoding="utf-8")
    )

    assert seed["agent_uid"] == AGENT_ID
    assert seed["callsign"] == CALLSIGN
    assert seed["authority"] == "external_worker_evidence_only"
    assert seed["identity_docs"]["soul"] == "SOUL.md"
    assert seed["identity_docs"]["context_engineering"] == "CONTEXT_ENGINEERING.md"
    assert seed["mailbox"]["route"] == "agent-inbox"
    assert seed["mailbox"]["nats_subject"] == "dharma.agent.cybernetics_codex.inbox"
    assert seed["mailbox"]["runtime_status"] == "declared_not_started"


def test_build_audit_reports_seed_and_missing_live_registration(tmp_path):
    report = build_audit(repo_root=".", state_dir=tmp_path / ".dharma")

    assert report["seed_registration"]["registered"] is True
    assert report["seed_registration"]["agent_uid"] == AGENT_ID
    assert report["live_registration"]["registered"] is False
    assert "missing registration surfaces" in report["live_registration"]["blocker"]


def test_build_audit_flags_stale_live_registration_route(tmp_path):
    state = tmp_path / ".dharma"
    external = state / "external_agents" / AGENT_ID / "registration.json"
    dock = state / "agents" / AGENT_ID / "living_agent.json"
    card = state / "a2a" / "cards" / f"{CALLSIGN}.json"
    receipt = state / "agents" / AGENT_ID / "last_receipt.json"
    for path in (external, dock, card, receipt):
        path.parent.mkdir(parents=True, exist_ok=True)
    external.write_text(
        json.dumps(
            {
                "authority": "external_worker_evidence_only",
                "mailbox": "nats://dharma.a2a.cybernetics-codex",
                "metadata": {"nats_subject": "dharma.a2a.cybernetics-codex"},
            }
        ),
        encoding="utf-8",
    )
    dock.write_text(json.dumps({"status": "starting"}), encoding="utf-8")
    card.write_text(json.dumps({"endpoint": "pending://manual"}), encoding="utf-8")
    receipt.write_text(json.dumps({"receipt_id": "r1"}), encoding="utf-8")

    report = build_audit(repo_root=".", state_dir=state)

    assert report["live_registration"]["registered"] is False
    assert "route drift" in report["live_registration"]["blocker"]


def test_external_worker_registration_builder_is_default_deny(tmp_path):
    worker = build_external_worker_registration(dharma_home=tmp_path / ".dharma")

    assert worker.agent_uid == AGENT_ID
    assert worker.callsign == CALLSIGN
    assert worker.authority.value == "external_worker_evidence_only"
    assert worker.endpoint == "pending://manual"
    assert worker.mailbox == "nats://dharma.agent.cybernetics_codex.inbox"
    assert worker.metadata["a2a_route"] == "agent-inbox"
    assert worker.autonomy_policy.requires_approval is True
    assert worker.autonomy_policy.can_write_source is False
    assert worker.workspace_policy.repo_writes_allowed is False
    assert worker.metadata["nats_runtime_status"] == "declared_not_started"



def test_loop1_bounded_replay_stays_harness_proven_without_runtime_db():
    bounded = {
        "loop1": {
            "harness_proven": True,
            "closed": True,
            "tasks_completed": 3,
            "tasks_requested": 3,
            "dispatch_dropoffs": 0,
            "evidence_receipts_ok": 3,
            "completed_runs_with_truth": 3,
        }
    }
    rows = {
        row["number"]: row
        for row in build_loop_statuses({}, {}, {}, bounded_replays=bounded)
    }
    loop1 = rows[1]
    assert loop1["verdict"] == "HARNESS_PROVEN"
    assert "bounded_replays.loop1" in loop1["evidence"]
    assert "not CLOSED_LIVE" in loop1["blocker"]
    assert "no completed delegation runs in runtime scope" in loop1["blocker"]
    assert "no served provider/model truth from completed work" in loop1["blocker"]
    assert "no later correlated routing/adaptation read" in loop1["blocker"]
