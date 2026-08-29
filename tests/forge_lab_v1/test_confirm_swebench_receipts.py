from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import confirm_swebench, provider_selftest
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_lab.version import PACKAGE_VERSION, source_commit


class _Budget:
    def __init__(self, cap_tokens: int, cap_usd: float | None = None):
        self.cap_tokens = cap_tokens
        self.cap_usd = cap_usd
        self.spent = 0
        self.invalid = False
        self.invalid_reason = None

    def charge(self, _component: str, tokens: int, **_kwargs):
        self.spent += int(tokens)
        return self.spent

    def to_dict(self):
        return {"spent_tokens": self.spent, "invalid": self.invalid}


def test_patch_metadata_persists_non_empty_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(confirm_swebench, "CONFIRM_ROOT", tmp_path)
    patch = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"

    meta = confirm_swebench._patch_metadata("run1", "django__django-12209", patch)

    assert meta["non_empty_patch"] is True
    assert meta["patch_len"] == len(patch)
    assert meta["patch_sha256"] == hashlib.sha256(patch.encode("utf-8")).hexdigest()
    assert meta["patch_path"]
    assert tmp_path.joinpath("run1", "django__django-12209.candidate.patch").read_text() == patch


def test_candidate_receipt_includes_patch_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(confirm_swebench, "CONFIRM_ROOT", tmp_path)
    patch = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n"

    seams = confirm_swebench.GradeSeams(
        slot_for_id=lambda model_id: SimpleNamespace(model_id=model_id),
        propose_slot=lambda *_args, **_kwargs: {"patch": patch, "tokens": 123},
        self_moa_arm=lambda *_args, **_kwargs: {"final_patch": patch},
        verify_chain_arm=lambda *_args, **_kwargs: {"final_patch": patch},
        mixed_moa_arm=lambda *_args, **_kwargs: {"final_patch": patch},
        grade_task=lambda _inst, _patch, timeout: (False, 1.25, None),
        budget_factory=_Budget,
    )
    monkeypatch.setattr(confirm_swebench, "production_seams", lambda: seams)

    payload = confirm_swebench._candidate(
        {"instance_id": "django__django-12209"},
        {"f.py": "a\n"},
        "swebench/example:latest",
        "run2",
        "kimi-code",
        1000,
        {
            "schema": "forge_lab.confirm_provider_admission.v1",
            "independent_routes": ["kimi_code", "zhipu"],
        },
    )

    assert payload["non_empty_patch"] is True
    assert payload["patch_len"] == len(patch)
    assert payload["patch_sha256"] == hashlib.sha256(patch.encode("utf-8")).hexdigest()
    assert payload["patch_path"]
    assert payload["per_task"][0]["patch_len"] == len(patch)
    assert payload["per_task"][0]["patch_sha256"] == payload["patch_sha256"]
    assert payload["provider_admission"]["independent_routes"] == ["kimi_code", "zhipu"]


def _provider_receipt(path, *, routes, callable_count=2, live=True, ok=True, age_s=0):
    policy = {
        "source": {
            "package_version": PACKAGE_VERSION,
            "commit": source_commit(),
            "tree_state": "clean",
        },
        "configuration": {
            "profile": "staged",
            "current_model": None,
            "requested_models": ["route-a", "route-b"],
        },
        "probe_policy": {
            "require_independent_routes": 2,
            "timeout_s": 20,
            "max_provider_calls": 4,
            "alias_policy": provider_selftest.ALIAS_POLICY_VERSION,
        },
    }
    payload = {
        "schema": provider_selftest.PROVIDER_SELFTEST_SCHEMA,
        "profile": "staged",
        "live": live,
        "ok": ok,
        "checked_at": (
            datetime.now(timezone.utc) - timedelta(seconds=age_s)
        ).isoformat(),
        "callable_count": callable_count,
        "independent_route_count": len(routes),
        "independent_routes": routes,
        "rows": [],
        "policy": policy,
        "policy_digest": content_digest(policy),
        "receipt_id": "test-receipt",
        "receipt": str(path),
        "cached": False,
    }
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def test_confirm_requires_two_distinct_live_provider_entitlements(tmp_path):
    path = _provider_receipt(
        tmp_path / "provider.json",
        routes=["kimi_code", "zhipu"],
    )

    admission = confirm_swebench.confirm_provider_admission(path)

    assert admission["policy"] == "two_distinct_live_provider_entitlements"
    assert admission["independent_route_count"] == 2
    assert admission["availability_only_not_judge_authority"] is True
    assert admission["receipt_digest"].startswith("sha256:")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"routes": ["ollama"], "callable_count": 2},
        {"routes": ["ollama", "ollama"], "callable_count": 2},
        {"routes": ["ollama", "zhipu"], "callable_count": 0},
        {"routes": ["ollama", "zhipu"], "live": False},
        {"routes": ["ollama", "zhipu"], "ok": False},
        {"routes": ["ollama", "zhipu"], "age_s": 7200},
    ],
)
def test_confirm_route_policy_fails_closed(tmp_path, kwargs):
    path = _provider_receipt(tmp_path / "provider.json", **kwargs)
    with pytest.raises(ValueError, match="admission refused"):
        confirm_swebench.confirm_provider_admission(path, max_age_seconds=3600)


def test_confirm_rejects_tampered_or_different_source_policy(tmp_path):
    path = _provider_receipt(
        tmp_path / "provider.json",
        routes=["kimi_code", "zhipu"],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["policy"]["source"]["commit"] = "0" * 40
    payload["policy_digest"] = content_digest(payload["policy"])
    payload["receipt_digest"] = provider_selftest._receipt_digest(payload)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt_source_commit_mismatch"):
        confirm_swebench.confirm_provider_admission(path)

    payload["callable_count"] = 99
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt_digest_mismatch"):
        confirm_swebench.confirm_provider_admission(path)
