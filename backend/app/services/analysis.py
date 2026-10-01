from collections.abc import Callable
from typing import Any

from PIL import Image
from pydantic import BaseModel

from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.services.ai_detector import AIDetectorModelUnavailableError, AIGenerationDetector
from app.services.ela import ELAService
from app.services.explanations import AnalysisExplanationService
from app.services.fusion import AdaptiveTrustScorer
from app.services.ocr import OCRService, OCRUnavailableError
from app.services.quality import ImageQualityService
from app.services.tampering_detector import TamperingDetector, TamperingModelUnavailableError
from app.schemas.xai import AnalysisExplanation


SignalCallable = Callable[[Image.Image], BaseModel]


class ImageAnalysisService:
    """Run registered backend-only signals and preserve their availability state."""

    def __init__(
        self,
        tampering_detector: TamperingDetector,
        ai_generation_detector: AIGenerationDetector,
        ocr_service: OCRService,
        ela_service: ELAService,
        quality_service: ImageQualityService | None = None,
        trust_scorer: AdaptiveTrustScorer | None = None,
        explanation_service: AnalysisExplanationService | None = None,
    ) -> None:
        self._signals: dict[str, SignalCallable] = {
            "tampering": tampering_detector.predict,
            "ai_generation": ai_generation_detector.predict,
            "ocr": ocr_service.extract,
            "quality": (quality_service or ImageQualityService()).analyze,
            "ela": ela_service.analyze,
        }
        self._trust_scorer = trust_scorer or AdaptiveTrustScorer()
        self._explanation_service = explanation_service or AnalysisExplanationService()

    def analyze(self, image: Image.Image) -> tuple[dict[str, AnalysisSignal], TrustScore | None]:
        """Execute each signal independently so one unavailable service never fabricates data."""
        signals = {name: self._run_signal(signal, image) for name, signal in self._signals.items()}
        return signals, self._trust_scorer.calculate(signals)

    def explain_evidence(
        self, signals: dict[str, AnalysisSignal], trust_score: TrustScore | None = None
    ) -> AnalysisExplanation:
        """Build an XAI description from already-completed signal outputs."""
        return self._explanation_service.explain_evidence(signals, trust_score)

    @staticmethod
    def _run_signal(signal: SignalCallable, image: Image.Image) -> AnalysisSignal:
        try:
            result = signal(image)
        except (
            TamperingModelUnavailableError,
            AIDetectorModelUnavailableError,
            OCRUnavailableError,
        ):
            return AnalysisSignal(status="unavailable", message="Signal is unavailable.")
        except Exception:
            return AnalysisSignal(status="failed", message="Signal processing failed.")
        return AnalysisSignal(status="available", result=result.model_dump(mode="json"))
