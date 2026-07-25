"""Tests for the Slice C LSFS-style semantic FS facade.

Hermetic: a fake kernel returns fake atoms, so the facade is exercised without
live ~/.dharma stores (mirrors the Slice A fake-invoker approach).
"""

from __future__ import annotations

from dharma_swarm.fs_substrate.semantic_fs import SemanticFS, parse_query


class _Atom:
    def __init__(self, surface_id, content, surface_role="MEMORY_PLANE", atom_type="FACT"):
        self.surface_id = surface_id
        self.content = content
        self.surface_role = surface_role
        self.atom_type = atom_type


class _FakeKernel:
    """Front-door stand-in: returns a fixed atom set, ignoring query filters."""

    def __init__(self, atoms):
        self._atoms = atoms

    def iter_memory_atoms(self, *, surface_ids=None, atom_types=None, query=None, limit_total=None):
        out = self._atoms
        if surface_ids is not None:
            out = [a for a in out if a.surface_id in set(surface_ids)]
        return iter(out[: (limit_total or len(out))])


def _kernel():
    return _FakeKernel([
        _Atom("home.knowledge_wiki", "filesystem native context substrate helps agents"),
        _Atom("home.memory_plane", "the swarm dispatches through the spine receipt"),
        _Atom("home.knowledge_wiki", "ontology typed objects and semantic commons naming"),
    ])


def test_parse_query_drops_stopwords():
    terms = parse_query("What is the filesystem substrate for agents?")
    assert "filesystem" in terms and "substrate" in terms
    assert "the" not in terms and "what" not in terms


def test_semantic_retrieve_ranks_by_overlap():
    fs = SemanticFS(_kernel())
    hits = fs.semantic_retrieve("filesystem substrate", k=3)
    assert hits, "expected at least one hit"
    # The atom mentioning both terms ranks first.
    assert "filesystem native context substrate" in hits[0].snippet
    assert hits[0].score >= hits[-1].score  # sorted descending


def test_keywords_retrieve_zero_when_no_overlap():
    fs = SemanticFS(_kernel())
    assert fs.keywords_retrieve(["nonexistentterm"], k=5) == []


def test_surface_filter_is_passed_through():
    fs = SemanticFS(_kernel())
    hits = fs.semantic_retrieve("ontology naming", k=5, surface_ids=["home.knowledge_wiki"])
    assert all(h.surface_id == "home.knowledge_wiki" for h in hits)


def test_integrated_retrieve_groups_by_role():
    fs = SemanticFS(_kernel())
    grouped = fs.integrated_retrieve("spine ontology filesystem", k=5)
    assert isinstance(grouped, dict)
    assert sum(len(v) for v in grouped.values()) >= 1
