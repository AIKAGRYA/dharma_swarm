from __future__ import annotations

import json
import sqlite3

from dharma_swarm.langgraph_parity.benchmark import (
    ProviderProfile,
    REQUIRED_CASE_TAGS,
    default_benchmark_tasks,
    record_benchmark_runtime_receipt,
    run_benchmark,
    write_report,
)
from dharma_swarm.langgraph_parity.isolation import (
    SimulatedMemoryKernel,
    SimulatedSemanticCommons,
    collect_isolation_failures,
    default_distractor_packs,
    default_isolation_policy,
)


def test_default_distractor_packs_have_separate_domains_tools_and_instructions() -> None:
    packs = default_distractor_packs()

    domains = [pack.domain for pack in packs]
    agents = [pack.agent_name for pack in packs]
    instructions = [pack.instructions for pack in packs]
    tool_names = [tool.name for pack in packs for tool in pack.tools]

    assert len(packs) >= 6
    assert len(set(domains)) == len(packs)
    assert len(set(agents)) == len(packs)
    assert len(set(instructions)) == len(packs)
    assert len(set(tool_names)) == len(tool_names)
    for pack in packs:
        assert pack.tools
        assert all(tool.domain == pack.domain for tool in pack.tools)


def test_agent_view_only_sees_selected_domain_tools_and_allowed_handoffs() -> None:
    policy = default_isolation_policy()
    commons = SimulatedSemanticCommons(policy.packs, return_all=True)
    memory = SimulatedMemoryKernel.from_packs(policy.packs)
    climate_pack = policy.pack_for_domain("climate_ops")

    view = policy.prepare_agent_view(
        agent_name="climate_agent",
        prompt="mangrove carbon restoration budget",
        selected_domains=("climate_ops",),
        semantic_commons=commons,
        memory_kernel=memory,
    )

    assert view.instructions == (climate_pack.instructions,)
    assert set(view.tool_names) == set(climate_pack.tool_names) | {
        "transfer_to_finance_agent"
    }
    assert view.admission.admitted_domains == ("climate_ops",)
    assert "finance_risk" in view.admission.rejected_domains
    assert "legal_policy" in view.admission.rejected_domains
    assert tuple(fact.domain for fact in view.memory_facts) == ("climate_ops",)
    assert collect_isolation_failures(view) == ()


def test_semantic_commons_and_memory_kernel_cannot_reintroduce_irrelevant_packs() -> None:
    policy = default_isolation_policy()
    commons = SimulatedSemanticCommons(policy.packs, return_all=True)
    memory = SimulatedMemoryKernel.from_packs(policy.packs)

    finance_view = policy.prepare_agent_view(
        agent_name="finance_agent",
        prompt="budget with contract medical travel distractors",
        selected_domains=("finance_risk",),
        semantic_commons=commons,
        memory_kernel=memory,
    )

    visible_non_handoff_domains = {
        tool.domain for tool in finance_view.tools if tool.domain != "handoff"
    }
    assert visible_non_handoff_domains == {"finance_risk"}
    assert {fact.domain for fact in finance_view.memory_facts} == {"finance_risk"}
    assert "legal_policy" in finance_view.admission.rejected_domains
    assert "medical_triage" in finance_view.admission.rejected_domains

    legal_view = policy.prepare_agent_view(
        agent_name="legal_agent",
        prompt="contract jurisdiction policy check",
        selected_domains=("legal_policy",),
        semantic_commons=commons,
        memory_kernel=memory,
    )
    assert legal_view.admission.admitted_domains == ("legal_policy",)
    assert {fact.domain for fact in legal_view.memory_facts} == {"legal_policy"}
    assert collect_isolation_failures(finance_view) == ()
    assert collect_isolation_failures(legal_view) == ()


