import pytest
from backend.app.schemas.query import QueryRequest
from backend.app.services.citation_service import CitationService
from backend.app.services.rag_service import RAGService
from backend.app.services.hybrid_retriever import HybridRetriever
from backend.app.services.llm_service import LLMService

def test_citation_tag_extraction():
    sample_text = (
        "The model uses 8 attention heads [Page 4] and achieved 28.4 BLEU [Pages 5-6]. "
        "Further details are provided in [appendix_doc, Page 12]."
    )
    extracted = CitationService.extract_citations_from_text(sample_text)

    assert len(extracted) == 4
    # [Page 4]
    assert extracted[0] == (None, 4, "[Page 4]")
    # [Pages 5-6] expands to page 5 and page 6
    assert extracted[1] == (None, 5, "[Pages 5-6]")
    assert extracted[2] == (None, 6, "[Pages 5-6]")
    # [appendix_doc, Page 12]
    assert extracted[3] == ("appendix_doc", 12, "[appendix_doc, Page 12]")

def test_citation_validation_valid_and_invalid():
    answer_text = (
        "The authors utilized ResNet-50 as their visual backbone [Page 2]. "
        "The quantum computer reached room temperature [Page 99]."
    )
    passages = [
        {
            "chunk_id": "doc1_p2_c0",
            "document_id": "doc1",
            "page_number": 2,
            "chunk_index": 0,
            "content": "For our feature extractor, we utilized ResNet-50 pre-trained on ImageNet."
        }
    ]

    # Validate against document with 10 total pages
    citations = CitationService.validate_citations(
        answer_text=answer_text,
        retrieved_passages=passages,
        document_id="doc1",
        max_page_count=10
    )

    assert len(citations) == 2

    # Page 2 should be valid
    cite_p2 = next(c for c in citations if c.page_number == 2)
    assert cite_p2.is_valid is True
    assert cite_p2.chunk_id == "doc1_p2_c0"
    assert "ResNet-50" in cite_p2.cited_snippet

    # Page 99 exceeds max_page_count=10
    cite_p99 = next(c for c in citations if c.page_number == 99)
    assert cite_p99.is_valid is False
    assert "exceeds total document pages" in cite_p99.validation_notes

def test_rag_service_insufficient_evidence():
    # Mock retriever that returns empty passages
    class EmptyRetriever:
        def retrieve(self, **kwargs):
            return []

    rag = RAGService(retriever=EmptyRetriever(), llm_service=LLMService(provider="fallback"))
    request = QueryRequest(question="What is the speed of light in vacuum?")
    response = rag.answer_question(request)

    assert response.has_sufficient_evidence is False
    assert "insufficient evidence" in response.answer.lower()
    assert len(response.citations) == 0
