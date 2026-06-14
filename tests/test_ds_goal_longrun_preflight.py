from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location(
        "ds_goal_longrun_preflight",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "ds_goal_longrun_preflight.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_wrapper(wrapper: Path, *, prefers_main: bool) -> None:
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    if prefers_main:
        body = "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then',
                '  repo="$DHARMA_SWARM_REPO"',
                'elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then',
                '  repo="$HOME/dharma_swarm_main"',
                "else",
                '  repo="$HOME/dharma_swarm"',
                "fi",
                'cd "$repo"',
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        )
    else:
        body = "\n".join(
            [
                "#!/usr/bin/env bash",
                'repo="${DHARMA_SWARM_REPO:-$HOME/dharma_swarm}"',
                'cd "$repo"',
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        )
    wrapper.write_text(body, encoding="utf-8")


def _write_repo(repo: Path) -> None:
    (repo / "scripts" / "runtime").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "runtime" / "autonomy_spine.py").write_text(
        "# probe\n",
        encoding="utf-8",
    )


def test_preflight_blocks_unpinned_split_brain_wrapper(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    mod = _load_preflight_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    default_repo = home / "dharma_swarm_main"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    _write_repo(audited_repo)
    _write_repo(default_repo)
    _write_wrapper(wrapper, prefers_main=True)
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("DHARMA_SWARM_REPO", raising=False)

    rc = mod.main(
        [
            "--wrapper",
            str(wrapper),
            "--audited-repo",
            str(audited_repo),
            "--json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked_unpinned_default_target"
    assert payload["passed"] is False
    assert payload["longrun_start_allowed"] is False
    assert payload["default_target_repo"] == str(default_repo)
    assert payload["default_target_matches_audited_checkout"] is False
    assert payload["operator_convergence_required"] is True
    assert "start_repo_native_longrun_from_unpinned_ds_goal" in payload[
        "forbidden_without_operator_approval"
    ]
    assert payload["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={audited_repo} {wrapper}"
    )


def test_preflight_allows_explicit_audited_checkout_pin_without_score_movement(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    mod = _load_preflight_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    default_repo = home / "dharma_swarm_main"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    _write_repo(audited_repo)
    _write_repo(default_repo)
    _write_wrapper(wrapper, prefers_main=True)
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("DHARMA_SWARM_REPO", str(audited_repo))

    rc = mod.main(
        [
            "--wrapper",
            str(wrapper),
            "--audited-repo",
            str(audited_repo),
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass_explicit_audited_checkout_pin"
    assert payload["passed"] is True
    assert payload["repo_pin_source"] == "DHARMA_SWARM_REPO"
    assert payload["repo_pin_matches_audited_checkout"] is True
    assert payload["operator_convergence_required"] is True
    assert payload["score_effect"] == "no_score_movement_preflight_only"
    assert payload["default_target_repo"] == str(default_repo)


def test_preflight_blocks_wrong_repo_pin(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    mod = _load_preflight_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    default_repo = home / "dharma_swarm_main"
    wrong_repo = home / "other"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    _write_repo(audited_repo)
    _write_repo(default_repo)
    _write_repo(wrong_repo)
    _write_wrapper(wrapper, prefers_main=True)
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: home))

    rc = mod.main(
        [
            "--wrapper",
            str(wrapper),
            "--audited-repo",
            str(audited_repo),
            "--repo-pin",
            str(wrong_repo),
            "--json",
        ]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked_repo_pin_mismatch"
    assert payload["repo_pin_source"] == "argument"
    assert payload["repo_pin_matches_audited_checkout"] is False


def test_preflight_passes_when_default_target_matches_audited_checkout(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    mod = _load_preflight_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    _write_repo(audited_repo)
    _write_wrapper(wrapper, prefers_main=False)
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("DHARMA_SWARM_REPO", raising=False)

    rc = mod.main(
        [
            "--wrapper",
            str(wrapper),
            "--audited-repo",
            str(audited_repo),
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass_default_matches_audited_checkout"
    assert payload["operator_convergence_required"] is False
    assert payload["default_target_repo"] == str(audited_repo)
