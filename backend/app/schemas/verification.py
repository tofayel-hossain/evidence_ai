from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AtomicClaim(BaseModel):
    claim_id: str
    text: str
    source_citation: Optional[str] = None
    page_number: Optional[int] = None
    char_offset: int = 0

class ClaimVerificationResult(BaseModel):
    claim_id: str
    claim_text: str
    classification: str = Field(..., description="'Supported', 'Contradicted', or 'Unverified'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated verification confidence score")
    premise_text: str = Field(..., description="Source document evidence used for verification")
    page_number: Optional[int] = None
    document_id: Optional[str] = None
    reasoning: str
    nli_scores: Dict[str, float] = Field(default_factory=dict, description="Entailment, contradiction, neutral probabilities")
    numerical_conflict: bool = False

class VerificationRequest(BaseModel):
    text: str = Field(..., description="Answer or claim text to verify")
    document_id: Optional[str] = Field(None, description="Document ID containing supporting evidence")
    top_k_evidence: int = Field(3, description="Number of evidence chunks to inspect per claim")

class VerificationResponse(BaseModel):
    total_claims: int
    supported_count: int
    contradicted_count: int
    unverified_count: int
    hallucination_rate: float = Field(..., description="Proportion of contradicted or unsupported claims")
    results: List[ClaimVerificationResult]
    latency_ms: float
