from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.document import Document
from backend.app.models.conversation import Conversation, Message
from backend.app.models.citation import Citation
from backend.app.schemas.query import QueryRequest, QueryResponse
from backend.app.services.rag_service import RAGService
from backend.app.services.hybrid_retriever import shared_retriever
from backend.app.services.llm_service import LLMService
from backend.app.services.citation_service import CitationService
from backend.app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/query", tags=["Research Q&A"])

rag_service = RAGService(
    retriever=shared_retriever,
    llm_service=LLMService(),
    citation_service=CitationService()
)

@router.post("", response_model=QueryResponse)
def ask_question(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Answers research questions grounded strictly in retrieved document passages.
    Validates page citations against stored chunks and records conversation history.
    """
    max_page_count = None
    if request.document_id:
        doc = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        ).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced document not found or unauthorized access."
            )
        max_page_count = doc.page_count

    # Execute RAG pipeline
    response = rag_service.answer_question(request=request, max_page_count=max_page_count)

    # If conversation_id is provided, persist messages and citations
    if request.conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if conv:
            # User question message
            user_msg = Message(
                conversation_id=conv.id,
                role="user",
                content=request.question
            )
            db.add(user_msg)

            # Assistant answer message
            asst_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=response.answer,
                retrieval_method=response.retrieval_method_used,
                latency_ms=response.latency_ms
            )
            db.add(asst_msg)
            db.commit()
            db.refresh(asst_msg)

            # Persist citations
            for c in response.citations:
                db_citation = Citation(
                    message_id=asst_msg.id,
                    document_id=c.document_id,
                    chunk_id=c.chunk_id,
                    page_number=c.page_number,
                    cited_snippet=c.cited_snippet,
                    is_valid=c.is_valid,
                    validation_notes=c.validation_notes,
                    overlap_score=c.overlap_score
                )
                db.add(db_citation)
            db.commit()

    return response
