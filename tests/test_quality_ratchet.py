"""Tests for scripts/governance/hygiene/ratchet.py (one-way quality ratchet).

Invariants under test, one per test (or named group):

1.  A run where every counter equals its baseline is green (exit 0, all OK).
2.  A DOWN counter rising — or an UP counter falling — is a regression
    (exit 1) and names the offending counter on stderr.
3.  An improvement WITHOUT --tighten leaves the baselines file
    byte-identical: observing an improvement must not adopt it silently.
4.  An improvement WITH --tighten rewrites exactly the improved keys,
    preserves all others, and the run stays green.
5.  A red run never mutates the baselines file, even with --tighten and
    even when other counters improved: tightening on red would launder a
    regression in with the improvement.
6.  Baseline/counter-set drift is BROKEN (exit 2), in all four shapes:
    missing key, unknown key, wrong schema_version, non-integer value.
7.  --init creates the file from current reality exactly once; a second
    --init refuses (exit 2) — loosening a ratchet must be a reviewed
    manual edit, never an accidental re-init.
8.  A counter that cannot measure raises through to exit 2, not exit 0:
    a broken gate blocks rather than waves through.
9.  save_baselines round-trips through load_baselines and leaves no
    temp-file droppings beside the target.
10. The measurement functions report ground truth on a synthetic repo:
    swallow-site detection matches exactly the `except [Exception|bare]:
    pass` shape (not narrower handlers, not handlers that act), the
    bypass counter counts the _INTENTIONAL_BYPASS dict literal, the
    module-budget counters see line counts, and the lifecycle counter
    counts only enforced/resolved stages.

The ruff-backed counter is exercised against the real binary only when
one is available (final test); everything else is hermetic via fake
counters, so the engine's algebra is tested without any tool dependency.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HYGIENE_DIR = REPO_ROOT / "scripts" / "governance" / "hygiene"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HYGIENE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


counters_mod = _load("ratchet_counters")
ratchet = _load("ratchet")

Counter = counters_mod.Counter
Direction = counters_mod.Direction
Reading = counters_mod.Reading
BrokenCounter = counters_mod.BrokenCounter


def _fake_counters(**values_by_name):
    """Build a COUNTERS tuple whose measurements are fixed values."""
    direction = {"debt": Direction.DOWN, "asset": Direction.UP}
    return tuple(
        Counter(
            name=name,
            direction=direction[name.split("_")[0]],
            end_target=0,
            definition=f"fake counter {name}",
            measure=(lambda root, v=value: Reading(value=v, evidence=(f"{name}-evidence",))),
        )
        for name, value in values_by_name.items()
    )


def _write_baselines(repo: Path, counters: dict[str, int]) -> Path:
    path = repo / ratchet.BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": ratchet.BASELINE_SCHEMA_VERSION,
        "tightened_on": "2026-06-12",
        "counters": counters,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    """A repo where one debt counter reads 5 and one asset counter reads 3."""
    monkeypatch.setattr(
        ratchet, "COUNTERS", _fake_counters(debt_things=5, asset_things=3)
    )
    return tmp_path


def _run(repo: Path, *flags: str) -> int:
    return ratchet.main(["--repo-root", str(repo), "--today", "2026-06-13", *flags])


# -- invariant 1: reality == baseline is green --------------------------------


def test_green_when_every_counter_equals_baseline(fake_repo, capsys):
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})
    assert _run(fake_repo) == ratchet.EXIT_GREEN
    out = capsys.readouterr().out
    assert out.count("OK") == 2 and "REGRESSION" not in out


# -- invariant 2: wrong-direction movement fails and is named -----------------


def test_down_counter_rising_is_a_regression(fake_repo, capsys):
    _write_baselines(fake_repo, {"debt_things": 4, "asset_things": 3})
    assert _run(fake_repo) == ratchet.EXIT_REGRESSION
    assert "debt_things" in capsys.readouterr().err


def test_up_counter_falling_is_a_regression(fake_repo, capsys):
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 4})
    assert _run(fake_repo) == ratchet.EXIT_REGRESSION
    assert "asset_things" in capsys.readouterr().err


# -- invariant: baseline freshness gate ---------------------------------------


def test_fresh_baseline_passes_the_freshness_gate(fake_repo):
    # tightened_on 2026-06-12, today 2026-06-13 => 1 day old, within 30.
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})
    assert _run(fake_repo, "--max-baseline-age-days", "30") == ratchet.EXIT_GREEN


def test_stale_baseline_is_broken_even_when_counters_match(fake_repo, capsys):
    # 1 day old vs a 0-day window => stale => fail closed, independent of
    # any regression (every counter here equals its baseline).
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})
    assert _run(fake_repo, "--max-baseline-age-days", "0") == ratchet.EXIT_BROKEN
    assert "freshness" in capsys.readouterr().err


def test_future_baseline_date_is_broken(fake_repo, capsys):
    path = _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tightened_on"] = "2099-01-01"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    assert _run(fake_repo, "--max-baseline-age-days", "30") == ratchet.EXIT_BROKEN
    assert "future baseline dates" in capsys.readouterr().err


def test_stale_but_green_baseline_can_refresh_with_explicit_tighten(fake_repo):
    path = _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})

    assert (
        _run(
            fake_repo,
            "--tighten",
            "--refresh-baseline-date",
            "--max-baseline-age-days",
            "0",
        )
        == ratchet.EXIT_GREEN
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["tightened_on"] == "2026-06-13"
    assert payload["counters"] == {"asset_things": 3, "debt_things": 5}


def test_refresh_baseline_date_requires_tighten(fake_repo, capsys):
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})

    assert (
        _run(
            fake_repo,
            "--refresh-baseline-date",
            "--max-baseline-age-days",
            "0",
        )
        == ratchet.EXIT_BROKEN
    )
    assert "freshness" in capsys.readouterr().err


def test_baseline_without_tightened_on_is_broken(fake_repo, capsys):
    # A baseline the freshness gate cannot date is untrustworthy.
    path = fake_repo / ratchet.BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": ratchet.BASELINE_SCHEMA_VERSION,
                "counters": {"debt_things": 5, "asset_things": 3},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert _run(fake_repo, "--max-baseline-age-days", "30") == ratchet.EXIT_BROKEN
    assert "tightened_on" in capsys.readouterr().err


def test_freshness_check_is_opt_in(fake_repo):
    # Without the flag the gate is backwards-compatible: regression-only,
    # no freshness failure regardless of baseline age.
    _write_baselines(fake_repo, {"debt_things": 5, "asset_things": 3})
    assert _run(fake_repo) == ratchet.EXIT_GREEN


# -- invariants 3-5: tighten semantics ----------------------------------------


def test_improvement_without_tighten_leaves_file_byte_identical(fake_repo):
    path = _write_baselines(fake_repo, {"debt_things": 9, "asset_things": 3})
    before = path.read_bytes()
    assert _run(fake_repo) == ratchet.EXIT_GREEN
    assert path.read_bytes() == before


def test_tighten_adopts_exactly_the_improved_keys(fake_repo):
    path = _write_baselines(fake_repo, {"debt_things": 9, "asset_things": 3})
    assert _run(fake_repo, "--tighten") == ratchet.EXIT_GREEN
    stored = json.loads(path.read_text())["counters"]
    assert stored == {"debt_things": 5, "asset_things": 3}


def test_red_run_never_mutates_baselines_even_with_tighten(fake_repo):
    # debt improved (9 -> 5) but asset regressed (4 -> 3): run is red.
    path = _write_baselines(fake_repo, {"debt_things": 9, "asset_things": 4})
    before = path.read_bytes()
    assert _run(fake_repo, "--tighten") == ratchet.EXIT_REGRESSION
    assert path.read_bytes() == before


# -- invariant 6: baseline drift is BROKEN in all four shapes -----------------


@pytest.mark.parametrize(
    "counters_payload",
    [
        {"debt_things": 5},  # missing key
        {"debt_things": 5, "asset_things": 3, "ghost": 0},  # unknown key
        {"debt_things": 5.5, "asset_things": 3},  # non-integer value
        {"debt_things": True, "asset_things": 3},  # bool is not a count
    ],
)
def test_baseline_drift_is_broken(fake_repo, counters_payload):
    _write_baselines(fake_repo, counters_payload)
    assert _run(fake_repo) == ratchet.EXIT_BROKEN


def test_wrong_schema_version_is_broken(fake_repo):
    path = fake_repo / ratchet.BASELINE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "v0", "counters": {}}))
    assert _run(fake_repo) == ratchet.EXIT_BROKEN


def test_missing_baselines_file_is_broken_with_init_hint(fake_repo, capsys):
    assert _run(fake_repo) == ratchet.EXIT_BROKEN
    assert "--init" in capsys.readouterr().err


# -- invariant 7: init exactly once -------------------------------------------


def test_init_writes_current_reality_then_refuses_to_overwrite(fake_repo, capsys):
    assert _run(fake_repo, "--init") == ratchet.EXIT_GREEN
    path = fake_repo / ratchet.BASELINE_PATH
    assert json.loads(path.read_text())["counters"] == {"debt_things": 5, "asset_things": 3}
    before = path.read_bytes()
    assert _run(fake_repo, "--init") == ratchet.EXIT_BROKEN
    assert path.read_bytes() == before


# -- invariant 8: broken measurement blocks -----------------------------------


def test_broken_counter_exits_broken_not_green(fake_repo, monkeypatch):
    def explode(_root):
        raise BrokenCounter("synthetic measurement failure")

    broken = Counter(
        name="debt_things", direction=Direction.DOWN, end_target=0,
        definition="always broken", measure=explode,
    )
    monkeypatch.setattr(ratchet, "COUNTERS", (broken,))
    _write_baselines(fake_repo, {"debt_things": 0})
    assert _run(fake_repo) == ratchet.EXIT_BROKEN


@pytest.mark.parametrize(
    "crash",
    [
        RuntimeError("tool wrapper blew up"),
        OSError("binary vanished mid-run"),
        __import__("subprocess").TimeoutExpired(cmd="ruff", timeout=120),
        ValueError("malformed tool output"),
    ],
)
def test_any_measurement_crash_is_broken_not_a_traceback(fake_repo, monkeypatch, crash, capsys):
    """The fail-closed contract covers UNEXPECTED crashes, not only the
    deliberate BrokenCounter — an unmeasured counter is an open gate."""

    def explode(_root):
        raise crash

    broken = Counter(
        name="debt_things", direction=Direction.DOWN, end_target=0,
        definition="crashes unexpectedly", measure=explode,
    )
    monkeypatch.setattr(ratchet, "COUNTERS", (broken,))
    _write_baselines(fake_repo, {"debt_things": 0})
    assert _run(fake_repo) == ratchet.EXIT_BROKEN
    err = capsys.readouterr().err
    assert "debt_things" in err and "BROKEN" in err


# -- invariant 9: persistence round-trip, no droppings ------------------------


def test_save_load_round_trip_and_no_temp_droppings(fake_repo, monkeypatch):
    monkeypatch.setattr(ratchet, "COUNTERS", _fake_counters(debt_things=1, asset_things=2))
    path = fake_repo / ratchet.BASELINE_PATH
    ratchet.save_baselines(path, {"debt_things": 1, "asset_things": 2}, "2026-06-13")
    assert ratchet.load_baselines(path) == {"debt_things": 1, "asset_things": 2}
    siblings = [p.name for p in path.parent.iterdir()]
    assert siblings == [path.name]


# -- invariant 10: measurement ground truth on a synthetic repo ---------------


SWALLOW_SOURCE = '''\
def handled():
    try:
        work()
    except ValueError:
        pass            # narrow: NOT a swallow site
    except Exception:
        pass            # swallow site


def acted_upon():
    try:
        work()
    except Exception:
        log("seen")     # acts: NOT a swallow site


def bare():
    try:
        work()
    except:
        pass            # swallow site
    try:
        work()
    except (ValueError, Exception):
        pass            # swallow site (tuple includes Exception)
'''


def _synthetic_repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "dharma_swarm"
    pkg.mkdir()
    (pkg / "swallows.py").write_text(SWALLOW_SOURCE)
    (pkg / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(501)) + "\n")
    (pkg / "small.py").write_text("y = 1\n")
    gov = tmp_path / "scripts" / "governance"
    gov.mkdir(parents=True)
    (gov / "spine_bypass_report.py").write_text(
        '_INTENTIONAL_BYPASS: dict[tuple[str, int], str] = {\n'
        '    ("a.py", 1): "first",\n'
        '    ("b.py", 2): "second",\n'
        '}\n'
    )
    props = tmp_path / "tests" / "properties"
    props.mkdir(parents=True)
    (props / "test_alpha.py").write_text("")
    (props / "helper.py").write_text("")
    patterns = tmp_path / "docs" / "governance" / "hygiene" / "patterns"
    patterns.mkdir(parents=True)
    for pattern_id, stage in [("VC-A1", "enforced"), ("VC-A2", "resolved"), ("VC-A3", "advisory")]:
        (patterns / f"{pattern_id}.yaml").write_text(
            json.dumps({"id": pattern_id, "stage": stage})
        )
    return tmp_path


def test_swallow_sites_match_the_exact_shape(tmp_path):
    repo = _synthetic_repo(tmp_path)
    reading = counters_mod.measure_silent_exception_swallows(repo)
    assert reading.value == 3
    assert all("swallows.py" in line for line in reading.evidence)


def test_bypass_counter_counts_dict_literal_entries(tmp_path):
    repo = _synthetic_repo(tmp_path)
    assert counters_mod.measure_spine_bypass_entries(repo).value == 2


def test_bypass_counter_is_broken_when_owner_missing(tmp_path):
    (tmp_path / "scripts" / "governance").mkdir(parents=True)
    with pytest.raises(BrokenCounter):
        counters_mod.measure_spine_bypass_entries(tmp_path)


def test_module_budget_counters_see_line_counts(tmp_path):
    repo = _synthetic_repo(tmp_path)
    assert counters_mod.measure_modules_over_500_lines(repo).value == 1
    assert counters_mod.measure_largest_module_lines(repo).value == 501


def test_lifecycle_counter_counts_only_enforced_or_resolved(tmp_path):
    repo = _synthetic_repo(tmp_path)
    reading = counters_mod.measure_hygiene_patterns_enforced_or_resolved(repo)
    assert reading.value == 2
    assert reading.evidence == ("VC-A1 (enforced)", "VC-A2 (resolved)")


def test_property_test_counter_counts_only_test_files(tmp_path):
    repo = _synthetic_repo(tmp_path)
    assert counters_mod.measure_property_test_files(repo).value == 1


_RUFF_AVAILABLE = shutil.which("ruff") is not None or (REPO_ROOT / ".venv/bin/ruff").exists()


def _link_ruff(repo: Path) -> None:
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    real = shutil.which("ruff") or str(REPO_ROOT / ".venv/bin/ruff")
    (venv_bin / "ruff").symlink_to(real)


@pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff binary not available")
def test_ruff_counter_finds_a_planted_undefined_name(tmp_path):
    repo = _synthetic_repo(tmp_path)
    (repo / "dharma_swarm" / "broken.py").write_text("value = undefined_name\n")
    _link_ruff(repo)
    reading = counters_mod.measure_ruff_undefined_or_redefined(repo)
    assert reading.value >= 1
    assert any("broken.py" in line and "F821" in line for line in reading.evidence)


@pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff binary not available")
def test_ruff_counter_cannot_be_bypassed_with_noqa(tmp_path):
    """A `# noqa: F821` comment must not hide a new undefined name —
    suppression is a review conversation, not a counter bypass."""
    repo = _synthetic_repo(tmp_path)
    (repo / "dharma_swarm" / "sneaky.py").write_text(
        "value = undefined_name  # noqa: F821\n"
    )
    _link_ruff(repo)
    reading = counters_mod.measure_ruff_undefined_or_redefined(repo)
    assert any("sneaky.py" in line and "F821" in line for line in reading.evidence)
