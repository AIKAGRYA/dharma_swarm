"""Portable Agent Card export formats.

The export layer is deliberately read-only: every packet is derived from the
AgentCardIndex projection and points back to existing identity lanes instead of
owning identity itself.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Literal

PUBLIC_CARD_SCHEMA_VERSION = "dharma.agent_card.public.v0"
EXTENDED_CARD_SCHEMA_VERSION = "dharma.agent_card.extended.v0"

AgentCardExportFormat = Literal[
    "public-json",
    "extended-json",
    "operator-json",
    "markdown",
    "jcard",
    "vcard",
]

_PATH_KEYS = {"path", "identity_file", "source_path"}
_LOCAL_PATH_PREFIXES = ("/Users/", "/private/", "/tmp/", "~/")


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strip_local_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_local_paths(item)
            for key, item in value.items()
            if key not in _PATH_KEYS
        }
    if isinstance(value, list):
        return [_strip_local_paths(item) for item in value]
    if isinstance(value, str) and value.startswith(_LOCAL_PATH_PREFIXES):
        return "[local-path-redacted]"
    return value


def _finding_without_path(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "severity": _text(finding.get("severity")),
        "check": _text(finding.get("check")),
        "agent_uid": _text(finding.get("agent_uid")),
        "detail": _text(finding.get("detail")),
    }


def _source_summary(agent: dict[str, Any]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for key, paths in _safe_dict(agent.get("sources")).items():
        summary[str(key)] = len(_safe_list(paths))
    return summary


def public_agent_card(agent: dict[str, Any]) -> dict[str, Any]:
    """Return the safe public discovery subset for unauthenticated handoff."""
    handoff = _safe_dict(agent.get("handoff"))
    return {
        "schema_version": PUBLIC_CARD_SCHEMA_VERSION,
        "agent_uid": _text(agent.get("agent_uid")),
        "display_name": _text(agent.get("display_name")),
        "callsign": _text(agent.get("callsign")),
        "role": _text(agent.get("role")),
        "status": _text(agent.get("status")),
        "endpoint": _text(agent.get("endpoint")),
        "provider": _text(agent.get("provider")),
        "model": _text(agent.get("model")),
        "harness": _text(agent.get("harness")),
        "capabilities": _safe_list(agent.get("capabilities")),
        "skills": _safe_list(agent.get("skills")),
        "semantic": _strip_local_paths(_safe_dict(agent.get("semantic"))),
        "a2a": _safe_dict(agent.get("a2a")),
        "nats": _safe_dict(agent.get("nats")),
        "trust_grade": _text(agent.get("trust_grade")),
        "handoff": {
            "public_card_ready": bool(handoff.get("public_card_ready")),
            "suggested_subjects": _safe_list(handoff.get("suggested_subjects")),
        },
    }


def extended_agent_card(agent: dict[str, Any]) -> dict[str, Any]:
    """Return an authenticated handoff card without local filesystem paths."""
    handoff = _safe_dict(agent.get("handoff"))
    return {
        **public_agent_card(agent),
        "schema_version": EXTENDED_CARD_SCHEMA_VERSION,
        "department": _text(agent.get("department")),
        "squad_id": _text(agent.get("squad_id")),
        "team_id": _text(agent.get("team_id")),
        "authority": _text(agent.get("authority")),
        "card_names": _safe_list(agent.get("card_names")),
        "registration": _strip_local_paths(_safe_dict(agent.get("registration"))),
        "identity_invariant": _strip_local_paths(
            _safe_dict(agent.get("identity_invariant"))
        ),
        "authority_passport": _strip_local_paths(
            _safe_dict(agent.get("authority_passport"))
        ),
        "living_dock": _strip_local_paths(_safe_dict(agent.get("living_dock"))),
        "source_summary": _source_summary(agent),
        "findings": [
            _finding_without_path(item)
            for item in _safe_list(agent.get("findings"))
            if isinstance(item, dict)
        ],
        "handoff": {
            "public_card_ready": bool(handoff.get("public_card_ready")),
            "extended_card_ready": bool(handoff.get("extended_card_ready")),
            "operator_card_ready": bool(handoff.get("operator_card_ready")),
            "suggested_subjects": _safe_list(handoff.get("suggested_subjects")),
        },
    }


def operator_agent_card(agent: dict[str, Any]) -> dict[str, Any]:
    """Return the full local operator card, including source path evidence."""
    return copy.deepcopy(agent)


def render_agent_card_markdown(agent: dict[str, Any]) -> str:
    card = extended_agent_card(agent)
    findings = _safe_list(card.get("findings"))
    capabilities = ", ".join(str(item) for item in _safe_list(card.get("capabilities"))) or "-"
    subjects = "\n".join(
        f"- `{subject}`"
        for subject in _safe_list(_safe_dict(card.get("handoff")).get("suggested_subjects"))
    )
    findings_lines = "\n".join(
        f"- `{item.get('severity')}` `{item.get('check')}`: {item.get('detail')}"
        for item in findings
        if isinstance(item, dict)
    )
    if not findings_lines:
        findings_lines = "- none"
    if not subjects:
        subjects = "- none"

    return "\n".join(
        [
            f"# Agent Card: {card.get('display_name') or card.get('agent_uid')}",
            "",
            f"- Agent UID: `{card.get('agent_uid')}`",
            f"- Callsign: `{card.get('callsign')}`",
            f"- Role: `{card.get('role')}`",
            f"- Status: `{card.get('status')}`",
            f"- Trust: `{card.get('trust_grade')}`",
            f"- Model: `{card.get('model') or card.get('provider')}`",
            f"- Harness: `{card.get('harness')}`",
            f"- Endpoint: `{card.get('endpoint')}`",
            f"- Authority: `{card.get('authority')}`",
            f"- Semantic Object: `{_safe_dict(card.get('semantic')).get('canonical_object_id', '') or 'unresolved'}`",
            f"- Capabilities: {capabilities}",
            "",
            "## Handoff Subjects",
            "",
            subjects,
            "",
            "## Findings",
            "",
            findings_lines,
            "",
        ]
    )


def _jcard_text_property(name: str, value: Any) -> list[Any]:
    return [name, {}, "text", _text(value)]


def agent_card_jcard(agent: dict[str, Any]) -> list[Any]:
    """Return a jCard-compatible digital meishi."""
    card = public_agent_card(agent)
    properties: list[list[Any]] = [
        _jcard_text_property("version", "4.0"),
        _jcard_text_property("fn", card.get("display_name") or card.get("agent_uid")),
        _jcard_text_property("nickname", card.get("callsign")),
        _jcard_text_property("role", card.get("role")),
        ["note", {}, "text", f"Agent UID: {card.get('agent_uid')} | Trust: {card.get('trust_grade')}"],
        _jcard_text_property("x-agent-uid", card.get("agent_uid")),
        _jcard_text_property("x-agent-trust-grade", card.get("trust_grade")),
        _jcard_text_property("x-agent-model", card.get("model") or card.get("provider")),
        _jcard_text_property("x-agent-harness", card.get("harness")),
    ]
    endpoint = _text(card.get("endpoint"))
    if endpoint:
        properties.append(["url", {"type": "endpoint"}, "uri", endpoint])
    for capability in _safe_list(card.get("capabilities")):
        properties.append(_jcard_text_property("x-agent-capability", capability))
    for subject in _safe_list(_safe_dict(card.get("handoff")).get("suggested_subjects")):
        properties.append(_jcard_text_property("x-agent-subject", subject))
    return ["vcard", properties]


def _escape_vcard(value: Any) -> str:
    text = _text(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _vcard_line(name: str, value: Any) -> str:
    return f"{name}:{_escape_vcard(value)}"


def render_agent_card_vcard(agent: dict[str, Any]) -> str:
    card = public_agent_card(agent)
    capabilities = ",".join(
        _escape_vcard(item) for item in _safe_list(card.get("capabilities"))
    )
    lines = [
        "BEGIN:VCARD",
        "VERSION:4.0",
        _vcard_line("FN", card.get("display_name") or card.get("agent_uid")),
        _vcard_line("NICKNAME", card.get("callsign")),
        _vcard_line("ROLE", card.get("role")),
        _vcard_line(
            "NOTE",
            f"Agent UID: {card.get('agent_uid')} | Trust: {card.get('trust_grade')}",
        ),
        _vcard_line("X-AGENT-UID", card.get("agent_uid")),
        _vcard_line("X-AGENT-TRUST-GRADE", card.get("trust_grade")),
        _vcard_line("X-AGENT-MODEL", card.get("model") or card.get("provider")),
        _vcard_line("X-AGENT-HARNESS", card.get("harness")),
    ]
    endpoint = _text(card.get("endpoint"))
    if endpoint:
        lines.append(_vcard_line("URL", endpoint))
    if capabilities:
        lines.append(f"CATEGORIES:{capabilities}")
    for subject in _safe_list(_safe_dict(card.get("handoff")).get("suggested_subjects")):
        lines.append(_vcard_line("X-AGENT-SUBJECT", subject))
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def normalize_export_format(value: str) -> AgentCardExportFormat:
    key = re.sub(r"[\s_]+", "-", _text(value).lower())
    aliases: dict[str, AgentCardExportFormat] = {
        "public": "public-json",
        "public-json": "public-json",
        "json": "public-json",
        "extended": "extended-json",
        "extended-json": "extended-json",
        "operator": "operator-json",
        "operator-json": "operator-json",
        "markdown": "markdown",
        "md": "markdown",
        "jcard": "jcard",
        "vcard": "vcard",
        "vcf": "vcard",
    }
    if key not in aliases:
        raise ValueError(f"Unsupported Agent Card export format: {value}")
    return aliases[key]


def export_agent_card(
    agent: dict[str, Any],
    export_format: str,
) -> tuple[str, str, str]:
    """Render an Agent Card export as (body, media_type, file_extension)."""
    normalized = normalize_export_format(export_format)
    if normalized == "public-json":
        return (
            json.dumps(public_agent_card(agent), indent=2, ensure_ascii=True, sort_keys=True)
            + "\n",
            "application/json",
            "public.json",
        )
    if normalized == "extended-json":
        return (
            json.dumps(extended_agent_card(agent), indent=2, ensure_ascii=True, sort_keys=True)
            + "\n",
            "application/json",
            "extended.json",
        )
    if normalized == "operator-json":
        return (
            json.dumps(operator_agent_card(agent), indent=2, ensure_ascii=True, sort_keys=True)
            + "\n",
            "application/json",
            "operator.json",
        )
    if normalized == "markdown":
        return render_agent_card_markdown(agent), "text/markdown; charset=utf-8", "md"
    if normalized == "jcard":
        return (
            json.dumps(agent_card_jcard(agent), indent=2, ensure_ascii=True)
            + "\n",
            "application/jcard+json",
            "jcard.json",
        )
    return render_agent_card_vcard(agent), "text/vcard; charset=utf-8", "vcf"
