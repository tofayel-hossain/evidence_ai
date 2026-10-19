export interface DocumentDTO {
  id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  title: string | null;
  author: string | null;
  status: 'uploaded' | 'processing' | 'indexed' | 'scanned_warning' | 'failed';
  error_message: string | null;
  created_at: string;
}

export interface DocumentChunkDTO {
  id: string;
  document_id: string;
  chunk_index: number;
  page_number: number;
  content: string;
  token_count: number;
  start_char: number;
  end_char: number;
}

export interface CitationDTO {
  citation_id: string;
  document_id: string;
  page_number: number;
  chunk_id: string | null;
  cited_snippet: string;
  is_valid: boolean;
  validation_notes: string;
  overlap_score: number;
}

export interface RetrievedPassageDTO {
  chunk_id: string;
  document_id: string;
  page_number: number;
  chunk_index: number;
  content: string;
  score: number;
  retrieval_method: string;
}

export interface QueryResponseDTO {
  question: string;
  answer: string;
  has_sufficient_evidence: boolean;
  retrieved_passages: RetrievedPassageDTO[];
  citations: CitationDTO[];
  latency_ms: number;
  retrieval_method_used: string;
}

export interface ClaimVerificationDTO {
  claim_id: string;
  claim_text: string;
  classification: 'Supported' | 'Contradicted' | 'Unverified';
  confidence: number;
  premise_text: string;
  page_number: number | null;
  document_id: string | null;
  reasoning: string;
  nli_scores: Record<string, number>;
  numerical_conflict: boolean;
}

export interface VerificationResponseDTO {
  total_claims: number;
  supported_count: number;
  contradicted_count: number;
  unverified_count: number;
  hallucination_rate: number;
  results: ClaimVerificationDTO[];
  latency_ms: number;
}

export interface ConversationDTO {
  id: string;
  title: string;
  document_id: string | null;
  created_at: string;
  updated_at: string;
}
