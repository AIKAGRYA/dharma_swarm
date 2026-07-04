from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


naga_citation = _load(
    "naga_citation_check",
    REPO_ROOT / "scripts/governance/naga_citation_check.py",
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mini.md"
    path.write_text(text, encoding="utf-8")
    return path


def _fetcher(mapping):
    def fake(url: str, timeout: float):
        result = mapping[url]
        if isinstance(result, naga_citation.FetchResult):
            return result
        return naga_citation.FetchResult(True, 200, url, result)

    return fake


def test_live_supportive_url_passes(tmp_path):
    path = _write(
        tmp_path,
        """# Mini

## Citation

MLIR verification dialects provide first-class verification support. [confidence: 90/100] [MLIR verification](https://example.test/mlir)
""",
    )

    assert naga_citation.main([str(path)], fetcher=_fetcher({"https://example.test/mlir": "MLIR verification dialects support first-class verification."})) == 0


def test_dead_url_flagged(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Citation

Viper verifier evidence can support proof receipts. [confidence: 90/100] [Viper](https://example.test/dead)
""",
    )
    fetcher = _fetcher({"https://example.test/dead": naga_citation.FetchResult(False, 404, "https://example.test/dead", "", "HTTP 404")})

    assert naga_citation.main([str(path)], fetcher=fetcher) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "NAGA-CITE-DEAD" in out


def test_offtopic_url_flagged(tmp_path, capsys):
    path = _write(
        tmp_path,
        """# Mini

## Citation

Nagini verifier output can lift into Proven_by evidence. [confidence: 90/100] [Nagini](https://example.test/nagini)
""",
    )
    fetcher = _fetcher({"https://example.test/nagini": "Sourdough bread recipe with flour, water, salt, and oven timing."})

    assert naga_citation.main([str(path)], fetcher=fetcher) == 1
    out = capsys.readouterr().out
    assert "mini.md:5" in out
    assert "NAGA-CITE-OFFTOPIC" in out


def test_no_citations_passes(tmp_path):
    path = _write(
        tmp_path,
        """# Mini

## No Citation

MiniSpec defines an internal placeholder. [confidence: 90/100]
""",
    )

    assert naga_citation.main([str(path)], fetcher=_fetcher({})) == 0
