import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.version import API_VERSION, PIPELINE_VERSION
from app.ml.model_registry import HYBRID_MODES
from app.analysis.reliability_calibrated_fusion import FUSION_POLICY
from app.core.security import require_admin
from app.db.database import get_db
from app.db.models import Claim, ReviewDecision, User, VerificationRun


router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(require_admin)]
)


class ReviewDecisionRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "ESCALATE"]
    note: str
    verification_run_id: int | None = None

    @field_validator("note")
    @classmethod
    def validate_note(cls, value):
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("A review note of at least 3 characters is required.")
        if len(normalized) > 2000:
            raise ValueError("Review notes cannot exceed 2000 characters.")
        return normalized


def latest_run_for(claim):
    if not claim.verification_runs:
        return None
    return max(claim.verification_runs, key=lambda run: run.id)


def trust_result_for(run):
    if run is None:
        return None

    return next(
        (
            analysis.result
            for analysis in run.analysis_results
            if analysis.analysis_type == "TRUST_ASSESSMENT"
            and analysis.status == "COMPLETED"
        ),
        None
    )


def trust_assessment_for(run):
    result = trust_result_for(run)
    return result.get("assessment") if result else None


def serialize_decision(decision):
    return {
        "id": decision.id,
        "claim_id": decision.claim_id,
        "verification_run_id": decision.verification_run_id,
        "action": decision.action,
        "note": decision.note,
        "previous_status": decision.previous_status,
        "resulting_status": decision.resulting_status,
        "assessment_snapshot": decision.assessment_snapshot,
        "reviewer": {
            "id": decision.reviewer.id,
            "full_name": decision.reviewer.full_name,
            "email": decision.reviewer.email
        },
        "created_at": decision.created_at
    }


def report_row(claim):
    latest_run = latest_run_for(claim)
    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status,
        "claim_type": claim.claim_type,
        "item_name": claim.item_name,
        "reference_number": claim.reference_number,
        "incident_date": claim.incident_date,
        "incident_summary": claim.incident_summary,
        "claimant": claim.owner.full_name if claim.owner else "Legacy / unassigned",
        "claimant_email": claim.owner.email if claim.owner else None,
        "evidence_count": len(claim.evidence),
        "verification_runs": len(claim.verification_runs),
        "latest_run_status": latest_run.status if latest_run else None,
        "trust_assessment": trust_assessment_for(latest_run),
        "created_at": claim.created_at
    }


@router.get("/reviews/queue")
def get_review_queue(db: Session = Depends(get_db)):
    claims = db.query(Claim).order_by(Claim.id.desc()).all()
    queue = []

    for claim in claims:
        if claim.status in {"APPROVED", "REJECTED"}:
            continue

        run = latest_run_for(claim)
        trust_result = trust_result_for(run)

        if not run or not trust_result:
            continue

        if trust_result.get("assessment") != "REVIEW_NEEDED" and claim.status != "ESCALATED":
            continue

        latest_decision = (
            max(claim.review_decisions, key=lambda item: item.id)
            if claim.review_decisions
            else None
        )
        queue.append({
            "claim": {
                "id": claim.id,
                "claim_number": claim.claim_number,
                "status": claim.status,
                "evidence_count": len(claim.evidence),
                "claimant": (
                    claim.owner.full_name
                    if claim.owner
                    else "Legacy / unassigned"
                ),
                "claimant_email": claim.owner.email if claim.owner else None,
                "claimant_id": claim.owner.id if claim.owner else None,
                "created_at": claim.created_at
            },
            "run": {
                "id": run.id,
                "status": run.status,
                "pipeline_version": run.pipeline_version,
                "started_at": run.started_at,
                "completed_at": run.completed_at
            },
            "trust_assessment": trust_result,
            "decision_count": len(claim.review_decisions),
            "latest_decision": (
                serialize_decision(latest_decision)
                if latest_decision
                else None
            )
        })

    return {"claims": queue, "count": len(queue)}


@router.get("/claims/{claim_id}/decisions")
def get_claim_decisions(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(Claim, claim_id)

    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    decisions = (
        db.query(ReviewDecision)
        .filter(ReviewDecision.claim_id == claim_id)
        .order_by(ReviewDecision.id.desc())
        .all()
    )
    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "current_status": claim.status,
        "decisions": [serialize_decision(decision) for decision in decisions]
    }


@router.post("/claims/{claim_id}/decisions", status_code=201)
def create_claim_decision(
    claim_id: int,
    request: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_admin)
):
    claim = db.get(Claim, claim_id)

    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    if claim.status in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=409,
            detail="This claim already has a terminal review decision."
        )

    if claim.status == "ESCALATED" and request.action == "ESCALATE":
        raise HTTPException(status_code=409, detail="This claim is already escalated.")

    run = None
    if request.verification_run_id is not None:
        run = db.get(VerificationRun, request.verification_run_id)
        if run is None or run.claim_id != claim.id:
            raise HTTPException(
                status_code=400,
                detail="The verification run does not belong to this claim."
            )
    else:
        run = latest_run_for(claim)

    if run is None or run.status != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail="A completed verification run is required before review."
        )

    assessment = trust_result_for(run)
    if not assessment:
        raise HTTPException(
            status_code=409,
            detail="The selected run does not contain a trust assessment."
        )

    resulting_status = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "ESCALATE": "ESCALATED"
    }[request.action]
    previous_status = claim.status
    decision = ReviewDecision(
        claim_id=claim.id,
        verification_run_id=run.id,
        reviewer_id=reviewer.id,
        action=request.action,
        note=request.note,
        previous_status=previous_status,
        resulting_status=resulting_status,
        assessment_snapshot=assessment
    )
    claim.status = resulting_status
    db.add(decision)
    db.commit()
    db.refresh(decision)

    return {
        "message": f"Claim {resulting_status.lower()} successfully.",
        "claim_status": claim.status,
        "decision": serialize_decision(decision)
    }


