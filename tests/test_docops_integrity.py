from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "docops" / "check_docops_integrity.py"
spec = importlib.util.spec_from_file_location("check_docops_integrity", SCRIPT_PATH)
docops = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["check_docops_integrity"] = docops
spec.loader.exec_module(docops)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def base_config(repo: Path) -> Path:
    config = {
        "version": 1,
        "verified_at": "2026-05-05",
        "ttl_days": 14,
        "assertions": [],
        "path_guards": {"include": [], "ignore_targets": ["http://*", "https://*"]},
        "canonical_guard": {
            "managed_include": [],
            "changed_include": ["**/*.md"],
            "ignore": [],
            "registered": [],
        },
        "auto_sections": {"include": []},
        "change_review": {"doc_include": []},
    }
    path = repo / "docs" / "docops" / "assertions.yaml"
    write(path, json.dumps(config, indent=2))
    return path


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def test_executable_assertion_passes_and_fails(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "dharma_swarm" / "a.py", "x = 1\n")
    write(repo / "docs" / "governance" / "SOVEREIGN_MANIFEST.md", "Total Python modules | **1** |\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["assertions"] = [
        {
            "id": "total-python",
            "doc": "docs/governance/SOVEREIGN_MANIFEST.md",
            "regex": r"Total Python modules \| \*\*(\d+)\*\*",
            "metric": "dharma_python_modules",
            "verify": "find dharma_swarm -name '*.py' -type f",
        }
    ]
    save_config(config_path, config)

    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    assert [finding for finding in findings if finding.severity == "FAIL"] == []

    write(repo / "dharma_swarm" / "b.py", "y = 2\n")
    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    assert any("doc says 1" in finding.message for finding in findings)


def test_path_guard_catches_missing_markdown_link_and_backticked_path(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "README.md", "See [missing](docs/missing.md) and `dharma_swarm/nope.py`.\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["path_guards"]["include"] = ["README.md"]
    save_config(config_path, config)

    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    messages = [finding.message for finding in findings]
    assert any("docs/missing.md" in message for message in messages)
    assert any("dharma_swarm/nope.py" in message for message in messages)


def test_canonical_guard_rejects_unregistered_authority_claim(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "docs" / "new.md", "This is the canonical source of truth.\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["canonical_guard"]["managed_include"] = ["docs/*.md"]
    save_config(config_path, config)

    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    assert any(finding.check == "canonical" for finding in findings)

    config["canonical_guard"]["registered"] = ["docs/new.md"]
    save_config(config_path, config)
    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    assert not any(finding.check == "canonical" for finding in findings)


def test_changed_canonical_guard_fails_added_and_modified_docs(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "docs" / "changed.md", "This is the canonical source of truth.\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["canonical_guard"]["changed_include"] = ["docs/*.md"]

    added_findings = docops.check_canonical_guard(
        repo, config, [("A", "docs/changed.md")]
    )
    assert any(
        finding.check == "canonical" and finding.severity == "FAIL"
        for finding in added_findings
    )

    modified_findings = docops.check_canonical_guard(
        repo, config, [("M", "docs/changed.md")]
    )
    assert any(
        finding.check == "canonical" and finding.severity == "FAIL"
        for finding in modified_findings
    )


def test_canonical_guard_ignores_archived_docs(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "docs" / "_archive" / "2026-04" / "old.md", "Historical source of truth.\n")
    write(repo / "docs" / "live.md", "Live source of truth.\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["canonical_guard"]["changed_include"] = ["docs/*.md", "docs/**/*.md"]
    config["canonical_guard"]["ignore"] = ["docs/_archive/**"]

    findings = docops.check_canonical_guard(
        repo,
        config,
        [
            ("A", "docs/_archive/2026-04/old.md"),
            ("A", "docs/live.md"),
        ],
    )

    messages = [finding.message for finding in findings]
    assert not any("docs/_archive/2026-04/old.md" in message for message in messages)
    assert any("docs/live.md" in message for message in messages)


def test_auto_section_update_writes_generated_inventory(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "dharma_swarm" / "a.py", "x = 1\n")
    write(
        repo / "docs" / "docops" / "AUTO_INVENTORY.md",
        "# Inventory\n\n<!-- DOCOPS:START metric=repo_inventory -->\nstale\n<!-- DOCOPS:END -->\n",
    )
    config_path = base_config(repo)
    config = load_config(config_path)
    config["auto_sections"]["include"] = ["docs/docops/AUTO_INVENTORY.md"]
    save_config(config_path, config)

    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), False)
    assert any(finding.check == "auto-section" for finding in findings)

    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-05-05"), True)
    assert not any(finding.check == "auto-section" for finding in findings)
    text = (repo / "docs" / "docops" / "AUTO_INVENTORY.md").read_text(encoding="utf-8")
    assert "| Dharma Python modules | 1 |" in text


