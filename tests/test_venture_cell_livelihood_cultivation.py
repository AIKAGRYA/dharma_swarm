from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.venture_cell.livelihood_loom.cli import main
from dharma_swarm.venture_cell.livelihood_loom.enablement_packets import (
    build_enablement_packets,
)
from dharma_swarm.venture_cell.livelihood_loom.evidence import run_cultivation_cycle
from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    write_top_50_reports,
)
from dharma_swarm.venture_cell.livelihood_loom.promotion import (
    build_promotion_readiness,
)
from dharma_swarm.venture_cell.livelihood_loom.safety import build_safety_review


def test_prioritization_uses_scores_not_alphabetical_order(tmp_path):
    csv_path = _cultivation_csv(tmp_path)
    outputs = write_top_50_reports(
        candidate_csv=csv_path,
        report_root=tmp_path / "reports",
        candidate_limit=20,
        top_n=7,
    )
    payload = json.loads(Path(outputs["top_50_json"]).read_text(encoding="utf-8"))
    names = [item["name"] for item in payload["candidates"]]

    assert names[0] == "Zeta Pay"
    assert names != sorted(names)
    assert payload["alphabetical_drift_fixed"] is True
    first = payload["candidates"][0]
    assert {"source_rank", "candidate_score", "confidence"} <= set(
        first["score_components"]
    )

    wedges = json.loads(Path(outputs["wedges_json"]).read_text(encoding="utf-8"))
    assert wedges["wedge_count"] == 3
    assert all(item["roi_thesis"] for item in wedges["wedges"])


def test_safety_review_flags_blocked_and_review_classes(tmp_path):
    csv_path = _cultivation_csv(tmp_path)
    top = write_top_50_reports(
        candidate_csv=csv_path,
        report_root=tmp_path / "reports",
        candidate_limit=20,
        top_n=7,
    )
    safety = build_safety_review(
        top_50_path=top["top_50_json"],
        report_root=tmp_path / "reports",
    )
    payload = json.loads(Path(safety["safety_review_json"]).read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in payload["reviews"]}

    assert by_name["Data Broker"]["safety_status"] == "blocked"
    assert "data_sale" in by_name["Data Broker"]["flags"]
    assert by_name["Mobi Loan"]["safety_status"] == "needs_review"
    assert "high_fee_lending" in by_name["Mobi Loan"]["flags"]
    assert by_name["Gig Courier"]["safety_status"] == "needs_review"
    assert "exploitative_gig_platform" in by_name["Gig Courier"]["flags"]


def test_packets_and_full_cycle_write_draft_only_receipts(tmp_path):
    csv_path = _cultivation_csv(tmp_path)
    top = write_top_50_reports(
        candidate_csv=csv_path,
        report_root=tmp_path / "reports",
        candidate_limit=20,
        top_n=7,
    )
    safety = build_safety_review(
        top_50_path=top["top_50_json"],
        report_root=tmp_path / "reports",
    )
    packets = build_enablement_packets(
        safety_review_path=safety["safety_review_json"],
        wedges_path=top["wedges_json"],
        report_root=tmp_path / "reports",
    )
    assert packets["packet_count"] == 5
    for index in range(1, 6):
        packet = tmp_path / "reports" / "enablement_packets" / f"packet_{index:02d}.json"
        payload = json.loads(packet.read_text(encoding="utf-8"))
        assert {
            "target_wedge",
            "beneficiary",
            "friction",
            "candidate_partners",
            "sponsor_value",
            "welfare_metric",
            "evidence_refs",
            "risks",
            "next_safe_action",
        } <= set(payload)

    cycle = run_cultivation_cycle(
        candidate_csv=csv_path,
        candidate_limit=20,
        top_n=7,
        report_root=tmp_path / "cycle_reports",
        dharma_home=tmp_path / ".dharma",
        external_action_log=tmp_path / "actions.jsonl",
    )
    assert cycle["status"] == "cultivation_ready_provider_blocked"
    assert cycle["provider_green"] is False
    assert cycle["safety_boundary"]["external_action_status"] == "risk_reviewed"
    action = json.loads(
        (tmp_path / "cycle_reports" / "demand" / "external_action_draft.json").read_text(
            encoding="utf-8"
        )
    )
    assert action["status"] == "risk_reviewed"
    assert action["approved"] is False
    assert action["executed"] is False
    assert (tmp_path / "cycle_reports" / "cycles" / "latest.json").exists()


