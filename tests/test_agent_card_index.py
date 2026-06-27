"""Tests for the Agent Card meishi index projection."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.a2a.agent_card_exports import (
    agent_card_jcard,
    export_agent_card,
    extended_agent_card,
    public_agent_card,
    render_agent_card_markdown,
    render_agent_card_vcard,
)
from dharma_swarm.a2a.agent_card_index import (
    build_agent_card_index,
    write_agent_card_index_reports,
)
from dharma_swarm.operator_core.identity_invariant import build_identity_invariant


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _write_semantic_commons(repo_root: Path) -> None:
    _write(
        repo_root / "docs/ontology/semantic_objects.yaml",
        """
schema_version: semantic-commons-v0
lifecycle_values: [seed, working, preferred, canonical, deprecated, forbidden]
objects:
  - id: semobj.codex_composer
    canonical_name: CodexComposer
    api_name: dharma.agent.CodexComposer
    lifecycle: working
    owner_surface: docs/agents/codex_composer/agent.seed.yaml
    authority_level: active_spec
    source_path: docs/agents/codex_composer/agent.seed.yaml
    aliases: [codex_composer, codex-composer, Codex Composer]
    forbidden_aliases: []
    supersedes: []
    superseded_by: []
    orientation_route: route.agent_cards
  - id: semobj.openclaw_integration
    canonical_name: OpenClawIntegration
    api_name: dharma.integration.OpenClawIntegration
    lifecycle: working
    owner_surface: docs/ontology/semantic_objects.yaml
    authority_level: active_spec
    source_path: docs/ontology/semantic_objects.yaml
    aliases: [openclaw, OpenClaw]
    forbidden_aliases: [opencalw]
    supersedes: []
    superseded_by: []
    orientation_route: route.agent_cards
""",
    )
    _write(
        repo_root / "docs/ontology/semantic_aliases.yaml",
        """
schema_version: semantic-aliases-v0
aliases:
  - alias: codex_composer
    canonical_id: semobj.codex_composer
    status: active
  - alias: codex-composer
    canonical_id: semobj.codex_composer
    status: active
  - alias: Codex Composer
    canonical_id: semobj.codex_composer
    status: active
  - alias: openclaw
    canonical_id: semobj.openclaw_integration
    status: active
  - alias: OpenClaw
    canonical_id: semobj.openclaw_integration
    status: active
forbidden_aliases:
  - alias: opencalw
    canonical_id: semobj.openclaw_integration
    reason: Typo-distance collision with OpenClaw.
""",
    )
    _write(
        repo_root / "docs/ontology/session_orientation.yaml",
        """
schema_version: session-orientation-v0
routes:
  - id: route.agent_cards
    layers:
      - id: L0
        source_kind: bootstrap
      - id: L1
        source_kind: routing_moc
      - id: L2
        source_kind: active_track_packet
