"""Reliability-calibrated evidence fusion for TrustLens.

The mathematical fusion supports both the bundled provisional policy and an
explicitly validated active artifact. Even a validated Trust Score is a
decision-support indicator, not a probability of authenticity or a fraud
verdict.
"""

import json
import math
from pathlib import Path

from app.analysis.base import create_analysis_output
from app.analysis.calibration_training import temperature_scale


POLICY_PATH = Path(__file__).with_name("fusion_policy.json")
ACTIVE_POLICY_PATH = (
    Path(__file__).resolve().parents[2]
    / "calibration"
    / "artifacts"
    / "active.json"
)


def _load_fusion_policy():
    with POLICY_PATH.open("r", encoding="utf-8") as policy_file:
        policy = json.load(policy_file)

    required_sections = {
        "policy_version",
        "validated",
        "calibration",
        "quality_reliability",
        "thresholds",
    }
    missing = required_sections.difference(policy)
    if missing:
        raise RuntimeError(
            "Fusion policy is missing required fields: "
            + ", ".join(sorted(missing))
        )
    if ACTIVE_POLICY_PATH.is_file():
        with ACTIVE_POLICY_PATH.open("r", encoding="utf-8") as artifact_file:
            artifact = json.load(artifact_file)
        if not artifact.get("validated", False):
            raise RuntimeError(
                "The active calibration artifact is not marked validated."
            )
        policy = {
            **policy,
            **artifact,
            "thresholds": {
                **policy["thresholds"],
                **artifact.get("thresholds", {}),
            },
        }
    return policy


FUSION_POLICY = _load_fusion_policy()


def _clamp(value):
    return max(0.0, min(float(value), 1.0))


def _conditional_policy(branch_name):
    policy = FUSION_POLICY.get("conditional_branches", {}).get(
        branch_name,
        {},
    )
    if not policy.get("enabled", False):
        return None, "CALIBRATION_NOT_ACTIVATED"
    if not policy.get("validated", False):
        return None, "CALIBRATION_NOT_VALIDATED"
    calibrated_branches = FUSION_POLICY.get("thresholds", {}).get(
        "calibrated_branches",
        [],
    )
    if branch_name not in calibrated_branches:
        return None, "THRESHOLDS_NOT_RECALIBRATED"
    return policy, None


def _reliability_for_policy(policy, quality_status="OVERALL"):
    reliability_by_quality = policy.get("reliability_by_quality", {})
    reliability = reliability_by_quality.get(
        quality_status,
        reliability_by_quality.get("OVERALL"),
    )
    if reliability is None:
        return None
    return _clamp(reliability)


def _logistic_feature_probability(value, transform):
    """Map a scalar forensic feature using validated location and scale."""
    if transform.get("method") != "LOGISTIC":
        return None
    center = transform.get("center")
    scale = transform.get("scale")
    if center is None or scale is None or float(scale) <= 0:
        return None
    exponent = -(float(value) - float(center)) / float(scale)
    if exponent >= 700:
        return 0.0
    if exponent <= -700:
        return 1.0
    return 1.0 / (1.0 + math.exp(exponent))


def make_belief_mass(suspicious_probability, reliability):
    """Convert a calibrated suspicious probability into A/F/Theta mass."""
    probability = _clamp(suspicious_probability)
    reliability = _clamp(reliability)
    return {
        "authentic": reliability * (1.0 - probability),
        "fraud": reliability * probability,
        "uncertainty": 1.0 - reliability,
    }


def combine_belief_masses(left, right):
    """Combine two binary belief assignments using Dempster's rule."""
    conflict = (
        left["authentic"] * right["fraud"]
        + left["fraud"] * right["authentic"]
    )
    denominator = 1.0 - conflict

    if denominator <= 1e-12:
        return None, 1.0

    combined = {
        "authentic": (
            left["authentic"] * right["authentic"]
            + left["authentic"] * right["uncertainty"]
            + left["uncertainty"] * right["authentic"]
        ) / denominator,
        "fraud": (
            left["fraud"] * right["fraud"]
            + left["fraud"] * right["uncertainty"]
            + left["uncertainty"] * right["fraud"]
        ) / denominator,
        "uncertainty": (
            left["uncertainty"] * right["uncertainty"]
        ) / denominator,
    }
    return combined, conflict


