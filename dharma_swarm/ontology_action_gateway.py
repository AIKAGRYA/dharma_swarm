"""Fail-closed write gateway for ontology-native product flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.models import GateCheckResult, GateDecision, GateResult
from dharma_swarm.ontology import Link, OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import get_shared_registry, persist_shared_registry
from dharma_swarm.telos_gates import DEFAULT_GATEKEEPER


class OntologyGatewayError(RuntimeError):
    """Raised when a mandatory ontology operation fails."""


class OntologyActionGateway:
    """Small fail-closed wrapper around OntologyRegistry mutations.

    TelicSeam is intentionally best-effort for the existing runtime. This
    gateway is the opposite: the proof flow stops if typed writes, links, or
    gated actions fail.
    """

    def __init__(
        self,
        registry: OntologyRegistry | None = None,
        *,
        path: str | Path | None = None,
        gatekeeper: Any = None,
        block_on_review: bool = False,
    ) -> None:
        self._path = path
        self.registry = registry or get_shared_registry(path)
        self.gatekeeper = gatekeeper or DEFAULT_GATEKEEPER
        self.block_on_review = block_on_review
        self._persist = registry is None

    def _flush(self) -> None:
        if self._persist:
            persist_shared_registry(self.registry, self._path)

    def create_object_or_fail(
        self,
        type_name: str,
        properties: dict[str, Any],
        *,
        created_by: str = "ontology_action_gateway",
    ) -> OntologyObj:
        obj, errors = self.registry.create_object(
            type_name,
            properties,
            created_by=created_by,
        )
        if obj is None:
            raise OntologyGatewayError(
                f"create_object failed for {type_name}: {'; '.join(errors)}"
            )
        self._flush()
        return obj

    def update_object_or_fail(
        self,
        object_id: str,
        updates: dict[str, Any],
        *,
        updated_by: str = "ontology_action_gateway",
    ) -> OntologyObj:
        obj, errors = self.registry.update_object(
            object_id,
            updates,
            updated_by=updated_by,
        )
        if obj is None:
            raise OntologyGatewayError(
                f"update_object failed for {object_id}: {'; '.join(errors)}"
            )
        self._flush()
        return obj

    def link_or_fail(
        self,
        link_name: str,
        source_id: str,
        target_id: str,
        *,
        created_by: str = "ontology_action_gateway",
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        link, errors = self.registry.create_link(
            link_name,
            source_id,
            target_id,
            created_by=created_by,
            metadata=metadata,
        )
        if link is None:
            raise OntologyGatewayError(
                f"link failed for {source_id} -[{link_name}]-> {target_id}: "
                f"{'; '.join(errors)}"
            )
        self._flush()
        return link

    def execute_action_or_fail(
        self,
        object_type: str,
        action_name: str,
        object_id: str,
        params: dict[str, Any] | None = None,
        *,
        executed_by: str = "ontology_action_gateway",
    ):
        params = params or {}
        action_def = self.registry.get_action_def(object_type, action_name)
        if action_def is None:
            execution = self.registry.execute_action(
                object_type,
                action_name,
                object_id,
                params,
                executed_by=executed_by,
            )
            self._flush()
            raise OntologyGatewayError(execution.error)

        gate_results: dict[str, str] = {}
        if action_def.telos_gates:
            gate_check = self._run_gate_check(object_type, action_name, params)
            gate_results = self._project_gate_results(gate_check, action_def.telos_gates)
            if (
                gate_check.decision == GateDecision.BLOCK
                or (self.block_on_review and gate_check.decision == GateDecision.REVIEW)
            ):
                execution = self.registry.execute_action(
                    object_type,
                    action_name,
                    object_id,
                    params,
                    executed_by=executed_by,
                    gate_check=lambda _name, _params: {
                        gate_check.gate or action_def.telos_gates[0]: "BLOCK"
                    },
                )
                self._flush()
                raise OntologyGatewayError(
                    f"telos gate blocked {object_type}.{action_name}: {gate_check.reason}"
                )

        execution = self.registry.execute_action(
            object_type,
            action_name,
            object_id,
            params,
            executed_by=executed_by,
            gate_check=(lambda _name, _params: gate_results) if action_def.telos_gates else None,
        )
        self._flush()
        if execution.result != "success":
            raise OntologyGatewayError(
                f"execute_action failed for {object_type}.{action_name}: {execution.error}"
            )
        return execution

    def _run_gate_check(
        self,
        object_type: str,
        action_name: str,
        params: dict[str, Any],
    ) -> GateCheckResult:
        return self.gatekeeper.check(
            action=f"{object_type}.{action_name}",
            content=json.dumps(params, sort_keys=True, default=str),
            tool_name="ontology_action_gateway",
        )

    @staticmethod
    def _project_gate_results(
        gate_check: GateCheckResult,
        required_gates: list[str],
    ) -> dict[str, str]:
        projected: dict[str, str] = {}
        for gate in required_gates:
            result = gate_check.gate_results.get(gate)
            if result is None:
                projected[gate] = "PASS"
                continue
            gate_result = result[0]
            if gate_result == GateResult.FAIL:
                projected[gate] = "BLOCK"
            elif gate_result == GateResult.WARN:
                projected[gate] = "WARN"
            else:
                projected[gate] = "PASS"
        return projected


__all__ = ["OntologyActionGateway", "OntologyGatewayError"]
