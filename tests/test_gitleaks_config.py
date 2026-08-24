"""Fail-closed contracts for the repository Gitleaks exception surface."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


CONFIG_PATH = Path(".gitleaks.toml")
SADHANA_FIXTURE_PATTERN = r"^idempotency-[0-9]{3}$"
ED25519_TYPE_PATTERN = r"^Ed25519PrivateKey$"


def _config() -> dict[str, object]:
    with CONFIG_PATH.open("rb") as stream:
        return tomllib.load(stream)


def test_sadhana_idempotency_exception_is_exact_and_not_path_wide() -> None:
    config = _config()
    allowlist = config["allowlist"]
    assert isinstance(allowlist, dict)
    regexes = allowlist["regexes"]
    paths = allowlist["paths"]
    assert isinstance(regexes, list)
    assert isinstance(paths, list)
    assert regexes.count(SADHANA_FIXTURE_PATTERN) == 1
    assert not any("dashboard" in str(path).lower() for path in paths)


def test_sadhana_idempotency_exception_rejects_broader_token_shapes() -> None:
    fixture = re.compile(SADHANA_FIXTURE_PATTERN)
    assert fixture.fullmatch("idempotency-000")
    assert fixture.fullmatch("idempotency-999")

    for candidate in (
        "idempotency-00",
        "idempotency-0000",
        "prefix-idempotency-001",
        "idempotency-001-suffix",
        "IDEMPOTENCY-001",
        "idempotency-abc",
        "idempotency-sk-proj-0123456789abcdef",
        "production-idempotency-secret-001",
    ):
        assert fixture.fullmatch(candidate) is None


def test_ed25519_type_exception_is_exact_unique_and_rule_scoped() -> None:
    config = _config()
    rules = config["rules"]
    assert isinstance(rules, list)
    matching_rules = [rule for rule in rules if rule.get("id") == "generic-api-key"]
    assert len(matching_rules) == 1

    allowlist = matching_rules[0]["allowlist"]
    assert isinstance(allowlist, dict)
    assert set(allowlist) == {"description", "regexTarget", "regexes"}
    assert allowlist["regexTarget"] == "secret"
    regexes = allowlist["regexes"]
    assert isinstance(regexes, list)
    assert regexes == [ED25519_TYPE_PATTERN]

    global_allowlist = config["allowlist"]
    assert isinstance(global_allowlist, dict)
    assert ED25519_TYPE_PATTERN not in global_allowlist["regexes"]
    assert "commits" not in global_allowlist


def test_ed25519_type_exception_rejects_other_literal_shapes() -> None:
    identifier = re.compile(ED25519_TYPE_PATTERN)
    assert identifier.fullmatch("Ed25519PrivateKey")

    credential_shaped = "api-key-" + ("A1b2" * 8)
    for candidate in (
        "prefix-Ed25519PrivateKey",
        "Ed25519PrivateKey-suffix",
        "ed25519PrivateKey",
        "Ed25519privateKey",
        "ED25519PRIVATEKEY",
        credential_shaped,
    ):
        assert identifier.fullmatch(candidate) is None
