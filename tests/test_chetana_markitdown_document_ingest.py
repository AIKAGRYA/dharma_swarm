import importlib
import os

from dharma_swarm.chetana.provenance import parse_frontmatter


ingest_module = importlib.import_module("dharma_swarm.chetana.ingest")
staging_module = importlib.import_module("dharma_swarm.chetana.staging")


def test_document_ingest_routes_through_markitdown(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    markitdown = bin_dir / "markitdown"
    markitdown.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('# Converted seed')\n"
        "print()\n"
        "print('source=' + sys.argv[1])\n",
        encoding="utf-8",
    )
    markitdown.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setattr(staging_module, "STAGING_ROOT", tmp_path / "staging")
    monkeypatch.setattr(ingest_module, "emit_mark", lambda **_kwargs: None)
    monkeypatch.setattr(ingest_module, "append_wiki_log", lambda **_kwargs: None)

    source = tmp_path / "world-signal.docx"
    source.write_text("opaque office payload", encoding="utf-8")

    result = ingest_module.ingest(
        source=source,
        source_kind="document",
        title="World Signal Seed",
        tags=["world-signal", "markitdown"],
        captured_by="test",
    )

    assert result.staged_count == 1
    atom_text = result.atoms[0].read_text(encoding="utf-8")
    schema, body = parse_frontmatter(atom_text, source_path=str(result.atoms[0]))
    assert schema.source[0].kind == "document"
    assert schema.source[0].path == str(source)
    assert schema.tags == ["world-signal", "markitdown"]
    assert "# Converted seed" in body
    assert f"source={source}" in body
