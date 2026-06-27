from __future__ import annotations

import json
from datetime import UTC, datetime

from dharma_swarm.holon_persistence import append_talk_receipt
from dharma_swarm.holon_service_liveness import record_service_heartbeat
from dharma_swarm.holon_transport_liveness import record_transport_heartbeat
from dharma_swarm.verify.d_score import score_agent, score_substrate, write_d_score_report


def _repo_fixture(repo_root):
    (repo_root / "docs" / "ontology").mkdir(parents=True)
    (repo_root / "docs" / "ontology" / "semantic_objects.yaml").write_text(
        """
objects:
  - id: semobj.codex_composer
    canonical_name: CodexComposer
    aliases: [codex_composer, codex-composer]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "ontology" / "semantic_aliases.yaml").write_text(
        """
aliases:
  - alias: codex_composer
    canonical_id: semobj.codex_composer
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "docs" / "ops").mkdir(parents=True)
    (repo_root / "docs" / "ops" / "AGENT_ADMISSION.md").write_text("admission\n", encoding="utf-8")
    (repo_root / "docs" / "governance").mkdir(parents=True)
    (repo_root / "docs" / "governance" / "NATS_SUBSTRATE_MASTER_SPEC.md").write_text("nats\n", encoding="utf-8")
    (repo_root / "dharma_swarm").mkdir()
    (repo_root / "dharma_swarm" / "persistent_agent.py").write_text(
        'logger.warning("gate check failed closed")\nreturn {"gate_status": "fail_closed"}\n',
        encoding="utf-8",
    )
    (repo_root / "dharma_swarm" / "operator_core").mkdir(parents=True)
    (repo_root / "dharma_swarm" / "operator_core" / "semantic_receipt.py").write_text("semantic\n", encoding="utf-8")
    (repo_root / "dharma_swarm" / "operator_core" / "runtime_truth.py").write_text("runtime\n", encoding="utf-8")
    (repo_root / "dharma_swarm" / "runtime_state.py").write_text("runtime\n", encoding="utf-8")
    (repo_root / "scripts" / "runtime").mkdir(parents=True)
    (repo_root / "scripts" / "runtime" / "model_critic_runner.py").write_text("runner\n", encoding="utf-8")
    (repo_root / "scripts" / "runtime" / "a2a_inbox_bridge.py").write_text("bridge\n", encoding="utf-8")
    (repo_root / "scripts" / "runtime" / "a2a_domain_reply_worker.py").write_text("domain\n", encoding="utf-8")
    (repo_root / "api" / "routers").mkdir(parents=True)
    (repo_root / "api" / "routers" / "control_surface.py").write_text("control\n", encoding="utf-8")
    (repo_root / "tests").mkdir()
    (repo_root / "tests" / "test_semantic_receipt.py").write_text("test\n", encoding="utf-8")
    (repo_root / "tests" / "test_model_critic_runner.py").write_text("test\n", encoding="utf-8")


