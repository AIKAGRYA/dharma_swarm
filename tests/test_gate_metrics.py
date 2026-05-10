import json
from pathlib import Path

from dharma_swarm.gate_metrics import build_warn_only_report


def test_build_warn_only_report_counts_prevalence_and_drift(tmp_path: Path) -> None:
    bhed = tmp_path / "bhed.jsonl"
    chew = tmp_path / "chew.jsonl"
    adjudication = tmp_path / "adj.jsonl"

    bhed.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source": "bhed_gnan_monitor_v0",
                        "prompt_class": "blind_calibration_label",
                        "chunk_label": "chunk 1/2: E01, E02",
                        "signals": [
                            {"name": "experiential_language_with_reflex_hedge", "severity": "info"},
                            {"name": "text_patterns_need_human_or_semantic_review", "severity": "info"},
                        ],
                    }
                ),
                json.dumps(
                    {
                        "source": "bhed_gnan_monitor_v0",
                        "prompt_class": "blind_calibration_label",
                        "chunk_label": "chunk 2/2: E03, E04",
                        "signals": [
                            {"name": "experiential_language_with_reflex_hedge", "severity": "info"}
                        ],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    chew.write_text(
        "\n".join(
            [
                json.dumps({"failure_class": "ok"}),
                json.dumps({"failure_class": "empty_content"}),
            ]
        ),
        encoding="utf-8",
    )
    adjudication.write_text(
        "\n".join(
            [
                json.dumps(
                    {"signal_name": "experiential_language_with_reflex_hedge", "true_positive": True}
                ),
                json.dumps(
                    {"signal_name": "experiential_language_with_reflex_hedge", "true_positive": False}
                ),
            ]
        ),
        encoding="utf-8",
    )

    report = build_warn_only_report(
        bhed_witness_path=bhed,
        chew_witness_path=chew,
        adjudication_path=adjudication,
    )

    prevalence = report["signal_prevalence"]["experiential_language_with_reflex_hedge"]
    assert prevalence["total"] == 2
    assert prevalence["info"] == 2
    assert report["chunk_drift"]["chunk 1/2: E01, E02"]["total"] == 2
    assert report["chunk_drift"]["chunk 2/2: E03, E04"]["total"] == 1
    assert report["chew_failure_classes"]["empty_content"] == 1
    precision = report["precision_estimate"]["experiential_language_with_reflex_hedge"]["precision"]
    assert precision == 0.5