""",
    )


def _seed_codex_composer(dharma_home: Path) -> None:
    invariant = build_identity_invariant(
        agent_uid="codex_composer",
        authority_floor="external_worker_evidence_only",
        memory_namespace="agent:codex_composer",
        trace_identity="trace:codex_composer",
        created_at="2026-06-26T00:00:00Z",
    )
    _write_json(
        dharma_home / "a2a/cards/codex_composer.json",
        {
            "name": "codex_composer",
            "description": "Composable Codex operator",
            "endpoint": "nats://127.0.0.1:4222/dharma.agent.codex_composer.inbox",
            "role": "orchestrator",
            "status": "registered",
            "provider": "openai",
            "model": "codex-5.5",
            "skills": [{"id": "code_review", "name": "code_review"}],
            "capabilities": [{"name": "code_review"}],
            "security_schemes": [],
            "signatures": [],
            "supported_interfaces": [],
            "extensions": [],
            "metadata": {
                "agent_uid": "codex_composer",
                "authority": "external_worker_evidence_only",
                "harness": "codex_cli",
                "department": "swarm",
                "squad_id": "composer",
                "team_id": "dharma_swarm",
                "canonical_transport_subject": "dharma.agent.codex_composer.inbox",
            },
        },
    )
    external = dharma_home / "external_agents/codex_composer"
    _write_json(
        external / "registration.json",
        {
            "agent_uid": "codex_composer",
            "callsign": "codex_composer",
            "display_name": "Codex Composer",
            "harness": "codex_cli",
            "model_identity": "codex-5.5",
            "department": "swarm",
            "role": "orchestrator",
            "squad_id": "composer",
            "team_id": "dharma_swarm",
            "endpoint": "local://codex",
            "authority": "external_worker_evidence_only",
            "status": "registered",
            "memory_namespace": "agent:codex_composer",
            "trace_identity": "trace:codex_composer",
            "autonomy_policy": {"requires_approval": True},
            "workspace_policy": {"repo_writes_allowed": False},
            "capabilities": ["code_review"],
            "identity_invariant": invariant,
        },
    )
    _write_json(external / "identity_invariant.json", invariant)
    _write_json(
        external / "authority/passport.json",
        {
            "agent_uid": "codex_composer",
            "status": "scaffolded_not_promoted",
            "authority": "external_worker_evidence_only",
            "allowed_capabilities": ["read"],
            "gated_capabilities": ["write"],
            "forbidden_capabilities": ["approve_pr"],
        },
    )
    _write_json(
        dharma_home / "agents/codex_composer/identity.json",
        {
            "agent_uid": "codex_composer",
            "callsign": "codex_composer",
            "display_name": "Codex Composer",
            "status": "registered_operator_candidate",
            "memory_namespace": "/tmp/memory/codex_composer",
        },
    )


def test_agent_card_index_joins_card_registration_invariant_and_semantic(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _write_semantic_commons(repo_root)
    _seed_codex_composer(dharma_home)

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)
    agent = next(item for item in index["agents"] if item["agent_uid"] == "codex_composer")

    assert index["summary"]["card_file_count"] == 1
    assert agent["display_name"] == "Codex Composer"
    assert agent["semantic"]["canonical_object_id"] == "semobj.codex_composer"
    assert agent["identity_invariant"]["valid"] is True
    assert agent["authority_passport"]["status"] == "scaffolded_not_promoted"
    assert agent["nats"]["subjects"] == ["dharma.agent.codex_composer.inbox"]
    assert agent["trust_grade"] == "verified"
    assert agent["handoff"]["public_card_ready"] is True
    assert agent["handoff"]["extended_card_ready"] is True


def test_agent_card_index_flags_forbidden_live_alias(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _write_semantic_commons(repo_root)
    _write_json(
        dharma_home / "a2a/cards/opencalw.json",
        {
            "name": "opencalw",
            "endpoint": "interop://opencalw",
            "status": "idle",
            "metadata": {},
        },
    )

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)

    assert index["summary"]["error_count"] == 1
    assert any(item["check"] == "forbidden_live_card_alias" for item in index["findings"])
    assert index["agents"][0]["trust_grade"] == "quarantine"


def test_agent_card_index_detects_duplicate_agent_uid(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _write_semantic_commons(repo_root)
    for name in ("codex-composer", "codex_composer"):
        _write_json(
            dharma_home / f"a2a/cards/{name}.json",
            {
                "name": name,
                "endpoint": "pending://manual",
                "status": "registered",
                "metadata": {"agent_uid": "codex_composer"},
            },
        )

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)

    assert index["summary"]["card_file_count"] == 2
    assert index["summary"]["error_count"] == 1
    assert any(item["check"] == "duplicate_live_card_agent_uid" for item in index["findings"])


def test_agent_card_index_reports_metadata_type_without_crashing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _write_semantic_commons(repo_root)
    _write_json(
        dharma_home / "a2a/cards/plain-card.json",
        {
            "name": "plain-card",
            "endpoint": "local://",
            "status": "idle",
            "metadata": "not-an-object",
        },
    )

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)

    assert index["summary"]["card_file_count"] == 1
    assert index["summary"]["warning_count"] >= 1
    assert any(item["check"] == "metadata_not_object" for item in index["findings"])


def test_agent_card_index_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    out_dir = tmp_path / "out"
    _write_semantic_commons(repo_root)
    _seed_codex_composer(dharma_home)

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)
    paths = write_agent_card_index_reports(index, out_dir)

    assert Path(paths["index_json"]).exists()
    assert Path(paths["findings_json"]).exists()
    markdown = Path(paths["index_markdown"]).read_text(encoding="utf-8")
    assert "Agent Card Meishi Index" in markdown
    assert "codex_composer" in markdown


def test_agent_card_exports_are_portable_and_path_scrubbed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _write_semantic_commons(repo_root)
    _seed_codex_composer(dharma_home)

    index = build_agent_card_index(repo_root=repo_root, dharma_home=dharma_home)
    agent = next(item for item in index["agents"] if item["agent_uid"] == "codex_composer")

    public = public_agent_card(agent)
    assert public["schema_version"] == "dharma.agent_card.public.v0"
    assert public["agent_uid"] == "codex_composer"
    assert "sources" not in public
    assert "findings" not in public

    extended = extended_agent_card(agent)
    extended_json = json.dumps(extended, sort_keys=True)
    assert extended["schema_version"] == "dharma.agent_card.extended.v0"
    assert extended["source_summary"]["a2a_card"] == 1
    assert "sources" not in extended
    assert str(tmp_path) not in extended_json

    markdown = render_agent_card_markdown(agent)
    assert "# Agent Card: Codex Composer" in markdown
    assert "dharma.agent_card.codex_composer.public" in markdown

    jcard = agent_card_jcard(agent)
    assert jcard[0] == "vcard"
    assert any(prop[0] == "x-agent-uid" for prop in jcard[1])

    vcard = render_agent_card_vcard(agent)
    assert vcard.startswith("BEGIN:VCARD\r\nVERSION:4.0")
    assert "X-AGENT-UID:codex_composer" in vcard

    body, media_type, extension = export_agent_card(agent, "vcf")
    assert body == vcard
    assert media_type.startswith("text/vcard")
    assert extension == "vcf"
