from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.services.explanations import AnalysisExplanationService


def test_explanation_service_uses_returned_signal_values_without_new_findings() -> None:
    explanation = AnalysisExplanationService().explain_evidence(
        {
            "tampering": AnalysisSignal(
                status="available",
                result={"label": "authentic", "top_class_softmax_score": 0.71},
            ),
            "ai_generation": AnalysisSignal(
                status="available",
                result={"label": "fake", "top_class_softmax_score": 1.0},
            ),
            "ocr": AnalysisSignal(
                status="available",
                result={"regions": [{"text": "Example", "confidence": 0.8}, {"text": "Text", "confidence": 0.6}]},
            ),
            "quality": AnalysisSignal(
                status="available",
                result={
                    "width": 640,
                    "height": 480,
                    "brightness_mean": 120.5,
                    "contrast_standard_deviation": 42.25,
                    "sharpness_laplacian_variance": 87.5,
                    "limitations": ["Quality is contextual."],
                },
            ),
            "ela": AnalysisSignal(
                status="available",
                result={
                    "mean_absolute_difference": 8.25,
                    "differing_pixel_fraction": 0.2,
                    "recompression_quality": 90,
                    "limitations": ["ELA is not proof."],
                },
            ),
        }
    )

    assert explanation.tampering is not None
    assert explanation.tampering.classification == "authentic"
    assert explanation.tampering.confidence == 0.71
    assert "71%" in explanation.tampering.interpretation
    assert explanation.ai_generated is not None
    assert explanation.ai_generated.classification == "fake"
    assert "review-direction" in explanation.ai_generated.contribution
    assert explanation.ocr is not None
    assert explanation.ocr.text_region_count == 2
    assert explanation.ocr.aggregate_confidence == 0.7
    assert explanation.image_quality is not None
    assert explanation.image_quality.width == 640
    assert "sharpness variance 87.50" in explanation.image_quality.interpretation
    assert explanation.ela is not None
    assert explanation.ela.observations == (
        "Mean absolute recompression difference: 8.25.",
        "Differing pixel fraction: 20%.",
        "JPEG recompression quality: 90.",
    )


def test_explanation_service_keeps_unavailable_failed_partial_and_missing_signals_explicit() -> None:
    explanation = AnalysisExplanationService().explain_evidence(
        {
            "tampering": AnalysisSignal(status="unavailable", message="Signal is unavailable."),
            "ai_generation": AnalysisSignal(status="failed", message="Signal processing failed."),
            "ocr": AnalysisSignal(status="available", result={"regions": []}),
            "quality": AnalysisSignal(status="available", result={"width": "not-a-number"}),
        }
    )

    assert explanation.tampering is not None and explanation.tampering.status == "unavailable"
    assert explanation.ai_generated is not None and explanation.ai_generated.status == "failed"
    assert explanation.ocr is not None and explanation.ocr.text_region_count == 0
    assert explanation.image_quality is not None
    assert explanation.image_quality.width is None
    assert explanation.ela is not None and explanation.ela.status == "unavailable"
    assert "1 unavailable and 1 failed" in explanation.overall_summary


def test_explanation_service_uses_the_actual_trust_score_weights_and_categories() -> None:
    signals = {
        "tampering": AnalysisSignal(
            status="available", result={"label": "authentic", "top_class_softmax_score": 0.71}
        ),
        "ai_generation": AnalysisSignal(
            status="available", result={"label": "fake", "top_class_softmax_score": 1.0}
        ),
        "ocr": AnalysisSignal(status="available", result={"regions": []}),
    }
    trust_score = TrustScore(
        score=36,
        category="Potentially Suspicious",
        signal_weights={"tampering": 0.5, "ai_generation": 0.5},
        contributing_signals=("tampering", "ai_generation"),
        limitations=("Model scores are not calibrated evidence.",),
    )

    explanation = AnalysisExplanationService().explain_evidence(signals, trust_score)

    assert explanation.trust_score is not None
    assert explanation.trust_score.score == 36
    assert explanation.trust_score.category == "Potentially Suspicious"
    assert len(explanation.trust_score.contributing_factors) == 1
    assert explanation.trust_score.contributing_factors[0].signal == "tampering"
    assert explanation.trust_score.caution_factors[0].signal == "ai_generation"
    assert explanation.fusion is not None
    assert explanation.fusion.signal_weights == trust_score.signal_weights
    assert explanation.fusion.signals_considered == trust_score.contributing_signals
    assert explanation.fusion.limitations == trust_score.limitations
    assert "OCR" in explanation.fusion.explanation


def test_explanation_service_explains_when_adaptive_scoring_is_unavailable() -> None:
    explanation = AnalysisExplanationService().explain_evidence(
        {"ocr": AnalysisSignal(status="available", result={"regions": []})}
    )

    assert explanation.trust_score is not None
    assert explanation.trust_score.score is None
    assert explanation.fusion is not None
    assert explanation.fusion.signals_considered == ()


def test_explanation_service_does_not_invent_factor_direction_for_unknown_labels() -> None:
    signals = {
        "tampering": AnalysisSignal(
            status="available", result={"label": "unknown", "top_class_softmax_score": 0.9}
        )
    }
    inconsistent_score = TrustScore(
        score=90,
        category="Likely Authentic",
        signal_weights={"tampering": 1.0},
        contributing_signals=("tampering",),
        limitations=("Decision support only.",),
    )

    explanation = AnalysisExplanationService().explain_evidence(signals, inconsistent_score)

    assert explanation.trust_score is not None
    assert explanation.trust_score.score == 90
    assert explanation.trust_score.contributing_factors == ()
    assert explanation.trust_score.caution_factors == ()
    assert explanation.fusion is not None
    assert explanation.fusion.positive_signals == ()
    assert explanation.fusion.suspicious_signals == ()
