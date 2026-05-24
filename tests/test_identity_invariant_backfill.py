from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "backfill_identity_invariants.py"
    )
    spec = importlib.util.spec_from_file_location("backfill_identity_invariants", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["backfill_identity_invariants"] = module
    spec.loader.exec_module(module)
    return module


def test_backfill_identity_invariants_updates_existing_surfaces(tmp_path):
    module = _load_module()
    state_root = tmp_path / ".dharma"
    sandbox = state_root / "external_agents" / "demo_agent"
    sandbox.mkdir(parents=True)
    (state_root / "agents" / "demo_agent").mkdir(parents=True)
    (state_root / "a2a" / "cards").mkdir(parents=True)
    (sandbox / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": "demo_agent",
                "callsign": "demo-agent",
                "authority": "external_worker_evidence_only",
                "memory_namespace": "agent:demo_agent",
                "trace_identity": "trace:demo_agent",
            }
        ),
        encoding="utf-8",
    )
    (state_root / "agents" / "demo_agent" / "living_agent.json").write_text(
        json.dumps({"agent_uid": "demo_agent"}),
        encoding="utf-8",
    )
    (state_root / "a2a" / "cards" / "demo-agent.json").write_text(
        json.dumps({"metadata": {}}),
        encoding="utf-8",
    )

    dry_run = module.run_backfill(state_root, apply=False)
    assert dry_run["agent_count"] == 1
    assert dry_run["invalid_count"] == 1
    assert dry_run["changed_count"] == 0

    applied = module.run_backfill(state_root, apply=True)
    assert applied["invalid_count"] == 0
    assert applied["changed_count"] == 1

    invariant = json.loads((sandbox / "identity_invariant.json").read_text())
    registration = json.loads((sandbox / "registration.json").read_text())
    living = json.loads((state_root / "agents" / "demo_agent" / "living_agent.json").read_text())
    card = json.loads((state_root / "a2a" / "cards" / "demo-agent.json").read_text())
    assert invariant["schema_version"] == "dharma_identity_invariant.v1"
    assert registration["identity_invariant"]["digest"] == invariant["digest"]
    assert living["identity_invariant"]["digest"] == invariant["digest"]
    assert card["metadata"]["identity_invariant"]["digest"] == invariant["digest"]


def test_backfill_identity_invariants_keeps_existing_valid_surface(tmp_path):
    module = _load_module()
    state_root = tmp_path / ".dharma"
    sandbox = state_root / "external_agents" / "demo_agent"
    sandbox.mkdir(parents=True)
    invariant = module.build_identity_invariant(
        agent_uid="demo_agent",
        authority_floor="external_worker_evidence_only",
        memory_namespace="agent:demo_agent",
        trace_identity="trace:demo_agent",
    )
    (sandbox / "registration.json").write_text(
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
    (sandbox / "identity_invariant.json").write_text(json.dumps(invariant), encoding="utf-8")
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

    applied = module.run_backfill(state_root, apply=True)

    assert applied["invalid_count"] == 0
    assert applied["changed_count"] == 0


def test_backfill_identity_invariants_skips_bare_external_alias(tmp_path):
    module = _load_module()
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

    dry_run = module.run_backfill(state_root, apply=False)

    assert dry_run["agent_count"] == 1
    assert dry_run["agents"][0]["agent_uid"] == "hermes_m5_bootstrap"


def test_backfill_identity_invariants_skips_external_alias_with_action_log_only(tmp_path):
    module = _load_module()
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

    dry_run = module.run_backfill(state_root, apply=False)

    assert dry_run["agent_count"] == 1
    assert dry_run["agents"][0]["agent_uid"] == "hermes_m5_bootstrap"
