import pytest
import os
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from pathlib import Path
from backend.app.services.pdf_service import PDFService, PDFProcessingError

@pytest.fixture
def temp_pdf_dir(tmp_path):
    pdf_dir = tmp_path / "test_pdfs"
    pdf_dir.mkdir()
    return pdf_dir

def create_synthetic_pdf(filepath: str, pages_text: list[str], metadata: dict = None):
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text.strip():
            page.insert_text((50, 72), text)
    if metadata:
        doc.set_metadata(metadata)
    doc.save(filepath)
    doc.close()

def test_extract_valid_multipage_pdf(temp_pdf_dir):
    pdf_path = str(temp_pdf_dir / "sample_research.pdf")
    pages_content = [
        "Abstract: We propose EvidenceAI, a robust hallucination detection framework. Page 1 introduces our benchmark.",
        "Section 2: Methodology. We utilize hybrid retrieval combining BM25 Okapi and dense Sentence Transformers.",
        "Section 3: Experimental Results. On the benchmark dataset, the system achieved 94.2% precision on claim verification."
    ]
    meta = {"title": "EvidenceAI Research Paper", "author": "Research Team"}
    create_synthetic_pdf(pdf_path, pages_content, meta)

    result = PDFService.extract_text_and_metadata(pdf_path, "sample_research.pdf")

    assert result.success is True
    assert result.page_count == 3
    assert len(result.pages) == 3
    assert result.is_scanned is False
    assert result.metadata["title"] == "EvidenceAI Research Paper"
    assert result.metadata["author"] == "Research Team"

    # Verify 1-indexed page mapping
    assert result.pages[0].page_number == 1
    assert "EvidenceAI, a robust hallucination detection framework" in result.pages[0].text
    assert result.pages[1].page_number == 2
    assert "Section 2: Methodology" in result.pages[1].text
    assert result.pages[2].page_number == 3
    assert "94.2% precision" in result.pages[2].text

def test_clean_text_normalization():
    dirty_text = "EvidenceAI   \t\t\n\n\n\x00introduces  hallucination  \n\n  detection."
    cleaned = PDFService.clean_text(dirty_text)
    assert "\x00" not in cleaned
    assert "EvidenceAI" in cleaned
    assert "   " not in cleaned
    assert "  " not in cleaned

def test_invalid_file_header(temp_pdf_dir):
    fake_pdf = temp_pdf_dir / "fake.pdf"
    fake_pdf.write_bytes(b"This is not a real PDF header")

    with pytest.raises(PDFProcessingError) as exc_info:
        PDFService.extract_text_and_metadata(str(fake_pdf), "fake.pdf")
    assert "Invalid file header" in str(exc_info.value)

def test_invalid_extension(temp_pdf_dir):
    txt_file = temp_pdf_dir / "document.txt"
    txt_file.write_bytes(b"%PDF-1.4 text file")

    with pytest.raises(PDFProcessingError) as exc_info:
        PDFService.extract_text_and_metadata(str(txt_file), "document.txt")
    assert "Unsupported file format" in str(exc_info.value)

def test_scanned_pdf_detection(temp_pdf_dir):
    scanned_pdf = str(temp_pdf_dir / "scanned.pdf")
    # 2 pages with zero text
    create_synthetic_pdf(scanned_pdf, ["", ""])

    result = PDFService.extract_text_and_metadata(scanned_pdf, "scanned.pdf")
    assert result.success is True
    assert result.page_count == 2
    assert result.is_scanned is True
    assert result.pages[0].is_empty is True
    assert result.pages[1].is_empty is True
