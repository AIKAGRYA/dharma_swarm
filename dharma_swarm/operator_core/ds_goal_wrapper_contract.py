"""Read-only contract helpers for the installed ds-goal wrapper."""

from __future__ import annotations

import hashlib
import re
import shlex
from pathlib import Path
from typing import Any


_TARGET_REPOS = ("dharma_swarm", "dharma_swarm_main")
_TARGET_PATTERNS = {
    "dharma_swarm": re.compile(r"(?:\$HOME|~)/dharma_swarm(?![_A-Za-z0-9-])"),
    "dharma_swarm_main": re.compile(
        r"(?:\$HOME|~)/dharma_swarm_main(?![_A-Za-z0-9-])"
    ),
}
_REPO_ASSIGNMENT = re.compile(
    r"""\brepo\s*=\s*["']?(?:\$HOME|~)/(?P<repo>dharma_swarm(?:_main)?)(?![_A-Za-z0-9-])"""
)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


def _append_unique(items: list[str], value: str) -> None:
    if value in _TARGET_REPOS and value not in items:
        items.append(value)


def _active_wrapper_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        code = raw_line.split("#", 1)[0].strip()
        if code:
            lines.append(code)
    return lines


def _wrapper_target_order(text: str) -> dict[str, Any]:
    conditional_order: list[str] = []
    assignment_order: list[str] = []
    assignment_sequence: list[str] = []

    for line in _active_wrapper_lines(text):
        if "DHARMA_SWARM_REPO" in line:
            continue

        line_matches = sorted(
            (
                (match.start(), repo)
                for repo, pattern in _TARGET_PATTERNS.items()
                if (match := pattern.search(line))
            ),
            key=lambda item: item[0],
        )
        is_condition = (
            "scripts/runtime/autonomy_spine.py" in line
            or "[[ -f" in line
            or " -f " in line
        )
        if is_condition:
            for _, repo in line_matches:
                _append_unique(conditional_order, repo)

        assignment = _REPO_ASSIGNMENT.search(line)
        if assignment:
            repo = assignment.group("repo")
            if repo in _TARGET_REPOS:
                assignment_sequence.append(repo)
            _append_unique(assignment_order, repo)

    order: list[str] = []
    for repo in [*conditional_order, *assignment_order]:
        _append_unique(order, repo)

    return {
        "default_target_order": order,
        "conditional_target_order": conditional_order,
        "fallback_target": assignment_sequence[-1] if assignment_sequence else "",
    }


def _repo_path(home: Path, repo: str) -> Path:
    if repo == "dharma_swarm_main":
        return home / "dharma_swarm_main"
    return home / "dharma_swarm"


def _repo_source(repo: str, *, fallback: bool = False) -> str:
    if repo == "dharma_swarm_main":
        return "installed_wrapper_dharma_swarm_main_preference"
    if fallback:
        return "installed_wrapper_dharma_swarm_fallback"
    return "installed_wrapper_dharma_swarm_preference"


