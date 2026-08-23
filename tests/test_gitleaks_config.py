"""Fail-closed contracts for the repository Gitleaks exception surface."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


CONFIG_PATH = Path(".gitleaks.toml")
SADHANA_FIXTURE_PATTERN = r"^idempotency-[0-9]{3}$"


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
