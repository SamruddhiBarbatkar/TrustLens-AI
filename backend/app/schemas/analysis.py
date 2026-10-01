from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from app.schemas.trust_score import TrustScore
from app.schemas.xai import AnalysisExplanation


class AnalysisSignal(BaseModel):
    """One analysis signal and its controlled execution state."""

    status: Literal["available", "unavailable", "failed"]
    result: dict[str, Any] | None = None
    message: str | None = None


class AnalysisResponse(BaseModel):
    """Persisted result for an authenticated user's image analysis."""

    id: str
    created_at: datetime
    signals: dict[str, AnalysisSignal]
    trust_score: TrustScore | None = None
    explanation: AnalysisExplanation | None = None
    report_title: str | None = None
    source_image_available: bool = False


class ReportTitleUpdate(BaseModel):
    """Owner-provided display title for a saved report."""

    report_title: str

    @field_validator("report_title")
    @classmethod
    def normalize_report_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Report title cannot be empty.")
        if len(normalized) > 120:
            raise ValueError("Report title must be 120 characters or fewer.")
        return normalized


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisResponse]
    limit: int
    offset: int
