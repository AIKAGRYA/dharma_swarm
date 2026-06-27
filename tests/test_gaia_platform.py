from __future__ import annotations

import json

from dharma_swarm.gaia_initiative import (
    GaiaConsentStatus,
    GaiaIndicatorCategory,
    GaiaInitiativeArea,
    GaiaInitiativeConsent,
    GaiaInitiativeIntegrityClass,
    GaiaInitiativeMeasurementMode,
    GaiaInitiativePartner,
    GaiaInitiativePartnerCredibility,
    GaiaInitiativePilotPacket,
    GaiaMonitoringIndicator,
    GaiaObservationProtocol,
    GaiaObservationSource,
    GaiaPilotMeasurementContract,
    GaiaRestorationInitiative,
)
from dharma_swarm.gaia_platform import (
    GaiaChallengeGround,
    GaiaChallengeState,
    GaiaClaimVisibility,
    GaiaMeasurementMode,
    GaiaPartnerCredibility,
    GaiaPilotIntake,
    GaiaPlatform,
    GaiaProject,
    GaiaRemediationOutcome,
    GaiaRemediationStep,
    main,
)


def _make_intake() -> GaiaPilotIntake:
    project = GaiaProject(
        project_id="bayou-lafourche-mangroves",
        name="Bayou Lafourche Mangrove Reciprocity Pilot",
        project_type="mangrove_restoration",
        country="USA",
        region="Louisiana Gulf Coast",
        hectares=420,
        carbon_potential_tons_yr=3800,
        labor_needed=48,
        funding_gap_usd=640_000,
        verification_status="verified",
        community_partner="Bayou Reciprocity Cooperative",
        description=(
            "Community-led mangrove restoration with satellite monitoring, local "
            "stewardship, and public challengeability."
        ),
        verification_channels=("satellite", "iot_sensor", "human_auditor", "community"),
    )
    return GaiaPilotIntake(
        model_id="anthropic_claude_ops",
        sponsor_name="Anthropic",
        reporting_period="2026-Q2",
        project=project,
        measurement_mode=GaiaMeasurementMode.MEASURED,
        energy_mwh=12.0,
        carbon_intensity=0.35,
        methodology_ref="method://mangrove-restoration/v1",
        measurement_ref="meter://anthropic/2026-q2/cluster-ops",
        obligation_rule="pilot_rule_v1=max(25000, co2e_tons*7500)",
        project_operator="Bayou Field Cooperative",
        integrity_class="high_integrity",
        partner_credibility=GaiaPartnerCredibility.CREDIBLE,
        due_diligence_ref="diligence://bayou-field-coop/2026-06-20",
        consent_status="documented",
        consent_ref="consent://bayou-field-coop/2026-06-20",
        benefit_sharing_ref="benefits://bayou-field-coop/2026-06-20",
        grievance_process_ref="grievance://bayou-field-coop/2026-06-20",
        challenge_contact="mailto:gaia-challenges@example.org",
        measurement_verifier="Anthropic Sustainability Metering",
        measurement_boundary_ref="boundary://anthropic/2026-q2/cluster-ops",
        metering_evidence_refs=(
            "meter://anthropic/2026-q2/cluster-ops/raw-kwh",
            "meter://anthropic/2026-q2/cluster-ops/emissions-factor",
        ),
        metering_audit_refs=("audit://anthropic/2026-q2/cluster-ops-metering",),
        livelihood_target_group="displaced coastal workers",
        livelihood_participant_count=42,
        livelihood_person_hours=1280.0,
        median_compensation_local=240.0,
        local_ownership_share=0.35,
        evidence_refs=(
            "evidence://bayou-lafourche/baseline-satellite",
            "evidence://bayou-lafourche/community-ledger",
        ),
        audit_refs=("audit://bayou-lafourche/independent-q2",),
    )


