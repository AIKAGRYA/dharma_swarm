from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_script_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "register_external_agent.py"
    spec = importlib.util.spec_from_file_location("register_external_agent_script", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_register_external_agent_script_writes_registration_desk_surfaces(tmp_path):
    module = _load_script_module()
    home = tmp_path / ".dharma"
    manifest = tmp_path / "agent.registration.json"
    manifest.write_text(
        json.dumps(
            {
                "agent_uid": "demo_worker",
                "callsign": "demo-worker",
                "display_name": "Demo Worker",
                "harness": "demo_harness",
                "model_identity": "demo/model",
                "memory_namespace": "agent:demo_worker",
                "trace_identity": "trace:demo_worker",
                "capabilities": ["research_evidence"],
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        module.run_registration(
            SimpleNamespace(
                manifest=manifest,
                dharma_home=home,
                dry_run=False,
                no_canonical=False,
                no_ops_hooks=False,
            )
        )
    )

    sandbox = home / "external_agents" / "demo_worker"
    assert result["agent_uid"] == "demo_worker"
    assert (sandbox / "registration.json").exists()
    assert (sandbox / "identity_manifest.normalized.json").exists()
    assert (sandbox / "self_model" / "REQUIRED_FIRST_WRITE.md").exists()
    assert (sandbox / "self_model" / "system_interpretation.md").exists()
    assert (sandbox / "logs" / "wake_receipts.jsonl").exists()
    assert (sandbox / "agentops" / "contract.json").exists()
    assert (home / "agents" / "demo_worker" / "living_agent.json").exists()
    assert (home / "onboarding" / "receipts.jsonl").exists()

    action_lines = (sandbox / "logs" / "action_log.jsonl").read_text(
        encoding="utf-8"
    ).strip().splitlines()
    assert len(action_lines) == 2
    first_action = json.loads(action_lines[0])
    assert first_action["schema_version"] == "dharma_external_agent_action_log.v1"
    assert first_action["model_identity"] == "demo/model"
    assert (sandbox / "logs" / "actions.jsonl").exists()

    card = json.loads((home / "a2a" / "cards" / "demo-worker.json").read_text())
    assert card["status"] == "registered"
    assert card["metadata"]["external_worker"] is True
    assert card["metadata"]["dispatch_enabled"] is False
    assert card["metadata"]["requires_approval"] is True

    contract = json.loads((sandbox / "agentops" / "contract.json").read_text())
    assert contract["status"] == "agentops_ready_not_scheduled"

    assert (home / "kaizen" / "ops.db").exists()
    marks = (home / "stigmergy" / "marks.jsonl").read_text(encoding="utf-8")
    assert "demo-worker registered through external-agent desk" in marks


def test_show_up_registration_assigns_identity_without_manifest(tmp_path):
    module = _load_script_module()
    home = tmp_path / ".dharma"

    result = asyncio.run(
        module.run_registration(
            SimpleNamespace(
                manifest=None,
                dharma_home=home,
                dry_run=False,
                no_canonical=False,
                no_ops_hooks=False,
                agent_uid=None,
                callsign=None,
                display_name=None,
                harness="mystery_harness",
                model_identity="mystery/model",
                endpoint=None,
                mailbox=None,
                department="swarm",
                role="external_worker",
                squad_id="external",
                team_id="dharma_swarm",
                capability=["self_registration"],
                notes="",
                registration_source="registration_desk_show_up",
            )
        )
    )

    agent_uid = result["agent_uid"]
    sandbox = home / "external_agents" / agent_uid
    registration = json.loads((sandbox / "registration.json").read_text())
    assert registration["harness"] == "mystery_harness"
    assert registration["model_identity"] == "mystery/model"
    assert registration["metadata"]["show_up_mode"] is True
    assert registration["authority"] == "external_worker_evidence_only"
    assert (home / "agents" / agent_uid / "living_agent.json").exists()
    assert (sandbox / "logs" / "action_log.jsonl").exists()
    assert (sandbox / "logs" / "wake_receipts.jsonl").exists()
