"""Generate cautious XAI evidence descriptions from completed signal outputs."""

from collections.abc import Mapping
from typing import Any

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


class AnalysisExplanationService:
    """Translate existing pipeline output into structured, non-conclusive text.

    This service does not run models or derive new measurements. It only uses
    the signal status and result fields supplied by the completed pipeline.
    """

    limitations = (
        "TrustLens explanations summarize returned technical signals and are not proof of authenticity, fraud, provenance, ownership, or intent.",
        "Model top-class scores are recorded classifier outputs, not calibrated probabilities or forensic conclusions.",
        "OCR, image-quality measurements, and ELA provide supporting context and do not independently establish authenticity.",
    )

    def explain_evidence(
        self, signals: Mapping[str, AnalysisSignal], trust_score: TrustScore | None = None
    ) -> AnalysisExplanation:
        """Create an explanation for available, unavailable, failed, or partial signals."""
        statuses = [signal.status for signal in signals.values()]
        available = sum(status == "available" for status in statuses)
        unavailable = sum(status == "unavailable" for status in statuses)
        failed = sum(status == "failed" for status in statuses)

        return AnalysisExplanation(
            overall_summary=(
                f"TrustLens completed {available} available signal(s), with {unavailable} unavailable "
                f"and {failed} failed signal(s). The descriptions below summarize returned outputs "
                "and require human review in context."
            ),
            tampering=self._model_explanation(
                self._signal(signals, "tampering"),
                signal_name="tampering detector",
                positive_label="authentic",
                caution_label="tampered",
            ),
            ai_generated=self._model_explanation(
                self._signal(signals, "ai_generation"),
                signal_name="AI-generated image detector",
                positive_label="real",
                caution_label="fake",
            ),
            ocr=self._ocr_explanation(self._signal(signals, "ocr")),
            image_quality=self._quality_explanation(self._signal(signals, "quality")),
            ela=self._ela_explanation(self._signal(signals, "ela")),
            trust_score=self._trust_score_explanation(signals, trust_score),
            fusion=self._fusion_explanation(signals, trust_score),
            limitations=self.limitations,
        )

    def _trust_score_explanation(
        self, signals: Mapping[str, AnalysisSignal], trust_score: TrustScore | None
    ) -> TrustScoreExplanation:
        if trust_score is None:
            return TrustScoreExplanation(
                explanation=(
                    "No adaptive Trust Score was returned because the available signals did not include "
                    "a verified model output that can be scored."
                )
            )

        signal_names = self._signal_names(trust_score.contributing_signals)
        factors = self._factors(signals, trust_score)
        return TrustScoreExplanation(
            score=trust_score.score,
            category=trust_score.category,
            explanation=(
                f"TrustLens assigned {trust_score.score}/100 ({trust_score.category}) using the available "
                f"adaptive model signal(s): {signal_names}. The result is AI-assisted decision support, not proof."
            ),
            contributing_factors=tuple(
                factor for factor in factors if factor.direction == "supports_authenticity"
            ),
            caution_factors=tuple(
                factor for factor in factors if factor.direction == "requires_review"
            ),
        )

    def _fusion_explanation(
        self, signals: Mapping[str, AnalysisSignal], trust_score: TrustScore | None
    ) -> FusionExplanation:
        if trust_score is None:
            return FusionExplanation(
                explanation=(
                    "Adaptive fusion did not produce a Trust Score because no available model signal had "
                    "a verified authenticity-direction mapping."
                )
            )

        factors = self._factors(signals, trust_score)
        signal_names = self._signal_names(trust_score.contributing_signals)
        return FusionExplanation(
            signals_considered=trust_score.contributing_signals,
            positive_signals=tuple(
                factor for factor in factors if factor.direction == "supports_authenticity"
            ),
            suspicious_signals=tuple(
                factor for factor in factors if factor.direction == "requires_review"
            ),
            signal_weights=dict(trust_score.signal_weights),
            explanation=(
                f"Adaptive fusion used {signal_names} with the returned configured weights. "
                "OCR, image-quality, and ELA signals remain contextual because the current scorer does not "
                "assign them a validated authenticity-direction contribution."
            ),
            limitations=trust_score.limitations,
        )

    def _factors(
        self, signals: Mapping[str, AnalysisSignal], trust_score: TrustScore
    ) -> tuple[ExplanationFactor, ...]:
        factors: list[ExplanationFactor] = []
        for name in trust_score.contributing_signals:
            signal = signals.get(name)
            result = self._result(signal) if signal is not None else {}
            label = result.get("label")
            confidence = self._probability(result.get("top_class_softmax_score"))
            weight = trust_score.signal_weights.get(name)
            if name == "tampering":
                if label not in {"authentic", "tampered"}:
                    continue
                direction = "supports_authenticity" if label == "authentic" else "requires_review"
                display_name = "Tampering detection"
            elif name == "ai_generation":
                if label not in {"real", "fake"}:
                    continue
                direction = "supports_authenticity" if label == "real" else "requires_review"
                display_name = "AI-generated detection"
            else:
                continue
            label_text = label if isinstance(label, str) else "an unrecognized classification"
            confidence_text = self._percent(confidence) if confidence is not None else "an unavailable confidence"
            weight_text = self._percent(weight) if self._probability(weight) is not None else "its returned weight"
            factors.append(
                ExplanationFactor(
                    signal=name,
                    direction=direction,
                    explanation=(
                        f"{display_name} returned {label_text} with a recorded top-class score of "
                        f"{confidence_text}; adaptive fusion assigned {weight_text}."
                    ),
                )
            )
        return tuple(factors)

    @staticmethod
    def _signal_names(names: tuple[str, ...]) -> str:
        display_names = {
            "tampering": "tampering detection",
            "ai_generation": "AI-generated detection",
        }
        return ", ".join(display_names.get(name, name) for name in names) or "no contributing signals"

    @staticmethod
    def _signal(signals: Mapping[str, AnalysisSignal], name: str) -> AnalysisSignal:
        return signals.get(
            name,
            AnalysisSignal(status="unavailable", message="This signal was not returned by the analysis pipeline."),
        )

    def _model_explanation(
        self,
        signal: AnalysisSignal,
        *,
        signal_name: str,
        positive_label: str,
        caution_label: str,
    ) -> ModelSignalExplanation:
        if signal.status != "available":
            return ModelSignalExplanation(
                status=signal.status,
                interpretation=self._status_message(signal, signal_name),
                limitations=self.limitations[:2],
            )

        result = self._result(signal)
        label = result.get("label")
        confidence = self._probability(result.get("top_class_softmax_score"))
        if not isinstance(label, str) or confidence is None:
            return ModelSignalExplanation(
                status="available",
                interpretation=(
                    f"The {signal_name} completed, but it did not return a recognized classification "
                    "and confidence pair for explanation."
                ),
                limitations=self.limitations[:2],
            )

        confidence_text = self._percent(confidence)
        if label == positive_label:
            contribution = "This classification contributes authenticity-direction evidence when adaptive fusion includes this signal."
        elif label == caution_label:
            contribution = "This classification contributes review-direction evidence when adaptive fusion includes this signal."
        else:
            contribution = "This classification is reported as returned; its contribution cannot be interpreted from the verified label mapping."

        return ModelSignalExplanation(
            status="available",
            classification=label,
            confidence=confidence,
            interpretation=(
                f"The {signal_name} classified the image as {label} with a recorded top-class score of "
                f"{confidence_text}. This is a classification signal, not pixel-level localization or proof."
            ),
            contribution=contribution,
            limitations=self.limitations[:2],
        )

    def _ocr_explanation(self, signal: AnalysisSignal) -> OCRExplanation:
        if signal.status != "available":
            return OCRExplanation(
                status=signal.status,
                interpretation=self._status_message(signal, "OCR"),
                limitations=(self.limitations[2],),
            )

        regions = self._result(signal).get("regions")
        regions = regions if isinstance(regions, list) else []
        confidences = [self._probability(region.get("confidence")) for region in regions if isinstance(region, Mapping)]
        valid_confidences = [confidence for confidence in confidences if confidence is not None]
        aggregate_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else None
        if not regions:
            interpretation = "OCR completed and returned no text regions. OCR is supporting information, not authenticity proof."
        elif aggregate_confidence is None:
            interpretation = f"OCR completed and returned {len(regions)} text region(s), but no valid confidence values were returned."
        else:
            interpretation = (
                f"OCR completed and returned {len(regions)} text region(s) with a mean reported confidence of "
                f"{self._percent(aggregate_confidence)}. OCR is supporting information, not authenticity proof."
            )
        return OCRExplanation(
            status="available",
            text_region_count=len(regions),
            aggregate_confidence=aggregate_confidence,
            interpretation=interpretation,
            limitations=(self.limitations[2],),
        )

    def _quality_explanation(self, signal: AnalysisSignal) -> ImageQualityExplanation:
        if signal.status != "available":
            return ImageQualityExplanation(
                status=signal.status,
                interpretation=self._status_message(signal, "Image-quality analysis"),
                limitations=(self.limitations[2],),
            )

        result = self._result(signal)
        width = self._positive_int(result.get("width"))
        height = self._positive_int(result.get("height"))
        brightness = self._number_in_range(result.get("brightness_mean"), 0, 255)
        contrast = self._non_negative_number(result.get("contrast_standard_deviation"))
        sharpness = self._non_negative_number(result.get("sharpness_laplacian_variance"))
        values: list[str] = []
        if width is not None and height is not None:
            values.append(f"resolution {width}×{height}")
        if brightness is not None:
            values.append(f"mean brightness {brightness:.2f}")
        if contrast is not None:
            values.append(f"contrast deviation {contrast:.2f}")
        if sharpness is not None:
            values.append(f"sharpness variance {sharpness:.2f}")
        interpretation = (
            f"Image-quality analysis completed with {', '.join(values)}. These are contextual measurements, not direct evidence of authenticity."
            if values
            else "Image-quality analysis completed, but no recognized quality measurements were returned."
        )
        return ImageQualityExplanation(
            status="available",
            width=width,
            height=height,
            brightness_mean=brightness,
            contrast_standard_deviation=contrast,
            sharpness_laplacian_variance=sharpness,
            interpretation=interpretation,
            limitations=self._result_limitations(result, fallback=(self.limitations[2],)),
        )

    def _ela_explanation(self, signal: AnalysisSignal) -> ELAExplanation:
        if signal.status != "available":
            return ELAExplanation(
                status=signal.status,
                interpretation=self._status_message(signal, "Error Level Analysis"),
                limitations=(self.limitations[2],),
            )

        result = self._result(signal)
        observations: list[str] = []
        mean_difference = self._number_in_range(result.get("mean_absolute_difference"), 0, 255)
        if mean_difference is not None:
            observations.append(f"Mean absolute recompression difference: {mean_difference:.2f}.")
        differing_fraction = self._probability(result.get("differing_pixel_fraction"))
        if differing_fraction is not None:
            observations.append(f"Differing pixel fraction: {self._percent(differing_fraction)}.")
        quality = self._positive_int(result.get("recompression_quality"))
        if quality is not None:
            observations.append(f"JPEG recompression quality: {quality}.")
        return ELAExplanation(
            status="available",
            observations=tuple(observations),
            interpretation=(
                "ELA completed by comparing the image with a controlled JPEG recompression. "
                "Its measurements are forensic-supporting context and do not prove editing or authenticity."
            ),
            limitations=self._result_limitations(result, fallback=(self.limitations[2],)),
        )

    @staticmethod
    def _result(signal: AnalysisSignal) -> Mapping[str, Any]:
        return signal.result if isinstance(signal.result, Mapping) else {}

    @staticmethod
    def _status_message(signal: AnalysisSignal, signal_name: str) -> str:
        if signal.message:
            return f"{signal_name} is {signal.status}: {signal.message}"
        return f"{signal_name} is {signal.status}; no result was returned."

    @staticmethod
    def _probability(value: object) -> float | None:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1 else None

    @staticmethod
    def _number_in_range(value: object, minimum: float, maximum: float) -> float | None:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum else None

    @staticmethod
    def _non_negative_number(value: object) -> float | None:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None

    @staticmethod
    def _positive_int(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    @staticmethod
    def _percent(value: float) -> str:
        return f"{value * 100:.0f}%"

    @staticmethod
    def _result_limitations(result: Mapping[str, Any], *, fallback: tuple[str, ...]) -> tuple[str, ...]:
        limitations = result.get("limitations")
        if isinstance(limitations, (list, tuple)) and all(isinstance(item, str) for item in limitations):
            return tuple(limitations)
        return fallback
