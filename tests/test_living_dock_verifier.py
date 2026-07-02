from __future__ import annotations

import pytest

from dharma_swarm.living_dock_verifier import verify_living_dock


def _complete_home(root, uid="codex_composer"):
    home = root / "agents" / uid
    for relative in [
        "identity.json",
        "living_agent.json",
        "service_heartbeats.jsonl",
        "transport_heartbeats.jsonl",
        "wake_ledger.jsonl",
        "dialogue/operator_sessions.jsonl",
        "dialogue/relationship_memory.jsonl",
    ]:
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "", encoding="utf-8")
    for relative in [
        "dialogue/conversation_receipts",
        "sanctum/codex",
        "sanctum/vault",
        "sanctum/dojo",
        "sanctum/ingest_gate",
        "sanctum/tools",
        "sanctum/receipts",
    ]:
        (home / relative).mkdir(parents=True, exist_ok=True)
    return home


def test_complete_canonical_shape_passes_with_dialogue_and_sanctum_required(tmp_path):
    _complete_home(tmp_path)

    report = verify_living_dock(
        "codex_composer",
        dharma_home=tmp_path,
        require_dialogue=True,
        require_sanctum=True,
    )

    assert report.status == "pass"
    assert report.living_dock_path.endswith("/agents/codex_composer")


def test_missing_identity_or_living_agent_fails(tmp_path):
    home = tmp_path / "agents" / "codex_composer"
    home.mkdir(parents=True)
    (home / "identity.json").write_text("{}\n", encoding="utf-8")

    report = verify_living_dock("codex_composer", dharma_home=tmp_path)

    assert report.status == "fail"
    assert any(finding.code == "path_missing" and "living_agent" in finding.path for finding in report.findings)


def test_missing_dialogue_fails_when_required(tmp_path):
    home = tmp_path / "agents" / "codex_composer"
    home.mkdir(parents=True)
    (home / "identity.json").write_text("{}\n", encoding="utf-8")
    (home / "living_agent.json").write_text("{}\n", encoding="utf-8")

    report = verify_living_dock("codex_composer", dharma_home=tmp_path, require_dialogue=True)

    assert report.status == "fail"
    assert any("dialogue" in finding.path for finding in report.findings if finding.severity == "fail")


def test_external_agent_mirror_allowed_when_canonical_exists(tmp_path):
    _complete_home(tmp_path, uid="hermes_m5")
    (tmp_path / "external_agents" / "hermes_m5").mkdir(parents=True)

    report = verify_living_dock("hermes_m5", dharma_home=tmp_path)

    assert report.status in {"pass", "warn"}
    assert report.legacy_mirrors == [str(tmp_path / "external_agents" / "hermes_m5")]
    assert any(finding.code == "external_agent_mirror" for finding in report.findings)


def test_ginko_legacy_only_fails(tmp_path):
    (tmp_path / "ginko" / "agents" / "legacy_agent").mkdir(parents=True)

    report = verify_living_dock("legacy_agent", dharma_home=tmp_path)

    assert report.status == "fail"
    assert any(finding.code == "ginko_legacy_agent" for finding in report.findings)


def test_missing_agent_check_is_read_only(tmp_path):
    report = verify_living_dock("missing_agent", dharma_home=tmp_path)

    assert report.status == "fail"
    assert not (tmp_path / "agents").exists()


def test_invalid_uid_rejected(tmp_path):
    with pytest.raises(ValueError):
        verify_living_dock("../bad", dharma_home=tmp_path)