def fuse_sources(sources):
    """Fuse source dictionaries and preserve cumulative disagreement."""
    if not sources:
        return None

    combined = sources[0]["mass"]
    remaining_agreement = 1.0
    steps = []

    for source in sources[1:]:
        combined, step_conflict = combine_belief_masses(
            combined,
            source["mass"],
        )
        remaining_agreement *= 1.0 - step_conflict
        steps.append({
            "source": source["source"],
            "step_conflict": round(step_conflict, 6),
        })
        if combined is None:
            break

    return {
        "mass": combined,
        "conflict": 1.0 - remaining_agreement,
        "combination_steps": steps,
    }


def _result_for(verification_run, analysis_type, evidence_id=None):
    return next(
        (
            item
            for item in verification_run.analysis_results
            if item.analysis_type == analysis_type
            and item.evidence_id == evidence_id
        ),
        None,
    )


def _quality_reliability(verification_run, evidence_id, analysis_type):
    quality = _result_for(verification_run, "QUALITY_GATE", evidence_id)
    quality_status = (
        (quality.result or {}).get("quality_status", "UNKNOWN")
        if quality and quality.status == "COMPLETED"
        else "UNKNOWN"
    )
    detector_policy = FUSION_POLICY.get("detectors", {}).get(
        analysis_type,
        {},
    )
    calibrated_reliability = detector_policy.get("reliability_by_quality", {})
    reliability = calibrated_reliability.get(
        quality_status,
        calibrated_reliability.get(
            "OVERALL",
            FUSION_POLICY["quality_reliability"].get(
                quality_status,
                FUSION_POLICY["quality_reliability"]["UNKNOWN"],
            ),
        ),
    )
    return quality_status, reliability


def _matches_calibrated_checkpoint(result, analysis_type):
    expected = (
        FUSION_POLICY.get("data_summary", {})
        .get("model_checkpoints", {})
        .get(analysis_type)
    )
    if not expected:
        return True
    return (
        result.get("model_version") == expected.get("model_version")
        and result.get("model_sha256") == expected.get("model_sha256")
    )


def _branch_source(claim, verification_run, analysis_type, probability_key):
    observations = []

    for evidence in claim.evidence:
        analysis = _result_for(
            verification_run,
            analysis_type,
            evidence.id,
        )
        result = analysis.result or {} if analysis else {}
        probability = result.get(probability_key)

        if (
            analysis is None
            or analysis.status != "COMPLETED"
            or probability is None
            or not result.get("model_available", False)
            or not _matches_calibrated_checkpoint(result, analysis_type)
        ):
            continue

        quality_status, reliability = _quality_reliability(
            verification_run,
            evidence.id,
            analysis_type,
        )
        detector_policy = FUSION_POLICY.get("detectors", {}).get(
            analysis_type,
            {},
        )
        temperature = detector_policy.get("temperature", 1.0)
        calibrated_probability = temperature_scale(probability, temperature)
        observations.append({
            "evidence_id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "raw_probability": round(_clamp(probability), 6),
            "calibrated_probability": round(calibrated_probability, 6),
            "temperature": temperature,
            "reliability": reliability,
            "quality_status": quality_status,
            "model_version": result.get("model_version"),
        })

    if not observations:
        return None

    total_reliability = sum(item["reliability"] for item in observations)
    calibrated_probability = (
        sum(
            item["calibrated_probability"] * item["reliability"]
            for item in observations
        ) / total_reliability
        if total_reliability
        else 0.5
    )
    reliability = sum(
        item["reliability"] for item in observations
    ) / len(observations)

    source_name = {
        "TAMPERING_DETECTION": "VISUAL_MANIPULATION_BRANCH",
        "AI_GENERATION": "SOURCE_AUTHENTICITY_BRANCH",
    }[analysis_type]

    return {
        "source": source_name,
        "analysis_type": analysis_type,
        "calibrated_suspicious_probability": round(
            calibrated_probability,
            6,
        ),
        "reliability": round(reliability, 6),
        "mass": make_belief_mass(calibrated_probability, reliability),
        "observations": observations,
    }


