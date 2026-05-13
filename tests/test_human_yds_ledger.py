from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "governance" / "record_human_yds_rating.py"

spec = importlib.util.spec_from_file_location("record_human_yds_rating", SCRIPT_PATH)
assert spec is not None
yds = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = yds
spec.loader.exec_module(yds)


def make_rating(
    *,
    artifact: str = "reports/agentops/job/20260505T000000Z/report.json",
    rating: str = "5.12",
    note: str = "Clean scoped packet.",
    created_at: str = "2026-05-05T00:00:00Z",
    supersedes_rating_id: str | None = None,
    private_note: str = "",
) -> dict[str, object]:
    return yds.build_rating_record(
        artifact=artifact,
        kind="agentops_report",
        rating=rating,
        note=note,
        operator_id="dhyana",
        title="AgentOps packet",
        evidence_refs=["reports/kaizen/latest/kaizen_review.md"],
        tags=["agentops", "kaizen"],
        supersedes_rating_id=supersedes_rating_id,
        private_note=private_note,
        created_at=created_at,
        repo_root=REPO_ROOT,
    )


def test_records_one_valid_rating_to_temp_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "ratings.jsonl"
    record = make_rating()

    yds.append_rating(ledger, record)

    ratings = yds.read_ratings(ledger)
    assert len(ratings) == 1
    assert ratings[0]["rating_value"] == "5.12"
    assert ratings[0]["artifact"]["uri"] == "repo://reports/agentops/job/20260505T000000Z/report.json"


def test_preserves_append_only_behavior(tmp_path: Path) -> None:
    ledger = tmp_path / "ratings.jsonl"
    first = make_rating(created_at="2026-05-05T00:00:00Z")
    second = make_rating(rating="5.13", note="Improved judgment.", created_at="2026-05-05T00:01:00Z")

    yds.append_rating(ledger, first)
    yds.append_rating(ledger, second)

    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [r["rating_value"] for r in yds.read_ratings(ledger)] == ["5.12", "5.13"]


@pytest.mark.parametrize("rating", ["5.5", "5.16", "5.09", "6.0", "AI-5.12", ""])
def test_rejects_invalid_rating_values(rating: str) -> None:
    with pytest.raises(yds.HumanYdsLedgerError):
        make_rating(rating=rating)


def test_rejects_missing_artifact() -> None:
    with pytest.raises(yds.HumanYdsLedgerError):
        make_rating(artifact="")


def test_rejects_missing_human_note() -> None:
    with pytest.raises(yds.HumanYdsLedgerError):
        make_rating(note="")


def test_normalizes_repo_relative_paths_to_repo_uri() -> None:
    assert (
        yds.normalize_artifact_uri("docs/governance/KAIZENOPS.md", repo_root=REPO_ROOT)
        == "repo://docs/governance/KAIZENOPS.md"
    )


def test_supports_supersession_without_modifying_old_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ratings.jsonl"
    first = make_rating(created_at="2026-05-05T00:00:00Z")
    second = make_rating(
        rating="5.13",
        note="Correction after deeper review.",
        created_at="2026-05-05T00:01:00Z",
        supersedes_rating_id=str(first["rating_id"]),
    )

    yds.append_rating(ledger, first)
    yds.append_rating(ledger, second)

    ratings = yds.read_ratings(ledger)
    assert ratings[0]["rating_id"] == first["rating_id"]
    assert ratings[1]["supersedes_rating_id"] == first["rating_id"]


def test_resolves_latest_non_superseded_rating_for_artifact(tmp_path: Path) -> None:
    ledger = tmp_path / "ratings.jsonl"
    first = make_rating(created_at="2026-05-05T00:00:00Z")
    second = make_rating(
        rating="5.13",
        note="Correction after deeper review.",
        created_at="2026-05-05T00:01:00Z",
        supersedes_rating_id=str(first["rating_id"]),
    )
    yds.append_rating(ledger, first)
    yds.append_rating(ledger, second)

    latest = yds.latest_rating_for_artifact(
        yds.read_ratings(ledger),
        "reports/agentops/job/20260505T000000Z/report.json",
        repo_root=REPO_ROOT,
    )

    assert latest is not None
    assert latest["rating_value"] == "5.13"


def test_omits_private_note_from_public_output() -> None:
    record = make_rating(private_note="private operator context")

    exported = yds.public_rating(record)

    assert "private_note" not in exported
    assert record["private_note"] == "private operator context"


def test_does_not_import_or_call_subprocess() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "os.system" not in source
    assert "git commit" not in source
    assert "git push" not in source
    assert "git merge" not in source


def test_cli_records_public_rating(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ledger = tmp_path / "ratings.jsonl"

    exit_code = yds.main(
        [
            "--ledger",
            str(ledger),
            "rate",
            "--artifact",
            "reports/agentops/job/20260505T000000Z/report.json",
            "--kind",
            "agentops_report",
            "--rating",
            "5.12",
            "--note",
            "Clean scoped packet.",
            "--private-note",
            "do not export",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["rating_value"] == "5.12"
    assert "private_note" not in output
    assert len(yds.read_ratings(ledger)) == 1
