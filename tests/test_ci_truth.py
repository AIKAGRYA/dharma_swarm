import json

import pytest

from scripts.runtime import ci_truth


def _contract():
    return {
        "schema": "dharma.ci_truth_contract.v1",
        "version": 1,
        "required": [
            {
                "id": "docops",
                "names": ["DocOps integrity gate"],
                "owner": "docops",
                "local_command": "make docops-integrity",
                "failure_category": "doc_drift",
                "autofix": "limited",
            }
        ],
        "advisory": [
            {
                "id": "tests",
                "names": ["pytest (3.11)", "pytest (3.12)"],
                "owner": "runtime",
                "local_command": "make test",
                "failure_category": "test_failure",
                "autofix": "manual",
            }
        ],
    }


def test_ci_truth_blocks_missing_required_check():
    result = ci_truth.evaluate_rollup([], _contract())

    assert result["verdict"] == "FAIL"
    assert result["required"][0]["status"] == "MISSING"
    assert "required CI docops is MISSING" in result["merge_blockers"][0]


def test_ci_truth_degrades_missing_advisory_check():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            }
        ],
        _contract(),
    )

    assert result["verdict"] == "DEGRADED"
    assert result["merge_blockers"] == []
    assert result["advisory"][0]["status"] == "MISSING"


def test_ci_truth_passes_latest_matching_required_and_advisory_checks():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "completedAt": "2026-06-05T00:00:00Z",
            },
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "completedAt": "2026-06-05T00:01:00Z",
            },
            {
                "name": "pytest (3.12)",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
        ],
        _contract(),
    )

    assert result["verdict"] == "PASS"
    assert result["required"][0]["status"] == "PASS"
    assert result["advisory"][0]["matched_name"] == "pytest (3.12)"
    assert result["raw_total"] == 3
    assert result["observed_total"] == 2


def test_ci_truth_records_uncontracted_checks_as_warnings():
    result = ci_truth.evaluate_rollup(
        [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "name": "pytest (3.11)",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "name": "surprise-check",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
        ],
        _contract(),
    )

    assert result["verdict"] == "PASS"
    assert result["unknown_checks"] == ["surprise-check"]
    assert any("uncontracted GitHub checks observed" in warning for warning in result["warnings"])


def test_default_ci_truth_required_set_equals_parity_manifest() -> None:
    contract = ci_truth.load_contract()
    manifest = ci_truth.load_json(ci_truth.DEFAULT_PARITY_MANIFEST_PATH)

    assert set(ci_truth.required_context_names(contract)) == set(
        ci_truth.manifest_required_context_names(manifest)
    )


def test_ci_truth_contract_fails_closed_when_required_set_drifts(tmp_path) -> None:
    contract = json.loads(ci_truth.DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(
        ci_truth.DEFAULT_PARITY_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    manifest["required_contexts"] = manifest["required_contexts"][:-1]
    manifest_path = tmp_path / "parity.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    contract["required_contexts_manifest"] = str(manifest_path)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ci_truth.CITruthError, match="disagree"):
        ci_truth.load_contract(contract_path)


def test_ci_truth_contract_requires_parity_manifest_binding(tmp_path) -> None:
    """Deleting the manifest binding must fail closed, not skip the parity check."""
    contract = json.loads(ci_truth.DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    for absent in (None, ""):
        contract["required_contexts_manifest"] = absent
        if absent is None:
            contract.pop("required_contexts_manifest")
        contract_path = tmp_path / "contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        with pytest.raises(ci_truth.CITruthError, match="required_contexts_manifest"):
            ci_truth.load_contract(contract_path)


# ── WP-0F1 (TIT-006/TIT-007): duplicate-key rejection + real local commands ──


def test_duplicate_top_level_json_key_is_rejected(tmp_path) -> None:
    """A duplicate top-level key must raise before decoding can erase evidence."""
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        '{"schema": "dharma.ci_truth_contract.v1", "advisory": [], "advisory": []}',
        encoding="utf-8",
    )
    with pytest.raises(ci_truth.CITruthError, match="duplicate JSON key 'advisory'"):
        ci_truth.load_json(contract_path)


def test_duplicate_nested_json_key_is_rejected(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        '{"required": [{"id": "x", "id": "y"}]}', encoding="utf-8"
    )
    with pytest.raises(ci_truth.CITruthError, match="duplicate JSON key 'id'"):
        ci_truth.load_json(contract_path)


def test_committed_contract_keeps_pytest_and_gitleaks_after_parsing() -> None:
    contract = ci_truth.load_contract()
    names = {name for entry in contract["required"] for name in entry["names"]}
    assert "pytest (3.11)" in names
    assert "pytest (3.12)" in names
    assert "gitleaks" in names


def test_every_local_command_resolves_to_a_real_command_surface() -> None:
    """No phantom repro commands (WP-0F1: `make frontend-check` was cited
    before any such target existed). Make targets must exist in the real
    Makefile, repo script paths must exist, and only allowlisted external
    binaries may anchor a command."""
    from pathlib import Path

    repo_root = Path(ci_truth.REPO_ROOT)
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    known_binaries = {"gh", "git", "npm", "python3"}
    # The one sanctioned absolute path: Apple's system make 3.81, which is
    # the exact interpreter the macOS-compatibility check exercises (pinned
    # by tests/test_onboarding_ci_contract.py, the owning contract).
    absolute_path_exceptions = {"/usr/bin/make"}
    contract = ci_truth.load_contract()
    for group in ("required", "advisory"):
        for entry in contract[group]:
            for part in str(entry["local_command"]).split("&&"):
                tokens = part.strip().split()
                assert tokens, f"{entry['id']}: empty command segment"
                head = tokens[0]
                if head in absolute_path_exceptions:
                    head = head.rsplit("/", 1)[-1]
                assert not head.startswith("/"), (
                    f"{entry['id']}: author-machine absolute path {head!r}"
                )
                if head == "make":
                    target = tokens[1]
                    assert f"\n{target}:" in makefile or makefile.startswith(
                        f"{target}:"
                    ), f"{entry['id']}: phantom make target {target!r}"
                elif head == "python3" and tokens[1].startswith("scripts/"):
                    assert (repo_root / tokens[1]).is_file(), (
                        f"{entry['id']}: missing script {tokens[1]!r}"
                    )
                else:
                    assert head in known_binaries, (
                        f"{entry['id']}: unrecognized command head {head!r}"
                    )
