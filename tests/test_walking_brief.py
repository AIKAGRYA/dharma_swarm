"""Walking brief: pure-composition tests + workflow contract pins (PR-C)."""

import subprocess
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

# ---------------------------------------------------------------- PR-C2
# Review-hardening pins (Codex, Devin, Greptile on the merged PR #1158).


def _fake_gh(stdout="", stderr="", returncode=1):
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return runner


def test_failed_walk_ready_query_renders_unknown_not_calm():
    body = walking_brief.compose_brief(_base_data(walk_ready=None))
    assert "nothing awaiting you" not in body
    assert "UNKNOWN" in body


def test_failed_automerge_query_renders_unknown_not_none():
    body = walking_brief.compose_brief(_base_data(automerge_log=None))
    assert "UNKNOWN" in body
    # The genuinely-empty case still reads as calm.
    calm = walking_brief.compose_brief(_base_data(automerge_log=[]))
    assert "none" in calm


def test_killswitch_missing_branch_is_disengaged(monkeypatch):
    # A repo where loop-control has never been created returns
    # "No commit found for the ref loop-control" — the switch contract
    # (docs/ops/loop_control/README.md) reads that as absent/disengaged.
    monkeypatch.setattr(
        walking_brief, "_gh",
        _fake_gh(stderr="gh: No commit found for the ref loop-control (HTTP 404)"),
    )
    assert walking_brief.gather_killswitch("o/r")["engaged"] is False


def test_killswitch_other_error_stays_unknown(monkeypatch):
    monkeypatch.setattr(walking_brief, "_gh", _fake_gh(stderr="HTTP 500 boom"))
    assert walking_brief.gather_killswitch("o/r")["engaged"] is None


def test_issue_lookup_failure_never_creates_duplicate(monkeypatch):
    created = []
    monkeypatch.setattr(walking_brief, "_gh_json", lambda args: None)
    monkeypatch.setattr(
        walking_brief, "_gh",
        lambda args, **kw: created.append(args)
        or subprocess.CompletedProcess(args, 0, "", ""),
    )
    assert walking_brief.find_or_create_brief_issue("o/r") is None
    assert created == [], "a failed lookup must not reach the create path"


def test_titles_are_markdown_escaped():
    body = walking_brief.compose_brief(
        _base_data(
            walk_ready=[
                {"number": 7, "title": "x](https://attacker.example)",
                 "url": "https://x/7", "isDraft": False}
            ]
        )
    )
    assert "x](https://attacker.example)" not in body
    assert "\\]" in body


def test_brief_carries_date_marker_for_idempotent_posting():
    body = walking_brief.compose_brief(_base_data())
    assert "<!-- walking-brief:date:2026-07-29 -->" in body


def test_todays_comment_is_updated_not_duplicated(monkeypatch):
    marker = "<!-- walking-brief:date:2026-07-29 -->"
    comments = [
        {"id": 11, "body": "unrelated"},
        {"id": 22, "body": f"{marker}\nold brief"},
    ]
    monkeypatch.setattr(walking_brief, "_gh_json", lambda args: comments)
    assert walking_brief.find_todays_brief_comment("o/r", 5, marker) == 22


def test_pending_nightly_renders_pending_not_red():
    body = walking_brief.compose_brief(
        _base_data(nightly_main={"conclusion": "in_progress", "url": "u",
                                 "completed_at": "t"})
    )
    assert "🟡" in body
    assert "🔴" not in body
