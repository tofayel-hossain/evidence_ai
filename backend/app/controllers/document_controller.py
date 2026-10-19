import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.document import Document
from backend.app.models.chunk import DocumentChunk
from backend.app.schemas.document import DocumentResponse, DocumentChunkDTO
from backend.app.services.pdf_service import PDFService, PDFProcessingError
from backend.app.services.chunking_service import ChunkingService
from backend.app.services.hybrid_retriever import shared_vector_index, shared_bm25_index
from backend.app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])

vector_index = shared_vector_index
bm25_index = shared_bm25_index
chunking_service = ChunkingService(
    chunk_size=settings.DEFAULT_CHUNK_SIZE,
    chunk_overlap=settings.DEFAULT_CHUNK_OVERLAP
)

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads a research paper in PDF format.
    Validates file integrity, extracts page-by-page text, chunks text,
    indexes into FAISS and BM25, and persists all records in PostgreSQL.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    safe_filename = f"{doc_id}_{os.path.basename(file.filename)}"
    destination_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    # Save uploaded file to disk
    try:
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file on disk: {str(e)}"
        )

    # Validate and extract text using PyMuPDF
    try:
        extract_result = PDFService.extract_text_and_metadata(
            file_path=destination_path,
            original_filename=file.filename
        )
    except PDFProcessingError as e:
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction failed: {str(e)}")

    if not extract_result.success:
        if os.path.exists(destination_path):
            os.remove(destination_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=extract_result.error_message)

    file_size = os.path.getsize(destination_path)
    title = extract_result.metadata.get("title") or file.filename
    author = extract_result.metadata.get("author") or "Unknown"

    # Create Document record in database
    db_doc = Document(
        id=doc_id,
        user_id=current_user.id,
        filename=file.filename,
        file_path=destination_path,
        file_size_bytes=file_size,
        page_count=extract_result.page_count,
        title=title,
        author=author,
        status="scanned_warning" if extract_result.is_scanned else "indexed",
        error_message=extract_result.error_message
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # If document has extractable text, chunk and index it
    if not extract_result.is_scanned and extract_result.pages:
        try:
            chunks = chunking_service.chunk_document(extract_result.pages, document_id=doc_id)

            # Index into FAISS and BM25
            vector_index.add_chunks(chunks)
            bm25_index.add_chunks(chunks)

            # Persist chunks into PostgreSQL
            for c in chunks:
                db_chunk = DocumentChunk(
                    id=c.chunk_id,
                    document_id=doc_id,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    content=c.content,
                    token_count=c.token_count,
                    start_char=c.start_char,
                    end_char=c.end_char
                )
                db.add(db_chunk)
            db.commit()
        except Exception as e:
            db.delete(db_doc)
            db.commit()
            if os.path.exists(destination_path):
                try:
                    os.remove(destination_path)
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Chunking and indexing failed: {str(e)}"
            )

    return db_doc

@router.get("", response_model=List[DocumentResponse])
def list_user_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all research documents owned by the authenticated user."""
    return db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc()).all()

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_detail(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves metadata for a specific document with ownership verification."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")
    return doc

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkDTO])
def get_document_chunks(
    document_id: str,
    page_number: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all indexed chunks for a document, optionally filtered by page number."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

    query = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)
    if page_number is not None:
        query = query.filter(DocumentChunk.page_number == page_number)
    return query.order_by(DocumentChunk.chunk_index.asc()).all()

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a document and synchronizes all persistent data:
    1. Removes database document and cascaded chunks.
    2. Synchronizes FAISS vector index (removes embeddings).
    3. Synchronizes BM25 keyword index (removes corpus tokens).
    4. Removes original file from disk.
    """
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or access denied.")

    # Remove indices
    vector_index.delete_document(document_id)
    bm25_index.delete_document(document_id)

    # Remove physical file if exists
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    # Cascade delete in database
    db.delete(doc)
    db.commit()

    return {"success": True, "message": f"Document {document_id} and all indexed evidence were deleted."}
