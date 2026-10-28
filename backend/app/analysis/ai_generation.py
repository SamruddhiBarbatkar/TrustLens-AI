from pathlib import Path

from app.analysis.base import create_analysis_output
from app.core.config import settings
from app.ml.model_registry import get_primary_ai_generation_model


def analyze_ai_generation(evidence):

    try:

        file_path = Path(
            evidence.file_path
        )

        if not file_path.exists():
            return create_analysis_output(
                analysis_type="AI_GENERATION",
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
                analysis_type="AI_GENERATION",
                evidence_id=evidence.id,
                status="NOT_SUPPORTED",
                result={
                    "prediction": None,
                    "real_image_probability": None,
                    "ai_generated_probability": None,
                    "confidence": None,
                    "model_available": False,
                    "model_version": None
                },
                message=(
                    "AI-generated image detection currently "
                    "supports image files only."
                )
            )

        model = get_primary_ai_generation_model()

        prediction = model.predict(
            file_path
        )
        prediction.update({
            "decision_role": "PRIMARY_AI_GENERATION_EVIDENCE",
            "detector_policy_mode": settings.detector_policy_mode,
            "excluded_from_trust_score": False,
        })

        return create_analysis_output(
            analysis_type="AI_GENERATION",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=prediction,
            message=(
                "AI-generated image analysis completed "
                "using the trained PyTorch model."
            )
        )

    except FileNotFoundError:

        return create_analysis_output(
            analysis_type="AI_GENERATION",
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result={
                "prediction": None,
                "real_image_probability": None,
                "ai_generated_probability": None,
                "confidence": None,
                "model_available": False,
                "model_version": None
            },
            message=(
                "AI-generated image model checkpoint "
                "is not available. Analysis was skipped."
            )
        )

    except PermissionError:

        return create_analysis_output(
            analysis_type="AI_GENERATION",
            evidence_id=evidence.id,
            status="MODEL_UNAVAILABLE",
            result={
                "prediction": None,
                "real_image_probability": None,
                "ai_generated_probability": None,
                "confidence": None,
                "model_available": False,
                "model_version": None
            },
            message=(
                "AI-generated image model checkpoint "
                "could not be accessed. Analysis was skipped."
            )
        )

    except Exception as error:

        error_message = str(error)

        if (
            "ai_detector_best.pth" in error_message
            or "No such file" in error_message
            or "cannot open" in error_message
        ):
            return create_analysis_output(
                analysis_type="AI_GENERATION",
                evidence_id=evidence.id,
                status="MODEL_UNAVAILABLE",
                result={
                    "prediction": None,
                    "real_image_probability": None,
                    "ai_generated_probability": None,
                    "confidence": None,
                    "model_available": False,
                    "model_version": None
                },
                message=(
                    "AI-generated image model checkpoint "
                    "is not available. Analysis was skipped."
                )
            )

        return create_analysis_output(
            analysis_type="AI_GENERATION",
            evidence_id=evidence.id,
            status="ERROR",
            result=None,
            message=(
                f"AI-generated image analysis failed: "
                f"{error_message}"
            )
        )
