"""Sarathi vs Hermes organ scoreboard."""

from __future__ import annotations


def organ_scoreboard() -> tuple[dict[str, str], ...]:
    return (
        {"organ": "identity", "dharma_status": "exists", "hermes_comparison": "partial parity"},
        {"organ": "provider_routing", "dharma_status": "exists", "hermes_comparison": "needs proof-gated wake routing"},
        {"organ": "gateway", "dharma_status": "partial", "hermes_comparison": "Hermes ahead operationally"},
        {"organ": "proof_gates", "dharma_status": "exists", "hermes_comparison": "Dharma stronger on deterministic gate"},
        {"organ": "operator_brief", "dharma_status": "partial", "hermes_comparison": "Sarathi source package only"},
    )


__all__ = ["organ_scoreboard"]
