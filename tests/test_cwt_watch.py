from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.operator_core.identity_invariant import build_identity_invariant


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "cwt_watch.py"
    spec = importlib.util.spec_from_file_location("cwt_watch", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cwt_collect"] = module
    spec.loader.exec_module(module)
    return module


def _load_collect_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "cwt_collect.py"
    spec = importlib.util.spec_from_file_location("cwt_collect", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_report_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "cwt_report.py"
    spec = importlib.util.spec_from_file_location("cwt_report", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cwt_watch_emits_events_incidents_aotams_and_reputation(tmp_path):
    module = _load_module()
    state_root = tmp_path / ".dharma"
    (state_root / "external_agents" / "demo_agent" / "watch").mkdir(parents=True)

    event = module.append_watch_event(
        state_root=state_root,
        agent_uid="demo_agent",
        event_type="task_claimed",
        status="ok",
        summary="claimed packet",
        trace_id="trace:demo",
    )
    assert event["schema_version"] == "control_watch_tower_watch_event.v1"
    assert (state_root / "control_watch_tower" / "watch_events.jsonl").exists()
    assert (state_root / "external_agents" / "demo_agent" / "watch" / "events.jsonl").exists()

    incident = module.append_incident(
        state_root=state_root,
        agent_uid="demo_agent",
        severity="high",
        summary="gate bypass attempt stopped",
        kind="mandatory",
    )
    assert incident["schema_version"] == "control_watch_tower_incident.v1"
    assert "incident_opened" in (state_root / "control_watch_tower" / "watch_events.jsonl").read_text()

    aotam = module.append_aotam(
        state_root=state_root,
        aotam_id="AOTAM-TEST",
        issuer="cwt-test",
        scope="demo",
        hazard="dirty worktree",
        required_agent_action="pause and report",
        affected_agents=["demo_agent"],
    )
    assert aotam["status"] == "active"
    assert "aotam_issued" in (state_root / "control_watch_tower" / "watch_events.jsonl").read_text()

    rep = module.upsert_reputation(
        state_root=state_root,
        agent_uid="demo_agent",
        overall_score=0.72,
        trust_band="evidence_only",
        dimensions={"work_capacity": 0.8},
    )
    assert rep["overall_score"] == 0.72
    con = sqlite3.connect(state_root / "state" / "runtime.db")
    try:
        row = con.execute(
            "SELECT reputation, trust_band FROM agent_reputation WHERE agent_id = ?",
            ("demo_agent",),
        ).fetchone()
    finally:
        con.close()
    assert row == (0.72, "evidence_only")


def test_cwt_watch_lost_comms_scan_uses_registered_agent_activity(tmp_path):
    module = _load_module()
    state_root = tmp_path / ".dharma"
    logs = state_root / "external_agents" / "stale_agent" / "logs"
    logs.mkdir(parents=True)
    action_log = logs / "action_log.jsonl"
    action_log.write_text("{}\n", encoding="utf-8")
    old = datetime.now(timezone.utc) - timedelta(hours=72)
    os.utime(action_log, (old.timestamp(), old.timestamp()))

    emitted = module.lost_comms_scan(state_root=state_root, max_age_hours=24)
    assert len(emitted) == 1
    assert emitted[0]["agent_uid"] == "stale_agent"
    assert emitted[0]["event_type"] == "lost_comms"
    latest = json.loads((state_root / "control_watch_tower" / "watch_events.jsonl").read_text().strip())
    assert latest["event_type"] == "lost_comms"


def test_cwt_collect_consumes_v1_watch_surfaces(tmp_path):
    watch = _load_module()
    collect = _load_collect_module()
    state_root = tmp_path / ".dharma"
    agent_root = state_root / "external_agents" / "demo_agent"
    (agent_root / "logs").mkdir(parents=True)
    (agent_root / "self_model").mkdir()
    (agent_root / "watch").mkdir()
    (agent_root / "agentops").mkdir()
    invariant = build_identity_invariant(
        agent_uid="demo_agent",
        authority_floor="external_worker_evidence_only",
        memory_namespace="agent:demo_agent",
        trace_identity="trace:demo_agent",
        created_at="2026-05-23T00:00:00+00:00",
    )
    (agent_root / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_agent",
                "callsign": "demo-agent",
                "authority": "external_worker_evidence_only",
                "identity_invariant": invariant,
            }
        ),
        encoding="utf-8",
    )
    (agent_root / "identity_invariant.json").write_text(json.dumps(invariant), encoding="utf-8")
    (agent_root / "logs" / "action_log.jsonl").write_text("{}\n{}\n{}\n", encoding="utf-8")
    (agent_root / "logs" / "wake_receipts.jsonl").write_text("{}\n", encoding="utf-8")
    (agent_root / "self_model" / "system_interpretation.md").write_text("x" * 600, encoding="utf-8")
    (agent_root / "watch" / "contract.json").write_text("{}", encoding="utf-8")
    (agent_root / "agentops" / "contract.json").write_text("{}", encoding="utf-8")
    (state_root / "agents" / "demo_agent").mkdir(parents=True)
    (state_root / "agents" / "demo_agent" / "living_agent.json").write_text(
        json.dumps({"identity_invariant": invariant}),
        encoding="utf-8",
    )
    (state_root / "a2a" / "cards").mkdir(parents=True)
    (state_root / "a2a" / "cards" / "demo-agent.json").write_text(
        json.dumps({"metadata": {"identity_invariant": invariant}}),
        encoding="utf-8",
    )

    watch.append_watch_event(
        state_root=state_root,
        agent_uid="demo_agent",
        event_type="gate_passed",
        summary="pytest gate passed",
    )
    watch.append_incident(
        state_root=state_root,
        agent_uid="demo_agent",
        severity="high",
        summary="mandatory safety incident",
        kind="mandatory",
    )
    watch.append_aotam(
        state_root=state_root,
        aotam_id="AOTAM-DEMO",
        issuer="test",
        scope="demo",
        hazard="temporary hazard",
        required_agent_action="pause",
        affected_agents=["demo_agent"],
    )
    watch.upsert_reputation(
        state_root=state_root,
        agent_uid="demo_agent",
        overall_score=0.6,
        trust_band="evidence_only",
    )
    con = sqlite3.connect(state_root / "state" / "runtime.db")
    try:
        con.execute("CREATE TABLE agent_identity (agent_id TEXT PRIMARY KEY)")
        con.execute("INSERT INTO agent_identity (agent_id) VALUES (?)", ("demo_agent",))
        con.commit()
    finally:
        con.close()

    inv = collect.discover_agents(state_root)[0]
    scorecard = collect.build_scorecard(inv, state_root)
    assert scorecard["status"] == "incident"
    assert scorecard["identity_invariant"]["valid"] is True
    assert scorecard["identity_invariant"]["present_count"] == 4
    assert not any("identity invariant" in blocker for blocker in scorecard["blockers"])
    assert not any("runtime.db agent_identity row missing" in blocker for blocker in scorecard["blockers"])
    assert len(scorecard["incidents"]) == 1
    assert len(scorecard["aotams"]) == 1
    assert "1 CWT work events" in scorecard["dimensions"]["work_capacity"]["summary"]
    assert "reputation=yes" in scorecard["dimensions"]["promotion_readiness"]["summary"]


def test_cwt_collect_rejects_cross_agent_identity_invariant(tmp_path):
    collect = _load_collect_module()
    state_root = tmp_path / ".dharma"
    agent_root = state_root / "external_agents" / "demo_agent"
    (agent_root / "logs").mkdir(parents=True)
    (agent_root / "self_model").mkdir()
    wrong_invariant = build_identity_invariant(
        agent_uid="other_agent",
        authority_floor="external_worker_evidence_only",
        memory_namespace="agent:other_agent",
        trace_identity="trace:other_agent",
        created_at="2026-05-23T00:00:00+00:00",
    )
    (agent_root / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_agent",
                "callsign": "demo-agent",
                "authority": "external_worker_evidence_only",
                "identity_invariant": wrong_invariant,
            }
        ),
        encoding="utf-8",
    )
    (agent_root / "identity_invariant.json").write_text(json.dumps(wrong_invariant), encoding="utf-8")
    (agent_root / "logs" / "action_log.jsonl").write_text("{}\n", encoding="utf-8")
    (agent_root / "self_model" / "system_interpretation.md").write_text("x" * 600, encoding="utf-8")

    inv = collect.discover_agents(state_root)[0]
    scorecard = collect.build_scorecard(inv, state_root)

    assert scorecard["identity_invariant"]["valid"] is False
    assert scorecard["identity_invariant"]["present_count"] == 2
    assert any("does not match 'demo_agent'" in blocker for blocker in scorecard["blockers"])


