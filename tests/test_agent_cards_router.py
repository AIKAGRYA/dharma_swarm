"""Tests for the Agent Card meishi API router."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import agent_cards as router_mod


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _seed(repo_root: Path, dharma_home: Path) -> None:
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
    aliases: [codex_composer, codex-composer]
    forbidden_aliases: []
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
forbidden_aliases: []
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
    _write_json(
        dharma_home / "a2a/cards/codex_composer.json",
        {
            "name": "codex_composer",
            "endpoint": "local://codex",
            "role": "orchestrator",
            "status": "registered",
            "capabilities": [{"name": "code_review"}],
            "metadata": {"agent_uid": "codex_composer"},
        },
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


def test_list_agent_cards(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed(repo_root, dharma_home)
    monkeypatch.setenv("DHARMA_HOME", str(dharma_home))
    monkeypatch.setattr(router_mod, "REPO_ROOT", repo_root)

    resp = _client().get("/api/agent-cards")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["summary"]["card_file_count"] == 1
    assert payload["agents"][0]["agent_uid"] == "codex_composer"


def test_get_public_agent_card_by_hyphen_alias(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed(repo_root, dharma_home)
    monkeypatch.setenv("DHARMA_HOME", str(dharma_home))
    monkeypatch.setattr(router_mod, "REPO_ROOT", repo_root)

    resp = _client().get("/api/agent-cards/codex-composer/public")

    assert resp.status_code == 200
    card = resp.json()["data"]
    assert card["schema_version"] == "dharma.agent_card.public.v0"
    assert card["agent_uid"] == "codex_composer"
    assert card["capabilities"] == ["code_review"]
    assert "sources" not in card


def test_export_agent_card_markdown_and_vcard(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed(repo_root, dharma_home)
    monkeypatch.setenv("DHARMA_HOME", str(dharma_home))
    monkeypatch.setattr(router_mod, "REPO_ROOT", repo_root)

    markdown_resp = _client().get("/api/agent-cards/codex-composer/exports/markdown")
    assert markdown_resp.status_code == 200
    assert markdown_resp.headers["content-type"].startswith("text/markdown")
    assert "# Agent Card:" in markdown_resp.text
    assert "codex_composer" in markdown_resp.text

    vcard_resp = _client().get("/api/agent-cards/codex-composer/exports/vcard")
    assert vcard_resp.status_code == 200
    assert vcard_resp.headers["content-type"].startswith("text/vcard")
    assert "BEGIN:VCARD" in vcard_resp.text
    assert "X-AGENT-UID:codex_composer" in vcard_resp.text


def test_export_agent_card_extended_json_is_path_scrubbed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed(repo_root, dharma_home)
    monkeypatch.setenv("DHARMA_HOME", str(dharma_home))
    monkeypatch.setattr(router_mod, "REPO_ROOT", repo_root)

    resp = _client().get("/api/agent-cards/codex-composer/exports/extended-json")

    assert resp.status_code == 200
    card = resp.json()
    assert card["schema_version"] == "dharma.agent_card.extended.v0"
    assert "sources" not in card
    assert str(tmp_path) not in resp.text


def test_export_agent_card_rejects_unknown_format(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed(repo_root, dharma_home)
    monkeypatch.setenv("DHARMA_HOME", str(dharma_home))
    monkeypatch.setattr(router_mod, "REPO_ROOT", repo_root)

    resp = _client().get("/api/agent-cards/codex-composer/exports/pdf")

    assert resp.status_code == 400
    assert "Unsupported Agent Card export format" in resp.text
