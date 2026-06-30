"""Tests for TFIDFEmbedder joblib basis persistence (stream mem #6).

Covers:
- fit_add persists vectorizer + svd via joblib; _fitted=True after fit.
- cold construction (new instance, same state_path) restores _fitted=True
  and the fitted estimators WITHOUT any fit_add call.
- embeddings from the two instances are in the same basis (near-identical
  for the same probe text).
- VectorStore.upsert does not call fit_add on every upsert once fitted.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dharma_swarm.vector_store import TFIDFEmbedder, VectorStore

_CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "machine learning interpretability neural networks",
    "contemplative practice meditation awareness consciousness",
    "vector database embedding similarity retrieval",
    "dharma swarm autonomous agent orchestration",
    "geometric lens representation contraction witness",
    "sqlite vec0 tfidf svd cosine similarity",
    "akram vignan mahatma self realization",
]
_PROBE = "the quick fox and dharma swarm interpretability"


def test_fit_add_persists_and_cold_loads_same_basis(tmp_path: Path) -> None:
    state_path = tmp_path / "tfidf_embedder.pkl"

    e1 = TFIDFEmbedder(dim=128, state_path=state_path)
    assert e1._fitted is False
    e1.fit_add(_CORPUS)
    assert e1._fitted is True
    assert e1._vectorizer is not None
    assert e1._svd is not None
    assert state_path.exists()
    assert Path(str(state_path) + ".joblib").exists()

    v1 = e1.embed([_PROBE])[0]
    assert len(v1) == 128

    # Cold construction in the same process simulates a fresh process load:
    # _load_state() runs in __init__ with no fit_add call.
    e2 = TFIDFEmbedder(dim=128, state_path=state_path)
    assert e2._fitted is True, "cold load must restore _fitted without refit"
    assert e2._vectorizer is not None
    assert e2._svd is not None

    v2 = e2.embed([_PROBE])[0]
    assert len(v2) == 128

    max_diff = max(abs(a - b) for a, b in zip(v1, v2))
    assert max_diff < 1e-9, f"cold-load embeddings not in same basis: max_diff={max_diff}"


def test_upsert_does_not_refit_when_fitted(tmp_path: Path) -> None:
    store = VectorStore(state_dir=tmp_path)
    emb = store._embedder
    calls = {"n": 0}
    orig = emb.fit_add

    def counting_fit_add(texts):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return orig(texts)

    emb.fit_add = counting_fit_add  # type: ignore[method-assign]
    # Bootstrap with a real corpus so the SVD is non-degenerate.
    emb.fit_add(_CORPUS)
    calls["n"] = 0
    for i in range(3):
        store.upsert(content=f"document number {i} about cats and dogs", layer="working")
    assert calls["n"] == 0, f"upsert called fit_add {calls['n']} times (basis would slide)"


def test_load_falls_back_when_joblib_missing(tmp_path: Path) -> None:
    state_path = tmp_path / "tfidf_embedder.pkl"
    # Write only the legacy JSON state (no joblib file).
    import json

    with open(state_path, "w") as fh:
        json.dump({"corpus": _CORPUS[:2], "corpus_hash": "x", "dim": 128, "fitted": True}, fh)
    e = TFIDFEmbedder(dim=128, state_path=state_path)
    # No joblib → must fall back to unfitted (refit on next embed).
    assert e._fitted is False
    assert e._vectorizer is None
    assert e._corpus == _CORPUS[:2]