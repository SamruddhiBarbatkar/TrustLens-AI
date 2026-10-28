import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from app.core.security import get_current_user, require_claim_access
from app.db.database import get_db
from app.db.models import Claim, User


router = APIRouter(
    prefix="/claims",
    tags=["Claims"]
)


class ClaimDetailsInput(BaseModel):
    claim_type: Literal["WARRANTY", "INSURANCE", "OTHER"]
    item_name: str = Field(min_length=3, max_length=120)
    reference_number: str | None = Field(default=None, max_length=80)
    incident_date: date
    incident_summary: str = Field(min_length=20, max_length=1000)

    @field_validator("item_name", "reference_number", "incident_summary", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("incident_date")
    @classmethod
    def reject_future_date(cls, value):
        if value > date.today():
            raise ValueError("The issue date cannot be in the future.")
        return value


def apply_claim_details(claim, details):
    claim.claim_type = details.claim_type
    claim.item_name = details.item_name
    claim.reference_number = details.reference_number or None
    claim.incident_date = details.incident_date
    claim.incident_summary = details.incident_summary
    claim.intake_version = 2
    claim.updated_at = datetime.now(timezone.utc)


def serialize_claim_details(claim):
    return {
        "claim_type": claim.claim_type,
        "item_name": claim.item_name,
        "reference_number": claim.reference_number,
        "incident_date": claim.incident_date,
        "incident_summary": claim.incident_summary,
        "intake_version": claim.intake_version,
        "updated_at": claim.updated_at,
        "submitted_at": claim.submitted_at,
    }


def serialize_claimant(claim):
    if claim.owner is None:
        return None
    return {
        "id": claim.owner.id,
        "full_name": claim.owner.full_name,
        "email": claim.owner.email
    }


def serialize_evidence(evidence):
    return {
        "id": evidence.id,
        "type": evidence.evidence_type,
        "original_filename": evidence.original_filename,
        "description": evidence.description,
        "source_type": evidence.source_type,
        "captured_at": evidence.captured_at,
        "location_label": evidence.location_label,
        "file_size_bytes": evidence.file_size_bytes,
        "image_width": evidence.image_width,
        "image_height": evidence.image_height,
        "created_at": evidence.created_at
    }


def serialize_verification_run_summary(run, include_trust_details=True):
    trust_assessment = next(
        (
            analysis.result
            for analysis in run.analysis_results
            if (
                analysis.analysis_type == "TRUST_ASSESSMENT"
                and analysis.status == "COMPLETED"
            )
        ),
        None
    )

    if trust_assessment and not include_trust_details:
        trust_assessment = None

    return {
        "id": run.id,
        "status": run.status,
        "pipeline_version": run.pipeline_version,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "analysis_count": len(run.analysis_results),
        "trust_assessment": trust_assessment
    }


def serialize_claimant_decision(claim):
    if not claim.review_decisions:
        return None

    decision = max(claim.review_decisions, key=lambda item: item.id)
    return {
        "action": decision.action,
        "resulting_status": decision.resulting_status,
        "verification_run_id": decision.verification_run_id,
        "decided_at": decision.created_at,
        "message": decision.note
    }

@router.get("/")
def get_all_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Claim)

    if current_user.role != "ADMIN":
        query = query.filter(Claim.owner_id == current_user.id)

    claims = query.order_by(Claim.id.desc()).all()

    return {
        "claims": [
            {
                "id": claim.id,
                "claim_number": claim.claim_number,
                "status": claim.status,
                "created_at": claim.created_at,
                **serialize_claim_details(claim),
                "evidence_count": len(claim.evidence),
                "claimant": serialize_claimant(claim),
                "review_decision": serialize_claimant_decision(claim),
                "verification_runs": [
                    serialize_verification_run_summary(
                        run,
                        include_trust_details=(
                            current_user.role == "ADMIN"
                            or claim.status in {"APPROVED", "REJECTED"}
                        )
                    )
                    for run in sorted(
                        claim.verification_runs,
                        key=lambda item: item.id,
                        reverse=True
                    )
                ],
            }
            for claim in claims
        ]
    }

@router.post("/")
def create_claim(
    details: ClaimDetailsInput | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    

    claim_number = (
        f"TL-{uuid.uuid4().hex[:8].upper()}"
    )

    claim = Claim(
        claim_number=claim_number,
        status="PENDING",
        owner_id=current_user.id
    )
    if details is not None:
        apply_claim_details(claim, details)

    db.add(claim)
    db.commit()
    db.refresh(claim)

    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status,
        **serialize_claim_details(claim),
        "evidence": [],
        "message": "Claim created successfully"
    }


@router.put("/{claim_id}/details")
def update_claim_details(
    claim_id: int,
    details: ClaimDetailsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = db.get(Claim, claim_id)
    require_claim_access(claim, current_user)
    if current_user.role == "ADMIN":
        raise HTTPException(status_code=403, detail="Only the claimant can edit claim details.")
    if claim.status != "PENDING":
        raise HTTPException(status_code=409, detail="Claim details cannot be changed after submission.")
    apply_claim_details(claim, details)
    db.commit()
    db.refresh(claim)
    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status,
        **serialize_claim_details(claim),
        "message": "Draft details saved.",
    }


@router.post("/{claim_id}/submit")
def submit_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    claim = db.get(Claim, claim_id)
    require_claim_access(claim, current_user)

    if current_user.role == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Claims must be submitted by their claimant."
        )

    if claim.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Only pending claims can be submitted."
        )

    if not claim.evidence:
        raise HTTPException(
            status_code=400,
            detail="Upload at least one evidence image before submitting."
        )

    if claim.intake_version >= 2 and not all((
        claim.claim_type,
        claim.item_name,
        claim.incident_date,
        claim.incident_summary,
    )):
        raise HTTPException(status_code=400, detail="Complete the claim details before submitting.")

    claim.status = "SUBMITTED"
    claim.submitted_at = datetime.now(timezone.utc)
    claim.updated_at = claim.submitted_at
    db.commit()
    db.refresh(claim)

    return {
        "message": "Claim submitted for administrator verification.",
        "id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status
    }


@router.get("/{claim_id}")
def get_claim(
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

    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status,
        "created_at": claim.created_at,
        **serialize_claim_details(claim),
        "claimant": serialize_claimant(claim),
        "review_decision": serialize_claimant_decision(claim),
        "evidence": [serialize_evidence(evidence) for evidence in claim.evidence],
        "verification_runs": [
            serialize_verification_run_summary(
                run,
                include_trust_details=(
                    current_user.role == "ADMIN"
                    or claim.status in {"APPROVED", "REJECTED"}
                )
            )
            for run in sorted(
                claim.verification_runs,
                key=lambda item: item.id,
                reverse=True
            )
        ]
    }