def _agent_fixture(state_root, repo_root, *, semantic=True, domain=True):
    home = state_root / "agents" / "codex_composer"
    home.mkdir(parents=True)
    for name in ["identity.json", "living_agent.json"]:
        (home / name).write_text(json.dumps({"agent_uid": "codex_composer"}) + "\n", encoding="utf-8")
    now = datetime.now(UTC)
    record_service_heartbeat(
        "codex_composer",
        agents_root=state_root / "agents",
        session_id="test-session",
        service_id="holon-l4-service",
        status="idle",
        observed_at=now,
    )
    record_transport_heartbeat(
        "codex_composer",
        agents_root=state_root / "agents",
        transport_id="a2a_inbox_bridge",
        status="reachable",
        observed_at=now,
        proof_ref={"kind": "test_bridge_heartbeat"},
    )
    (home / "dialogue").mkdir()
    (home / "dialogue" / "operator_sessions.jsonl").write_text("", encoding="utf-8")
    (home / "dialogue" / "relationship_memory.jsonl").write_text("", encoding="utf-8")
    (home / "dialogue" / "conversation_receipts").mkdir(parents=True)
    append_talk_receipt(
        "codex_composer",
        {
            "routing_mode": "holon_route",
            "you": "status",
            "reply": "codex_composer is in a read-only test dialogue.",
            "model": "test",
            "context_refs": [str(home / "identity.json"), str(home / "living_agent.json")],
            "provider_error": "",
        },
        agents_root=state_root / "agents",
    )
    for relative in ["codex", "vault", "dojo", "ingest_gate", "tools", "receipts"]:
        (home / "sanctum" / relative).mkdir(parents=True)
    (home / "artifacts").mkdir()
    (state_root / "agent_passports").mkdir(parents=True)
    (state_root / "agent_passports" / "codex_composer.json").write_text("{}\n", encoding="utf-8")
    (state_root / "a2a" / "cards").mkdir(parents=True)
    (state_root / "a2a" / "cards" / "codex_composer.json").write_text("{}\n", encoding="utf-8")
    if domain:
        (repo_root / "reports" / "a2a" / "domain_reply_receipts").mkdir(parents=True)
        (repo_root / "reports" / "a2a" / "domain_reply_receipts" / "codex_composer-domain.json").write_text(
            json.dumps(
                {
                    "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
                    "status": "DOMAIN_REPLY_PUBLISHED",
                    "agent_uid": "codex_composer",
                    "packet_id": "codex_composer-packet",
                    "reply_subject": "dharma.agent.codex_composer.inbox.reply.codex_composer-packet",
                    "domain_receipt_claim": True,
                    "semantic_reply_claim": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if semantic:
        (repo_root / "reports" / "agentops" / "semantic_receipts").mkdir(parents=True)
        (repo_root / "reports" / "agentops" / "semantic_receipts" / "codex_composer-semantic.json").write_text(
            json.dumps(
                {
                    "schema_version": "dharma.semantic_receipt.v1",
                    "agent_uid": "codex_composer",
                    "correlation_id": "codex_composer-packet",
                    "semantic_reply_claim": True,
                    "peer_model_processed_claim": True,
                    "failure_type": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )


def test_score_agent_uses_hard_gates_and_writes_reports(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo)

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert report.agent_uid == "codex_composer"
    assert report.policy_gate_status["status"] == "fail_closed"
    assert report.receipt_bundle_status["semantic_receipt"] is True
    assert "d4_semantic_receipt_missing" not in report.hard_gate_failures
    assert "d5_apex_command_identity_unproven" in report.hard_gate_failures
    assert report.verified_level == "D4"

    json_path, md_path = write_d_score_report(report, tmp_path / "out")
    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "dharma.d_score_report.v1"


def test_score_agent_missing_semantic_receipt_caps_below_d4(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo, semantic=False)

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert "d4_semantic_receipt_missing" in report.hard_gate_failures
    assert report.verified_level in {"D0", "D1", "D2", "D3"}


def test_score_agent_rejects_unhealthy_heartbeat_rows(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo)
    now = datetime.now(UTC)
    record_service_heartbeat(
        "codex_composer",
        agents_root=state / "agents",
        session_id="test-session",
        service_id="holon-l4-service",
        status="error",
        observed_at=now,
    )
    record_transport_heartbeat(
        "codex_composer",
        agents_root=state / "agents",
        transport_id="a2a_inbox_bridge",
        status="unreachable",
        observed_at=now,
    )

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert report.service_heartbeat_status["status"] == "error"
    assert report.transport_heartbeat_status["status"] == "unreachable"
    assert "d3_service_heartbeat_not_fresh" in report.hard_gate_failures
    assert "d3_transport_heartbeat_not_fresh" in report.hard_gate_failures


def test_score_agent_ignores_cross_agent_receipts(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo, semantic=False, domain=False)
    semantic_dir = repo / "reports" / "agentops" / "semantic_receipts"
    domain_dir = repo / "reports" / "a2a" / "domain_reply_receipts"
    semantic_dir.mkdir(parents=True)
    domain_dir.mkdir(parents=True)
    (semantic_dir / "other-semantic.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.semantic_receipt.v1",
                "agent_uid": "other_agent",
                "semantic_reply_claim": True,
                "peer_model_processed_claim": True,
                "failure_type": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (domain_dir / "other-domain.json").write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
                "status": "DOMAIN_REPLY_PUBLISHED",
                "agent_uid": "other_agent",
                "domain_receipt_claim": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert report.receipt_bundle_status["semantic_receipt"] is False
    assert report.receipt_bundle_status["domain_receipt"] is False
    assert "d4_semantic_receipt_missing" in report.hard_gate_failures
    assert "d4_domain_receipt_missing" in report.hard_gate_failures


def test_score_agent_rejects_dialogue_receipt_with_provider_error(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo)
    home = state / "agents" / "codex_composer"
    (home / "talk_receipts.jsonl").write_text("", encoding="utf-8")
    for receipt in (home / "dialogue" / "conversation_receipts").glob("*.json"):
        receipt.unlink()
    append_talk_receipt(
        "codex_composer",
        {
            "routing_mode": "holon_route",
            "you": "status",
            "reply": "partial response before provider error",
            "model": "test",
            "context_refs": [str(home / "identity.json")],
            "provider_error": "RuntimeError",
        },
        agents_root=state / "agents",
    )

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert report.receipt_bundle_status["dialogue_receipt"] is False
    assert "d4_dialogue_receipt_missing" in report.hard_gate_failures


def test_score_agent_rejects_contextless_dialogue_receipt(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    _agent_fixture(state, repo)
    home = state / "agents" / "codex_composer"
    (home / "talk_receipts.jsonl").write_text("", encoding="utf-8")
    for receipt in (home / "dialogue" / "conversation_receipts").glob("*.json"):
        receipt.unlink()
    append_talk_receipt(
        "codex_composer",
        {
            "routing_mode": "holon_route",
            "you": "status",
            "reply": "contextless reply should not satisfy D-score",
            "model": "test",
            "context_refs": [],
            "provider_error": "",
        },
        agents_root=state / "agents",
    )

    report = score_agent("codex_composer", repo_root=repo, state_root=state)

    assert report.receipt_bundle_status["dialogue_receipt"] is False
    assert "d4_dialogue_receipt_missing" in report.hard_gate_failures


def test_score_substrate_is_system_row(tmp_path):
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    _repo_fixture(repo)
    (state / "state").mkdir(parents=True)
    (state / "state" / "runtime.db").write_text("", encoding="utf-8")

    report = score_substrate(repo_root=repo, state_root=state)

    assert report.agent_uid == "dharma_substrate"
    assert "Substrate score is a system row" in report.notes[0]
    assert "d5_single_apex_control_plane_unproven" in report.hard_gate_failures
