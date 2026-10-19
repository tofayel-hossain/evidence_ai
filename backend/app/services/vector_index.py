import os
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import faiss

from backend.app.config import settings
from backend.app.services.chunking_service import TextChunk
from backend.app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class VectorIndex:
    """
    FAISS-based dense semantic vector store with persistent storage
    and document-level metadata tracking.
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or settings.INDEX_DIR
        self.index_file = os.path.join(self.index_dir, "faiss.index")
        self.meta_file = os.path.join(self.index_dir, "faiss_meta.json")
        self.embedding_service = EmbeddingService()
        self.dimension = self.embedding_service.get_dimension()

        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []

        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        """Loads an existing index from disk or initializes a new IndexFlatIP."""
        os.makedirs(self.index_dir, exist_ok=True)
        if os.path.exists(self.index_file) and os.path.exists(self.meta_file):
            try:
                self.index = faiss.read_index(self.index_file)
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors.")
                return
            except Exception as e:
                logger.warning(f"Failed to load FAISS index from disk ({str(e)}). Reinitializing empty index.")

        # IndexFlatIP calculates inner product (dot product) which equals cosine similarity for normalized vectors
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []

    def save(self) -> None:
        """Persists FAISS index binary and chunk metadata JSON to disk."""
        if self.index is not None:
            faiss.write_index(self.index, self.index_file)
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors.")

    def add_chunks(self, chunks: List[TextChunk]) -> None:
        """Embeds text chunks and appends them to the index with metadata."""
        if not chunks:
            return

        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(texts)

        if self.index is None:
            self._load_or_initialize()

        self.index.add(embeddings)
        for chunk in chunks:
            self.metadata.append(chunk.to_dict())

        self.save()

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes dense semantic similarity search against the index.
        Returns matched passages sorted by similarity score descending.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = self.embedding_service.embed_query(query)
        # Fetch up to 4x top_k to account for post-filtering if document_id is specified
        fetch_k = min(self.index.ntotal, top_k * 4 if document_id else top_k)
        if fetch_k <= 0:
            return []

        scores, indices = self.index.search(query_vector, fetch_k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            if document_id and meta.get("document_id") != document_id:
                continue

            results.append({
                "chunk_id": meta["chunk_id"],
                "document_id": meta["document_id"],
                "page_number": meta["page_number"],
                "chunk_index": meta["chunk_index"],
                "content": meta["content"],
                "score": float(score),
                "retrieval_type": "dense_faiss",
                "start_char": meta.get("start_char", 0),
                "end_char": meta.get("end_char", 0)
            })

            if len(results) >= top_k:
                break

        return results

    def delete_document(self, document_id: str) -> None:
        """
        Deletes all chunks associated with a document_id and rebuilds the FAISS index.
        Guarantees that deleted documents do not leave stale embeddings.
        """
        remaining_meta = [m for m in self.metadata if m.get("document_id") != document_id]
        if len(remaining_meta) == len(self.metadata):
            return  # Nothing to remove

        # Rebuild index from remaining chunks
        self.metadata = remaining_meta
        self.index = faiss.IndexFlatIP(self.dimension)

        if remaining_meta:
            texts = [m["content"] for m in remaining_meta]
            embeddings = self.embedding_service.embed_texts(texts)
            self.index.add(embeddings)

        self.save()

    def clear(self) -> None:
        """Clears all vectors and metadata."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.save()
