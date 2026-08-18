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
    memory: Any = None,
    include_memory_content: bool = False,
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

    lines += ["", "## Memory"]
    status = getattr(memory, "status", None) if memory is not None else None
    detail = str(getattr(memory, "detail", "") or "")
    excerpt = str(getattr(memory, "excerpt", "") or "")

    if status is None or status == "not_configured":
        lines.append(
            "NOT CONFIGURED — no memory kernel was available to this cycle. No "
            "read was attempted. This is not the same as recalling nothing."
        )
    elif status == "unavailable":
        lines.append(
            f"UNAVAILABLE — the memory organ could not be loaded, so no read was "
            f"attempted. This is a fault, not an empty memory: {detail}"
        )
    elif status == "read_failed":
        # Never render a failed read as silence. A read that ran and broke is a
        # live fault; collapsing it into "not consulted" hides it in the one
        # artifact that is durably recorded.
        lines.append(
            f"READ FAILED — memory was consulted and the read raised. Recall is "
            f"missing from this cycle's plan because of a fault, NOT because "
            f"policy admitted nothing: {detail}"
        )
    else:
        admitted = getattr(memory, "admitted", 0)
        candidates = getattr(memory, "candidates", 0)
        meta = getattr(memory, "metadata", {}) or {}
        lines.append(
            f"Consulted through MemoryKernel ({admitted} admitted of "
            f"{candidates} candidates). 0 admitted means policy excluded them, "
            f"not that memory was skipped."
        )

        # Isolation is REPORTED FROM THE READ, never asserted. An earlier
        # revision hardcoded "supervisor-scoped ... other agents omitted as
        # agent_not_allowed". That sentence is false whenever the legacy escape
        # hatch downgrades isolation_mode to "unrestricted", in which case
        # context_admission applies no agent filter at all — so the brief would
        # promise an isolation guarantee that did not hold, in the one artifact
        # an operator trusts for provenance.
        applied = meta.get("isolation_applied")
        semantics = str(meta.get("isolation_semantics") or "unknown")
        allowed = meta.get("allowed_agent_ids") or []

        # Keyed on SEMANTICS, not on `applied`. `applied` is true even under the
        # legacy escape hatch (DHARMA_MEMORY_KERNEL_ISOLATION_LEGACY), which
        # returns semantics="legacy" while the budget is built with
        # isolation_mode="unrestricted" — and `_omission_reasons` then skips
        # owner filtering for non-AGENT-scope atoms. Keying on `applied` alone
        # printed "Isolation ENFORCED: legacy ... omitted as agent_not_allowed"
        # while another agent's swarm-scope memory could enter this artifact.
        # Only `*_scoped` semantics actually filter by owner.
        scoped = applied and semantics.endswith("_scoped")
        if scoped:
            lines.append(
                f"Isolation ENFORCED: {semantics}; readable agent ids "
                f"{allowed or '(none declared)'}. Atoms owned by other agents "
                f"are omitted as `agent_not_allowed`."
            )
        else:
            lines.append(
                f"Isolation NOT ENFORCED (applied={bool(applied)}, "
                f"semantics={semantics}). Owner filtering did not run, so atoms "
                f"admitted here MAY belong to other agents. Do not read this "
                f"section as Sarathi-only recall."
            )
        for warning in meta.get("isolation_warnings") or []:
            lines.append(f"Isolation warning: {warning}")

        if excerpt and include_memory_content:
            lines += [
                "",
                "The pack below includes content snippets of admitted atoms, not "
                "references alone, and is written to disk with this brief.",
                "",
                excerpt.rstrip(),
            ]
        elif excerpt:
            # Default: counts and provenance, NOT payloads. The supported
            # entrypoint reads with include_content=True and the daemon persists
            # this brief under the state root, so embedding the pack verbatim
            # puts memory content on disk every wake cycle. Disclosure alone did
            # not reduce that footprint. The operator can opt in per call.
            lines.append(
                "Pack content withheld from this durable brief (counts and "
                "provenance above). Pass include_memory_content=True to embed "
                "the admitted atoms' snippets."
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
