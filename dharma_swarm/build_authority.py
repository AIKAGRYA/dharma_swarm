"""Canonical authority matrix for build governance.

This module is intentionally narrow:

- define the stable build lanes
- define the actions that matter for execution authority
- provide a single place to answer "who is allowed to do what?"

It does not own runtime task execution. It owns the build-governance contract
that other layers can consult.
"""

from __future__ import annotations

from enum import Enum


class BuildLane(str, Enum):
    OPERATOR = "operator"
    GOVERNOR = "governor"
    CONDUCTOR = "conductor"
    BUILDER = "builder"
    RESEARCHER = "researcher"
    VERIFIER = "verifier"
    GATEWAY = "gateway"


class BuildAction(str, Enum):
    CREATE_TASK = "create_task"
    ASSIGN_TASK = "assign_task"
    CLAIM_TASK = "claim_task"
    SUBMIT_TASK = "submit_task"
    RECORD_DECISION = "record_decision"
    VERIFY_TASK = "verify_task"
    QUARANTINE_TASK = "quarantine_task"
    ABANDON_TASK = "abandon_task"
    NOMINATE_CAMPAIGN = "nominate_campaign"
    DEMOTE_CAMPAIGN = "demote_campaign"
    PROMOTE_CAMPAIGN = "promote_campaign"
    KILL_CAMPAIGN = "kill_campaign"
    APPROVE_IRREVERSIBLE_ACTION = "approve_irreversible_action"
    RECORD_EVALUATION = "record_evaluation"
    RECORD_INCIDENT = "record_incident"
    RECORD_ROLLBACK = "record_rollback"


class SettlementState(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"
    ABANDONED = "abandoned"


AUTHORITY_MATRIX: dict[BuildLane, frozenset[BuildAction]] = {
    BuildLane.OPERATOR: frozenset(
        {
            BuildAction.CREATE_TASK,
            BuildAction.ASSIGN_TASK,
            BuildAction.RECORD_DECISION,
            BuildAction.NOMINATE_CAMPAIGN,
            BuildAction.DEMOTE_CAMPAIGN,
            BuildAction.PROMOTE_CAMPAIGN,
            BuildAction.KILL_CAMPAIGN,
            BuildAction.APPROVE_IRREVERSIBLE_ACTION,
            BuildAction.RECORD_EVALUATION,
            BuildAction.RECORD_INCIDENT,
            BuildAction.RECORD_ROLLBACK,
        }
    ),
    BuildLane.GOVERNOR: frozenset(
        {
            BuildAction.DEMOTE_CAMPAIGN,
            BuildAction.PROMOTE_CAMPAIGN,
            BuildAction.KILL_CAMPAIGN,
            BuildAction.APPROVE_IRREVERSIBLE_ACTION,
            BuildAction.RECORD_DECISION,
            BuildAction.QUARANTINE_TASK,
            BuildAction.RECORD_EVALUATION,
            BuildAction.RECORD_INCIDENT,
            BuildAction.RECORD_ROLLBACK,
        }
    ),
    BuildLane.CONDUCTOR: frozenset(
        {
            BuildAction.CREATE_TASK,
            BuildAction.ASSIGN_TASK,
            BuildAction.CLAIM_TASK,
            BuildAction.ABANDON_TASK,
            BuildAction.RECORD_DECISION,
            BuildAction.NOMINATE_CAMPAIGN,
            BuildAction.DEMOTE_CAMPAIGN,
            BuildAction.RECORD_INCIDENT,
        }
    ),
    BuildLane.BUILDER: frozenset(
        {
            BuildAction.CLAIM_TASK,
            BuildAction.SUBMIT_TASK,
        }
    ),
    BuildLane.RESEARCHER: frozenset(
        {
            BuildAction.CLAIM_TASK,
            BuildAction.SUBMIT_TASK,
        }
    ),
    BuildLane.VERIFIER: frozenset(
        {
            BuildAction.CLAIM_TASK,
            BuildAction.VERIFY_TASK,
            BuildAction.QUARANTINE_TASK,
            BuildAction.RECORD_EVALUATION,
            BuildAction.RECORD_INCIDENT,
        }
    ),
    BuildLane.GATEWAY: frozenset(
        {
            BuildAction.CLAIM_TASK,
            BuildAction.SUBMIT_TASK,
        }
    ),
}


class AuthorityError(PermissionError):
    """Raised when a lane attempts an action outside its contract."""


def normalize_lane(value: BuildLane | str) -> BuildLane:
    if isinstance(value, BuildLane):
        return value
    return BuildLane(str(value).strip().lower())


def normalize_action(value: BuildAction | str) -> BuildAction:
    if isinstance(value, BuildAction):
        return value
    return BuildAction(str(value).strip().lower())


def lane_actions(lane: BuildLane | str) -> frozenset[BuildAction]:
    resolved = normalize_lane(lane)
    return AUTHORITY_MATRIX[resolved]


def can_perform(
    lane: BuildLane | str,
    action: BuildAction | str,
) -> bool:
    resolved_lane = normalize_lane(lane)
    resolved_action = normalize_action(action)
    return resolved_action in AUTHORITY_MATRIX[resolved_lane]


def assert_authorized(
    lane: BuildLane | str,
    action: BuildAction | str,
) -> None:
    resolved_lane = normalize_lane(lane)
    resolved_action = normalize_action(action)
    if can_perform(resolved_lane, resolved_action):
        return
    allowed = ", ".join(sorted(item.value for item in AUTHORITY_MATRIX[resolved_lane]))
    raise AuthorityError(
        f"lane '{resolved_lane.value}' is not authorized for '{resolved_action.value}' "
        f"(allowed: {allowed})"
    )


__all__ = [
    "AUTHORITY_MATRIX",
    "AuthorityError",
    "BuildAction",
    "BuildLane",
    "SettlementState",
    "assert_authorized",
    "can_perform",
    "lane_actions",
    "normalize_action",
    "normalize_lane",
]
