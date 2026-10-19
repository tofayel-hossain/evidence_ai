import os
import re
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.app.config import settings
from backend.app.schemas.document import ExtractionResult, ExtractedPage

class PDFProcessingError(Exception):
    """Custom exception raised during PDF parsing failures."""
    pass

class PDFService:
    """
    Robust PDF text extraction, validation, and metadata extraction engine.
    Uses PyMuPDF (fitz) to guarantee high-speed, page-accurate extraction.
    """

    @staticmethod
    def validate_file(file_path: str, original_filename: str) -> None:
        """
        Validates file existence, extension, magic bytes, and size.
        """
        path = Path(file_path)
        if not path.is_file():
            raise PDFProcessingError(f"File not found: {file_path}")

        # Size check
        size_bytes = path.stat().st_size
        if size_bytes == 0:
            raise PDFProcessingError("Uploaded file is empty (0 bytes).")
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            raise PDFProcessingError(
                f"File size ({size_bytes / (1024*1024):.2f}MB) exceeds maximum allowed limit ({settings.MAX_UPLOAD_SIZE_MB}MB)."
            )

        # Extension check
        if not original_filename.lower().endswith(".pdf"):
            raise PDFProcessingError(f"Unsupported file format: {original_filename}. Only PDF files are supported.")

        # Magic number check (PDF header %PDF-)
        try:
            with open(path, "rb") as f:
                header = f.read(5)
                if not header.startswith(b"%PDF-"):
                    raise PDFProcessingError("Invalid file header: File is not a valid PDF document.")
        except Exception as e:
            if isinstance(e, PDFProcessingError):
                raise
            raise PDFProcessingError(f"Failed to read file header: {str(e)}")

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Normalizes whitespace while preserving paragraphs and sentence boundaries.
        Removes non-printable/control characters.
        """
        if not text:
            return ""
        # Remove null characters and non-printable control characters (except newline, tab)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize multiple spaces and tabs to a single space
        text = re.sub(r"[ \t]+", " ", text)
        # Normalize multiple newlines to double newline (paragraph boundary)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    @classmethod
    def extract_text_and_metadata(cls, file_path: str, original_filename: str) -> ExtractionResult:
        """
        Extracts page-by-page text, document metadata, and structural diagnostics.
        Guarantees that page numbers are 1-indexed and exact.
        """
        cls.validate_file(file_path, original_filename)

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise PDFProcessingError(f"PyMuPDF failed to open PDF document: {str(e)}")

        try:
            # Check for encryption
            if doc.is_encrypted:
                doc.close()
                return ExtractionResult(
                    success=False,
                    filename=original_filename,
                    page_count=0,
                    error_message="Document is password protected or encrypted and cannot be processed."
                )

            page_count = len(doc)
            if page_count == 0:
                doc.close()
                return ExtractionResult(
                    success=False,
                    filename=original_filename,
                    page_count=0,
                    error_message="Document contains 0 pages."
                )

            # Metadata extraction
            raw_meta = doc.metadata or {}
            metadata: Dict[str, Any] = {
                "title": raw_meta.get("title") or Path(original_filename).stem,
                "author": raw_meta.get("author") or "Unknown",
                "subject": raw_meta.get("subject") or "",
                "creator": raw_meta.get("creator") or "",
                "producer": raw_meta.get("producer") or "",
                "creation_date": raw_meta.get("creationDate") or "",
                "mod_date": raw_meta.get("modDate") or "",
                "page_count": page_count
            }

            extracted_pages: List[ExtractedPage] = []
            total_extracted_chars = 0

            for page_idx in range(page_count):
                page_num = page_idx + 1  # 1-indexed page numbering
                page = doc.load_page(page_idx)
                raw_page_text = page.get_text("text") or ""
                cleaned_page_text = cls.clean_text(raw_page_text)
                char_count = len(cleaned_page_text)
                total_extracted_chars += char_count

                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=cleaned_page_text,
                        char_count=char_count,
                        is_empty=(char_count == 0)
                    )
                )

            # Intelligent perception of Title & Authors directly from Page 1 text
            if extracted_pages and extracted_pages[0].text:
                p1_lines = [l.strip() for l in extracted_pages[0].text.splitlines() if l.strip() and l.strip() != '|']
                clean_lines = [l for l in p1_lines if not re.match(r'^(?:ieee|arxiv|conf|proc|vol|no|page|\d+$|http|doi:)', l, re.IGNORECASE)]
                if clean_lines:
                    affil_idx = -1
                    for i, l in enumerate(clean_lines[:12]):
                        if re.search(r'\b(?:abstract|index terms)\b', l, re.IGNORECASE):
                            break
                        if re.search(r'(?:department|university|college|email|institute|school|@)', l, re.IGNORECASE):
                            affil_idx = i
                            break

                    if affil_idx > 1:
                        detected_title = " ".join(clean_lines[:affil_idx - 1]).strip()
                        detected_author = clean_lines[affil_idx - 1].strip().rstrip('*†‡')
                    elif affil_idx == 1:
                        detected_title = clean_lines[0].strip()
                        detected_author = "Unknown"
                    else:
                        detected_title = clean_lines[0].strip()
                        detected_author = clean_lines[1].strip().rstrip('*†‡') if len(clean_lines) > 1 else "Unknown"

                    raw_title = (raw_meta.get("title") or "").strip()
                    if len(detected_title) >= 10 and (not raw_title or raw_title.lower() in ("untitled", "microsoft word", Path(original_filename).stem.lower())):
                        metadata["title"] = detected_title

                    if detected_author and (not raw_meta.get("author") or raw_meta.get("author") == "Unknown"):
                        metadata["author"] = detected_author

            # Detect scanned PDFs (e.g. average less than 30 chars per page across document)
            is_scanned = (total_extracted_chars < (page_count * 30))

            return ExtractionResult(
                success=True,
                filename=original_filename,
                page_count=page_count,
                pages=extracted_pages,
                metadata=metadata,
                is_scanned=is_scanned,
                error_message="Warning: Document appears to be a scanned image with minimal or no extractable digital text." if is_scanned else None
            )

        except Exception as e:
            raise PDFProcessingError(f"Error during document extraction: {str(e)}")
        finally:
            if doc and not doc.is_closed:
                doc.close()