def test_cultivation_cycle_cli_json(tmp_path, capsys):
    csv_path = _cultivation_csv(tmp_path)
    assert (
        main(
            [
                "run-cultivation-cycle",
                "--candidate-csv",
                str(csv_path),
                "--candidate-limit",
                "20",
                "--top-n",
                "7",
                "--report-root",
                str(tmp_path / "reports"),
                "--dharma-home",
                str(tmp_path / ".dharma"),
                "--external-action-log",
                str(tmp_path / "actions.jsonl"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "cultivation_ready_provider_blocked"
    assert payload["provider_readiness_gap"]["status"] == "red"
    assert payload["definition_of_done"]["enablement_packets"] == 5


def test_individual_cultivation_cli_commands(tmp_path, capsys):
    csv_path = _cultivation_csv(tmp_path)
    report_root = tmp_path / "reports"
    assert (
        main(
            [
                "top-50",
                "--candidate-csv",
                str(csv_path),
                "--candidate-limit",
                "20",
                "--top-n",
                "7",
                "--report-root",
                str(report_root),
                "--json",
            ]
        )
        == 0
    )
    top_payload = json.loads(capsys.readouterr().out)
    assert Path(top_payload["top_50_json"]).exists()

    assert (
        main(
            [
                "safety-review",
                "--top-50",
                top_payload["top_50_json"],
                "--report-root",
                str(report_root),
                "--json",
            ]
        )
        == 0
    )
    safety_payload = json.loads(capsys.readouterr().out)
    assert Path(safety_payload["safety_review_json"]).exists()

    assert (
        main(
            [
                "build-packets",
                "--safety-review",
                safety_payload["safety_review_json"],
                "--wedges",
                top_payload["wedges_json"],
                "--report-root",
                str(report_root),
                "--json",
            ]
        )
        == 0
    )
    packet_payload = json.loads(capsys.readouterr().out)
    assert packet_payload["packet_count"] == 5

    assert (
        main(
            [
                "draft-demand",
                "--top-50",
                top_payload["top_50_json"],
                "--safety-review",
                safety_payload["safety_review_json"],
                "--wedges",
                top_payload["wedges_json"],
                "--packets-dir",
                packet_payload["packet_dir"],
                "--report-root",
                str(report_root),
                "--dharma-home",
                str(tmp_path / ".dharma"),
                "--external-action-log",
                str(tmp_path / "actions.jsonl"),
                "--json",
            ]
        )
        == 0
    )
    demand_payload = json.loads(capsys.readouterr().out)
    assert demand_payload["external_action_status"] == "risk_reviewed"
    assert demand_payload["sent"] is False


def test_promotion_readiness_builds_draft_only_external_gates(tmp_path):
    csv_path = _cultivation_csv(tmp_path)
    cycle = run_cultivation_cycle(
        candidate_csv=csv_path,
        candidate_limit=20,
        top_n=7,
        report_root=tmp_path / "reports",
        dharma_home=tmp_path / ".dharma",
        external_action_log=tmp_path / "actions.jsonl",
    )
    assert cycle["provider_green"] is False

    promotion = build_promotion_readiness(
        report_root=tmp_path / "reports",
        dharma_home=tmp_path / ".dharma",
        external_action_log=tmp_path / "promotion_actions.jsonl",
    )
    assert promotion["steps"]["1_internal_homepage"] == "implemented_dashboard_route"
    assert promotion["steps"]["5_first_sponsor_target"]["name"] == "Accion"
    assert promotion["safety_boundary"]["outreach_action_status"] == "risk_reviewed"
    assert promotion["safety_boundary"]["outreach_approved"] is False
    assert promotion["safety_boundary"]["outreach_executed"] is False

    acted_gate = json.loads(
        (tmp_path / "reports" / "promotion" / "external_acted_receipt_gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert acted_gate["complete"] is False
    assert acted_gate["not_fabricated"] is True


def test_promotion_cli_json(tmp_path, capsys):
    csv_path = _cultivation_csv(tmp_path)
    assert (
        main(
            [
                "run-cultivation-cycle",
                "--candidate-csv",
                str(csv_path),
                "--candidate-limit",
                "20",
                "--top-n",
                "7",
                "--report-root",
                str(tmp_path / "reports"),
                "--dharma-home",
                str(tmp_path / ".dharma"),
                "--external-action-log",
                str(tmp_path / "actions.jsonl"),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "build-promotion-kit",
                "--report-root",
                str(tmp_path / "reports"),
                "--dharma-home",
                str(tmp_path / ".dharma"),
                "--external-action-log",
                str(tmp_path / "promotion_actions.jsonl"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["steps"]["6_external_acted_receipt"] == "blocked_pending_real_external_act"
    assert payload["safety_boundary"]["external_contacts_made"] is False
    assert Path(payload["artifacts"]["sponsor_one_pager"]).exists()


def _cultivation_csv(tmp_path) -> Path:
    csv_path = tmp_path / "enablers.csv"
    csv_path.write_text(
        "rank,name,domain,subdomain,country,website,source_url,source_type,"
        "source_tag,all_source_tags,all_subdomains,description,"
        "informal_economy_role,candidate_score,confidence,cultivation_priority\n"
        "1,Zeta Pay,finance_rails,mobile_payment,India,https://zeta.example,"
        "https://source.example/zeta,wikidata_structured_tag,mobile payment,"
        "mobile payment,mobile_payment,merchant wallet,"
        "mobile acceptance for micro merchants and workers,10,high_candidate,"
        "B_research_next\n"
        "2,Alpha Market,commerce_rails,online_marketplace,Kenya,"
        "https://alpha.example,https://source.example/alpha,"
        "wikidata_structured_tag,online marketplace,online marketplace,"
        "online_marketplace,buyer marketplace,buyer access for micro sellers,"
        "9,high_candidate,B_research_next\n"
        "3,Mobi Loan,finance_rails,microfinance,Indonesia,"
        "https://loan.example,https://source.example/loan,"
        "wikidata_structured_tag,microfinance,microfinance,microfinance,"
        "small-ticket lending,credit and loan rails for informal workers,"
        "9,medium_candidate,B_research_next\n"
        "4,Gig Courier,labor_rails,food_delivery,India,https://gig.example,"
        "https://source.example/gig,wikidata_structured_tag,food delivery,"
        "food delivery,food_delivery,food delivery platform,"
        "demand and dispatch rails for couriers,9,medium_candidate,"
        "B_research_next\n"
        "5,Local Logistics,logistics_rails,logistics_company,Nigeria,"
        "https://logistics.example,https://source.example/logistics,"
        "wikidata_structured_tag,logistics company,logistics company,"
        "logistics_company,local delivery network,"
        "delivery reliability for micro sellers,8,medium_candidate,"
        "B_research_next\n"
        "6,Data Broker,commerce_rails,online_marketplace,United States,"
        "https://data.example,https://source.example/data,"
        "wikidata_structured_tag,online marketplace,online marketplace,"
        "online_marketplace,lead list marketplace,"
        "data sale and lead list for sellers,10,high_candidate,"
        "B_research_next\n"
        "7,Aardvark Backlog,finance_rails,fintech,United States,"
        "https://backlog.example,https://source.example/backlog,"
        "wikidata_structured_tag,fintech,fintech,fintech,"
        "general fintech,financial tools for small earners,5,low_candidate,"
        "C_backlog\n",
        encoding="utf-8",
    )
    return csv_path
