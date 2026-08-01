"""Operator brief rendering for Sarathi.

v2 (PR-S2) appends a delegation ledger — planned / gated / logged / proposed /
dispatched / completed, each row carrying its receipt reference — and an
explicit runtime-audit line. The brief never fabricates state: a missing
audit renders as MISSING, and the audit JSON always outranks this prose.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .pulse import sarathi_pulse

_LEDGER_ORDER = ("gated", "logged", "proposed", "dispatched")


def _outcome_row(outcome: Any) -> str:
    data = outcome.to_dict() if hasattr(outcome, "to_dict") else dict(outcome)
    receipt = data.get("receipt_ref") or "-"
    gate = data.get("gate") or {}
    return (
        f"- [{data.get('status')}] {data.get('summary')} -> {data.get('recipient')} "
        f"(channel={data.get('channel')}, gate={gate.get('action_class')}, "
        f"receipt={receipt})"
    )


def build_operator_brief(
    pulse: dict[str, object] | None = None,
    *,
    outcomes: Sequence[Any] | None = None,
    responses: Sequence[Mapping[str, Any]] | None = None,
    audit: Mapping[str, Any] | None = None,
) -> str:
    pulse = pulse or sarathi_pulse()
    lines = [
        "# Sarathi Operator Brief",
        "",
        "Status: not alive; no unattended wake-loop proof is claimed.",
        f"Schema: {pulse.get('schema_version')}",
        "",
        "## Roster",
    ]
    for row in pulse.get("roster", []) or []:
        if isinstance(row, dict):
            lines.append(f"- {row.get('name')}: registered={row.get('registered')} kill_requested={row.get('kill_requested')}")

    if outcomes is not None or responses is not None:
        lines += ["", "## Delegation ledger"]
        outcome_list = list(outcomes or [])
        rows = [o.to_dict() if hasattr(o, "to_dict") else dict(o) for o in outcome_list]
        counts: dict[str, int] = {status: 0 for status in _LEDGER_ORDER}
        for row in rows:
            status = str(row.get("status"))
            counts[status] = counts.get(status, 0) + 1
        completed = list(responses or [])
        summary = ", ".join(f"{status}={counts.get(status, 0)}" for status in _LEDGER_ORDER)
        lines.append(f"Planned={len(rows)}, {summary}, completed={len(completed)}")
        for outcome in outcome_list:
            lines.append(_outcome_row(outcome))
        for response in completed:
            lines.append(
                f"- [completed] {response.get('summary')} by {response.get('responder')} "
                f"(task={response.get('task_id')}, response_ref={response.get('response_ref') or '-'})"
            )

    lines += ["", "## Runtime audit"]
    if audit is None:
        lines.append(
            "latest_audit.json: MISSING from this cycle's boot pack — no runtime "
            "claims are made in its absence."
        )
    else:
        lines.append(
            "latest_audit.json: present in the boot pack; that JSON outranks this "
            "brief wherever they disagree."
        )
    return "\n".join(lines) + "\n"


__all__ = ["build_operator_brief"]
