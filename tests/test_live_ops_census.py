from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.operator_core.control_surface import (
    _rows_from_live_ops_census,
    build_control_surface_summary,
)
from dharma_swarm.operator_core.control_surface_models import (
    _build_human_decision_context,
)
import scripts.runtime.live_ops_census as live_ops_census
from scripts.runtime.live_ops_census import AUTHORITY_SOURCES, build_live_ops_census


REPO_ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_live_ops_census_folds_in_canonical_sources(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state_root"
    for source in AUTHORITY_SOURCES:
        _write(repo / source["path"])
    _write(
        state / "state" / "revenue_wedge_last_state.json",
        json.dumps(
            {
                "gauntlet_decision": "HOLD",
                "human_approved_outreach": False,
                "revenue_usd": 0,
                "fire_ts": "2026-06-02T00:00:00Z",
            }
        ),
    )
    _write(
        state / "forge_reality_arena_master" / "codex_overnight_heartbeat.json",
        json.dumps({"ts": "2026-06-02T00:00:00Z", "status": "handoff"}),
    )
    _write(state / "a2a_bus" / "receipts" / "hermes" / "receipt_1.json", "{}")
    _write(state / "a2a_bus" / "messages" / "message_1.json", "{}")
    _write(state / "a2a_bus" / "tasks" / "queue.jsonl", "{}\n")
    _write(state / "a2a_bus" / "nats_live_receipt.json", "{}")
    _write(state / "a2a_bus" / "nats_contact_receipts.jsonl", "{}\n")
    _write(state / "a2a_bus" / "nats_oz_receipts.jsonl", "{}\n")
    _write(state / "nats" / "receipts" / "receipt_1.json", "{}")
    _write(state / "nats" / "nats-server.log", "ready\n")

    payload = build_live_ops_census(
        repo_root=repo,
        state_root=state,
        run_probes=False,
        processes={
            "dharma_daemon": [{"pid": "101", "command": "dharma_swarm.dgc_cli orchestrate-live"}],
            "nats": [{"pid": "102", "command": "nats-server local-nats.conf"}],
        },
        ports={
            "dharma_daemon": {"port": 7433, "listening": True, "evidence": "daemon"},
            "nats": {"port": 4222, "listening": True, "evidence": "nats"},
            "dashboard_api": {"port": 8420, "listening": True, "evidence": "api"},
            "dashboard_web": {"port": 3420, "listening": True, "evidence": "web"},
        },
    )

    assert payload["schema_version"] == "live_ops_census.v1"
    assert {source["path"] for source in payload["authority_sources"]} >= {
        "ACTIVE_SURFACE_MANIFEST.yaml",
        "docs/governance/ACTIVE_TRACK.yaml",
        "docs/governance/SOVEREIGN_MANIFEST.md",
        "docs/governance/ANTI_SLOP_RULES.md",
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
        "docs/ops/TMUX_AGENT_SUBSTRATE.md",
    }
    assert all(source["exists"] for source in payload["authority_sources"])

    surfaces = {surface["id"]: surface for surface in payload["surfaces"]}
    assert surfaces["substrate.dharma_daemon"]["status"] == "live"
    assert surfaces["substrate.dharma_daemon"]["human_authority_required"] is True
    assert "issue #1246" in surfaces["substrate.dharma_daemon"]["next_action"]
    assert surfaces["transport.nats"]["status"] == "live"
    assert surfaces["evidence.a2a_mirrors"]["status"] == "live"
    assert surfaces["evidence.a2a_mirrors"]["desired_state"] == "evidence-mirror-not-authority"
    assert surfaces["evidence.nats_receipts"]["status"] == "live"
    assert surfaces["evidence.nats_receipts"]["desired_state"] == "ack-receipt-evidence"
    assert surfaces["evidence.nats_receipts"]["raw"]["nats_live_receipt_exists"] is True
    assert surfaces["dashboard.local"]["status"] == "live"
    assert surfaces["revenue.cashclaw_gate"]["status"] == "blocked"
    assert surfaces["revenue.cashclaw_gate"]["human_authority_required"] is True


def test_live_ops_census_surface_contract_is_complete(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=False,
    )
    surfaces = payload["surfaces"]
    required = {
        "id",
        "label",
        "class",
        "status",
        "desired_state",
        "priority",
        "evidence",
        "authority_refs",
        "restart_command",
        "stop_policy",
        "next_action",
        "human_authority_required",
        "vps_candidate",
        "raw",
        "observation",
        "process_observation",
        "port_observation",
    }

    assert payload["summary"]["total"] == len(surfaces) == 16
    for surface in surfaces:
        assert required <= set(surface)
        assert isinstance(surface["evidence"], list)
        assert isinstance(surface["authority_refs"], list)
        assert surface["authority_refs"], surface["id"]
        assert isinstance(surface["restart_command"], str)
        assert isinstance(surface["stop_policy"], str)
        assert isinstance(surface["human_authority_required"], bool)
        assert isinstance(surface["vps_candidate"], bool)

    human_authority_ids = {
        surface["id"]
        for surface in surfaces
        if surface["human_authority_required"]
    }
    assert {
        "substrate.dharma_daemon",
        "revenue.cashclaw_gate",
        "remote.agni",
        "agent.merge_master_mike",
        "load.colima_openclaw",
    } <= human_authority_ids
    assert payload["summary"]["human_authority_required"] == len(human_authority_ids)


def test_probe_observation_distinguishes_positive_negative_and_unavailable(
    monkeypatch,
) -> None:
    def fake_run(args: list[str], **_kwargs):
        pattern = args[-1]
        if pattern == live_ops_census.PROCESS_PATTERNS["dharma_cron"]:
            return 1, ""
        if pattern == live_ops_census.PROCESS_PATTERNS["terminal_tui"]:
            return 0, "4321 python terminal_tui_interaction.py"
        return 127, "pgrep unavailable"

    monkeypatch.setattr(live_ops_census, "_run", fake_run)

    processes = live_ops_census._process_snapshot(run_probes=True)

    assert live_ops_census._process_observation("dharma_cron", processes) == "negative"
    assert live_ops_census._process_observation("terminal_tui", processes) == "positive"
    assert live_ops_census._process_observation("merge_master_mike", processes) == "unavailable"


def test_process_or_port_status_requires_current_probe_evidence() -> None:
    assert (
        live_ops_census._live_if_process_or_port(
            "dharma_cron",
            {"dharma_cron": []},
            {},
        )
        == "stopped"
    )
    assert (
        live_ops_census._live_if_process_or_port(
            "dharma_cron",
            {},
            {},
        )
        == "unknown"
    )
    assert (
        live_ops_census._live_if_process_or_port(
            "dharma_cron",
            {"dharma_cron": [{"pid": "99", "command": "cron daemon"}]},
            {},
        )
        == "live"
    )


def test_launchd_crash_loop_is_current_stopped_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        live_ops_census,
        "_run",
        lambda *_args, **_kwargs: (
            0,
            "state = not running\nruns = 13648\nlast exit code = 2",
        ),
    )

    result = live_ops_census._launchd_observation(
        "com.dharma.fugu-ultra-semantic-responder",
        run_probes=True,
    )

    assert result["observation"] == "stopped"
    assert "last exit code = 2" in result["evidence"]


