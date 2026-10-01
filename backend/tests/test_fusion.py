from app.schemas.analysis import AnalysisSignal
from app.services.fusion import AdaptiveTrustScorer


def available(label: str, score: float) -> AnalysisSignal:
    return AnalysisSignal(status="available", result={"label": label, "top_class_softmax_score": score})


def test_adaptive_scorer_uses_real_model_outputs_and_normalizes_available_weights() -> None:
    trust_score = AdaptiveTrustScorer().calculate(
        {
            "tampering": available("authentic", 0.9),
            "ai_generation": available("fake", 0.8),
            "ela": AnalysisSignal(status="available", result={"mean_absolute_difference": 2.0}),
        }
    )

    assert trust_score is not None
    assert trust_score.score == 55
    assert trust_score.category == "Needs Review"
    assert trust_score.signal_weights == {"tampering": 0.5, "ai_generation": 0.5}
    assert trust_score.contributing_signals == ("tampering", "ai_generation")


def test_adaptive_scorer_reweights_when_one_model_signal_is_unavailable() -> None:
    trust_score = AdaptiveTrustScorer().calculate(
        {
            "tampering": AnalysisSignal(status="unavailable", message="Signal is unavailable."),
            "ai_generation": available("real", 0.82),
        }
    )

    assert trust_score is not None
    assert trust_score.score == 82
    assert trust_score.category == "Likely Authentic"
    assert trust_score.signal_weights == {"ai_generation": 1.0}


def test_adaptive_scorer_keeps_score_unavailable_without_a_verified_model_output() -> None:
    trust_score = AdaptiveTrustScorer().calculate(
        {"ela": AnalysisSignal(status="available", result={"mean_absolute_difference": 2.0})}
    )

    assert trust_score is None
