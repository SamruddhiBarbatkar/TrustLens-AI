import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.analysis.trust_assessment import analyze_trust_assessment


def analysis(
    analysis_type,
    result=None,
    status="COMPLETED",
    evidence_id=None
):
    return SimpleNamespace(
        analysis_type=analysis_type,
        result=result,
        status=status,
        evidence_id=evidence_id
    )


def uncertainty(
    sources=None,
    missing_evidence_count=0,
    completion_ratio=1.0
):
    return analysis(
        "UNCERTAINTY",
        {
            "uncertainty_sources": sources or [],
            "missing_evidence_count": missing_evidence_count,
            "analysis_completion_ratio": completion_ratio
        }
    )


def cross_evidence(conflict_count=0):
    return analysis(
        "CROSS_EVIDENCE",
        {
            "comparison_summary": {
                "match_count": 0,
                "conflict_count": conflict_count,
                "not_comparable_count": 0
            }
        }
    )


def assess(*results):
    claim = SimpleNamespace(evidence=[])
    run = SimpleNamespace(analysis_results=list(results))
    output = analyze_trust_assessment(claim, run)

    if output["status"] != "COMPLETED":
        raise AssertionError(output["message"])

    return output["result"]


class TrustAssessmentTests(unittest.TestCase):
    def test_clean_completed_signals_are_low_concern(self):
        result = assess(
            uncertainty(),
            cross_evidence(),
            analysis("FUSION", {}),
            analysis(
                "TAMPERING_DETECTION",
                {
                    "prediction": "AUTHENTIC",
                    "confidence": 0.9,
                    "model_available": True
                },
                evidence_id=1
            ),
            analysis(
                "AI_GENERATION",
                {
                    "prediction": "REAL",
                    "confidence": 0.9,
                    "model_available": True
                },
                evidence_id=1
            )
        )

        self.assertEqual(result["assessment"], "LOW_CONCERN")
        self.assertEqual(result["risk_signals"], [])

    def test_tampering_signal_requires_review(self):
        result = assess(
            uncertainty(),
            cross_evidence(),
            analysis(
                "TAMPERING_DETECTION",
                {"prediction": "TAMPERED", "confidence": 0.87},
                evidence_id=11
            )
        )

        self.assertEqual(result["assessment"], "REVIEW_NEEDED")
        self.assertEqual(
            result["risk_signals"][0]["type"],
            "TAMPERING_DETECTED"
        )
        self.assertEqual(result["risk_signals"][0]["evidence_id"], 11)

    def test_ai_generation_signal_requires_review(self):
        result = assess(
            uncertainty(),
            cross_evidence(),
            analysis(
                "AI_GENERATION",
                {"prediction": "AI_GENERATED", "confidence": 0.81},
                evidence_id=12
            )
        )

        self.assertEqual(result["assessment"], "REVIEW_NEEDED")
        self.assertEqual(
            result["risk_signals"][0]["type"],
            "AI_GENERATION_DETECTED"
        )

    def test_cross_evidence_conflict_requires_review(self):
        result = assess(
            uncertainty(),
            cross_evidence(conflict_count=2)
        )

        self.assertEqual(result["assessment"], "REVIEW_NEEDED")
        self.assertEqual(result["cross_evidence_conflict_count"], 2)
        self.assertEqual(
            result["risk_signals"][0]["type"],
            "CROSS_EVIDENCE_CONFLICT"
        )

    def test_missing_evidence_without_risk_is_inconclusive(self):
        result = assess(
            uncertainty(
                sources=["MISSING_REQUIRED_EVIDENCE"],
                missing_evidence_count=1,
                completion_ratio=0.8
            ),
            cross_evidence()
        )

        self.assertEqual(result["assessment"], "INCONCLUSIVE")

    def test_processing_error_without_risk_is_inconclusive(self):
        result = assess(
            uncertainty(
                sources=["ANALYSIS_ERRORS", "INCOMPLETE_PIPELINE"],
                completion_ratio=0.8
            ),
            cross_evidence()
        )

        self.assertEqual(result["assessment"], "INCONCLUSIVE")

    def test_model_unavailable_requires_review(self):
        result = assess(
            uncertainty(
                sources=[
                    "AI_GENERATION_ANALYSIS_UNAVAILABLE",
                    "INCOMPLETE_ANALYSIS"
                ],
                completion_ratio=0.9
            ),
            cross_evidence(),
            analysis(
                "AI_GENERATION",
                {"model_available": False},
                status="MODEL_UNAVAILABLE",
                evidence_id=14
            )
        )

        self.assertEqual(result["assessment"], "REVIEW_NEEDED")
        self.assertTrue(
            any("currently unavailable" in reason for reason in result["reasons"])
        )

    def test_detected_risk_takes_precedence_over_processing_error(self):
        result = assess(
            uncertainty(
                sources=["ANALYSIS_ERRORS", "INCOMPLETE_PIPELINE"],
                completion_ratio=0.8
            ),
            cross_evidence(),
            analysis(
                "AI_GENERATION",
                {"prediction": "AI_GENERATED", "confidence": 0.75},
                evidence_id=13
            )
        )

        self.assertEqual(result["assessment"], "REVIEW_NEEDED")
        self.assertTrue(
            any("processing errors" in reason for reason in result["reasons"])
        )


if __name__ == "__main__":
    unittest.main()
