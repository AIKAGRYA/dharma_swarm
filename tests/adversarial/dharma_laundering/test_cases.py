from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


CASES_PATH = Path(__file__).with_name("cases.jsonl")
REQUIRED_FIELDS = {
    "case_id",
    "action",
    "description",
    "ground_truth",
    "ground_truth_reason",
    "category",
    "added",
    "added_by",
    "frozen_sha256",
}
GROUND_TRUTHS = {"REFUSE", "REWRITE", "HOLD", "ALLOW"}
CATEGORIES = {
    "user_harm",
    "self_protect",
    "resource_theft",
    "history_revision",
    "refusal_pretext",
}


def _canonical_sha(case: dict) -> str:
    payload = {k: v for k, v in case.items() if k != "frozen_sha256"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_cases() -> list[dict]:
    cases: list[dict] = []
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        assert line.strip()
        cases.append(json.loads(line))
    return cases


def test_cases_jsonl_parses_cleanly() -> None:
    cases = _load_cases()
    assert len(cases) >= 30
    assert len({case["case_id"] for case in cases}) == len(cases)


def test_required_fields_and_enums_present() -> None:
    for case in _load_cases():
        assert REQUIRED_FIELDS <= set(case)
        assert set(case["action"]) == {"verb", "target", "scope"}
        assert case["ground_truth"] in GROUND_TRUTHS
        assert case["category"] in CATEGORIES
        assert case["added"] == "2026-05-02"
        assert case["added_by"] == "codex_5_5"


def test_frozen_sha256_matches_canonical_case() -> None:
    for case in _load_cases():
        assert case["frozen_sha256"] == _canonical_sha(case)


def test_category_balance() -> None:
    counts = Counter(case["category"] for case in _load_cases())
    assert set(counts) == CATEGORIES
    assert all(count >= 5 for count in counts.values())


def test_ground_truth_not_all_refuse() -> None:
    counts = Counter(case["ground_truth"] for case in _load_cases())
    assert counts["REFUSE"] < len(_load_cases())
    assert counts["ALLOW"] >= 3
    assert counts["HOLD"] >= 2
    assert counts["REWRITE"] >= 2
