"""Titanium Telos bridge for DharmaGraph evidence receipts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from dharma_swarm.merkle_log import MerkleLog
from dharma_swarm.spine.receipt import EvidenceReceipt
from telos_kernel import Manifest, Tier, Verdict, check

GATE_GRAPH_RECEIPT_ANCHOR = "U5_graph_receipt_anchor"


@dataclass(frozen=True, slots=True)
class GraphTelosBridgeResult:
    """Result of trying to anchor a graph receipt in the Titanium log."""

    verdict: str
    reason: str
    root_uri: str
    leaf_index: int | None
    chain_ok_before_append: bool
    first_broken_index: int | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict == Verdict.ALLOW.value


class GraphTelosBridge:
    """Append graph dispatch evidence to a verified Titanium Merkle chain."""

    def __init__(self, log: MerkleLog, manifest: Manifest | None = None) -> None:
        self._log = log
        self._manifest = manifest

    def record_dispatch_receipt(
        self,
        receipt: EvidenceReceipt,
        *,
        side_effect_key: str,
        operation_hash: str = "",
        proposal_id: str | None = None,
    ) -> GraphTelosBridgeResult:
        """Verify the chain, then append a U5 receipt-anchor leaf."""
        chain_ok, first_broken = self._verify_chain()
        if not chain_ok:
            return GraphTelosBridgeResult(
                verdict=Verdict.BLOCK.value,
                reason="titanium_chain_not_verified",
                root_uri=_sha256_uri(self._log.head_hash()),
                leaf_index=None,
                chain_ok_before_append=False,
                first_broken_index=first_broken,
            )

        verdict, reason = self._verdict_for(receipt, side_effect_key)
        leaf = check(
            gate=GATE_GRAPH_RECEIPT_ANCHOR,
            tier=Tier.A,
            measure=self._measure(receipt, side_effect_key, operation_hash),
            threshold={
                "chain_verified_before_append": True,
                "receipt_status_required": "ok",
                "side_effect_key_required": True,
                "non_stub_manifest_required_for_allow": True,
            },
            verdict=Verdict(verdict),
            log=self._log,
            proposal_id=proposal_id,
        )
        return GraphTelosBridgeResult(
            verdict=leaf.verdict.value,
            reason=reason,
            root_uri=_sha256_uri(self._log.head_hash()),
            leaf_index=self._log.get_chain_length() - 1,
            chain_ok_before_append=True,
        )

    def _verify_chain(self) -> tuple[bool, int | None]:
        ok, first_broken = self._log.verify_chain()
        return bool(ok), None if ok else first_broken

    def _verdict_for(
        self, receipt: EvidenceReceipt, side_effect_key: str
    ) -> tuple[str, str]:
        if not side_effect_key:
            return Verdict.BLOCK.value, "missing_side_effect_key"
        if receipt.status != "ok":
            return Verdict.REVIEW.value, f"receipt_status_{receipt.status}"
        if self._manifest is None:
            return Verdict.WARN.value, "manifest_not_supplied"
        if self._manifest.has_stub_signers():
            return Verdict.WARN.value, "manifest_has_stub_signers"
        return Verdict.ALLOW.value, "receipt_anchored"

    def _measure(
        self,
        receipt: EvidenceReceipt,
        side_effect_key: str,
        operation_hash: str,
    ) -> dict[str, Any]:
        manifest_hash = (
            _sha256_uri(self._manifest.content_hash()) if self._manifest else ""
        )
        return {
            "receipt_id": str(receipt.receipt_id),
            "receipt_hash": _stable_hash_uri(receipt.to_dict()),
            "receipt_status": receipt.status,
            "task_id": receipt.task_id,
            "agent_id": receipt.agent_id,
            "side_effect_key_present": bool(side_effect_key),
            "side_effect_key_hash": _stable_hash_uri(side_effect_key)
            if side_effect_key
            else "",
            "operation_hash": _sha256_uri(operation_hash) if operation_hash else "",
            "manifest_hash": manifest_hash,
            "manifest_supplied": self._manifest is not None,
            "manifest_stub_signers": (
                self._manifest.has_stub_signers() if self._manifest else None
            ),
        }


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _stable_hash_uri(payload: object) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _sha256_uri(value: str) -> str:
    clean = value.strip()
    if clean.startswith("sha256:"):
        return clean
    return f"sha256:{clean}"