def _ela_support_source(claim, verification_run):
    policy, exclusion_reason = _conditional_policy("ELA_SUPPORT")
    if policy is None:
        return None, {
            "branch": "ELA_SUPPORT",
            "status": "EXCLUDED",
            "reason": exclusion_reason,
        }

    observations = []
    expected_version = policy.get("analysis_version")
    feature_name = policy.get("feature", "ela_enhanced_mean")
    for evidence in claim.evidence:
        analysis = _result_for(
            verification_run,
            "FORENSICS",
            evidence.id,
        )
        result = analysis.result or {} if analysis else {}
        if (
            analysis is None
            or analysis.status != "COMPLETED"
            or not result.get("ela_applicable", False)
            or result.get(feature_name) is None
            or result.get("analysis_version") != expected_version
        ):
            continue

        quality_status, _ = _quality_reliability(
            verification_run,
            evidence.id,
            "TAMPERING_DETECTION",
        )
        reliability = _reliability_for_policy(policy, quality_status)
        raw_probability = _logistic_feature_probability(
            result[feature_name],
            policy.get("transform", {}),
        )
        if reliability is None or raw_probability is None:
            continue
        calibrated_probability = temperature_scale(
            raw_probability,
            policy.get("temperature", 1.0),
        )
        observations.append({
            "evidence_id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "feature": feature_name,
            "feature_value": result[feature_name],
            "raw_probability": round(raw_probability, 6),
            "calibrated_probability": round(calibrated_probability, 6),
            "reliability": round(reliability, 6),
            "quality_status": quality_status,
            "analysis_version": result.get("analysis_version"),
        })

    if not observations:
        return None, {
            "branch": "ELA_SUPPORT",
            "status": "NOT_APPLICABLE",
            "reason": "NO_COMPATIBLE_ELA_OBSERVATIONS",
        }

    total_reliability = sum(item["reliability"] for item in observations)
    probability = (
        sum(
            item["calibrated_probability"] * item["reliability"]
            for item in observations
        ) / total_reliability
        if total_reliability
        else 0.5
    )
    reliability = sum(
        item["reliability"] for item in observations
    ) / len(observations)
    source = {
        "source": "ELA_SUPPORT",
        "analysis_type": "FORENSICS",
        "calibrated_suspicious_probability": round(probability, 6),
        "reliability": round(reliability, 6),
        "mass": make_belief_mass(probability, reliability),
        "observations": observations,
        "visual_support_weight": _clamp(
            policy.get("visual_support_weight", 0.25)
        ),
    }
    return source, {
        "branch": "ELA_SUPPORT",
        "status": "INCLUDED_AS_VISUAL_SUPPORT",
        "reason": "VALIDATED_AND_APPLICABLE",
    }


def _merge_visual_manipulation_source(tampering, ela_support):
    """Use ELA as discounted support without treating it as independent."""
    if tampering is None:
        if ela_support is None:
            return None
        return {
            **ela_support,
            "source": "VISUAL_MANIPULATION_BRANCH",
            "supporting_sources": ["ELA_SUPPORT"],
        }
    if ela_support is None:
        return tampering

    primary_weight = tampering["reliability"]
    support_weight = (
        ela_support["reliability"]
        * ela_support["visual_support_weight"]
    )
    denominator = primary_weight + support_weight
    probability = (
        (
            tampering["calibrated_suspicious_probability"] * primary_weight
            + ela_support["calibrated_suspicious_probability"] * support_weight
        ) / denominator
        if denominator
        else 0.5
    )
    # ELA can adjust the visual probability, but cannot inflate the branch's
    # reliability beyond the independently validated tampering reliability.
    reliability = tampering["reliability"]
    return {
        **tampering,
        "calibrated_suspicious_probability": round(probability, 6),
        "reliability": round(reliability, 6),
        "mass": make_belief_mass(probability, reliability),
        "supporting_sources": ["TAMPERING_DETECTION", "ELA_SUPPORT"],
        "ela_support": ela_support,
    }


