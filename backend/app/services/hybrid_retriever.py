import re
import logging
from typing import List, Dict, Any, Optional
from backend.app.config import settings
from backend.app.services.vector_index import VectorIndex
from backend.app.services.bm25_index import BM25Index

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Intelligent retrieval engine supporting:
    1. Sparse keyword retrieval (BM25)
    2. Dense semantic retrieval (SentenceTransformers + FAISS)
    3. Hybrid retrieval with Reciprocal Rank Fusion (RRF) and Score Normalization.
    4. Structural Semantic Anchoring (intelligently identifies document headers,
       paper titles, and author lines even when explicit keywords are omitted).
    """

    def __init__(
        self,
        vector_index: Optional[VectorIndex] = None,
        bm25_index: Optional[BM25Index] = None
    ):
        self.vector_index = vector_index or VectorIndex()
        self.bm25_index = bm25_index or BM25Index()

    def _get_header_anchors(self, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves Page 1 header chunks (chunks 0-4) containing the true paper title,
        authors, affiliations, and abstract even when the PDF does not print explicit label keywords.
        """
        anchors: List[Dict[str, Any]] = []
        meta_source = self.vector_index.metadata or self.bm25_index.corpus_metadata or []
        for m in meta_source:
            if document_id and m.get("document_id") != document_id:
                continue
            if m.get("page_number") == 1 and m.get("chunk_index", 99) <= 4:
                chunk_copy = dict(m)
                chunk_copy["score"] = 1.0
                anchors.append(chunk_copy)
        anchors.sort(key=lambda x: (x.get("document_id", ""), x.get("chunk_index", 0)))
        return anchors

    def retrieve(
        self,
        query: str,
        method: str = "auto",  # "auto", "hybrid", "dense", "bm25"
        top_k: int = 5,
        alpha: float = 0.5,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k passages using the chosen or auto-adaptive retrieval strategy,
        with structural perception for paper titles, authors, and document overviews.
        """
        method_lower = (method or "auto").lower()

        # Semantic Intent Detection: check if query asks for document identity / header attributes
        q_lower = query.lower()
        is_metadata_query = bool(re.search(
            r'\b(title|name of (?:the|this)? (?:paper|document|article|study|work|project)|paper(?:[\'’]s)? (?:name|title)|what is (?:the|this)? (?:paper|document|article|study) called|authors?|who (?:wrote|authored|conducted|published)|researchers?|writers?|creators?|who are (?:the )?authors|affiliations?|universit(?:y|ies)|departments?|institution|colleges?|what is (?:this|the) (?:paper|study|document|work) about|summar(?:y|ize)|overview|abstract|main objective|purpose of (?:this|the) (?:study|paper)|doi|published in|journal|conference)\b',
            q_lower
        ))

        # Check for exact technical indicators (numbers, percentages, uppercase acronyms, equations, quotes)
        has_exact_terms = bool(
            re.search(r'["\']|\b\d+(?:\.\d+)?%?\b|[A-Z]{2,}(?:\d+)?|\b(?:table|figure|eq|equation|dataset|accuracy|f1|auc)\b', query)
        )
        is_conceptual = bool(
            re.search(r'\b(why|how does|explain|concept|intuition|mechanism|limitation|drawback|advantage|difference between|motivation)\b', q_lower)
        )

        # Auto-adaptive strategy routing
        if method_lower in ("auto", "adaptive", "default", ""):
            if is_metadata_query:
                strategy_label = "Auto: Structural Perception"
                effective_alpha = 0.65
                results = self.retrieve_hybrid(query, top_k=top_k, alpha=effective_alpha, document_id=document_id)
            elif has_exact_terms and not is_conceptual:
                strategy_label = "Auto: Keyword-Boosted Hybrid"
                effective_alpha = 0.35
                results = self.retrieve_hybrid(query, top_k=top_k, alpha=effective_alpha, document_id=document_id)
            elif is_conceptual:
                strategy_label = "Auto: Dense Semantic Hybrid"
                effective_alpha = 0.75
                results = self.retrieve_hybrid(query, top_k=top_k, alpha=effective_alpha, document_id=document_id)
            else:
                strategy_label = "Auto: Balanced Hybrid (RRF)"
                effective_alpha = 0.50
                results = self.retrieve_hybrid(query, top_k=top_k, alpha=effective_alpha, document_id=document_id)
            for r in results:
                r["retrieval_method"] = strategy_label
        elif method_lower == "bm25":
            results = self.retrieve_bm25(query, top_k=top_k, document_id=document_id)
        elif method_lower in ("dense", "faiss"):
            results = self.retrieve_dense(query, top_k=top_k, document_id=document_id)
        elif method_lower == "hybrid":
            results = self.retrieve_hybrid(query, top_k=top_k, alpha=alpha, document_id=document_id)
        else:
            raise ValueError(f"Unknown retrieval method: '{method}'. Valid options are 'auto', 'bm25', 'dense', 'hybrid'.")

        if is_metadata_query:
            header_chunks = self._get_header_anchors(document_id)
            if header_chunks:
                eff_method = results[0].get("retrieval_method", method) if results else method
                for h in header_chunks:
                    h["retrieval_method"] = eff_method
                header_cids = {h["chunk_id"] for h in header_chunks}
                # Inject header chunks at the front so the LLM directly sees Title, Authors, and Affiliations
                results = (header_chunks + [r for r in results if r.get("chunk_id") not in header_cids])[:max(top_k, len(header_chunks))]

        return results

    def retrieve_bm25(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Sparse BM25 keyword search."""
        results = self.bm25_index.search(query, top_k=top_k, document_id=document_id)
        for r in results:
            r["retrieval_method"] = "bm25"
        return results

    def retrieve_dense(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Dense semantic FAISS search."""
        results = self.vector_index.search(query, top_k=top_k, document_id=document_id)
        for r in results:
            r["retrieval_method"] = "dense"
        return results

    def retrieve_hybrid(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        rrf_k: int = 60,
        document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Combines Dense and Sparse results via Reciprocal Rank Fusion (RRF).
        RRF Score: S(d) = alpha * (1 / (rrf_k + dense_rank)) + (1 - alpha) * (1 / (rrf_k + sparse_rank))
        """
        # Fetch candidate pools from both sources (up to 2x top_k to blend rankings)
        candidate_k = max(top_k * 2, 10)
        dense_results = self.vector_index.search(query, top_k=candidate_k, document_id=document_id)
        bm25_results = self.bm25_index.search(query, top_k=candidate_k, document_id=document_id)

        # Map by chunk_id
        chunk_map: Dict[str, Dict[str, Any]] = {}

        # Dense ranking
        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "chunk_id": cid,
                    "document_id": item["document_id"],
                    "page_number": item["page_number"],
                    "chunk_index": item["chunk_index"],
                    "content": item["content"],
                    "start_char": item.get("start_char", 0),
                    "end_char": item.get("end_char", 0),
                    "dense_rank": rank,
                    "dense_score": item["score"],
                    "bm25_rank": None,
                    "bm25_score": 0.0,
                    "rrf_score": 0.0
                }
            else:
                chunk_map[cid]["dense_rank"] = rank
                chunk_map[cid]["dense_score"] = item["score"]

        # BM25 ranking
        for rank, item in enumerate(bm25_results, start=1):
            cid = item["chunk_id"]
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "chunk_id": cid,
                    "document_id": item["document_id"],
                    "page_number": item["page_number"],
                    "chunk_index": item["chunk_index"],
                    "content": item["content"],
                    "start_char": item.get("start_char", 0),
                    "end_char": item.get("end_char", 0),
                    "dense_rank": None,
                    "dense_score": 0.0,
                    "bm25_rank": rank,
                    "bm25_score": item["score"],
                    "rrf_score": 0.0
                }
            else:
                chunk_map[cid]["bm25_rank"] = rank
                chunk_map[cid]["bm25_score"] = item["score"]

        # Calculate RRF scores
        for cid, data in chunk_map.items():
            dense_comp = (alpha / (rrf_k + data["dense_rank"])) if data["dense_rank"] is not None else 0.0
            bm25_comp = ((1.0 - alpha) / (rrf_k + data["bm25_rank"])) if data["bm25_rank"] is not None else 0.0
            data["rrf_score"] = dense_comp + bm25_comp
            data["score"] = data["rrf_score"]
            data["retrieval_method"] = "hybrid"

        # Sort descending by RRF score
        ranked_chunks = sorted(chunk_map.values(), key=lambda x: x["rrf_score"], reverse=True)
        return ranked_chunks[:top_k]

# Global shared retriever instances for application-wide synchronization
shared_vector_index = VectorIndex()
shared_bm25_index = BM25Index()
shared_retriever = HybridRetriever(vector_index=shared_vector_index, bm25_index=shared_bm25_index)

