from datetime import datetime, timezone

from app.models.analysis import AnalysisInDatabase
from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.schemas.xai import (
    AnalysisExplanation,
    ELAExplanation,
    ExplanationFactor,
    FusionExplanation,
    ImageQualityExplanation,
    ModelSignalExplanation,
    OCRExplanation,
    TrustScoreExplanation,
)
from app.services.reports import build_analysis_report, collect_report_sections


def analysis_with_persisted_xai() -> AnalysisInDatabase:
    return AnalysisInDatabase(
        id="507f1f77bcf86cd799439012",
        owner_id="507f1f77bcf86cd799439011",
        created_at=datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc),
        signals={
            "tampering": AnalysisSignal(status="available", result={"label": "authentic", "top_class_softmax_score": 0.71}),
            "ai_generation": AnalysisSignal(status="available", result={"label": "fake", "top_class_softmax_score": 1.0}),
            "ocr": AnalysisSignal(status="available", result={"regions": [{"text": "TRUSTLENS", "confidence": 0.91}]}),
            "quality": AnalysisSignal(status="available", result={"width": 640, "height": 480, "brightness_mean": 120.5, "contrast_standard_deviation": 42.25, "sharpness_laplacian_variance": 87.5, "method": "Measured image properties."}),
            "ela": AnalysisSignal(status="available", result={"mean_absolute_difference": 8.25, "differing_pixel_fraction": 0.2, "recompression_quality": 90, "method": "JPEG recompression"}),
        },
        trust_score=TrustScore(score=36, category="Potentially Suspicious", signal_weights={"tampering": 0.5, "ai_generation": 0.5}, contributing_signals=("tampering", "ai_generation"), limitations=("Decision support only.",)),
        explanation=AnalysisExplanation(
            overall_summary="Returned signals require human review.",
            trust_score=TrustScoreExplanation(score=36, category="Potentially Suspicious", explanation="The server returned 36/100.", caution_factors=(ExplanationFactor(signal="ai_generation", direction="requires_review", explanation="AI-generated detection returned fake."),)),
            tampering=ModelSignalExplanation(status="available", interpretation="Tampering classification is contextual."),
            ai_generated=ModelSignalExplanation(status="available", interpretation="AI-generated classification is contextual."),
            ocr=OCRExplanation(status="available", interpretation="OCR is supporting information."),
            image_quality=ImageQualityExplanation(status="available", interpretation="Quality is contextual."),
            ela=ELAExplanation(status="available", observations=("Mean absolute recompression difference: 8.25.",), interpretation="ELA is supporting context."),
            fusion=FusionExplanation(signals_considered=("tampering", "ai_generation"), suspicious_signals=(ExplanationFactor(signal="ai_generation", direction="requires_review", explanation="AI-generated detection returned fake."),), signal_weights={"tampering": 0.5, "ai_generation": 0.5}, explanation="Fusion used returned weights.", limitations=("Decision support only.",)),
            limitations=("Models are probabilistic.",),
        ),
    )


def test_report_sections_use_persisted_analysis_values_and_disclose_missing_artifacts() -> None:
    sections = collect_report_sections(analysis_with_persisted_xai())
    text = "\n".join(line for section in sections for line in section.lines)

    assert "Score: 36/100" in text
    assert "Classification: authentic" in text
    assert "Classification: fake" in text
    assert "OCR region 1: TRUSTLENS (confidence: 91%)" in text
    assert "Resolution: 640 x 480" in text
    assert "Mean absolute difference: 8.25" in text
    assert "ELA visualization: Not available" in text
    assert "Original uploaded image: Not retained" in text
    assert any(section.title == "Positive / Supporting signals" for section in sections)
    assert any(section.title == "Caution / Review signals" for section in sections)
    assert any(section.title == "Technical analysis details" for section in sections)
    assert "TrustLens provides AI-assisted decision support only." in text


def test_report_builds_for_new_and_legacy_analysis_records() -> None:
    named_analysis = analysis_with_persisted_xai().model_copy(update={"report_title": "Kitchen claim review"})
    report = build_analysis_report(named_analysis)
    legacy = analysis_with_persisted_xai().model_copy(update={"explanation": None, "trust_score": None})
    legacy_report = build_analysis_report(legacy)

    assert report.startswith(b"%PDF-") and len(report) > 1_000
    assert legacy_report.startswith(b"%PDF-") and len(legacy_report) > 1_000
