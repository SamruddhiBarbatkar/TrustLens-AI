from sqlalchemy.orm import Session

from app.db.models import AnalysisResult, Evidence


def build_evidence_reliability_profile(
    db: Session,
    evidence: Evidence,
    verification_run_id: int
):
    """
    Build a transparent reliability profile for one evidence item.

    This stage does not calculate a numerical reliability score.
    It summarizes the availability and quality of upstream
    evidence-analysis signals.
    """

    analysis_results = (
        db.query(AnalysisResult)
        .filter(
            AnalysisResult.verification_run_id == verification_run_id,
            AnalysisResult.evidence_id == evidence.id
        )
        .all()
    )

    results_by_type = {
        result.analysis_type: result
        for result in analysis_results
    }

    reliability_factors = []

    # ---------------------------------------------------------
    # IMAGE QUALITY
    # ---------------------------------------------------------

    image_quality = results_by_type.get("IMAGE_QUALITY")

    if image_quality is None:
        reliability_factors.append(
            "IMAGE_QUALITY_UNAVAILABLE"
        )

    elif image_quality.status != "COMPLETED":
        reliability_factors.append(
            "IMAGE_QUALITY_INCOMPLETE"
        )

    # ---------------------------------------------------------
    # QUALITY GATE
    # ---------------------------------------------------------

    quality_gate = results_by_type.get("QUALITY_GATE")

    quality_status = None

    if quality_gate is None:
        reliability_factors.append(
            "QUALITY_GATE_UNAVAILABLE"
        )

    elif quality_gate.status != "COMPLETED":
        reliability_factors.append(
            "QUALITY_GATE_INCOMPLETE"
        )

    elif quality_gate.result:
        quality_status = quality_gate.result.get(
            "quality_status"
        )

        if quality_status == "WARNING":
            reliability_factors.append(
                "QUALITY_WARNING"
            )

        elif quality_status == "POOR":
            reliability_factors.append(
                "QUALITY_POOR"
            )

    # ---------------------------------------------------------
    # OCR
    # ---------------------------------------------------------

    ocr = results_by_type.get("OCR")

    ocr_available = False

    if ocr is None:
        reliability_factors.append(
            "OCR_UNAVAILABLE"
        )

    elif ocr.status != "COMPLETED":
        reliability_factors.append(
            "OCR_INCOMPLETE"
        )

    elif ocr.result:
        ocr_text = ocr.result.get("text")
        ocr_text_length = ocr.result.get("text_length", 0)

        ocr_available = bool(
            ocr_text and str(ocr_text).strip()
        ) or bool(ocr_text_length)

        if not ocr_available:
            reliability_factors.append(
                "OCR_TEXT_UNAVAILABLE"
            )

    else:
        reliability_factors.append(
            "OCR_RESULT_UNAVAILABLE"
        )

    # ---------------------------------------------------------
    # OCR ENTITIES
    # ---------------------------------------------------------

    ocr_entities = results_by_type.get("OCR_ENTITIES")

    ocr_entities_available = False

    if ocr_entities is None:
        reliability_factors.append(
            "OCR_ENTITIES_UNAVAILABLE"
        )

    elif ocr_entities.status != "COMPLETED":
        reliability_factors.append(
            "OCR_ENTITIES_INCOMPLETE"
        )

    elif ocr_entities.result:
        ocr_entities_available = bool(
            ocr_entities.result.get(
                "text_available",
                False
            )
        )

        if not ocr_entities_available:
            reliability_factors.append(
                "OCR_ENTITIES_TEXT_UNAVAILABLE"
            )

    # ---------------------------------------------------------
    # FORENSICS
    # ---------------------------------------------------------

    forensics = results_by_type.get("FORENSICS")

    forensics_available = False

    if (
        forensics
        and forensics.status == "COMPLETED"
        and forensics.result
    ):
        forensics_available = True
    else:
        reliability_factors.append(
            "FORENSICS_UNAVAILABLE"
        )

    # ---------------------------------------------------------
    # METADATA
    # ---------------------------------------------------------

    metadata = results_by_type.get("METADATA")

    metadata_available = False

    if (
        metadata
        and metadata.status == "COMPLETED"
        and metadata.result
    ):
        metadata_available = True
    else:
        reliability_factors.append(
            "METADATA_UNAVAILABLE"
        )

    # ---------------------------------------------------------
    # AI GENERATION
    # ---------------------------------------------------------

    ai_generation = results_by_type.get("AI_GENERATION")

    ai_generation_available = False

    if (
        ai_generation
        and ai_generation.status == "COMPLETED"
        and ai_generation.result
        and ai_generation.result.get("model_available")
    ):
        ai_generation_available = True
    else:
        reliability_factors.append(
            "AI_GENERATION_UNAVAILABLE"
        )

    # ---------------------------------------------------------
    # PROFILE STATUS
    # ---------------------------------------------------------

    if "QUALITY_POOR" in reliability_factors:
        profile_status = "CAUTION"

    elif reliability_factors:
        profile_status = "PARTIAL"

    else:
        profile_status = "READY"

    # ---------------------------------------------------------
    # FINAL PROFILE
    # ---------------------------------------------------------

    return {
        "evidence_id": evidence.id,
        "evidence_type": evidence.evidence_type,

        "profile_status": profile_status,

        "quality": {
            "status": quality_status
        },

        "ocr": {
            "available": ocr_available
        },

        "ocr_entities": {
            "available": ocr_entities_available
        },

        "forensics": {
            "available": forensics_available
        },

        "metadata": {
            "available": metadata_available
        },

        "ai_generation": {
            "available": ai_generation_available
        },

        "reliability_factors": reliability_factors,

        "analysis_types_available": sorted(
            results_by_type.keys()
        )
    }