from dharma_swarm.forge_lab.freeform_explore import (
    CANONICAL_PROMOTION_REQUIREMENTS,
    MEMBRANE_REQUIREMENTS,
    EvolutionPhase,
    FreeformExploreEnvelope,
    RequirementLevel,
    canonical_packet_required,
    explore_law_summary,
    positive_lift_claim_allowed,
    requirement_for,
    validate_freeform_explore_envelope,
)


def _safe_membrane():
    return {name: True for name in MEMBRANE_REQUIREMENTS}


def test_explore_requires_membrane_but_not_canonical_packet() -> None:
    assert canonical_packet_required(EvolutionPhase.EXPLORE) is False
    assert positive_lift_claim_allowed(EvolutionPhase.EXPLORE) is False

    for requirement in MEMBRANE_REQUIREMENTS:
        assert requirement_for(EvolutionPhase.EXPLORE, requirement) is RequirementLevel.REQUIRED

    for requirement in CANONICAL_PROMOTION_REQUIREMENTS:
        assert requirement_for(EvolutionPhase.EXPLORE, requirement) is RequirementLevel.OPTIONAL


def test_confirm_and_promote_are_stricter_than_explore() -> None:
    assert canonical_packet_required(EvolutionPhase.CONFIRM) is True
    assert canonical_packet_required(EvolutionPhase.PROMOTE) is True
    assert positive_lift_claim_allowed(EvolutionPhase.CONFIRM) is True
    assert positive_lift_claim_allowed(EvolutionPhase.PROMOTE) is True
    assert requirement_for(EvolutionPhase.PROMOTE, "signed_promotion_receipt") is RequirementLevel.REQUIRED


def test_freeform_envelope_accepts_messy_artifacts_when_membrane_safe() -> None:
    envelope = FreeformExploreEnvelope(
        candidate_id="cand_weird_stepstone",
        parent_id="cand_parent",
        experiment_id="exp_freeform",
        category="agent_evolution",
        raw_output="rambling model output with a half-formed idea",
        notes="ugly but benchmarkable; preserve it as a stepping stone",
        artifacts={
            "scratch.diff": "not necessarily canonical",
            "prompt_fragment.txt": "strange verifier ritual",
            "unstructured": {"anything": ["can", "be", "kept"]},
        },
        membrane=_safe_membrane(),
    )

    assert validate_freeform_explore_envelope(envelope) == ()
    assert envelope.is_membrane_safe() is True


def test_freeform_envelope_reports_missing_membrane_without_requiring_schema() -> None:
    membrane = _safe_membrane()
    membrane["no_secret_wallet_or_prod_access"] = False
    envelope = FreeformExploreEnvelope(
        candidate_id="cand_missing_membrane",
        parent_id=None,
        experiment_id="exp_freeform",
        category="swarm_evolution",
        artifacts={"weird_topology.json": {"roles": ["poet", "critic", "builder"]}},
        membrane=membrane,
    )

    issues = validate_freeform_explore_envelope(envelope)
    assert "missing_membrane:no_secret_wallet_or_prod_access" in issues
    assert "missing_canonical_candidate_schema" not in issues
    assert "missing_complete_canonical_packet" not in issues


def test_unknown_exploratory_artifact_requirements_are_optional() -> None:
    assert requirement_for("explore", "new_weird_mutation_format") is RequirementLevel.OPTIONAL
    assert "Govern the membrane" in explore_law_summary()