def _make_initiative_packet() -> GaiaInitiativePilotPacket:
    return GaiaInitiativePilotPacket(
        contract=GaiaPilotMeasurementContract(
            model_id="anthropic_claude_ops",
            sponsor_name="Anthropic",
            reporting_period="2026-Q2",
            measurement_mode=GaiaInitiativeMeasurementMode.MEASURED,
            energy_mwh=12.0,
            carbon_intensity=0.35,
            measurement_ref="meter://anthropic/2026-q2/cluster-ops",
            obligation_rule="pilot_rule_v1=max(25000, co2e_tons*7500)",
            challenge_contact="mailto:gaia-challenges@example.org",
            measurement_verifier="Anthropic Sustainability Metering",
            measurement_boundary_ref="boundary://anthropic/2026-q2/cluster-ops",
            metering_evidence_refs=(
                "meter://anthropic/2026-q2/cluster-ops/raw-kwh",
                "meter://anthropic/2026-q2/cluster-ops/emissions-factor",
            ),
            metering_audit_refs=("audit://anthropic/2026-q2/cluster-ops-metering",),
        ),
        initiative=GaiaRestorationInitiative(
            initiative_id="bayou-lafourche-mangroves",
            initiative_name="Bayou Lafourche Mangrove Reciprocity Pilot",
            project_type="mangrove_restoration",
            description=(
                "Community-led mangrove restoration with satellite monitoring, "
                "local stewardship, and public challengeability."
            ),
            area=GaiaInitiativeArea(
                country="USA",
                region="Louisiana Gulf Coast",
                hectares=420,
                ecosystem_type="mangrove",
                boundary_ref="stac://bayou-lafourche/footprint",
            ),
            carbon_potential_tons_yr=3800,
            labor_needed=48,
            funding_gap_usd=640_000,
            integrity_class=GaiaInitiativeIntegrityClass.HIGH_INTEGRITY,
            methodology_ref="method://mangrove-restoration/v1",
            livelihood_target_group="displaced coastal workers",
            partners=GaiaInitiativePartner(
                project_operator="Bayou Field Cooperative",
                community_partner="Bayou Reciprocity Cooperative",
                partner_credibility=GaiaInitiativePartnerCredibility.CREDIBLE,
                due_diligence_ref="diligence://bayou-field-coop/2026-06-20",
            ),
            consent=GaiaInitiativeConsent(
                consent_status=GaiaConsentStatus.DOCUMENTED,
                consent_ref="consent://bayou-field-coop/2026-06-20",
                benefit_sharing_ref="benefits://bayou-field-coop/2026-06-20",
                grievance_process_ref="grievance://bayou-field-coop/2026-06-20",
            ),
            planned_activities=(
                "nursery propagation",
                "shoreline planting",
                "community monitoring",
            ),
            verification_channels=(
                "satellite",
                "iot_sensor",
                "human_auditor",
                "community",
            ),
            monitoring_indicators=(
                GaiaMonitoringIndicator(
                    indicator_id="seedling-survival",
                    label="Seedling Survival",
                    category=GaiaIndicatorCategory.BIOPHYSICAL,
                    unit="pct",
                    baseline_value=0.0,
                    target_value=85.0,
                    cadence="monthly",
                    source_ref="indicator://bayou/seedling-survival",
                ),
                GaiaMonitoringIndicator(
                    indicator_id="worker-retention",
                    label="Worker Retention",
                    category=GaiaIndicatorCategory.SOCIOECONOMIC,
                    unit="pct",
                    baseline_value=0.0,
                    target_value=80.0,
                    cadence="quarterly",
                    source_ref="indicator://bayou/worker-retention",
                ),
            ),
            observation_sources=(
                GaiaObservationSource(
                    protocol=GaiaObservationProtocol.FERM,
                    source_ref="ferm://bayou-lafourche/initiative",
                ),
                GaiaObservationSource(
                    protocol=GaiaObservationProtocol.SENSORTHINGS,
                    source_ref="sensorthings://bayou-lafourche/stations",
                ),
                GaiaObservationSource(
                    protocol=GaiaObservationProtocol.STAC,
                    source_ref="stac://bayou-lafourche/assets",
                ),
                GaiaObservationSource(
                    protocol=GaiaObservationProtocol.DARWIN_CORE,
                    source_ref="dwc://bayou-lafourche/occurrences",
                ),
            ),
            evidence_refs=(
                "evidence://bayou-lafourche/baseline-satellite",
                "evidence://bayou-lafourche/community-ledger",
            ),
            audit_refs=("audit://bayou-lafourche/independent-q2",),
        ),
    )


def test_recommendations_prioritize_verified_projects(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)

    recommendations = platform.recommend_projects("anthropic_claude_ops", top_n=3)

    assert recommendations
    top = recommendations[0]
    assert top.strategy.approved is True
    assert top.project.verification_status == "verified"
    assert top.welfare_tons > 0
    assert top.match_score > 0
    assert "anekanta" in top.strategy.principles
    assert "jagat_kalyan" in top.strategy.principles


