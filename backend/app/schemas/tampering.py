from typing import Literal

from pydantic import BaseModel, Field


class TamperingPrediction(BaseModel):
    """Verified ResNet18 output without an unvalidated authenticity claim."""

    class_index: Literal[0, 1]
    label: Literal["authentic", "tampered"]
    top_class_softmax_score: float = Field(ge=0, le=1)
    preprocessing_note: str
    gradcam_data_url: str | None = None
