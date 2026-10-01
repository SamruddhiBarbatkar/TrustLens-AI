from typing import Literal

from pydantic import BaseModel, Field


class AIGenerationPrediction(BaseModel):
    """Verified EfficientNet-B0 output without an unvalidated provenance claim."""

    class_index: Literal[0, 1]
    label: Literal["fake", "real"]
    top_class_softmax_score: float = Field(ge=0, le=1)
    preprocessing_note: str
