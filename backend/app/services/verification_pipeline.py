from datetime import datetime, timezone

from app.db.models import (
    Claim,
    VerificationRun,
    AnalysisResult
)

from app.analysis.dispatcher import run_analysis
from app.analysis.cross_evidence import analyze_cross_evidence
from app.analysis.fusion import analyze_fusion
from app.analysis.uncertainty import analyze_uncertainty
from app.analysis.trust_assessment import analyze_trust_assessment
from app.analysis.reliability_calibrated_fusion import (
    analyze_reliability_calibrated_fusion
)
from app.analysis.evidence_reliability import (
    build_evidence_reliability_profile
)
from app.core.version import PIPELINE_VERSION

EVIDENCE_ANALYSIS_STAGES = [
    "IMAGE_QUALITY",
    "QUALITY_GATE",
    "FORENSICS",
    "TAMPERING_DETECTION",
    "TAMPERING_RESNET_SHADOW",
    "TAMPERING_MULTIVIEW_CANDIDATE",
    "AI_GENERATION",
    "METADATA",
    "OCR",
    "OCR_ENTITIES"
]


def create_analysis_result(
    db,
    verification_run,
    analysis_type,
    evidence_id=None,
    status="PENDING",
    result=None,
    message=None
):
    analysis = AnalysisResult(
        verification_run_id=verification_run.id,
        evidence_id=evidence_id,
        analysis_type=analysis_type,
        status=status,
        result=result,
        message=message
    )

    db.add(analysis)

    # Keep the SQLAlchemy relationship synchronized
    # during the current pipeline execution.
    verification_run.analysis_results.append(analysis)

    return analysis


def create_verification_run(db, claim):

    run = VerificationRun(
        claim_id=claim.id,
        status="RUNNING",
        pipeline_version=PIPELINE_VERSION,
        started_at=datetime.now(timezone.utc)
    )

    db.add(run)
    claim.status = "VERIFICATION_STARTED"
    db.commit()
    db.refresh(run)

    run_id = run.id
    claim_id = claim.id

    try:
        return execute_verification_pipeline(
            db=db,
            claim=claim,
            run=run
        )

    except Exception as error:
        db.rollback()

        failed_run = db.get(
            VerificationRun,
            run_id
        )
        failed_claim = db.get(
            Claim,
            claim_id
        )

        if failed_run is not None:
            failed_run.status = "FAILED"
            failed_run.completed_at = datetime.now(
                timezone.utc
            )

            db.add(
                AnalysisResult(
                    verification_run_id=failed_run.id,
                    evidence_id=None,
                    analysis_type="PIPELINE_ERROR",
                    status="ERROR",
                    result={
                        "error_type": type(error).__name__
                    },
                    message=(
                        "Verification pipeline failed unexpectedly."
                    )
                )
            )

        if failed_claim is not None:
            failed_claim.status = "VERIFICATION_FAILED"

        db.commit()
        raise


def execute_verification_pipeline(
    db,
    claim,
    run
):

    # --------------------------------------------------
    # 1. Evidence-level analysis
    # --------------------------------------------------

    for evidence in claim.evidence:

        image_quality_result = None
        ocr_result = None

        for stage in EVIDENCE_ANALYSIS_STAGES:

            if stage == "QUALITY_GATE":

                analysis_output = run_analysis(
                    stage,
                    evidence,
                    image_quality_result=image_quality_result
                )

            elif stage == "OCR_ENTITIES":

                analysis_output = run_analysis(
                    stage,
                    evidence,
                    ocr_result=ocr_result
                )

            else:

                analysis_output = run_analysis(
                    stage,
                    evidence
                )

                if stage == "IMAGE_QUALITY":
                    image_quality_result = (
                        analysis_output["result"]
                    )

                if stage == "OCR":
                    ocr_result = (
                        analysis_output["result"]
                    )

            create_analysis_result(
                db=db,
                verification_run=run,
                analysis_type=stage,
                evidence_id=evidence.id,
                status=analysis_output["status"],
                result=analysis_output["result"],
                message=analysis_output["message"]
            )

        db.flush()

    # --------------------------------------------------
    # 2. Evidence reliability profiles
    # --------------------------------------------------

    db.flush()

    for evidence in claim.evidence:

        reliability_output = (
            build_evidence_reliability_profile(
                db=db,
                evidence=evidence,
                verification_run_id=run.id
            )
        )

        create_analysis_result(
            db=db,
            verification_run=run,
            analysis_type="EVIDENCE_RELIABILITY",
            evidence_id=evidence.id,
            status="COMPLETED",
            result=reliability_output,
            message=(
                "Evidence reliability profile "
                "generated successfully."
            )
        )

    db.flush()

    # --------------------------------------------------
    # 3. Cross-evidence analysis
    # --------------------------------------------------

    cross_evidence_output = analyze_cross_evidence(
        db=db,
        claim=claim,
        verification_run=run
    )

    create_analysis_result(
        db=db,
        verification_run=run,
        analysis_type="CROSS_EVIDENCE",
        evidence_id=None,
        status=cross_evidence_output["status"],
        result=cross_evidence_output["result"],
        message=cross_evidence_output["message"]
    )

    db.flush()

    # --------------------------------------------------
    # 4. Evidence fusion
    # --------------------------------------------------

    fusion_output = analyze_fusion(
        claim=claim,
        verification_run=run
    )

    create_analysis_result(
        db=db,
        verification_run=run,
        analysis_type="FUSION",
        evidence_id=None,
        status=fusion_output["status"],
        result=fusion_output["result"],
        message=fusion_output["message"]
    )

    db.flush()

    # --------------------------------------------------
    # 5. Reliability-calibrated evidence fusion
    # --------------------------------------------------

    calibrated_fusion_output = analyze_reliability_calibrated_fusion(
        claim=claim,
        verification_run=run
    )

    create_analysis_result(
        db=db,
        verification_run=run,
        analysis_type="RELIABILITY_CALIBRATED_FUSION",
        evidence_id=None,
        status=calibrated_fusion_output["status"],
        result=calibrated_fusion_output["result"],
        message=calibrated_fusion_output["message"]
    )

    db.flush()

    # --------------------------------------------------
    # 6. Uncertainty analysis
    # --------------------------------------------------

    uncertainty_output = analyze_uncertainty(
        claim=claim,
        verification_run=run
    )

    create_analysis_result(
        db=db,
        verification_run=run,
        analysis_type="UNCERTAINTY",
        evidence_id=None,
        status=uncertainty_output["status"],
        result=uncertainty_output["result"],
        message=uncertainty_output["message"]
    )

    db.flush()

    # --------------------------------------------------
    # 7. Trust assessment
    # --------------------------------------------------

    trust_output = analyze_trust_assessment(
        claim=claim,
        verification_run=run
    )

    create_analysis_result(
        db=db,
        verification_run=run,
        analysis_type="TRUST_ASSESSMENT",
        evidence_id=None,
        status=trust_output["status"],
        result=trust_output["result"],
        message=trust_output["message"]
    )

    # --------------------------------------------------
    # 8. Complete verification run
    # --------------------------------------------------

    run.status = "COMPLETED"
    run.completed_at = datetime.now(timezone.utc)
    claim.status = "AWAITING_DECISION"

    db.commit()
    db.refresh(run)

    return run
