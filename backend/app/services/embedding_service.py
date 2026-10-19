import numpy as np
from typing import List, Union, Any
from backend.app.config import settings

class EmbeddingService:
    """
    Singleton embedding generator utilizing Sentence Transformers.
    Uses lazy model loading to ensure sub-second application startup and fast testing.
    Generates normalized dense vector embeddings for cosine similarity retrieval.
    """
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    @property
    def model(self) -> Any:
        """Lazy load SentenceTransformer only when first requested."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return self._model

    def get_dimension(self) -> int:
        """Returns the embedding vector dimensionality (384 for all-MiniLM-L6-v2)."""
        return 384

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Embeds a batch of texts into L2-normalized numpy arrays.
        Normalization enables cosine similarity via inner product (dot product).
        """
        if not texts:
            return np.empty((0, self.get_dimension()), dtype=np.float32)

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embeds a single search query."""
        embedding = self.model.encode(
            query,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embedding.astype(np.float32).reshape(1, -1)
