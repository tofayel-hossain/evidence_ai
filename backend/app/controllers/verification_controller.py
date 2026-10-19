from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.document import Document
from backend.app.schemas.verification import VerificationRequest, VerificationResponse
from backend.app.services.verification_service import VerificationService
from backend.app.services.hybrid_retriever import shared_retriever
from backend.app.controllers.auth_controller import get_current_user

router = APIRouter(prefix="/verify", tags=["Hallucination Verification"])

verification_service = VerificationService(retriever=shared_retriever)

@router.post("", response_model=VerificationResponse)
def verify_answer_claims(
    request: VerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Decomposes an answer or claim into atomic factual propositions,
    retrieves source evidence, checks numerical and negation consistency,
    and returns fine-grained Supported / Contradicted / Unverified labels.
    """
    if request.document_id:
        doc = db.query(Document).filter(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        ).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced document not found or access denied."
            )

    response = verification_service.verify_text(
        text=request.text,
        document_id=request.document_id
    )
    return response