@router.get("/reports/summary")
def get_report_summary(db: Session = Depends(get_db)):
    claims = db.query(Claim).order_by(Claim.id.desc()).all()
    rows = [report_row(claim) for claim in claims]
    status_distribution = Counter(row["status"] for row in rows)
    trust_distribution = Counter(
        row["trust_assessment"] or "NOT_ASSESSED"
        for row in rows
    )

    today = datetime.now(timezone.utc).date()
    activity = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        activity.append({
            "date": day.isoformat(),
            "claims": sum(
                1
                for claim in claims
                if claim.created_at and claim.created_at.date() == day
            )
        })

    total_evidence = sum(row["evidence_count"] for row in rows)
    total_runs = sum(row["verification_runs"] for row in rows)
    open_review_count = sum(
        1
        for row in rows
        if (row["trust_assessment"] == "REVIEW_NEEDED" or row["status"] == "ESCALATED")
        and row["status"] not in {"APPROVED", "REJECTED"}
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "metrics": {
            "total_claims": len(rows),
            "total_evidence": total_evidence,
            "verification_runs": total_runs,
            "review_needed": open_review_count,
            "completed_claims": sum(
                1 for row in rows
                if row["latest_run_status"] == "COMPLETED"
            ),
            "failed_claims": status_distribution["VERIFICATION_FAILED"]
        },
        "status_distribution": dict(status_distribution),
        "trust_distribution": dict(trust_distribution),
        "seven_day_activity": activity,
        "recent_claims": rows[:10]
    }


@router.get("/reports/claims.csv")
def export_claim_report(db: Session = Depends(get_db)):
    claims = db.query(Claim).order_by(Claim.id.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Claim ID",
        "Claim Number",
        "Status",
        "Claim Type",
        "Item or Product",
        "Reference Number",
        "Issue Date",
        "Claim Statement",
        "Claimant",
        "Claimant Email",
        "Evidence Count",
        "Verification Runs",
        "Latest Run Status",
        "Trust Assessment",
        "Created At"
    ])

    for claim in claims:
        row = report_row(claim)
        writer.writerow([
            row["id"],
            row["claim_number"],
            row["status"],
            row["claim_type"] or "",
            row["item_name"] or "",
            row["reference_number"] or "",
            row["incident_date"].isoformat() if row["incident_date"] else "",
            row["incident_summary"] or "",
            row["claimant"],
            row["claimant_email"] or "",
            row["evidence_count"],
            row["verification_runs"],
            row["latest_run_status"] or "",
            row["trust_assessment"] or "NOT_ASSESSED",
            row["created_at"].isoformat() if row["created_at"] else ""
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=trustlens-claims-report.csv"
            )
        }
    )


@router.get("/system")
def get_system_settings():
    database_engine = (
        "mongodb" if settings.database_backend == "mongodb"
        else settings.database_url.split(":", 1)[0]
    )
    ai_model_ready = settings.ai_generation_candidate_path.is_file()
    authenticity_model_ready = (
        settings.evidence_authenticity_candidate_path.is_file()
    )
    multiview_model_ready = settings.multiview_candidate_path.is_file()
    primary_tampering_ready = (
        multiview_model_ready
        if settings.detector_policy_mode == "HYBRID_V2"
        else authenticity_model_ready
    )
    resnet_shadow_ready = settings.resnet_shadow_candidate_path.is_file()
    return {
        "api_version": API_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "detector_policy_mode": settings.detector_policy_mode,
        "resnet_shadow_enabled": (
            settings.detector_policy_mode in HYBRID_MODES
            and settings.enable_resnet_shadow
        ),
        "fusion_policy_version": FUSION_POLICY["policy_version"],
        "fusion_policy_validated": FUSION_POLICY["validated"],
        "calibration_method": FUSION_POLICY["calibration"]["method"],
        "database_engine": database_engine,
        "maximum_upload_mb": settings.max_upload_bytes / (1024 * 1024),
        "accepted_upload_types": ["JPG", "JPEG", "PNG", "WEBP"],
        "access_token_minutes": settings.access_token_minutes,
        "ocr_configured": bool(settings.tesseract_path),
        "model_status": {
            "ai_generation_efficientnet": ai_model_ready,
            "authenticity_efficientnet": authenticity_model_ready,
            "forensic_multiview_efficientnet": multiview_model_ready,
            "tampering_resnet_shadow": resnet_shadow_ready,
            "primary_models_ready": (
                ai_model_ready and primary_tampering_ready
            )
        }
    }
