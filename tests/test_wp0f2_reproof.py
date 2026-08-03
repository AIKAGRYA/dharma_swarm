"""Offline exercises of the WP-0F2 reproof harness itself."""

import json
from pathlib import Path

from scripts.governance import wp0f2_reproof as harness
from scripts.runtime import ci_truth

REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest_contexts() -> list[str]:
    manifest = json.loads((REPO_ROOT / harness.MANIFEST_REL).read_text(encoding="utf-8"))
    return [row["context"] for row in manifest["required_contexts"]]


def test_offline_run_has_no_failures():
    results = harness.run_all(REPO_ROOT, contexts=None, offline=True)
    failures = [r for r in results if r["status"] == "FAIL"]
    assert not failures, failures
    names = {r["name"] for r in results}
    assert {"manifest_shape", "contract_manifest_parity", "rollup_green",
            "rollup_missing", "rollup_pending", "loop_watcher_required",
            "parity_guard_workflows"} <= names
    network = [r for r in results if r["name"] == "parity_guard_live"]
    assert network and network[0]["status"] == "SKIP"


def test_synthetic_rollup_fixtures_drive_evaluate_rollup():
    contexts = _manifest_contexts()
    contract = ci_truth.load_contract(REPO_ROOT / harness.CONTRACT_REL)
    green = ci_truth.evaluate_rollup(harness.synthetic_rollup(contexts), contract)
    assert green["merge_blockers"] == []
    assert all(r["status"] == "PASS" for r in green["required"])
    missing = ci_truth.evaluate_rollup(
        harness.synthetic_rollup(contexts, drop=contexts[0]), contract)
    assert missing["verdict"] == "FAIL"
    assert any("MISSING" in b for b in missing["merge_blockers"])
    pending = ci_truth.evaluate_rollup(
        harness.synthetic_rollup(contexts, pending=contexts[0]), contract)
    assert pending["verdict"] == "FAIL"
    assert any("PENDING" in b for b in pending["merge_blockers"])


def test_contexts_override_mismatch_fails():
    results = harness.run_all(REPO_ROOT, contexts=["bogus-context"], offline=True)
    failing = {r["name"] for r in results if r["status"] == "FAIL"}
    assert "contract_manifest_parity" in failing
    assert "ratified_vs_manifest" in failing


def test_jq_program_extraction():
    text = (REPO_ROOT / harness.AUTOMERGE_REL).read_text(encoding="utf-8")
    program = harness.extract_automerge_jq(text)
    assert "ci-parity-guard/v1" in program
    assert "unique" in program


def test_main_offline_exit_zero(capsys):
    rc = harness.main(["--offline", "--repo-root", str(REPO_ROOT)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "VERDICT: PASS" in out


def test_main_offline_json_contract(capsys):
    rc = harness.main(["--offline", "--repo-root", str(REPO_ROOT), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["schema"] == "dharma.wp0f2_reproof.v1"
    assert payload["verdict"] == "PASS"
