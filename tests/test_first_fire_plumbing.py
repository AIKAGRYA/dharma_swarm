"""Hermetic tests for scripts/first_fire_plumbing.py.

Verifies the runner against the *real* DarwinEngine.apply_diff_and_test
wrapper shape and parse_unified_diff a/b strip. No network. Does not
light the fuse (no grant consumed against a live checkout).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.diff_applier import parse_unified_diff  # noqa: E402
from dharma_swarm.evolution import DarwinEngine, EvolutionStatus, Proposal  # noqa: E402
from scripts import first_fire_plumbing as ff  # noqa: E402


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _grant(path: Path, **overrides) -> Path:
    data = {
        "grant_id": "first-fire-test",
        "granted_by": "test-operator",
        "expires_at": (_utc() + timedelta(hours=12)).isoformat(),
        "max_cycles": 1,
        "allowed_paths": ["experiments/first_fire/probe.py"],
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_unified_diff ↔ difflib a/ b/ prefix
# ---------------------------------------------------------------------------


def test_unified_diff_strips_to_allowlist_path():
    old = "def spark() -> int:\n    return 1\n"
    new = "def spark() -> int:\n    return 2\n"
    body = ff.unified_diff(ff.TOY_REL, old, new)
    assert body.startswith("--- a/experiments/first_fire/probe.py\n")
    assert "+++ b/experiments/first_fire/probe.py\n" in body
    patches = parse_unified_diff(body)
    assert len(patches) == 1
    assert patches[0].target_path == "experiments/first_fire/probe.py"
    ff.assert_paths(body, ff.ALLOWED_PATHS)


def test_unified_diff_refuses_identical_bytes():
    src = "def spark() -> int:\n    return 1\n"
    with pytest.raises(SystemExit) as excinfo:
        ff.unified_diff(ff.TOY_REL, src, src)
    assert excinfo.value.code == 2


def test_assert_paths_refuses_off_allowlist():
    body = ff.unified_diff(
        Path("dharma_swarm/evolution.py"),
        "x = 1\n",
        "x = 2\n",
    )
    with pytest.raises(SystemExit) as excinfo:
        ff.assert_paths(body, ff.ALLOWED_PATHS)
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# apply_diff_and_test wrapper shape (not raw ApplyTestResult)
# ---------------------------------------------------------------------------


async def test_empty_diff_wrapper_is_skipped_fake_green(tmp_path):
    engine = DarwinEngine(
        archive_path=tmp_path / "archive.jsonl",
        traces_path=tmp_path / "traces",
        predictor_path=tmp_path / "predictor.jsonl",
        archive_enforce_one_wire=False,
    )
    proposal = Proposal(
        component=str(ff.TOY_REL),
        change_type="mutation",
        description="empty",
        diff="   \n",
        status=EvolutionStatus.TESTING,
    )
    _, results = await engine.apply_diff_and_test(proposal, workspace=tmp_path)
    assert results == {"pass_rate": 1.0, "skipped": True}
    assert "rolled_back" not in results
    assert "applied" not in results
    n = ff.normalize_apply_results(results)
    assert n["skipped"] is True
    assert n["pass_rate"] == 1.0
    assert n["rolled_back"] is False
    assert ff.red_cycle_ok(results, file_restored=True) is False
    assert ff.green_cycle_ok(results, file_applied=True) is False


def test_red_ok_requires_rolled_back_not_just_untouched_file():
    # Apply never happened: pass_rate 0, no rolled_back, file still original.
    fake_apply_fail = {"pass_rate": 0.0, "rolled_back": False}
    assert ff.red_cycle_ok(fake_apply_fail, file_restored=True) is False
    honest_red = {"pass_rate": 0.0, "rolled_back": True}
    assert ff.red_cycle_ok(honest_red, file_restored=True) is True
    assert ff.red_cycle_ok(honest_red, file_restored=False) is False


def test_green_ok_rejects_skip_and_rollback():
    skip = {"pass_rate": 1.0, "skipped": True}
    assert ff.green_cycle_ok(skip, file_applied=True) is False
    rolled = {"pass_rate": 1.0, "rolled_back": True}
    assert ff.green_cycle_ok(rolled, file_applied=True) is False
    honest = {"pass_rate": 1.0, "rolled_back": False}
    assert ff.green_cycle_ok(honest, file_applied=True) is True
    assert ff.green_cycle_ok(honest, file_applied=False) is False


# ---------------------------------------------------------------------------
# grant / host / live-pin refuse
# ---------------------------------------------------------------------------


def test_grant_missing_expired_consumed_wrong_paths(tmp_path):
    g = _grant(tmp_path / "g.json")
    loaded = ff.load_grant(g)
    assert loaded["grant_id"] == "first-fire-test"

    _grant(tmp_path / "expired.json", expires_at="2020-01-01T00:00:00+00:00")
    with pytest.raises(SystemExit):
        ff.load_grant(tmp_path / "expired.json")

    _grant(tmp_path / "consumed.json", consumed_at="2026-08-18T00:00:00Z")
    with pytest.raises(SystemExit):
        ff.load_grant(tmp_path / "consumed.json")

    _grant(
        tmp_path / "paths.json",
        allowed_paths=["dharma_swarm/evolution.py"],
    )
    with pytest.raises(SystemExit):
        ff.load_grant(tmp_path / "paths.json")


def test_refuse_megha_host(monkeypatch):
    monkeypatch.setattr(ff.socket, "gethostname", lambda: "meghadharma-cloud")
    with pytest.raises(SystemExit) as excinfo:
        ff.refuse_host()
    assert excinfo.value.code == 2


def test_refuse_live_pin_source():
    with pytest.raises(SystemExit) as excinfo:
        ff.assert_not_live_source(Path("/root/dharma_swarm"))
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# real apply_diff_and_test on a toy workspace (hermetic; not the fuse)
# ---------------------------------------------------------------------------


def _toy_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "scratch"
    dest = ws / "experiments" / "first_fire"
    dest.mkdir(parents=True)
    (dest / "__init__.py").write_text("# toy\n", encoding="utf-8")
    (ws / "experiments" / "__init__.py").write_text("# toy\n", encoding="utf-8")
    (dest / "probe.py").write_text(
        (REPO_ROOT / "experiments" / "first_fire" / "probe.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (dest / "test_probe.py").write_text(
        (REPO_ROOT / "experiments" / "first_fire" / "test_probe.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    return ws


async def test_apply_diff_and_test_planted_red_rolls_back(tmp_path):
    ws = _toy_workspace(tmp_path)
    probe = ws / ff.TOY_REL
    original = probe.read_text(encoding="utf-8")
    red_src = original.replace("return 1", 'return "red"', 1)
    red_diff = ff.unified_diff(ff.TOY_REL, original, red_src)

    engine = DarwinEngine(
        archive_path=ws / ".first_fire_archive.jsonl",
        traces_path=ws / ".first_fire_traces",
        predictor_path=ws / ".first_fire_predictor.jsonl",
        archive_enforce_one_wire=False,
    )
    proposal = Proposal(
        component=str(ff.TOY_REL),
        change_type="mutation",
        description="planted-red",
        diff=red_diff,
        status=EvolutionStatus.TESTING,
        experiment_id="first-fire-plumbing",
    )
    _, results = await engine.apply_diff_and_test(
        proposal,
        test_command="python3 -m pytest experiments/first_fire/test_probe.py -q --tb=short",
        timeout=90.0,
        workspace=ws,
    )
    n = ff.normalize_apply_results(results)
    assert n["skipped"] is False
    assert n["pass_rate"] < 1.0
    assert n["rolled_back"] is True
    assert probe.read_text(encoding="utf-8") == original
    assert ff.red_cycle_ok(results, file_restored=True) is True


async def test_apply_diff_and_test_real_green_keeps_return_2(tmp_path):
    ws = _toy_workspace(tmp_path)
    probe = ws / ff.TOY_REL
    original = probe.read_text(encoding="utf-8")
    green_src = original.replace("return 1", "return 2", 1)
    green_diff = ff.unified_diff(ff.TOY_REL, original, green_src)

    engine = DarwinEngine(
        archive_path=ws / ".first_fire_archive.jsonl",
        traces_path=ws / ".first_fire_traces",
        predictor_path=ws / ".first_fire_predictor.jsonl",
        archive_enforce_one_wire=False,
    )
    proposal = Proposal(
        component=str(ff.TOY_REL),
        change_type="mutation",
        description="real-green",
        diff=green_diff,
        status=EvolutionStatus.TESTING,
        experiment_id="first-fire-plumbing",
    )
    _, results = await engine.apply_diff_and_test(
        proposal,
        test_command="python3 -m pytest experiments/first_fire/test_probe.py -q --tb=short",
        timeout=90.0,
        workspace=ws,
    )
    n = ff.normalize_apply_results(results)
    assert n["skipped"] is False
    assert n["pass_rate"] >= 1.0
    assert n["rolled_back"] is False
    assert "return 2" in probe.read_text(encoding="utf-8")
    assert ff.green_cycle_ok(results, file_applied=True) is True
