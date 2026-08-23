"""One locked post-bootstrap transaction for SADHANA runtime manifests.

This renderer binds nondeterministic TaskBoard identities to precommitted input
hashes.  It has no provider, agent-spawn, lease, dispatch, verifier, acceptance,
or publication surface.  A partial crash therefore remains authority-unbound;
an exact replay finishes the same three immutable files.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_binding import (
    load_campaign_authority_manifest,
)
from dharma_swarm.mission_control_binding_render import (
    deterministic_read_only_policies,
    render_campaign_authority_manifest,
)
from dharma_swarm.mission_control_bootstrap import (
    CampaignBootstrapLock,
    GoalPortfolio,
    inspect_sadhana_campaign,
)
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_held_out_oracle import (
    load_held_out_oracle_manifest,
    render_held_out_oracle_manifest,
)
from dharma_swarm.mission_control_observed_input import (
    ingest_observed_input_manifest,
    load_observed_input_manifest,
    render_observed_input_manifest,
)
from dharma_swarm.mission_control_oracle_custody import (
    list_private_directory,
    private_directory,
    write_exact,
)
from dharma_swarm.mission_control_roster import CampaignAgentRoster
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


OBSERVED_INPUT_MANIFEST_NAME = "observed-inputs.json"
HELD_OUT_ORACLE_MANIFEST_NAME = "held-out-oracle.json"
AUTHORITY_MANIFEST_NAME = "authority-manifest.json"
RUNTIME_MANIFEST_NAMES = (
    OBSERVED_INPUT_MANIFEST_NAME,
    HELD_OUT_ORACLE_MANIFEST_NAME,
    AUTHORITY_MANIFEST_NAME,
)
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class RuntimeManifestPins:
    evaluator_path: Path
    evaluator_sha256: str
    policy_path: Path
    policy_sha256: str
    operator_control_semantics_sha256: str
    operator_control_authority_binding_sha256: str
    deployment_authority_topology_sha256: str
    deployment_authority_credential_clarification_sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeManifestRenderResult:
    campaign_id: str
    canary_task_id: str
    observed_input_manifest_digest: str
    held_out_oracle_manifest_digest: str
    authority_manifest_digest: str
    files: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "dharma.sadhana.runtime_manifest_render.v1",
            "campaign_id": self.campaign_id,
            "canary_task_id": self.canary_task_id,
            "dispatch_ready": False,
            "authority_state": "rendered_not_bound",
            "observed_input_manifest_digest": self.observed_input_manifest_digest,
            "held_out_oracle_manifest_digest": self.held_out_oracle_manifest_digest,
            "authority_manifest_digest": self.authority_manifest_digest,
            "files": dict(self.files),
            "claims": {
                "proves": [
                    "The three runtime manifests bind the inspected bootstrap identities.",
                    "Observed inputs were durably ingested as prompt-only evidence.",
                ],
                "does_not_prove": [
                    "No agent, lease, provider effect, dispatch, verification, or acceptance occurred."
                ],
            },
        }

    def to_json(self) -> str:
        return (
            json.dumps(
                self.to_dict(),
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _sha256(value: str, label: str) -> str:
    _need(
        isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
        f"{label} must be sha256",
    )
    return value


def _raw_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_pins(pins: RuntimeManifestPins) -> None:
    _need(
        pins.evaluator_path.is_absolute() and pins.policy_path.is_absolute(),
        "held-out evaluator and policy paths must be absolute",
    )
    for label, digest in (
        ("evaluator digest", pins.evaluator_sha256),
        ("policy digest", pins.policy_sha256),
        ("operator control semantics digest", pins.operator_control_semantics_sha256),
        (
            "operator control authority binding digest",
            pins.operator_control_authority_binding_sha256,
        ),
        (
            "deployment authority topology digest",
            pins.deployment_authority_topology_sha256,
        ),
        (
            "deployment authority credential clarification digest",
            pins.deployment_authority_credential_clarification_sha256,
        ),
    ):
        _sha256(digest, label)


async def render_runtime_manifests(
    portfolio: GoalPortfolio,
    control: MissionControl,
    board: TaskBoard,
    runtime: RuntimeStateStore,
    roster: CampaignAgentRoster,
    *,
    observed_source_path: Path,
    output_root: Path,
    verifier_seat_name: str,
    pins: RuntimeManifestPins,
    operator_id: str,
    lock: CampaignBootstrapLock,
) -> RuntimeManifestRenderResult:
    """Render/ingest the exact runtime files while the core owner lock is held."""
    _validate_pins(pins)
    _need(output_root.is_absolute(), "runtime manifest output root must be absolute")
    bootstrap = await inspect_sadhana_campaign(
        portfolio,
        control,
        operator_id=operator_id,
        lock=lock,
    )
    _need(roster.campaign_id == bootstrap.mission_id, "roster campaign is foreign")
    output_root = private_directory(output_root, "runtime manifest output root")
    existing = set(list_private_directory(output_root, "runtime manifest output root"))
    _need(
        existing <= set(RUNTIME_MANIFEST_NAMES),
        "runtime manifest output root contains a foreign entry",
    )

    observed_path = output_root / OBSERVED_INPUT_MANIFEST_NAME
    held_path = output_root / HELD_OUT_ORACLE_MANIFEST_NAME
    authority_path = output_root / AUTHORITY_MANIFEST_NAME

    observed_bytes = await render_observed_input_manifest(
        observed_source_path,
        bootstrap,
        board,
    )
    write_exact(observed_path, observed_bytes, canonical_json_on_replay=False)
    observed = await ingest_observed_input_manifest(observed_path, board, runtime)

    held_bytes = await render_held_out_oracle_manifest(
        bootstrap,
        board,
        evaluator_path=pins.evaluator_path,
        evaluator_sha256=pins.evaluator_sha256,
        policy_path=pins.policy_path,
        policy_sha256=pins.policy_sha256,
    )
    write_exact(held_path, held_bytes, canonical_json_on_replay=False)
    held = load_held_out_oracle_manifest(held_path)

    policies = deterministic_read_only_policies(
        bootstrap,
        roster,
        verifier_seat_name=verifier_seat_name,
    )
    authority_bytes = await render_campaign_authority_manifest(
        bootstrap,
        board,
        roster,
        policies,
        observed,
        reserved_agent_names=(verifier_seat_name,),
        held_out_oracle_manifest_digest=held.manifest_digest,
        operator_control_semantics_sha256=pins.operator_control_semantics_sha256,
        operator_control_authority_binding_sha256=(
            pins.operator_control_authority_binding_sha256
        ),
        deployment_authority_topology_sha256=(
            pins.deployment_authority_topology_sha256
        ),
        deployment_authority_credential_clarification_sha256=(
            pins.deployment_authority_credential_clarification_sha256
        ),
    )
    write_exact(authority_path, authority_bytes, canonical_json_on_replay=False)
    authority = load_campaign_authority_manifest(authority_path)
    _need(
        authority.observed_input_manifest_digest == observed.manifest_digest
        and authority.held_out_oracle_manifest_digest == held.manifest_digest,
        "rendered authority evidence lineage conflicts",
    )
    _need(
        set(list_private_directory(output_root, "runtime manifest output root"))
        == set(RUNTIME_MANIFEST_NAMES),
        "runtime manifest output set is incomplete",
    )

    observed_payload = load_observed_input_manifest(observed_path)
    _need(
        observed_payload["manifest_digest"] == observed.manifest_digest,
        "rendered observed input digest conflicts",
    )
    return RuntimeManifestRenderResult(
        campaign_id=bootstrap.mission_id,
        canary_task_id=bootstrap.canary_task_id,
        observed_input_manifest_digest=observed.manifest_digest,
        held_out_oracle_manifest_digest=held.manifest_digest,
        authority_manifest_digest=authority.manifest_digest,
        files=tuple(
            sorted(
                (
                    (OBSERVED_INPUT_MANIFEST_NAME, _raw_digest(observed_bytes)),
                    (HELD_OUT_ORACLE_MANIFEST_NAME, _raw_digest(held_bytes)),
                    (AUTHORITY_MANIFEST_NAME, _raw_digest(authority_bytes)),
                )
            )
        ),
    )


def add_campaign_runtime_arguments(parser: Any) -> None:
    """Attach the exact manifest, activation, verifier, and control inputs."""
    parser.add_argument("--authority-manifest", required=True)
    parser.add_argument("--observed-input-manifest", required=True)
    parser.add_argument("--held-out-oracle-manifest", required=True)
    parser.add_argument("--verifier-seat", default="sadhana-nemotron")
    parser.add_argument("--verifier-lock-root", default=None)
    parser.add_argument("--oracle-work-root", default=None)
    parser.add_argument(
        "--oracle-request-root",
        default="/run/dharma-sadhana/oracle/requests",
    )
    parser.add_argument(
        "--oracle-terminal-root",
        default="/run/dharma-sadhana/oracle/terminals",
    )
    parser.add_argument("--oracle-sandbox-evidence-sha256", default="")
    parser.add_argument("--oracle-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--oracle-poll-interval-seconds", type=float, default=0.25)
    parser.add_argument("--lease-root", default=None)
    parser.add_argument("--shutdown-timeout", type=float, default=15.0)
    parser.add_argument("--writer-handoff-timeout", type=float, default=10.0)
    parser.add_argument("--fast-boot", action="store_true")
    parser.add_argument("--agent-roster", default="")
    parser.add_argument("--agent-roster-sha256", default="")
    parser.add_argument("--objective-sha256", default="")
    parser.add_argument("--observer-health-receipt", default="")
    parser.add_argument("--observer-health-receipt-sha256", default="")
    parser.add_argument(
        "--operator-control-normal-inbox",
        default="/run/dharma-sadhana/control/normal",
    )
    parser.add_argument(
        "--operator-control-inflight-inbox",
        default="/run/dharma-sadhana/control/inflight",
    )
    parser.add_argument(
        "--operator-control-applied-inbox",
        default="/run/dharma-sadhana/control/applied",
    )
    parser.add_argument(
        "--operator-control-rejected-inbox",
        default="/run/dharma-sadhana/control/rejected",
    )
    parser.add_argument("--operator-control-hmac-credential", default="")
    parser.add_argument("--operator-control-hmac-sha256", default="")
    parser.add_argument(
        "--operator-control-max-candidates-per-cycle",
        type=int,
        default=128,
    )


__all__ = [
    "AUTHORITY_MANIFEST_NAME",
    "HELD_OUT_ORACLE_MANIFEST_NAME",
    "OBSERVED_INPUT_MANIFEST_NAME",
    "RUNTIME_MANIFEST_NAMES",
    "RuntimeManifestPins",
    "RuntimeManifestRenderResult",
    "add_campaign_runtime_arguments",
    "render_runtime_manifests",
]
