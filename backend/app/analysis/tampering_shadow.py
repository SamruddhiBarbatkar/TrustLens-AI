"""Run the ResNet tampering candidate without affecting TrustLens decisions."""

from pathlib import Path

from app.analysis.base import create_analysis_output
from app.core.config import settings
from app.ml.model_registry import get_resnet_shadow_model, resnet_shadow_enabled


ANALYSIS_TYPE = "TAMPERING_RESNET_SHADOW"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _empty_result(reason):
    return {
        "prediction": None,
        "authentic_probability": None,
        "tampered_probability": None,
        "confidence": None,
        "model_available": False,
        "model_version": None,
        "decision_role": "SHADOW_ONLY",
        "excluded_from_trust_score": True,
        "detector_policy_mode": settings.detector_policy_mode,
        "reason": reason,
    }


def analyze_tampering_resnet_shadow(evidence):
    if not resnet_shadow_enabled():
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="SKIPPED",
            result=_empty_result("RESNET_SHADOW_DISABLED"),
            message="ResNet shadow analysis is disabled for this policy.",
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
            message="ResNet shadow analysis currently supports image files only.",
        )

    try:
        model = get_resnet_shadow_model()
        if model is None:
            raise RuntimeError("ResNet shadow model was not selected.")
        prediction = model.predict(file_path)
        prediction.update({
            "decision_role": "SHADOW_ONLY",
            "excluded_from_trust_score": True,
            "detector_policy_mode": settings.detector_policy_mode,
        })
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="COMPLETED",
            result=prediction,
            message=(
                "ResNet-18 shadow analysis completed. Its output is recorded "
                "for research comparison and excluded from the Trust Score."
            ),
        )
    except (FileNotFoundError, PermissionError):
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result=_empty_result("CHECKPOINT_UNAVAILABLE"),
            message="The ResNet shadow checkpoint is unavailable.",
        )
    except Exception as error:
        return create_analysis_output(
            analysis_type=ANALYSIS_TYPE,
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=f"ResNet shadow analysis failed: {error}",
        )
