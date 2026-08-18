"""Walking brief: pure-composition tests + workflow contract pins (PR-C)."""

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

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
        "router_workflow": {"enabled": True, "state": "active"},
        "automerge_workflow": {"enabled": True, "state": "active"},
        "scanner_heartbeat": {
            "found": True,
            "conclusion": "success",
            "completed_at": "2026-07-29T20:59:30Z",
            "head_sha": "a" * 40,
        },
        "router_progress": {
            "found": True,
            "conclusion": "success",
            "completed_at": "2026-07-29T19:00:00Z",
            "head_sha": "b" * 40,
        },
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
        "KILLSWITCH", "Needs John", "Merge arm", "scanner heartbeat",
        "Merge window", "Automerges", "Nightly main",
        "Lane runs", "Review disagreements", "Canary results",
        "Ingested from your comments", "Sublimation Foundry",
    ):
        assert heading in body, f"missing section: {heading}"


def test_foundry_section_not_run_when_absent():
    body = walking_brief.compose_brief(_base_data())  # no "foundry" key
    assert "🏭 Sublimation Foundry" in body
    assert "foundry lane not yet run" in body
    # the one-time unblock pointer is always shown
    assert "OPERATOR_UNBLOCKS.md" in body


def test_foundry_section_green_on_success():
    body = walking_brief.compose_brief(_base_data(foundry={
        "found": True, "conclusion": "success",
        "completed_at": "2026-08-18T19:00:00Z", "url": "https://x",
    }))
    assert "🟢 lane [success]" in body


def test_foundry_section_red_on_kill_verdict():
    # A KILL kill-metric verdict fails the lane; the brief must show red, not green.
    body = walking_brief.compose_brief(_base_data(foundry={
        "found": True, "conclusion": "failure",
        "completed_at": "2026-08-18T19:00:00Z", "url": "https://x",
    }))
    assert "🔴 lane [failure]" in body
    assert "🟢 lane" not in body.split("Sublimation Foundry")[1]


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
    # _base_data generates at 2026-07-29T21:00:00Z — the 06:00 JST schedule,
    # which belongs to the 07-30 walk day.
    body = walking_brief.compose_brief(_base_data())
    assert "<!-- walking-brief:date:2026-07-30 -->" in body


