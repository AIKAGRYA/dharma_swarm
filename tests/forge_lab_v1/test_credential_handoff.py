from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import credential_handoff as handoff


def test_status_and_plan_expose_names_not_values(tmp_path: Path) -> None:
    store = tmp_path / ".dharma" / "agent_keys.env"
    store.parent.mkdir()
    secret = "super-secret-provider-value"
    store.write_text(f"export ZHIPU_API_KEY={secret}\n", encoding="utf-8")
    store.chmod(0o600)

    status = handoff.credential_status("zhipu", home=tmp_path, env={})
    plan = handoff.plan_credential("zhipu", home=tmp_path)
    encoded = json.dumps({"status": status, "plan": plan}, sort_keys=True)

    assert status["rows"][0]["credential_present_in_store"] is True
    assert plan["action"] == "upsert"
    assert secret not in encoded
    assert plan["credential_env"] == "ZHIPU_API_KEY"
    assert plan["secret_digests_recorded"] is False


def test_status_rejects_unsafe_mode_empty_and_unresolved_assignments(tmp_path: Path) -> None:
    store = tmp_path / ".dharma" / "agent_keys.env"
    store.parent.mkdir()
    store.write_text(
        "export ZHIPU_API_KEY=''\nexport OLLAMA_API_KEY=$MISSING_KEY\n",
        encoding="utf-8",
    )
    store.chmod(0o644)

    zhipu = handoff.credential_status("zhipu", home=tmp_path, env={})
    ollama = handoff.credential_status("ollama", home=tmp_path, env={})

    assert zhipu["ok"] is False
    assert zhipu["store_mode_safe"] is False
    assert zhipu["rows"][0]["credential_present_in_store"] is False
    assert ollama["rows"][0]["credential_present_in_store"] is False


def test_apply_uses_existing_store_and_receipt_never_contains_secret(
    tmp_path: Path,
) -> None:
    old = "old-provider-secret"
    new = "new-provider-secret"
    store = tmp_path / ".dharma" / "agent_keys.env"
    store.parent.mkdir()
    store.write_text(
        f"export ZHIPU_API_KEY={old}\nexport OLLAMA_API_KEY=keep-me-safe\n",
        encoding="utf-8",
    )
    store.chmod(0o600)
    plan = handoff.plan_credential("zhipu", home=tmp_path)

    result = handoff.apply_credential(
        "zhipu",
        plan_digest=plan["plan_digest"],
        request_id="test-credential-update",
        secret=new,
        home=tmp_path,
    )

    contents = store.read_text(encoding="utf-8")
    receipt = Path(result["receipt"]).read_text(encoding="utf-8")
    intent = Path(result["intent"]).read_text(encoding="utf-8")
    assert new in contents
    assert old not in contents
    assert "OLLAMA_API_KEY=keep-me-safe" in contents
    assert new not in receipt
    assert old not in receipt
    assert "keep-me-safe" not in receipt
    assert new not in intent
    assert store.stat().st_mode & 0o777 == 0o600
    assert result["secret_value_recorded"] is False
    assert result["secret_digest_recorded"] is False

    replay = handoff.apply_credential(
        "zhipu",
        plan_digest=plan["plan_digest"],
        request_id="test-credential-update",
        secret="a-different-secret-must-not-reapply",
        home=tmp_path,
    )
    assert replay["idempotent_replay"] is True
    assert new in store.read_text(encoding="utf-8")

    with pytest.raises(handoff.CredentialHandoffError) as wrong_replay:
        handoff.apply_credential(
            "zhipu",
            plan_digest="sha256:" + "0" * 64,
            request_id="test-credential-update",
            secret="another-provider-secret",
            home=tmp_path,
        )
    assert wrong_replay.value.code == "PLAN_CHANGED"


def test_apply_refuses_changed_plan_and_unsafe_store(tmp_path: Path) -> None:
    with pytest.raises(handoff.CredentialHandoffError) as changed:
        handoff.apply_credential(
            "ollama",
            plan_digest="sha256:" + "0" * 64,
            request_id="test-plan-changed",
            secret="provider-secret-value",
            home=tmp_path,
        )
    assert changed.value.code == "PLAN_CHANGED"

    store = tmp_path / ".dharma" / "agent_keys.env"
    store.parent.mkdir()
    store.write_text("", encoding="utf-8")
    store.chmod(0o644)
    unsafe_plan = handoff.plan_credential("ollama", home=tmp_path)
    with pytest.raises(handoff.CredentialHandoffError) as unsafe:
        handoff.apply_credential(
            "ollama",
            plan_digest=unsafe_plan["plan_digest"],
            request_id="test-unsafe-store",
            secret="provider-secret-value",
            home=tmp_path,
        )
    assert unsafe.value.code == "STORE_MODE_UNSAFE"


def test_unknown_provider_requires_implementation(tmp_path: Path) -> None:
    with pytest.raises(handoff.CredentialHandoffError) as error:
        handoff.plan_credential("dream-provider", home=tmp_path)

    assert error.value.code == "IMPLEMENTATION_REQUIRED"


@pytest.mark.parametrize(
    "secret",
    ["        ", " leading-secret", "trailing-secret ", "$MISSING_SECRET"],
)
def test_apply_rejects_secrets_the_runtime_loader_would_change_or_drop(
    tmp_path: Path,
    secret: str,
) -> None:
    plan = handoff.plan_credential("zhipu", home=tmp_path)

    with pytest.raises(handoff.CredentialHandoffError) as error:
        handoff.apply_credential(
            "zhipu",
            plan_digest=plan["plan_digest"],
            request_id="invalid-secret-input",
            secret=secret,
            home=tmp_path,
        )

    assert error.value.code == "INVALID_SECRET"


def test_durable_intent_makes_receipt_failure_outcome_explicitly_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = handoff.plan_credential("zhipu", home=tmp_path)
    original_write = handoff.write_json_exclusive
    fail_once = True

    def flaky_write(path, payload, **kwargs):
        nonlocal fail_once
        if path.parent.name == "applied" and fail_once:
            fail_once = False
            raise OSError("simulated receipt fsync failure")
        return original_write(path, payload, **kwargs)

    monkeypatch.setattr(handoff, "write_json_exclusive", flaky_write)
    with pytest.raises(handoff.CredentialHandoffError) as failed:
        handoff.apply_credential(
            "zhipu",
            plan_digest=plan["plan_digest"],
            request_id="recover-after-receipt-failure",
            secret="durable-provider-secret",
            home=tmp_path,
        )
    assert failed.value.code == "RECEIPT_WRITE_FAILED"
    intents = list(
        (tmp_path / ".dharma" / "provider_credential_receipts" / "intents").glob("*.json")
    )
    assert len(intents) == 1

    with pytest.raises(handoff.CredentialHandoffError) as uncertain:
        handoff.apply_credential(
            "zhipu",
            plan_digest=plan["plan_digest"],
            request_id="recover-after-receipt-failure",
            secret="a-different-provider-secret",
            home=tmp_path,
        )
    assert uncertain.value.code == "OUTCOME_UNKNOWN"
    assert "durable-provider-secret" in (
        tmp_path / ".dharma" / "agent_keys.env"
    ).read_text(encoding="utf-8")


def test_handoff_rejects_symlinked_canonical_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".dharma").symlink_to(outside, target_is_directory=True)

    with pytest.raises(handoff.CredentialHandoffError) as error:
        handoff.plan_credential("zhipu", home=tmp_path)

    assert error.value.code == "STORE_PATH_UNSAFE"
