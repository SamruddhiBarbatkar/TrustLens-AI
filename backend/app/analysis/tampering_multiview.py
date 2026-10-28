"""Evaluate local image patches without changing the validated Trust Score."""

from pathlib import Path

from app.analysis.base import create_analysis_output
from app.core.config import settings
from app.ml.model_registry import (
    get_multiview_candidate_model,
    multiview_candidate_enabled,
)


ANALYSIS_TYPE = "TAMPERING_MULTIVIEW_CANDIDATE"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _empty_result(reason):
    return {
        "prediction": None,
        "authentic_probability": None,
        "tampered_probability": None,
        "ai_generated_probability": None,
        "confidence": None,
        "model_available": False,
        "model_version": None,
        "decision_role": "RESEARCH_CANDIDATE_ONLY",
        "excluded_from_trust_score": True,
        "detector_policy_mode": settings.detector_policy_mode,
        "reason": reason,
    }


def analyze_tampering_multiview(evidence):
    if not multiview_candidate_enabled():
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="SKIPPED",
            result=_empty_result("MULTIVIEW_CANDIDATE_DISABLED"),
            message="Multi-view candidate analysis is disabled for this policy.",
        )

    file_path = Path(evidence.file_path)
    if not file_path.exists():
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message="Evidence file was not found.",
        )
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="NOT_SUPPORTED",
            result=_empty_result("UNSUPPORTED_MEDIA_TYPE"),
            message="Multi-view candidate currently supports image files only.",
        )

    try:
        model = get_multiview_candidate_model()
        if model is None:
            raise RuntimeError("Multi-view candidate model was not selected.")
        prediction = model.predict_multiview(file_path)
        prediction.update({
            "decision_role": "RESEARCH_CANDIDATE_ONLY",
            "excluded_from_trust_score": True,
            "detector_policy_mode": settings.detector_policy_mode,
        })
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="COMPLETED",
            result=prediction,
            message=(
                "Global-and-patch candidate analysis completed. Its output is "
                "recorded for comparison and excluded from the Trust Score."
            ),
        )
    except (FileNotFoundError, PermissionError):
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result=_empty_result("CHECKPOINT_UNAVAILABLE"),
            message="The multi-view candidate checkpoint is unavailable.",
        )
    except Exception as error:
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=f"Multi-view candidate analysis failed: {error}",
        )
