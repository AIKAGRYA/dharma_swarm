"""Walking brief: pure-composition tests + workflow contract pins (PR-C)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))
import walking_brief  # noqa: E402


def _base_data(**overrides):
    data = {
        "generated_at": "2026-07-29T21:00:00Z",
        "repo": "owner/repo",
        "killswitch": {"engaged": False, "detail": ""},
        "walk_ready": [],
        "automerge_log": [],
        "nightly_main": {"conclusion": "success", "url": "https://x", "completed_at": "t"},
        "lane_runs": None,
        "disagreements": None,
        "canary": None,
        "ingested": None,
    }
    data.update(overrides)
    return data


def test_brief_carries_marker_and_all_sections():
    body = walking_brief.compose_brief(_base_data())
    assert walking_brief.BRIEF_MARKER in body
    for heading in (
        "KILLSWITCH", "Merge window", "Automerges", "Nightly main",
        "Lane runs", "Review disagreements", "Canary results",
        "Ingested from your comments",
    ):
        assert heading in body, f"missing section: {heading}"


def test_killswitch_engaged_renders_red_and_resume_path():
    body = walking_brief.compose_brief(
        _base_data(killswitch={"engaged": True, "detail": "x"})
    )
    assert "🔴 KILLSWITCH" in body
    assert "ENGAGED" in body
    assert "loop-resume" in body


def test_killswitch_unknown_is_never_rendered_green():
    body = walking_brief.compose_brief(
        _base_data(killswitch={"engaged": None, "detail": "state UNKNOWN"})
    )
    assert "🟢 KILLSWITCH" not in body
    assert "UNKNOWN" in body


def test_missing_producers_say_so_instead_of_empty_calm():
    body = walking_brief.compose_brief(_base_data())
    assert body.count("no producer landed yet") >= 4


def test_walk_ready_draft_carries_flip_instruction():
    body = walking_brief.compose_brief(
        _base_data(
            walk_ready=[
                {"number": 7, "title": "t", "url": "https://x/7", "isDraft": True}
            ]
        )
    )
    assert "flip ready" in body


def test_automerge_log_is_newest_first_with_overflow():
    merged = [
        {"number": i, "title": f"t{i}", "url": f"https://x/{i}",
         "mergedAt": f"2026-07-29T{i:02d}:00:00Z"}
        for i in range(1, 11)
    ]
    # newest first (as gather_automerge_log now orders) must survive the
    # MAX_ROWS truncation, and overflow must be explicit.
    body = walking_brief.compose_brief(_base_data(automerge_log=merged[::-1]))
    assert "#10" in body, "newest merge must be visible"
    assert "…and 2 more" in body, "overflow must be explicit, never silent"
    assert "newest first" in body


def test_red_nightly_renders_red():
    body = walking_brief.compose_brief(
        _base_data(nightly_main={"conclusion": "failure", "url": "u", "completed_at": "t"})
    )
    assert "🔴" in body


def test_workflow_contract():
    doc = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "walking-brief.yml").read_text()
    )
    triggers = doc.get("on", doc.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert triggers["schedule"] == [{"cron": "0 21 * * *"}]
    assert doc["permissions"] == {
        "contents": "read",
        "issues": "write",
        "pull-requests": "read",
        "actions": "read",
    }
    text = (REPO_ROOT / ".github" / "workflows" / "walking-brief.yml").read_text()
    assert "walking_brief.py" in text
    # Deliberate KILLSWITCH exception: the brief is read-only visibility and
    # must keep publishing during an emergency stop — documented in-file.
    assert "KILLSWITCH exception" in text
