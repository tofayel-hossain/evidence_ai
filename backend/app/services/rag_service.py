import time
import logging
from typing import Dict, Any, Optional

from backend.app.schemas.query import QueryRequest, QueryResponse, RetrievedPassageDTO
from backend.app.services.hybrid_retriever import HybridRetriever
from backend.app.services.llm_service import LLMService
from backend.app.services.citation_service import CitationService

logger = logging.getLogger(__name__)

class RAGService:
    """
    Orchestrates the complete Retrieval-Augmented Generation workflow:
    1. Hybrid/Dense/Sparse passage retrieval
    2. Context isolation & prompt injection guardrails
    3. Evidence-grounded generation
    4. Deterministic citation validation against real document chunks
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        llm_service: Optional[LLMService] = None,
        citation_service: Optional[CitationService] = None
    ):
        self.retriever = retriever or HybridRetriever()
        self.llm_service = llm_service or LLMService()
        self.citation_service = citation_service or CitationService()

    def answer_question(
        self,
        request: QueryRequest,
        max_page_count: Optional[int] = None
    ) -> QueryResponse:
        t0 = time.time()

        # Step 1: Passage Retrieval
        passages = self.retriever.retrieve(
            query=request.question,
            method=request.retrieval_method,
            top_k=request.top_k,
            alpha=request.alpha,
            document_id=request.document_id
        )

        # Step 2: Evidence Sufficiency Verification
        if not passages:
            latency_ms = (time.time() - t0) * 1000
            return QueryResponse(
                question=request.question,
                answer="Based on the uploaded documents, there is insufficient evidence to answer this question.",
                has_sufficient_evidence=False,
                retrieved_passages=[],
                citations=[],
                latency_ms=round(latency_ms, 2),
                retrieval_method_used=request.retrieval_method
            )

        # Step 3: Evidence-grounded generation
        answer = self.llm_service.generate_answer(
            question=request.question,
            passages=passages
        )

        # Step 4: Citation Extraction & Validation
        citations = self.citation_service.validate_citations(
            answer_text=answer,
            retrieved_passages=passages,
            document_id=request.document_id,
            max_page_count=max_page_count
        )

        latency_ms = (time.time() - t0) * 1000

        passage_dtos = [
            RetrievedPassageDTO(
                chunk_id=p["chunk_id"],
                document_id=p["document_id"],
                page_number=p["page_number"],
                chunk_index=p["chunk_index"],
                content=p["content"],
                score=float(p.get("score", 0.0)),
                retrieval_method=p.get("retrieval_method", request.retrieval_method)
            )
            for p in passages
        ]

        return QueryResponse(
            question=request.question,
            answer=answer,
            has_sufficient_evidence=True,
            retrieved_passages=passage_dtos,
            citations=citations,
            latency_ms=round(latency_ms, 2),
            retrieval_method_used=passages[0].get("retrieval_method", request.retrieval_method) if passages else request.retrieval_method
        )
