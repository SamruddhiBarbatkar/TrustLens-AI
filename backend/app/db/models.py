from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Date
)

from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from sqlalchemy import JSON, func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="CLAIMANT", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    claims = relationship("Claim", back_populates="owner")
    review_decisions = relationship(
        "ReviewDecision",
        back_populates="reviewer"
    )


class Claim(Base):
    __tablename__ = "claims"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    status = Column(
        String,
        default="PENDING",
        nullable=False
    )

    claim_type = Column(String(24), nullable=True)
    item_name = Column(String(120), nullable=True)
    reference_number = Column(String(80), nullable=True)
    incident_date = Column(Date, nullable=True)
    incident_summary = Column(Text, nullable=True)
    intake_version = Column(Integer, nullable=False, default=1, server_default="1")
    updated_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    evidence = relationship(
        "Evidence",
        back_populates="claim",
        cascade="all, delete-orphan"
    )

    verification_runs = relationship(
        "VerificationRun",
        back_populates="claim",
        cascade="all, delete-orphan"
    )

    owner = relationship(
        "User",
        back_populates="claims"
    )

    review_decisions = relationship(
        "ReviewDecision",
        back_populates="claim",
        cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False
    )

    evidence_type = Column(
        String,
        nullable=False
    )

    original_filename = Column(
        String,
        nullable=False
    )

    stored_filename = Column(
        String,
        nullable=False
    )

    file_path = Column(
        String,
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    source_type = Column(
        String,
        nullable=True
    )

    captured_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    location_label = Column(
        String,
        nullable=True
    )

    file_size_bytes = Column(
        Integer,
        nullable=True
    )

    image_width = Column(
        Integer,
        nullable=True
    )

    image_height = Column(
        Integer,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    claim = relationship(
        "Claim",
        back_populates="evidence"
    )

    analysis_results = relationship(
        "AnalysisResult",
        back_populates="evidence",
        cascade="all, delete-orphan"
    )


class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False
    )

    status = Column(
        String,
        default="PENDING",
        nullable=False
    )

    pipeline_version = Column(
        String,
        default="0.1.0",
        nullable=False
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    claim = relationship(
        "Claim",
        back_populates="verification_runs"
    )

    analysis_results = relationship(
        "AnalysisResult",
        back_populates="verification_run",
        cascade="all, delete-orphan"
    )

    review_decisions = relationship(
        "ReviewDecision",
        back_populates="verification_run"
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    verification_run_id = Column(
        Integer,
        ForeignKey("verification_runs.id"),
        nullable=False
    )

    evidence_id = Column(
        Integer,
        ForeignKey("evidence.id"),
        nullable=True
    )

    analysis_type = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        default="PENDING",
        nullable=False
    )

    result = Column(
        JSON,
        nullable=True
    )

    message = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    verification_run = relationship(
        "VerificationRun",
        back_populates="analysis_results"
    )

    evidence = relationship(
        "Evidence",
        back_populates="analysis_results"
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(
        Integer,
        ForeignKey("claims.id"),
        nullable=False,
        index=True
    )
    verification_run_id = Column(
        Integer,
        ForeignKey("verification_runs.id"),
        nullable=False
    )
    reviewer_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    action = Column(String, nullable=False)
    note = Column(Text, nullable=False)
    previous_status = Column(String, nullable=False)
    resulting_status = Column(String, nullable=False)
    assessment_snapshot = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    claim = relationship("Claim", back_populates="review_decisions")
    verification_run = relationship(
        "VerificationRun",
        back_populates="review_decisions"
    )
    reviewer = relationship("User", back_populates="review_decisions")
