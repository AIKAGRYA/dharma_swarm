from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import model_onboarding
from dharma_swarm.forge_lab.state_io import content_digest


GREEN_BINDINGS = [
    {"role": "mutator", "provider": "zhipu", "model_id": "glm-5.2"},
    {"role": "solver", "provider": "zhipu", "model_id": "glm-5.2"},
    {
        "role": "verifier",
        "provider": "ollama",
        "model_id": "deepseek-v4-pro:cloud",
    },
]
ALTERNATE_BINDINGS = [
    {
        "role": "mutator",
        "provider": "ollama",
        "model_id": "deepseek-v4-pro:cloud",
    },
    {
        "role": "solver",
        "provider": "ollama",
        "model_id": "deepseek-v4-pro:cloud",
    },
    {"role": "verifier", "provider": "zhipu", "model_id": "glm-5.2"},
]


@pytest.fixture
def isolated_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / "rsi-state"
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.setenv("DHARMA_HOME", str(state / ".dharma"))
    return state


def _activation_root(state: Path) -> Path:
    return state / ".dharma" / "forge_lab" / "model_onboarding"


def _plan(
    bindings: list[dict[str, str]],
    *,
    current: str | None = None,
) -> dict[str, object]:
    return model_onboarding.plan_activation(
        bindings,
        expected_current_digest=current,
    )


def _apply(
    bindings: list[dict[str, str]],
    request_id: str,
    *,
    current: str | None = None,
) -> dict[str, object]:
    return model_onboarding.apply_activation(
        _plan(bindings, current=current),
        request_id=request_id,
        expected_current_digest=current,
    )


def test_catalog_and_plan_are_exact_deterministic_and_pure(
    isolated_state: Path,
) -> None:
    first_catalog = model_onboarding.list_supported_routes()
    second_catalog = model_onboarding.list_supported_routes()
    assert first_catalog == second_catalog
    assert first_catalog["catalog_digest"] == content_digest(
        {
            key: value
            for key, value in first_catalog.items()
            if key != "catalog_digest"
        }
    )
    exact_routes = {
        (row["provider"], row["model_id"]): row
        for row in first_catalog["routes"]
    }
    assert exact_routes[("zhipu", "glm-5.2")]["below_floor"] is False
    assert exact_routes[("zhipu", "glm-5.2")]["runtime_selectable"] is True
    assert exact_routes[("openai", "gpt-5.5")]["runtime_selectable"] is False
    assert (
        exact_routes[("ollama", "deepseek-v4-pro:cloud")]["logical_model_id"]
        == "deepseek-v4-pro"
    )

    plan = _plan(GREEN_BINDINGS)
    assert plan == _plan(reversed(GREEN_BINDINGS))
    assert plan["outcome"] == "ready"
    assert plan["bindings"] == [
        {
            **binding,
            "logical_model_id": "glm-5.2",
            "tier": "strong",
            "below_floor": False,
            "runtime_selectable": True,
            "runtime_blocker": None,
        }
        if binding["provider"] == "zhipu"
        else {
            **binding,
            "logical_model_id": "deepseek-v4-pro",
            "tier": "strong",
            "below_floor": False,
            "runtime_selectable": True,
            "runtime_blocker": None,
        }
        for binding in GREEN_BINDINGS
    ]
    assert plan["staged_models"] == ["glm-5.2", "deepseek-v4-pro:cloud"]
    assert plan["claim_boundary"] == model_onboarding.CLAIM_BOUNDARY
    assert not _activation_root(isolated_state).exists()


def test_unknown_transport_and_unknown_exact_route_return_bounded_outcomes(
    isolated_state: Path,
) -> None:
    unknown_transport = deepcopy(GREEN_BINDINGS)
    unknown_transport[0] = {
        "role": "mutator",
        "provider": "future_transport",
        "model_id": "future-model",
    }
    result = _plan(unknown_transport)
    assert result["outcome"] == "implementation_required"
    assert result["blockers"] == [
        "implementation_required:mutator:future_transport"
    ]

    unknown_route = deepcopy(GREEN_BINDINGS)
    unknown_route[0]["model_id"] = "not-in-model-pool"
    result = _plan(unknown_route)
    assert result["outcome"] == "source_change_required"
    assert result["blockers"] == [
        "source_change_required:mutator:zhipu:not-in-model-pool"
    ]
    assert not _activation_root(isolated_state).exists()


