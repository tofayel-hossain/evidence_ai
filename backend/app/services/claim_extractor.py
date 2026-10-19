import re
import uuid
from typing import List
from backend.app.schemas.verification import AtomicClaim
from backend.app.services.citation_service import CitationService

class ClaimExtractor:
    """
    Decomposes answer narratives into discrete, testable atomic factual claims
    while extracting associated citation anchors.
    """

    # Rhetorical prefixes to strip iteratively from claims
    FLUFF_PATTERNS = [
        r'^(?:according to the (?:paper|authors|document|study|researchers),?\s*)',
        r'^(?:the (?:authors|researchers|paper|study) (?:state|note|report|demonstrate|show|find) that\s*)',
        r'^(?:we (?:observe|find|note) that\s*)',
        r'^(?:in conclusion,?\s*)',
        r'^(?:furthermore,?\s*)',
        r'^(?:moreover,?\s*)',
        r'^(?:it is reported that\s*)'
    ]

    @classmethod
    def clean_claim_text(cls, text: str) -> str:
        """Removes rhetorical discourse markers iteratively and trims whitespace."""
        text = text.strip()
        changed = True
        while changed:
            changed = False
            for pat in cls.FLUFF_PATTERNS:
                new_text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
                if new_text != text:
                    text = new_text
                    changed = True
        return text

    @classmethod
    def extract_claims(cls, text: str) -> List[AtomicClaim]:
        """
        Splits text into atomic claims, isolating citations and stripping fluff.
        """
        if not text or not text.strip():
            return []

        # Split into initial sentences
        raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        claims: List[AtomicClaim] = []
        claim_counter = 0

        for sentence in raw_sentences:
            s_clean = sentence.strip()
            if not s_clean:
                continue

            # Extract citations attached to this sentence
            citations = CitationService.extract_citations_from_text(s_clean)
            associated_page = citations[0][1] if citations else None
            citation_tag = citations[0][2] if citations else None

            # Remove citation tags from the claim text itself
            text_without_citations = CitationService.CITATION_PATTERN.sub("", s_clean).strip()
            # Clean punctuation spacing: "rate 0.001 ." -> "rate 0.001."
            text_without_citations = re.sub(r'\s+([.,;:!?])', r'\1', text_without_citations)

            # Clean fluff
            normalized = cls.clean_claim_text(text_without_citations)

            if len(normalized) < 15:
                continue

            # Split compound conjunctions if both parts are self-contained: " ; ", " whereas ", " while "
            clauses = re.split(r';\s+|\s+whereas\s+|\s+while\s+', normalized, flags=re.IGNORECASE)

            for clause in clauses:
                clause_text = clause.strip()
                if len(clause_text) < 15:
                    continue
                # Ensure ends with period
                if not clause_text.endswith("."):
                    clause_text += "."

                claim_id = f"claim_{uuid.uuid4().hex[:8]}"
                claims.append(
                    AtomicClaim(
                        claim_id=claim_id,
                        text=clause_text,
                        source_citation=citation_tag,
                        page_number=associated_page,
                        char_offset=0
                    )
                )
                claim_counter += 1

        return claims
