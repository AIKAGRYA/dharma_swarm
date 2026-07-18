"""Committed registry, CLI/rendering, readiness, and public-contract tests."""
from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.fleet_field_registry import (  # noqa: E402
    load_registry,
    main as ffr_main,
    render_table,
)
from scripts.runtime.fleet_field_registry_contract import (  # noqa: E402
    RUNTIME_CELL_COMPONENTS,
    SCHEMA_V2,
    RegistryError,
    compute_readiness_ceiling,
    load_card_declared_routes,
    load_expected_identity_uids,
    load_registry_data,
    validate_registry,
)
from tests.test_fleet_field_registry_validation import (  # noqa: E402
    API,
    JWT,
    _no_leak,
    _reg,
    _v,
)

PY = sys.executable
LINE_BUDGET = 500
RUNTIME_FILES = (
    REPO_ROOT / "scripts/runtime/fleet_field_registry.py",
    REPO_ROOT / "scripts/runtime/fleet_field_registry_contract.py",
    REPO_ROOT / "scripts/runtime/fleet_field_registry_validation.py",
)
TEST_FILES = (
    REPO_ROOT / "tests/test_fleet_field_registry.py",
    REPO_ROOT / "tests/test_fleet_field_registry_validation.py",
)
NON_PROOF = (
    "unknown",
    "unprobed",
    "declared",
    "absent",
    "runtime_observed_uncommitted",
)
EXPECTED_UIDS = (
    "codex_composer",
    "fable_composer",
    "fable_claude_code",
    "hermes-m5",
    "devin-roaming-2987d222",
    "fable_5_cursor",
    "perplexity-computer",
    "kestrel",
    "merge_master_mike",
    "qwen_code",
    "sis_steward",
)
CLI = REPO_ROOT / "scripts/runtime/fleet_field_registry.py"


def test_runtime_scripts_under_line_budget():
    for path in (*RUNTIME_FILES, *TEST_FILES):
        n = len(path.read_text(encoding="utf-8").splitlines())
        assert n < LINE_BUDGET, f"{path.name} has {n} lines (budget {LINE_BUDGET})"


def test_registry_file_exists_parses_and_is_valid():
    data = load_registry()
    assert data["schema"] == SCHEMA_V2 and data["secret_policy"] == "env_var_names_only"
    assert _v(data) == []


def test_every_probed_agent_has_receipt_in_repo():
    honest = {"runtime_observed_uncommitted", "reference_gap", "unprobed", "unknown"}
    for agent in load_registry()["agents"]:
        receipt = agent.get("probe_receipt")
        if not receipt:
            assert agent.get("evidence_status") in honest, agent["agent_uid"]
            continue
        assert (REPO_ROOT / receipt).exists(), agent["agent_uid"]


@pytest.mark.parametrize("status", NON_PROOF, ids=list(NON_PROOF))
def test_non_proof_component_statuses_force_readiness_unknown(status):
    statuses = {n: "probed" for n in RUNTIME_CELL_COMPONENTS}
    statuses["receipt_lifecycle"] = status
    assert (
        compute_readiness_ceiling(
            component_statuses=statuses,
            semantic_executor_mode="always_on",
            transport_contact_tier="HANDLER_ACKED",
            semantic_effect_ceiling="DOMAIN_RECEIPTED",
        )
        == "unknown"
    )


@pytest.mark.parametrize(
    "mode,transport,effect,expected",
    [
        ("always_on", "DOMAIN_RECEIPTED", "DOMAIN_RECEIPTED", "DOMAIN_RECEIPTED"),
        ("none", "DOMAIN_RECEIPTED", "DOMAIN_RECEIPTED", "HANDLER_ACKED"),
        ("always_on", "HANDLER_ACKED", "HANDLER_ACKED", "HANDLER_ACKED"),
    ],
    ids=["proven_semantic_may_exceed", "delivery_only_caps_handler", "handler_baseline"],
)
def test_readiness_semantic_advancement(mode, transport, effect, expected):
    statuses = {n: "probed" for n in RUNTIME_CELL_COMPONENTS}
    assert (
        compute_readiness_ceiling(
            component_statuses=statuses,
            semantic_executor_mode=mode,
            transport_contact_tier=transport,
            semantic_effect_ceiling=effect,
        )
        == expected
    )


def test_runtime_observed_uncommitted_identity_and_grok_build_unknown():
    statuses = {n: "probed" for n in RUNTIME_CELL_COMPONENTS}
    assert (
        compute_readiness_ceiling(
            component_statuses=statuses,
            semantic_executor_mode="always_on",
            transport_contact_tier="HANDLER_ACKED",
            semantic_effect_ceiling="HANDLER_ACKED",
            identity_source="runtime_observed_uncommitted",
        )
        == "unknown"
    )
    a = {x["agent_uid"]: x for x in load_registry()["agents"]}["grok_build"]
    assert a["readiness_ceiling"] == a["runtime_cell"]["readiness_ceiling"] == "unknown"
    assert a["identity_source"] == "runtime_observed_uncommitted"


def test_cli_json_refuses_invalid_registry(monkeypatch, capsys):
    data = copy.deepcopy(load_registry())
    data["agents"][0]["password"] = "cli-json-secret-should-not-print"
    monkeypatch.setattr("scripts.runtime.fleet_field_registry.load_registry", lambda: data)
    assert ffr_main(["--json"]) == 2
    cap = capsys.readouterr()
    _no_leak(cap.out + cap.err, "cli-json-secret-should-not-print")
    assert "secret-bearing key" in cap.err


