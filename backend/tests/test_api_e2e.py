import io
import uuid
import pytest
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app
from backend.app.database import engine, Base

def create_synthetic_pdf_bytes(title: str, text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), f"{title}\n\n{text}")
    data = doc.tobytes()
    doc.close()
    return data

@pytest.fixture(scope="module", autouse=True)
def setup_database_and_mocks():
    """Ensure database tables exist and mock heavy ML models for fast test execution."""
    Base.metadata.create_all(bind=engine)
    with patch("backend.app.services.verification_service.VerificationService._get_nli_pipeline", return_value=False):
        yield

def test_health_check_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["project"] == "EvidenceAI"

def test_auth_workflow():
    with TestClient(app) as client:
        unique_email = f"user_{uuid.uuid4().hex[:8]}@evidenceai.org"
        reg_resp = client.post(
            "/api/v1/auth/register",
            json={"email": unique_email, "password": "securepassword123"}
        )
        assert reg_resp.status_code == 201

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "securepassword123"}
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"

def test_document_lifecycle_and_rag():
    with TestClient(app) as client:
        pdf_bytes = create_synthetic_pdf_bytes(
            title="EvidenceAI System Overview",
            text="EvidenceAI incorporates hybrid retrieval using BM25 Okapi and FAISS dense embeddings. "
                 "The system verifies factual claims using Natural Language Inference."
        )

        # 1. Upload
        files = {"file": ("overview.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_resp = client.post("/api/v1/documents/upload", files=files)
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = doc_data["id"]
        assert doc_data["page_count"] == 1
        assert doc_data["filename"] == "overview.pdf"

        # 2. List documents
        list_resp = client.get("/api/v1/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert any(d["id"] == doc_id for d in docs)

        # 3. Query RAG
        query_resp = client.post(
            "/api/v1/query",
            json={
                "question": "What retrieval methods does EvidenceAI incorporate?",
                "document_id": doc_id,
                "retrieval_method": "hybrid",
                "top_k": 3
            }
        )
        assert query_resp.status_code == 200
        q_data = query_resp.json()
        assert q_data["has_sufficient_evidence"] is True
        assert len(q_data["retrieved_passages"]) > 0

        # 4. Verify Claims
        verify_resp = client.post(
            "/api/v1/verify",
            json={
                "text": "EvidenceAI incorporates hybrid retrieval with BM25 Okapi and FAISS dense embeddings [Page 1].",
                "document_id": doc_id
            }
        )
        assert verify_resp.status_code == 200
        v_data = verify_resp.json()
        assert v_data["total_claims"] >= 1
        assert v_data["supported_count"] >= 1

        # 5. Delete Document
        del_resp = client.delete(f"/api/v1/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

