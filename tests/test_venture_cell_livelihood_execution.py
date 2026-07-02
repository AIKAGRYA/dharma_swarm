from __future__ import annotations

import json

from dharma_swarm.venture_cell.livelihood_loom.execution import (
    bootstrap_summary,
    run_safe_bootstrap,
)


def test_safe_bootstrap_registers_ceo_spawns_lanes_scores_candidates_and_drafts_action(tmp_path):
    csv_path = tmp_path / "enablers.csv"
    csv_path.write_text(
        "rank,name,domain,subdomain,country,website,source_url,informal_economy_role\n"
        "1,Example Pay,finance_rails,mobile_payment,India,https://pay.example,https://source.example,payment rails for small merchants\n"
        "2,Market Link,market_access,buyer_discovery,Kenya,https://market.example,https://source2.example,buyer access for micro sellers\n",
        encoding="utf-8",
    )

    receipt = run_safe_bootstrap(
        dharma_home=tmp_path / ".dharma",
        repo_root=tmp_path,
        agents_dir=tmp_path / "agents",
        candidate_csv=csv_path,
        candidate_limit=1000,
        receipt_dir=tmp_path / "receipts",
        external_action_log=tmp_path / "actions.jsonl",
    )

    assert receipt["agent_uid"] == "livelihood_loom_ceo"
    assert receipt["candidate_source"]["loaded_count"] == 2
    assert len(receipt["mission"]["lanes"]) == 6
    assert receipt["scored_candidates"][0]["score"] > 0
    assert receipt["external_action"]["status"] == "drafted"
    assert receipt["safety_boundary"]["external_contacts_made"] is False
    assert receipt["safety_boundary"]["payments_made"] is False
    assert (tmp_path / "receipts" / "latest.json").exists()
    assert (tmp_path / ".dharma" / "external_agents" / "livelihood_loom_ceo" / "receipts").exists()

    summary = bootstrap_summary(receipt)
    assert summary["candidate_count"] == 2
    assert summary["external_action_status"] == "drafted"


def test_safe_bootstrap_receipts_missing_candidate_source_without_fabricating_action(tmp_path):
    receipt = run_safe_bootstrap(
        dharma_home=tmp_path / ".dharma",
        repo_root=tmp_path,
        agents_dir=tmp_path / "agents",
        candidate_csv=tmp_path / "missing.csv",
        receipt_dir=tmp_path / "receipts",
        external_action_log=tmp_path / "actions.jsonl",
        write_canonical_onboarding=False,
    )
    assert receipt["candidate_source"]["status"] == "missing"
    assert receipt["candidate_source"]["loaded_count"] == 0
    assert receipt["external_action"] is None


def test_cli_run_bootstrap_json(capsys, tmp_path):
    from dharma_swarm.venture_cell.livelihood_loom.cli import main

    csv_path = tmp_path / "enablers.csv"
    csv_path.write_text(
        "name,sector,geography,enablement_levers,source_refs\n"
        "Example Pay,finance,India,payments,https://source.example\n"
        "Market Link,commerce,Kenya,buyer access,https://source2.example\n",
        encoding="utf-8",
    )

    assert main(
        [
            "run-bootstrap",
            "--dharma-home",
            str(tmp_path / ".dharma"),
            "--repo-root",
            str(tmp_path),
            "--agents-dir",
            str(tmp_path / "agents"),
            "--candidate-csv",
            str(csv_path),
            "--receipt-dir",
            str(tmp_path / "receipts"),
            "--external-action-log",
            str(tmp_path / "actions.jsonl"),
            "--no-onboarding",
            "--json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidate_source"]["loaded_count"] == 2
    assert payload["external_action"]["status"] == "drafted"
