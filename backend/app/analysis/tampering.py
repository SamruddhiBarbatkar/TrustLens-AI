from pathlib import Path

from app.analysis.base import create_analysis_output
from app.core.config import settings
from app.ml.model_registry import (
    get_primary_tampering_model,
    primary_tampering_uses_multiview,
)


def analyze_tampering(evidence):

    try:

        file_path = Path(
            evidence.file_path
        )

        if not file_path.exists():

            return create_analysis_output(
                analysis_type="TAMPERING_DETECTION",
                evidence_id=evidence.id,
                status="ERROR",
                result=None,
                message=(
                    "Evidence file was not found."
                )
            )

        supported_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".bmp"
        }

        if file_path.suffix.lower() not in supported_extensions:

            return create_analysis_output(
                analysis_type="TAMPERING_DETECTION",
                evidence_id=evidence.id,
                status="NOT_SUPPORTED",
                result={
                    "prediction": None,
                    "authentic_probability": None,
                    "tampered_probability": None,
                    "confidence": None,
                    "model_available": False,
                    "model_version": None
                },
                message=(
                    "Tampering detection currently "
                    "supports image files only."
                )
            )

        model = get_primary_tampering_model()

        prediction = (
            model.predict_multiview(file_path)
            if primary_tampering_uses_multiview()
            else model.predict(file_path)
        )
        prediction.update({
            "decision_role": "PRIMARY_TAMPERING_EVIDENCE",
            "detector_policy_mode": settings.detector_policy_mode,
            "excluded_from_trust_score": False,
        })

        return create_analysis_output(
            analysis_type="TAMPERING_DETECTION",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=prediction,
            message=(
                "Tampering detection completed "
                f"using the trained {prediction['model_name']} model."
            )
        )

    except FileNotFoundError:

        return create_analysis_output(
            analysis_type="TAMPERING_DETECTION",
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result={
                "prediction": None,
                "authentic_probability": None,
                "tampered_probability": None,
                "confidence": None,
                "model_available": False,
                "model_version": None
            },
            message=(
                "Tampering detection model checkpoint "
                "is not available. Analysis was skipped."
            )
        )

    except PermissionError:

        return create_analysis_output(
            analysis_type="TAMPERING_DETECTION",
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result={
                "prediction": None,
                "authentic_probability": None,
                "tampered_probability": None,
                "confidence": None,
                "model_available": False,
                "model_version": None
            },
            message=(
                "Tampering detection model checkpoint "
                "could not be accessed. Analysis was skipped."
            )
        )

    except Exception as error:

        error_message = str(error)

        if (
            "tampering_model.pth" in error_message
            or "No such file" in error_message
            or "cannot open" in error_message
        ):

            return create_analysis_output(
                analysis_type="TAMPERING_DETECTION",
                evidence_id=evidence.id,
                status="MODEL_UNAVAILABLE",
                result={
                    "prediction": None,
                    "authentic_probability": None,
                    "tampered_probability": None,
                    "confidence": None,
                    "model_available": False,
                    "model_version": None
                },
                message=(
                    "Tampering detection model checkpoint "
                    "is not available. Analysis was skipped."
                )
            )

        return create_analysis_output(
            analysis_type="TAMPERING_DETECTION",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=(
                "Tampering detection failed: "
                f"{error_message}"
            )
        )
