"""Tests for the Agent Card governance checker CLI."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from dharma_swarm.operator_core.identity_invariant import build_identity_invariant

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/governance/agent_card_check.py"

spec = importlib.util.spec_from_file_location("agent_card_check", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["agent_card_check"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write(path, json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _seed_minimal_repo(repo_root: Path, dharma_home: Path) -> None:
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
    invariant = build_identity_invariant(
        agent_uid="codex_composer",
        authority_floor="external_worker_evidence_only",
        memory_namespace="agent:codex_composer",
        trace_identity="trace:codex_composer",
    )
    _write_json(
        dharma_home / "a2a/cards/codex_composer.json",
        {
            "name": "codex_composer",
            "endpoint": "local://codex",
            "role": "orchestrator",
            "status": "registered",
            "metadata": {"agent_uid": "codex_composer"},
        },
    )
    _write_json(
        dharma_home / "external_agents/codex_composer/registration.json",
        {
            "agent_uid": "codex_composer",
            "callsign": "codex_composer",
            "display_name": "Codex Composer",
            "harness": "codex_cli",
            "role": "orchestrator",
            "endpoint": "local://codex",
            "authority": "external_worker_evidence_only",
            "status": "registered",
            "memory_namespace": "agent:codex_composer",
            "trace_identity": "trace:codex_composer",
            "identity_invariant": invariant,
        },
    )


def test_agent_card_check_writes_reports(tmp_path: Path, capsys) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    out_dir = tmp_path / "reports"
    _seed_minimal_repo(repo_root, dharma_home)

    rc = mod.main(
        [
            "--repo-root",
            str(repo_root),
            "--dharma-home",
            str(dharma_home),
            "--out-dir",
            str(out_dir),
            "--json",
            "--strict",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["summary"]["status"] == "pass"
    assert Path(payload["paths"]["index_json"]).exists()
    assert Path(payload["paths"]["index_markdown"]).exists()


def test_agent_card_check_strict_fails_on_error(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    dharma_home = tmp_path / "dharma"
    _seed_minimal_repo(repo_root, dharma_home)
    _write_json(
        dharma_home / "a2a/cards/codex-composer-copy.json",
        {
            "name": "codex-composer-copy",
            "endpoint": "local://copy",
            "metadata": {"agent_uid": "codex_composer"},
        },
    )

    rc = mod.main(
        [
            "--repo-root",
            str(repo_root),
            "--dharma-home",
            str(dharma_home),
            "--out-dir",
            str(tmp_path / "reports"),
            "--strict",
        ]
    )

    assert rc == 1
