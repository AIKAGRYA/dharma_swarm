"""Embedders for the dharma_swarm vector store.

Extracted from dharma_swarm/vector_store.py to keep that module inside the
Rule 10 line budget. Import surface is preserved: vector_store re-exports
Embedder, SentenceTransformerEmbedder, and TFIDFEmbedder.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedder protocol — swappable TF-IDF now, sentence-transformers later
# ---------------------------------------------------------------------------

@runtime_checkable
class Embedder(Protocol):
    """Pluggable embedding interface.

    TF-IDF now; sentence-transformers as drop-in replacement later.
    Both must implement embed() and dim.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into fixed-dimension dense vectors."""
        ...

    @property
    def dim(self) -> int:
        """Embedding dimensionality."""
        ...


class SentenceTransformerEmbedder:
    """Neural embedder using sentence-transformers for real semantic similarity.

    Drop-in replacement for TFIDFEmbedder via the Embedder protocol.
    Loads model lazily on first embed() call to avoid slow startup.
    Model and state are cached at state_path for fast restarts.

    Default model: all-MiniLM-L6-v2 (384-dim, 22M params, fast on CPU).
    For better quality at ~2x cost: all-mpnet-base-v2 (768-dim).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dim: int = 384,
        state_path: Path | None = None,
    ) -> None:
        self._model_name = model_name
        self._dim = dim
        self._state_path = state_path  # unused but matches protocol shape
        self._model: Any = None
        self._last_error: str | None = None

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim and actual_dim != self._dim:
                logger.info(
                    "SentenceTransformerEmbedder: model dim=%d, configured dim=%d — using model dim",
                    actual_dim, self._dim,
                )
                self._dim = actual_dim
        except ImportError:
            logger.warning("sentence-transformers not installed, falling back to zero vectors")
        except Exception as exc:
            self._last_error = f"model load failed: {exc}"
            logger.warning("SentenceTransformerEmbedder model load failed: %s", exc)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the sentence-transformer model."""
        if not texts:
            return []
        self._ensure_model()
        if self._model is None:
            return [[0.0] * self._dim for _ in texts]
        try:
            embeddings = self._model.encode(
                texts,
                show_progress_bar=False,
                normalize_embeddings=True,
                batch_size=64,
            )
            return [list(map(float, vec)) for vec in embeddings]
        except Exception as exc:
            logger.debug("SentenceTransformerEmbedder.embed failed: %s", exc)
            return [[0.0] * self._dim for _ in texts]

    def fit_add(self, texts: list[str]) -> None:
        """No-op for pre-trained model — vocabulary is fixed."""
        pass


class TFIDFEmbedder:
    """Lightweight embedder using scikit-learn TF-IDF + TruncatedSVD.

    Produces fixed-dimension dense vectors from TF-IDF sparse matrices.
    Uses TruncatedSVD to reduce to `dim` dimensions (default 128).
    Fits incrementally — call fit_add() to expand vocabulary.

    Pickle-persisted alongside the SQLite database so vocab survives restarts.
    """

    def __init__(
        self,
        dim: int = 128,
        state_path: Path | None = None,
        fit_on_embed: bool = True,
    ) -> None:
        self._dim = dim
        self._state_path = state_path  # Path for pickle persistence
        self._fit_on_embed = fit_on_embed
        self._vectorizer: Any = None   # TfidfVectorizer
        self._svd: Any = None          # TruncatedSVD
        self._corpus: list[str] = []
        self._corpus_hash: str = ""
        self._fitted = False
        self._last_error: str | None = None
        self._load_state()

    @property
    def dim(self) -> int:
        return self._dim

    def _sklearn_available(self) -> bool:
        try:
            return (
                importlib.util.find_spec("sklearn.feature_extraction.text") is not None
                and importlib.util.find_spec("sklearn.decomposition") is not None
            )
        except ModuleNotFoundError:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts. Fits on first call if not already fitted."""
        if not texts:
            return []
        if not self._sklearn_available():
            logger.debug("scikit-learn not available")
            return [[0.0] * self._dim for _ in texts]

        try:
            if not self._fitted or self._vectorizer is None:
                if self._corpus:
                    self._fit(self._corpus)
                if not self._fitted or self._vectorizer is None:
                    if not self._fit_on_embed:
                        return [[0.0] * self._dim for _ in texts]
                    self._fit(texts)
                if not self._fitted or self._vectorizer is None:
                    return [[0.0] * self._dim for _ in texts]

            # Transform
            tfidf_matrix = self._vectorizer.transform(texts)
            if tfidf_matrix.shape[1] == 0:
                if not self._fit_on_embed:
                    return [[0.0] * self._dim for _ in texts]
                # Empty vocabulary — refit with current texts only for standalone embedders.
                self._fit(texts)
                tfidf_matrix = self._vectorizer.transform(texts)

            # Project to lower dimension via SVD
            n_features = tfidf_matrix.shape[1]
            if n_features == 0:
                return [[0.0] * self._dim for _ in texts]

            # SVD may need refit if feature count changed
            actual_dim = min(self._dim, n_features)
            if self._svd is None or self._svd.n_components != actual_dim:
                if self._corpus:
                    self._fit(self._corpus)
                elif self._fit_on_embed:
                    self._fit(texts)
                else:
                    return [[0.0] * self._dim for _ in texts]
                if not self._fitted or self._vectorizer is None or self._svd is None:
                    return [[0.0] * self._dim for _ in texts]
                tfidf_matrix = self._vectorizer.transform(texts)
                n_features = tfidf_matrix.shape[1]
                actual_dim = min(self._dim, n_features)

            dense = self._svd.transform(tfidf_matrix)

            # Pad or trim to exactly self._dim
            result: list[list[float]] = []
            for row in dense:
                vec = list(map(float, row))
                if len(vec) < self._dim:
                    vec = vec + [0.0] * (self._dim - len(vec))
                else:
                    vec = vec[:self._dim]
                # L2-normalize
                norm = (sum(v * v for v in vec) ** 0.5) or 1.0
                result.append([v / norm for v in vec])
            return result

        except Exception as exc:
            logger.debug("TFIDFEmbedder.embed failed: %s", exc)
            return [[0.0] * self._dim for _ in texts]

    def fit_add(self, texts: list[str]) -> None:
        """Expand vocabulary with new texts and refit."""
        if not texts:
            return
        self._corpus.extend(texts)
        # Keep corpus bounded
        if len(self._corpus) > 10000:
            self._corpus = self._corpus[-10000:]
        self._fit(self._corpus)
        if not self._fitted:
            self._save_state()

    def fit_replace(self, texts: list[str]) -> None:
        """Replace the persisted corpus and refit from trusted document text."""
        self._corpus = list(dict.fromkeys(texts[-10000:]))
        self._corpus_hash = ""
        self._fitted = False
        self._vectorizer = None
        self._svd = None
        self._fit(self._corpus)
        if not self._fitted:
            self._save_state()

    def _fit(self, texts: list[str]) -> None:
        """Fit TF-IDF + SVD on provided texts."""
        if not texts:
            return
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.decomposition import TruncatedSVD

            corpus = list(set(texts))  # Deduplicate
            if not corpus:
                return

            vec = TfidfVectorizer(
                max_features=5000,
                sublinear_tf=True,
                min_df=1,
                token_pattern=r"(?u)\b\w+\b",
            )
            tfidf = vec.fit_transform(corpus)
            n_features = tfidf.shape[1]

            if n_features == 0:
                return

            actual_dim = min(self._dim, n_features, len(corpus) - 1)
            if actual_dim < 1:
                actual_dim = 1

            svd = TruncatedSVD(n_components=actual_dim, random_state=42)
            svd.fit(tfidf)

            self._vectorizer = vec
            self._svd = svd
            self._fitted = True

            # Update corpus and hash
            self._corpus = list(corpus)
            corpus_str = " ".join(sorted(corpus))
            self._corpus_hash = hashlib.md5(corpus_str.encode()).hexdigest()[:16]

            self._save_state()

        except Exception as exc:
            self._last_error = f"_fit failed: {exc}"
            logger.debug("TFIDFEmbedder._fit failed: %s", exc)

    def _save_state(self) -> None:
        """Persist fitted state to disk."""
        if self._state_path is None:
            return
        try:
            import json as _json
            state = {
                # vectorizer/svd are sklearn objects — not JSON-serializable
                # persist only the corpus and metadata; refit on next load
                "corpus": self._corpus[-2000:],
                "corpus_hash": self._corpus_hash,
                "dim": self._dim,
                "fitted": False,
            }
            with open(self._state_path, "w", encoding="utf-8") as fh:
                _json.dump(state, fh)
        except Exception as exc:
            self._last_error = f"_save_state failed: {exc}"
            logger.debug("TFIDFEmbedder._save_state failed: %s", exc)

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if self._state_path is None or not Path(self._state_path).exists():
            return
        try:
            import json as _json
            with open(self._state_path, "r", encoding="utf-8") as fh:
                state = _json.load(fh)
            # vectorizer and svd cannot be serialized to JSON — rebuild on next fit
            self._vectorizer = None
            self._svd = None
            self._corpus = state.get("corpus", [])
            self._corpus_hash = state.get("corpus_hash", "")
            self._fitted = False
            if self._corpus:
                self._fit(self._corpus)
        except Exception as exc:
            self._last_error = f"_load_state failed: {exc}"
            logger.debug("TFIDFEmbedder._load_state failed: %s", exc)