def test_ahimsa_blocks_harmful_monoculture_project(tmp_path):
    harmful = GaiaProject(
        project_id="harmful-monoculture",
        name="Export Monoculture Plantation",
        project_type="monoculture",
        country="Nowhere",
        region="Test Region",
        hectares=500,
        carbon_potential_tons_yr=2000,
        labor_needed=10,
        funding_gap_usd=400_000,
        verification_status="verified",
        community_partner="Absent",
        description="Monoculture plantation that would clearcut native habitat.",
        verification_channels=("satellite", "ground", "community"),
    )
    platform = GaiaPlatform(data_dir=tmp_path, projects=[harmful])

    assessment = platform.assess_project(harmful)

    assert assessment.approved is False
    assert any("AHIMSA" in warning for warning in assessment.warnings)
    assert platform.recommend_projects("anthropic_claude_ops") == []


def test_stage_pilot_records_full_auditable_chain(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)

    pilot = platform.stage_pilot(
        model_id="anthropic_claude_ops",
        energy_mwh=12.0,
        carbon_intensity=0.35,
    )

    summary = pilot["ledger_summary"]
    assert summary["chain_valid"] is True
    assert summary["compute_units"] == 1
    assert summary["funding_units"] == 1
    assert summary["labor_units"] == 1
    assert summary["offset_units"] == 1
    assert summary["verification_units"] >= 3
    assert summary["total_verified_offset"] > 0
    assert pilot["fitness"]["weighted_score"] > 0
    assert pilot["recommendation"].strategy.approved is True


