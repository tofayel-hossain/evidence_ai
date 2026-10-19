import pytest
from unittest.mock import patch
from backend.app.services.claim_extractor import ClaimExtractor
from backend.app.services.verification_service import VerificationService

@pytest.fixture(autouse=True)
def disable_remote_nli_download():
    """Ensure fast, deterministic unit test execution without remote model downloads."""
    with patch("backend.app.services.verification_service.VerificationService._get_nli_pipeline", return_value=False):
        yield

def test_claim_extractor():
    text = (
        "According to the authors, the model achieved 94.2% accuracy [Page 2]. "
        "Furthermore, we observe that Adam optimizer was used with learning rate 0.001 [Page 3]."
    )
    claims = ClaimExtractor.extract_claims(text)

    assert len(claims) == 2
    assert "94.2% accuracy" in claims[0].text
    assert claims[0].page_number == 2
    assert "According to the authors" not in claims[0].text
    assert "[Page 2]" not in claims[0].text

    assert "Adam optimizer was used" in claims[1].text
    assert claims[1].page_number == 3
    assert "we observe that" not in claims[1].text
    assert "Furthermore" not in claims[1].text

def test_numerical_conflict_detection():
    service = VerificationService()
    premise = "The proposed network achieved a Top-1 accuracy of 88.5% on ImageNet."
    hypothesis = "The network achieved 98.5% accuracy on ImageNet."

    eval_result = service.evaluate_pair(premise, hypothesis)
    assert eval_result["classification"] == "Contradicted"
    assert eval_result["numerical_conflict"] is True
    assert "Numerical discrepancy" in eval_result["reasoning"]

def test_negation_conflict_detection():
    service = VerificationService()
    premise = "The experimental architecture did not use dropout during pre-training."
    hypothesis = "The experimental architecture used dropout during pre-training."

    eval_result = service.evaluate_pair(premise, hypothesis)
    assert eval_result["classification"] == "Contradicted"
    assert "negation" in eval_result["reasoning"].lower()

def test_supported_claim_evaluation():
    service = VerificationService()
    premise = "We fine-tuned the model using the AdamW optimizer with a learning rate of 0.0001."
    hypothesis = "The model was fine-tuned with AdamW optimizer at learning rate 0.0001."

    eval_result = service.evaluate_pair(premise, hypothesis)
    assert eval_result["classification"] == "Supported"
    assert eval_result["confidence"] >= 0.70

def test_unverified_claim_evaluation():
    service = VerificationService()
    premise = "We fine-tuned the model using the AdamW optimizer."
    hypothesis = "The researchers deployed the system on a fleet of NASA satellites."

    eval_result = service.evaluate_pair(premise, hypothesis)
    assert eval_result["classification"] == "Unverified"
    assert "insufficient" in eval_result["reasoning"].lower() or "no relevant" in eval_result["reasoning"].lower()
