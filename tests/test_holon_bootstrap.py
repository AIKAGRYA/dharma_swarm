from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.holon_system.identity.bootstrap import (
    HolonBootstrapError,
    HolonBootstrapSpec,
    apply_holon_bootstrap,
    plan_holon_bootstrap,
)


def _spec(**overrides: object) -> HolonBootstrapSpec:
    values: dict[str, object] = {
        "name": "codex_remote",
        "role": "builder",
        "provider": "codex",
        "model": "gpt-test-codex",
        "system_prompt": "You are Codex Remote. Build carefully and leave receipts.",
        "harness": "codex",
    }
    values.update(overrides)
    return HolonBootstrapSpec(**values)  # type: ignore[arg-type]


def test_plan_is_read_only_and_does_not_embed_prompt(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    spec = _spec()

    plan = plan_holon_bootstrap(spec, dharma_home=home)

    assert plan.ready_to_apply is True
    assert plan.action == "materialize"
    assert plan.secret_material_required is False
    assert not home.exists()
    assert spec.system_prompt not in json.dumps(plan.to_dict())


@pytest.mark.asyncio
async def test_apply_materializes_all_canonical_surfaces_and_roundtrips(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    spec = _spec()

    result = await apply_holon_bootstrap(spec, dharma_home=home)

    assert result["ok"] is True
    assert result["status"] == "materialized"
    assert result["runtime_roundtrip"] is True
    assert result["secret_material_read"] is False
    identity = json.loads(
        (home / "agents" / spec.name / "identity.json").read_text(encoding="utf-8")
    )
    assert identity["provider"] == "codex"
    assert identity["authority_mode"] == "read_only_until_execution_lease"
    assert (
        home / "agents" / spec.name / "prompt_variants" / "active.txt"
    ).read_text(encoding="utf-8") == spec.system_prompt
    assert (home / "agents" / spec.name / "living_agent.json").exists()
    assert (home / "a2a" / "cards" / f"{spec.name}.json").exists()
    assert result["onboarding_receipt"]["receipt_path"]


@pytest.mark.asyncio
async def test_apply_is_idempotent_without_duplicate_onboarding_receipt(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    spec = _spec()
    first = await apply_holon_bootstrap(spec, dharma_home=home)
    receipt_files = list((home / "onboarding" / "receipts").glob("*.json"))

    second = await apply_holon_bootstrap(spec, dharma_home=home)

    assert first["status"] == "materialized"
    assert second["status"] == "already_materialized"
    assert second["onboarding_receipt"] is None
    assert list((home / "onboarding" / "receipts").glob("*.json")) == receipt_files


@pytest.mark.asyncio
async def test_apply_repairs_only_missing_identity_claims(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    identity_path = home / "agents" / "codex_remote" / "identity.json"
    identity_path.parent.mkdir(parents=True)
    identity_path.write_text(
        json.dumps({"agent_uid": "codex_remote", "role": "builder"}),
        encoding="utf-8",
    )

    result = await apply_holon_bootstrap(_spec(), dharma_home=home)

    assert result["runtime_roundtrip"] is True
    repaired = json.loads(identity_path.read_text(encoding="utf-8"))
    assert repaired["provider"] == "codex"
    assert repaired["model"] == "gpt-test-codex"


def test_conflicting_existing_identity_fails_closed(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    identity_path = home / "agents" / "codex_remote" / "identity.json"
    identity_path.parent.mkdir(parents=True)
    identity_path.write_text(
        json.dumps({"name": "codex_remote", "provider": "claude_code"}),
        encoding="utf-8",
    )

    plan = plan_holon_bootstrap(_spec(), dharma_home=home)

    assert plan.ready_to_apply is False
    assert any("provider" in conflict for conflict in plan.conflicts)


def test_unsupported_provider_is_rejected_instead_of_coerced(tmp_path: Path) -> None:
    with pytest.raises(HolonBootstrapError, match="unsupported provider"):
        plan_holon_bootstrap(_spec(provider="xai"), dharma_home=tmp_path / ".dharma")


def test_evolved_active_prompt_is_canonical_over_creation_prompt(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    agent_dir = home / "agents" / "codex_remote"
    (agent_dir / "prompt_variants").mkdir(parents=True)
    identity = {
        "name": "codex_remote",
        "agent_uid": "codex_remote",
        "callsign": "codex_remote",
        "role": "builder",
        "provider": "codex",
        "model": "gpt-test-codex",
        "system_prompt": "creation-time prompt",
        "authority_mode": "read_only_until_execution_lease",
    }
    (agent_dir / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        _spec().system_prompt,
        encoding="utf-8",
    )

    plan = plan_holon_bootstrap(_spec(), dharma_home=home)

    assert plan.ready_to_apply is True
    assert not any("system_prompt" in conflict for conflict in plan.conflicts)


def test_symlinked_canonical_identity_path_is_rejected(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "agents").mkdir(parents=True)
    (home / "agents" / "codex_remote").symlink_to(outside, target_is_directory=True)

    with pytest.raises(HolonBootstrapError, match="contains a symlink"):
        plan_holon_bootstrap(_spec(), dharma_home=home)
