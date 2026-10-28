from app.db.models import AnalysisResult


EXPECTED_EVIDENCE_TYPES = {
    "invoice",
    "product",
    "damage"
}


def analyze_uncertainty(
    claim,
    verification_run
):
    """
    Build a diagnostic uncertainty profile for a verification run.

    This stage does not calculate:
    - calibrated probabilities
    - numerical uncertainty scores
    - authenticity scores
    - trust scores

    Instead, it identifies the sources and characteristics
    of uncertainty present in the current verification run.
    """

    analysis_results = list(
        verification_run.analysis_results
    )

    evidence_items = list(claim.evidence)

    # --------------------------------------------------
    # Basic analysis counts
    # --------------------------------------------------

    total_analyses = len(analysis_results)

    completed_analyses = sum(
        1
        for result in analysis_results
        if result.status == "COMPLETED"
    )

    incomplete_analyses = sum(
        1
        for result in analysis_results
        if result.status != "COMPLETED"
    )

    error_analyses = sum(
        1
        for result in analysis_results
        if result.status == "ERROR"
    )

    unsupported_analyses = sum(
        1
        for result in analysis_results
        if result.status == "NOT_IMPLEMENTED"
    )

    if total_analyses:
        analysis_completion_ratio = (
            completed_analyses / total_analyses
        )
    else:
        analysis_completion_ratio = 0.0

    # --------------------------------------------------
    # Evidence completeness
    # --------------------------------------------------

    evidence_types = {
        evidence.evidence_type
        for evidence in evidence_items
    }

    missing_evidence_types = sorted(
        EXPECTED_EVIDENCE_TYPES - evidence_types
    )

    missing_evidence_count = len(
        missing_evidence_types
    )

    # --------------------------------------------------
    # Stage-level uncertainty
    # --------------------------------------------------

    uncertainty_sources = []

    incomplete_stages = []

    for result in analysis_results:

        if result.status != "COMPLETED":

            incomplete_stages.append({
                "analysis_type": result.analysis_type,
                "evidence_id": result.evidence_id,
                "status": result.status
            })

    if incomplete_analyses > 0:
        uncertainty_sources.append(
            "INCOMPLETE_ANALYSIS"
        )

    if error_analyses > 0:
        uncertainty_sources.append(
            "ANALYSIS_ERRORS"
        )

    if unsupported_analyses > 0:
        uncertainty_sources.append(
            "UNSUPPORTED_ANALYSIS"
        )

    # --------------------------------------------------
    # Evidence-quality uncertainty
    # --------------------------------------------------

    quality_warnings = []

    for result in analysis_results:

        if result.analysis_type != "QUALITY_GATE":
            continue

        if not result.result:
            continue

        quality_status = result.result.get(
            "quality_status"
        )

        if quality_status in {
            "WARNING",
            "POOR"
        }:

            quality_warnings.append({
                "evidence_id": result.evidence_id,
                "quality_status": quality_status,
                "reasons": result.result.get(
                    "reasons",
                    []
                )
            })

    if quality_warnings:
        uncertainty_sources.append(
            "EVIDENCE_QUALITY_WARNING"
        )

    # --------------------------------------------------
    # OCR/content uncertainty
    # --------------------------------------------------

    ocr_unavailable = []

    for result in analysis_results:

        if result.analysis_type != "OCR":
            continue

        if result.status != "COMPLETED":

            ocr_unavailable.append(
                result.evidence_id
            )
            continue

        if not result.result:
            ocr_unavailable.append(
                result.evidence_id
            )
            continue

        text = result.result.get("text")
        text_length = result.result.get(
            "text_length",
            0
        )

        if not text and not text_length:
            ocr_unavailable.append(
                result.evidence_id
            )

    ocr_unavailable = sorted(
        set(ocr_unavailable)
    )

    if ocr_unavailable:
        uncertainty_sources.append(
            "OCR_CONTENT_UNAVAILABLE"
        )

    # --------------------------------------------------
    # Cross-evidence uncertainty
    # --------------------------------------------------

    cross_evidence_result = None

    for result in analysis_results:

        if result.analysis_type == "CROSS_EVIDENCE":
            cross_evidence_result = result
            break

    cross_evidence_available = (
        cross_evidence_result is not None
        and cross_evidence_result.status == "COMPLETED"
    )

    cross_evidence_not_comparable_count = 0

    cross_evidence_conflict_count = 0

    if cross_evidence_available:

        cross_result = (
            cross_evidence_result.result
            or {}
        )

        comparison_summary = (
            cross_result.get(
                "comparison_summary",
                {}
            )
        )

        cross_evidence_not_comparable_count = (
            comparison_summary.get(
                "not_comparable_count",
                0
            )
        )

        cross_evidence_conflict_count = (
            comparison_summary.get(
                "conflict_count",
                0
            )
        )

        if cross_evidence_not_comparable_count > 0:
            uncertainty_sources.append(
                "LIMITED_CROSS_EVIDENCE_COMPARABILITY"
            )

    else:
        uncertainty_sources.append(
            "CROSS_EVIDENCE_UNAVAILABLE"
        )

    # --------------------------------------------------
    # AI-generation uncertainty
    # --------------------------------------------------

    ai_generation_unavailable = []

    for result in analysis_results:

        if result.analysis_type != "AI_GENERATION":
            continue

        if (
            result.status == "NOT_IMPLEMENTED"
            or not result.result
            or not result.result.get(
                "model_available",
                False
            )
        ):
            ai_generation_unavailable.append(
                result.evidence_id
            )

    ai_generation_unavailable = sorted(
        set(ai_generation_unavailable)
    )

    if ai_generation_unavailable:
        uncertainty_sources.append(
            "AI_GENERATION_ANALYSIS_UNAVAILABLE"
        )

    # --------------------------------------------------
    # Missing evidence
    # --------------------------------------------------

    if missing_evidence_count > 0:
        uncertainty_sources.append(
            "MISSING_REQUIRED_EVIDENCE"
        )

    # --------------------------------------------------
    # Pipeline-level uncertainty
    # --------------------------------------------------

    if (
        incomplete_analyses > 0
        or missing_evidence_count > 0
    ):
        uncertainty_sources.append(
            "INCOMPLETE_PIPELINE"
        )

    # Remove duplicate sources while preserving order.
    uncertainty_sources = list(
        dict.fromkeys(uncertainty_sources)
    )

    # --------------------------------------------------
    # Diagnostic interpretation
    # --------------------------------------------------

    uncertainty_characteristics = []

    if incomplete_analyses > 0:
        uncertainty_characteristics.append(
            "Some analysis stages did not produce completed results."
        )

    if unsupported_analyses > 0:
        uncertainty_characteristics.append(
            "Some analysis capabilities are not implemented yet."
        )

    if error_analyses > 0:
        uncertainty_characteristics.append(
            "One or more analysis stages produced an error."
        )

    if quality_warnings:
        uncertainty_characteristics.append(
            "One or more evidence items have quality warnings."
        )

    if ocr_unavailable:
        uncertainty_characteristics.append(
            "OCR-derived content is unavailable for one or more evidence items."
        )

    if missing_evidence_count > 0:
        uncertainty_characteristics.append(
            "One or more expected evidence types are missing."
        )

    if cross_evidence_not_comparable_count > 0:
        uncertainty_characteristics.append(
            "Some cross-evidence comparisons could not be established under the current applicability rules."
        )

    if ai_generation_unavailable:
        uncertainty_characteristics.append(
            "AI-generated image analysis is unavailable for one or more evidence items."
        )

    if not uncertainty_characteristics:
        uncertainty_characteristics.append(
            "No diagnostic uncertainty source was identified by the current rule set."
        )

    # --------------------------------------------------
    # Build diagnostic uncertainty result
    # --------------------------------------------------

    uncertainty_result = {
        "evidence_count": len(evidence_items),

        "expected_evidence_count": len(
            EXPECTED_EVIDENCE_TYPES
        ),

        "missing_evidence_count": (
            missing_evidence_count
        ),

        "missing_evidence_types": (
            missing_evidence_types
        ),

        "total_analyses": total_analyses,

        "completed_analyses": completed_analyses,

        "incomplete_analyses": incomplete_analyses,

        "error_analyses": error_analyses,

        "unsupported_analyses": unsupported_analyses,

        "analysis_completion_ratio": round(
            analysis_completion_ratio,
            4
        ),

        "uncertainty_sources": (
            uncertainty_sources
        ),

        "incomplete_stages": (
            incomplete_stages
        ),

        "quality_warnings": (
            quality_warnings
        ),

        "ocr_unavailable_evidence_ids": (
            ocr_unavailable
        ),

        "ai_generation_unavailable_evidence_ids": (
            ai_generation_unavailable
        ),

        "cross_evidence": {
            "available": cross_evidence_available,
            "conflict_count": (
                cross_evidence_conflict_count
            ),
            "not_comparable_count": (
                cross_evidence_not_comparable_count
            )
        },

        "uncertainty_characteristics": (
            uncertainty_characteristics
        )
    }

    # --------------------------------------------------
    # Standard analysis output
    # --------------------------------------------------

    return {
        "status": "COMPLETED",
        "result": uncertainty_result,
        "message": (
            "Diagnostic uncertainty assessment completed. "
            "This assessment identifies uncertainty sources "
            "without producing calibrated probabilities, "
            "numerical uncertainty scores, authenticity "
            "scores, or trust scores."
        )
    }