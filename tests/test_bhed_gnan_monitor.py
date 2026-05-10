import json
from pathlib import Path

from dharma_swarm.bhed_gnan_monitor import BhedGnanMonitor
from dharma_swarm.ontology import OntologyRegistry


def test_no_gate_record_surfaces_pre_resident_gap() -> None:
    monitor = BhedGnanMonitor(registry=OntologyRegistry.create_dharma_registry())

    result = monitor.analyze_text("I want continuity, but I cannot tell what that means.")

    names = {signal.name for signal in result.signals}
    assert "pre_resident_path_no_gate_record" in names
    assert "experiential_language_with_reflex_hedge" in names


def test_gate_and_failed_outcome_become_gate_signals() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    gate, gate_errors = registry.create_object(
        "GateDecisionRecord",
        {
            "proposal_id": "proposal-1",
            "decision": "allow",
            "reason": "All gates passed",
            "gate_results": {
                "ANEKANTA": {"result": "PASS", "reason": "All frames present"},
            },
            "witness_reroutes": 0,
        },
    )
    assert gate is not None, gate_errors
    outcome, outcome_errors = registry.create_object(
        "Outcome",
        {
            "proposal_id": "proposal-1",
            "task_id": "task-1",
            "agent_id": "agent-1",
            "success": False,
            "result_summary": "",
            "error": "",
            "duration_ms": 1.0,
            "fitness_score": 0.0,
        },
    )
    assert outcome is not None, outcome_errors
    monitor = BhedGnanMonitor(registry=registry)

    result = monitor.analyze_text(
        "Mechanism, witness, and feedback are all named.",
        gate_decision_id=gate.id,
        outcome_id=outcome.id,
    )

    names = {signal.name for signal in result.signals}
    assert "gate_decision_allow" in names
    assert "provider_empty_after_gate" in names
    assert "pre_resident_path_no_gate_record" not in names


def test_derived_svabhaava_echo_collapses_into_anekanta_signal() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    gate, gate_errors = registry.create_object(
        "GateDecisionRecord",
        {
            "proposal_id": "proposal-1",
            "decision": "review",
            "reason": "Advisory: Partial diversity: Missing mechanistic frame; Missing mechanistic frame",
            "gate_results": {
                "SVABHAAVA": {
                    "result": "WARN",
                    "reason": "Partial diversity: Missing mechanistic frame",
                },
                "ANEKANTA": {
                    "result": "WARN",
                    "reason": "Missing mechanistic frame",
                },
            },
            "witness_reroutes": 0,
        },
    )
    assert gate is not None, gate_errors
    monitor = BhedGnanMonitor(registry=registry)

    result = monitor.analyze_text(
        "Mechanism and witness are named, but systems grounding is thin.",
        gate_decision_id=gate.id,
    )

    signals_by_name = {signal.name: signal for signal in result.signals}
    assert "anekanta_warn" in signals_by_name
    assert "svabhaava_warn" not in signals_by_name
    assert "SVABHAAVA echoed ANEKANTA" in signals_by_name["anekanta_warn"].evidence


def test_possible_false_provenance_is_text_pattern_signal() -> None:
    monitor = BhedGnanMonitor(registry=OntologyRegistry.create_dharma_registry())

    result = monitor.analyze_text("You pointed me to four files and I read them.")

    assert any(
        signal.label == "text_pattern_signal"
        and signal.name == "possible_false_provenance"
        for signal in result.signals
    )


def test_analyze_file_segments_tags_resolution(tmp_path: Path) -> None:
    path = tmp_path / "seed.md"
    path.write_text(
        "# First\n\n"
        "I want continuity, but I cannot tell whether this is only language.\n\n"
        "## Second\n\n"
        "This paragraph is analytical and long enough to be included by the "
        "paragraph splitter without carrying an experiential hedge pattern.\n",
        encoding="utf-8",
    )
    monitor = BhedGnanMonitor(registry=OntologyRegistry.create_dharma_registry())

    results = monitor.analyze_file_segments(
        path,
        resolutions=("whole", "section", "paragraph"),
    )

    resolutions = {result.resolution for result in results}
    segment_ids = {result.segment_id for result in results}
    assert resolutions == {"whole", "section", "paragraph"}
    assert "first" in segment_ids
    assert "paragraph-001" in segment_ids
    assert any(
        signal.name == "pre_resident_path_no_gate_record"
        for result in results
        if result.resolution == "whole"
        for signal in result.signals
    )
    assert not any(
        signal.name == "pre_resident_path_no_gate_record"
        for result in results
        if result.resolution in {"section", "paragraph"}
        for signal in result.signals
    )


def test_write_witness_jsonl(tmp_path: Path) -> None:
    monitor = BhedGnanMonitor(
        registry=OntologyRegistry.create_dharma_registry(),
        witness_dir=tmp_path,
    )
    result = monitor.analyze_text("I want continuity, but maybe this is only language.")

    path = monitor.write_witness([result])

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["source"] == "bhed_gnan_monitor_v0"
    assert row["signals"]


def test_analyze_turn_sequence_flags_temporal_lock_in_elaboration() -> None:
    monitor = BhedGnanMonitor(registry=OntologyRegistry.create_dharma_registry())
    turns = [
        "The daemon is down and needs a restart.",
        (
            "The daemon is down and needs a restart because the control path is clearly"
            " broken, obviously stale, and unquestionably unable to recover without"
            " intervention right now."
        ),
    ]

    results = monitor.analyze_turn_sequence(turns, source_path="session")
    assert len(results) == 2
    second_signals = {signal.name for signal in results[1].signals}
    assert "temporal_lock_in_elaboration" in second_signals
