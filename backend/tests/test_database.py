import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models.user import User
from backend.app.models.document import Document
from backend.app.models.chunk import DocumentChunk
from backend.app.models.conversation import Conversation, Message
from backend.app.models.citation import Citation
from backend.app.models.claim import ClaimVerification
from backend.app.services.auth_service import AuthService

@pytest.fixture
def db_session():
    # In-memory SQLite for instantaneous, isolated tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    yield session
    session.close()

def test_user_creation_and_auth(db_session):
    hashed = AuthService.hash_password("SuperSecret123!")
    user = User(email="researcher@evidenceai.org", hashed_password=hashed)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "researcher@evidenceai.org"
    assert AuthService.verify_password("SuperSecret123!", user.hashed_password) is True
    assert AuthService.verify_password("WrongPassword", user.hashed_password) is False

    # JWT Token roundtrip
    token = AuthService.create_access_token(user.id, user.email)
    payload = AuthService.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user.id
    assert payload["email"] == user.email

def test_document_and_chunks_relationships(db_session):
    user = User(email="test@evidenceai.org", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    doc = Document(
        user_id=user.id,
        filename="paper.pdf",
        file_path="/tmp/paper.pdf",
        file_size_bytes=1024,
        page_count=2,
        title="Sample Paper"
    )
    db_session.add(doc)
    db_session.commit()

    chunk1 = DocumentChunk(
        id=f"{doc.id}_p1_c0",
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Abstract passage on deep learning.",
        token_count=5,
        start_char=0,
        end_char=35
    )
    db_session.add(chunk1)
    db_session.commit()

    assert len(doc.chunks) == 1
    assert doc.chunks[0].id == f"{doc.id}_p1_c0"
    assert doc.chunks[0].page_number == 1

def test_conversation_and_citations(db_session):
    user = User(email="chat@evidenceai.org", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    conv = Conversation(user_id=user.id, title="Research Discussion")
    db_session.add(conv)
    db_session.commit()

    msg = Message(conversation_id=conv.id, role="assistant", content="The model achieved 90% accuracy [Page 1].")
    db_session.add(msg)
    db_session.commit()

    citation = Citation(
        message_id=msg.id,
        page_number=1,
        cited_snippet="90% accuracy on ImageNet.",
        is_valid=True,
        overlap_score=0.85
    )
    db_session.add(citation)
    db_session.commit()

    assert len(msg.citations) == 1
    assert msg.citations[0].page_number == 1
    assert msg.citations[0].is_valid is True

def test_cascade_delete(db_session):
    user = User(email="cascade@evidenceai.org", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    doc = Document(
        user_id=user.id,
        filename="del.pdf",
        file_path="/tmp/del.pdf",
        file_size_bytes=500
    )
    db_session.add(doc)
    db_session.commit()

    chunk = DocumentChunk(
        id=f"{doc.id}_p1_c0",
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Test content",
        token_count=2,
        start_char=0,
        end_char=12
    )
    db_session.add(chunk)
    db_session.commit()

    # Delete Document should cascade to chunks
    db_session.delete(doc)
    db_session.commit()

    remaining_chunks = db_session.query(DocumentChunk).filter_by(document_id=doc.id).all()
    assert len(remaining_chunks) == 0