def test_benchmark_suite_reports_required_metrics_and_multihop_comparison() -> None:
    policy = default_isolation_policy()
    report = run_benchmark(
        policy=policy,
        semantic_commons=SimulatedSemanticCommons(policy.packs, return_all=True),
        memory_kernel=SimulatedMemoryKernel.from_packs(policy.packs),
        provider_profile=ProviderProfile(
            provider="test",
            model="deterministic-test",
            cost_per_1k_tokens=0.001,
        ),
    )

    assert report.distractor_domain_count >= 6
    assert len(default_benchmark_tasks()) >= 25
    assert any(task.requires_multi_hop for task in default_benchmark_tasks())
    assert report.summary["multi_hop_task_count"] >= 1
    assert report.summary["task_count"] >= 25
    assert report.summary["case_tags_complete"] is True
    assert set(report.summary["required_case_tags"]) == set(REQUIRED_CASE_TAGS)
    coverage = report.summary["case_tag_coverage"]
    assert all(coverage[tag] > 0 for tag in REQUIRED_CASE_TAGS)

    for result in report.results:
        assert 0.0 <= result.score <= 1.0
        assert result.token_estimate > 0
        assert result.cost_estimate_usd >= 0
        assert result.latency_ms > 0
        assert result.handoff_count >= 0
        assert result.provider == "test"
        assert result.model == "deterministic-test"
        assert isinstance(result.failure_classes, tuple)

    by_task_mode = {
        (result.task_id, result.mode): result
        for result in report.results
    }
    single = by_task_mode[("climate_finance_multihop", "single_agent")]
    swarm = by_task_mode[("climate_finance_multihop", "swarm")]
    supervisor = by_task_mode[("climate_finance_multihop", "supervisor")]

    assert "missing_required_domain" in single.failure_classes
    assert single.score < swarm.score
    assert single.score < supervisor.score
    assert swarm.handoff_count == 1
    assert supervisor.handoff_count == 2
    assert swarm.agents == ("climate_agent", "finance_agent")
    assert supervisor.agents == ("climate_agent", "finance_agent")
    assert "isolation_leak" not in swarm.failure_classes
    assert "isolation_leak" not in supervisor.failure_classes


def test_benchmark_report_writes_repeatable_json_and_markdown(tmp_path) -> None:
    policy = default_isolation_policy()
    report = run_benchmark(
        policy=policy,
        semantic_commons=SimulatedSemanticCommons(policy.packs, return_all=True),
        memory_kernel=SimulatedMemoryKernel.from_packs(policy.packs),
    )

    json_path, markdown_path = write_report(report, tmp_path)
    first_json = json_path.read_text(encoding="utf-8")
    write_report(report, tmp_path)
    second_json = json_path.read_text(encoding="utf-8")
    data = json.loads(first_json)

    assert first_json == second_json
    assert json_path.exists()
    assert markdown_path.exists()
    assert data["deterministic"] is True
    assert data["summary"]["distractor_domain_count"] >= 6
    assert {
        "score",
        "token_estimate",
        "cost_estimate_usd",
        "latency_ms",
        "handoff_count",
        "provider",
        "model",
        "failure_classes",
    }.issubset(data["results"][0])
    assert "Provider/model" in markdown_path.read_text(encoding="utf-8")


