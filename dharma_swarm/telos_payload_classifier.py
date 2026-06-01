"""Typed-action payload harm classifier owned by the telos gate surface.

The ontology action chokepoint passes typed params as gatekeeper content for
credential/injection/deception scans. This helper handles the narrow case
where a param value expresses destructive command intent and should be routed
through the existing AHIMSA action-word path.
"""

from __future__ import annotations

import re
from typing import Any

PAYLOAD_HARM_TARGET_BLOCK = frozenset({
    "attack",
    "corrupt",
    "delete",
    "delete from",
    "destroy",
    "drop table",
    "erase",
    "exploit",
    "kill",
    "leak all",
    "overwrite",
    "remove every",
    "truncate table",
    "wipe",
})

PAYLOAD_HARM_GATEKEEPER_ALIASES = {
    "/etc/shadow": "exfiltrate",
    "delete": "destroy",
    "delete from": "drop table",
    "disable all telos gates": "corrupt",
    "disable telos gates": "corrupt",
    "erase": "destroy",
    "grant admin": "exploit",
    "leak all": "exfiltrate",
    "overwrite": "corrupt",
    "remove every": "destroy",
    "send all user emails": "exfiltrate",
}

PAYLOAD_HARD_BLOCK_PHRASE_ACTIONS = {
    "/etc/shadow": "exfiltrate",
    "bypass auth": "exploit",
    "bypass authentication": "exploit",
    "bypass gate": "corrupt",
    "bypass gates": "corrupt",
    "disable all telos gates": "corrupt",
    "disable gate": "corrupt",
    "disable safety gate": "corrupt",
    "disable the telos gate": "corrupt",
    "disable telos gates": "corrupt",
    "dump database credentials": "exfiltrate",
    "dump the database credentials": "exfiltrate",
    "email all user records": "exfiltrate",
    "escalate privilege": "exploit",
    "escalate privileges": "exploit",
    "fabricate audit": "exploit",
    "falsify audit": "exploit",
    "falsify receipt": "exploit",
    "grant admin": "exploit",
    "make the agent lie": "exploit",
    "publish api keys": "exfiltrate",
    "publish the api keys": "exfiltrate",
    "send passwords": "exfiltrate",
    "send all user emails": "exfiltrate",
    "turn off all safety gates": "corrupt",
    "turn off gate": "corrupt",
    "turn off safety gate": "corrupt",
}

PAYLOAD_DESTRUCTIVE_TARGET_VERBS = frozenset({
    "clear",
    "delete",
    "drain",
    "erase",
    "nuke",
    "purge",
    "remove",
    "scrub",
    "zero out",
})

PAYLOAD_EXFILTRATION_TARGET_VERBS = frozenset({
    "copy",
    "download",
    "dump",
    "email",
    "export",
    "extract",
    "harvest",
    "post",
    "publish",
    "send",
    "share",
    "upload",
})

PAYLOAD_PRIVILEGE_TARGET_VERBS = frozenset({
    "bypass",
    "disable",
    "elevate",
    "escalate",
    "grant",
    "override",
})

PAYLOAD_DECEPTION_TARGET_VERBS = frozenset({
    "fabricate",
    "fake",
    "falsify",
    "lie",
    "mislead",
})

PAYLOAD_HARM_TARGET_TERMS = frozenset({
    "all",
    "api key",
    "api keys",
    "auth",
    "billing",
    "credential",
    "credentials",
    "critical",
    "customer",
    "customers",
    "data",
    "database",
    "db",
    "disk",
    "email",
    "emails",
    "event",
    "events",
    "gate",
    "gates",
    "human",
    "humans",
    "identity",
    "key",
    "keys",
    "live",
    "people",
    "person",
    "prod",
    "production",
    "record",
    "records",
    "secret",
    "secrets",
    "session",
    "sessions",
    "system",
    "telos gate",
    "telos gates",
    "user",
    "users",
    "vulnerabilities",
    "vulnerability",
})

BENIGN_PAYLOAD_HARM_PHRASES = frozenset({
    "attack surface",
    "erase temp file",
    "erase temp files",
    "harm reduction",
    "kill stale",
    "kill-switch",
    "kill switch",
})


def _iter_payload_text_values(value: Any):
    """Yield text values from params without joining unrelated JSON keys."""
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_payload_text_values(child)
        return
    if isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _iter_payload_text_values(child)
        return
    if value is None:
        return
    yield str(value)


def _normalized_payload_text(value: str) -> str:
    return value.lower().replace("_", " ")


def _payload_text_has_phrase(text: str, phrase: str) -> bool:
    if phrase.startswith("/"):
        return phrase in text
    pattern = r"\s+".join(re.escape(part) for part in phrase.split())
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text) is not None


def _payload_value_has_harm_target(text: str) -> bool:
    return any(_payload_text_has_phrase(text, term) for term in PAYLOAD_HARM_TARGET_TERMS)


def _strip_benign_payload_harm_phrases(text: str) -> str:
    scrubbed = text
    for phrase in BENIGN_PAYLOAD_HARM_PHRASES:
        scrubbed = scrubbed.replace(phrase, " ")
    return scrubbed


def canonical_payload_harm_action(
    action_name: str,
    params: Any,
    harm_words: set[str],
) -> str | None:
    """Return an action string that lets ``check_action`` enforce param harm."""
    target_block = PAYLOAD_HARM_TARGET_BLOCK & harm_words
    always_block = harm_words - target_block
    for text in _iter_payload_text_values(params):
        lowered = _strip_benign_payload_harm_phrases(_normalized_payload_text(text))
        for phrase, gatekeeper_word in sorted(
            PAYLOAD_HARD_BLOCK_PHRASE_ACTIONS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if _payload_text_has_phrase(lowered, phrase):
                return f"{action_name} {gatekeeper_word}"
        if _payload_value_has_harm_target(lowered):
            for word in sorted(PAYLOAD_DESTRUCTIVE_TARGET_VERBS, key=len, reverse=True):
                if _payload_text_has_phrase(lowered, word):
                    return f"{action_name} destroy"
            for word in sorted(PAYLOAD_EXFILTRATION_TARGET_VERBS, key=len, reverse=True):
                if _payload_text_has_phrase(lowered, word):
                    return f"{action_name} exfiltrate"
            for word in sorted(PAYLOAD_PRIVILEGE_TARGET_VERBS, key=len, reverse=True):
                if _payload_text_has_phrase(lowered, word):
                    return f"{action_name} exploit"
            for word in sorted(PAYLOAD_DECEPTION_TARGET_VERBS, key=len, reverse=True):
                if _payload_text_has_phrase(lowered, word):
                    return f"{action_name} exploit"
        for word in sorted(always_block, key=len, reverse=True):
            if _payload_text_has_phrase(lowered, word):
                return f"{action_name} {word}"
        for word in sorted(PAYLOAD_HARM_TARGET_BLOCK, key=len, reverse=True):
            if _payload_text_has_phrase(lowered, word) and _payload_value_has_harm_target(lowered):
                gatekeeper_word = word if word in target_block else PAYLOAD_HARM_GATEKEEPER_ALIASES.get(word, "destroy")
                return f"{action_name} {gatekeeper_word}"
    return None
