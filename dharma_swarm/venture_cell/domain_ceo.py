"""Domain CEO contract for governed VentureCells.

The contract is intentionally policy-first: it describes what a cell CEO may
coordinate, what it may not execute, and what proof is required before liveness
or external-world claims can be made.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dharma_swarm.holon_budget_guard import check_cost_cap


class DomainCEOContractError(ValueError):
    """Raised when a VentureCell CEO contract blocks an unsafe operation."""


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


@dataclass(frozen=True)
class BudgetPolicy:
    """Budget ceilings enforced before a CEO lane/tool/activity runs."""

    mission_cap_usd: float = 0.0
    daily_cap_usd: float = 0.0
    lane_cap_usd: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BudgetPolicy":
        data = data or {}
        return cls(
            mission_cap_usd=float(data.get("mission_cap_usd", 0.0)),
            daily_cap_usd=float(data.get("daily_cap_usd", 0.0)),
            lane_cap_usd=float(data.get("lane_cap_usd", 0.0)),
        )

    def check_mission_spend(self, *, spent_usd: float) -> None:
        check_cost_cap("domain_ceo.mission", spent_usd, self.mission_cap_usd)

    def check_daily_spend(self, *, spent_usd: float) -> None:
        check_cost_cap("domain_ceo.daily", spent_usd, self.daily_cap_usd)

    def check_lane_spend(self, lane_id: str, *, spent_usd: float) -> None:
        check_cost_cap(f"domain_ceo.lane.{lane_id}", spent_usd, self.lane_cap_usd)


@dataclass(frozen=True)
class DataPolicy:
    """Data partition rules for public proof and external action payloads."""

    sensitive_data_classes: tuple[str, ...] = (
        "identity",
        "exact_location",
        "income",
        "debt",
        "migration_status",
        "caste",
        "religion",
        "health",
        "household",
        "case_notes",
        "consent_record",
    )
    public_proof_allowed_fields: tuple[str, ...] = (
        "claim_id",
        "cell_id",
        "claim_type",
        "aggregate_count",
        "sector",
        "region_level",
        "evidence_refs",
        "audit_status",
        "outcome_metric",
        "outcome_value",
        "time_period",
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DataPolicy":
        data = data or {}
        return cls(
            sensitive_data_classes=tuple(
                _as_list(data.get("sensitive_data_classes"))
                or cls.sensitive_data_classes
            ),
            public_proof_allowed_fields=tuple(
                _as_list(data.get("public_proof_allowed_fields"))
                or cls.public_proof_allowed_fields
            ),
        )

    def validate_public_payload(self, payload: dict[str, Any]) -> None:
        sensitive = set(self.sensitive_data_classes)
        public_fields = set(self.public_proof_allowed_fields)
        present_sensitive = sensitive.intersection(payload)
        if present_sensitive:
            raise DomainCEOContractError(
                "public payload contains sensitive field(s): "
                + ", ".join(sorted(present_sensitive))
            )
        unknown = set(payload) - public_fields
        if unknown:
            raise DomainCEOContractError(
                "public payload contains unapproved field(s): "
                + ", ".join(sorted(unknown))
            )


@dataclass(frozen=True)
class ExternalActionPolicy:
    """Approval rules for actions that touch the world."""

    approval_required_for: tuple[str, ...] = (
        "outreach",
        "publication",
        "payment",
        "on_chain_transaction",
        "procurement_intro",
        "partner_claim",
        "capital_signal",
    )
    forbidden_actions: tuple[str, ...] = (
        "autonomous_lending_decision",
        "autonomous_investment_decision",
        "data_sale",
        "trading_alpha_extraction",
        "worker_surveillance",
    )
    external_action_mode: str = "human_approved_only"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExternalActionPolicy":
        data = data or {}
        return cls(
            approval_required_for=tuple(
                _as_list(data.get("approval_required_for"))
                or cls.approval_required_for
            ),
            forbidden_actions=tuple(
                _as_list(data.get("forbidden_actions"))
                or cls.forbidden_actions
            ),
            external_action_mode=str(
                data.get("external_action_mode", "human_approved_only")
            ),
        )

    def validate_action_kind(self, action_kind: str) -> None:
        if action_kind in self.forbidden_actions:
            raise DomainCEOContractError(f"external action forbidden: {action_kind}")
        if self.external_action_mode != "human_approved_only":
            raise DomainCEOContractError(
                "external action mode must remain human_approved_only"
            )
        if action_kind not in self.approval_required_for:
            raise DomainCEOContractError(
                f"external action kind not explicitly approved by policy: {action_kind}"
            )


@dataclass(frozen=True)
class ProviderProof:
    """Proof gate for "provider is green" claims."""

    provider: str = ""
    model: str = ""
    attempted_at: str = ""
    success: bool = False
    receipt_id: str = ""
    trace_id: str = ""
    result_ref: str = ""

    def is_green(self) -> bool:
        return all((
            self.provider,
            self.model,
            self.attempted_at,
            self.success,
            self.receipt_id,
            self.trace_id,
            self.result_ref,
        ))


@dataclass(frozen=True)
class DomainCEOContract:
    """A bounded CEO seat for a VentureCell."""

    cell_id: str
    mission_id: str
    human_governor: str
    parent_plane: str
    capital_boundary: str
    first_metric: str
    allowed_agent_roles: tuple[str, ...]
    allowed_internal_tools: tuple[str, ...] = ()
    max_children: int = 0
    max_depth: int = 0
    budget_policy: BudgetPolicy = field(default_factory=BudgetPolicy)
    data_policy: DataPolicy = field(default_factory=DataPolicy)
    external_action_policy: ExternalActionPolicy = field(
        default_factory=ExternalActionPolicy
    )
    proof_contract: tuple[str, ...] = ()
    shutdown_conditions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainCEOContract":
        return cls(
            cell_id=str(data["cell_id"]),
            mission_id=str(data.get("mission_id", "")),
            human_governor=str(data["human_governor"]),
            parent_plane=str(data.get("parent_plane", "")),
            capital_boundary=str(data.get("capital_boundary", "")),
            first_metric=str(data.get("first_metric", "")),
            allowed_agent_roles=tuple(_as_list(data.get("allowed_agent_roles"))),
            allowed_internal_tools=tuple(_as_list(data.get("allowed_internal_tools"))),
            max_children=int(data.get("max_children", 0)),
            max_depth=int(data.get("max_depth", 0)),
            budget_policy=BudgetPolicy.from_dict(data.get("budget_policy")),
            data_policy=DataPolicy.from_dict(data.get("data_policy")),
            external_action_policy=ExternalActionPolicy.from_dict(
                data.get("external_action_policy")
            ),
            proof_contract=tuple(_as_list(data.get("proof_contract"))),
            shutdown_conditions=tuple(_as_list(data.get("shutdown_conditions"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if not self.cell_id:
            raise DomainCEOContractError("cell_id is required")
        if not self.human_governor:
            raise DomainCEOContractError("human_governor is required")
        if self.parent_plane != "jagat_kalyan":
            raise DomainCEOContractError("Livelihood-style VentureCells must serve jagat_kalyan")
        if "dharma_capital_read_only_aggregated_signals" not in self.capital_boundary:
            raise DomainCEOContractError("capital boundary must be read-only and aggregated")
        if self.max_children < 0 or self.max_depth < 0:
            raise DomainCEOContractError("max_children and max_depth must be non-negative")
        if not self.allowed_agent_roles:
            raise DomainCEOContractError("allowed_agent_roles cannot be empty")

    def check_spawn(
        self,
        *,
        requested_role: str,
        current_children: int,
        requested_depth: int,
    ) -> None:
        if requested_role not in self.allowed_agent_roles:
            raise DomainCEOContractError(f"agent role not allowed: {requested_role}")
        if current_children >= self.max_children:
            raise DomainCEOContractError("child spawn denied: max_children reached")
        if requested_depth > self.max_depth:
            raise DomainCEOContractError("child spawn denied: max_depth exceeded")

    def check_internal_tool(self, tool_name: str) -> None:
        if tool_name not in self.allowed_internal_tools:
            raise DomainCEOContractError(f"internal tool not allowed: {tool_name}")

    def check_external_action(self, action_kind: str) -> None:
        self.external_action_policy.validate_action_kind(action_kind)

    def assert_provider_green(self, proof: ProviderProof) -> None:
        if not proof.is_green():
            raise DomainCEOContractError("provider cannot be green without complete proof")


def load_domain_ceo_contract(path: str | Path) -> DomainCEOContract:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DomainCEOContractError("CEO contract file must contain a mapping")
    contract = DomainCEOContract.from_dict(payload)
    contract.validate()
    return contract
