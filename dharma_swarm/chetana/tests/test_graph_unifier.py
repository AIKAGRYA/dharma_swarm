"""Tests for chetana.graph_unifier — unified query interface across 4 graphs."""

from __future__ import annotations

import json

from dharma_swarm.chetana import graph_unifier as gu_mod
from dharma_swarm.chetana import staging as staging_mod
from dharma_swarm.chetana.graph_unifier import _query_wiki, coverage_summary, query
from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote


def _build_multitier_wiki(root):
    """Populate a sandboxed wiki root with a multi-tier tree for _query_wiki.

    Every file matches the needle "needle". concepts/ gets more matches than the
    default per-tier limit so the round-robin / anti-starvation behavior is
    exercised; the smaller tiers get a single match each.
    """
    concepts = root / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    for i in range(8):
        (concepts / f"concept-{i}.md").write_text(
            f"# Concept {i}\n\nThis page mentions the needle token.", encoding="utf-8"
        )
    for tier in ("atoms", "mocs", "inter_agent", "connections"):
        d = root / tier
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{tier}-page.md").write_text(
            f"# {tier} page\n\nThis page mentions the needle token.", encoding="utf-8"
        )
    # Root-level uncurated scratch (a co-equal-looking peer in older code).
    (root / "operator-scratch.md").write_text(
        "# Scratch\n\nThis root scratch mentions the needle token.", encoding="utf-8"
    )
    # Generated aggregates that substring-match nearly everything — must never
    # surface as content hits.
    (root / "index.md").write_text(
        "# Index\n\nneedle " * 100, encoding="utf-8"
    )
    (root / "log.md").write_text(
        "# Log\n\nneedle entry\n" * 100, encoding="utf-8"
    )
    (root / "contradictions.md").write_text(
        "# Contradictions\n\nneedle contradiction\n", encoding="utf-8"
    )


def test_query_against_empty_catalytic_returns_no_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", tmp_path / "missing.json", raising=True)
    result = query("strange loop", sources=["catalytic"])
    assert result.coverage["catalytic"] == 0
    assert any("missing" in n for n in result.notes)


def test_query_finds_node_in_catalytic_graph(tmp_path, monkeypatch):
    cat_file = tmp_path / "catalytic_graph.json"
    cat_file.write_text(
        json.dumps(
            {
                "nodes": {
                    "strange-loop": {"label": "Strange Loop (Hofstadter)", "weight": 0.9},
                    "telos-gradient": {"label": "Telos Gradient", "weight": 0.7},
                    "rv-paper": {"label": "R_V Paper", "weight": 1.0},
                },
                "edges": [],
            }
        )
    )
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", cat_file, raising=True)
    result = query("strange loop", sources=["catalytic"])
    assert result.coverage["catalytic"] >= 1
    hits = result.by_source("catalytic")
    assert any("Strange Loop" in h.label for h in hits)


def test_query_finds_promoted_wiki_atom(chetana_sandbox):
    ingested = ingest(
        source="A wiki-native strange loop page for direct markdown search.",
        source_kind="note",
        title="Wiki Search Atom",
        confidence=0.8,
    )
    promote(staged_path=ingested.atoms[0], promoted_by="graph-test")

    result = query("strange loop", sources=["wiki"])
    assert result.coverage["wiki"] == 1
    assert result.by_source("wiki")[0].label == "Wiki Search Atom"


def test_query_missing_backends_dont_break(tmp_path, monkeypatch):
    """Memory + contextplus require an MCP client; graph_unifier should not crash."""
    monkeypatch.setattr(gu_mod, "CATALYTIC_GRAPH_PATH", tmp_path / "missing.json", raising=True)
    result = query("anything", sources=["memory", "contextplus", "gitnexus"])
    # All three either produce 0 hits with notes, or some hits — no exceptions.
    assert isinstance(result.coverage, dict)
    assert all(v >= 0 for v in result.coverage.values())


