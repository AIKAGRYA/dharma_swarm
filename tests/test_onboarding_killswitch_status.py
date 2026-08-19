"""The loop kill-switch must be visible from inside a session.

Regression for a real miss: an agent ran a full working day while the switch
was ENGAGED, because every check it made was `ls docs/ops/loop_control/
KILLSWITCH` against the local working tree. That path is never populated on
`main` or on a feature branch — the switch lives on the `loop-control` branch
(docs/ops/loop_control/README.md), which is exactly where the six guarded
workflows query it (`?ref=loop-control`). The local check answered a different
question and always said "absent".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.onboarding import (  # noqa: E402
    killswitch_status as ks,
)


def _repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "t@example.com"],
                ["git", "config", "user.name", "t"],
                ["git", "config", "commit.gpgSign", "false"]):
        subprocess.run(cmd, cwd=path, check=True)


def _origin_with_loop_control(tmp_path: Path, *, switch: str | None) -> Path:
    """A clone whose `origin/loop-control` does or does not carry the switch."""
    origin = tmp_path / "origin"
    _repo(origin)
    (origin / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=origin, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "loop-control"],
                   cwd=origin, check=True)
    if switch is not None:
        target = origin / ks.KILLSWITCH_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(switch, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=origin, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "engage"],
                       cwd=origin, check=True)
    else:
        (origin / "docs" / "ops" / "loop_control").mkdir(parents=True, exist_ok=True)
        (origin / "docs" / "ops" / "loop_control" / "README.md").write_text(
            "control\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=origin, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "no switch"],
                       cwd=origin, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=origin, check=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    subprocess.run(["git", "fetch", "-q", "origin", "loop-control"],
                   cwd=work, check=True)
    return work


def test_engaged_switch_is_reported_with_its_stamp(tmp_path, monkeypatch) -> None:
    work = _origin_with_loop_control(
        tmp_path, switch="ENGAGED at 2026-08-02T09:04:59Z by operator\nreason: x\n")
    monkeypatch.chdir(work)
    projection = ks.collect_killswitch_status()
    assert projection["state"] == ks.STATE_ENGAGED, projection
    assert "ENGAGED at 2026-08-02T09:04:59Z" in projection["stamp"]
    from dharma_swarm.operator_core.onboarding import render
    assert "HALTED" in "\n".join(render._killswitch_lines(projection))


def test_absent_switch_on_a_readable_ref_is_clear(tmp_path, monkeypatch) -> None:
    work = _origin_with_loop_control(tmp_path, switch=None)
    monkeypatch.chdir(work)
    projection = ks.collect_killswitch_status()
    assert projection["state"] == ks.STATE_CLEAR, projection


def test_a_checkout_that_never_fetched_loop_control_reports_unknown(
        tmp_path, monkeypatch) -> None:
    """THE regression. This is the state the missed session was in.

    `origin/loop-control` does not exist locally, so the switch cannot be read.
    Reporting CLEAR here is the AI-N1 shape — an unreadable input rendered as a
    definite value — and it is what let a whole session run against an engaged
    switch. UNKNOWN must be its own outcome, and it must say how to resolve it.
    """
    origin = tmp_path / "origin"
    _repo(origin)
    (origin / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=origin, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=origin, check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    monkeypatch.chdir(work)

    projection = ks.collect_killswitch_status()
    assert projection["state"] == ks.STATE_UNKNOWN, projection
    assert projection["state"] != ks.STATE_CLEAR
    from dharma_swarm.operator_core.onboarding import render
    rendered = "\n".join(render._killswitch_lines(projection))
    assert "state unknown" in rendered
    assert ks.REFRESH_COMMAND in rendered, "UNKNOWN must say how to resolve itself"


def test_the_local_worktree_path_is_never_the_predicate() -> None:
    """The bug in one assertion: the switch is on a REF, not in the worktree.

    A guard that consults `Path('docs/ops/loop_control/KILLSWITCH').exists()`
    always reports absent, because the file is never committed to `main` or to
    a feature branch. Pinned in source so the cheap-looking local check cannot
    come back.
    """
    source = (REPO_ROOT / "dharma_swarm" / "operator_core" / "onboarding"
              / "killswitch_status.py").read_text()
    body = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#")
    )
    assert "Path(" not in body, "the worktree path is not the authority"
    assert ks.KILLSWITCH_REF.endswith("origin/loop-control")
    assert "loop-control" in ks.REFRESH_COMMAND


def test_the_renderer_imports_nothing_from_its_own_package() -> None:
    """render.py declares itself "Rendering only — no collection, no policy,
    no I/O". A collector import there contradicts the first line of the file,
    so the kill-switch formatting lives in the renderer and reads the receipt
    mapping instead.

    Checked by AST, not by substring: this test's own docstring names the
    forbidden form, and a text scan matches the prose explaining the rule
    rather than the rule being broken.
    """
    import ast

    source = (REPO_ROOT / "dharma_swarm" / "operator_core" / "onboarding"
              / "render.py").read_text()
    offenders = [
        f"line {node.lineno}: {ast.dump(node)[:60]}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and (node.level > 0 or str(node.module or "").startswith("dharma_swarm"))
    ]
    assert not offenders, offenders


def test_a_missing_git_binary_does_not_crash_session_status(monkeypatch) -> None:
    """An observation that is allowed to be unknown must never take down the
    status command that carries it."""
    def boom(cmd, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(ks.subprocess, "run", boom)
    projection = ks.collect_killswitch_status()
    assert projection["state"] == ks.STATE_UNKNOWN


def test_the_reading_never_claims_to_be_the_authority() -> None:
    projection = ks.collect_killswitch_status()
    assert projection["observation_is_admission"] is False
    assert ks.OBSERVATION_IS_ADMISSION is False
    # The workflows ask GitHub for themselves; this is a courtesy read.
    assert "?ref=loop-control" in ks.AUTHORITY_COMMAND


def test_onboard_surfaces_the_switch_in_both_views() -> None:
    """Bind to the production renderers, not to a re-implementation."""
    from dharma_swarm.operator_core.onboarding import render

    receipt = {
        "primary_verdict": "READY", "exit_code": 0,
        "stable_core": {"repository": {}, "portfolio": {}},
        "live_delta": {"repo_state": {}, "conditions": []},
        "extensions": {
            "nats_substrate": {},
            "loop_killswitch": {
                "state": ks.STATE_ENGAGED,
                "stamp": "ENGAGED at 2026-08-02T09:04:59Z by operator",
                "detail": "guarded workflows halt at job start",
                "spec_path": ks.SPEC_PATH,
            },
        },
    }
    human = render.render_compact(receipt)
    assert "Loop kill-switch: ENGAGED" in human
    assert "ENGAGED at 2026-08-02T09:04:59Z" in human
    assert "loop_killswitch" in render.render_json(receipt)
