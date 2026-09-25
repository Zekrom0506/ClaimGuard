"""Turn text into vectors (lists of numbers) so similar meanings are close together.

The model runs locally on this machine, so no text is sent anywhere to be embedded.
"""

from abc import ABC, abstractmethod

# bge models were trained to expect this prefix on search queries (not on documents).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(ABC):
    """Common interface so tests can use a fast fake instead of the real model."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectors for pieces of policy text."""

    @abstractmethod
    def embed_query(self, query_text: str) -> list[float]:
        """Vector for a search query."""


class SentenceTransformerEmbedder(Embedder):
    """Embeddings from a sentence-transformers model such as BAAI/bge-small-en-v1.5."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        """Load the model on first use; it takes a few seconds and ~130 MB of memory."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts in one batch."""
        # normalize_embeddings makes every vector length 1, so cosine distance is a fair comparison.
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, query_text: str) -> list[float]:
        """Embed a search query with the prefix bge expects."""
        vector = self._get_model().encode(BGE_QUERY_PREFIX + query_text, normalize_embeddings=True)
        return vector.tolist()
