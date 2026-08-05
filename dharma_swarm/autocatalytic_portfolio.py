"""Ten-node autocatalytic portfolio and local semantic A2A rehearsal harness.

This compatibility facade preserves the established public and private imports
and CLI. Structural validation and local mutable-receipt consistency remain
distinct; no result from this module authenticates execution provenance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.autocatalytic_adapters import (
    _consume_project_cross_feeds as _consume_project_cross_feeds,
    _project_cross_feeds as _project_cross_feeds,
    _project_evidence_for as _project_evidence_for,
    _source_snapshot as _source_snapshot,
    _validate_project_semantics as _validate_project_semantics,
)
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_PROOF_SCHEMA as CYCLE_PROOF_SCHEMA,
    CYCLE_WITNESS_SCHEMA as CYCLE_WITNESS_SCHEMA,
    LOCAL_RECEIPT_CONSISTENCY_SCOPE as LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    PORTFOLIO_SCHEMA as PORTFOLIO_SCHEMA,
    REQUIRED_NODE_COUNT as REQUIRED_NODE_COUNT,
    RUNTIME_ATTESTATION_SCHEMA as RUNTIME_ATTESTATION_SCHEMA,
    SEMANTIC_HOP_SCHEMA as SEMANTIC_HOP_SCHEMA,
    VERIFIER_VERSION as VERIFIER_VERSION,
    LocalReceiptConsistencyCheck as LocalReceiptConsistencyCheck,
    PortfolioContractError as PortfolioContractError,
    SemanticPromotionError as SemanticPromotionError,
    StructuralCycleCheck as StructuralCycleCheck,
    StructuralCycleProof as StructuralCycleProof,
    StructuralHop as StructuralHop,
    TransportAck as TransportAck,
    _build_catalytic_graph as _build_catalytic_graph,
    _canonical_json as _canonical_json,
    _completion_hash as _completion_hash,
    _declared_source_digest as _declared_source_digest,
    _digest as _digest,
    _ordered_nodes as _ordered_nodes,
    _semantic_seed as _semantic_seed,
    _utc_now as _utc_now,
    _verify_artifact_hash as _verify_artifact_hash,
    load_portfolio_manifest as load_portfolio_manifest,
    validate_portfolio as validate_portfolio,
)
from dharma_swarm.autocatalytic_cycle_runtime import (
    _default_runtime_db as _default_runtime_db,
    _default_state_dir as _default_state_dir,
    _default_witness_dir as _default_witness_dir,
    _write_json_atomic as _write_json_atomic,
    load_latest_cycle as load_latest_cycle,
    run_local_cycle as run_local_cycle,
)
from dharma_swarm.autocatalytic_proof_builders import (
    build_structural_cycle_proof as build_structural_cycle_proof,
    build_structural_hop as build_structural_hop,
)
from dharma_swarm.autocatalytic_task_runtime import (
    _handler_for as _handler_for,
    _input_artifact as _input_artifact,
)
from dharma_swarm.autocatalytic_verifier import (
    _check_structural_cycle_witness as _check_structural_cycle_witness,
    _implementation_fingerprint as _implementation_fingerprint,
    _runtime_attestation_core as _runtime_attestation_core,
    verify_cycle_witness as verify_cycle_witness,
)

__all__ = [
    "LOCAL_RECEIPT_CONSISTENCY_SCOPE",
    "LocalReceiptConsistencyCheck",
    "PortfolioContractError",
    "REQUIRED_NODE_COUNT",
    "SemanticPromotionError",
    "StructuralCycleCheck",
    "StructuralCycleProof",
    "StructuralHop",
    "TransportAck",
    "build_autocatalytic_snapshot",
    "build_structural_cycle_proof",
    "build_structural_hop",
    "load_latest_cycle",
    "load_portfolio_manifest",
    "run_local_cycle",
    "validate_portfolio",
    "verify_cycle_witness",
    "_build_catalytic_graph",
    "_check_structural_cycle_witness",
    "_declared_source_digest",
    "_digest",
    "_implementation_fingerprint",
    "_project_evidence_for",
    "_semantic_seed",
    "_source_snapshot",
]


def build_autocatalytic_snapshot(
    *, witness_dir: Path | None = None, runtime_db: Path | None = None
) -> dict[str, Any]:
    """Return the API/dashboard read model with topology and latest proof."""

    portfolio = load_portfolio_manifest()
    errors = validate_portfolio(portfolio)
    graph = _build_catalytic_graph(portfolio)
    summary = graph.summary()
    topology = {
        **summary,
        "required_nodes": REQUIRED_NODE_COUNT,
        "strongly_connected": summary["largest_scc"] == REQUIRED_NODE_COUNT,
        "one_autocatalytic_set": summary["autocatalytic_sets"] == 1,
        "contract_valid": not errors,
        "validation_errors": errors,
    }
    return {
        "schema_version": PORTFOLIO_SCHEMA,
        "portfolio": portfolio,
        "topology": topology,
        "latest_cycle": load_latest_cycle(
            portfolio,
            witness_dir=witness_dir,
            runtime_db=runtime_db,
        ),
    }


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate declared topology and print snapshot")
    run_parser = subparsers.add_parser("run", help="run a local two-turn A2A rehearsal")
    run_parser.add_argument("--turns", type=int, default=2)
    run_parser.add_argument("--witness-dir", type=Path)
    run_parser.add_argument("--runtime-db", type=Path)
    args = parser.parse_args(argv)

    if args.command == "check":
        snapshot = build_autocatalytic_snapshot()
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0 if snapshot["topology"]["contract_valid"] else 1
    witness = run_local_cycle(
        witness_dir=args.witness_dir,
        runtime_db=args.runtime_db,
        turns=args.turns,
        persist=True,
    )
    print(json.dumps(witness, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
