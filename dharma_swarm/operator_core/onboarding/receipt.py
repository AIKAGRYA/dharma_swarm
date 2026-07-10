"""Strict reader-first negotiation for onboarding receipt v1 and v2."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.memory_kernel.write_receipts import stable_digest

from .models import (
    RECEIPT_SCHEMA_V1,
    RECEIPT_SCHEMA_V2,
    LoadedReceipt,
    ReceiptValidationError,
    UnsupportedReceiptSchema,
    _VOLATILE_KEYS,
)


_SCHEMA_RE = re.compile(r"^dharma_swarm\.onboard_receipt\.v([1-9][0-9]*)$")
_EXTENSION_SCHEMA_RE = re.compile(r"^[A-Za-z0-9_.-]+\.v[1-9][0-9]*$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z$"
)
_V1_KEYS = {
    "schema", "observed_at", "authority", "repo", "work_lanes", "portfolio",
    "next_items", "swarm_bulletins", "broken_register", "open_prs",
    "runtime_truth_packets",
}
_V2_KEYS = {
    "schema", "authority", "observed_at", "primary_verdict", "exit_code",
    "stable_core", "live_delta", "cache", "delta", "legacy_v1", "extensions",
    "stable_digest",
}
_STABLE_CORE_KEYS = {
    "repository", "contract", "packet", "portfolio", "orientation",
    "required_reading",
}
_VERDICTS = {
    "READY", "BLOCKED", "NEEDS_HOST", "CONFIG_ERROR", "TOOLCHAIN_MISSING",
    "USAGE_ERROR",
}
_EXIT_BY_VERDICT = {
    "READY": {0},
    "BLOCKED": {1},
    "NEEDS_HOST": {0, 4},
    "CONFIG_ERROR": {3},
    "TOOLCHAIN_MISSING": {5},
    "USAGE_ERROR": {2},
}


def compute_stable_digest(stable_core: Mapping[str, Any]) -> str:
    """Digest exactly stable_core; never infer volatility from nested key names."""
    if not isinstance(stable_core, Mapping):
        raise ReceiptValidationError("stable_core must be an object")
    return stable_digest(stable_core)


def _fail(message: str) -> ReceiptValidationError:
    return ReceiptValidationError(message)


def _expect_exact_keys(
    value: Any,
    expected: set[str],
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{field} must be an object")
    actual = set(value)
    missing, unknown = sorted(expected - actual), sorted(actual - expected)
    if missing:
        raise _fail(f"{field} missing required field(s): {', '.join(missing)}")
    if unknown:
        raise _fail(f"{field} carries unknown field(s): {', '.join(unknown)}")
    return value


def _expect_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{field} must be an object")
    return value


def _expect_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise _fail(f"{field} must be a list")
    return value


def _expect_text(value: Any, field: str, *, exact: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(f"{field} must be a non-empty string")
    if exact is not None and value != exact:
        raise _fail(f"{field} must equal {exact!r}")
    return value


def _expect_utc_timestamp(value: Any, field: str) -> str:
    text = _expect_text(value, field)
    if not _UTC_TIMESTAMP_RE.fullmatch(text):
        raise _fail(f"{field} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise _fail(f"{field} must be a valid ISO-8601 UTC timestamp") from exc
    return text


def _validate_v1(payload: dict[str, Any]) -> LoadedReceipt:
    row = _expect_exact_keys(payload, _V1_KEYS, "v1 receipt")
    _expect_text(row["schema"], "schema", exact=RECEIPT_SCHEMA_V1)
    _expect_text(row["authority"], "authority", exact="projection_only")
    _expect_utc_timestamp(row["observed_at"], "observed_at")
    for field in ("repo", "work_lanes", "portfolio", "broken_register"):
        _expect_object(row[field], field)
    for field in (
        "next_items", "swarm_bulletins", "open_prs", "runtime_truth_packets",
    ):
        _expect_list(row[field], field)
    return LoadedReceipt(RECEIPT_SCHEMA_V1, 1, payload, admission_eligible=False)


def _validate_repository(value: Any) -> None:
    row = _expect_exact_keys(value, {"identity", "head", "branch"}, "stable_core.repository")
    for field in ("identity", "head", "branch"):
        if not isinstance(row[field], str):
            raise _fail(f"stable_core.repository.{field} must be a string")


def _validate_contract(value: Any) -> None:
    row = _expect_exact_keys(
        value, {"required_files", "source_hashes", "contract_digest"},
        "stable_core.contract",
    )
    _expect_list(row["required_files"], "stable_core.contract.required_files")
    _expect_object(row["source_hashes"], "stable_core.contract.source_hashes")
    if not isinstance(row["contract_digest"], str):
        raise _fail("stable_core.contract.contract_digest must be a string")


def _validate_packet(value: Any) -> None:
    row = _expect_exact_keys(
        value,
        {"id", "digest", "track", "owner", "allowed_files", "forbidden_files"},
        "stable_core.packet",
    )
    for field in ("id", "digest", "track", "owner"):
        if not isinstance(row[field], str):
            raise _fail(f"stable_core.packet.{field} must be a string")
    _expect_list(row["allowed_files"], "stable_core.packet.allowed_files")
    _expect_list(row["forbidden_files"], "stable_core.packet.forbidden_files")


def _validate_stable_core(value: Any) -> dict[str, Any]:
    row = _expect_exact_keys(value, _STABLE_CORE_KEYS, "stable_core")
    _validate_repository(row["repository"])
    _validate_contract(row["contract"])
    _validate_packet(row["packet"])
    portfolio = _expect_exact_keys(
        row["portfolio"], {"tracks", "selected_track", "ownership_conflicts"},
        "stable_core.portfolio",
    )
    _expect_list(portfolio["tracks"], "stable_core.portfolio.tracks")
    if not isinstance(portfolio["selected_track"], str):
        raise _fail("stable_core.portfolio.selected_track must be a string")
    _expect_list(
        portfolio["ownership_conflicts"],
        "stable_core.portfolio.ownership_conflicts",
    )
    orientation = _expect_exact_keys(
        row["orientation"], {"identity", "broken_register", "static_surfaces"},
        "stable_core.orientation",
    )
    for field in ("identity", "broken_register", "static_surfaces"):
        _expect_object(orientation[field], f"stable_core.orientation.{field}")
    _expect_list(row["required_reading"], "stable_core.required_reading")
    return row


def _validate_live_delta(value: Any) -> None:
    row = _expect_exact_keys(
        value,
        {"repo_state", "conditions", "host_gaps", "toolchain", "projection_freshness"},
        "live_delta",
    )
    repo_state = _expect_exact_keys(
        row["repo_state"], {"base", "dirty", "conflicted", "ahead", "behind"},
        "live_delta.repo_state",
    )
    if not isinstance(repo_state["base"], str):
        raise _fail("live_delta.repo_state.base must be a string")
    for field in ("dirty", "conflicted"):
        if not isinstance(repo_state[field], bool):
            raise _fail(f"live_delta.repo_state.{field} must be a boolean")
    for field in ("ahead", "behind"):
        if isinstance(repo_state[field], bool) or not isinstance(repo_state[field], int):
            raise _fail(f"live_delta.repo_state.{field} must be an integer")
    for field in ("conditions", "host_gaps"):
        _expect_list(row[field], f"live_delta.{field}")
    for field in ("toolchain", "projection_freshness"):
        _expect_object(row[field], f"live_delta.{field}")


def _validate_cache(value: Any) -> None:
    row = _expect_exact_keys(
        value, {"key", "hit", "miss_reasons", "input_manifest", "section_fingerprints"},
        "cache",
    )
    if not isinstance(row["key"], str) or not isinstance(row["hit"], bool):
        raise _fail("cache.key/hit have invalid types")
    _expect_list(row["miss_reasons"], "cache.miss_reasons")
    _expect_object(row["input_manifest"], "cache.input_manifest")
    _expect_object(row["section_fingerprints"], "cache.section_fingerprints")


def _validate_delta(value: Any) -> None:
    row = _expect_exact_keys(
        value, {"previous_stable_digest", "added", "resolved", "changed"}, "delta"
    )
    if not isinstance(row["previous_stable_digest"], str):
        raise _fail("delta.previous_stable_digest must be a string")
    for field in ("added", "resolved", "changed"):
        _expect_list(row[field], f"delta.{field}")


def _validate_legacy_v1(value: Any) -> None:
    expected = _V1_KEYS - {"schema"} | {"schema"}
    row = _expect_exact_keys(value, expected, "legacy_v1")
    for field in ("schema", "observed_at", "authority"):
        if not isinstance(row[field], str):
            raise _fail(f"legacy_v1.{field} must be a string")
    for field in ("repo", "work_lanes", "portfolio", "broken_register"):
        _expect_object(row[field], f"legacy_v1.{field}")
    for field in (
        "next_items", "swarm_bulletins", "open_prs", "runtime_truth_packets",
    ):
        _expect_list(row[field], f"legacy_v1.{field}")


def _validate_extensions(value: Any) -> None:
    extensions = _expect_object(value, "extensions")
    for name, extension in extensions.items():
        if not isinstance(name, str) or not name:
            raise _fail("extension names must be non-empty strings")
        row = _expect_object(extension, f"extensions.{name}")
        schema = row.get("schema")
        if not isinstance(schema, str) or not _EXTENSION_SCHEMA_RE.fullmatch(schema):
            raise _fail(f"extensions.{name}.schema must declare a versioned schema")


def _validate_v2(payload: dict[str, Any]) -> LoadedReceipt:
    row = _expect_exact_keys(payload, _V2_KEYS, "v2 receipt")
    _expect_text(row["schema"], "schema", exact=RECEIPT_SCHEMA_V2)
    _expect_text(row["authority"], "authority", exact="projection_only")
    _expect_utc_timestamp(row["observed_at"], "observed_at")
    verdict = row["primary_verdict"]
    if verdict not in _VERDICTS:
        raise _fail("primary_verdict is not recognized")
    exit_code = row["exit_code"]
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise _fail("exit_code must be an integer")
    if exit_code not in _EXIT_BY_VERDICT[str(verdict)]:
        raise _fail("exit_code contradicts primary_verdict")
    stable_core = _validate_stable_core(row["stable_core"])
    _validate_live_delta(row["live_delta"])
    _validate_cache(row["cache"])
    _validate_delta(row["delta"])
    _validate_legacy_v1(row["legacy_v1"])
    _validate_extensions(row["extensions"])
    stored = row["stable_digest"]
    if not isinstance(stored, str) or not _HEX_64.fullmatch(stored):
        raise _fail("stable_digest must be a lowercase 64-character digest")
    if stored != compute_stable_digest(stable_core):
        raise _fail("stable_digest mismatch")
    # Loader integrity is not admission: hard/live checks must still be rerun.
    return LoadedReceipt(RECEIPT_SCHEMA_V2, 2, payload, admission_eligible=False)


def load_receipt(path: Path) -> LoadedReceipt:
    """Load one receipt, negotiating schema before interpreting any other field."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _fail(f"receipt is unreadable or corrupt: {exc}") from exc
    if not isinstance(payload, dict):
        raise _fail("receipt root must be an object")
    schema = payload.get("schema")
    if not isinstance(schema, str) or not schema:
        raise _fail("receipt schema is missing or malformed")
    match = _SCHEMA_RE.fullmatch(schema)
    if not match:
        raise _fail(f"receipt schema is malformed: {schema}")
    major = int(match.group(1))
    if major == 1:
        return _validate_v1(payload)
    if major == 2:
        return _validate_v2(payload)
    raise UnsupportedReceiptSchema(f"unsupported onboarding receipt major: v{major}")


__all__ = [
    "_VOLATILE_KEYS",
    "compute_stable_digest",
    "load_receipt",
]
