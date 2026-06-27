"""Tests for the read-only agent admission verifier."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/governance/agent_admission.py"

spec = importlib.util.spec_from_file_location("agent_admission", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["agent_admission"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repo_semantic_commons_report_has_no_errors() -> None:
    report = mod.validate_semantic_commons(REPO_ROOT)

    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["object_count"] >= 12
    assert report["orientation_route_count"] >= 1


def test_existing_candidate_passes_with_name_drift_receipt(tmp_path: Path) -> None:
    report = mod.validate_semantic_commons(REPO_ROOT)
    receipt = tmp_path / "name_drift.json"
    receipt.write_text(json.dumps({"hit_count": 0}), encoding="utf-8")

    findings = mod.validate_candidate(
        report,
        agent_uid="palantir_pilot",
        canonical_id="semobj.palantir_pilot",
        orientation_route="route.semantic_commons_campaign",
        name_drift_receipt=receipt,
    )

    assert findings == []


def test_candidate_requires_registered_alias(tmp_path: Path) -> None:
    report = mod.validate_semantic_commons(REPO_ROOT)
    receipt = tmp_path / "name_drift.json"
    receipt.write_text(json.dumps({"hit_count": 0}), encoding="utf-8")

    findings = mod.validate_candidate(
        report,
        agent_uid="unregistered_agent",
        canonical_id="semobj.palantir_pilot",
        orientation_route="route.semantic_commons_campaign",
        name_drift_receipt=receipt,
    )

    assert any(item.check == "candidate_alias_registered" for item in findings)


def test_candidate_requires_name_drift_receipt() -> None:
    report = mod.validate_semantic_commons(REPO_ROOT)

    findings = mod.validate_candidate(
        report,
        agent_uid="palantir_pilot",
        canonical_id="semobj.palantir_pilot",
        orientation_route="route.semantic_commons_campaign",
        name_drift_receipt=None,
    )

    assert any(item.check == "candidate_name_drift_receipt" for item in findings)


def test_duplicate_active_agent_uid_fails(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/ontology/semantic_objects.yaml",
        """
schema_version: semantic-commons-v0
lifecycle_values: [seed, working, preferred, canonical, deprecated, forbidden]
objects:
  - id: semobj.agent_a
    canonical_name: AgentA
    api_name: dharma.agent.AgentA
    lifecycle: working
    owner_surface: docs/agents/a/agent.seed.yaml
    authority_level: active_spec
    source_path: docs/agents/a/agent.seed.yaml
    aliases: [agent-a, agent_a]
    forbidden_aliases: []
    supersedes: []
    superseded_by: []
    orientation_route: route.test
""",
    )
    _write(
        tmp_path / "docs/ontology/semantic_aliases.yaml",
        """
schema_version: semantic-aliases-v0
aliases:
  - alias: agent-a
    canonical_id: semobj.agent_a
    status: active
  - alias: agent_a
    canonical_id: semobj.agent_a
    status: active
forbidden_aliases: []
""",
    )
    _write(
        tmp_path / "docs/ontology/session_orientation.yaml",
        """
schema_version: session-orientation-v0
routes:
  - id: route.test
    layers:
      - id: L0
        source_kind: bootstrap
      - id: L1
        source_kind: routing_moc
      - id: L2
        source_kind: active_track_packet
""",
    )
    _write(tmp_path / "docs/agents/a/agent.seed.yaml", "agent_uid: duplicate_agent\n")
    _write(tmp_path / "docs/agents/b/agent.seed.yaml", "agent_uid: duplicate_agent\n")

    report = mod.validate_semantic_commons(tmp_path)

    assert any(item["check"] == "duplicate_active_agent_uid" for item in report["errors"])


def test_same_target_forbidden_typo_alias_is_clean_regression_guard(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "docs/ontology/semantic_objects.yaml",
        """
