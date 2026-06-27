from __future__ import annotations

import json

from dharma_swarm.operator_core.apex_command_map import (
    build_apex_command_map,
    write_apex_command_map,
)


def _repo_fixture(repo_root):
    (repo_root / "docs" / "ontology").mkdir(parents=True)
    (repo_root / "docs" / "ontology" / "semantic_objects.yaml").write_text(
        """
objects:
  - id: semobj.codex_composer
    canonical_name: codex_composer
    aliases: [codex_composer]
  - id: semobj.sarathi
    canonical_name: sarathi
    aliases: [sarathi]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "ontology" / "semantic_aliases.yaml").write_text(
        """
aliases:
  - alias: codex_composer
    canonical_id: semobj.codex_composer
  - alias: sarathi
    canonical_id: semobj.sarathi
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "ops").mkdir(parents=True)
    (repo_root / "docs" / "ops" / "AGENT_ADMISSION.md").write_text("admission\n", encoding="utf-8")
    (repo_root / "docs" / "governance").mkdir(parents=True)
    (repo_root / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md").write_text("nats\n", encoding="utf-8")
    (repo_root / "dharma_swarm" / "operator_core").mkdir(parents=True)
    (repo_root / "dharma_swarm" / "operator_core" / "semantic_receipt.py").write_text("semantic\n", encoding="utf-8")
    (repo_root / "dharma_swarm" / "operator_core" / "runtime_truth.py").write_text("runtime\n", encoding="utf-8")
    (repo_root / "dharma_swarm").mkdir(exist_ok=True)
    (repo_root / "dharma_swarm" / "runtime_state.py").write_text("runtime\n", encoding="utf-8")
    (repo_root / "dharma_swarm" / "persistent_agent.py").write_text(
        'logger.warning("gate check failed closed")\nreturn {"gate_status": "fail_closed"}\n',
        encoding="utf-8",
    )
    (repo_root / "scripts" / "runtime").mkdir(parents=True)
    (repo_root / "scripts" / "runtime" / "a2a_inbox_bridge.py").write_text("bridge\n", encoding="utf-8")
    (repo_root / "scripts" / "runtime" / "a2a_domain_reply_worker.py").write_text("domain\n", encoding="utf-8")
    (repo_root / "scripts" / "runtime" / "model_critic_runner.py").write_text("critic\n", encoding="utf-8")
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "test_semantic_receipt.py").write_text("test\n", encoding="utf-8")
    (repo_root / "tests" / "test_model_critic_runner.py").write_text("test\n", encoding="utf-8")


def _agent_home(state_root, agent_uid):
    home = state_root / "agents" / agent_uid
    (home / "dialogue" / "conversation_receipts").mkdir(parents=True)
    (home / "sanctum" / "receipts").mkdir(parents=True)
    (home / "identity.json").write_text(json.dumps({"agent_uid": agent_uid}) + "\n", encoding="utf-8")
    (home / "living_agent.json").write_text(json.dumps({"agent_uid": agent_uid}) + "\n", encoding="utf-8")
    (home / "talk_receipts.jsonl").write_text(
        '{"schema_version":"dharma.holon_conversation_receipt.v1"}\n',
        encoding="utf-8",
    )
    return home


def test_apex_command_map_is_read_only_receipt_projection(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    state.mkdir()
    _repo_fixture(repo)
    _agent_home(state, "codex_composer")
    _agent_home(state, "sarathi")

    payload = build_apex_command_map(
        repo_root=repo,
        state_root=state,
        targets=["codex_composer", "sarathi"],
    )

    assert payload["schema_version"] == "dharma.apex_command_map.v1"
    assert payload["authority"]["mode"] == "read_only"
    assert payload["authority"]["protected_actions_allowed"] is False
    assert payload["apex"]["agent_uid"] == "sarathi"
    assert [agent["agent_uid"] for agent in payload["agents"]] == ["codex_composer", "sarathi"]
    assert payload["agents"][0]["chat_href"] == "/holon/codex_composer/chat"
    assert "d5_single_apex_control_plane_unproven" in payload["blockers"]

    out = write_apex_command_map(payload, tmp_path / "out" / "map.json")
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == "dharma.apex_command_map.v1"
