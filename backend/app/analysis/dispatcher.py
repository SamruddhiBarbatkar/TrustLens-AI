from app.analysis.image_quality import analyze_image_quality
from app.analysis.quality_gate import evaluate_quality_gate
from app.analysis.forensics import analyze_forensics
from app.analysis.tampering import analyze_tampering
from app.analysis.tampering_shadow import analyze_tampering_resnet_shadow
from app.analysis.tampering_multiview import analyze_tampering_multiview
from app.analysis.ai_generation import analyze_ai_generation
from app.analysis.metadata import analyze_metadata
from app.analysis.ocr import analyze_ocr
from app.analysis.ocr_entities import extract_ocr_entities


ANALYZERS = {
    "IMAGE_QUALITY": analyze_image_quality,
    "QUALITY_GATE": evaluate_quality_gate,
    "FORENSICS": analyze_forensics,
    "TAMPERING_DETECTION": analyze_tampering,
    "TAMPERING_RESNET_SHADOW": analyze_tampering_resnet_shadow,
    "TAMPERING_MULTIVIEW_CANDIDATE": analyze_tampering_multiview,
    "AI_GENERATION": analyze_ai_generation,
    "METADATA": analyze_metadata,
    "OCR": analyze_ocr,
    "OCR_ENTITIES": extract_ocr_entities,
}


def run_analysis(
    analysis_type,
    evidence,
    image_quality_result=None,
    ocr_result=None
):

    analyzer = ANALYZERS.get(
        analysis_type
    )

    if analyzer is None:

        return {
            "status": "ERROR",
            "analysis_type": analysis_type,
            "evidence_id": evidence.id,
            "result": None,
            "message": (
                f"No analyzer registered for "
                f"{analysis_type}"
            )
        }

    if analysis_type == "QUALITY_GATE":

        return analyzer(
            image_quality_result=image_quality_result,
            evidence_id=evidence.id
        )

    if analysis_type == "OCR_ENTITIES":

        return analyzer(
            evidence=evidence,
            ocr_result=ocr_result
        )

    return analyzer(evidence)