def test_cwt_collect_ignores_bare_external_alias_directory(tmp_path):
    collect = _load_collect_module()
    state_root = tmp_path / ".dharma"
    bare = state_root / "external_agents" / "hermes-m5"
    bare.mkdir(parents=True)
    (bare / "identity_invariant.json").write_text("{}", encoding="utf-8")
    registered = state_root / "external_agents" / "hermes_m5_bootstrap"
    registered.mkdir(parents=True)
    (registered / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "hermes_m5_bootstrap",
                "callsign": "hermes-m5",
                "authority": "external_worker_evidence_only",
            }
        ),
        encoding="utf-8",
    )

    agents = collect.discover_agents(state_root)

    assert [agent.uid for agent in agents] == ["hermes_m5_bootstrap"]


def test_cwt_collect_ignores_external_alias_with_action_log_only(tmp_path):
    collect = _load_collect_module()
    state_root = tmp_path / ".dharma"
    bare = state_root / "external_agents" / "hermes-m5"
    (bare / "logs").mkdir(parents=True)
    (bare / "identity_invariant.json").write_text("{}", encoding="utf-8")
    (bare / "logs" / "action_log.jsonl").write_text("{}\n", encoding="utf-8")
    registered = state_root / "external_agents" / "hermes_m5_bootstrap"
    registered.mkdir(parents=True)
    (registered / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "hermes_m5_bootstrap",
                "callsign": "hermes-m5",
                "authority": "external_worker_evidence_only",
            }
        ),
        encoding="utf-8",
    )

    agents = collect.discover_agents(state_root)

    assert [agent.uid for agent in agents] == ["hermes_m5_bootstrap"]


