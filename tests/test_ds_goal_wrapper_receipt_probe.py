from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def _load_probe_module():
    spec = importlib.util.spec_from_file_location(
        "ds_goal_wrapper_receipt_probe",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "ds_goal_wrapper_receipt_probe.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _init_probe_db(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                receipt_type TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                side_effect_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE idempotency_records (
                idempotency_key TEXT NOT NULL,
                side_effect_key TEXT NOT NULL,
                status TEXT NOT NULL,
                result_receipt_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, side_effect_key)
            );
            """
        )


def _insert_receipt(
    db: sqlite3.Connection,
    *,
    receipt_id: str,
    receipt_type: str,
    side_effect_key: str,
) -> None:
    db.execute(
        "INSERT INTO runtime_receipts"
        " (receipt_id, receipt_type, run_id, task_id, trace_id, correlation_id,"
        " agent_id, idempotency_key, side_effect_key, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            receipt_id,
            receipt_type,
            "run-ds-goal",
            "task-ds-goal",
            "trace-ds-goal",
            "corr-ds-goal",
            "codex_composer",
            "idem-ds-goal",
            side_effect_key,
            "completed",
            f"2026-06-14T05:00:0{receipt_id[-1]}Z",
        ),
    )


def _insert_idempotency(db: sqlite3.Connection, *, side_effect_key: str, receipt_id: str) -> None:
    db.execute(
        "INSERT INTO idempotency_records"
        " (idempotency_key, side_effect_key, status, result_receipt_id, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            "idem-ds-goal",
            side_effect_key,
            "completed",
            receipt_id,
            "2026-06-14T05:00:00Z",
            "2026-06-14T05:00:01Z",
        ),
    )


def test_probe_summary_marks_keyed_major_receipts_clean(tmp_path: Path) -> None:
    mod = _load_probe_module()
    db_path = tmp_path / "runtime.db"
    _init_probe_db(db_path)
    with sqlite3.connect(db_path) as db:
        rows = [
            ("rr-claim-1", "task_claim", "task_claim:claim:completed"),
            ("rr-run-2", "delegation_run", "delegation_run:run:completed"),
            ("rr-final-3", "delegation_run", "ds_goal.run:mission:task"),
        ]
        for receipt_id, receipt_type, side_effect_key in rows:
            _insert_receipt(
                db,
                receipt_id=receipt_id,
                receipt_type=receipt_type,
                side_effect_key=side_effect_key,
            )
            _insert_idempotency(
                db,
                side_effect_key=side_effect_key,
                receipt_id=receipt_id,
            )

    summary = mod.summarize_runtime_receipts(db_path, run_id="run-ds-goal")

    assert summary["clean"] is True
    assert summary["major_total"] == 3
    assert summary["major_missing_side_effect_key"] == 0
    assert summary["major_missing_idempotency_joins"] == 0


def test_probe_summary_marks_blank_sync_receipts_dirty(tmp_path: Path) -> None:
    mod = _load_probe_module()
    db_path = tmp_path / "runtime.db"
    _init_probe_db(db_path)
    with sqlite3.connect(db_path) as db:
        _insert_receipt(
            db,
            receipt_id="rr-claim-1",
            receipt_type="task_claim",
            side_effect_key="",
        )
        _insert_receipt(
            db,
            receipt_id="rr-run-2",
            receipt_type="delegation_run",
            side_effect_key="",
        )
        _insert_receipt(
            db,
            receipt_id="rr-final-3",
            receipt_type="delegation_run",
            side_effect_key="ds_goal.run:mission:task",
        )
        _insert_idempotency(
            db,
            side_effect_key="ds_goal.run:mission:task",
            receipt_id="rr-final-3",
        )

    summary = mod.summarize_runtime_receipts(db_path, run_id="run-ds-goal")

    assert summary["clean"] is False
    assert summary["major_total"] == 3
    assert summary["major_missing_side_effect_key"] == 2
    assert summary["major_missing_idempotency_joins"] == 2


def test_probe_classifies_clean_pin_and_dirty_default_as_split_brain() -> None:
    mod = _load_probe_module()

    status, next_action = mod.classify_cases([
        {"case": "pinned", "receipt_summary": {"clean": True}},
        {"case": "default", "receipt_summary": {"clean": False}},
    ])

    assert status == "split_brain_confirmed"
    assert "default wrapper target emits weak receipts" in next_action


def test_probe_classifies_both_clean_as_clean() -> None:
    mod = _load_probe_module()

    status, next_action = mod.classify_cases([
        {"case": "pinned", "receipt_summary": {"clean": True}},
        {"case": "default", "receipt_summary": {"clean": True}},
    ])

    assert status == "clean"
    assert "both produce keyed major receipts" in next_action


def test_default_wrapper_target_uses_installed_wrapper_contract(tmp_path: Path) -> None:
    mod = _load_probe_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    main_repo = home / "dharma_swarm_main"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    for repo in (audited_repo, main_repo):
        (repo / "scripts" / "runtime").mkdir(parents=True)
        (repo / "scripts" / "runtime" / "autonomy_spine.py").write_text(
            "# probe\n",
            encoding="utf-8",
        )
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then',
                '  repo="$DHARMA_SWARM_REPO"',
                'elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then',
                '  repo="$HOME/dharma_swarm_main"',
                "else",
                '  repo="$HOME/dharma_swarm"',
                "fi",
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        ),
        encoding="utf-8",
    )

    target = mod._default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )

    assert target["target_repo"] == str(main_repo)
    assert target["target_resolution_source"] == (
        "installed_wrapper_dharma_swarm_main_preference"
    )
    assert target["target_matches_audited_repo"] is False
    contract = target["installed_wrapper_contract"]
    assert contract["wrapper_exists"] is True
    assert contract["wrapper_sha256"]
    assert contract["dharma_swarm_repo_pin_supported"] is True
    assert contract["dharma_swarm_main_preference_declared"] is True
    assert contract["dharma_swarm_fallback_declared"] is True
    assert contract["execs_autonomy_spine"] is True
    packet = mod.wrapper_convergence_decision_packet(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    assert packet["approval_state"] == "operator_approval_required"
    assert packet["operator_approval_required"] is True
    assert packet["default_target_repo"] == str(main_repo)
    assert packet["default_target_matches_audited_checkout"] is False
    assert packet["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={audited_repo} {wrapper}"
    )
    assert [
        item["id"] for item in packet["operator_decision_options"]
    ] == [
        "converge_installed_wrapper_default_to_audited_checkout",
        "harden_current_default_target_checkout",
        "retain_default_with_mandatory_pin_or_quarantine",
    ]
    assert "edit_installed_wrapper" in packet["forbidden_without_operator_approval"]
    assert "declare_75_plus_from_pin_mitigation_only" in packet[
        "forbidden_without_operator_approval"
    ]
    assert packet["score_effect"].startswith("no_score_movement")
    assert packet["preflight_commands"][0] == (
        "python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict"
    )
    assert packet["preflight_commands"][1] == (
        "python3 scripts/runtime/ds_goal_longrun_preflight.py --json"
    )
    assert packet["preflight_commands"][2] == (
        f"DHARMA_SWARM_REPO={audited_repo} "
        "python3 scripts/runtime/ds_goal_longrun_preflight.py --json"
    )


def test_default_wrapper_target_accepts_converged_wrapper_order(
    tmp_path: Path,
) -> None:
    mod = _load_probe_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    main_repo = home / "dharma_swarm_main"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    for repo in (audited_repo, main_repo):
        (repo / "scripts" / "runtime").mkdir(parents=True)
        (repo / "scripts" / "runtime" / "autonomy_spine.py").write_text(
            "# probe\n",
            encoding="utf-8",
        )
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# Was: preferred dharma_swarm_main; keep it only as fallback.",
                'if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then',
                '  repo="$DHARMA_SWARM_REPO"',
                'elif [[ -f "$HOME/dharma_swarm/scripts/runtime/autonomy_spine.py" ]]; then',
                '  repo="$HOME/dharma_swarm"',
                'elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then',
                '  repo="$HOME/dharma_swarm_main"',
                "else",
                '  repo="$HOME/dharma_swarm"',
                "fi",
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        ),
        encoding="utf-8",
    )

    target = mod._default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )

    assert target["target_repo"] == str(audited_repo)
    assert target["target_resolution_source"] == (
        "installed_wrapper_dharma_swarm_preference"
    )
    assert target["target_matches_audited_repo"] is True
    contract = target["installed_wrapper_contract"]
    assert contract["dharma_swarm_preference_declared"] is True
    assert contract["dharma_swarm_main_preference_declared"] is False
    assert contract["dharma_swarm_fallback_declared"] is True
    assert contract["default_target_order"] == ["dharma_swarm", "dharma_swarm_main"]
    assert contract["fallback_target"] == "dharma_swarm"
    packet = mod.wrapper_convergence_decision_packet(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    assert packet["approval_state"] == "not_required_default_matches_audited_checkout"
    assert packet["operator_approval_required"] is False
    assert packet["default_target_repo"] == str(audited_repo)
    assert packet["current_mitigation"] == "none_needed"


def test_default_wrapper_target_falls_back_when_main_not_declared(tmp_path: Path) -> None:
    mod = _load_probe_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    fallback_repo = home / "dharma_swarm"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    (fallback_repo / "scripts" / "runtime").mkdir(parents=True)
    (fallback_repo / "scripts" / "runtime" / "autonomy_spine.py").write_text(
        "# probe\n",
        encoding="utf-8",
    )
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'repo="$HOME/dharma_swarm"',
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        ),
        encoding="utf-8",
    )

    target = mod._default_wrapper_target(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )

    assert target["target_repo"] == str(fallback_repo)
    assert target["target_resolution_source"] == "installed_wrapper_dharma_swarm_fallback"
    assert target["target_matches_audited_repo"] is True
    assert target["installed_wrapper_contract"][
        "dharma_swarm_main_preference_declared"
    ] is False
    packet = mod.wrapper_convergence_decision_packet(
        home=home,
        audited_repo=audited_repo,
        wrapper=wrapper,
    )
    assert packet["approval_state"] == "not_required_default_matches_audited_checkout"
    assert packet["operator_approval_required"] is False
    assert packet["current_mitigation"] == "none_needed"


def test_probe_json_output_includes_convergence_decision_packet(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    mod = _load_probe_module()
    home = tmp_path / "home"
    audited_repo = home / "dharma_swarm"
    default_repo = home / "dharma_swarm_main"
    wrapper = home / ".dharma" / "bin" / "ds-goal"
    for repo in (audited_repo, default_repo):
        (repo / "scripts" / "runtime").mkdir(parents=True)
        (repo / "scripts" / "runtime" / "autonomy_spine.py").write_text(
            "# probe\n",
            encoding="utf-8",
        )
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                'if [[ -n "${DHARMA_SWARM_REPO:-}" ]]; then',
                '  repo="$DHARMA_SWARM_REPO"',
                'elif [[ -f "$HOME/dharma_swarm_main/scripts/runtime/autonomy_spine.py" ]]; then',
                '  repo="$HOME/dharma_swarm_main"',
                "else",
                '  repo="$HOME/dharma_swarm"',
                "fi",
                'exec python3 scripts/runtime/autonomy_spine.py "$@"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod.Path, "home", staticmethod(lambda: home))

    def fake_run_wrapper_case(**kwargs):
        case = kwargs["case"]
        return {
            "case": case,
            "run_id": f"run-{case}",
            "receipt_summary": {
                "clean": case == "pinned",
                "major_total": 3,
                "major_missing_side_effect_key": 0 if case == "pinned" else 2,
                "major_missing_idempotency_joins": 0 if case == "pinned" else 2,
            },
        }

    monkeypatch.setattr(mod, "_run_wrapper_case", fake_run_wrapper_case)

    rc = mod.main(
        [
            "--wrapper",
            str(wrapper),
            "--audited-repo",
            str(audited_repo),
            "--proof-root",
            str(tmp_path / "proof"),
            "--expect-split-brain",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    packet = payload["convergence_decision_packet"]
    assert packet["approval_state"] == "operator_approval_required"
    assert packet["latest_probe_status"] == "split_brain_confirmed"
    assert packet["latest_probe_next_action"] == payload["next_action"]
    assert packet["latest_probe_proof_root"] == str(tmp_path / "proof")
    assert packet["default_target_repo"] == str(default_repo)
    assert packet["safe_current_checkout_invocation"] == (
        f"DHARMA_SWARM_REPO={audited_repo} {wrapper}"
    )