def test_change_review_reports_docs_that_reference_changed_python(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "dharma_swarm" / "runner.py", "x = 1\n")
    write(repo / "docs" / "architecture" / "NAVIGATION.md", "See dharma_swarm/runner.py.\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["change_review"]["doc_include"] = ["docs/**/*.md"]
    save_config(config_path, config)

    findings = docops.doc_review_candidates(repo, config, ["dharma_swarm/runner.py"])
    assert any("NAVIGATION.md" in finding.message for finding in findings)
    assert all(finding.severity == "WARN" for finding in findings)


def test_staleness_ttl_expires(tmp_path: Path) -> None:
    repo = tmp_path
    config_path = base_config(repo)
    findings, _metrics = docops.run_checks(repo, config_path, None, docops.parse_iso_date("2026-06-01"), False)
    assert any(finding.check == "staleness" for finding in findings)


def test_report_json_writes_machine_readable_check_result(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "dharma_swarm" / "a.py", "x = 1\n")
    write(repo / "docs" / "governance" / "SOVEREIGN_MANIFEST.md", "Total Python modules | **1** |\n")
    config_path = base_config(repo)
    config = load_config(config_path)
    config["assertions"] = [
        {
            "id": "total-python",
            "doc": "docs/governance/SOVEREIGN_MANIFEST.md",
            "regex": r"Total Python modules \| \*\*(\d+)\*\*",
            "metric": "dharma_python_modules",
        }
    ]
    save_config(config_path, config)

    report_path = repo / "reports" / "docops.json"
    exit_code = docops.main(
        [
            "--repo-root",
            str(repo),
            "--assertions",
            str(config_path),
            "--today",
            "2026-05-05",
            "--report-json",
            str(report_path),
        ]
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["metrics"]["dharma_python_modules"] == 1


def test_inventory_reports_non_blocking_corpus_debt(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "docs" / "registered.md", "This is canonical for one narrow domain.\n")
    write(
        repo / "docs" / "loose.md",
        "---\nstatus: active\n---\nThis is the source of truth. See `/Users/dhyana/dharma_swarm/docs/missing.md`.\n",
    )
    config_path = base_config(repo)
    config = load_config(config_path)
    config["canonical_guard"]["registered"] = ["docs/registered.md"]
    save_config(config_path, config)

    inventory = docops.scan_doc_inventory(repo, config, ["docs/*.md"])
    assert inventory["markdown_files_scanned"] == 2
    assert inventory["unregistered_authority_doc_count"] == 1
    assert inventory["frontmatter_doc_count"] == 1
    assert inventory["absolute_path_ref_count"] == 1

    markdown = docops.render_inventory_markdown(inventory)
    assert "docs/loose.md" in markdown
    assert "Absolute Repo Path References" in markdown


def test_generated_docops_reports_are_ignored_by_metrics(tmp_path: Path) -> None:
    repo = tmp_path
    write(repo / "docs" / "note.md", "live doc\n")
    write(repo / "reports" / "docops" / "corpus_inventory.md", "generated doc\n")

    metrics = docops.collect_metrics(repo)
    assert metrics["markdown_files"] == 1
    assert metrics["markdown_total_lines"] == 1