def test_query_gitnexus_parses_modern_query_json(monkeypatch):
    """gitnexus 1.6 dropped `search --json`; the unifier must use `query`."""

    class _Proc:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["which", "gitnexus"]:
            return _Proc(stdout="/usr/local/bin/gitnexus\n")
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(stdout="/Users/dhyana/dharma_swarm\n")
        if cmd[:2] == ["gitnexus", "query"]:
            payload = {
                "processes": [],
                "process_symbols": [],
                "definitions": [
                    {
                        "id": "SwarmManager",
                        "name": "SwarmManager",
                        "kind": "Class",
                    }
                ],
            }
            return _Proc(
                stdout='{"level":40,"msg":"log"}\n' + json.dumps(payload, indent=2)
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(gu_mod.subprocess, "run", fake_run)
    hits, note = gu_mod._query_gitnexus("SwarmManager", limit=5)
    assert note is None
    assert len(hits) == 1
    assert hits[0].label == "SwarmManager"
    assert hits[0].kind == "Class"
    query_cmds = [c for c in calls if c[:2] == ["gitnexus", "query"]]
    assert query_cmds, calls
    assert "--repo" in query_cmds[0]
    assert "search" not in query_cmds[0]


def test_coverage_summary_renders():
    from dharma_swarm.chetana.graph_unifier import UnifiedQueryResult, GraphHit

    result = UnifiedQueryResult(query="x")
    result.coverage = {"catalytic": 2, "memory": 0}
    result.hits = [
        GraphHit(source="catalytic", kind="node", id="a", label="A"),
        GraphHit(source="catalytic", kind="node", id="b", label="B"),
    ]
    text = coverage_summary(result)
    assert "Unified graph query" in text
    assert "catalytic: 2" in text


def test_wiki_multitier_anti_starvation(chetana_sandbox):
    """concepts/ with >limit matches must not starve the smaller tiers."""
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    hits, note = _query_wiki("needle", limit=5)
    assert note is None
    tiers = {h.id.split("/")[0] if "/" in h.id else "<root>" for h in hits}
    # The round-1 starvation bug surfaced only concepts; at least one smaller
    # curated tier must appear within the limit.
    assert tiers & {"atoms", "mocs", "inter_agent", "connections"}


def test_wiki_round_robin_interleaving(chetana_sandbox):
    """No single tier may occupy the first N consecutive slots when others match."""
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    hits, _ = _query_wiki("needle", limit=6)
    first_tiers = [h.id.split("/")[0] for h in hits[:5] if "/" in h.id]
    # concepts/ has 8 matches but must not monopolize the first 5 slots.
    assert first_tiers.count("concepts") < 5


def test_wiki_aggregate_files_never_returned(chetana_sandbox):
    """index.md / log.md / contradictions.md substring-match but must be excluded."""
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    hits, _ = _query_wiki("needle", limit=50)
    ids = {h.id for h in hits}
    assert "index.md" not in ids
    assert "log.md" not in ids
    assert "contradictions.md" not in ids


def test_wiki_root_scratch_drained_last(chetana_sandbox):
    """Uncurated root-level files rank below curated tiers."""
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    # With limit small enough that curated tiers fill it, root scratch is absent.
    hits, _ = _query_wiki("needle", limit=6)
    assert "operator-scratch.md" not in {h.id for h in hits}
    # With a large limit, it appears but only after curated hits.
    hits_all, _ = _query_wiki("needle", limit=50)
    ids = [h.id for h in hits_all]
    assert "operator-scratch.md" in ids
    scratch_pos = ids.index("operator-scratch.md")
    curated_after = [i for i in ids[scratch_pos + 1 :] if "/" in i]
    assert not curated_after  # nothing curated comes after the root tail


def test_wiki_empty_and_whitespace_query(chetana_sandbox):
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    assert _query_wiki("", limit=5) == ([], "empty query")
    assert _query_wiki("   \t  ", limit=5) == ([], "empty query")


def test_wiki_non_string_query(chetana_sandbox):
    assert _query_wiki(123, limit=5) == ([], "non-string query")  # type: ignore[arg-type]


def test_wiki_non_positive_limit(chetana_sandbox):
    hits, note = _query_wiki("needle", limit=0)
    assert hits == []
    assert note is not None and "positive" in note
    hits, note = _query_wiki("needle", limit=-3)
    assert hits == []
    assert note is not None and "positive" in note


def test_wiki_non_utf8_file_does_not_crash(chetana_sandbox):
    """A non-utf8 .md in one tier must not crash; other tiers still return."""
    _build_multitier_wiki(staging_mod.WIKI_ROOT)
    bad = staging_mod.WIKI_ROOT / "atoms" / "bad-bytes.md"
    bad.write_bytes(b"\xff\xfe needle invalid utf8 \x80\x81")
    hits, note = _query_wiki("needle", limit=20)
    assert note is None
    assert hits  # other tiers still produced results despite the bad file
