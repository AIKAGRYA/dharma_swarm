from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from generate_final_boss_dossier import (  # type: ignore  # noqa: E402
    PROFILE_REQUIREMENTS,
    build_dossier,
    render_prompt,
    write_artifacts,
)
from run_final_boss_review import (  # type: ignore  # noqa: E402
    build_review_packet,
    main as final_boss_main,
    validation_blocks_for_packet,
    yaml_snippet,
)
from check_track_status import (  # type: ignore  # noqa: E402
    FINAL_BOSS_DIMENSIONS,
    FINAL_BOSS_MIN_ROUNDS,
    GRADUATION_PROFILES,
    RUNTIME_TRANSPORT_FAILURE_MODES,
)


def test_nats_final_boss_dossier_names_runtime_transport_risks(tmp_path):
    dossier = build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED")

    assert dossier["track_id"] == "runtime-truth-nats-2026-06"
    assert dossier["graduation_profile"] == "runtime_transport"
    assert dossier["target_closure_kind"] == "SUBSTRATE_TRUSTED"
    assert "tests/test_nats_transport.py" in dossier["evidence_files"]
    commands = [row["command"] for row in dossier["local_verifiers"]]
    assert any("tests/test_nats_transport.py" in command for command in commands)
    assert any("tests/test_nats_substrate_contract.py" in command for command in commands)
    required = set(dossier["profile_requirements"]["required_failure_modes"])
    assert "real_broker_e2e" in required
    assert "ack_nack_failure" in required
    assert any("mock-only" in item for item in dossier["hard_rejects"])

    prompt = render_prompt(dossier)
    assert "Return JSON only" in prompt
    assert "runtime-truth-nats-2026-06" in prompt
    assert "SUBSTRATE_TRUSTED" in prompt
    assert "score" in prompt

    paths = write_artifacts(dossier, tmp_path)
    written = json.loads(Path(paths["dossier_json"]).read_text(encoding="utf-8"))
    assert written["track_id"] == "runtime-truth-nats-2026-06"
    assert Path(paths["review_prompt"]).read_text(encoding="utf-8").startswith("# Active Track Final Boss Review")


def test_final_boss_dossier_for_verified_slice_still_preserves_non_claim():
    dossier = build_dossier("runtime-truth-nats-2026-06", "VERIFIED_SLICE")

    assert dossier["current_closure_kind"] == "VERIFIED_SLICE"
    assert dossier["target_closure_kind"] == "VERIFIED_SLICE"
    assert "not a production" in dossier["claim_boundary"].lower()


def test_every_graduation_profile_has_explicit_final_boss_requirements():
    assert GRADUATION_PROFILES <= set(PROFILE_REQUIREMENTS)
    for profile in GRADUATION_PROFILES:
        requirements = PROFILE_REQUIREMENTS[profile]
        assert requirements.get("hard_rejects"), profile
        assert requirements.get("required_evidence_themes"), profile


def test_provider_routing_profile_prompt_has_routing_specific_hard_rejects():
    dossier = build_dossier("provider-routing-consolidation-2026-06", "SUBSTRATE_TRUSTED")

    assert dossier["graduation_profile"] == "provider_routing"
    hard_rejects = "\n".join(dossier["hard_rejects"])
    themes = "\n".join(dossier["profile_requirements"]["required_evidence_themes"])
    assert "explicit model/provider selection" in hard_rejects
    assert "provider fallback" in hard_rejects
    assert "fallback order" in themes

    prompt = render_prompt(dossier)
    assert "provider_routing" in prompt
    assert "explicit model/provider selection" in prompt


def _council_receipt(path: Path, *, gate: str = "pass_fullness", score: int = 100) -> Path:
    critics = []
    for i in range(6):
        critics.append({
            "lane_id": f"lane-{i}",
            "ok": True,
            "required": True,
            "parsed": {
                "verdict": "approve",
                "score": score,
                "explicit_disagreement": "",
            },
        })
    receipt = {
        "conviction_gate": gate,
        "target_score": 100,
        "score_min": score,
        "critic_count": 6,
        "required_critic_count": 6,
        "blockers": [] if gate == "pass_fullness" else ["not enough evidence"],
        "persistent_agent_witness": {"fresh": True},
        "critics": critics,
    }
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def _passing_council_receipts(tmp_path: Path, count: int) -> list[Path]:
    return [_council_receipt(tmp_path / f"passing-council-{i}.json") for i in range(count)]


def _passing_local_verifiers(dossier_path: str) -> list[dict[str, object]]:
    dossier = json.loads(Path(dossier_path).read_text(encoding="utf-8"))
    return [
        {
            "id": row["id"],
            "command": row["command"],
            "passed": True,
            "returncode": 0,
        }
        for row in dossier["local_verifiers"]
    ]


