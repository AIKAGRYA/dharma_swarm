"""Executable contracts for the ten-node autocatalytic A2A portfolio."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.autocatalytic_contracts import PROMOTION_CHECKS_BY_NODE
from dharma_swarm.autocatalytic_portfolio import (
    LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    LocalReceiptConsistencyCheck,
    PortfolioContractError,
    REQUIRED_NODE_COUNT,
    SemanticPromotionError,
    StructuralCycleCheck,
    StructuralHop,
    TransportAck,
    _build_catalytic_graph,
    _check_structural_cycle_witness,
    _declared_source_digest,
    _digest,
    _implementation_fingerprint,
    _project_evidence_for,
    _semantic_seed,
    _source_snapshot,
    build_structural_hop,
    load_latest_cycle,
    load_portfolio_manifest,
    run_local_cycle,
    validate_portfolio,
    verify_cycle_witness,
)


_ARENA_RECEIPT = Path("reports/governance/arena/arena_truth_receipt.json")
_DARSHAN_CHARTER = Path("docs/plans/DARSHAN_CHARTER_2026-07-12.md")
_DARSHAN_EFFECT_RECEIPT = Path("reports/darshan/issue_one_receipt.json")


@pytest.fixture(scope="module")
def adversarial_cycle(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, dict]:
    """One fresh cycle shared by immutable adversarial witness projections."""

    root = tmp_path_factory.mktemp("autocatalytic-adversarial")
    portfolio = load_portfolio_manifest()
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=root / "witness",
        runtime_db=root / "runtime.db",
        turns=2,
        persist=True,
    )
    return portfolio, witness


def _patch_adapter_repo_root(
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
) -> None:
    """Patch the implementation owner, whether the facade re-exports it or not."""

    owners = {
        inspect.getmodule(_source_snapshot),
        inspect.getmodule(_project_evidence_for),
    }
    for owner in owners:
        assert owner is not None
        monkeypatch.setattr(owner, "_REPO_ROOT", repo_root)


def _write_path(root: Path, relative: Path, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _adapter_task(*, node_id: str, hop: dict | None = None) -> A2ATask:
    task_id = str(hop["task_id"]) if hop is not None else f"task_{node_id}_probe"
    run_id = str(hop["run_id"]) if hop is not None else f"run_{node_id}_probe"
    return A2ATask(
        id=task_id,
        to_agent=node_id,
        trace_id="trace_adapter_probe",
        metadata={"execution_identity": {"run_id": run_id}},
    )


def _target_hop_context(
    portfolio: dict,
    witness: dict,
    *,
    node_id: str,
    turn: int,
) -> tuple[dict, dict, dict, A2ATask]:
    nodes = {str(row["id"]): row for row in portfolio["nodes"]}
    node = nodes[node_id]
    hops = witness["proofs"][turn]["hops"]
    hop = next(row for row in hops if row["node_id"] == node_id)
    ordinal = int(node["ordinal"])
    if ordinal > 1:
        predecessor = hops[ordinal - 2]["artifact"]
    elif turn > 0:
        predecessor = witness["proofs"][turn - 1]["hops"][-1]["artifact"]
    else:
        predecessor = witness["seed_artifact"]
    return node, hop, predecessor, _adapter_task(node_id=node_id, hop=hop)


def test_declared_portfolio_is_exactly_one_ten_node_autocatalytic_set() -> None:
    portfolio = load_portfolio_manifest()
    assert validate_portfolio(portfolio) == []
    nodes = sorted(portfolio["nodes"], key=lambda node: node["ordinal"])
    assert len(nodes) == REQUIRED_NODE_COUNT
    assert [node["ordinal"] for node in nodes] == list(range(1, 11))

    graph = _build_catalytic_graph(portfolio)
    sets = graph.detect_autocatalytic_sets()
    assert len(sets) == 1
    assert set(sets[0]) == {node["id"] for node in nodes}


def test_every_active_project_is_bound_into_the_metabolism() -> None:
    portfolio = load_portfolio_manifest()
    bound = {
        project for node in portfolio["nodes"] for project in node["project_bindings"]
    }
    active_data = yaml.safe_load(
        Path("docs/governance/ACTIVE_TRACK.yaml").read_text(encoding="utf-8")
    )
    active = {
        row["id"]
        for row in active_data["active_tracks"]
        if row.get("status") == "ACTIVE"
    }
    assert bound == active


def test_two_turn_local_a2a_cycle_closes_with_twenty_verified_hops(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    assert witness["structural_proof_valid"] is True
    assert witness["local_receipt_consistency_valid"] is True
    assert witness["execution_evidence_scope"] == LOCAL_RECEIPT_CONSISTENCY_SCOPE
    assert witness["execution_provenance_authenticated"] is False
    assert witness["completed_hops"] == witness["required_hops"] == 10
    assert witness["turns_proven"] == 2
    assert witness["transport_evidence"] == "in_process_local"
    assert witness["claim_ceiling"] == "local_rehearsal"
    assert witness["external_effects_proven"] is False
    assert len(witness["proofs"]) == 2
    assert all(len(proof["hops"]) == 10 for proof in witness["proofs"])
    assert witness["proofs"][1]["start_hash"] == witness["proofs"][0]["end_hash"]

    consistency = verify_cycle_witness(witness, portfolio, runtime_db=runtime_db)
    assert consistency.valid is True, consistency.error
    assert consistency.modality == LOCAL_RECEIPT_CONSISTENCY_SCOPE
    assert consistency.independently_authenticated is False
    card_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "witness" / "cards").glob("*.json"))
    ]
    assert {card["name"] for card in card_payloads} == {
        node["id"] for node in portfolio["nodes"]
    }
    assert all(
        card["skills"][0]["name"] == f"autocatalytic.{card['name']}"
        for card in card_payloads
    )
    task_ids = {hop["task_id"] for proof in witness["proofs"] for hop in proof["hops"]}
    assert len(task_ids) == 20


def test_persisted_cycle_records_task_and_cycle_receipts(tmp_path: Path) -> None:
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    assert witness["runtime_receipts_recorded"] is True
    with sqlite3.connect(runtime_db) as db:
        task_count = db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_type = 'a2a_task'"
        ).fetchone()[0]
        semantic_hop_count = db.execute(
            "SELECT COUNT(*) FROM runtime_receipts "
            "WHERE receipt_type = 'autocatalytic_hop_proof'"
        ).fetchone()[0]
        cycle_rows = db.execute(
            "SELECT status, payload_json FROM runtime_receipts "
            "WHERE receipt_type = 'autocatalytic_cycle_proof'"
        ).fetchall()
    assert task_count == 20
    assert semantic_hop_count == 20
    assert len(cycle_rows) == 1
    assert cycle_rows[0][0] == "completed"
    payload = json.loads(cycle_rows[0][1])
    assert payload["completed_hops"] == 10
    assert payload["external_effects_proven"] is False


def test_input_required_cannot_promote() -> None:
    portfolio = load_portfolio_manifest()
    node = sorted(portfolio["nodes"], key=lambda row: row["ordinal"])[0]
    predecessor = {
        "artifact_hash": "a" * 64,
        "message_id": "msg_predecessor",
        "turn": -1,
        "visited_nodes": [],
    }
    task = A2ATask(
        id="task_nonterminal",
        to_agent=node["id"],
        status=A2ATaskStatus.INPUT_REQUIRED,
        trace_id="trc_nonterminal",
        metadata={"causation_id": "msg_predecessor"},
    )
    with pytest.raises(SemanticPromotionError, match="not exact completed"):
        build_structural_hop(
            task,
            node=node,
            predecessor=predecessor,
            cycle_id="cycle_nonterminal",
            trace_id="trc_nonterminal",
            turn=0,
        )


def test_transport_ack_has_no_semantic_promotion_surface() -> None:
    ack = TransportAck(task_id="task_1", transport="nats", accepted=True)
    assert ack.accepted is True
    assert not hasattr(ack, "to_completed_hop")
    assert not hasattr(ack, "artifact")


def test_tampered_semantic_artifact_invalidates_persisted_witness(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    witness["proofs"][1]["hops"][4]["artifact"]["output_signal"] = "forged"
    consistency = verify_cycle_witness(witness, portfolio, runtime_db=runtime_db)
    assert consistency.valid is False
    assert "artifact hash is invalid" in consistency.error


def test_structurally_valid_witness_cannot_promote_without_runtime_receipts(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    consistency = verify_cycle_witness(
        witness,
        portfolio,
        runtime_db=tmp_path / "missing-runtime.db",
    )
    assert consistency.valid is False
    assert "runtime receipt database is missing" in consistency.error


def test_semantic_cycle_proof_cannot_run_without_receipt_persistence(
    tmp_path: Path,
) -> None:
    with pytest.raises(PortfolioContractError, match="requires persisted"):
        run_local_cycle(witness_dir=tmp_path, persist=False)


def test_structural_hop_constructor_rejects_invalid_structural_value() -> None:
    with pytest.raises(SemanticPromotionError, match="artifact hash is invalid"):
        StructuralHop(
            turn=0,
            ordinal=1,
            node_id="world_signal_supply",
            task_id="task_forged",
            run_id="run_forged",
            idempotency_key="idem_forged",
            a2a_receipt_id="rr_forged_a2a",
            semantic_receipt_id="rr_forged_semantic",
            status="completed",
            artifact={"artifact_hash": "0" * 64},
            artifact_hash="0" * 64,
            predecessor_hash="0" * 64,
            completion_hash="0" * 64,
        )


def test_manifest_contract_locks_pages_promotions_and_cross_feeds() -> None:
    portfolio = load_portfolio_manifest()
    assert {
        node["id"]: tuple(node["promotion_checks"]) for node in portfolio["nodes"]
    } == PROMOTION_CHECKS_BY_NODE

    duplicated_pages = copy.deepcopy(portfolio)
    for node in duplicated_pages["nodes"]:
        node["page"] = "/dashboard/organism/shared"
    assert any(
        "page must be" in error for error in validate_portfolio(duplicated_pages)
    )

    ack_promotes = copy.deepcopy(portfolio)
    ack_promotes["promotion_rule"]["transport_ack_promotes"] = True
    assert any(
        "transport_ack_promotes" in error for error in validate_portfolio(ack_promotes)
    )

    untyped_cross_feed = copy.deepcopy(portfolio)
    untyped_cross_feed["nodes"][0]["cross_outputs"] = []
    assert any(
        "cross-feed" in error for error in validate_portfolio(untyped_cross_feed)
    )

    duplicate_bus_key = copy.deepcopy(portfolio)
    duplicate_bus_key["nodes"][6]["cross_outputs"][0]["signal"] = "oracle_evidence"
    duplicate_bus_key["nodes"][2]["cross_inputs"][0]["signal"] = "oracle_evidence"
    for edge in duplicate_bus_key["edges"]:
        if edge["source"] == "assurance_merge":
            edge["signal"] = "oracle_evidence"
    assert any(
        "globally unique" in error for error in validate_portfolio(duplicate_bus_key)
    )


def test_stale_verifier_and_turn_chain_cannot_promote(tmp_path: Path) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )

    stale = copy.deepcopy(witness)
    stale["implementation"]["verifier_sha256"] = "0" * 64
    consistency = verify_cycle_witness(stale, portfolio, runtime_db=runtime_db)
    assert consistency.valid is False
    assert "fingerprint" in consistency.error

    broken_turn = copy.deepcopy(witness)
    broken_turn["proofs"][1]["start_hash"] = "0" * 64
    consistency = verify_cycle_witness(broken_turn, portfolio, runtime_db=runtime_db)
    assert consistency.valid is False
    assert "turn-to-turn" in consistency.error


def test_project_adapters_consume_every_hop_and_preserve_negative_modality(
    tmp_path: Path,
) -> None:
    witness = run_local_cycle(
        witness_dir=tmp_path / "witness",
        runtime_db=tmp_path / "runtime.db",
        turns=2,
        persist=True,
    )
    first_turn = witness["proofs"][0]["hops"]
    evidence = [hop["artifact"]["project_evidence"] for hop in first_turn]
    assert len({row["adapter_id"] for row in evidence}) == 10
    assert all(
        row["schema_version"] == "dharma.autocatalytic.project_evidence.v1"
        for row in evidence
    )
    assert all(row["side_effects_performed"] is False for row in evidence)
    assert all(row["external_effects_proven"] is False for row in evidence)
    assert all(row["signal"]["promotion_authorized"] is False for row in evidence)
    assert all(
        gate["satisfied"] is False
        and gate["state"] == "blocked"
        and gate["authority_upgrade_authorized"] is False
        for gate in (row["promotion_gate"] for row in evidence)
    )
    assert all(
        source["declared_digest_valid"] is not False
        for row in evidence
        for source in row["sources"]
    )
    assert [row["signal"]["state"] for row in evidence[4:]] == [
        "candidate_only_not_selected",
        "blocked_no_proposal",
        "not_verified",
        "authorization_not_observed",
        "external_gate_closed",
        "promotion_blocked",
    ]


def test_declared_source_digest_preserves_governance_receipt_encoding() -> None:
    payload = {"kind": "観測", "rows": ["日本", "Bali"]}
    producer_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    assert _declared_source_digest(payload) == hashlib.sha256(
        producer_bytes
    ).hexdigest()
    assert _declared_source_digest(payload) != _digest(payload)


def test_cross_feeds_are_exercised_across_turns(tmp_path: Path) -> None:
    witness = run_local_cycle(
        witness_dir=tmp_path / "witness",
        runtime_db=tmp_path / "runtime.db",
        turns=2,
        persist=True,
    )
    turn_zero = witness["proofs"][0]["hops"]
    turn_one = witness["proofs"][1]["hops"]
    assert (
        turn_zero[1]["artifact"]["consumed_cross_feeds"][0]["status"] == "not_available"
    )
    assert (
        turn_zero[2]["artifact"]["consumed_cross_feeds"][0]["status"] == "not_available"
    )
    assert turn_zero[5]["artifact"]["consumed_cross_feeds"][0]["status"] == "consumed"
    assert (
        turn_one[1]["artifact"]["consumed_cross_feeds"][0]["signal"]
        == "operator_intent"
    )
    assert turn_one[1]["artifact"]["consumed_cross_feeds"][0]["status"] == "consumed"
    assert (
        turn_one[2]["artifact"]["consumed_cross_feeds"][0]["signal"]
        == "safety_contract"
    )
    assert turn_one[2]["artifact"]["consumed_cross_feeds"][0]["status"] == "consumed"


def test_hash_valid_self_authored_project_promotion_is_rejected(tmp_path: Path) -> None:
    portfolio = load_portfolio_manifest()
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=tmp_path / "runtime.db",
        turns=2,
        persist=True,
    )
    node = sorted(portfolio["nodes"], key=lambda row: row["ordinal"])[0]
    predecessor = witness["seed_artifact"]
    hop = witness["proofs"][0]["hops"][0]
    artifact = copy.deepcopy(hop["artifact"])
    evidence = artifact["project_evidence"]
    evidence["promotion_gate"]["authority_upgrade_authorized"] = True
    evidence["evidence_hash"] = _digest(
        {key: value for key, value in evidence.items() if key != "evidence_hash"}
    )
    artifact["signal"] = copy.deepcopy(evidence["signal"])
    artifact["payload"]["project_evidence_ledger"][-1] = copy.deepcopy(evidence)
    artifact["artifact_hash"] = _digest(
        {key: value for key, value in artifact.items() if key != "artifact_hash"}
    )
    identity = {
        "task_id": hop["task_id"],
        "run_id": hop["run_id"],
        "trace_id": witness["trace_id"],
        "correlation_id": witness["cycle_id"],
        "causation_id": predecessor["message_id"],
        "agent_id": node["id"],
        "idempotency_key": hop["idempotency_key"],
        "external_a2a_task_id": hop["task_id"],
        "artifact_id": f"artifact_{hop['task_id']}",
    }
    task = A2ATask(
        id=hop["task_id"],
        context_id=witness["cycle_id"],
        to_agent=node["id"],
        status=A2ATaskStatus.COMPLETED,
        capability=f"autocatalytic.{node['id']}",
        artifacts=[
            A2AArtifact(
                id=identity["artifact_id"],
                parts=[A2APart.data(json.dumps(artifact, sort_keys=True))],
            )
        ],
        result=node["output_signal"],
        trace_id=witness["trace_id"],
        metadata={
            "execution_identity": identity,
            "causation_id": predecessor["message_id"],
            "output_message_id": artifact["message_id"],
        },
    )
    with pytest.raises(SemanticPromotionError, match="not adapter-derived"):
        build_structural_hop(
            task,
            node=node,
            predecessor=predecessor,
            cycle_id=witness["cycle_id"],
            trace_id=witness["trace_id"],
            turn=0,
        )


def test_transport_ack_fails_with_controlled_structural_type_error() -> None:
    ack = TransportAck(task_id="task_ack_only", transport="nats", accepted=True)
    with pytest.raises(SemanticPromotionError, match="not transport evidence"):
        build_structural_hop(  # type: ignore[arg-type]
            ack,
            node={},
            predecessor={},
            cycle_id="cycle_ack_only",
            trace_id="trace_ack_only",
            turn=0,
        )


def test_structural_and_local_receipt_checks_have_distinct_modalities(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )

    structural = _check_structural_cycle_witness(witness, portfolio)
    assert structural.valid is True
    assert structural.modality == "structure_only"
    assert (
        "require_runtime_receipts"
        not in inspect.signature(verify_cycle_witness).parameters
    )

    hop = StructuralHop(**witness["proofs"][0]["hops"][0])
    assert hop.status == "completed"
    assert not hasattr(hop, "execution_authority")

    consistency = verify_cycle_witness(
        witness,
        portfolio,
        runtime_db=tmp_path / "absent.db",
    )
    assert consistency.valid is False
    assert consistency.modality == LOCAL_RECEIPT_CONSISTENCY_SCOPE
    assert consistency.independently_authenticated is False


def test_evaluator_result_metadata_is_invariant_and_truthiness_is_forbidden() -> None:
    structural = StructuralCycleCheck(valid=False, error="no")
    consistency = LocalReceiptConsistencyCheck(valid=False, error="no")
    with pytest.raises(TypeError, match="valid explicitly"):
        bool(structural)
    with pytest.raises(TypeError, match="valid explicitly"):
        bool(consistency)
    with pytest.raises(TypeError):
        StructuralCycleCheck(valid=True, modality="authenticated")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        LocalReceiptConsistencyCheck(  # type: ignore[call-arg]
            valid=True,
            modality="authenticated_execution",
            independently_authenticated=True,
        )


def test_local_mutable_receipts_cannot_claim_authenticated_execution(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=tmp_path / "witness",
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    forged = copy.deepcopy(witness)
    forged["execution_provenance_authenticated"] = True
    consistency = verify_cycle_witness(forged, portfolio, runtime_db=runtime_db)
    assert consistency.valid is False
    assert "cannot claim authenticated" in consistency.error


def test_loaded_latest_witness_preserves_attested_path_and_reverifies(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness_dir = tmp_path / "witness"
    witness = run_local_cycle(
        portfolio=portfolio,
        witness_dir=witness_dir,
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )

    loaded = load_latest_cycle(
        portfolio,
        witness_dir=witness_dir,
        runtime_db=runtime_db,
    )
    assert loaded is not None
    assert loaded["witness_path"] == witness["witness_path"]
    assert loaded["source_alias_path"] == str(witness_dir / "latest.json")
    consistency = verify_cycle_witness(loaded, portfolio, runtime_db=runtime_db)
    assert consistency.valid is True, consistency.error


@pytest.mark.parametrize(
    ("serialized", "expected_error"),
    [
        ("{", "cannot load witness"),
        ("{}", "wrong cycle witness schema"),
    ],
)
def test_loaded_latest_witness_fails_closed_on_corrupt_or_incomplete_json(
    tmp_path: Path,
    serialized: str,
    expected_error: str,
) -> None:
    witness_dir = tmp_path / "witness"
    witness_dir.mkdir()
    (witness_dir / "latest.json").write_text(serialized, encoding="utf-8")

    loaded = load_latest_cycle(
        load_portfolio_manifest(),
        witness_dir=witness_dir,
        runtime_db=tmp_path / "runtime.db",
    )
    assert loaded is not None
    assert loaded["structural_proof_valid"] is False
    assert loaded["local_receipt_consistency_valid"] is False
    assert expected_error in loaded["verification_error"]


def test_loaded_latest_witness_rejects_tampered_alias_cycle_identity(
    tmp_path: Path,
) -> None:
    portfolio = load_portfolio_manifest()
    runtime_db = tmp_path / "runtime.db"
    witness_dir = tmp_path / "witness"
    run_local_cycle(
        portfolio=portfolio,
        witness_dir=witness_dir,
        runtime_db=runtime_db,
        turns=2,
        persist=True,
    )
    alias_path = witness_dir / "latest.json"
    alias = json.loads(alias_path.read_text(encoding="utf-8"))
    alias["cycle_id"] = "autocat_tampered_alias"
    alias_path.write_text(json.dumps(alias), encoding="utf-8")

    loaded = load_latest_cycle(
        portfolio,
        witness_dir=witness_dir,
        runtime_db=runtime_db,
    )
    assert loaded is not None
    assert loaded["structural_proof_valid"] is False
    assert loaded["local_receipt_consistency_valid"] is False
    assert "cycle" in loaded["verification_error"]


def test_loaded_verifier_fingerprint_is_immutable_after_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portfolio = load_portfolio_manifest()
    before = _implementation_fingerprint(portfolio)
    monkeypatch.setattr(Path, "read_bytes", lambda _path: b"replacement bytes")
    after = _implementation_fingerprint(portfolio)
    assert after == before


def test_seed_is_exactly_canonical_and_disjoint_from_hop_message_ids(
    adversarial_cycle: tuple[dict, dict],
) -> None:
    _portfolio, witness = adversarial_cycle
    canonical = _semantic_seed(witness["cycle_id"], witness["trace_id"])
    hop_message_ids = {
        hop["artifact"]["message_id"]
        for proof in witness["proofs"]
        for hop in proof["hops"]
    }

    assert witness["seed_artifact"] == canonical
    assert canonical["message_id"] not in hop_message_ids


def test_hash_valid_noncanonical_seed_fails_before_chain_promotion(
    adversarial_cycle: tuple[dict, dict],
) -> None:
    portfolio, witness = adversarial_cycle
    forged = copy.deepcopy(witness)
    forged["seed_artifact"]["payload"]["self_authored_extension"] = True
    forged["seed_artifact"]["artifact_hash"] = _digest(
        {
            key: value
            for key, value in forged["seed_artifact"].items()
            if key != "artifact_hash"
        }
    )

    check = _check_structural_cycle_witness(forged, portfolio)
    assert check.valid is False
    assert "canonical" in check.error.lower()
    assert "seed" in check.error.lower()


def test_seed_message_identity_cannot_collide_with_a_hop(
    adversarial_cycle: tuple[dict, dict],
) -> None:
    portfolio, witness = adversarial_cycle
    forged = copy.deepcopy(witness)
    proof = forged["proofs"][-1]
    hop = proof["hops"][-1]
    artifact = hop["artifact"]
    artifact["message_id"] = forged["seed_artifact"]["message_id"]
    artifact["artifact_hash"] = _digest(
        {
            key: value
            for key, value in artifact.items()
            if key != "artifact_hash"
        }
    )
    hop["artifact_hash"] = artifact["artifact_hash"]
    hop["completion_hash"] = _digest(
        {
            "task_id": hop["task_id"],
            "run_id": hop["run_id"],
            "idempotency_key": hop["idempotency_key"],
            "a2a_receipt_id": hop["a2a_receipt_id"],
            "semantic_receipt_id": hop["semantic_receipt_id"],
            "status": hop["status"],
            "node_id": hop["node_id"],
            "artifact_hash": artifact["artifact_hash"],
            "predecessor_hash": artifact["predecessor_hash"],
            "causation_id": artifact["causation_id"],
        }
    )
    proof["hop_receipt_hashes"][-1] = hop["completion_hash"]
    proof["end_hash"] = artifact["artifact_hash"]
    proof["proof_hash"] = _digest(
        {
            "schema_version": proof["schema_version"],
            "cycle_id": proof["cycle_id"],
            "trace_id": proof["trace_id"],
            "turn": proof["turn"],
            "start_hash": proof["start_hash"],
            "end_hash": proof["end_hash"],
            "hop_receipt_hashes": proof["hop_receipt_hashes"],
            "cycle_closed": True,
        }
    )

    check = _check_structural_cycle_witness(forged, portfolio)
    assert check.valid is False
    assert "identities are not globally unique" in check.error


@pytest.mark.parametrize(
    "variant",
    ("malformed", "duplicate_key", "wrong_schema", "wrong_digest"),
)
def test_required_structured_adapter_source_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    original_text = _ARENA_RECEIPT.read_text(encoding="utf-8")
    receipt = json.loads(original_text)
    if variant == "malformed":
        serialized = "{"
    elif variant == "duplicate_key":
        # The duplicate has the same semantic value, so a last-key-wins parser
        # would still accept the original declared digest. The parser itself
        # must reject this ambiguity.
        serialized = original_text.replace(
            "{", '{"schema":"arena_truth_report.v1",', 1
        )
    else:
        if variant == "wrong_schema":
            receipt["schema"] = "arena_truth_report.forged"
            receipt["digest"] = _declared_source_digest(
                {key: value for key, value in receipt.items() if key != "digest"}
            )
        else:
            receipt["digest"] = "0" * 64
        serialized = json.dumps(receipt, sort_keys=True)

    _write_path(tmp_path, _ARENA_RECEIPT, serialized)
    _patch_adapter_repo_root(monkeypatch, tmp_path)
    portfolio = load_portfolio_manifest()
    node = next(row for row in portfolio["nodes"] if row["id"] == "arena_selection")
    predecessor = _semantic_seed("cycle_source_contract", "trace_source_contract")

    with pytest.raises(
        SemanticPromotionError,
        match=r"(?i)(source|receipt|json|schema|digest|duplicate)",
    ):
        _project_evidence_for(
            node,
            predecessor,
            _adapter_task(node_id="arena_selection"),
            0,
        )


def test_absent_explicitly_optional_darshan_receipt_is_a_negative_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_path(
        tmp_path,
        _DARSHAN_CHARTER,
        "# Darshan charter\n\nIntent reference only; this is not an effect receipt.\n",
    )
    assert not (tmp_path / _DARSHAN_EFFECT_RECEIPT).exists()
    _patch_adapter_repo_root(monkeypatch, tmp_path)
    portfolio = load_portfolio_manifest()
    node = next(
        row for row in portfolio["nodes"] if row["id"] == "external_value_delivery"
    )
    predecessor = _semantic_seed("cycle_optional_source", "trace_optional_source")

    evidence = _project_evidence_for(
        node,
        predecessor,
        _adapter_task(node_id="external_value_delivery"),
        0,
    )

    effect_source = next(
        row
        for row in evidence["sources"]
        if row["path"] == str(_DARSHAN_EFFECT_RECEIPT)
    )
    assert effect_source["present"] is False
    assert evidence["signal"]["state"] == "external_gate_closed"
    assert evidence["signal"]["promotion_authorized"] is False
    assert "missing_effect_receipt" in evidence["signal"]["blockers"]
    assert evidence["details"]["delivery_observed"] is False
    assert evidence["details"]["independent_outcome_observed"] is False


_CROSS_FEED_TARGETS = (
    ("oracle_evidence", "chamber_research", 0, "oracle_evidence_bound"),
    ("safety_contract", "dharmagraph_execution", 1, "safety_contract_bound"),
    ("operator_intent", "sarathi_runtime", 1, "operator_intent_bound"),
)


@pytest.mark.parametrize(
    ("signal", "node_id", "turn", "bound_field"),
    _CROSS_FEED_TARGETS,
)
def test_cross_feed_is_ledger_bound_causal_and_one_shot(
    adversarial_cycle: tuple[dict, dict],
    signal: str,
    node_id: str,
    turn: int,
    bound_field: str,
) -> None:
    portfolio, witness = adversarial_cycle
    node, hop, predecessor, task = _target_hop_context(
        portfolio,
        witness,
        node_id=node_id,
        turn=turn,
    )
    evidence = hop["artifact"]["project_evidence"]
    consumed = next(
        row for row in hop["artifact"]["consumed_cross_feeds"] if row["signal"] == signal
    )
    details = evidence["details"]
    causal_input = details["cross_feed_inputs"][signal]

    assert consumed["status"] == "consumed"
    assert causal_input["source_evidence_hash"] == consumed["source_evidence_hash"]
    assert causal_input["state"] == consumed["state"]
    assert causal_input["modality"] == consumed["modality"]
    assert causal_input["emitted_turn"] == consumed["emitted_turn"]
    ledger_matches = [
        row
        for row in predecessor["payload"]["project_evidence_ledger"]
        if row["evidence_hash"] == causal_input["source_evidence_hash"]
    ]
    assert len(ledger_matches) == 1
    source_evidence = ledger_matches[0]
    assert source_evidence["node_id"] == consumed["source"]
    assert source_evidence["signal"]["state"] == causal_input["state"]
    assert source_evidence["signal"]["modality"] == causal_input["modality"]
    source_ordinal = int(
        next(row for row in portfolio["nodes"] if row["id"] == consumed["source"])[
            "ordinal"
        ]
    )
    expected_emitted_turn = turn if source_ordinal < int(node["ordinal"]) else turn - 1
    assert causal_input["emitted_turn"] == expected_emitted_turn
    assert details[bound_field] is True
    assert signal not in hop["artifact"]["payload"]["cross_feed_bus"]
    if signal == "safety_contract":
        assert details["safety_contract_satisfied"] is False
    if signal == "operator_intent":
        assert details["dispatch_proven"] is False

    missing_predecessor = copy.deepcopy(predecessor)
    missing_predecessor["payload"]["cross_feed_bus"].pop(signal)
    missing_predecessor["artifact_hash"] = _digest(
        {
            key: value
            for key, value in missing_predecessor.items()
            if key != "artifact_hash"
        }
    )
    missing = _project_evidence_for(node, missing_predecessor, task, turn)

    assert missing["evidence_hash"] != evidence["evidence_hash"]
    assert missing["details"] != details
    assert missing["details"][bound_field] is False
    missing_input = missing["details"]["cross_feed_inputs"].get(signal)
    assert missing_input is None or missing_input.get("status") == "not_available"
    assert any(
        "unavailable" in blocker for blocker in missing["signal"]["blockers"]
    )


@pytest.mark.parametrize(
    ("signal", "node_id", "turn", "_bound_field"),
    _CROSS_FEED_TARGETS,
)
@pytest.mark.parametrize("forgery", ("source_hash", "state", "stale_turn"))
def test_forged_cross_feed_fails_adapter_recomputation(
    adversarial_cycle: tuple[dict, dict],
    signal: str,
    node_id: str,
    turn: int,
    _bound_field: str,
    forgery: str,
) -> None:
    portfolio, witness = adversarial_cycle
    node, _hop, predecessor, task = _target_hop_context(
        portfolio,
        witness,
        node_id=node_id,
        turn=turn,
    )
    forged = copy.deepcopy(predecessor)
    feed = forged["payload"]["cross_feed_bus"][signal]
    if forgery == "source_hash":
        feed["source_evidence_hash"] = "f" * 64
    elif forgery == "state":
        feed["state"] = "self_authored_authority"
    else:
        feed["emitted_turn"] = int(feed["emitted_turn"]) - 1
    forged["artifact_hash"] = _digest(
        {key: value for key, value in forged.items() if key != "artifact_hash"}
    )

    with pytest.raises(
        SemanticPromotionError,
        match=r"(?i)(cross.feed|source evidence|ledger|state|turn|stale)",
    ):
        _project_evidence_for(node, forged, task, turn)