def test_provider_ambiguous_model_id_requires_qualified_runtime_implementation(
    isolated_state: Path,
) -> None:
    ambiguous = deepcopy(GREEN_BINDINGS)
    ambiguous[0] = {
        "role": "mutator",
        "provider": "openai",
        "model_id": "gpt-5.5",
    }

    result = _plan(ambiguous)

    assert result["outcome"] == "implementation_required"
    assert result["blockers"] == [
        "implementation_required:provider_qualified_execution:"
        "mutator:openai:gpt-5.5"
    ]
    assert result["bindings"][0]["runtime_selectable"] is False
    assert not _activation_root(isolated_state).exists()


@pytest.mark.parametrize(
    "bindings, outcome, blocker",
    [
        (
            GREEN_BINDINGS[:2],
            "invalid_request",
            "missing_role:verifier",
        ),
        (
            [*GREEN_BINDINGS, GREEN_BINDINGS[0]],
            "invalid_request",
            "duplicate_role:mutator",
        ),
    ],
)
def test_plan_requires_each_role_once(
    bindings: list[dict[str, str]],
    outcome: str,
    blocker: str,
) -> None:
    result = _plan(bindings)
    assert result["outcome"] == outcome
    assert blocker in result["blockers"]


def test_apply_writes_atomic_current_immutable_profile_and_secret_free_receipt(
    isolated_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "must-never-appear-in-model-activation-artifacts"
    monkeypatch.setenv("ZHIPU_API_KEY", secret)
    monkeypatch.setenv("OLLAMA_API_KEY", secret)

    result = _apply(GREEN_BINDINGS, "activate-green-pair")
    status = model_onboarding.activation_status()
    assert result["idempotent"] is False
    assert result["generation"] == 1
    assert status["active"] is True
    assert status["integrity"] == "verified"
    assert status["role_bindings"] == _plan(GREEN_BINDINGS)["bindings"]
    assert status["staged_models"] == ["glm-5.2", "deepseek-v4-pro:cloud"]
    assert status["receipt_count"] == 1
    assert status["claim_boundary"] == {
        "authority": "role_selection_only",
        "credentials_loaded": False,
        "provider_calls": False,
        "source_edits": False,
        "weights_changed": False,
        "availability_attested": False,
        "quality_attested": False,
        "promotion_authority": False,
    }

    root = _activation_root(isolated_state)
    current = json.loads((root / "current.json").read_text(encoding="utf-8"))
    digest_name = str(current["profile_digest"]).removeprefix("sha256:")
    profile_path = root / "profiles" / f"{digest_name}.json"
    receipt_path = root / "receipts" / "activate-green-pair.json"
    assert json.loads(profile_path.read_text(encoding="utf-8")) == current
    assert profile_path.stat().st_mode & 0o777 == 0o600
    assert receipt_path.stat().st_mode & 0o777 == 0o600
    artifact_text = "".join(
        path.read_text(encoding="utf-8")
        for path in root.rglob("*.json")
        if path.is_file()
    )
    assert secret not in artifact_text
    assert "API_KEY" not in artifact_text


def test_apply_is_idempotent_and_request_ids_cannot_change_intent(
    isolated_state: Path,
) -> None:
    plan = _plan(GREEN_BINDINGS)
    first = model_onboarding.apply_activation(
        plan,
        request_id="idempotent-apply",
        expected_current_digest=None,
    )
    second = model_onboarding.apply_activation(
        plan,
        request_id="idempotent-apply",
        expected_current_digest=None,
    )
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["profile_digest"] == first["profile_digest"]
    assert model_onboarding.activation_status()["receipt_count"] == 1

    other_plan = _plan(ALTERNATE_BINDINGS, current=first["profile_digest"])
    with pytest.raises(
        model_onboarding.ModelOnboardingError,
        match="another activation intent",
    ) as raised:
        model_onboarding.apply_activation(
            other_plan,
            request_id="idempotent-apply",
            expected_current_digest=first["profile_digest"],
        )
    assert raised.value.code == "REQUEST_ID_REUSED"


def test_apply_rejects_stale_cas_stale_plan_and_plan_tampering(
    isolated_state: Path,
) -> None:
    stale_plan = _plan(ALTERNATE_BINDINGS)
    first = _apply(GREEN_BINDINGS, "first-profile")

    with pytest.raises(model_onboarding.ModelOnboardingError) as raised:
        model_onboarding.apply_activation(
            stale_plan,
            request_id="stale-cas",
            expected_current_digest=None,
        )
    assert raised.value.code == "CONCURRENT_ACTIVATION"

    current_digest = first["profile_digest"]
    with pytest.raises(model_onboarding.ModelOnboardingError) as raised:
        model_onboarding.apply_activation(
            stale_plan,
            request_id="stale-plan",
            expected_current_digest=current_digest,
        )
    assert raised.value.code == "STALE_PLAN"

    tampered = _plan(ALTERNATE_BINDINGS, current=current_digest)
    tampered["bindings"][0]["model_id"] = "tampered"
    with pytest.raises(model_onboarding.ModelOnboardingError) as raised:
        model_onboarding.apply_activation(
            tampered,
            request_id="tampered-plan",
            expected_current_digest=current_digest,
        )
    assert raised.value.code == "PLAN_TAMPERED"


def test_rollback_is_cas_guarded_append_only_and_monotonic(
    isolated_state: Path,
) -> None:
    first = _apply(GREEN_BINDINGS, "profile-one")
    second = _apply(
        ALTERNATE_BINDINGS,
        "profile-two",
        current=first["profile_digest"],
    )

    with pytest.raises(model_onboarding.ModelOnboardingError) as raised:
        model_onboarding.rollback_activation(
            request_id="stale-rollback",
            expected_current_digest=first["profile_digest"],
        )
    assert raised.value.code == "CONCURRENT_ACTIVATION"

    rolled_back = model_onboarding.rollback_activation(
        request_id="rollback-to-one",
        expected_current_digest=second["profile_digest"],
    )
    status = model_onboarding.activation_status()
    assert rolled_back["generation"] == 3
    assert rolled_back["profile_digest"] not in {
        first["profile_digest"],
        second["profile_digest"],
    }
    assert status["role_bindings"] == first["role_bindings"]
    assert status["staged_models"] == ["glm-5.2", "deepseek-v4-pro:cloud"]
    assert status["rollback_target_digest"] == first["profile_digest"]
    assert status["previous_profile_digest"] == second["profile_digest"]
    assert status["receipt_count"] == 3
    assert len(list((_activation_root(isolated_state) / "profiles").glob("*.json"))) == 3

    retry = model_onboarding.rollback_activation(
        request_id="rollback-to-one",
        expected_current_digest=second["profile_digest"],
    )
    assert retry["idempotent"] is True
    assert retry["profile_digest"] == rolled_back["profile_digest"]
    assert model_onboarding.activation_status()["receipt_count"] == 3


def test_current_profile_tampering_fails_closed(isolated_state: Path) -> None:
    _apply(GREEN_BINDINGS, "tamper-current")
    current_path = _activation_root(isolated_state) / "current.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current["bindings"][0]["model_id"] = "tampered"
    current_path.write_text(json.dumps(current) + "\n", encoding="utf-8")

    with pytest.raises(model_onboarding.ModelOnboardingError) as raised:
        model_onboarding.activation_status()
    assert raised.value.code == "PROFILE_INVALID"


def test_inactive_status_is_explicit_and_has_no_authority(
    isolated_state: Path,
) -> None:
    assert model_onboarding.activation_status() == {
        "schema": model_onboarding.STATUS_SCHEMA,
        "active": False,
        "integrity": "absent",
        "current_profile_digest": None,
        "generation": 0,
        "role_bindings": [],
        "staged_models": [],
        "previous_profile_digest": None,
        "rollback_target_digest": None,
        "last_action": None,
        "receipt_count": 0,
        "claim_boundary": model_onboarding.CLAIM_BOUNDARY,
    }
    assert not _activation_root(isolated_state).exists()