def test_live_ops_census_projects_into_control_surface_rows(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-02T00:00:00Z",
        "surfaces": [
            {
                "id": "revenue.cashclaw_gate",
                "label": "Revenue / CashClaw gate",
                "class": "revenue",
                "status": "blocked",
                "desired_state": "blocked-until-operator-approval",
                "priority": "p0",
                "evidence": ["state/revenue_wedge_last_state.json"],
                "authority_refs": ["docs/governance/ACTIVE_TRACK.yaml"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "keep HOLD until explicit operator approval",
                "raw": {},
            }
        ],
    }
    _write(tmp_path / "docs" / "governance" / "ACTIVE_TRACK.yaml")

    rows = _rows_from_live_ops_census(payload, tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == "live_ops.revenue.cashclaw_gate"
    assert row.kind == "fleet"
    assert row.coherence_state == "drifted"
    assert "human_authority_required" in row.gap_codes
    assert any(ref.path == "docs/governance/ACTIVE_TRACK.yaml" for ref in row.source_refs)

    ctx = _build_human_decision_context(row)
    assert ctx.required is True
    assert "operator authority" in ctx.why_now


def test_live_ops_rows_preserve_operator_contract_fields(tmp_path: Path) -> None:
    payload = {
        "schema_version": "live_ops_census.v1",
        "generated_at": "2026-06-02T00:00:00Z",
        "surfaces": [
            {
                "id": "remote.agni",
                "label": "AGNI remote watcher / trading",
                "class": "remote",
                "status": "stale",
                "desired_state": "remote-observed-or-blocked",
                "priority": "p0",
                "evidence": ["remote_nodes/agni/kaizen_agni_latest.json"],
                "authority_refs": ["docs/ops/TMUX_AGENT_SUBSTRATE.md"],
                "human_authority_required": True,
                "vps_candidate": True,
                "next_action": "refresh remote receipts and feeds",
                "restart_command": "ssh agni  # inspect remote receipts before launching anything",
                "stop_policy": "no-real-money-without-operator-approval",
                "raw": {"ack": "fixture"},
            },
            {
                "id": "load.colima_openclaw",
                "label": "Colima / OpenClaw VM",
                "class": "heavy",
                "status": "live",
                "desired_state": "operator-choice",
                "priority": "p2",
                "evidence": ["colima-openclaw-secure"],
                "authority_refs": ["docs/ops/LIVE_OPS_COCKPIT.md"],
                "human_authority_required": True,
                "vps_candidate": False,
                "next_action": "stop for battery/flight if not needed",
                "restart_command": "colima start openclaw-secure",
                "stop_policy": "safe-to-stop-if-not-using-openclaw",
                "raw": {},
            },
        ],
    }
    _write(tmp_path / "docs" / "ops" / "TMUX_AGENT_SUBSTRATE.md")
    _write(tmp_path / "docs" / "ops" / "LIVE_OPS_COCKPIT.md")

    rows = {row.id: row for row in _rows_from_live_ops_census(payload, tmp_path)}
    agni = rows["live_ops.remote.agni"]
    assert agni.observed_state == "stale"
    assert "live_ops_status:stale" in agni.gap_codes
    assert "live_ops_not_live" in agni.gap_codes
    assert "human_authority_required" in agni.gap_codes
    assert "vps_candidate" in agni.gap_codes
    assert agni.raw["restart_command"].startswith("ssh agni")
    assert agni.raw["stop_policy"] == "no-real-money-without-operator-approval"
    assert any(ref.path == "docs/ops/TMUX_AGENT_SUBSTRATE.md" and ref.exists for ref in agni.source_refs)
    assert any(ev.source == "remote_nodes/agni/kaizen_agni_latest.json" for ev in agni.evidence)

    colima = rows["live_ops.load.colima_openclaw"]
    assert colima.observed_state == "live"
    assert "heavy_local_load" in colima.gap_codes
    assert "human_authority_required" in colima.gap_codes
    assert colima.raw["restart_command"] == "colima start openclaw-secure"
    assert colima.raw["stop_policy"] == "safe-to-stop-if-not-using-openclaw"


def test_control_surface_summary_names_live_ops_source() -> None:
    summary = build_control_surface_summary(rows=[])
    assert "live_ops_census" in summary["sources_consulted"]


def test_build_live_ops_census_without_write_does_not_create_receipt(tmp_path: Path) -> None:
    output = tmp_path / "state" / "ops" / "live_process_census.json"

    payload = live_ops_census.build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=False,
    )

    assert payload["schema_version"] == "live_ops_census.v1"
    assert not output.exists()


def test_live_ops_census_cli_requires_write_flag_for_receipt(monkeypatch, capsys, tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "live_ops_census.py",
            "--repo-root",
            str(tmp_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output",
            str(output),
            "--no-probes",
        ],
    )

    assert live_ops_census.main() == 0
    assert not output.exists()
    assert "live_ops_census.v1" in capsys.readouterr().out


def test_control_surface_live_ops_adapter_does_not_write_receipts() -> None:
    tree = ast.parse((REPO_ROOT / "dharma_swarm/operator_core/control_surface_live_ops.py").read_text())
    write_calls: list[str] = []
    forbidden_path_attrs = {
        "chmod",
        "mkdir",
        "open",
        "rename",
        "replace",
        "rmdir",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_path_attrs:
            write_calls.append(node.func.attr)
        if isinstance(node.func, ast.Name) and node.func.id in {"open", "write_census"}:
            write_calls.append(node.func.id)
    assert write_calls == []


def test_live_ops_census_subprocess_is_centralized_in_run_helper() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    call_owners: list[str] = []
    shell_true_locations: list[int] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
            ):
                call_owners.append(self.stack[-1] if self.stack else "<module>")
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                        if keyword.value.value is True:
                            shell_true_locations.append(node.lineno)
            self.generic_visit(node)

    Visitor().visit(tree)
    assert call_owners == ["_run"]
    assert shell_true_locations == []


def test_live_ops_census_writes_only_from_explicit_write_census_function() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    write_owners: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"mkdir", "write_text", "write_bytes"}:
                write_owners.append(self.stack[-1] if self.stack else "<module>")
            self.generic_visit(node)

    Visitor().visit(tree)
    assert write_owners
    assert set(write_owners) == {"write_census"}


