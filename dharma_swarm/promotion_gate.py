"""The one-door promotion gate.

Live self-modification anywhere on the Darwin/DGM surface is admitted by
exactly one authority: a judge-signed ``forge_v2.promotion_verification.v1``
packet checked by :func:`promotion_verification_allows_live`. The packet is a
capability scoped to the specific mutation it authorizes — never a bearer
token. Absent or unbound evidence refuses.

This module also owns ``SEALED_PACKET_BLOCKED_PATHS``: the files a live sealed
packet may never touch, including this gate and everything that feeds it — a
live packet must never be able to rewrite the door that admitted it.
"""

from __future__ import annotations

from typing import Any, Iterable

# Paths a live sealed packet may never modify.
SEALED_PACKET_BLOCKED_PATHS: tuple[str, ...] = (
    ".github/workflows/*",
    ".pre-commit-config.yaml",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/dgc_cli.py",
    "dharma_swarm/dharma_kernel.py",
    "dharma_swarm/diff_applier.py",
    "dharma_swarm/dgm_loop.py",
    "dharma_swarm/evolution.py",
    "dharma_swarm/evolution_safety.py",
    "dharma_swarm/evolution_safety_runtime.py",
    "dharma_swarm/frontier_council.py",
    "dharma_swarm/guardian_crew.py",
    "dharma_swarm/insight_brief.py",
    "dharma_swarm/models.py",
    "dharma_swarm/orchestrate_live.py",
    "dharma_swarm/orchestrator.py",
    "dharma_swarm/promotion_gate.py",
    "dharma_swarm/sealed_packet_apply.py",
    "dharma_swarm/swarm.py",
    "dharma_swarm/telos_gates.py",
    "dharma_swarm/forge_v1/forge_v2/*",
    "dharma_swarm/operator_core/governed_work_admission.py",
    "dharma_swarm/telos_formal.py",
    "scripts/governance/*",
)


def promotion_verification_allows_live(
    packet: dict[str, Any] | None,
    *,
    trusted_judge_public_keys: Iterable[str | bytes] = (),
    requested_source_files: Iterable[str] | None = None,
) -> bool:
    """Return True only for a fail-closed Forge promotion verification packet.

    A packet is a capability scoped to the specific mutation it authorizes,
    never a bearer token: it must name ``authorized_source_files``, and when
    the caller supplies ``requested_source_files`` every requested path must
    be covered by the packet's authorization.
    """
    if not isinstance(packet, dict):
        return False
    if packet.get("schema") != "forge_v2.promotion_verification.v1":
        return False
    if packet.get("decision") != "allow":
        return False
    if packet.get("live_apply_allowed") is not True:
        return False
    if packet.get("operator_lease_present") is not True:
        return False
    if packet.get("blockers"):
        return False
    promotion_packet = dict(packet.get("promotion_packet") or {})
    if promotion_packet.get("decision") != "promotable_candidate":
        return False
    admission = dict(packet.get("governed_admission") or {})
    if admission.get("decision") != "allow":
        return False
    telos = dict(packet.get("telos") or {})
    if telos.get("decision") != "allow":
        return False
    signed_receipts = dict(packet.get("signed_receipts") or {})
    try:
        from dharma_swarm.forge_v1.forge_v2.promote import REQUIRED_RECEIPTS_V0_ABSENT
    except Exception:
        return False
    if not all(signed_receipts.get(name) is True for name in REQUIRED_RECEIPTS_V0_ABSENT):
        return False
    authorized_source_files = {
        str(entry).strip() for entry in (packet.get("authorized_source_files") or []) if str(entry).strip()
    }
    if not authorized_source_files:
        return False
    if requested_source_files is not None:
        requested = {str(entry).strip() for entry in requested_source_files if str(entry).strip()}
        if not requested or not requested.issubset(authorized_source_files):
            return False
    try:
        from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
            verify_promotion_verification_signature,
        )

        if not verify_promotion_verification_signature(
            packet,
            trusted_public_keys=trusted_judge_public_keys,
        ):
            return False
    except Exception:
        return False
    if packet.get("payload_sha256"):
        try:
            from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

            body = {
                k: v
                for k, v in packet.items()
                if k not in {"payload_sha256", "verification_signature"}
            }
            if canonical_sha256(body) != packet["payload_sha256"]:
                return False
        except Exception:
            return False
    return True



# Backward-compatible name used by evolution.py and sealed_packet_apply.py.
_promotion_verification_allows_live = promotion_verification_allows_live
