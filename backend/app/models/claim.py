import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class ClaimVerification(Base):
    __tablename__ = "claim_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    claim_text = Column(Text, nullable=False)
    classification = Column(String(20), nullable=False, index=True)  # 'Supported', 'Contradicted', 'Unverified'
    confidence = Column(Float, nullable=False)
    premise_text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    reasoning = Column(Text, nullable=True)
    numerical_conflict = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="claims")