def test_live_ops_census_has_no_process_control_api_calls() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    forbidden_names = {"system", "popen", "spawn", "kill", "killpg", "execv", "execve"}
    forbidden_subprocess_attrs = {"Popen", "call", "check_call", "check_output"}
    observed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"os", "subprocess"}
        ):
            if node.func.value.id == "subprocess" and node.func.attr in forbidden_subprocess_attrs:
                observed.append(f"subprocess.{node.func.attr}")
            if node.func.value.id == "os" and node.func.attr in forbidden_names:
                observed.append(f"os.{node.func.attr}")
    assert observed == []


def test_live_ops_census_only_uses_read_only_probe_commands_static() -> None:
    tree = ast.parse((REPO_ROOT / "scripts/runtime/live_ops_census.py").read_text())
    allowed = {"git", "launchctl", "pgrep", "lsof", "tmux"}
    observed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_run":
            continue
        if not node.args or not isinstance(node.args[0], ast.List) or not node.args[0].elts:
            continue
        first = node.args[0].elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            observed.add(first.value)
    assert observed
    assert observed <= allowed


def test_live_ops_census_does_not_execute_displayed_policy_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(live_ops_census.subprocess, "run", fake_run)

    payload = live_ops_census.build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=True,
    )

    allowed = {"git", "launchctl", "pgrep", "lsof", "tmux"}
    observed = {call[0] for call in calls}
    display_first_words = {
        str(surface.get("restart_command", "")).split()[0]
        for surface in payload["surfaces"]
        if str(surface.get("restart_command", "")).strip()
    }
    assert observed
    assert observed <= allowed
    assert not (display_first_words - allowed) & observed


def test_dharma_daemon_pattern_matches_container_and_cli_spellings():
    """Dockerfile.swarm boots `python -m dharma_swarm.orchestrate_live`; the
    CLI-only pattern could never match that cmdline, so the census reported
    the daemon dead on every containerized host."""
    import re

    pattern = live_ops_census.PROCESS_PATTERNS["dharma_daemon"]
    assert re.search(pattern, "python -m dharma_swarm.orchestrate_live")
    assert re.search(pattern, "python3 -m dharma_swarm.dgc_cli orchestrate-live")
    assert not re.search(pattern, "python3 -m dharma_swarm.dgc_cli cron daemon")