def test_cli_dashboard_renders_user_interface(tmp_path, capsys):
    exit_code = main(
        [
            "dashboard",
            "--data-dir",
            str(tmp_path),
            "--model",
            "anthropic_claude_ops",
        ]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "GAIA Platform" in out
    assert "Aptavani" in out
    assert "Top Recommendations" in out


def test_build_pilot_report_writes_monitoring_and_feedback_artifacts(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)

    result = platform.build_pilot_report(
        model_id="anthropic_claude_ops",
        project_id="bayou-lafourche-mangroves",
        feedback_entries=[
            {
                "actor_id": "steward-1",
                "role": "community_steward",
                "satisfaction": 4.8,
                "confidence": 0.91,
                "summary": "The dashboard made the verification burden legible for field operators.",
                "requested_follow_up": "Add a monthly readiness checklist.",
            },
            {
                "actor_id": "reviewer-1",
                "role": "scientific_reviewer",
                "satisfaction": 4.2,
                "confidence": 0.87,
                "summary": "Evidence trace is strong, but shoreline survival should stay visible.",
                "requested_follow_up": "Track seedling survival at the 90-day review.",
            },
        ],
    )

    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    markdown = result["markdown_path"].read_text(encoding="utf-8")

    assert result["project"].project_id == "bayou-lafourche-mangroves"
    assert payload["monitoring"]["snapshot_count"] >= 3
    assert payload["monitoring"]["snapshots"][0]["label"] == "baseline"
    assert payload["feedback_summary"]["response_count"] == 2
    assert payload["feedback_summary"]["average_satisfaction"] > 4.0
    assert payload["effectiveness"]["status"] == "on_track"
    assert "# GAIA Pilot Report" in markdown
    assert "## User Feedback" in markdown
    assert "Bayou Lafourche Mangrove Reciprocity Pilot" in markdown


def test_qualify_intake_blocks_missing_consent_and_challenge_path(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    intake = _make_intake().model_copy(
        update={
            "consent_status": "pending",
            "consent_ref": "",
            "challenge_contact": "",
        }
    )

    decision = platform.qualify_intake(intake)

    assert decision.approved is False
    assert decision.visibility is GaiaClaimVisibility.INTERNAL_ONLY
    assert any("CONSENT" in blocker for blocker in decision.blockers)
    assert any("challenge contact" in blocker for blocker in decision.blockers)


def test_qualify_intake_blocks_standards_packet_missing_monitoring_surface(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    intake = _make_initiative_packet().to_pilot_intake().model_copy(
        update={
            "boundary_ref": "",
            "monitoring_indicators": (),
            "observation_protocols": (),
        }
    )

    decision = platform.qualify_intake(intake)

    assert decision.approved is False
    assert any("boundary reference" in blocker for blocker in decision.blockers)
    assert any("monitoring indicators" in blocker for blocker in decision.blockers)
    assert any("observation protocols" in blocker for blocker in decision.blockers)


def test_qualify_intake_keeps_disclosed_measurement_claims_provisional(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    intake = _make_intake().model_copy(
        update={
            "measurement_mode": GaiaMeasurementMode.DISCLOSED,
            "measurement_verifier": "",
            "measurement_boundary_ref": "",
            "metering_evidence_refs": (),
            "metering_audit_refs": (),
            "measurement_ref": "disclosure://anthropic/2026-q2/cluster-ops",
        }
    )

    decision = platform.qualify_intake(intake)

    assert decision.approved is True
    assert decision.visibility is GaiaClaimVisibility.PROVISIONAL
    assert decision.public_claim_ready is False
    assert decision.measurement_claim_ready is False
    assert any("public claims require metered evidence" in warning for warning in decision.warnings)


def test_qualify_intake_blocks_measured_claim_missing_metering_surface(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    intake = _make_intake().model_copy(
        update={
            "measurement_verifier": "",
            "measurement_boundary_ref": "",
            "metering_evidence_refs": (),
        }
    )

    decision = platform.qualify_intake(intake)

    assert decision.approved is False
    assert any("measurement verifier" in blocker for blocker in decision.blockers)
    assert any("measurement boundary reference" in blocker for blocker in decision.blockers)
    assert any("metering evidence references" in blocker for blocker in decision.blockers)


def test_build_intake_pilot_report_writes_claim_card_and_intake_artifacts(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)

    result = platform.build_intake_pilot_report(
        intake=_make_intake(),
        feedback_entries=[
            {
                "actor_id": "operator-1",
                "role": "platform_operator",
                "satisfaction": 4.5,
                "confidence": 0.9,
                "summary": "Qualification artifacts make the pilot packet challengeable.",
                "requested_follow_up": "Keep the grievance path visible in the claim card.",
            }
        ],
    )

    report_payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    claim_card_payload = json.loads(result["claim_card_path"].read_text(encoding="utf-8"))
    measurement_payload = json.loads(result["measurement_path"].read_text(encoding="utf-8"))
    livelihood_payload = json.loads(result["livelihood_path"].read_text(encoding="utf-8"))
    challenge_payload = json.loads(result["challenge_path"].read_text(encoding="utf-8"))
    claim_explorer_payload = json.loads(
        result["claim_explorer_path"].read_text(encoding="utf-8")
    )
    claim_markdown = result["claim_card_markdown_path"].read_text(encoding="utf-8")
    measurement_markdown = result["measurement_markdown_path"].read_text(encoding="utf-8")
    livelihood_markdown = result["livelihood_markdown_path"].read_text(encoding="utf-8")
    challenge_markdown = result["challenge_markdown_path"].read_text(encoding="utf-8")
    claim_explorer_markdown = result["claim_explorer_markdown_path"].read_text(
        encoding="utf-8"
    )

    assert result["qualification"].approved is True
    assert result["claim_card"].visibility is GaiaClaimVisibility.PUBLIC_READY
    assert result["claim_card"].measurement_claim_ready is True
    assert result["intake_path"].exists()
    assert result["qualification_path"].exists()
    assert result["claim_card_path"].exists()
    assert result["claim_card_markdown_path"].exists()
    assert result["measurement_path"].exists()
    assert result["measurement_markdown_path"].exists()
    assert result["livelihood_path"].exists()
    assert result["livelihood_markdown_path"].exists()
    assert result["challenge_path"].exists()
    assert result["challenge_markdown_path"].exists()
    assert result["claim_explorer_path"].exists()
    assert result["claim_explorer_markdown_path"].exists()
    assert result["reciprocity_path"].exists()
    assert result["reciprocity_projection_path"].exists()
    assert report_payload["claim_card"]["methodology_ref"] == "method://mangrove-restoration/v1"
    assert report_payload["qualification"]["public_claim_ready"] is True
    assert report_payload["qualification"]["measurement_claim_ready"] is True
    assert report_payload["measurement"]["public_claim_ready"] is True
    assert report_payload["livelihood"]["participant_count"] == 42
    assert report_payload["livelihood"]["person_hours"] == 1280.0
    assert report_payload["challenge"]["freeze_promotional_use"] is False
    assert report_payload["challenge"]["packet_path"].endswith("challenge_packet.json")
    assert report_payload["claim_explorer"]["claim_count"] == 1
    assert claim_card_payload["challenge_status"] == "open"
    assert claim_card_payload["claim_type"] == "mixed"
    assert "Anthropic routed $" in claim_card_payload["claim_statement"]
    assert "2026-Q2" in claim_card_payload["claim_scope"]
    assert claim_card_payload["audit_status"] == "passed"
    assert claim_card_payload["measurement_mode"] == "measured"
    assert claim_card_payload["measurement_claim_ready"] is True
    assert claim_card_payload["measurement_packet_path"].endswith("measurement_packet.json")
    assert claim_card_payload["livelihood_packet_path"].endswith("livelihood_packet.json")
    assert claim_card_payload["challenge_packet_path"].endswith("challenge_packet.json")
    assert len(claim_card_payload["metering_evidence_refs"]) == 2
    assert len(claim_card_payload["metering_audit_refs"]) == 1
    assert len(claim_card_payload["evidence_refs"]) == 2
    assert len(claim_card_payload["audit_refs"]) == 1
    assert claim_card_payload["livelihood_person_hours"] == 1280.0
    assert claim_card_payload["median_compensation_local"] == 240.0
    assert claim_card_payload["local_ownership_share"] == 0.35
    assert claim_card_payload["livelihood_feedback_count"] == 1
    assert claim_card_payload["livelihood_feedback_roles"] == ["platform_operator"]
    assert measurement_payload["measurement_mode"] == "measured"
    assert measurement_payload["measurement_verifier"] == "Anthropic Sustainability Metering"
    assert len(measurement_payload["metering_evidence_refs"]) == 2
    assert len(measurement_payload["metering_audit_refs"]) == 1
    assert livelihood_payload["participant_count"] == 42
    assert livelihood_payload["person_hours"] == 1280.0
    assert livelihood_payload["feedback_response_count"] == 1
    assert livelihood_payload["feedback_roles"] == ["platform_operator"]
    assert livelihood_payload["local_ownership_share"] == 0.35
    assert challenge_payload["challenge_status"] == "open"
    assert challenge_payload["freeze_promotional_use"] is False
    assert challenge_payload["challenge_count"] == 0
    assert challenge_payload["material_challenge_count"] == 0
    assert claim_explorer_payload["public_ready_count"] == 1
    assert claim_explorer_payload["provisional_count"] == 0
    assert claim_explorer_payload["entries"][0]["claim_id"] == claim_card_payload["claim_id"]
    assert claim_explorer_payload["entries"][0]["challenge_packet_path"].endswith(
        "challenge_packet.json"
    )
    assert claim_card_payload["total_verified_offset"] > 0
    assert claim_card_payload["obligation_quantity_usd"] >= claim_card_payload["routed_value_usd"]
    assert claim_card_payload["reciprocity_invariant_issues"] == 0
    assert claim_card_payload["reciprocity_ledger_path"].endswith("reciprocity_ledger.jsonl")
    assert report_payload["reciprocity"]["summary"]["chain_valid"] is True
    assert report_payload["reciprocity"]["summary"]["invariant_issues"] == 0
    assert report_payload["reciprocity"]["projection_warnings"] == []
    assert report_payload["reciprocity"]["projection_summary"]["compute_units"] == 1
    assert report_payload["reciprocity"]["projection_summary"]["funding_units"] == 1
    assert report_payload["reciprocity"]["projection_summary"]["labor_units"] == 1
    assert report_payload["reciprocity"]["projection_summary"]["offset_units"] == 1
    assert report_payload["reciprocity"]["projection_summary"]["total_verified_offset"] > 0
    assert report_payload["reciprocity"]["outcome_status"] == "verified"
    assert "## Claim Card" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Challengeability" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Claim Explorer" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Measurement" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Livelihood Transition" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Reciprocity Proof Chain" in result["markdown_path"].read_text(encoding="utf-8")
    assert "## Claim" in claim_markdown
    assert "## Challengeability" in claim_markdown
    assert "# GAIA Claim Card" in claim_markdown
    assert "Measurement claim ready: yes" in claim_markdown
    assert "## Livelihood" in claim_markdown
    assert "## Reciprocity" in claim_markdown
    assert "# GAIA Measurement Packet" in measurement_markdown
    assert "# GAIA Livelihood Packet" in livelihood_markdown
    assert "# GAIA Challenge Packet" in challenge_markdown
    assert "# GAIA Claim Explorer" in claim_explorer_markdown


def test_build_initiative_pilot_report_preserves_standards_metadata(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)

    result = platform.build_initiative_pilot_report(
        packet=_make_initiative_packet(),
        feedback_entries=[
            {
                "actor_id": "operator-1",
                "role": "platform_operator",
                "satisfaction": 4.6,
                "confidence": 0.92,
                "summary": "Standards packet is now preserved end to end.",
                "requested_follow_up": "Keep the boundary reference visible.",
            }
        ],
    )

    report_payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    claim_card_payload = json.loads(result["claim_card_path"].read_text(encoding="utf-8"))
    report_markdown = result["markdown_path"].read_text(encoding="utf-8")
    claim_markdown = result["claim_card_markdown_path"].read_text(encoding="utf-8")

    assert result["initiative_packet_path"].exists()
    assert result["measurement_path"].exists()
    assert result["livelihood_path"].exists()
    assert result["challenge_path"].exists()
    assert result["claim_explorer_path"].exists()
    assert report_payload["initiative"]["ecosystem_type"] == "mangrove"
    assert report_payload["initiative"]["boundary_ref"] == "stac://bayou-lafourche/footprint"
    assert report_payload["initiative"]["monitoring_indicator_count"] == 2
    assert report_payload["initiative"]["standards_profile"] == [
        "FERM",
        "SensorThings",
        "STAC",
        "Darwin Core",
    ]
    assert claim_card_payload["ecosystem_type"] == "mangrove"
    assert claim_card_payload["boundary_ref"] == "stac://bayou-lafourche/footprint"
    assert claim_card_payload["monitoring_indicator_count"] == 2
    assert claim_card_payload["planned_activity_count"] == 3
    assert claim_card_payload["standards_profile"] == [
        "FERM",
        "SensorThings",
        "STAC",
        "Darwin Core",
    ]
    assert claim_card_payload["observation_protocols"] == [
        "darwin_core",
        "ferm",
        "sensorthings",
        "stac",
    ]
    assert claim_card_payload["measurement_claim_ready"] is True
    assert "## Initiative Context" in report_markdown
    assert "## Challengeability" in report_markdown
    assert "## Measurement" in report_markdown
    assert "## Livelihood Transition" in report_markdown
    assert "## Challengeability" in claim_markdown
    assert "## Standards" in claim_markdown
    assert "## Livelihood" in claim_markdown


def test_cli_pilot_report_writes_named_artifacts(tmp_path, capsys):
    feedback_file = tmp_path / "feedback.json"
    feedback_file.write_text(
        json.dumps(
            [
                {
                    "actor_id": "operator-1",
                    "role": "platform_operator",
                    "satisfaction": 4.4,
                    "confidence": 0.9,
                    "summary": "Pilot outputs are audit-friendly.",
                    "requested_follow_up": "Expose the report in facilitator training.",
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "pilot-report",
            "--data-dir",
            str(tmp_path),
            "--model",
            "anthropic_claude_ops",
            "--project-id",
            "narmada-watershed-commons",
            "--feedback-file",
            str(feedback_file),
        ]
    )

    out = capsys.readouterr().out
    pilot_dir = (
        tmp_path
        / "pilots"
        / "anthropic_claude_ops-narmada-watershed-commons"
    )

    assert exit_code == 0
    assert "GAIA pilot report written" in out
    assert (pilot_dir / "pilot_report.json").exists()
    assert (pilot_dir / "pilot_report.md").exists()


def test_cli_pilot_intake_report_writes_claim_card_artifacts(tmp_path, capsys):
    intake_file = tmp_path / "pilot_intake.json"
    intake_file.write_text(
        json.dumps(_make_intake().model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "pilot-intake-report",
            "--data-dir",
            str(tmp_path),
            "--intake-file",
            str(intake_file),
        ]
    )

    out = capsys.readouterr().out
    pilot_dir = tmp_path / "pilots" / "anthropic_claude_ops-bayou-lafourche-mangroves"

    assert exit_code == 0
    assert "GAIA intake pilot packet written" in out
    assert (pilot_dir / "pilot_report.json").exists()
    assert (pilot_dir / "claim_card.json").exists()
    assert (pilot_dir / "claim_card.md").exists()
    assert (pilot_dir / "measurement_packet.json").exists()
    assert (pilot_dir / "measurement_packet.md").exists()
    assert (pilot_dir / "livelihood_packet.json").exists()
    assert (pilot_dir / "livelihood_packet.md").exists()
    assert (pilot_dir / "challenge_packet.json").exists()
    assert (pilot_dir / "challenge_packet.md").exists()
    assert (tmp_path / "claim_explorer.json").exists()
    assert (tmp_path / "claim_explorer.md").exists()


def test_cli_initiative_pilot_report_writes_standards_artifacts(tmp_path, capsys):
    packet_file = tmp_path / "initiative_packet.json"
    packet_file.write_text(
        json.dumps(
            _make_initiative_packet().model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "initiative-pilot-report",
            "--data-dir",
            str(tmp_path),
            "--packet-file",
            str(packet_file),
        ]
    )

    out = capsys.readouterr().out
    pilot_dir = tmp_path / "pilots" / "anthropic_claude_ops-bayou-lafourche-mangroves"

    assert exit_code == 0
    assert "GAIA initiative pilot packet written" in out
    assert (pilot_dir / "initiative_packet.json").exists()
    assert (pilot_dir / "pilot_report.json").exists()
    assert (pilot_dir / "claim_card.json").exists()
    assert (pilot_dir / "measurement_packet.json").exists()
    assert (pilot_dir / "livelihood_packet.json").exists()
    assert (pilot_dir / "livelihood_packet.md").exists()


def test_submit_claim_challenge_freezes_promotional_claim_and_updates_explorer(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    result = platform.build_intake_pilot_report(
        intake=_make_intake(),
        feedback_entries=[
            {
                "actor_id": "operator-1",
                "role": "platform_operator",
                "satisfaction": 4.4,
                "confidence": 0.9,
                "summary": "Initial packet is ready for public challengeability.",
                "requested_follow_up": "Keep reversal review explicit.",
            }
        ],
    )

    update = platform.submit_claim_challenge(
        claim_card_path=result["claim_card_path"],
        challenge={
            "raised_by": "community-observer",
            "role": "community_steward",
            "summary": "Recent shoreline monitoring suggests reversal risk exceeds the published wording.",
            "ground": GaiaChallengeGround.ECOLOGICAL_REVERSAL.value,
            "state": GaiaChallengeState.ACKNOWLEDGED.value,
            "evidence_ref": "evidence://bayou-lafourche/reversal-review",
            "requested_action": "Freeze promotional use until the updated monitoring bundle is reviewed.",
        },
    )

    claim_card_payload = json.loads(update["claim_card_path"].read_text(encoding="utf-8"))
    challenge_payload = json.loads(update["challenge_path"].read_text(encoding="utf-8"))
    explorer_payload = json.loads(
        update["claim_explorer_path"].read_text(encoding="utf-8")
    )
    challenge_markdown = update["challenge_path"].with_suffix(".md").read_text(
        encoding="utf-8"
    )

    assert claim_card_payload["challenge_status"] == "acknowledged"
    assert claim_card_payload["visibility"] == "provisional"
    assert claim_card_payload["promotional_use_frozen"] is True
    assert claim_card_payload["reversal_status"] == "watch"
    assert claim_card_payload["challenge_count"] == 1
    assert claim_card_payload["unresolved_challenge_count"] == 1
    assert claim_card_payload["material_challenge_count"] == 0
    assert claim_card_payload["claim_statement"].startswith("Claim under review for")
    assert challenge_payload["freeze_promotional_use"] is True
    assert challenge_payload["challenge_status"] == "acknowledged"
    assert challenge_payload["challenge_count"] == 1
    assert challenge_payload["next_triage_due_at"] is not None
    assert challenge_payload["next_initial_finding_due_at"] is not None
    assert challenge_payload["service_level_notes"]
    assert explorer_payload["challenged_count"] == 1
    assert explorer_payload["entries"][0]["promotional_use_frozen"] is True
    assert explorer_payload["entries"][0]["challenge_count"] == 1
    assert "## Service Levels" in challenge_markdown


def test_apply_claim_remediation_resolves_challenge_and_restores_public_ready(tmp_path):
    platform = GaiaPlatform(data_dir=tmp_path)
    result = platform.build_intake_pilot_report(
        intake=_make_intake(),
        feedback_entries=[
            {
                "actor_id": "operator-1",
                "role": "platform_operator",
                "satisfaction": 4.4,
                "confidence": 0.9,
                "summary": "Initial packet is ready for public challengeability.",
                "requested_follow_up": "Keep reversal review explicit.",
            }
        ],
    )

    challenge_result = platform.submit_claim_challenge(
        claim_card_path=result["claim_card_path"],
        challenge={
            "raised_by": "community-observer",
            "role": "community_steward",
            "summary": "Recent shoreline monitoring suggests reversal risk exceeds the published wording.",
            "ground": GaiaChallengeGround.ECOLOGICAL_REVERSAL.value,
            "state": GaiaChallengeState.ACKNOWLEDGED.value,
            "evidence_ref": "evidence://bayou-lafourche/reversal-review",
            "requested_action": "Freeze promotional use until the updated monitoring bundle is reviewed.",
        },
    )
    challenge_payload = json.loads(
        challenge_result["challenge_path"].read_text(encoding="utf-8")
    )
    challenge_id = challenge_payload["challenge_records"][0]["challenge_id"]

    remediation_result = platform.apply_claim_remediation(
        claim_card_path=result["claim_card_path"],
        remediation={
            "owner": "gaia-review-council",
            "summary": "Updated monitoring bundle accepted and claim reissued with narrowed wording.",
            "outcome": GaiaRemediationOutcome.CLAIM_REISSUE.value,
            "step": GaiaRemediationStep.HISTORICAL_APPEND.value,
            "linked_challenge_ids": [challenge_id],
            "evidence_refs": ("decision://bayou-lafourche/reissue",),
            "decision_ref": "decision://bayou-lafourche/reissue",
        },
    )

    claim_card_payload = json.loads(
        remediation_result["claim_card_path"].read_text(encoding="utf-8")
    )
    challenge_payload = json.loads(
        remediation_result["challenge_path"].read_text(encoding="utf-8")
    )

    assert claim_card_payload["challenge_status"] == "resolved"
    assert claim_card_payload["visibility"] == "public_ready"
    assert claim_card_payload["promotional_use_frozen"] is False
    assert claim_card_payload["remediation_status"] == "resolved"
    assert claim_card_payload["claim_statement"].startswith("Anthropic routed $")
    assert challenge_payload["resolved_challenge_count"] == 1
    assert challenge_payload["unresolved_challenge_count"] == 0
    assert challenge_payload["remediation_case_count"] == 1
    assert challenge_payload["freeze_promotional_use"] is False


def test_cli_challenge_and_remediation_commands_update_governance_artifacts(
    tmp_path,
    capsys,
):
    platform = GaiaPlatform(data_dir=tmp_path)
    result = platform.build_intake_pilot_report(
        intake=_make_intake(),
        feedback_entries=[
            {
                "actor_id": "operator-1",
                "role": "platform_operator",
                "satisfaction": 4.4,
                "confidence": 0.9,
                "summary": "Initial packet is ready for public challengeability.",
                "requested_follow_up": "Keep reversal review explicit.",
            }
        ],
    )

    challenge_file = tmp_path / "challenge.json"
    challenge_file.write_text(
        json.dumps(
            {
                "raised_by": "community-observer",
                "role": "community_steward",
                "summary": "Recent shoreline monitoring suggests reversal risk exceeds the published wording.",
                "ground": GaiaChallengeGround.ECOLOGICAL_REVERSAL.value,
                "state": GaiaChallengeState.ACKNOWLEDGED.value,
                "evidence_ref": "evidence://bayou-lafourche/reversal-review",
                "requested_action": "Freeze promotional use until the updated monitoring bundle is reviewed.",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "challenge-claim",
            "--data-dir",
            str(tmp_path),
            "--claim-card-file",
            str(result["claim_card_path"]),
            "--challenge-file",
            str(challenge_file),
        ]
    )

    out = capsys.readouterr().out
    challenge_payload = json.loads(result["challenge_path"].read_text(encoding="utf-8"))
    challenge_id = challenge_payload["challenge_records"][0]["challenge_id"]

    assert exit_code == 0
    assert "GAIA claim challenge recorded" in out

    remediation_file = tmp_path / "remediation.json"
    remediation_file.write_text(
        json.dumps(
            {
                "owner": "gaia-review-council",
                "summary": "Updated monitoring bundle accepted and claim reissued with narrowed wording.",
                "outcome": GaiaRemediationOutcome.CLAIM_REISSUE.value,
                "step": GaiaRemediationStep.HISTORICAL_APPEND.value,
                "linked_challenge_ids": [challenge_id],
                "evidence_refs": ["decision://bayou-lafourche/reissue"],
                "decision_ref": "decision://bayou-lafourche/reissue",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "remediate-claim",
            "--data-dir",
            str(tmp_path),
            "--claim-card-file",
            str(result["claim_card_path"]),
            "--remediation-file",
            str(remediation_file),
        ]
    )

    out = capsys.readouterr().out
    claim_card_payload = json.loads(result["claim_card_path"].read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "GAIA claim remediation recorded" in out
    assert claim_card_payload["challenge_status"] == "resolved"
    assert claim_card_payload["promotional_use_frozen"] is False
    assert result["challenge_path"].exists()
    assert result["challenge_markdown_path"].exists()
    assert (tmp_path / "claim_explorer.json").exists()
    assert (tmp_path / "claim_explorer.md").exists()