def installed_wrapper_contract(wrapper: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "wrapper_exists": wrapper.exists(),
        "wrapper_sha256": "",
        "dharma_swarm_repo_pin_supported": False,
        "dharma_swarm_preference_declared": False,
        "dharma_swarm_main_preference_declared": False,
        "dharma_swarm_fallback_declared": False,
        "default_target_order": [],
        "conditional_target_order": [],
        "fallback_target": "",
        "execs_autonomy_spine": False,
        "read_error": "",
    }
    if not wrapper.exists():
        result["read_error"] = "wrapper missing"
        return result
    try:
        text = wrapper.read_text(encoding="utf-8")
    except OSError as exc:
        result["read_error"] = str(exc)
        return result
    target_order = _wrapper_target_order(text)
    active_text = "\n".join(_active_wrapper_lines(text))
    default_order = list(target_order["default_target_order"])
    result["wrapper_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    result["dharma_swarm_repo_pin_supported"] = "DHARMA_SWARM_REPO" in active_text
    result["dharma_swarm_preference_declared"] = bool(default_order) and (
        default_order[0] == "dharma_swarm"
    )
    result["dharma_swarm_main_preference_declared"] = bool(default_order) and (
        default_order[0] == "dharma_swarm_main"
    )
    result["dharma_swarm_fallback_declared"] = "dharma_swarm" in default_order
    result["default_target_order"] = default_order
    result["conditional_target_order"] = list(target_order["conditional_target_order"])
    result["fallback_target"] = str(target_order["fallback_target"] or "")
    result["execs_autonomy_spine"] = "scripts/runtime/autonomy_spine.py" in active_text
    return result


def default_wrapper_target(
    *,
    home: Path,
    audited_repo: Path,
    wrapper: Path,
) -> dict[str, Any]:
    contract = installed_wrapper_contract(wrapper)
    conditional_order = [
        str(repo)
        for repo in contract.get("conditional_target_order") or []
        if str(repo) in _TARGET_REPOS
    ]
    fallback_target = str(contract.get("fallback_target") or "")
    default_order = [
        str(repo)
        for repo in contract.get("default_target_order") or []
        if str(repo) in _TARGET_REPOS
    ]

    target: Path | None = None
    source = ""
    for repo in conditional_order:
        candidate = _repo_path(home, repo)
        if (candidate / "scripts" / "runtime" / "autonomy_spine.py").exists():
            target = candidate
            source = _repo_source(repo)
            break

    if target is None:
        if fallback_target in _TARGET_REPOS:
            target = _repo_path(home, fallback_target)
            source = _repo_source(fallback_target, fallback=True)
        elif default_order:
            target = _repo_path(home, default_order[0])
            source = _repo_source(default_order[0])
        elif (
            home
            / "dharma_swarm_main"
            / "scripts"
            / "runtime"
            / "autonomy_spine.py"
        ).exists():
            target = home / "dharma_swarm_main"
            source = "assumed_dharma_swarm_main_preference_unparsed"
        else:
            target = home / "dharma_swarm"
            source = "assumed_dharma_swarm_fallback_unparsed"
    return {
        "target_repo": str(target),
        "target_resolution_source": source,
        "target_matches_audited_repo": _same_resolved_path(target, audited_repo)
        if target.exists() and audited_repo.exists()
        else str(target) == str(audited_repo),
        "installed_wrapper_contract": contract,
    }


def wrapper_convergence_decision_packet(
    *,
    home: Path,
    audited_repo: Path,
    wrapper: Path,
) -> dict[str, Any]:
    """Build the non-mutating operator packet for wrapper convergence.

    This function deliberately does not inspect receipt DB state and does not
    edit the installed wrapper or target checkout. Runtime proof remains owned
    by ds_goal_wrapper_receipt_probe.py and runtime_receipt_coverage_report.py.
    """

    target = default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    contract = target.get("installed_wrapper_contract")
    if not isinstance(contract, dict):
        contract = installed_wrapper_contract(wrapper)
    pin_supported = bool(contract.get("dharma_swarm_repo_pin_supported"))
    target_matches = target.get("target_matches_audited_repo") is True
    safe_invocation = ""
    if pin_supported:
        safe_invocation = (
            f"DHARMA_SWARM_REPO={shlex.quote(str(audited_repo))} "
            f"{shlex.quote(str(wrapper))}"
        )
    approval_state = (
        "not_required_default_matches_audited_checkout"
        if target_matches
        else "operator_approval_required"
    )
    return {
        "schema_version": "dharma.ds_goal_wrapper_convergence_decision.v1",
        "approval_state": approval_state,
        "operator_approval_required": not target_matches,
        "score_effect": (
            "no_score_movement_until_default_wrapper_or_target_is_converged_and_"
            "post_change_receipt_gate_evidence_passes"
        ),
        "installed_wrapper_path": str(wrapper),
        "installed_wrapper_sha256": str(contract.get("wrapper_sha256") or ""),
        "audited_checkout": str(audited_repo),
        "default_target_repo": str(target.get("target_repo") or ""),
        "default_target_resolution_source": str(
            target.get("target_resolution_source") or ""
        ),
        "default_target_matches_audited_checkout": target_matches,
        "safe_current_checkout_invocation": safe_invocation,
        "current_mitigation": (
            "use_DHARMA_SWARM_REPO_pin_for_each_invocation"
            if safe_invocation and not target_matches
            else "none_needed"
            if target_matches
            else "none_available"
        ),
        "operator_decision_options": [
            {
                "id": "converge_installed_wrapper_default_to_audited_checkout",
                "requires_operator_approval": True,
                "summary": (
                    "Change the installed ds-goal default target so unpinned "
                    "invocations resolve to the audited checkout."
                ),
                "post_change_evidence": [
                    "default wrapper temp run produces keyed task_claim and "
                    "delegation_run receipts",
                    "runtime_receipt_coverage_report active-head windows are "
                    "clean after a fresh default invocation",
                    "make onboard and make orient show target_matches_current=true",
                ],
            },
            {
                "id": "harden_current_default_target_checkout",
                "requires_operator_approval": True,
                "summary": (
                    "Keep the installed wrapper target but patch/sync that "
                    "checkout to the audited receipt hardening."
                ),
                "post_change_evidence": [
                    "default target source shows sync side-effect-key hardening",
                    "default wrapper temp run produces keyed task_claim and "
                    "delegation_run receipts",
                    "live census no longer reports "
                    "ds_goal_cli_target_lacks_sync_side_effect_hardening",
                ],
            },
            {
                "id": "retain_default_with_mandatory_pin_or_quarantine",
                "requires_operator_approval": True,
                "summary": (
                    "Leave the default target unchanged, require the audited "
                    "checkout pin for runtime use, and keep the production "
                    "readiness cap in place."
                ),
                "post_change_evidence": [
                    "operator-approved quarantine is recorded in governance",
                    "all runtime invocations use the safe pin command",
                    "production readiness remains blocked until default-path "
                    "proof exists",
                ],
            },
        ],
        "forbidden_without_operator_approval": [
            "edit_installed_wrapper",
            "patch_default_target_checkout",
            "start_repo_native_longrun_from_unpinned_ds_goal",
            "declare_75_plus_from_pin_mitigation_only",
        ],
        "preflight_commands": [
            "python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict",
            "python3 scripts/runtime/ds_goal_longrun_preflight.py --json",
            (
                "DHARMA_SWARM_REPO="
                f"{shlex.quote(str(audited_repo))} "
                "python3 scripts/runtime/ds_goal_longrun_preflight.py --json"
            ),
            "python3 scripts/runtime/live_ops_census.py --write",
            (
                "python3 scripts/runtime/ds_goal_wrapper_receipt_probe.py "
                "--expect-split-brain --json"
            ),
            "python3 scripts/governance/runtime_receipt_coverage_report.py --strict",
            "make onboard",
        ],
        "post_change_verifier_commands": [
            "python3 scripts/runtime/live_ops_census.py --write",
            "python3 scripts/runtime/ds_goal_wrapper_receipt_probe.py --json",
            "python3 scripts/governance/runtime_receipt_coverage_report.py --strict",
            "make onboard",
            "make orient",
        ],
    }


def wrapper_longrun_preflight_gate(
    *,
    home: Path,
    audited_repo: Path,
    wrapper: Path,
    repo_pin: Path | None = None,
    repo_pin_source: str = "none",
) -> dict[str, Any]:
    """Return a read-only start gate for repo-native ds-goal longruns.

    The gate is intentionally conservative: pinning the audited checkout may
    allow this invocation to start, but it does not converge the installed
    wrapper default and does not justify readiness score movement.
    """

    target = default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    decision = wrapper_convergence_decision_packet(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    contract = target.get("installed_wrapper_contract")
    if not isinstance(contract, dict):
        contract = installed_wrapper_contract(wrapper)
    default_matches = target.get("target_matches_audited_repo") is True
    pin_matches = (
        _same_resolved_path(repo_pin, audited_repo)
        if repo_pin is not None and repo_pin.exists() and audited_repo.exists()
        else str(repo_pin) == str(audited_repo)
        if repo_pin is not None
        else False
    )

    passed = False
    status = "blocked_unpinned_default_target"
    reason = (
        "installed ds-goal default target does not match the audited checkout; "
        "set DHARMA_SWARM_REPO to the audited checkout before starting a longrun"
    )
    if not contract.get("wrapper_exists"):
        status = "blocked_wrapper_missing"
        reason = "installed ds-goal wrapper is missing"
    elif contract.get("read_error"):
        status = "blocked_wrapper_unreadable"
        reason = f"installed ds-goal wrapper is unreadable: {contract.get('read_error')}"
    elif default_matches:
        passed = True
        status = "pass_default_matches_audited_checkout"
        reason = "installed ds-goal default target already matches the audited checkout"
    elif repo_pin is not None and pin_matches:
        passed = True
        status = "pass_explicit_audited_checkout_pin"
        reason = (
            "this invocation is pinned to the audited checkout; default wrapper "
            "convergence is still required before score movement"
        )
    elif repo_pin is not None:
        status = "blocked_repo_pin_mismatch"
        reason = "repo pin does not match the audited checkout"

    return {
        "schema_version": "dharma.ds_goal_longrun_preflight.v1",
        "read_only": True,
        "passed": passed,
        "longrun_start_allowed": passed,
        "status": status,
        "reason": reason,
        "score_effect": "no_score_movement_preflight_only",
        "audited_checkout": str(audited_repo),
        "installed_wrapper_path": str(wrapper),
        "repo_pin": str(repo_pin) if repo_pin is not None else "",
        "repo_pin_source": repo_pin_source,
        "repo_pin_matches_audited_checkout": pin_matches,
        "default_target_repo": str(target.get("target_repo") or ""),
        "default_target_resolution_source": str(
            target.get("target_resolution_source") or ""
        ),
        "default_target_matches_audited_checkout": default_matches,
        "safe_current_checkout_invocation": str(
            decision.get("safe_current_checkout_invocation") or ""
        ),
        "operator_convergence_required": not default_matches,
        "current_mitigation": str(decision.get("current_mitigation") or ""),
        "forbidden_without_operator_approval": list(
            decision.get("forbidden_without_operator_approval") or []
        ),
        "convergence_decision_packet": decision,
    }
