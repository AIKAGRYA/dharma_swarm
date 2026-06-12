from __future__ import annotations

from pathlib import Path

from scripts.governance.check_module_coherence import analyze_module_coherence


def test_module_coherence_skips_generated_dirs(tmp_path: Path) -> None:
    package = tmp_path / "dharma_swarm"
    package.mkdir()
    (package / "bridge.py").write_text("VALUE = 1\n", encoding="utf-8")

    generated = tmp_path / "reports" / "generated"
    generated.mkdir(parents=True)
    (generated / "bridge.py").write_text("VALUE = 2\n", encoding="utf-8")

    report = analyze_module_coherence(tmp_path)

    assert report.ok
    assert report.scanned_files == 1
    assert report.family_counts["bridge"] == 1


def test_module_coherence_allows_same_module_stem_in_different_packages(tmp_path: Path) -> None:
    package_a = tmp_path / "dharma_swarm" / "pkg_a"
    package_b = tmp_path / "dharma_swarm" / "pkg_b"
    package_a.mkdir(parents=True)
    package_b.mkdir(parents=True)
    (package_a / "router.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package_b / "router.py").write_text("VALUE = 2\n", encoding="utf-8")

    report = analyze_module_coherence(tmp_path)

    assert report.ok
    assert report.scanned_files == 2
    assert report.family_counts["router"] == 2
    assert report.duplicate_modules_same_package == []
