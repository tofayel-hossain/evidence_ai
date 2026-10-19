import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from backend.app.schemas.query import CitationDTO

class CitationService:
    """
    Independent citation validation engine.
    Extracts citation markers from answer text, verifies that the referenced
    pages and source passages exist in the document store, and measures
    exact lexical provenance.
    """

    # Regex matches: [Page 3], [Pages 2-3], [Page 2, 4], [doc_id, Page 1]
    CITATION_PATTERN = re.compile(
        r'\[(?:([a-zA-Z0-9_\-]+),\s*)?[Pp]ages?\s*([0-9]+(?:\s*[-–,]\s*[0-9]+)*)\]'
    )

    @classmethod
    def extract_citations_from_text(cls, text: str) -> List[Tuple[Optional[str], int, str]]:
        """
        Parses all citation tags out of text.
        Returns list of tuples: (doc_id_or_none, page_number, raw_matched_tag).
        """
        found_citations = []
        for match in cls.CITATION_PATTERN.finditer(text):
            doc_id = match.group(1)
            pages_str = match.group(2)
            raw_tag = match.group(0)

            # Handle comma or range of pages
            if "-" in pages_str or "–" in pages_str:
                parts = re.split(r'[-–]', pages_str)
                try:
                    start_p = int(parts[0].strip())
                    end_p = int(parts[1].strip())
                    for p in range(start_p, end_p + 1):
                        found_citations.append((doc_id, p, raw_tag))
                except ValueError:
                    pass
            elif "," in pages_str:
                for p_str in pages_str.split(","):
                    try:
                        p = int(p_str.strip())
                        found_citations.append((doc_id, p, raw_tag))
                    except ValueError:
                        pass
            else:
                try:
                    p = int(pages_str.strip())
                    found_citations.append((doc_id, p, raw_tag))
                except ValueError:
                    pass

        return found_citations

    @staticmethod
    def _compute_token_overlap(text_a: str, text_b: str) -> float:
        """Computes Jaccard similarity between two texts based on alphanumeric tokens."""
        words_a = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', text_a.lower()))
        words_b = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)
        return len(intersection) / len(union)

    @classmethod
    def validate_citations(
        cls,
        answer_text: str,
        retrieved_passages: List[Dict[str, Any]],
        document_id: Optional[str] = None,
        max_page_count: Optional[int] = None
    ) -> List[CitationDTO]:
        """
        Validates every citation found in answer_text against the retrieved passages.
        """
        extracted = cls.extract_citations_from_text(answer_text)
        validated_citations: List[CitationDTO] = []

        # If answer has no citations, return empty
        if not extracted:
            return []

        # Map available passages by (doc_id, page_number)
        passage_map: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for p in retrieved_passages:
            pid = p.get("document_id", document_id or "default")
            p_page = p.get("page_number", 1)
            key = (pid, p_page)
            if key not in passage_map:
                passage_map[key] = []
            passage_map[key].append(p)

        seen_keys = set()
        for doc_override, page_num, raw_tag in extracted:
            target_doc = doc_override or document_id or (
                retrieved_passages[0]["document_id"] if retrieved_passages else "unknown"
            )
            cite_key = (target_doc, page_num)
            if cite_key in seen_keys:
                continue
            seen_keys.add(cite_key)

            citation_id = f"cite_{uuid.uuid4().hex[:8]}"

            # Check 1: Is page number within valid physical document range?
            if max_page_count is not None and (page_num < 1 or page_num > max_page_count):
                validated_citations.append(
                    CitationDTO(
                        citation_id=citation_id,
                        document_id=target_doc,
                        page_number=page_num,
                        chunk_id=None,
                        cited_snippet="",
                        is_valid=False,
                        validation_notes=f"Invalid page reference: Page {page_num} exceeds total document pages ({max_page_count}).",
                        overlap_score=0.0
                    )
                )
                continue

            # Check 2: Does the referenced page exist among stored/retrieved chunks?
            matching_chunks = passage_map.get((target_doc, page_num), [])
            if not matching_chunks:
                # Check if page exists under another doc_id in single-doc mode
                fallback_chunks = [p for p in retrieved_passages if p.get("page_number") == page_num]
                if fallback_chunks:
                    matching_chunks = fallback_chunks

            if not matching_chunks:
                validated_citations.append(
                    CitationDTO(
                        citation_id=citation_id,
                        document_id=target_doc,
                        page_number=page_num,
                        chunk_id=None,
                        cited_snippet="",
                        is_valid=False,
                        validation_notes=f"Unverified citation: No retrieved evidence passage found for Page {page_num}.",
                        overlap_score=0.0
                    )
                )
                continue

            # Find chunk with highest textual overlap with answer sentence surrounding the citation
            best_chunk = matching_chunks[0]
            best_overlap = 0.0

            for chk in matching_chunks:
                overlap = cls._compute_token_overlap(answer_text, chk.get("content", ""))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_chunk = chk

            # Source snippet (preview of first 150 chars)
            snippet = best_chunk.get("content", "")
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."

            validated_citations.append(
                CitationDTO(
                    citation_id=citation_id,
                    document_id=best_chunk.get("document_id", target_doc),
                    page_number=page_num,
                    chunk_id=best_chunk.get("chunk_id"),
                    cited_snippet=snippet,
                    is_valid=True,
                    validation_notes=f"Verified: Corresponds to stored passage on Page {page_num}.",
                    overlap_score=round(best_overlap, 3)
                )
            )

        return validated_citations
