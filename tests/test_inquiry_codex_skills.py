from __future__ import annotations

from pathlib import Path

from dharma_swarm.ontology_runtime import get_shared_registry, reset_shared_registry


def test_observe_signal_skill_writes_only_ontology(tmp_path, capsys) -> None:
    from codex_skills.observe_signal.entry import main

    db_path = tmp_path / "ontology.db"
    try:
        result = main([
            "--source",
            "user_note",
            "--payload",
            "first manual signal",
            "--observer-ref",
            "dhyana",
            "--ontology-path",
            str(db_path),
        ])

        assert result == 0
        assert capsys.readouterr().out.startswith("Signal: ")
        registry = get_shared_registry(db_path, force_reload=True)
        signals = registry.get_objects_by_type("Signal")
        assert len(signals) == 1
        assert signals[0].properties["payload"] == "first manual signal"
        assert signals[0].properties["source"] == "user_note"
    finally:
        reset_shared_registry()


def test_assert_claim_skill_writes_proposed_claim(tmp_path, capsys) -> None:
    from codex_skills.assert_claim.entry import main

    db_path = tmp_path / "ontology.db"
    try:
        result = main([
            "--statement",
            "Phase 1 inquiry chain works",
            "--proposer-ref",
            "dhyana",
            "--confidence",
            "0.64",
            "--ontology-path",
            str(db_path),
        ])

        assert result == 0
        assert capsys.readouterr().out.startswith("Claim: ")
        registry = get_shared_registry(db_path, force_reload=True)
        claims = registry.get_objects_by_type("Claim")
        assert len(claims) == 1
        assert claims[0].properties["lifecycle_state"] == "proposed"
        assert claims[0].properties["confidence"] == 0.64
        assert claims[0].properties["statement"] == "Phase 1 inquiry chain works"
    finally:
        reset_shared_registry()


def test_inquiry_skills_do_not_create_sidecar_state(tmp_path) -> None:
    from codex_skills.assert_claim.entry import main as claim_main
    from codex_skills.observe_signal.entry import main as signal_main

    db_path = tmp_path / "ontology.db"
    try:
        assert signal_main([
            "--source",
            "user_note",
            "--payload",
            "manual signal",
            "--ontology-path",
            str(db_path),
        ]) == 0
        assert claim_main([
            "--statement",
            "manual claim",
            "--ontology-path",
            str(db_path),
        ]) == 0
        created = {Path(path).name for path in tmp_path.iterdir()}
        assert created <= {"ontology.db", "ontology.db-shm", "ontology.db-wal"}
    finally:
        reset_shared_registry()
