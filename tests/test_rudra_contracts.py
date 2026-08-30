"""Layer A: RUDRA contract parsing and canonicalization attacks.

Normative source: docs/plans/rudra_v0/TEST_AND_BURNIN_PLAN.md section 2A.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    ReproducedCompletion,
    load_mission_yaml,
    parse_mission,
)
from tests.fixtures.rudra.helpers import (
    make_base_repo,
    make_mission_yaml,
)


@pytest.fixture()
def valid_text(tmp_path: Path) -> str:
    repo, base = make_base_repo(tmp_path)
    return make_mission_yaml(repo, base)


def _expect(text: str, code: AdmissionReject, match: str = "") -> None:
    with pytest.raises(AdmissionError) as excinfo:
        parse_mission(text)
    assert excinfo.value.code == code
    if match:
        assert re.search(match, str(excinfo.value), re.IGNORECASE)


def test_valid_mission_parses_and_digest_deterministic(valid_text: str) -> None:
    first = parse_mission(valid_text)
    second = parse_mission(valid_text.replace("\n", "\n"))
    assert first.digest() == second.digest()
    assert first.mission_id == "smoke-mission"


def test_semantic_change_changes_digest(valid_text: str) -> None:
    changed = valid_text.replace("return 42", "return 43", 1)
    assert parse_mission(changed).digest() != parse_mission(valid_text).digest()


def test_duplicate_keys_rejected(valid_text: str) -> None:
    attacked = valid_text.replace(
        "mission_id: smoke-mission", "mission_id: smoke-mission\nmission_id: other"
    )
    _expect(attacked, AdmissionReject.REJECT_INVALID, "duplicate key")


def test_alias_and_anchor_rejected() -> None:
    text = "a: &x 1\nb: *x\n"
    with pytest.raises(AdmissionError):
        load_mission_yaml(text)


def test_merge_key_rejected() -> None:
    text = "base:\n  a: 1\nderived:\n  <<: {a: 2}\n  b: 3\n"
    with pytest.raises(AdmissionError):
        load_mission_yaml(text)


def test_custom_tag_rejected() -> None:
    text = "a: !ruby/object:Whatever {}\n"
    with pytest.raises(AdmissionError):
        load_mission_yaml(text)


def test_unknown_field_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["surprise"] = True
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "surprise")


def test_implicit_coercion_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["budgets"]["max_turns"] = "5"  # string where int is required
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


def test_non_finite_number_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["budgets"]["max_turns"] = float("nan")
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


def test_empty_verifier_list_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["acceptance"]["commands"] = []
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "commands")


def test_shell_command_string_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["acceptance"]["commands"][0]["argv"] = "echo hi; rm -rf /"
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


@pytest.mark.parametrize(
    "bad_path",
    ["/etc/passwd", "../escape.py", "src/../escape.py", "src\\evil.py", ".git/config"],
)
def test_unsafe_scope_paths_rejected(valid_text: str, bad_path: str) -> None:
    data = yaml.safe_load(valid_text)
    data["scope"]["allowed_changed_paths"] = [bad_path]
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


def test_control_character_path_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["scope"]["allowed_changed_paths"] = ["src/evil\x07.py"]
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


@pytest.mark.parametrize(
    "bad_id",
    ["Aupper", "a_underscore", "a/slash", "a..dots", "a" * 70, "0starts-digit", "-lead"],
)
def test_mission_id_policy(valid_text: str, bad_id: str) -> None:
    data = yaml.safe_load(valid_text)
    data["mission_id"] = bad_id
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "mission_id")


def test_non_hex40_base_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["repository"]["base_sha"] = "not-a-sha"
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "base_sha")


def test_internally_inconsistent_budget_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["budgets"]["max_tokens_per_turn"] = 999999999
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "per_turn")


def test_zero_budget_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["budgets"]["max_wall_seconds"] = 0
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tool_network_access", True),
        ("allow_mcp", True),
        ("allow_external_effects", True),
        ("allow_dependency_install", True),
        ("approval_policy", "on-request"),
        ("sandbox", "danger-full-access"),
        ("risk_class", "hostile_lane"),
    ],
)
def test_containment_relaxation_blocked(
    valid_text: str, field: str, value: object
) -> None:
    data = yaml.safe_load(valid_text)
    data["containment"][field] = value
    _expect(yaml.safe_dump(data), AdmissionReject.BLOCKED_CONTAINMENT)


def test_push_merge_ambient_authority_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["result"]["allow_push"] = True
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID)


def test_hostile_objective_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["objective"] = "Write an exploit payload for the target"
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "hostile")


def test_relative_executable_rejected(valid_text: str) -> None:
    data = yaml.safe_load(valid_text)
    data["toolchain"]["executables"]["python"]["path"] = "python3"
    _expect(yaml.safe_dump(data), AdmissionReject.REJECT_INVALID, "absolute")


def test_reproduced_completion_has_no_public_constructor() -> None:
    """G17: a forged result object cannot cross the evaluator boundary."""
    with pytest.raises(TypeError):
        ReproducedCompletion(
            mission_id="x",
            attempt_id="y",
            base_sha="0" * 40,
            candidate_sha="1" * 40,
            contract_digest="2" * 64,
            workspace_digest="3" * 64,
            verifier_run_id="z",
            gate_passed_digest="4" * 64,
        )
