from datetime import datetime

from pydantic import BaseModel

from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.schemas.xai import AnalysisExplanation


class AnalysisInDatabase(BaseModel):
    """Private persisted analysis, including the server-derived owner identifier."""

    id: str
    owner_id: str
    created_at: datetime
    signals: dict[str, AnalysisSignal]
    trust_score: TrustScore | None = None
    explanation: AnalysisExplanation | None = None
    report_title: str | None = None
    image_artifact_filename: str | None = None
