import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Citation(Base):
    __tablename__ = "citations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    chunk_id = Column(String(64), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    page_number = Column(Integer, nullable=False)
    cited_snippet = Column(Text, nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)
    validation_notes = Column(Text, nullable=True)
    overlap_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="citations")
