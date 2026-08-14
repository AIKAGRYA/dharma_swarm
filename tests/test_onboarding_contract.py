from __future__ import annotations

import ast
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

from dharma_swarm.memory_kernel.write_receipts import stable_digest
from dharma_swarm.operator_core.onboarding import receipt
from dharma_swarm.operator_core.onboarding.contract import (
    canonical_first_read_manifest,
    detect_surface_collisions,
    resolve_external_dir,
)
from dharma_swarm.operator_core.onboarding.models import (
    ConfigError,
    ReceiptValidationError,
    UnsupportedReceiptSchema,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_FIRST_READ = (
    ("command", "make onboard"),
    ("file", "CLAUDE.md"),
    ("file", "docs/governance/SWARM_GENOME.md"),
    ("file", "docs/governance/ACTIVE_TRACK.yaml"),
    ("file", "docs/governance/ANTI_SLOP_RULES.md"),
)


def test_onboarding_imports_without_optional_tui_deps() -> None:
    probe = """
import importlib.abc
import importlib
import sys

sys.dont_write_bytecode = True

class BlockTextual(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "textual" or fullname.startswith("textual."):
            raise ModuleNotFoundError(
                "blocked optional dependency: textual", name=fullname
            )
        return None

sys.meta_path.insert(0, BlockTextual())
operator_core = importlib.import_module("dharma_swarm.operator_core")
assert set(operator_core.__all__) == set(operator_core._EXPORT_MODULES)
lazy_modules = {
    f"{operator_core.__name__}.{module_name}"
    for module_name in operator_core._EXPORT_MODULES.values()
}
assert lazy_modules.isdisjoint(sys.modules)
importlib.import_module("dharma_swarm.operator_core.onboarding")
assert lazy_modules.isdisjoint(sys.modules)

import pytest
raise SystemExit(
    pytest.main([
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_onboarding_contract.py",
    ])
)
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _valid_v1() -> dict[str, Any]:
    return {
        "schema": "dharma_swarm.onboard_receipt.v1",
        "observed_at": "2026-07-10T00:00:00Z",
        "authority": "projection_only",
        "repo": {},
        "work_lanes": {},
        "portfolio": {},
        "next_items": [],
        "swarm_bulletins": [],
        "broken_register": {},
        "open_prs": [],
        "runtime_truth_packets": [],
    }


def _stable_core() -> dict[str, Any]:
    return {
        "repository": {
            "identity": "AIKAGRYA/dharma_swarm",
            "head": "1" * 40,
            "branch": "test/onboarding-contract",
        },
        "contract": {
            "required_files": ["CLAUDE.md"],
            "source_hashes": {"CLAUDE.md": "2" * 64},
            "contract_digest": "3" * 64,
        },
        "packet": {
            "id": "session-entry-test-WP-T1",
            "digest": "4" * 64,
            "track": "session-entry-test-track",
            "owner": "@AmitabhainArunachala",
            "allowed_files": ["tests/test_onboarding_contract.py"],
            "forbidden_files": ["pyproject.toml"],
        },
        "portfolio": {
            "tracks": ["session-entry-test-track"],
            "selected_track": "session-entry-test-track",
            "ownership_conflicts": [],
        },
        "orientation": {
            "identity": {},
            "broken_register": {},
            "static_surfaces": {},
        },
        "required_reading": [],
    }


def _valid_v2() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "dharma_swarm.onboard_receipt.v2",
        "authority": "projection_only",
        "observed_at": "2026-07-10T00:00:00Z",
        "primary_verdict": "BLOCKED",
        "exit_code": 1,
        "stable_core": _stable_core(),
        "live_delta": {
            "repo_state": {
                "base": "main",
                "dirty": False,
                "conflicted": False,
                "ahead": 0,
                "behind": 0,
            },
            "conditions": [],
            "host_gaps": [],
            "toolchain": {},
            "projection_freshness": {},
        },
        "cache": {
            "key": "",
            "hit": False,
            "miss_reasons": [],
            "input_manifest": {},
            "section_fingerprints": {},
        },
        "delta": {
            "previous_stable_digest": "",
            "added": [],
            "resolved": [],
            "changed": [],
        },
        "legacy_v1": {
            "schema": "",
            "observed_at": "",
            "authority": "",
            "repo": {},
            "work_lanes": {},
            "portfolio": {},
            "next_items": [],
            "swarm_bulletins": [],
            "broken_register": {},
            "open_prs": [],
            "runtime_truth_packets": [],
        },
        "extensions": {},
        "stable_digest": "",
    }
    payload["stable_digest"] = receipt.compute_stable_digest(payload["stable_core"])
    return payload


def _assert_load_fails(
    path: Path,
    payload: Any,
    error: type[Exception] = ReceiptValidationError,
) -> None:
    _write_json(path, payload)
    with pytest.raises(error):
        receipt.load_receipt(path)


def test_canonical_first_read_manifest_matches_doc_stack(tmp_path: Path) -> None:
    owner_contents = {
        "CLAUDE.md": "# Contract\n",
        "docs/governance/SWARM_GENOME.md": "# Genome\n",
        "docs/governance/ACTIVE_TRACK.yaml": "schema_version: 2\n",
        "docs/governance/ANTI_SLOP_RULES.md": "# Anti-slop\n",
    }
    for relative, content in owner_contents.items():
        _write(tmp_path / relative, content)

    manifest = canonical_first_read_manifest(tmp_path)

    assert [(entry["kind"], entry["source"]) for entry in manifest] == list(
        CANONICAL_FIRST_READ
    )
    assert len(manifest) == 5
    assert manifest[0]["sha256"] == stable_digest("make onboard")
    for entry in manifest[1:]:
        expected = stable_digest((tmp_path / entry["source"]).read_text(encoding="utf-8"))
        assert entry["sha256"] == expected
        assert HEX_64.fullmatch(entry["sha256"])

    before = {entry["source"]: entry["sha256"] for entry in manifest}
    _write(tmp_path / "docs/governance/SWARM_GENOME.md", "# Genome changed\n")
    after = {
        entry["source"]: entry["sha256"]
        for entry in canonical_first_read_manifest(tmp_path)
    }
    assert {
        source for source in before if before[source] != after[source]
    } == {"docs/governance/SWARM_GENOME.md"}

    (tmp_path / "CLAUDE.md").unlink()
    with pytest.raises(ConfigError, match="CLAUDE.md"):
        canonical_first_read_manifest(tmp_path)


def test_receipt_v1_v2_compatibility_matrix(tmp_path: Path) -> None:
    v1 = _valid_v1()
    v2 = _valid_v2()

    loaded_v1 = receipt.load_receipt(_write_json(tmp_path / "v1.json", v1))
    assert loaded_v1.major == 1
    assert loaded_v1.admission_eligible is False
    assert loaded_v1.payload == v1

    loaded_v2 = receipt.load_receipt(_write_json(tmp_path / "v2.json", v2))
    assert loaded_v2.major == 2
    assert loaded_v2.payload == v2

    _assert_load_fails(tmp_path / "missing-schema.json", {})
    _assert_load_fails(tmp_path / "non-object.json", [])
    _assert_load_fails(
        tmp_path / "future.json",
        {"schema": "dharma_swarm.onboard_receipt.v3"},
        UnsupportedReceiptSchema,
    )
    _assert_load_fails(
        tmp_path / "malformed-schema.json",
        {"schema": "dharma_swarm.onboard_receipt.v2.1"},
    )

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text('{"schema":', encoding="utf-8")
    with pytest.raises(ReceiptValidationError):
        receipt.load_receipt(corrupt)

    v1_missing = copy.deepcopy(v1)
    del v1_missing["repo"]
    _assert_load_fails(tmp_path / "v1-missing.json", v1_missing)
    v1_unknown = copy.deepcopy(v1)
    v1_unknown["future_field"] = {}
    _assert_load_fails(tmp_path / "v1-unknown.json", v1_unknown)

    v2_bad_digest = copy.deepcopy(v2)
    v2_bad_digest["stable_digest"] = "f" * 64
    _assert_load_fails(tmp_path / "v2-bad-digest.json", v2_bad_digest)
    v2_unknown = copy.deepcopy(v2)
    v2_unknown["future_field"] = {}
    _assert_load_fails(tmp_path / "v2-unknown.json", v2_unknown)

    invalid_timestamps: tuple[object, ...] = (
        "definitely-not-ISO-8601Z",
        "2026-07-10 00:00:00Z",
        "2026-07-10T00:00:00+00:00",
        "2026-02-30T00:00:00Z",
        "2026-07-10T24:00:00Z",
        None,
    )
    for major, valid in (("v1", v1), ("v2", v2)):
        fractional = copy.deepcopy(valid)
        fractional["observed_at"] = "2026-07-10T00:00:00.123456Z"
        receipt.load_receipt(
            _write_json(tmp_path / f"{major}-fractional-timestamp.json", fractional)
        )
        for index, invalid in enumerate(invalid_timestamps):
            bad_timestamp = copy.deepcopy(valid)
            bad_timestamp["observed_at"] = invalid
            _assert_load_fails(
                tmp_path / f"{major}-bad-timestamp-{index}.json",
                bad_timestamp,
            )

    # The compatibility shim keeps the legacy v1 helper isolated from the
    # source-controlled v2 writer default.
    writer_source = (REPO_ROOT / "scripts/governance/agent_onboard.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(writer_source)
    writer = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_receipt_payload"
    )
    string_constants = {
        node.value
        for node in ast.walk(writer)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "dharma_swarm.onboard_receipt.v1" in string_constants
    assert "dharma_swarm.onboard_receipt.v2" not in string_constants


def test_timestamp_live_delta_and_previous_digest_do_not_change_stable_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _valid_v2()
    baseline_digest = baseline["stable_digest"]
    assert baseline_digest == stable_digest(baseline["stable_core"])

    mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda row: row.__setitem__("observed_at", "2099-01-01T00:00:00Z"),
        lambda row: row["live_delta"]["conditions"].append(
            {"id": "live-only", "state": "warn", "reason": "fixture"}
        ),
        lambda row: row["cache"].update(
            {"hit": True, "miss_reasons": ["different-run"]}
        ),
        lambda row: row["delta"].update(
            {"previous_stable_digest": "a" * 64, "added": ["new-condition"]}
        ),
    )
    for index, mutate in enumerate(mutations):
        candidate = copy.deepcopy(baseline)
        mutate(candidate)
        assert receipt.compute_stable_digest(candidate["stable_core"]) == baseline_digest
        loaded = receipt.load_receipt(
            _write_json(tmp_path / f"volatile-{index}.json", candidate)
        )
        assert loaded.payload["stable_digest"] == baseline_digest

    # Key names are not recursively volatile. If they occur inside stable_core,
    # they are stable contract data and must alter the digest.
    stable_change = copy.deepcopy(baseline)
    stable_change["stable_core"]["orientation"]["identity"]["observed_at"] = (
        "2099-01-01T00:00:00Z"
    )
    assert receipt.compute_stable_digest(stable_change["stable_core"]) != baseline_digest
    _assert_load_fails(tmp_path / "stable-change.json", stable_change)

    calls: list[object] = []

    def mandated_primitive(payload: object) -> str:
        calls.append(payload)
        return "primitive-was-used"

    monkeypatch.setattr(receipt, "stable_digest", mandated_primitive)
    assert receipt.compute_stable_digest(baseline["stable_core"]) == "primitive-was-used"
    assert calls == [baseline["stable_core"]]


def test_stable_core_repository_shape_remains_exact() -> None:
    from dharma_swarm.operator_core.onboarding import evidence

    repository = evidence.collect_stable_core()["repository"]
    assert set(repository) == {"identity", "head", "branch"}
    assert repository["identity"] == "AIKAGRYA/dharma_swarm"


def test_ops_dir_inside_repo_and_symlink_escape_are_config_error(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    external = tmp_path / "external"
    external.mkdir()

    missing_external_child = external / "not-created-yet"
    assert resolve_external_dir(
        missing_external_child, repo_root=repo_root
    ) == missing_external_child.resolve()
    assert not missing_external_child.exists()

    direct_forbidden = (
        repo_root,
        repo_root / "ops",
        repo_root / ".git",
        repo_root / ".git" / "ops",
    )
    for candidate in direct_forbidden:
        with pytest.raises(ConfigError):
            resolve_external_dir(candidate, repo_root=repo_root)

    outside_link_into_repo = external / "into-repo"
    outside_link_into_repo.symlink_to(repo_root, target_is_directory=True)
    with pytest.raises(ConfigError):
        resolve_external_dir(outside_link_into_repo / "ops", repo_root=repo_root)

    outside_link_into_git = external / "into-git"
    outside_link_into_git.symlink_to(repo_root / ".git", target_is_directory=True)
    with pytest.raises(ConfigError):
        resolve_external_dir(outside_link_into_git / "ops", repo_root=repo_root)

    inside_link_out = repo_root / "outside"
    inside_link_out.symlink_to(external, target_is_directory=True)
    with pytest.raises(ConfigError):
        resolve_external_dir(inside_link_out / "ops", repo_root=repo_root)


def test_glob_intersection_requires_a_concrete_shared_witness() -> None:
    disjoint = (
        ("src/a*.py", "src/b*.py"),
        ("docs/foo-*.md", "docs/bar-*.md"),
        ("pkg/[a].py", "pkg/[b].py"),
        ("services/*/config.toml", "tests/*/config.toml"),
    )
    for allowed, sibling in disjoint:
        assert detect_surface_collisions(
            [allowed], {"sibling": [sibling]}, []
        ) == []

    intersecting = (
        ("docs/**/test_*.py", "docs/governance/**/*.py"),
        ("src", "*/src"),
        ("src/**", "**/src"),
        ("**", "src/**"),
    )
    for allowed, sibling in intersecting:
        collisions = detect_surface_collisions(
            [allowed], {"sibling": [sibling]}, []
        )
        assert {row["kind"] for row in collisions} == {"glob_intersection"}


def test_receipt_extensions_are_versioned_and_nonadmission(tmp_path: Path) -> None:
    baseline = _valid_v2()
    baseline_loaded = receipt.load_receipt(
        _write_json(tmp_path / "baseline.json", baseline)
    )

    extended = copy.deepcopy(baseline)
    extended["extensions"] = {
        "vendor_probe": {
            "schema": "dharma_swarm.vendor_probe.v1",
            "primary_verdict": "READY",
            "exit_code": 0,
            "stable_core": {"forged": True},
            "payload": {"observation": "opaque auxiliary evidence"},
        }
    }
    loaded = receipt.load_receipt(_write_json(tmp_path / "extended.json", extended))
    assert loaded.payload["extensions"] == extended["extensions"]
    assert loaded.payload["primary_verdict"] == "BLOCKED"
    assert loaded.payload["exit_code"] == 1
    assert loaded.payload["stable_digest"] == baseline["stable_digest"]
    assert loaded.admission_eligible == baseline_loaded.admission_eligible

    changed_extension = copy.deepcopy(extended)
    changed_extension["extensions"]["vendor_probe"]["payload"] = {
        "observation": "different but still opaque"
    }
    assert receipt.compute_stable_digest(
        changed_extension["stable_core"]
    ) == baseline["stable_digest"]
    receipt.load_receipt(
        _write_json(tmp_path / "changed-extension.json", changed_extension)
    )

    unversioned = copy.deepcopy(baseline)
    unversioned["extensions"] = {"vendor_probe": {"payload": {}}}
    _assert_load_fails(tmp_path / "unversioned-extension.json", unversioned)

    wrong_schema_type = copy.deepcopy(baseline)
    wrong_schema_type["extensions"] = {"vendor_probe": {"schema": 1}}
    _assert_load_fails(tmp_path / "wrong-extension-schema.json", wrong_schema_type)

    unknown_root = copy.deepcopy(baseline)
    unknown_root["vendor_probe"] = {
        "schema": "dharma_swarm.vendor_probe.v1",
        "payload": {},
    }
    _assert_load_fails(tmp_path / "unknown-root.json", unknown_root)
