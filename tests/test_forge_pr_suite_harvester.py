from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dharma_swarm.forge_v1.forge_v2 import fresh_task_oracle, pr_suite_harvester


def _fake_fetcher(url: str, _headers: dict[str, str]) -> list[dict]:
    parsed = urlparse(url)
    path = parsed.path
    query = parse_qs(parsed.query)
    page = int(query.get("page", ["1"])[0])
    if path == "/repos/example/project/pulls":
        if page > 1:
            return []
        return [
            {
                "number": 10,
                "created_at": "2026-06-30T00:00:00Z",
                "merged_at": "2026-07-01T00:00:00Z",
                "title": "Fix parser regression",
                "html_url": "https://github.com/example/project/pull/10",
                "base": {"sha": "base10"},
                "head": {"sha": "head10"},
                "merge_commit_sha": "merge10",
            },
            {
                "number": 9,
                "created_at": "2026-04-01T00:00:00Z",
                "merged_at": "2026-04-15T00:00:00Z",
                "title": "Too old",
            },
            {
                "number": 8,
                "created_at": "2026-07-01T00:00:00Z",
                "merged_at": None,
                "title": "Closed unmerged",
            },
        ]
    if path == "/repos/example/project/pulls/10/files":
        if page > 1:
            return []
        return [
            {"filename": "src/parser.py"},
            {"filename": "tests/test_parser.py"},
            {"filename": "frontend/parser.spec.ts"},
        ]
    raise AssertionError(f"unexpected URL {url}")


def test_harvester_writes_candidate_not_validated_task(tmp_path: Path) -> None:
    summary = pr_suite_harvester.harvest_repos(
        ["https://github.com/example/project"],
        since="2026-06-01T00:00:00Z",
        limit_per_repo=5,
        fetcher=_fake_fetcher,
    )

    assert summary["candidate_count"] == 1
    assert summary["errors"] == []
    row = summary["rows"][0]
    assert row["repo"] == "example/project"
    assert row["pr_number"] == 10
    assert row["test_files"] == ["tests/test_parser.py", "frontend/parser.spec.ts"]
    assert row["fail_to_pass"] == []
    assert row["validation_state"] == "needs_fail_to_pass_validation"
    assert row["requires_fail_to_pass_validation"] is True

    manifest = tmp_path / "manifest.jsonl"
    pr_suite_harvester.write_manifest(manifest, list(summary["rows"]))
    assert [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()] == summary["rows"]


def test_harvested_candidate_is_skipped_until_fail_to_pass_validated(tmp_path: Path) -> None:
    summary = pr_suite_harvester.harvest_repos(
        ["example/project"],
        since="2026-06-01",
        limit_per_repo=1,
        fetcher=_fake_fetcher,
    )

    imported = fresh_task_oracle.import_fresh_tasks(
        list(summary["rows"]),
        model_cutoff="2026-06-01",
        db_path=tmp_path / "taskbed.db",
    )

    assert imported["imported_count"] == 0
    assert imported["skipped_count"] == 1
    assert imported["derived_state_counts"] == {"possible_pretrain": 1}
    assert "missing_fail_to_pass_suite" in imported["skipped"][0]["blockers"]


def test_token_from_env_spec_uses_first_available_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh-token")
    monkeypatch.setenv("OTHER_TOKEN", "other-token")

    assert pr_suite_harvester.token_from_env_spec("GITHUB_TOKEN,GH_TOKEN,OTHER_TOKEN") == "gh-token"
