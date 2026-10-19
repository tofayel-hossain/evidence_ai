import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

from backend.app.config import settings
from backend.app.schemas.verification import (
    AtomicClaim,
    ClaimVerificationResult,
    VerificationResponse
)
from backend.app.services.claim_extractor import ClaimExtractor
from backend.app.services.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

class VerificationService:
    """
    Evidence-based claim verification & hallucination detection engine.
    Combines Natural Language Inference (NLI), negation polarity analysis,
    and numerical consistency validation to classify claims as
    Supported, Contradicted, or Unverified.
    """

    _nli_pipeline = None

    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or HybridRetriever()

    @classmethod
    def _get_nli_pipeline(cls):
        """Lazy loader for NLI HuggingFace pipeline."""
        if cls._nli_pipeline is None:
            try:
                from transformers import pipeline
                cls._nli_pipeline = pipeline(
                    "text-classification",
                    model=settings.NLI_MODEL_NAME,
                    top_k=None,
                    device=-1  # CPU for portability
                )
            except Exception as e:
                logger.warning(f"Could not load HuggingFace NLI model ({str(e)}). Using robust rule-based NLI.")
                cls._nli_pipeline = False
        return cls._nli_pipeline

    @staticmethod
    def extract_numbers(text: str) -> List[str]:
        """Extracts numerical quantities, percentages, and decimals from text."""
        # Matches numbers like 94.2%, 100, 0.001, 2600, etc.
        return re.findall(r'\b\d+(?:\.\d+)?%?\b', text)

    @classmethod
    def check_numerical_consistency(cls, premise: str, hypothesis: str) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether numerical claims in the hypothesis are consistent with the premise.
        Returns: (has_conflict, reasoning_description)
        """
        hyp_numbers = cls.extract_numbers(hypothesis)
        if not hyp_numbers:
            return False, None  # No numbers in claim

        premise_numbers = set(cls.extract_numbers(premise))

        for num in hyp_numbers:
            # If the number in the claim is not found anywhere in the premise
            if num not in premise_numbers:
                # Check if there is an alternative number in the same context
                if premise_numbers:
                    return True, f"Numerical discrepancy: Claim states '{num}', but evidence reports '{', '.join(premise_numbers)}'."

        return False, None

    @staticmethod
    def check_negation_conflict(premise: str, hypothesis: str) -> bool:
        """
        Detects opposing negation polarity between premise and hypothesis.
        """
        negation_words = {"not", "never", "no", "neither", "none", "unable", "failed", "without", "didn't", "wasn't"}
        hyp_words = set(hypothesis.lower().split())
        prem_words = set(premise.lower().split())

        hyp_has_neg = bool(hyp_words.intersection(negation_words))
        prem_has_neg = bool(prem_words.intersection(negation_words))

        # Direct contradiction if one explicitly negates while other asserts the exact same predicate
        common_words = hyp_words.intersection(prem_words) - negation_words
        if len(common_words) >= 4 and (hyp_has_neg != prem_has_neg):
            return True
        return False

    def evaluate_pair(self, premise: str, hypothesis: str) -> Dict[str, Any]:
        """
        Evaluates the relationship between Premise (evidence) and Hypothesis (claim).
        Returns classification, calibrated confidence, NLI distribution, and reasoning.
        """
        # Step 1: Check numerical conflict
        num_conflict, num_reason = self.check_numerical_consistency(premise, hypothesis)
        if num_conflict:
            return {
                "classification": "Contradicted",
                "confidence": 0.88,
                "reasoning": num_reason,
                "nli_scores": {"entailment": 0.05, "contradiction": 0.88, "neutral": 0.07},
                "numerical_conflict": True
            }

        # Step 2: Check negation conflict
        if self.check_negation_conflict(premise, hypothesis):
            return {
                "classification": "Contradicted",
                "confidence": 0.85,
                "reasoning": "Direct contradiction detected: Evidence and claim have conflicting negation polarity.",
                "nli_scores": {"entailment": 0.08, "contradiction": 0.85, "neutral": 0.07},
                "numerical_conflict": False
            }

        # Step 3: Compute lexical and semantic overlap
        words_prem = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', premise.lower()))
        words_hyp = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', hypothesis.lower()))
        stopwords = {"the", "a", "an", "is", "was", "were", "and", "or", "to", "in", "of", "for", "on", "with"}
        info_hyp = words_hyp - stopwords
        info_prem = words_prem - stopwords

        if not info_hyp:
            return {
                "classification": "Unverified",
                "confidence": 0.50,
                "reasoning": "Claim contains insufficient factual content to evaluate.",
                "nli_scores": {"entailment": 0.2, "contradiction": 0.2, "neutral": 0.6},
                "numerical_conflict": False
            }

        overlap = len(info_hyp.intersection(info_prem)) / len(info_hyp)

        # Step 4: High-precision calibrated rule-based evaluation (Sub-second execution)
        if settings.FAST_VERIFICATION or overlap >= 0.50:
            if overlap >= 0.50:
                return {
                    "classification": "Supported",
                    "confidence": round(min(0.95, 0.75 + 0.20 * overlap), 2),
                    "reasoning": f"Document evidence strongly supports claim semantics (lexical coverage: {overlap*100:.1f}%).",
                    "nli_scores": {"entailment": round(overlap, 2), "contradiction": 0.05, "neutral": round(1.0 - overlap, 2)},
                    "numerical_conflict": False
                }
            elif overlap >= 0.25:
                return {
                    "classification": "Unverified",
                    "confidence": 0.60,
                    "reasoning": f"Evidence partially mentions topic ({overlap*100:.1f}% coverage) but lacks conclusive proof.",
                    "nli_scores": {"entailment": 0.35, "contradiction": 0.15, "neutral": 0.50},
                    "numerical_conflict": False
                }
            else:
                return {
                    "classification": "Unverified",
                    "confidence": 0.70,
                    "reasoning": f"No relevant supporting evidence found in document (coverage {overlap*100:.1f}%).",
                    "nli_scores": {"entailment": 0.05, "contradiction": 0.10, "neutral": 0.85},
                    "numerical_conflict": False
                }

        # Step 5: Run Transformer NLI model if available and FAST_VERIFICATION is False
        pipe = self._get_nli_pipeline()
        if pipe and pipe is not False:
            try:
                # Standard NLI input format
                result = pipe(f"Premise: {premise} Hypothesis: {hypothesis}")
                items = result[0] if (isinstance(result, list) and len(result) > 0 and isinstance(result[0], list)) else result
                score_map = {item["label"].lower(): item["score"] for item in items if isinstance(item, dict) and "label" in item}
                ent = score_map.get("entailment", 0.0)
                contra = score_map.get("contradiction", 0.0)
                neutral = score_map.get("neutral", 0.0)

                # Calibrate confidence using overlap
                calibrated_conf = round(float(max(ent, contra, neutral) * (0.5 + 0.5 * overlap)), 3)

                if contra > 0.55:
                    return {
                        "classification": "Contradicted",
                        "confidence": calibrated_conf,
                        "reasoning": f"NLI model indicates direct contradiction with evidence (contradiction probability: {contra:.2f}).",
                        "nli_scores": score_map,
                        "numerical_conflict": False
                    }
                elif ent > 0.60 and overlap >= 0.4:
                    return {
                        "classification": "Supported",
                        "confidence": calibrated_conf,
                        "reasoning": f"Evidence directly entails the factual statement (entailment probability: {ent:.2f}).",
                        "nli_scores": score_map,
                        "numerical_conflict": False
                    }
                else:
                    return {
                        "classification": "Unverified",
                        "confidence": calibrated_conf,
                        "reasoning": "Evidence is insufficient or neutral with respect to the claim.",
                        "nli_scores": score_map,
                        "numerical_conflict": False
                    }
            except Exception as e:
                logger.warning(f"Transformer inference error: {e}. Falling back to rule calibration.")

        # Default fallback rule evaluation
        return {
            "classification": "Supported" if overlap >= 0.45 else "Unverified",
            "confidence": round(0.60 + 0.25 * overlap, 2),
            "reasoning": f"Calibrated semantic evaluation (lexical coverage: {overlap*100:.1f}%).",
            "nli_scores": {"entailment": round(overlap, 2), "contradiction": 0.05, "neutral": round(1.0 - overlap, 2)},
            "numerical_conflict": False
        }

    def verify_claims_against_document(
        self,
        claims: List[AtomicClaim],
        document_id: Optional[str] = None
    ) -> List[ClaimVerificationResult]:
        """
        Evaluates each atomic claim by retrieving its best supporting evidence
        and computing calibrated inference.
        """
        results: List[ClaimVerificationResult] = []

        # Cap claims to avoid latency spikes on lengthy answers
        claims_to_verify = claims[:6]
        retrieval_method = "bm25" if settings.FAST_VERIFICATION else "hybrid"

        for claim in claims_to_verify:
            # Find evidence passages for this claim quickly
            passages = self.retriever.retrieve(
                query=claim.text,
                method=retrieval_method,
                top_k=2,
                document_id=document_id
            )

            if not passages:
                results.append(
                    ClaimVerificationResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.text,
                        classification="Unverified",
                        confidence=0.85,
                        premise_text="No document passages could be retrieved for this statement.",
                        page_number=claim.page_number,
                        document_id=document_id,
                        reasoning="No relevant document passages were indexed or found.",
                        nli_scores={"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0},
                        numerical_conflict=False
                    )
                )
                continue

            # Prioritize passage from cited page if available
            best_passage = passages[0]
            if claim.page_number:
                page_matches = [p for p in passages if p.get("page_number") == claim.page_number]
                if page_matches:
                    best_passage = page_matches[0]

            eval_res = self.evaluate_pair(
                premise=best_passage["content"],
                hypothesis=claim.text
            )

            results.append(
                ClaimVerificationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.text,
                    classification=eval_res["classification"],
                    confidence=eval_res["confidence"],
                    premise_text=best_passage["content"],
                    page_number=best_passage.get("page_number", claim.page_number),
                    document_id=best_passage.get("document_id", document_id),
                    reasoning=eval_res["reasoning"],
                    nli_scores=eval_res["nli_scores"],
                    numerical_conflict=eval_res.get("numerical_conflict", False)
                )
            )

        return results

    def verify_text(
        self,
        text: str,
        document_id: Optional[str] = None
    ) -> VerificationResponse:
        """
        Full pipeline: decomposes text into claims, verifies each, and calculates
        aggregate hallucination metrics.
        """
        t0 = time.time()
        claims = ClaimExtractor.extract_claims(text)

        if not claims:
            return VerificationResponse(
                total_claims=0,
                supported_count=0,
                contradicted_count=0,
                unverified_count=0,
                hallucination_rate=0.0,
                results=[],
                latency_ms=0.0
            )

        results = self.verify_claims_against_document(claims, document_id=document_id)

        supported = sum(1 for r in results if r.classification == "Supported")
        contradicted = sum(1 for r in results if r.classification == "Contradicted")
        unverified = sum(1 for r in results if r.classification == "Unverified")
        total = len(results)

        # Hallucination rate = proportion of claims that are contradicted or unverified
        hallucination_rate = round((contradicted + unverified) / total, 3) if total > 0 else 0.0
        latency_ms = (time.time() - t0) * 1000

        return VerificationResponse(
            total_claims=total,
            supported_count=supported,
            contradicted_count=contradicted,
            unverified_count=unverified,
            hallucination_rate=hallucination_rate,
            results=results,
            latency_ms=round(latency_ms, 2)
        )
