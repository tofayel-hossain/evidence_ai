from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Research question to ask")
    document_id: Optional[str] = Field(None, description="Optional document ID to restrict search to")
    retrieval_method: str = Field("auto", description="Retrieval method: 'auto', 'hybrid', 'dense', or 'bm25'")
    top_k: int = Field(5, ge=1, le=20, description="Number of passages to retrieve")
    alpha: float = Field(0.5, ge=0.0, le=1.0, description="Hybrid retrieval weight (1.0 = 100% dense, 0.0 = 100% sparse)")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID to link message")

class CitationDTO(BaseModel):
    citation_id: str
    document_id: str
    page_number: int
    chunk_id: Optional[str] = None
    cited_snippet: str
    is_valid: bool
    validation_notes: str
    overlap_score: float = 0.0

class RetrievedPassageDTO(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int
    chunk_index: int
    content: str
    score: float
    retrieval_method: str

class QueryResponse(BaseModel):
    question: str
    answer: str
    has_sufficient_evidence: bool
    retrieved_passages: List[RetrievedPassageDTO]
    citations: List[CitationDTO]
    latency_ms: float
    retrieval_method_used: str
