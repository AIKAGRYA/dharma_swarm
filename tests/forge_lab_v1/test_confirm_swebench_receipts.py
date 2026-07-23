from __future__ import annotations

import hashlib
from types import SimpleNamespace

from dharma_swarm.forge_lab import confirm_swebench


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
    )

    assert payload["non_empty_patch"] is True
    assert payload["patch_len"] == len(patch)
    assert payload["patch_sha256"] == hashlib.sha256(patch.encode("utf-8")).hexdigest()
    assert payload["patch_path"]
    assert payload["per_task"][0]["patch_len"] == len(patch)
    assert payload["per_task"][0]["patch_sha256"] == payload["patch_sha256"]