schema_version: semantic-commons-v0
lifecycle_values: [seed, working, preferred, canonical, deprecated, forbidden]
objects:
  - id: semobj.openclaw_integration
    canonical_name: OpenClaw
    api_name: dharma.integration.OpenClawIntegration
    lifecycle: working
    owner_surface: docs/ontology/semantic_objects.yaml
    authority_level: active_spec
    source_path: docs/ontology/semantic_objects.yaml
    object_kind: integration
    public_ontology: true
    aliases: [OpenClaw, openclaw]
    forbidden_aliases: []
    supersedes: []
    superseded_by: []
    orientation_route: route.test
""",
    )
    _write(
        tmp_path / "docs/ontology/semantic_aliases.yaml",
        """
schema_version: semantic-aliases-v0
aliases:
  - alias: OpenClaw
    canonical_id: semobj.openclaw_integration
    status: active
  - alias: openclaw
    canonical_id: semobj.openclaw_integration
    status: active
forbidden_aliases:
  - alias: opencalw
    canonical_id: semobj.openclaw_integration
    reason: Typo-distance collision with OpenClaw.
""",
    )
    _write(
        tmp_path / "docs/ontology/session_orientation.yaml",
        """
schema_version: session-orientation-v0
routes:
  - id: route.test
    layers:
      - id: L0
        source_kind: bootstrap
      - id: L1
        source_kind: routing_moc
      - id: L2
        source_kind: active_track_packet
""",
    )

    report = mod.validate_semantic_commons(tmp_path)

    assert report["errors"] == []
    assert report["warnings"] == []


def test_cross_target_forbidden_typo_alias_still_warns(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs/ontology/semantic_objects.yaml",
        """
schema_version: semantic-commons-v0
lifecycle_values: [seed, working, preferred, canonical, deprecated, forbidden]
objects:
  - id: semobj.openclaw_integration
    canonical_name: OpenClaw
    api_name: dharma.integration.OpenClawIntegration
    lifecycle: working
    owner_surface: docs/ontology/semantic_objects.yaml
    authority_level: active_spec
    source_path: docs/ontology/semantic_objects.yaml
    object_kind: integration
    public_ontology: true
    aliases: [OpenClaw, openclaw]
    forbidden_aliases: []
    supersedes: []
    superseded_by: []
    orientation_route: route.test
  - id: semobj.other_integration
    canonical_name: OtherIntegration
    api_name: dharma.integration.OtherIntegration
    lifecycle: working
    owner_surface: docs/ontology/semantic_objects.yaml
    authority_level: active_spec
    source_path: docs/ontology/semantic_objects.yaml
    object_kind: integration
    public_ontology: true
    aliases: [OtherIntegration, other-integration, other_integration]
    forbidden_aliases: []
    supersedes: []
    superseded_by: []
    orientation_route: route.test
""",
    )
    _write(
        tmp_path / "docs/ontology/semantic_aliases.yaml",
        """
schema_version: semantic-aliases-v0
aliases:
  - alias: OpenClaw
    canonical_id: semobj.openclaw_integration
    status: active
  - alias: openclaw
    canonical_id: semobj.openclaw_integration
    status: active
  - alias: OtherIntegration
    canonical_id: semobj.other_integration
    status: active
  - alias: other-integration
    canonical_id: semobj.other_integration
    status: active
  - alias: other_integration
    canonical_id: semobj.other_integration
    status: active
forbidden_aliases:
  - alias: opencalw
    canonical_id: semobj.other_integration
    reason: Confusable with the OpenClaw integration name.
""",
    )
    _write(
        tmp_path / "docs/ontology/session_orientation.yaml",
        """
schema_version: session-orientation-v0
routes:
  - id: route.test
    layers:
      - id: L0
        source_kind: bootstrap
      - id: L1
        source_kind: routing_moc
      - id: L2
        source_kind: active_track_packet
""",
    )

    report = mod.validate_semantic_commons(tmp_path)

    assert report["errors"] == []
    assert any(item["check"] == "typo_distance_collision" for item in report["warnings"])
