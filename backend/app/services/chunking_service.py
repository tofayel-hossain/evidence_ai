import re
import uuid
from typing import List, Dict, Any
from backend.app.schemas.document import ExtractedPage

class TextChunk:
    """Represents an atomic indexed text unit with exact provenance metadata."""
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        page_number: int,
        chunk_index: int,
        content: str,
        token_count: int,
        start_char: int,
        end_char: int,
        metadata: Dict[str, Any] = None
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.page_number = page_number
        self.chunk_index = chunk_index
        self.content = content
        self.token_count = token_count
        self.start_char = start_char
        self.end_char = end_char
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextChunk":
        return cls(
            chunk_id=data["chunk_id"],
            document_id=data["document_id"],
            page_number=data["page_number"],
            chunk_index=data["chunk_index"],
            content=data["content"],
            token_count=data["token_count"],
            start_char=data["start_char"],
            end_char=data["end_char"],
            metadata=data.get("metadata", {})
        )

class ChunkingService:
    """
    Sentence-aware recursive text splitter that preserves exact document
    and page-level provenance without corrupting sentence structures.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError(f"Chunk overlap ({chunk_overlap}) must be strictly smaller than chunk size ({chunk_size}).")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """
        Splits text into sentences using punctuation boundaries (.!?),
        preserving abbreviations reasonably.
        """
        sentence_end = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')
        sentences = sentence_end.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_page(self, page: ExtractedPage, document_id: str, starting_index: int = 0) -> List[TextChunk]:
        """
        Chunks a single page while guaranteeing that all returned chunks
        remain anchored to the source page number.
        """
        text = page.text
        if not text or len(text.strip()) == 0:
            return []

        chunks: List[TextChunk] = []
        sentences = self._split_into_sentences(text)
        if not sentences:
            sentences = [text]

        current_sentences: List[str] = []
        current_len = 0
        chunk_idx = starting_index

        for sentence in sentences:
            sentence_len = len(sentence)

            # If adding this sentence exceeds chunk size and we already have content
            if current_len + sentence_len > self.chunk_size and current_sentences:
                chunk_text = " ".join(current_sentences)
                start_char = text.find(chunk_text[:30]) if len(chunk_text) >= 30 else text.find(chunk_text)
                if start_char == -1:
                    start_char = 0
                end_char = start_char + len(chunk_text)

                chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        page_number=page.page_number,
                        chunk_index=chunk_idx,
                        content=chunk_text,
                        token_count=len(chunk_text.split()),
                        start_char=start_char,
                        end_char=end_char
                    )
                )
                chunk_idx += 1

                # Carry over overlap
                overlap_sentences: List[str] = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    if overlap_len + len(s) <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break

                current_sentences = overlap_sentences + [sentence]
                current_len = sum(len(s) for s in current_sentences) + len(current_sentences) - 1
            else:
                current_sentences.append(sentence)
                current_len += sentence_len + 1

        # Final remaining chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            start_char = text.find(chunk_text[:30]) if len(chunk_text) >= 30 else text.find(chunk_text)
            if start_char == -1:
                start_char = 0
            end_char = start_char + len(chunk_text)

            chunk_id = f"{document_id}_p{page.page_number}_c{chunk_idx}"
            chunks.append(
                TextChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    page_number=page.page_number,
                    chunk_index=chunk_idx,
                    content=chunk_text,
                    token_count=len(chunk_text.split()),
                    start_char=start_char,
                    end_char=end_char
                )
            )

        return chunks

    def chunk_document(self, pages: List[ExtractedPage], document_id: str) -> List[TextChunk]:
        """
        Chunks all pages of a document while preserving 1-indexed page boundaries.
        """
        all_chunks: List[TextChunk] = []
        global_idx = 0
        for page in pages:
            page_chunks = self.chunk_page(page, document_id, starting_index=global_idx)
            all_chunks.extend(page_chunks)
            global_idx += len(page_chunks)
        return all_chunks
