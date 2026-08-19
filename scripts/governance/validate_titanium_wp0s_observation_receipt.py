#!/usr/bin/env python3
"""Fail-closed validator for the bounded Titanium WP-0S observation receipt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "dharma.titanium.wp0s_observation_receipt.v1"
WORK_PACKET = "WP-0S"
ACTIVE_TRACK = "repository-titanium-hardening-2026-07"
BASE_REF = "61df22a85e2083a96a7b0a9500b611e384d40730"
AUTHORITY = "implementation_observer"
SECRET_POLICY = "environment_names_and_presence_booleans_only"
SECRET_NAMES = (
    "DASHBOARD_API_KEY",
    "DHARMA_VERIFY_WEBHOOK_SECRET",
    "DHARMA_API_MODE",
)
EVIDENCE_MODALITIES = ("live_host", "listener", "public_http", "code_version")
PROMOTIONAL_STATES = {"PASS", "CLOSED", "CLOSED_NOT_PROD", "CLOSED_LIVE"}
TOP_LEVEL_KEYS = {
    "schema",
    "work_packet",
    "active_track",
    "generated_at",
    "requested_snapshot_at",
    "observation_window",
    "base_ref",
    "authority",
    "claim_boundary",
    "inventory_complete",
    "exact_host_scope",
    "status",
    "operator_attestation",
    "verdict",
    "secret_policy",
    "secret_name_observations",
    "evidence",
    "reconciliation",
    "actions_not_taken",
}

_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(?:api[_-]?key|password|passwd|secret|token)[\"']?\s*[:=]\s*"
        r"[\"']?(?!true\b|false\b|null\b|none\b|present\b|absent\b)"
        r"[^\s,;}\"]{4,}"
    ),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{4,}"),
    re.compile(r"\b(?:sk|ghp)_[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"),
)


def _is_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: object, path: str, errors: list[str]) -> datetime | None:
    if not _is_string(value):
        errors.append(f"{path} must be a non-empty RFC3339 timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path} must be a valid RFC3339 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{path} must include a timezone")
        return None
    return parsed


def _mapping(value: object, path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    return value


def _list(value: object, path: str, errors: list[str]) -> list[Any] | None:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return None
    return value


def _validate_secret_boundary(receipt: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(receipt, sort_keys=True)
    for pattern in _SECRET_PATTERNS:
        if pattern.search(serialized):
            errors.append("receipt contains a forbidden secret-like value")
            break

    policy = _mapping(receipt.get("secret_policy"), "secret_policy", errors)
    if policy is None:
        return
    if policy.get("mode") != SECRET_POLICY:
        errors.append(f"secret_policy.mode must equal {SECRET_POLICY!r}")
    if policy.get("secret_values_accessed") is not False:
        errors.append("secret_policy.secret_values_accessed must be false")
    allowed_names = policy.get("allowed_environment_names")
    if not isinstance(allowed_names, list) or set(allowed_names) != set(SECRET_NAMES):
        errors.append("secret_policy.allowed_environment_names must be the exact allowlist")
    elif len(allowed_names) != len(set(allowed_names)):
        errors.append("secret_policy.allowed_environment_names must be unique")

    observations = _list(
        receipt.get("secret_name_observations"), "secret_name_observations", errors
    )
    if observations is None:
        return
    if not observations:
        errors.append("secret_name_observations must not be empty")
        return

    exact_scope = receipt.get("exact_host_scope")
    scope = set(exact_scope) if isinstance(exact_scope, list) else set()
    seen_pairs: set[tuple[str, str]] = set()
    for index, raw_observation in enumerate(observations):
        path = f"secret_name_observations[{index}]"
        observation = _mapping(raw_observation, path, errors)
        if observation is None:
            continue
        host_id = observation.get("host_id")
        runtime_id = observation.get("runtime_id")
        if not _is_string(host_id) or host_id not in scope:
            errors.append(f"{path}.host_id must be in exact_host_scope")
        if not _is_string(runtime_id):
            errors.append(f"{path}.runtime_id must be non-empty")
        if _is_string(host_id) and _is_string(runtime_id):
            pair = (str(host_id), str(runtime_id))
            if pair in seen_pairs:
                errors.append(f"{path} duplicates host/runtime observation {pair!r}")
            seen_pairs.add(pair)
        _timestamp(observation.get("observed_at"), f"{path}.observed_at", errors)
        if not _is_string(observation.get("source_vantage")):
            errors.append(f"{path}.source_vantage must be non-empty")
        names_present = _mapping(observation.get("names_present"), f"{path}.names_present", errors)
        if names_present is None:
            continue
        if set(names_present) != set(SECRET_NAMES):
            errors.append(f"{path}.names_present must contain the exact secret-name allowlist")
        for name, present in names_present.items():
            if name in SECRET_NAMES and not isinstance(present, bool):
                errors.append(f"{path}.names_present.{name} must be a boolean")


def _validate_evidence(receipt: dict[str, Any], errors: list[str]) -> None:
    evidence = _mapping(receipt.get("evidence"), "evidence", errors)
    if evidence is None:
        return
    if set(evidence) != set(EVIDENCE_MODALITIES):
        errors.append("evidence must contain exactly live_host, listener, public_http, and code_version")

    exact_scope = receipt.get("exact_host_scope")
    scope = set(exact_scope) if isinstance(exact_scope, list) else set()
    evidence_ids: set[str] = set()
    runtime_evidence_pairs: set[tuple[str, str]] = set()
    live_hosts: set[str] = set()

    for modality in EVIDENCE_MODALITIES:
        items = _list(evidence.get(modality), f"evidence.{modality}", errors)
        if items is None:
            continue
        if not items:
            errors.append(f"evidence.{modality} must not be empty")
            continue
        for index, raw_item in enumerate(items):
            path = f"evidence.{modality}[{index}]"
            item = _mapping(raw_item, path, errors)
            if item is None:
                continue
            evidence_id = item.get("id")
            host_id = item.get("host_id")
            if not _is_string(evidence_id):
                errors.append(f"{path}.id must be non-empty")
            elif evidence_id in evidence_ids:
                errors.append(f"{path}.id must be unique")
            else:
                evidence_ids.add(str(evidence_id))
            if not _is_string(host_id) or host_id not in scope:
                errors.append(f"{path}.host_id must be in exact_host_scope")
            _timestamp(item.get("observed_at"), f"{path}.observed_at", errors)
            if not _is_string(item.get("source_vantage")):
                errors.append(f"{path}.source_vantage must be non-empty")

            if modality == "live_host":
                if _is_string(host_id):
                    live_hosts.add(str(host_id))
                if not _is_string(item.get("hostname")):
                    errors.append(f"{path}.hostname must be non-empty")
                if not isinstance(item.get("reachable"), bool):
                    errors.append(f"{path}.reachable must be a boolean")
                continue

            runtime_id = item.get("runtime_id")
            if not _is_string(runtime_id):
                errors.append(f"{path}.runtime_id must be non-empty")
            elif _is_string(host_id):
                runtime_evidence_pairs.add((str(host_id), str(runtime_id)))

            if modality == "listener":
                addresses = item.get("bind_addresses")
                if (
                    not isinstance(addresses, list)
                    or not addresses
                    or not all(_is_string(address) for address in addresses)
                ):
                    errors.append(f"{path}.bind_addresses must be a non-empty string array")
                port = item.get("port")
                if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                    errors.append(f"{path}.port must be an integer from 1 through 65535")
                if item.get("transport") != "tcp":
                    errors.append(f"{path}.transport must equal 'tcp'")
                if not isinstance(item.get("public_bind"), bool):
                    errors.append(f"{path}.public_bind must be a boolean")
            elif modality == "public_http":
                if not _is_string(item.get("endpoint")):
                    errors.append(f"{path}.endpoint must be non-empty")
                status_code = item.get("status_code")
                if (
                    isinstance(status_code, bool)
                    or not isinstance(status_code, int)
                    or not 100 <= status_code <= 599
                ):
                    errors.append(f"{path}.status_code must be an HTTP status integer")
                if item.get("reachable") is not True:
                    errors.append(f"{path}.reachable must be true for observed public HTTP evidence")
                if item.get("public_network") is not True:
                    errors.append(f"{path}.public_network must be true")
            elif modality == "code_version":
                if not _is_string(item.get("version_kind")):
                    errors.append(f"{path}.version_kind must be non-empty")
                if not _is_string(item.get("observed_ref")):
                    errors.append(f"{path}.observed_ref must be non-empty")

    if live_hosts != scope:
        errors.append("evidence host scope must exactly match exact_host_scope")

    observations = receipt.get("secret_name_observations")
    secret_pairs = {
        (str(item.get("host_id")), str(item.get("runtime_id")))
        for item in observations
        if isinstance(item, dict)
        and _is_string(item.get("host_id"))
        and _is_string(item.get("runtime_id"))
    } if isinstance(observations, list) else set()
    missing_runtime_observations = runtime_evidence_pairs - secret_pairs
    if missing_runtime_observations:
        rendered = ", ".join(f"{host}/{runtime}" for host, runtime in sorted(missing_runtime_observations))
        errors.append(f"runtime evidence lacks names-only secret observation: {rendered}")


def _validate_operator_gate(receipt: dict[str, Any], errors: list[str]) -> None:
    inventory_complete = receipt.get("inventory_complete")
    if not isinstance(inventory_complete, bool):
        errors.append("inventory_complete must be a boolean")

    status = receipt.get("status")
    verdict = _mapping(receipt.get("verdict"), "verdict", errors)
    classification = verdict.get("classification") if verdict is not None else None
    if not _is_string(status):
        errors.append("status must be non-empty")
    if not _is_string(classification):
        errors.append("verdict.classification must be non-empty")
    if _is_string(status) and _is_string(classification) and status != classification:
        errors.append("status and verdict.classification must match")

    attestation = _mapping(receipt.get("operator_attestation"), "operator_attestation", errors)
    if attestation is None:
        return
    present = attestation.get("present")
    if not isinstance(present, bool):
        errors.append("operator_attestation.present must be a boolean")
        present = False
    attestor = attestation.get("attestor")
    attested_at = attestation.get("attested_at")
    attested_scope = attestation.get("exact_host_scope")
    scope = receipt.get("exact_host_scope")

    if present:
        if not _is_string(attestor):
            errors.append("operator_attestation.attestor must be non-empty when present")
        _timestamp(attested_at, "operator_attestation.attested_at", errors)
        if not isinstance(attested_scope, list) or attested_scope != scope:
            errors.append("operator attestation must cover the exact host scope in order")
    elif not (
        attestor is None
        and attested_at is None
        and isinstance(attested_scope, list)
        and not attested_scope
    ):
        errors.append("absent operator attestation must carry null identity/time and empty scope")

    promoted = status in PROMOTIONAL_STATES or classification in PROMOTIONAL_STATES
    if inventory_complete is True or promoted:
        if not present:
            errors.append("complete or promotional receipt requires operator attestation")
        if not isinstance(attested_scope, list) or attested_scope != scope:
            errors.append("complete or promotional receipt requires exact host scope attestation")

    if inventory_complete is False:
        if status != "BLOCKED_OPERATOR" or classification != "BLOCKED_OPERATOR":
            errors.append("incomplete inventory must remain BLOCKED_OPERATOR")
        if verdict is not None:
            expected = {
                "classification": "BLOCKED_OPERATOR",
                "live_exposure": "observed",
                "operator_action": "required",
                "phase0_promotion": "forbidden",
            }
            if verdict != expected:
                errors.append("incomplete inventory must retain the exact blocked live-exposure verdict")


def validate_receipt(receipt: object) -> list[str]:
    """Return fail-closed validation errors without mutating *receipt*."""
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]

    if receipt.get("schema") != SCHEMA:
        errors.append(f"schema must equal {SCHEMA!r}")
    if receipt.get("work_packet") != WORK_PACKET:
        errors.append(f"work_packet must equal {WORK_PACKET!r}")
    if set(receipt) != TOP_LEVEL_KEYS:
        missing = sorted(TOP_LEVEL_KEYS - set(receipt))
        unknown = sorted(set(receipt) - TOP_LEVEL_KEYS)
        errors.append(
            f"top-level keys must be exact (missing={missing!r}, unknown={unknown!r})"
        )
    if receipt.get("authority") != AUTHORITY:
        errors.append(f"authority must equal {AUTHORITY!r}")
    if receipt.get("active_track") != ACTIVE_TRACK:
        errors.append(f"active_track must equal {ACTIVE_TRACK!r}")
    if receipt.get("base_ref") != BASE_REF:
        errors.append(f"base_ref must equal the sealed packet base {BASE_REF!r}")
    if not _is_string(receipt.get("claim_boundary")):
        errors.append("claim_boundary must be non-empty")

    generated_at = _timestamp(receipt.get("generated_at"), "generated_at", errors)
    requested_at = _timestamp(
        receipt.get("requested_snapshot_at"), "requested_snapshot_at", errors
    )
    window = _mapping(receipt.get("observation_window"), "observation_window", errors)
    first_at = last_at = None
    if window is not None:
        first_at = _timestamp(window.get("first_observed_at"), "observation_window.first_observed_at", errors)
        last_at = _timestamp(window.get("last_observed_at"), "observation_window.last_observed_at", errors)
    if requested_at and first_at and requested_at > first_at:
        errors.append("requested_snapshot_at must not be later than the observation window")
    if first_at and last_at and first_at > last_at:
        errors.append("observation window must be ordered")
    if last_at and generated_at and last_at > generated_at:
        errors.append("generated_at must not precede the observation window")

    scope = _list(receipt.get("exact_host_scope"), "exact_host_scope", errors)
    if scope is not None:
        if not scope or not all(_is_string(host_id) for host_id in scope):
            errors.append("exact_host_scope must be a non-empty string array")
        if len(scope) != len(set(scope)):
            errors.append("exact_host_scope entries must be unique")

    _validate_secret_boundary(receipt, errors)
    _validate_evidence(receipt, errors)
    _validate_operator_gate(receipt, errors)
    return errors


def _load(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        receipt = _load(args.receipt)
        errors = validate_receipt(receipt)
    except (OSError, json.JSONDecodeError) as exc:
        errors = [f"unable to load receipt: {exc}"]
        receipt = None

    valid = not errors
    operator_blocked = bool(
        valid
        and isinstance(receipt, dict)
        and receipt.get("status") == "BLOCKED_OPERATOR"
    )
    result = {
        "error_count": len(errors),
        "receipt_is_operator_blocked": operator_blocked,
        "validation_status": "VALID" if valid else "INVALID",
    }
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    elif valid:
        print("VALID: receipt passed structural validation")
    else:
        print(
            "INVALID: receipt failed structural validation; details are not logged",
            file=sys.stderr,
        )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