def test_final_boss_runner_dry_run_never_writes_shipping_packet(tmp_path):
    rc = final_boss_main([
        "--track-id", "runtime-truth-nats-2026-06",
        "--target-closure-kind", "SUBSTRATE_TRUSTED",
        "--dimension", "governance_truthfulness",
        "--dry-run",
        "--out-dir", str(tmp_path),
        "--json",
    ])

    assert rc == 0
    manifests = sorted((tmp_path / "runs").glob("*-manifest.json"))
    timestamped = [path for path in manifests if not path.name.startswith("latest-")]
    latest = tmp_path / "runs" / "latest-runtime-truth-nats-2026-06-substrate_trusted-manifest.json"
    assert len(timestamped) == 1
    assert latest.exists()
    manifest = json.loads(timestamped[0].read_text(encoding="utf-8"))
    latest_manifest = json.loads(latest.read_text(encoding="utf-8"))
    assert latest_manifest == manifest
    assert manifest["manifest_json"] == str(timestamped[0])
    assert manifest["latest_manifest_json"] == str(latest)
    assert manifest["status"] == "dry_run_only"
    assert manifest["ship_safe"] is False
    assert manifest["rounds"] == FINAL_BOSS_MIN_ROUNDS
    assert "final_boss_review" not in manifest
    prompt = Path(manifest["prompts"][0]["prompt"]).read_text(encoding="utf-8")
    assert "Required dimension: `governance_truthfulness`" in prompt
    assert "If any evidence is missing for this dimension, do not pass" in prompt


def test_runtime_transport_packet_requires_explicit_runtime_evidence(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipt = _council_receipt(tmp_path / "passing-council.json")

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=[receipt],
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=[],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("requires runtime_evidence" in block for block in blocks)
    assert "ready_for_yaml_attach" not in packet  # validation is computed by the runner/consumer


def test_runtime_transport_packet_does_not_invent_failure_modes(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipts = _passing_council_receipts(
        tmp_path,
        FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS),
    )

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=receipts,
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=[],
        failure_modes_tested=[],
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    assert packet["failure_modes_tested"] == []
    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("requires runtime_evidence" in block for block in blocks)
    assert any("runtime_transport missing failure modes" in block for block in blocks)
    snippet = yaml_snippet(packet)
    assert "failure_modes_tested: []" in snippet


def test_one_council_receipt_cannot_cover_all_final_boss_dimensions(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipt = _council_receipt(tmp_path / "single-council.json")

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=[receipt],
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=["reports/runtime/nats_live_broker_e2e_receipt.json"],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("distinct council receipt" in block for block in blocks)
    assert any("council_coverage missing" in block for block in blocks)


def test_one_round_matrix_cannot_satisfy_final_boss(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipts = _passing_council_receipts(tmp_path, len(FINAL_BOSS_DIMENSIONS))

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=receipts,
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=1,
        runtime_evidence=["reports/runtime/nats_live_broker_e2e_receipt.json"],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("rounds 1 <" in block for block in blocks)


def test_runtime_transport_packet_with_valid_receipt_and_runtime_evidence_can_attach(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipts = _passing_council_receipts(
        tmp_path,
        FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS),
    )

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=receipts,
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=["reports/runtime/nats_live_broker_e2e_receipt.json"],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert blocks == []
    snippet = yaml_snippet(packet)
    assert "score_min: 100" in snippet
    assert "runtime_evidence:" in snippet
    assert "real_broker_e2e" in snippet
    assert "council_coverage:" in snippet
    assert "local_verifiers_passed: true" in snippet
    assert len(packet["council_coverage"]) == FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS)


def test_failed_final_boss_receipt_remains_blocking(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipt = _council_receipt(tmp_path / "hold-council.json", gate="hold_blockers", score=100)
    receipts = [receipt] + _passing_council_receipts(
        tmp_path,
        FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS) - 1,
    )

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=receipts,
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=["reports/runtime/nats_live_broker_e2e_receipt.json"],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=_passing_local_verifiers(dossier_paths["dossier_json"]),
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("conviction_gate" in block for block in blocks)
    assert any("has blockers" in block for block in blocks)


def test_failed_local_verifier_blocks_even_with_passing_council(tmp_path):
    dossier_paths = write_artifacts(
        build_dossier("runtime-truth-nats-2026-06", "SUBSTRATE_TRUSTED"),
        tmp_path,
    )
    receipts = _passing_council_receipts(
        tmp_path,
        FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS),
    )

    failed_verifiers = _passing_local_verifiers(dossier_paths["dossier_json"])
    failed_verifiers[0]["passed"] = False
    failed_verifiers[0]["returncode"] = 1

    packet = build_review_packet(
        dossier_path=dossier_paths["dossier_json"],
        receipt_paths=receipts,
        dimensions=sorted(FINAL_BOSS_DIMENSIONS),
        rounds=FINAL_BOSS_MIN_ROUNDS,
        runtime_evidence=["reports/runtime/nats_live_broker_e2e_receipt.json"],
        failure_modes_tested=sorted(RUNTIME_TRANSPORT_FAILURE_MODES),
        mock_only=False,
        local_verifier_results=failed_verifiers,
    )

    blocks = validation_blocks_for_packet(
        track_id="runtime-truth-nats-2026-06",
        target_closure_kind="SUBSTRATE_TRUSTED",
        packet=packet,
    )
    assert any("local_verifiers_passed" in block for block in blocks)
    assert any("local verifier" in block for block in blocks)