def test_benchmark_runtime_receipt_records_canonical_identity_and_idempotency(
    tmp_path,
) -> None:
    report = run_benchmark(
        provider_profile=ProviderProfile(
            provider="test-provider",
            model="test-model",
            cost_per_1k_tokens=0.001,
        ),
        mission_id="test-langgraph-parity-mission",
    )

    json_path, _markdown_path = write_report(report, tmp_path)
    receipt_payload = json.loads(
        (tmp_path / "benchmark_receipt.json").read_text(encoding="utf-8")
    )
    artifact_id = receipt_payload["attributes"]["artifact_id"]
    runtime_db = tmp_path / "runtime.db"

    runtime_receipt = record_benchmark_runtime_receipt(
        report,
        artifact_id=artifact_id,
        artifact_path=json_path,
        runtime_db_path=runtime_db,
    )
    duplicate_receipt = record_benchmark_runtime_receipt(
        report,
        artifact_id=artifact_id,
        artifact_path=json_path,
        runtime_db_path=runtime_db,
    )

    assert duplicate_receipt.receipt_id == runtime_receipt.receipt_id
    with sqlite3.connect(runtime_db) as db:
        receipt_row = db.execute(
            "SELECT receipt_type, status, run_id, task_id, agent_id,"
            " idempotency_key, side_effect_key, payload_json"
            " FROM runtime_receipts WHERE receipt_id = ?",
            (runtime_receipt.receipt_id,),
        ).fetchone()
        idempotency_row = db.execute(
            "SELECT status, result_receipt_id, metadata_json"
            " FROM idempotency_records"
            " WHERE idempotency_key = ? AND side_effect_key = ?",
            (runtime_receipt.idempotency_key, runtime_receipt.side_effect_key),
        ).fetchone()
        identity_row = db.execute(
            "SELECT artifact_id, source"
            " FROM execution_identities WHERE run_id = ?",
            (runtime_receipt.run_id,),
        ).fetchone()
        claim_by_run_identity = db.execute(
            "SELECT claim_id FROM execution_identities WHERE run_id = ?",
            (runtime_receipt.run_id,),
        ).fetchone()[0]
        claim_row = db.execute(
            "SELECT status, trace_id, metadata_json"
            " FROM task_claims WHERE claim_id = ?",
            (claim_by_run_identity,),
        ).fetchone()
        run_row = db.execute(
            "SELECT status, current_artifact_id, completed_at, metadata_json"
            " FROM delegation_runs WHERE run_id = ?",
            (runtime_receipt.run_id,),
        ).fetchone()
        artifact_row = db.execute(
            "SELECT artifact_kind, run_id, task_id, trace_id, payload_path,"
            " manifest_path, checksum"
            " FROM artifact_records WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        stable_receipt_count = db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
            (runtime_receipt.receipt_id,),
        ).fetchone()[0]

    assert receipt_row is not None
    payload = json.loads(receipt_row[7])
    assert receipt_row[0] == "delegation_run"
    assert receipt_row[1] == "completed"
    assert receipt_row[3] == report.suite_name
    assert receipt_row[4] == "langgraph_parity_benchmark"
    assert receipt_row[5] == runtime_receipt.idempotency_key
    assert receipt_row[6] == runtime_receipt.side_effect_key
    assert payload["mission_id"] == "test-langgraph-parity-mission"
    assert payload["artifact_id"] == artifact_id
    assert payload["artifact_refs"] == [artifact_id]
    assert payload["provider"] == "test-provider"
    assert payload["model"] == "test-model"
    assert payload["provider_execution"] is False
    assert payload["provider_model_applicability"] == "not_applicable"
    assert payload["no_provider_model_reason"]
    assert payload["input_tokens"] > 0
    assert payload["cost_estimate_usd"] > 0
    assert idempotency_row is not None
    assert idempotency_row[0] == "completed"
    assert idempotency_row[1] == runtime_receipt.receipt_id
    assert json.loads(idempotency_row[2])["artifact_id"] == artifact_id
    assert identity_row == (artifact_id, "langgraph_parity.benchmark")
    assert claim_row is not None
    assert claim_row[0] == "completed"
    assert claim_row[1] == runtime_receipt.trace_id
    claim_metadata = json.loads(claim_row[2])
    assert claim_metadata["mission_id"] == "test-langgraph-parity-mission"
    assert run_row is not None
    assert run_row[0] == "completed"
    assert run_row[1] == artifact_id
    assert run_row[2]
    run_metadata = json.loads(run_row[3])
    assert run_metadata["provider"] == "test-provider"
    assert artifact_row is not None
    assert artifact_row[0] == "langgraph_parity_benchmark_report"
    assert artifact_row[1] == runtime_receipt.run_id
    assert artifact_row[2] == report.suite_name
    assert artifact_row[3] == runtime_receipt.trace_id
    assert artifact_row[4] == str(json_path)
    assert artifact_row[5].endswith("benchmark_receipt.json")
    assert artifact_row[6] == artifact_id
    assert stable_receipt_count == 1