def test_todays_comment_is_updated_not_duplicated(monkeypatch):
    marker = "<!-- walking-brief:date:2026-07-29 -->"
    bot = {"login": "github-actions[bot]"}
    comments = [
        {"id": 11, "body": "unrelated", "user": bot},
        {"id": 22, "body": f"{marker}\nold brief", "user": bot},
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


# --- PR-C3 truthful merge-control inbox ----------------------------------


def test_workflow_state_is_tri_state_and_fail_closed(monkeypatch):
    calls = []

    def fake(args):
        calls.append(args)
        if args[-1].endswith("automerge.yml"):
            return {"state": "disabled_manually"}
        if args[-1].endswith("codex-mention-router.yml"):
            return {"state": "active"}
        return None

    monkeypatch.setattr(walking_brief, "_gh_json", fake)
    assert walking_brief.gather_workflow_state(
        "owner/repo", walking_brief.AUTOMERGE_WORKFLOW
    )["enabled"] is False
    assert walking_brief.gather_workflow_state(
        "owner/repo", walking_brief.ROUTER_WORKFLOW
    )["enabled"] is True
    assert walking_brief.gather_workflow_state(
        "owner/repo", "missing.yml"
    )["enabled"] is None
    assert all(call[0] == "api" for call in calls)


def test_disabled_is_red_and_unknown_never_looks_enabled():
    body = walking_brief.compose_brief(
        _base_data(
            router_workflow={"enabled": False, "state": "disabled_manually"},
            automerge_workflow={"enabled": None, "state": "unknown"},
        )
    )
    merge_section = body.split("### 🔐 Merge arm + router activity", 1)[1].split(
        "### 🔎", 1
    )[0]
    assert "🔴 Router: **DISABLED**" in merge_section
    assert "🟠 Automerge: **UNKNOWN**" in merge_section
    assert "🟢 Automerge" not in merge_section


def test_scanner_heartbeat_and_router_progress_are_separate_queries(monkeypatch):
    calls = []

    def fake(args):
        endpoint = args[-1]
        calls.append(endpoint)
        return {
            "workflow_runs": [
                {
                    "conclusion": "success",
                    "updated_at": "2026-07-29T20:59:30Z",
                    "head_sha": "c" * 40,
                }
            ]
        }

    monkeypatch.setattr(walking_brief, "_gh_json", fake)
    assert walking_brief.gather_scanner_heartbeat("owner/repo")["found"] is True
    assert walking_brief.gather_router_progress("owner/repo")["found"] is True
    assert walking_brief.BACKLOG_WORKFLOW in calls[0]
    assert "event=workflow_dispatch" not in calls[0]
    assert walking_brief.ROUTER_WORKFLOW in calls[1]
    assert "event=workflow_dispatch" in calls[1]
    assert "status=success" not in calls[1]


def test_fresh_packet_scanner_never_claims_merge_health_and_age_is_deterministic():
    body = walking_brief.compose_brief(
        _base_data(
            generated_at="2026-07-29T21:00:00Z",
            router_progress={
                "found": True,
                "completed_at": "2026-07-29T19:00:00Z",
                "head_sha": "d" * 40,
            },
            scanner_heartbeat={
                "found": True,
                "conclusion": "success",
                "completed_at": "2026-07-29T20:59:30Z",
                "head_sha": "e" * 40,
            },
        )
    )
    merge_section = body.split("### 🔐 Merge arm + router activity", 1)[1].split(
        "### 🔎", 1
    )[0]
    scanner_section = body.split("### 🔎 Mike scanner heartbeat", 1)[1].split(
        "### 👍", 1
    )[0]
    assert "2h ago" in merge_section
    assert "30s ago" in scanner_section
    assert "Packet scanner only" in scanner_section
    assert "not merge authority or merge progress" in scanner_section
    assert "🟢" not in scanner_section


def test_needs_john_is_max_five_control_first_same_repo_links_with_overflow():
    ready = [
        {
            "number": number,
            "title": f"PR {number} https://attacker.example/bad",
            "url": "https://attacker.example/not-used",
            "isDraft": False,
        }
        for number in range(1, 7)
    ]
    data = _base_data(
        router_workflow={"enabled": False, "state": "disabled_manually"},
        automerge_workflow={"enabled": None, "state": "unknown"},
        walk_ready=ready,
    )
    items, overflow = walking_brief.derive_needs_john(data)
    assert len(items) == walking_brief.MAX_NEEDS_JOHN == 5
    assert overflow == 3
    assert "Merge router" in items[0]
    assert "Automerge" in items[1]
    for item in items:
        urls = re.findall(r"https://[^)\s]+", item)
        assert len(urls) == 1, item
        assert urls[0].startswith("https://github.com/owner/repo/"), item
    assert "attacker.example" not in "\n".join(items)
    body = walking_brief.compose_brief(data)
    assert "…and 3 additional Needs John item(s) omitted" in body


# --- PR-C2 second review round (Greptile + Codex on #1166) ----------------


def test_marker_buckets_by_walk_day_not_raw_utc_date():
    """The 21:00 UTC schedule is 06:00 JST, so a walk day straddles UTC
    midnight. The scheduled run and a rerun 3.5h later must share a marker,
    or the next morning's run edits yesterday's comment."""
    scheduled = walking_brief._date_marker("2026-07-30T21:00:00Z")
    rerun_after_midnight = walking_brief._date_marker("2026-07-31T00:30:00Z")
    assert scheduled == rerun_after_midnight
    # The next scheduled run is a different bucket.
    assert walking_brief._date_marker("2026-07-31T21:00:00Z") != scheduled
    # Unparseable input degrades to the raw date prefix instead of raising.
    assert "2026-07-30" in walking_brief._date_marker("2026-07-30 weird")


def test_todays_comment_lookup_paginates(monkeypatch):
    marker = "<!-- walking-brief:date:2026-07-31 -->"
    bot = {"login": "github-actions[bot]"}
    page1 = [{"id": i, "body": "chatter", "user": bot} for i in range(100)]
    page2 = [{"id": 999, "body": f"{marker}\nbrief", "user": bot}]

    def fake(args):
        return page2 if args[-1].endswith("page=2") else page1

    monkeypatch.setattr(walking_brief, "_gh_json", fake)
    assert walking_brief.find_todays_brief_comment("o/r", 5, marker) == 999


def test_only_the_workflows_own_comment_is_updated(monkeypatch):
    """The marker is predictable and this issue accepts operator replies —
    a human comment carrying it must never be overwritten."""
    marker = "<!-- walking-brief:date:2026-07-31 -->"
    comments = [
        {"id": 41, "body": f"{marker} spoofed", "user": {"login": "someone"}},
        {"id": 42, "body": f"{marker} real", "user": {"login": "github-actions[bot]"}},
        {"id": 43, "body": f"{marker} later spoof", "user": {"login": "other-bot[bot]"}},
    ]
    monkeypatch.setattr(walking_brief, "_gh_json", lambda args: comments)
    assert walking_brief.find_todays_brief_comment("o/r", 5, marker) == 42


def test_bootstrap_body_keeps_the_manual_pin_instruction(monkeypatch):
    """The GraphQL pin is best-effort; if it fails the operator needs a
    visible remediation in the thread itself."""
    created = {}

    def fake_gh(args, **kwargs):
        if args[:2] == ["issue", "create"]:
            created["body"] = args[args.index("--body") + 1]
            return subprocess.CompletedProcess(args, 0, "https://x/issues/7", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(walking_brief, "_gh_json", lambda args: [])
    monkeypatch.setattr(walking_brief, "_gh", fake_gh)
    monkeypatch.setattr(walking_brief, "_pin_issue", lambda repo, number: False)
    assert walking_brief.find_or_create_brief_issue("o/r") == 7
    assert "Pin this issue" in created["body"]
