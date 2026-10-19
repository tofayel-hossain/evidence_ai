import os
import re
import pickle
import logging
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi

from backend.app.config import settings
from backend.app.services.chunking_service import TextChunk

logger = logging.getLogger(__name__)

# Standard English stopwords
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

class BM25Index:
    """
    BM25Okapi sparse lexical search index with persistence
    and document lifecycle synchronization.
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or settings.INDEX_DIR
        self.index_file = os.path.join(self.index_dir, "bm25.pkl")
        self.bm25: Optional[BM25Okapi] = None
        self.corpus_tokens: List[List[str]] = []
        self.metadata: List[Dict[str, Any]] = []

        self._load_or_initialize()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenizes text into cleaned alphanumeric tokens without stopwords."""
        words = re.findall(r'\b[a-zA-Z0-9_\-]+\b', text.lower())
        return [w for w in words if w not in STOPWORDS and len(w) > 1]

    def _load_or_initialize(self) -> None:
        """Loads BM25 model and metadata from disk or initializes empty."""
        os.makedirs(self.index_dir, exist_ok=True)
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "rb") as f:
                    data = pickle.load(f)
                    self.corpus_tokens = data.get("corpus_tokens", [])
                    self.metadata = data.get("metadata", [])
                if self.corpus_tokens:
                    self.bm25 = BM25Okapi(self.corpus_tokens)
                logger.info(f"Loaded BM25 index with {len(self.metadata)} chunks.")
                return
            except Exception as e:
                logger.warning(f"Failed to load BM25 index ({str(e)}). Reinitializing empty index.")

        self.bm25 = None
        self.corpus_tokens = []
        self.metadata = []

    def save(self) -> None:
        """Persists tokenized corpus and metadata to disk."""
        data = {
            "corpus_tokens": self.corpus_tokens,
            "metadata": self.metadata
        }
        with open(self.index_file, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"Saved BM25 index with {len(self.metadata)} chunks.")

    def add_chunks(self, chunks: List[TextChunk]) -> None:
        """Tokenizes text chunks, appends to corpus, and builds BM25Okapi index."""
        if not chunks:
            return

        for chunk in chunks:
            tokens = self.tokenize(chunk.content)
            self.corpus_tokens.append(tokens)
            self.metadata.append(chunk.to_dict())

        if self.corpus_tokens:
            self.bm25 = BM25Okapi(self.corpus_tokens)

        self.save()

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes BM25 keyword search against the corpus.
        Returns ranked passages sorted by BM25 score descending.
        """
        if self.bm25 is None or not self.corpus_tokens:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        raw_scores = self.bm25.get_scores(query_tokens)

        # Sort indices by score descending
        ranked_indices = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)

        results: List[Dict[str, Any]] = []
        query_set = set(query_tokens)
        for idx in ranked_indices:
            score = float(raw_scores[idx])
            # If BM25 IDF is zero or negative due to small corpus size (N=2), award positive score based on lexical overlap
            doc_tokens = self.corpus_tokens[idx]
            overlap = len(query_set.intersection(doc_tokens))
            if score <= 0.0 and overlap > 0:
                score = 0.1 * overlap

            if score <= 0.0:
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
                "score": score,
                "retrieval_type": "sparse_bm25",
                "start_char": meta.get("start_char", 0),
                "end_char": meta.get("end_char", 0)
            })

            if len(results) >= top_k:
                break

        return results

    def delete_document(self, document_id: str) -> None:
        """Removes chunks belonging to a document and rebuilds BM25 index."""
        keep_indices = [
            i for i, meta in enumerate(self.metadata)
            if meta.get("document_id") != document_id
        ]
        if len(keep_indices) == len(self.metadata):
            return

        self.corpus_tokens = [self.corpus_tokens[i] for i in keep_indices]
        self.metadata = [self.metadata[i] for i in keep_indices]

        if self.corpus_tokens:
            self.bm25 = BM25Okapi(self.corpus_tokens)
        else:
            self.bm25 = None

        self.save()

    def clear(self) -> None:
        """Clears all tokens and metadata."""
        self.bm25 = None
        self.corpus_tokens = []
        self.metadata = []
        self.save()