def _ocr_consistency_source(verification_run):
    policy, exclusion_reason = _conditional_policy("OCR_CONSISTENCY")
    if policy is None:
        return None, {
            "branch": "OCR_CONSISTENCY",
            "status": "EXCLUDED",
            "reason": exclusion_reason,
        }

    cross_evidence = _result_for(
        verification_run,
        "CROSS_EVIDENCE",
        None,
    )
    result = cross_evidence.result or {} if cross_evidence else {}
    expected_version = policy.get("analysis_version")
    if result.get("analysis_version") != expected_version:
        return None, {
            "branch": "OCR_CONSISTENCY",
            "status": "EXCLUDED",
            "reason": "INCOMPATIBLE_ANALYSIS_VERSION",
        }
    summary = result.get("comparison_summary", {})
    matches = int(summary.get("match_count", 0) or 0)
    conflicts = int(summary.get("conflict_count", 0) or 0)
    comparable = matches + conflicts
    minimum_comparisons = max(
        1,
        int(policy.get("minimum_comparisons", 1)),
    )
    if comparable < minimum_comparisons:
        return None, {
            "branch": "OCR_CONSISTENCY",
            "status": "NOT_APPLICABLE",
            "reason": "INSUFFICIENT_COMPARABLE_TEXT_FIELDS",
            "comparable_field_count": comparable,
        }

    reliability = _reliability_for_policy(policy)
    if reliability is None:
        return None, {
            "branch": "OCR_CONSISTENCY",
            "status": "EXCLUDED",
            "reason": "MISSING_VALIDATED_RELIABILITY",
        }

    # Jeffreys smoothing avoids absolute 0/1 claims from a small number of
    # text comparisons. Calibration is still mandatory before activation.
    raw_probability = (conflicts + 0.5) / (comparable + 1.0)
    probability = temperature_scale(
        raw_probability,
        policy.get("temperature", 1.0),
    )
    source = {
        "source": "DOCUMENT_CONSISTENCY_BRANCH",
        "analysis_type": "OCR_CONSISTENCY",
        "analysis_version": policy.get("analysis_version"),
        "calibrated_suspicious_probability": round(probability, 6),
        "reliability": round(reliability, 6),
        "mass": make_belief_mass(probability, reliability),
        "observations": [{
            "match_count": matches,
            "conflict_count": conflicts,
            "comparable_field_count": comparable,
            "raw_probability": round(raw_probability, 6),
            "calibrated_probability": round(probability, 6),
        }],
    }
    return source, {
        "branch": "OCR_CONSISTENCY",
        "status": "INCLUDED",
        "reason": "VALIDATED_AND_APPLICABLE",
        "comparable_field_count": comparable,
    }


def _decision_for(trust, uncertainty, conflict):
    thresholds = FUSION_POLICY["thresholds"]
    qualifier = (
        "validated" if FUSION_POLICY.get("validated", False)
        else "provisional"
    )
    if conflict >= thresholds["conflict_review"]:
        return "REVIEW_NEEDED", f"Detector conflict exceeds the {qualifier} review threshold."
    if uncertainty >= thresholds["uncertainty_review"]:
        return "REVIEW_NEEDED", f"Unresolved uncertainty exceeds the {qualifier} review threshold."
    if trust >= thresholds["approve"]:
        return "LOW_CONCERN", f"Trust exceeds the {qualifier} approval threshold."
    if trust <= thresholds["reject"]:
        return "REVIEW_NEEDED", f"Trust is below the {qualifier} rejection threshold."
    return "REVIEW_NEEDED", f"Trust falls inside the {qualifier} manual-review interval."


