from __future__ import annotations

from dharma_swarm.artifact_surfaces import (
    artifact_surface_map,
    canonical_daily_brief_surface,
    validate_artifact_surface_registry,
)


def test_artifact_surface_registry_has_one_canonical_daily_brief() -> None:
    surface = canonical_daily_brief_surface()

    assert surface.surface_id == "insight_brief"
    assert surface.status == "canonical"


def test_operator_brief_is_parked() -> None:
    surfaces = artifact_surface_map()

    assert surfaces["operator_brief"].status == "parked"
    assert "insight_brief" in surfaces["operator_brief"].must_not_replace


def test_immune_mission_xray_wraps_existing_surfaces_without_replacing_them() -> None:
    surfaces = artifact_surface_map()
    immune = surfaces["immune_mission_xray"]

    assert {"repo_xray", "check_claim_redlines", "proof_artifact_to_spec"} <= set(immune.wraps)
    assert {"insight_brief", "daily_operating_brief", "repo_xray", "proof_artifact"} <= set(
        immune.must_not_replace
    )


def test_artifact_surface_registry_validates_without_overlap_violations() -> None:
    assert validate_artifact_surface_registry() == ()
