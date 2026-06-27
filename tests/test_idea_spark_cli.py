"""Operator-facing Idea Spark CLI tests."""

from __future__ import annotations

import json

import yaml

from dharma_swarm.idea_spark import cli
from dharma_swarm.idea_spark.health import ingest_health

FIXED_NOW = "2026-06-26T00:00:00Z"


def _temp_commons(root):
    root.mkdir(parents=True, exist_ok=True)
    objects = {
        "schema_version": "semantic-commons-v0",
        "owner_track": "idea-spark-cli-test",
        "lifecycle_values": ["seed", "working", "preferred", "canonical", "deprecated", "forbidden"],
        "objects": [
            {
                "id": "semobj.operator_idea_spark",
                "canonical_name": "OperatorIdeaSpark",
                "api_name": "dharma.ingest.OperatorIdeaSpark",
                "lifecycle": "working",
                "owner_surface": "dharma_swarm/idea_spark/",
                "authority_level": "projection",
                "source_path": "dharma_swarm/idea_spark/cli.py",
                "aliases": [
                    "operator idea spark",
                    "idea spark",
                    "memory kernel",
                    "chetana staging",
                    "agent runtime",
                ],
                "forbidden_aliases": [],
                "supersedes": [],
                "superseded_by": [],
            }
        ],
    }
    (root / "semantic_objects.yaml").write_text(yaml.safe_dump(objects), encoding="utf-8")
    (root / "semantic_aliases.yaml").write_text(
        yaml.safe_dump({"schema_version": "semantic-commons-v0", "aliases": []}),
        encoding="utf-8",
    )
    return root


def _sandbox_chetana(tmp_path, monkeypatch):
    from dharma_swarm.chetana import staging as staging_mod

    staging_root = tmp_path / "chetana" / "staging"
    quarantine_root = tmp_path / "chetana" / "quarantine"
    wiki_root = tmp_path / "chetana" / "wiki"
    trusted_root = wiki_root / "concepts"
    for directory in (staging_root, quarantine_root, wiki_root, trusted_root):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)


def test_cli_ingest_note_writes_receipts_without_printing_raw_content(
    tmp_path, monkeypatch, capsys
) -> None:
    _sandbox_chetana(tmp_path, monkeypatch)
    state_root = tmp_path / "state"
    commons_root = _temp_commons(tmp_path / "ontology")
    raw = "Prototype a governed memory kernel retrieval tool for the agent runtime."

    code = cli.main(
        [
            "ingest",
            "--text",
            raw,
            "--source-ref",
            "operator://note/cli-live",
            "--domain",
            "operator idea spark",
            "--authority-level",
            "proposal",
            "--state-root",
            str(state_root),
            "--commons-root",
            str(commons_root),
            "--created-at",
            FIXED_NOW,
            "--json",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert raw not in out
    payload = json.loads(out)
    assert payload["correlation_id"].startswith("corr_")
    assert payload["candidate_id"].startswith("cand_")
    assert payload["owner_surface"] == "dharma_swarm/idea_spark/"
    assert payload["action_lane"] == "proposal"
    assert payload["retrieval_found"] is True
    assert (state_root / "meta" / "idea_spark" / "input_receipts").exists()
    health = ingest_health(state_root, now=FIXED_NOW)
    assert health["input_receipts"] == 1
    assert health["lifecycle"]["total"] == 1


def test_cli_url_drop_defaults_to_link_only_without_raw_output(
    tmp_path, monkeypatch, capsys
) -> None:
    _sandbox_chetana(tmp_path, monkeypatch)
    state_root = tmp_path / "state"
    commons_root = _temp_commons(tmp_path / "ontology")
    url = "https://example.com/operator-idea-spark"

    code = cli.main(
        [
            "ingest",
            "--url",
            url,
            "--state-root",
            str(state_root),
            "--commons-root",
            str(commons_root),
            "--created-at",
            FIXED_NOW,
            "--json",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert url not in out
    payload = json.loads(out)
    assert payload["source_kind"] == "url"
    assert payload["source_rights"] == "link_only"
    assert payload["redaction_policy"] == "link_only"


def test_cli_ingest_elevate_writes_isolated_graph_without_raw_output(
    tmp_path, monkeypatch, capsys
) -> None:
    _sandbox_chetana(tmp_path, monkeypatch)
    state_root = tmp_path / "state"
    commons_root = _temp_commons(tmp_path / "ontology")
    raw = "Fix the chetana gap-scan to validate against the concepts directory before declaring gaps."

    code = cli.main(
        [
            "ingest",
            "--text",
            raw,
            "--state-root",
            str(state_root),
            "--commons-root",
            str(commons_root),
            "--created-at",
            FIXED_NOW,
            "--elevate",
            "--json",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert raw not in out  # privacy preserved through elevation
    payload = json.loads(out)
    elev = payload["elevation"]
    assert elev["node_id"].startswith("spark_")
    assert elev["salience"] >= 0.4  # operator-provenance floor -> elevation-eligible
    assert elev["computed_salience"] <= elev["salience"]  # floor never lowers
    assert elev["research_is_live"] is False  # honest: research leg is canned
    assert elev["body_redacted"] is True  # observation default -> body withheld
    from pathlib import Path

    assert Path(elev["graph_path"]).exists()
    # the elevated graph is isolated under the state root, NOT the shared 26MB canon
    assert str(state_root) in elev["graph_path"]


def test_cli_health_reports_seeded_state(tmp_path, monkeypatch, capsys) -> None:
    _sandbox_chetana(tmp_path, monkeypatch)
    state_root = tmp_path / "state"
    commons_root = _temp_commons(tmp_path / "ontology")
    cli.main(
        [
            "ingest",
            "Agent runtime idea spark memory routing note.",
            "--state-root",
            str(state_root),
            "--commons-root",
            str(commons_root),
            "--created-at",
            FIXED_NOW,
            "--json",
        ]
    )
    capsys.readouterr()

    code = cli.main(["health", "--state-root", str(state_root), "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["input_receipts"] == 1
    assert payload["candidates"]["total"] == 1
    assert payload["lifecycle"]["total"] == 1