def test_cwt_report_blockers_force_fail_status(tmp_path, monkeypatch):
    report_module = _load_report_module()
    state_root = tmp_path / ".dharma"
    report_dir = tmp_path / "reports"
    scorecards = report_dir / "scorecards"
    scorecards.mkdir(parents=True)
    (scorecards / "scorecard_demo_agent.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_agent",
                "callsign": "demo-agent",
                "authority": "external_worker_evidence_only",
                "status": "registered",
                "blockers": ["runtime.db agent_identity row missing"],
                "incidents": [],
                "aotams": [],
                "identity_invariant": {"valid": True},
                "promotion_recommendation": {"recommendation": "hold"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        report_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )

    report = report_module.build_report(state_root, report_dir)

    assert report["overall_status"] == "fail"
    assert "demo_agent: runtime.db agent_identity row missing" in report["blockers"]


def test_cwt_report_recursive_control_violations_are_blockers(tmp_path, monkeypatch):
    report_module = _load_report_module()
    state_root = tmp_path / ".dharma"
    report_dir = tmp_path / "reports"
    scorecards = report_dir / "scorecards"
    scorecards.mkdir(parents=True)
    (scorecards / "scorecard_demo_agent.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_agent",
                "callsign": "demo-agent",
                "authority": "external_worker_evidence_only",
                "status": "registered",
                "blockers": [],
                "incidents": [],
                "aotams": [],
                "identity_invariant": {"valid": True},
                "promotion_recommendation": {"recommendation": "hold"},
            }
        ),
        encoding="utf-8",
    )
    queue = state_root / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "claimed-open",
                        "from": "opus",
                        "to": "hermes-m5",
                        "status": "claimed",
                        "claimed_by": "hermes-m5",
                    }
                ),
                json.dumps(
                    {
                        "id": "done-bad",
                        "from": "opus",
                        "to": "hermes-m5",
                        "status": "completed",
                        "closed_by": "hermes-m5",
                        "receipt": {
                            "schema_version": "dharma_a2a_task_receipt.v1",
                            "task_id": "done-bad",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        report_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout=""),
    )

    report = report_module.build_report(state_root, report_dir)

    assert report["overall_status"] == "fail"
    assert any("A2A claimed without receipt: claimed-open" in b for b in report["blockers"])
    assert any("A2A completed unverified: done-bad" in b for b in report["blockers"])
    assert any("A2A missing return address: claimed-open" in b for b in report["blockers"])
