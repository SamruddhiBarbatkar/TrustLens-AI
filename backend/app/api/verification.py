from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_admin, require_claim_access
from app.db.database import get_db
from app.db.models import (
    Claim,
    User,
    VerificationRun
)
from app.services.verification_pipeline import (
    create_verification_run
)


router = APIRouter(
    prefix="/claims",
    tags=["Verification"]
)


# ============================================================
# START VERIFICATION
# ============================================================

@router.post("/{claim_id}/verify")
def start_verification(
    claim_id: int,
    db: Session = Depends(get_db),
    administrator: User = Depends(require_admin)
):

    claim = (
        db.query(Claim)
        .filter(Claim.id == claim_id)
        .first()
    )

    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    if not claim.evidence:
        raise HTTPException(
            status_code=400,
            detail="No evidence uploaded for this claim."
        )

    if claim.status == "PENDING":
        raise HTTPException(
            status_code=409,
            detail="The claimant must submit this claim before verification."
        )

    if claim.status in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=409,
            detail="A terminal claim cannot be verified again."
        )

    try:
        run = create_verification_run(
            db=db,
            claim=claim
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Verification failed. The failed run was recorded."
            )
        ) from error

    return {
        "message": "Verification completed successfully.",
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "verification_run_id": run.id,
        "status": run.status
    }


# ============================================================
# GET ALL VERIFICATION RUNS FOR A CLAIM
# ============================================================

@router.get("/{claim_id}/verification-runs")
def get_claim_verification_runs(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    claim = (
        db.query(Claim)
        .filter(Claim.id == claim_id)
        .first()
    )

    require_claim_access(claim, current_user)

    runs = (
        db.query(VerificationRun)
        .filter(
            VerificationRun.claim_id == claim_id
        )
        .order_by(
            VerificationRun.id.desc()
        )
        .all()
    )

    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "verification_runs": [
            {
                "id": run.id,
                "claim_id": run.claim_id,
                "status": run.status,
                "pipeline_version": run.pipeline_version,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "analysis_count": len(
                    run.analysis_results
                )
            }
            for run in runs
        ]
    }


# ============================================================
# GET SINGLE VERIFICATION RUN
# ============================================================

@router.get("/verification/{run_id}")
def get_verification_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    run = (
        db.query(VerificationRun)
        .filter(VerificationRun.id == run_id)
        .first()
    )

    if not run:
        raise HTTPException(
            status_code=404,
            detail="Verification run not found."
        )

    require_claim_access(run.claim, current_user)

    can_view_results = (
        current_user.role == "ADMIN"
        or run.claim.status in {"APPROVED", "REJECTED"}
    )

    return {
        "id": run.id,
        "claim_id": run.claim_id,
        "status": run.status,
        "pipeline_version": run.pipeline_version,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "results_restricted": not can_view_results,
        "result_message": (
            None
            if can_view_results
            else "Verification results will be shared after administrator review."
        ),
        "analysis_results": [
            {
                "id": result.id,
                "evidence_id": result.evidence_id,
                "analysis_type": result.analysis_type,
                "status": result.status,
                "result": result.result,
                "message": result.message
            }
            for result in run.analysis_results
            if can_view_results
        ]
    }