def test_malformed_yaml_exits_2_without_traceback(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("schema: [\n  - unclosed\n", encoding="utf-8")
    with pytest.raises(RegistryError) as ei:
        load_registry_data(bad)
    msg = str(ei.value)
    assert "parse error" in msg.lower() or "YAMLError" in msg
    assert "Traceback" not in msg


def test_cli_malformed_yaml_exit_2(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "broken.yaml"
    bad.write_text("{this: is: invalid: yaml: [", encoding="utf-8")
    monkeypatch.setattr("scripts.runtime.fleet_field_registry.REGISTRY_PATH", bad)
    monkeypatch.setattr(
        "scripts.runtime.fleet_field_registry.load_registry",
        lambda: load_registry_data(bad),
    )
    assert ffr_main(["--check"]) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err and "registry" in err.lower()


def test_hermes_rushabdev_quarantine_and_target_not_laundered():
    data = load_registry()
    assert any(
        c.get("collision_id") == "hermes-rushabdev-shared-worker-subject"
        for c in (data.get("routing_collisions") or [])
    )
    agents = {a["agent_uid"]: a for a in data["agents"]}
    for uid in ("hermes-m5", "rushabdev"):
        obs = agents[uid]["observed_effective_route"]
        assert obs.get("inbox_subject") in (None, "null")
        assert obs.get("collision_ref") == "hermes-rushabdev-shared-worker-subject"
    rush = agents["rushabdev"]
    assert rush["target_route"]["inbox_subject"] == "dharma.a2a.rushabdev"
    assert rush["observed_effective_route"].get("inbox_subject") in (None, "null")


def test_card_roster_union_aliases_and_declaration_parity():
    expected = load_expected_identity_uids(REPO_ROOT)
    for uid in EXPECTED_UIDS:
        assert uid in expected
    assert "codex" not in expected
    present = {a["agent_uid"] for a in load_registry()["agents"]}
    assert expected - present == set()
    assert "codex_composer" in present and "codex" not in present
    assert "hermes-m5" in present and "hermes" not in present
    card = load_card_declared_routes(REPO_ROOT)["devin-roaming-2987d222"]
    assert card["inbox_subject"] == "dharma.a2a.devin"
    assert card["durable_consumer"] == "devin_inbox"
    devin = {a["agent_uid"]: a for a in load_registry()["agents"]}["devin-roaming-2987d222"]
    assert devin["declared_route"]["inbox_subject"] == "dharma.a2a.devin"
    assert devin["declared_route"]["durable_consumer"] == "devin_inbox"
    assert (devin.get("target_route") or {}).get("inbox_subject") == (
        "dharma.agent.devin-roaming-2987d222.inbox"
    )
    assert devin["canonical_inbox_subject"] == "dharma.a2a.devin"
    data = _reg()
    assert not any("extra identity" in e for e in _v(data))
    data["agents"][0]["identity_source"] = "card"
    assert any("runtime_observed_uncommitted" in e for e in _v(data))
    if expected:
        assert any("missing runtime-cell projection" in e for e in _v(_reg()))


def test_v2_schema_projection_renderer_and_check_mode():
    assert SCHEMA_V2 == load_registry()["schema"] == "dharma_fleet_field_registry.v2"
    comps = load_registry()["runtime_cell_contract"]["components"]
    assert set(comps) == set(RUNTIME_CELL_COMPONENTS) and len(comps) == 10
    data = load_registry()
    for agent in data["agents"]:
        uid, cell = agent["agent_uid"], agent.get("runtime_cell")
        assert isinstance(cell, dict) and isinstance(cell.get("components"), dict)
        for name in RUNTIME_CELL_COMPONENTS:
            c = cell["components"].get(name)
            assert isinstance(c, dict) and c.get("status"), f"{uid}:{name}"
        for field in ("transport_contact_tier", "semantic_effect_ceiling", "readiness_ceiling"):
            assert str(cell.get(field)) == str(agent.get(field)) != "None"
    table = render_table(data)
    assert "READY" not in table and "LIVE-SEMANTIC" not in table
    assert "unknown" in table.lower() and "agni" in table.lower()
    for agent in data["agents"]:
        assert agent["agent_uid"] in table
    proc = subprocess.run(
        [PY, str(CLI), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_cli_secret_shaped_invalid_registry_never_leaks(monkeypatch, capsys):
    data = copy.deepcopy(_reg())
    data["agents"][0]["runtime"] = JWT
    data["agents"][0]["agent_uid"] = API
    data["agents"][0]["runtime_cell"]["components"]["agent_uid"]["value"] = API
    monkeypatch.setattr(
        "scripts.runtime.fleet_field_registry.load_registry",
        lambda path=None: data,
    )
    assert ffr_main(["--json"]) == 2
    cap = capsys.readouterr()
    _no_leak(cap.out + cap.err, JWT, API, "sk-attacker")
    assert "Traceback" not in cap.err


def test_public_validate_registry_lazy_wrapper_matches_validation_module():
    """Negative-control surface: contract.validate_registry must work at call time."""
    data = _reg()
    data["password"] = "wrapper-secret-value"
    from scripts.runtime import fleet_field_registry_validation as val

    via_contract = validate_registry(data, repo_root=REPO_ROOT)
    via_module = val.validate_registry(data, repo_root=REPO_ROOT)
    assert via_contract == via_module
    assert any("secret-bearing key" in e for e in via_contract)
    _no_leak(via_contract, "wrapper-secret-value")
