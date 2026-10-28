from app.db.models import AnalysisResult


def analyze_fusion(
    claim,
    verification_run
):
    """
    Assemble research-structured evidence signals for fusion.

    This stage intentionally does not calculate:
    - numerical reliability weights
    - authenticity probabilities
    - trust scores

    Instead, it organizes evidence dimensions and generates
    transparent observations that can later support a calibrated
    evidence-fusion model.
    """

    analysis_results = list(
        verification_run.analysis_results
    )

    evidence_results = {}
    claim_level_results = []

    for analysis in analysis_results:

        if analysis.evidence_id is not None:

            evidence_results.setdefault(
                analysis.evidence_id,
                []
            ).append(analysis)

        else:
            claim_level_results.append(analysis)

    # --------------------------------------------------
    # Helper
    # --------------------------------------------------

    def get_result(evidence_id, analysis_type):

        for analysis in evidence_results.get(
            evidence_id,
            []
        ):
            if analysis.analysis_type == analysis_type:
                return analysis

        return None

    # --------------------------------------------------
    # 1. Analysis summary
    # --------------------------------------------------

    analysis_summary = {}

    for analysis in analysis_results:

        analysis_summary.setdefault(
            analysis.analysis_type,
            {
                "count": 0,
                "completed": 0,
                "not_implemented": 0,
                "errors": 0
            }
        )

        summary = analysis_summary[
            analysis.analysis_type
        ]

        summary["count"] += 1

        if analysis.status == "COMPLETED":
            summary["completed"] += 1

        elif analysis.status == "NOT_IMPLEMENTED":
            summary["not_implemented"] += 1

        elif analysis.status == "ERROR":
            summary["errors"] += 1

    # --------------------------------------------------
    # 2. Evidence dimensions
    # --------------------------------------------------

    evidence_signal_summary = {}

    for evidence_id, results in evidence_results.items():

        image_quality = get_result(
            evidence_id,
            "IMAGE_QUALITY"
        )

        quality_gate = get_result(
            evidence_id,
            "QUALITY_GATE"
        )

        forensics = get_result(
            evidence_id,
            "FORENSICS"
        )

        metadata = get_result(
            evidence_id,
            "METADATA"
        )

        ocr = get_result(
            evidence_id,
            "OCR"
        )

        ocr_entities = get_result(
            evidence_id,
            "OCR_ENTITIES"
        )

        ai_generation = get_result(
            evidence_id,
            "AI_GENERATION"
        )

        evidence = next(
            (
                item
                for item in claim.evidence
                if item.id == evidence_id
            ),
            None
        )

        # ----------------------------------------------
        # QUALITY
        # ----------------------------------------------

        quality_dimension = {
            "image_quality": {
                "status": (
                    image_quality.status
                    if image_quality
                    else "UNAVAILABLE"
                ),
                "brightness": None,
                "contrast": None,
                "sharpness": None,
                "width": None,
                "height": None
            },
            "quality_gate": {
                "status": (
                    quality_gate.status
                    if quality_gate
                    else "UNAVAILABLE"
                ),
                "quality_status": None,
                "reasons": []
            }
        }

        if (
            image_quality
            and image_quality.result
        ):

            quality_dimension[
                "image_quality"
            ].update({
                "brightness": image_quality.result.get(
                    "brightness_mean"
                ),
                "contrast": image_quality.result.get(
                    "contrast_std"
                ),
                "sharpness": image_quality.result.get(
                    "sharpness_score"
                ),
                "width": image_quality.result.get(
                    "width"
                ),
                "height": image_quality.result.get(
                    "height"
                )
            })

        if (
            quality_gate
            and quality_gate.result
        ):

            quality_dimension[
                "quality_gate"
            ].update({
                "quality_status":
                    quality_gate.result.get(
                        "quality_status"
                    ),
                "reasons":
                    quality_gate.result.get(
                        "reasons",
                        []
                    )
            })

        # ----------------------------------------------
        # FORENSIC
        # ----------------------------------------------

        forensic_dimension = {
            "status": (
                forensics.status
                if forensics
                else "UNAVAILABLE"
            ),
            "ela_mean_difference": None,
            "ela_enhanced_mean": None,
            "ela_max_difference": None
        }

        if (
            forensics
            and forensics.result
        ):

            forensic_dimension.update({
                "ela_mean_difference":
                    forensics.result.get(
                        "ela_mean_difference"
                    ),
                "ela_enhanced_mean":
                    forensics.result.get(
                        "ela_enhanced_mean"
                    ),
                "ela_max_difference":
                    forensics.result.get(
                        "ela_max_difference"
                    )
            })

        # ----------------------------------------------
        # PROVENANCE
        # ----------------------------------------------

        provenance_dimension = {
            "status": (
                metadata.status
                if metadata
                else "UNAVAILABLE"
            ),
            "format": None,
            "file_size_bytes": None,
            "exif_available": False
        }

        if (
            metadata
            and metadata.result
        ):

            provenance_dimension.update({
                "format":
                    metadata.result.get(
                        "format"
                    ),
                "file_size_bytes":
                    metadata.result.get(
                        "file_size_bytes"
                    ),
                "exif_available":
                    bool(
                        metadata.result.get(
                            "exif"
                        )
                    )
            })

        # ----------------------------------------------
        # CONTENT
        # ----------------------------------------------

        content_dimension = {
            "ocr": {
                "status": (
                    ocr.status
                    if ocr
                    else "UNAVAILABLE"
                ),
                "text_available": False,
                "text_length": 0,
                "word_count": 0
            },
            "ocr_entities": {
                "status": (
                    ocr_entities.status
                    if ocr_entities
                    else "UNAVAILABLE"
                ),
                "text_available": False,
                "entity_counts": {
                    "urls": 0,
                    "dates": 0,
                    "datetimes": 0,
                    "identifiers": 0,
                    "emails": 0,
                    "phone_numbers": 0,
                    "financial_amounts": 0
                }
            }
        }

        if (
            ocr
            and ocr.result
        ):

            ocr_text = ocr.result.get(
                "text"
            )

            content_dimension[
                "ocr"
            ].update({
                "text_available": bool(
                    ocr_text
                    and str(ocr_text).strip()
                ),
                "text_length":
                    ocr.result.get(
                        "text_length",
                        0
                    ),
                "word_count":
                    ocr.result.get(
                        "word_count",
                        0
                    )
            })

        if (
            ocr_entities
            and ocr_entities.result
        ):

            entity_result = (
                ocr_entities.result
            )

            content_dimension[
                "ocr_entities"
            ].update({
                "text_available":
                    entity_result.get(
                        "text_available",
                        False
                    ),
                "entity_counts": {
                    "urls": len(
                        entity_result.get(
                            "urls",
                            []
                        )
                    ),
                    "dates": len(
                        entity_result.get(
                            "dates",
                            []
                        )
                    ),
                    "datetimes": len(
                        entity_result.get(
                            "datetimes",
                            []
                        )
                    ),
                    "identifiers": len(
                        entity_result.get(
                            "identifiers",
                            []
                        )
                    ),
                    "emails": len(
                        entity_result.get(
                            "emails",
                            []
                        )
                    ),
                    "phone_numbers": len(
                        entity_result.get(
                            "phone_numbers",
                            []
                        )
                    ),
                    "financial_amounts": len(
                        entity_result.get(
                            "financial_amounts",
                            []
                        )
                    )
                }
            })

        # ----------------------------------------------
        # GENERATIVE
        # ----------------------------------------------

        generative_dimension = {
            "status": (
                ai_generation.status
                if ai_generation
                else "UNAVAILABLE"
            ),
            "model_available": False,
            "model_version": None,
            "prediction": None,
            "confidence": None
        }

        if (
            ai_generation
            and ai_generation.result
        ):

            generative_dimension.update({
                "model_available":
                    ai_generation.result.get(
                        "model_available",
                        False
                    ),
                "model_version":
                    ai_generation.result.get(
                        "model_version"
                    ),
                "prediction":
                    ai_generation.result.get(
                        "prediction"
                    ),
                "confidence":
                    ai_generation.result.get(
                        "confidence"
                    )
            })

        evidence_signal_summary[
            str(evidence_id)
        ] = {
            "evidence_type": (
                evidence.evidence_type
                if evidence
                else None
            ),
            "quality": quality_dimension,
            "forensic": forensic_dimension,
            "provenance": provenance_dimension,
            "content": content_dimension,
            "generative": generative_dimension
        }

    # --------------------------------------------------
    # 3. Evidence reliability
    # --------------------------------------------------

    evidence_reliability_summary = {}

    for evidence_id, results in evidence_results.items():

        reliability = get_result(
            evidence_id,
            "EVIDENCE_RELIABILITY"
        )

        if not reliability:
            continue

        evidence_reliability_summary[
            str(evidence_id)
        ] = reliability.result

    # --------------------------------------------------
    # 4. Cross-evidence signals
    # --------------------------------------------------

    cross_evidence = next(
        (
            analysis
            for analysis in claim_level_results
            if analysis.analysis_type
            == "CROSS_EVIDENCE"
        ),
        None
    )

    cross_evidence_summary = {
        "available": False,
        "status": "UNAVAILABLE",
        "match_count": 0,
        "conflict_count": 0,
        "not_comparable_count": 0
    }

    if (
        cross_evidence
        and cross_evidence.result
    ):

        comparison_summary = (
            cross_evidence.result.get(
                "comparison_summary",
                {}
            )
        )

        cross_evidence_summary.update({
            "available": True,
            "status": cross_evidence.status,
            "match_count":
                comparison_summary.get(
                    "match_count",
                    0
                ),
            "conflict_count":
                comparison_summary.get(
                    "conflict_count",
                    0
                ),
            "not_comparable_count":
                comparison_summary.get(
                    "not_comparable_count",
                    0
                )
        })

    # --------------------------------------------------
    # 5. Pipeline completeness
    # --------------------------------------------------

    total_count = len(
        analysis_results
    )

    completed_count = sum(
        1
        for analysis in analysis_results
        if analysis.status == "COMPLETED"
    )

    analysis_completion_ratio = (
        completed_count / total_count
        if total_count
        else 0
    )

    # --------------------------------------------------
    # 6. Research observations
    # --------------------------------------------------

    observations = []
    limitations = []

    # Evidence availability
    if claim.evidence:

        observations.append(
            f"{len(claim.evidence)} evidence items "
            "were available for structured fusion."
        )

    # OCR
    ocr_available_count = sum(
        1
        for evidence_id in evidence_signal_summary
        if evidence_signal_summary[
            evidence_id
        ]["content"]["ocr"]["text_available"]
    )

    if ocr_available_count:

        observations.append(
            f"OCR text was available for "
            f"{ocr_available_count} of "
            f"{len(evidence_signal_summary)} "
            "evidence items."
        )

    # Structured entities
    structured_entity_count = sum(
        sum(
            dimension_count
            for dimension_count in
            evidence_signal_summary[
                evidence_id
            ]["content"]["ocr_entities"]
            ["entity_counts"].values()
        )
        for evidence_id in evidence_signal_summary
    )

    if structured_entity_count:

        observations.append(
            "Structured OCR entities were "
            "available across the evidence set."
        )

    # Cross-evidence conflicts
    if (
        cross_evidence_summary[
            "conflict_count"
        ] == 0
    ):

        observations.append(
            "No direct cross-evidence conflict "
            "was established under the current "
            "applicability-aware comparison rules."
        )

    else:

        observations.append(
            f"{cross_evidence_summary['conflict_count']} "
            "cross-evidence conflict(s) were detected."
        )

    # Not comparable
    if (
        cross_evidence_summary[
            "not_comparable_count"
        ] > 0
    ):

        observations.append(
            f"{cross_evidence_summary['not_comparable_count']} "
            "comparisons were not comparable because "
            "the current rules did not establish a "
            "valid shared field or identity."
        )

    # Quality warnings
    quality_warning_count = sum(
        1
        for evidence_id in evidence_signal_summary
        if evidence_signal_summary[
            evidence_id
        ]["quality"]["quality_gate"]
        ["quality_status"] == "WARNING"
    )

    if quality_warning_count:

        observations.append(
            f"{quality_warning_count} evidence item(s) "
            "received a quality warning."
        )

    # AI generation limitation
    ai_available_count = sum(
        1
        for evidence_id in evidence_signal_summary
        if evidence_signal_summary[
            evidence_id
        ]["generative"]["model_available"]
    )

    if ai_available_count == 0:

        limitations.append(
            "AI-generated image detection is "
            "not currently available."
        )

    # Calibration limitation
    limitations.append(
        "Fusion observations are descriptive and "
        "are not calibrated authenticity probabilities."
    )

    # Numerical weighting limitation
    limitations.append(
        "No numerical reliability weights or "
        "trust scores are calculated at this stage."
    )

    # Pipeline completeness
    if completed_count < total_count:

        limitations.append(
            f"{total_count - completed_count} "
            "analysis result(s) are not completed."
        )

    # --------------------------------------------------
    # 7. Final fusion inputs
    # --------------------------------------------------

    fusion_inputs = {
        "evidence_dimensions":
            evidence_signal_summary,

        "evidence_reliability":
            evidence_reliability_summary,

        "cross_evidence_signals":
            cross_evidence_summary,

        "pipeline_completeness": {
            "analysis_count": total_count,
            "completed_analysis_count":
                completed_count,
            "analysis_completion_ratio":
                round(
                    analysis_completion_ratio,
                    4
                )
        },

        "research_observations":
            observations,

        "research_limitations":
            limitations
    }

    return {
        "status": "COMPLETED",

        "result": {
            "fusion_inputs": fusion_inputs,

            "fusion_status":
                "BASELINE_SIGNALS_READY",

            "analysis_count":
                total_count,

            "evidence_count":
                len(evidence_signal_summary),

            "completed_analysis_count":
                completed_count,

            "analysis_completion_ratio":
                round(
                    analysis_completion_ratio,
                    4
                ),

            "evidence_analysis_summary":
                analysis_summary
        },

        "message": (
            "Research-structured evidence fusion inputs "
            "and transparent interpretation observations "
            "were assembled successfully. No numerical "
            "reliability weight, authenticity score, or "
            "trust score is generated at this stage."
        )
    }