def analyze_reliability_calibrated_fusion(claim, verification_run):
    sources = []
    unavailable_branches = []
    branch_status = []

    tampering = _branch_source(
        claim,
        verification_run,
        "TAMPERING_DETECTION",
        "tampered_probability",
    )
    ela_support, ela_status = _ela_support_source(
        claim,
        verification_run,
    )
    branch_status.append(ela_status)
    visual_manipulation = _merge_visual_manipulation_source(
        tampering,
        ela_support,
    )
    if visual_manipulation:
        sources.append(visual_manipulation)
    else:
        unavailable_branches.append("VISUAL_MANIPULATION_BRANCH")

    synthetic = _branch_source(
        claim,
        verification_run,
        "AI_GENERATION",
        "ai_generated_probability",
    )
    if synthetic:
        sources.append(synthetic)
    else:
        unavailable_branches.append("SOURCE_AUTHENTICITY_BRANCH")

    ocr_consistency, ocr_status = _ocr_consistency_source(
        verification_run,
    )
    branch_status.append(ocr_status)
    if ocr_consistency:
        sources.append(ocr_consistency)
    else:
        unavailable_branches.append(
            "DOCUMENT_CONSISTENCY_CALIBRATED_BRANCH"
        )

    fusion = fuse_sources(sources)
    if not fusion or fusion["mass"] is None:
        result = {
            "score_status": "UNAVAILABLE",
            "method": "DEMPSTER_SHAFER",
            "policy": FUSION_POLICY,
            "source_count": len(sources),
            "sources": sources,
            "unavailable_branches": unavailable_branches,
            "conditional_branch_status": branch_status,
            "trust_score": None,
            "fraud_evidence": None,
            "uncertainty": None,
            "conflict": 100.0 if fusion else None,
            "decision": "REVIEW_NEEDED",
            "decision_reason": "Insufficient calibrated evidence for numerical fusion.",
        }
        return create_analysis_output(
            analysis_type="RELIABILITY_CALIBRATED_FUSION",
            evidence_id=None,
            status="COMPLETED",
            result=result,
            message="Calibrated fusion could not produce a score from the available branches.",
        )

    mass = fusion["mass"]
    trust = max(0.0, min(
        100.0 * (mass["authentic"] + 0.5 * mass["uncertainty"]),
        100.0,
    ))
    fraud = max(0.0, min(100.0 * mass["fraud"], 100.0))
    uncertainty = max(0.0, min(100.0 * mass["uncertainty"], 100.0))
    conflict = max(0.0, min(100.0 * fusion["conflict"], 100.0))
    decision, decision_reason = _decision_for(trust, uncertainty, conflict)
    if len(sources) < 2:
        decision = "REVIEW_NEEDED"
        decision_reason = (
            "Only one calibrated evidence branch is available; corroboration "
            "is required before an automated outcome."
        )

    policy_validated = FUSION_POLICY.get("validated", False)
    result = {
        "score_status": (
            "VALIDATED_CALIBRATED"
            if policy_validated
            else "PROVISIONAL_UNVALIDATED"
        ),
        "method": "DEMPSTER_SHAFER_WITH_PIGNISTIC_TRANSFORMATION",
        "policy": FUSION_POLICY,
        "source_count": len(sources),
        "sources": sources,
        "unavailable_branches": unavailable_branches,
        "conditional_branch_status": branch_status,
        "belief_mass": {
            key: round(value, 6) for key, value in mass.items()
        },
        "trust_score": round(trust, 2),
        "fraud_evidence": round(fraud, 2),
        "uncertainty": round(uncertainty, 2),
        "conflict": round(conflict, 2),
        "decision": decision,
        "decision_reason": decision_reason,
        "combination_steps": fusion["combination_steps"],
        "interpretation": (
            "This score uses a validated calibration artifact and "
            "quality-based reliability. It is a decision-support indicator, "
            "not a probability of authenticity or a conclusive fraud verdict."
            if policy_validated
            else
            "This score uses provisional identity calibration and "
            "quality-based reliability. It is not a validated probability "
            "of authenticity."
        ),
    }
    return create_analysis_output(
        analysis_type="RELIABILITY_CALIBRATED_FUSION",
        evidence_id=None,
        status="COMPLETED",
        result=result,
        message=(
            "Validated reliability-calibrated evidence fusion completed."
            if policy_validated
            else "Provisional reliability-calibrated evidence fusion completed."
        ),
    )
