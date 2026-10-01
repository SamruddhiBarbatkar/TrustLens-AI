from collections.abc import Mapping
from typing import Any

from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore


class AdaptiveTrustScorer:
    """Fuse only available, directionally verified model outputs.

    The ResNet18 contract maps ``authentic`` to class 0 and ``tampered`` to
    class 1. The EfficientNet-B0 contract maps ``fake`` to class 0 and
    ``real`` to class 1. Their returned top-class softmax score is converted
    to support for the authentic/real direction, then equal base weights are
    renormalized across whichever supported signals are available.
    """

    limitations = (
        "This score is decision support, not proof of authenticity, provenance, ownership, or intent.",
        "Only available model signals with a verified authenticity-direction mapping contribute to the score.",
        "OCR and ELA remain reported evidence but are not assigned an unvalidated authenticity probability.",
        "Model scores are not calibrated evidence and can be affected by image content and preprocessing.",
    )

    def calculate(self, signals: Mapping[str, AnalysisSignal]) -> TrustScore | None:
        contributions: dict[str, float] = {}

        tampering_support = self._tampering_support(signals.get("tampering"))
        if tampering_support is not None:
            contributions["tampering"] = tampering_support

        ai_generation_support = self._ai_generation_support(signals.get("ai_generation"))
        if ai_generation_support is not None:
            contributions["ai_generation"] = ai_generation_support

        if not contributions:
            return None

        weight = 1 / len(contributions)
        weights = {name: weight for name in contributions}
        score = round(sum(contributions[name] * weights[name] for name in contributions) * 100)
        return TrustScore(
            score=score,
            category=self._category(score),
            signal_weights=weights,
            contributing_signals=tuple(contributions),
            limitations=self.limitations,
        )

    @staticmethod
    def _tampering_support(signal: AnalysisSignal | None) -> float | None:
        result = AdaptiveTrustScorer._available_result(signal)
        if result is None:
            return None
        label = result.get("label")
        confidence = result.get("top_class_softmax_score")
        if label not in {"authentic", "tampered"} or not AdaptiveTrustScorer._valid_probability(confidence):
            return None
        return confidence if label == "authentic" else 1 - confidence

    @staticmethod
    def _ai_generation_support(signal: AnalysisSignal | None) -> float | None:
        result = AdaptiveTrustScorer._available_result(signal)
        if result is None:
            return None
        label = result.get("label")
        confidence = result.get("top_class_softmax_score")
        if label not in {"fake", "real"} or not AdaptiveTrustScorer._valid_probability(confidence):
            return None
        return confidence if label == "real" else 1 - confidence

    @staticmethod
    def _available_result(signal: AnalysisSignal | None) -> Mapping[str, Any] | None:
        if signal is None or signal.status != "available" or not isinstance(signal.result, Mapping):
            return None
        return signal.result

    @staticmethod
    def _valid_probability(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1

    @staticmethod
    def _category(score: int) -> str:
        if score >= 80:
            return "Likely Authentic"
        if score >= 50:
            return "Needs Review"
        return "Potentially Suspicious"
