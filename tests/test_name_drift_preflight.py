"""Tests for scripts/governance/name_drift_preflight.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/governance/name_drift_preflight.py"

spec = importlib.util.spec_from_file_location("name_drift_preflight", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["name_drift_preflight"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_routes_name_drift_sources(tmp_path: Path) -> None:
    _write(tmp_path / "DE_BUG_CORRAL" / "00.md", "# index\n")
    _write(
        tmp_path / "INTERFACE_MISMATCH_MAP.md",
        "IMM-26 is a key-name contract drift between vendor env names.\n",
    )
    _write(
        tmp_path / "docs/governance/REPO_GOVERNANCE_AUDIT.md",
        "### P3: Naming Inconsistency\nbridge vs adapter vs connector all mean interface.\n",
    )
    _write(
        tmp_path / "docs/governance/ACTIVE_TRACK.yaml",
        "NameDriftPreflight requires semantic_objects and semantic_aliases.\n",
    )
    _write(
        tmp_path / "reports/governance/active_track_evidence.md",
        "name_drift_preflight_exists failed in generated track evidence.\n",
    )

    payload = mod.build_payload(tmp_path)
    routes = payload["by_route"]

    assert payload["corral_state"]["canonical_index_present"] is True
    assert routes["DE_BUG_CORRAL/01.md"] == 1
    assert routes["DE_BUG_CORRAL/03.md"] == 2
    assert routes["DE_BUG_CORRAL/04.md"] == 1
    assert routes["DE_BUG_CORRAL/07.md"] == 1


def test_detects_noncanonical_corral_path(tmp_path: Path) -> None:
    _write(tmp_path / "docs/bug-corral-arbiter" / "README.md", "Bug Corral packet\n")

    payload = mod.build_payload(tmp_path)
    corral = payload["corral_state"]

    assert corral["canonical_dir_present"] is False
    assert "docs/bug-corral-arbiter" in corral["noncanonical_paths"]


def test_ignores_stale_missing_claim_when_file_exists(tmp_path: Path) -> None:
    _write(tmp_path / "scripts/governance/name_drift_preflight.py", "# present\n")
    _write(
        tmp_path / "reports/governance/active_track_evidence.md",
        "- x scripts/governance/name_drift_preflight.py MISSING\n",
    )

    payload = mod.build_payload(tmp_path)

    assert payload["hit_count"] == 0


def test_writes_receipts(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    _write(repo / "docs/governance/ACTIVE_TRACK.yaml", "NameDriftPreflight\n")
    json_out = tmp_path / "out" / "scan.json"
    md_out = tmp_path / "out" / "scan.md"
    digest_out = tmp_path / "out" / "digest.json"

    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    rc = mod.main(
        [
            "--json-output",
            str(json_out),
            "--markdown-output",
            str(md_out),
            "--digest-output",
            str(digest_out),
            "--limit",
            "1",
        ]
    )

    assert rc == 0
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["hit_count"] == 1
    assert "Name Drift Preflight" in md_out.read_text(encoding="utf-8")
    digest = json.loads(digest_out.read_text(encoding="utf-8"))
    assert digest["schema_version"] == "name_drift_preflight_digest.v1"
    assert digest["hit_count"] == 1
    assert digest["status"] == "blocked"
    assert "canonical_corral_dir_missing" in digest["blockers"]
