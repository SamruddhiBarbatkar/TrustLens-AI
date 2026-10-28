from app.analysis.base import create_analysis_output


def analyze_trust_assessment(
    claim,
    verification_run
):
    """Build an evidence-aware, categorical trust assessment.

    The result is decision support, not a calibrated probability or a
    conclusive authenticity/fraud verdict. Detected forensic risk signals
    take precedence so they cannot be hidden by an otherwise incomplete
    pipeline.
    """

    try:
        uncertainty_result = None
        fusion_result = None
        cross_evidence_result = None
        calibrated_fusion_result = None
        tampering_results = []
        ai_generation_results = []

        for analysis in verification_run.analysis_results:
            if analysis.analysis_type == "UNCERTAINTY":
                uncertainty_result = analysis.result
            elif analysis.analysis_type == "FUSION":
                fusion_result = analysis.result
            elif analysis.analysis_type == "CROSS_EVIDENCE":
                cross_evidence_result = analysis.result
            elif analysis.analysis_type == "RELIABILITY_CALIBRATED_FUSION":
                calibrated_fusion_result = analysis.result
            elif analysis.analysis_type == "TAMPERING_DETECTION":
                tampering_results.append(analysis)
            elif analysis.analysis_type == "AI_GENERATION":
                ai_generation_results.append(analysis)

        uncertainty_available = uncertainty_result is not None
        cross_evidence_available = cross_evidence_result is not None

        uncertainty_result = uncertainty_result or {}
        cross_evidence_result = cross_evidence_result or {}

        uncertainty_sources = uncertainty_result.get(
            "uncertainty_sources",
            []
        )
        missing_evidence_count = uncertainty_result.get(
            "missing_evidence_count",
            0
        )
        analysis_completion_ratio = uncertainty_result.get(
            "analysis_completion_ratio",
            0.0
        )

        risk_signals = []

        for analysis in tampering_results:
            result = analysis.result or {}

            if (
                analysis.status == "COMPLETED"
                and result.get("prediction") == "TAMPERED"
            ):
                risk_signals.append({
                    "type": "TAMPERING_DETECTED",
                    "evidence_id": analysis.evidence_id,
                    "prediction": result.get("prediction"),
                    "confidence": result.get("confidence"),
                    "message": (
                        "The tampering model identified a manipulation "
                        "signal that requires human review."
                    )
                })

        for analysis in ai_generation_results:
            result = analysis.result or {}

            if (
                analysis.status == "COMPLETED"
                and result.get("prediction") == "AI_GENERATED"
            ):
                risk_signals.append({
                    "type": "AI_GENERATION_DETECTED",
                    "evidence_id": analysis.evidence_id,
                    "prediction": result.get("prediction"),
                    "confidence": result.get("confidence"),
                    "message": (
                        "The AI-generation model identified a synthetic-"
                        "image signal that requires human review."
                    )
                })

        comparison_summary = cross_evidence_result.get(
            "comparison_summary",
            {}
        )
        conflict_count = comparison_summary.get(
            "conflict_count",
            0
        )

        if conflict_count > 0:
            risk_signals.append({
                "type": "CROSS_EVIDENCE_CONFLICT",
                "evidence_id": None,
                "conflict_count": conflict_count,
                "message": (
                    f"{conflict_count} cross-evidence conflict(s) require "
                    "human review."
                )
            })

        if (
            calibrated_fusion_result
            and calibrated_fusion_result.get("score_status")
            != "UNAVAILABLE"
            and calibrated_fusion_result.get("decision")
            == "REVIEW_NEEDED"
        ):
            risk_signals.append({
                "type": "CALIBRATED_FUSION_REVIEW",
                "evidence_id": None,
                "trust_score": calibrated_fusion_result.get("trust_score"),
                "uncertainty": calibrated_fusion_result.get("uncertainty"),
                "conflict": calibrated_fusion_result.get("conflict"),
                "message": calibrated_fusion_result.get(
                    "decision_reason",
                    "Reliability-calibrated fusion requires human review."
                )
            })

        has_analysis_error = (
            "ANALYSIS_ERROR" in uncertainty_sources
            or "ANALYSIS_ERRORS" in uncertainty_sources
        )
        has_model_unavailable = (
            "AI_GENERATION_ANALYSIS_UNAVAILABLE"
            in uncertainty_sources
        )
        has_tampering_unavailable = any(
            analysis.status != "COMPLETED"
            or not (analysis.result or {}).get(
                "model_available",
                False
            )
            for analysis in tampering_results
        )
        has_ai_generation_unavailable = any(
            analysis.status != "COMPLETED"
            or not (analysis.result or {}).get(
                "model_available",
                False
            )
            for analysis in ai_generation_results
        )
        has_quality_warning = (
            "EVIDENCE_QUALITY_WARNING"
            in uncertainty_sources
        )
        has_limited_comparability = (
            "LIMITED_CROSS_EVIDENCE_COMPARABILITY"
            in uncertainty_sources
        )
        has_incomplete_analysis = (
            "INCOMPLETE_ANALYSIS"
            in uncertainty_sources
        )
        has_incomplete_pipeline = (
            "INCOMPLETE_PIPELINE"
            in uncertainty_sources
        )

        reasons = []

        if risk_signals:
            assessment = "REVIEW_NEEDED"
            reasons.extend(
                signal["message"]
                for signal in risk_signals
            )

            if missing_evidence_count > 0:
                reasons.append(
                    "Required evidence is also missing."
                )

            if has_analysis_error:
                reasons.append(
                    "One or more analysis stages also encountered "
                    "processing errors."
                )

        elif missing_evidence_count > 0:
            assessment = "INCONCLUSIVE"
            reasons.append(
                "Required evidence is missing."
            )

        elif has_analysis_error:
            assessment = "INCONCLUSIVE"
            reasons.append(
                "One or more analysis stages encountered processing "
                "errors."
            )

        else:
            assessment = "LOW_CONCERN"

            if (
                has_model_unavailable
                or has_ai_generation_unavailable
            ):
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "AI-generated image analysis is currently unavailable."
                )

            if has_tampering_unavailable:
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "Tampering detection is currently unavailable for one "
                    "or more evidence items."
                )

            if has_quality_warning:
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "One or more evidence items have quality warnings."
                )

            if has_limited_comparability:
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "Some cross-evidence comparisons could not be "
                    "established under the current rules."
                )

            if has_incomplete_analysis:
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "One or more analysis stages did not produce "
                    "completed results."
                )

            if has_incomplete_pipeline:
                assessment = "REVIEW_NEEDED"
                reasons.append(
                    "The verification pipeline is not fully complete."
                )

        if not reasons:
            reasons.append(
                "No current forensic risk or baseline uncertainty "
                "condition requiring additional review was detected."
            )

        interpretation = {
            "low_concern": (
                "No current forensic risk or baseline uncertainty "
                "condition requiring additional review was detected."
            ),
            "inconclusive": (
                "The system does not have enough valid information to "
                "perform a meaningful baseline assessment."
            ),
            "review_needed": (
                "One or more forensic risk signals, evidence conflicts, "
                "or capability limitations require human review."
            )
        }

        if assessment == "INCONCLUSIVE":
            assessment_basis = (
                "The available evidence or completed analysis is "
                "insufficient for a meaningful baseline assessment."
            )
        elif assessment == "REVIEW_NEEDED":
            assessment_basis = (
                "One or more evidence-linked forensic signals, conflicts, "
                "or analysis limitations require human review."
            )
        else:
            assessment_basis = (
                "The current rule set found no forensic risk or baseline "
                "uncertainty condition requiring additional review."
            )

        result = {
            "assessment": assessment,
            "trust_score": (
                calibrated_fusion_result.get("trust_score")
                if calibrated_fusion_result
                else None
            ),
            "fraud_evidence": (
                calibrated_fusion_result.get("fraud_evidence")
                if calibrated_fusion_result
                else None
            ),
            "fusion_uncertainty": (
                calibrated_fusion_result.get("uncertainty")
                if calibrated_fusion_result
                else None
            ),
            "fusion_conflict": (
                calibrated_fusion_result.get("conflict")
                if calibrated_fusion_result
                else None
            ),
            "score_status": (
                calibrated_fusion_result.get("score_status")
                if calibrated_fusion_result
                else "UNAVAILABLE"
            ),
            "fusion_sources": (
                calibrated_fusion_result.get("sources", [])
                if calibrated_fusion_result
                else []
            ),
            "conditional_branch_status": (
                calibrated_fusion_result.get(
                    "conditional_branch_status",
                    [],
                )
                if calibrated_fusion_result
                else []
            ),
            "unavailable_fusion_branches": (
                calibrated_fusion_result.get("unavailable_branches", [])
                if calibrated_fusion_result
                else []
            ),
            "trust_score_note": (
                "Reliability-calibrated Dempster-Shafer decision-support "
                "indicator. The active calibration and thresholds passed "
                "held-out validation; the score is still not a probability "
                "of authenticity or a conclusive fraud verdict."
                if (
                    calibrated_fusion_result
                    and calibrated_fusion_result.get("score_status")
                    == "VALIDATED_CALIBRATED"
                )
                else
                "Reliability-calibrated Dempster-Shafer decision-support "
                "indicator. It remains provisional until calibration and "
                "threshold validation are completed."
            ),
            "reasons": reasons,
            "risk_signals": risk_signals,
            "assessment_basis": assessment_basis,
            "interpretation": interpretation,
            "inputs_available": {
                "fusion": fusion_result is not None,
                "reliability_calibrated_fusion": (
                    calibrated_fusion_result is not None
                ),
                "uncertainty": uncertainty_available,
                "cross_evidence": cross_evidence_available,
                "tampering": bool(tampering_results),
                "ai_generation": bool(ai_generation_results)
            },
            "uncertainty_factors": uncertainty_sources,
            "missing_evidence_count": missing_evidence_count,
            "analysis_completion_ratio": analysis_completion_ratio,
            "cross_evidence_conflict_count": conflict_count
        }

        return create_analysis_output(
            analysis_type="TRUST_ASSESSMENT",
            evidence_id=None,
            status="COMPLETED",
            result=result,
            message=(
                "Evidence-aware trust assessment completed. The result "
                "supports human review and is not a calibrated authenticity "
                "probability or conclusive fraud verdict."
            )
        )

    except Exception as error:
        return create_analysis_output(
            analysis_type="TRUST_ASSESSMENT",
            evidence_id=None,
            status="ERROR",
            result=None,
            message=(
                f"Trust assessment failed: {str(error)}"
            )
        )
